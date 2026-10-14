"""Public read-only market and RSS adapters. Never fabricate missing observations."""
import asyncio
import html
import json
import math
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
import httpx
from zoneinfo import ZoneInfo

TREASURY_URL='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml'
TREASURY_DOC='https://home.treasury.gov/treasury-daily-interest-rate-xml-feed'
BLS_URL='https://api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SA0'
_memo={}
_memo_locks={}

async def memoized(key,loader,ttl):
    lock=_memo_locks.setdefault(key,asyncio.Lock())
    async with lock:
        entry=_memo.get(key)
        if entry and time.monotonic()-entry[0]<ttl:return entry[1]
        value=await loader()
        _memo[key]=(time.monotonic(),value)
        return value

def parse_treasury(content):
    root=ET.fromstring(content)
    ns={'m':'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata','d':'http://schemas.microsoft.com/ado/2007/08/dataservices'}
    points=[]
    for p in root.findall('.//m:properties',ns):
        date=p.findtext('d:NEW_DATE',namespaces=ns)
        value=p.findtext('d:BC_10YEAR',namespaces=ns)
        if date and value: points.append({'date':date[:10],'value':number(value)})
    return sorted(points,key=lambda x:x['date'])

def parse_bls(data):
    if data.get('status')!='REQUEST_SUCCEEDED': raise ValueError('BLS request not successful')
    points=[]
    series=data['Results']['series'][0]
    if series['seriesID']!='CUSR0000SA0': raise ValueError('Unexpected BLS series')
    for row in series['data']:
        period=row['period']
        # M13 is an annual average, not a month. Date denotes the reference month.
        if period.startswith('M') and 1<=int(period[1:])<=12 and row['value'] not in ('-', '.', '', 'N/A'):
            points.append({'date':f"{row['year']}-{period[1:]}-01",'value':number(row['value'])})
    return sorted(points,key=lambda x:x['date'])

async def _macro_series(symbol):
    if symbol=='DGS10':
        year=datetime.now(timezone.utc).year
        points=parse_treasury((await get(TREASURY_URL,{'data':'daily_treasury_yield_curve','field_tdr_date_value':str(year)})).content)
        # Include prior year to cover the early-January lookback.
        if not points or points[0]['date']>(datetime.now(timezone.utc)-timedelta(days=365)).date().isoformat():
            points=parse_treasury((await get(TREASURY_URL,{'data':'daily_treasury_yield_curve','field_tdr_date_value':str(year-1)})).content)+points
        return {'points':points,'source':'U.S. Treasury • 10-year daily par yield','source_url':TREASURY_DOC,'definition':'Treasury 10-year par yield; keyless alternative to FRED DGS10, not the FRED series','frequency':'business daily'}
    data=(await get(BLS_URL)).json()
    return {'points':parse_bls(data),'source':'BLS • CUSR0000SA0','source_url':'https://data.bls.gov/timeseries/CUSR0000SA0','definition':'CPI-U, all items, U.S. city average, seasonally adjusted; 1982–84=100. Date is reference month, not release date. Subject to revision.','frequency':'monthly'}

async def macro_series(symbol):
    return await memoized('macro:'+symbol,lambda:_macro_series(symbol),21600)

def parse_equity_chart(data,symbol):
    chart=data['chart']
    if chart.get('error'): raise ValueError('Equity chart provider error')
    result=chart['result'][0]; meta=result['meta']
    if meta['symbol'].upper()!=symbol or meta.get('currency')!='USD': raise ValueError('Unexpected equity symbol/currency')
    zone=ZoneInfo(meta.get('exchangeTimezoneName','America/New_York'))
    points=[]
    bars=result['indicators']['quote'][0]
    for index,(stamp,close) in enumerate(zip(result.get('timestamp',[]),bars['close'])):
        if close is not None:
            date=datetime.fromtimestamp(stamp,zone).date().isoformat()
            point={'date':date,'value':number(close)}
            for key in ('open','high','low','volume'):
                values=bars.get(key,[])
                if index<len(values) and values[index] is not None:point[key]=number(values[index])
            points.append(point)
    return meta, sorted(points,key=lambda x:x['date'])

async def _equity_series(symbol):
    # Public website endpoint, not a supported/sla-backed API. No cookies, tokens,
    # browser impersonation, authentication bypass, or retries after denial.
    url='https://query1.finance.yahoo.com/v8/finance/chart/'+symbol
    data=(await get(url,{'range':'1y','interval':'1d'})).json()
    meta,points=parse_equity_chart(data,symbol)
    return meta,points,'https://finance.yahoo.com/quote/'+symbol+'/history/'

async def equity_series(symbol):
    return await memoized('equity:'+symbol,lambda:_equity_series(symbol),900)

def now(): return datetime.now(timezone.utc).isoformat()

from backend.transport import get


def number(value):
    n = float(value)
    if not math.isfinite(n): raise ValueError('Nonfinite provider observation')
    return n

def credentials(name):
    key = os.getenv(name)
    if not key: raise ValueError(name+' required; configure it in terminal/.env')
    return key

async def av(function, symbol):
    r = await get('https://www.alphavantage.co/query', {'function':function,'symbol':symbol,'apikey':credentials('ALPHA_VANTAGE_API_KEY')})
    data = r.json()
    if any(k in data for k in ['Information','Note','Error Message']):
        raise ValueError('Alpha Vantage quota, entitlement or symbol error')
    return data

async def quote_provider(a):
    symbol,name,kind,*_ = a
    q = dict(symbol=symbol,name=name,asset_class=kind,price=None,change_pct=None,mode='provider',retrieved_at=now(),unit='percent' if symbol=='DGS10' else 'index' if kind=='Macro' else 'USD')
    if kind=='Crypto':
        base='https://api.exchange.coinbase.com/products/'+symbol+'-USD'
        ticker, stats = await asyncio.gather(get(base+'/ticker'),get(base+'/stats'))
        t,s=ticker.json(),stats.json()
        q.update(price=number(t['price']),change_pct=(number(t['price'])/number(s['open'])-1)*100,as_of=t['time'],source='Coinbase Exchange',source_url=base+'/ticker',freshness='Exchange last trade; polled',change_period='24h')
    elif kind=='FX':
        start=(datetime.now(timezone.utc)-timedelta(days=10)).date().isoformat()
        url='https://api.frankfurter.dev/v1/'+start+'..'
        data=(await get(url,{'base':symbol[:3],'symbols':'USD'})).json()
        dates=sorted(data['rates']); last,prev=dates[-1],dates[-2]
        p=number(data['rates'][last]['USD']); old=number(data['rates'][prev]['USD'])
        q.update(price=p,change_pct=(p/old-1)*100,as_of=last,source='Frankfurter / ECB',source_url='https://frankfurter.dev/v1/',freshness='Daily reference rate; not a tradable quote',change_period='previous published day')
    elif kind=='Macro':
        series=await macro_series(symbol)
        last=series['points'][-1]
        q.update(price=last['value'],as_of=last['date'],source=series['source'],source_url=series['source_url'],freshness=series['definition'],change_period='not comparable')
    else:
        if os.getenv('ALPHA_VANTAGE_API_KEY'):
            data=await av('GLOBAL_QUOTE',symbol); v=data['Global Quote']
            q.update(price=number(v['05. price']),change_pct=number(v['10. change percent'].strip('%')),as_of=v['07. latest trading day'],source='Alpha Vantage',source_url='https://www.alphavantage.co/documentation/#latestprice',freshness='Latest trading day / delayed; account entitlement applies',change_period='previous trading close')
        else:
            meta,points,url=await equity_series(symbol)
            price=number(meta['regularMarketPrice'])
            date=datetime.fromtimestamp(meta['regularMarketTime'],timezone.utc).isoformat()
            localdate=datetime.fromtimestamp(meta['regularMarketTime'],ZoneInfo(meta.get('exchangeTimezoneName','America/New_York'))).date().isoformat()
            prior=[p for p in points if p['date']<localdate]
            previous=prior[-1]['value'] if prior else None
            q.update(price=price,change_pct=(price/previous-1)*100 if previous else None,as_of=date,source='Yahoo Finance • public website data',source_url=url,freshness='Delayed/indicative; best-effort unsupported website endpoint; no real-time guarantee',change_period='previous available daily close')
    if q['price']<=0: raise ValueError('Nonpositive provider price')
    return q

async def history_provider(a,days=100):
    symbol,_,kind,*_=a
    since=(datetime.now(timezone.utc)-timedelta(days=days)).date().isoformat()
    if kind=='Crypto':
        url='https://api.exchange.coinbase.com/products/'+symbol+'-USD/candles'
        start=datetime.fromisoformat(since).replace(tzinfo=timezone.utc);end=datetime.now(timezone.utc);data=[]
        # Coinbase limits each response to 300 candles. Request bounded windows.
        while start<end:
            stop=min(start+timedelta(days=290),end)
            data.extend((await get(url,{'granularity':86400,'start':start.isoformat(),'end':stop.isoformat()})).json())
            start=stop
        # Exclude the still-open UTC daily candle.
        today=datetime.now(timezone.utc).date().isoformat()
        points=[{'date':datetime.fromtimestamp(x[0],timezone.utc).date().isoformat(),'value':number(x[4]),'open':number(x[3]),'high':number(x[2]),'low':number(x[1]),'volume':number(x[5])} for x in data]
        points=sorted({p['date']:p for p in points if since<=p['date']<today}.values(),key=lambda p:p['date'])
        source='Coinbase Exchange • completed UTC daily closes'
    elif kind=='FX':
        url='https://api.frankfurter.dev/v1/'+since+'..'
        data=(await get(url,{'base':symbol[:3],'symbols':'USD'})).json()
        points=[{'date':date,'value':number(rate['USD'])} for date,rate in sorted(data['rates'].items())]
        source='Frankfurter / ECB • daily reference rates'
    elif kind=='Macro':
        series=await macro_series(symbol)
        points=[p for p in series['points'] if p['date']>=since]
        source=series['source']+' • '+series['definition'];url=series['source_url']
    else:
        if os.getenv('ALPHA_VANTAGE_API_KEY'):
            data=await av('TIME_SERIES_DAILY',symbol)
            points=[{'date':date,'value':number(v['4. close'])} for date,v in sorted(data['Time Series (Daily)'].items()) if date>=since]
            source='Alpha Vantage • daily closes, unadjusted'
            url='https://www.alphavantage.co/documentation/#daily'
        else:
            meta,points,url=await equity_series(symbol)
            today=datetime.now(ZoneInfo(meta.get('exchangeTimezoneName','America/New_York'))).date().isoformat()
            points=[p for p in points if since<=p['date']<today]
            source='Yahoo Finance • daily closes; delayed, best-effort website data; current session excluded'
    if not points: raise ValueError('No historical observations returned')
    return {'points':points,'source':source,'source_url':url,'mode':'provider','as_of':points[-1]['date'],'retrieved_at':now()}

async def fundamentals_provider(a):
    if a[2]!='Equities':
        return {'metrics':{'Asset class':a[2],'Coverage':'Financial statements do not apply to this instrument'},'source':'Instrument directory','mode':'metadata','as_of':None}
    if not os.getenv('ALPHA_VANTAGE_API_KEY'):
        meta,_,url=await equity_series(a[0])
        return {'metrics':{'Coverage':'Market reference data, not company financial statements',
                'Exchange':meta.get('fullExchangeName',meta.get('exchangeName','Unavailable')),
                'Currency':meta.get('currency','Unavailable'),
                '52-week high':str(meta.get('fiftyTwoWeekHigh','Unavailable')),
                '52-week low':str(meta.get('fiftyTwoWeekLow','Unavailable')),
                'Session volume':str(meta.get('regularMarketVolume','Unavailable'))},
                'source':'Yahoo Finance public website • market reference data','source_url':url,'mode':'provider',
                'as_of':datetime.fromtimestamp(meta['regularMarketTime'],timezone.utc).isoformat(),'retrieved_at':now()}
    data=await av('OVERVIEW',a[0])
    if not data.get('Symbol'): raise ValueError('No company overview available (ETF or provider coverage)')
    return {'metrics':{label:str(data.get(key,'Unavailable')) for label,key in [('Market capitalization (USD)','MarketCapitalization'),('P/E ratio','PERatio'),('Sector','Sector'),('Currency','Currency'),('Fiscal year end','FiscalYearEnd'),('Latest fiscal quarter','LatestQuarter')]},'source':'Alpha Vantage • company overview','source_url':'https://www.alphavantage.co/documentation/#company-overview','mode':'provider','as_of':data.get('LatestQuarter'),'retrieved_at':now()}

# Fixed provider allowlist: no arbitrary URLs are fetched from user/model input.
FEEDS=[('Federal Reserve','https://www.federalreserve.gov/feeds/press_all.xml','federalreserve.gov'),('SEC','https://www.sec.gov/news/pressreleases.rss','sec.gov'),('CNBC Top News','https://www.cnbc.com/id/100003114/device/rss/rss.html','cnbc.com'),('BBC News Business','https://feeds.bbci.co.uk/news/business/rss.xml',('bbc.co.uk','bbc.com'))]
def plain(text): return html.unescape(re.sub('<[^>]*>',' ',text or '')).strip()
def parse_feed(content, publisher, domain):
    root=ET.fromstring(content)
    items=[]
    for node in root.findall('./channel/item')[:20]:
        url=(node.findtext('link') or '').strip(); parsed=urlparse(url)
        domains=(domain,) if isinstance(domain,str) else domain
        if parsed.scheme!='https' or not any(parsed.hostname==d or (parsed.hostname or '').endswith('.'+d) for d in domains): continue
        raw=node.findtext('pubDate') or node.findtext('{http://purl.org/dc/elements/1.1/}date')
        try:
            date=parsedate_to_datetime(raw) if raw else None
        except (ValueError,TypeError):
            try: date=datetime.fromisoformat(raw.replace('Z','+00:00')) if raw else None
            except ValueError: date=None
        title=plain(node.findtext('title'))
        if not title: continue
        items.append({'title':title,'url':url,'publisher':publisher,'published_at':date.astimezone(timezone.utc).isoformat() if date and date.tzinfo else None,'summary':plain(node.findtext('description'))[:1200],'retrieved_at':now(),'evidence_scope':'RSS headline and publisher summary; full article not fetched'})
    if not items: raise ValueError('Feed contained no valid entries')
    return items

async def feed_provider(publisher,url,domain):
    response=await get(url)
    return {'items':parse_feed(response.content,publisher,domain),'mode':'provider','source':publisher,'as_of':now(),'retrieved_at':now()}

class Cache:
    def __init__(self, connection): self.connection=connection; self.locks={}
    async def fetch(self,key,loader,ttl,empty):
        # Single flight avoids duplicate upstream requests within this process.
        lock=self.locks.setdefault(key,asyncio.Lock())
        async with lock:
            with self.connection() as c: row=c.execute('SELECT * FROM cache WHERE key=?',(key,)).fetchone()
            if row and row['expires']>time.time(): return json.loads(row['payload'])
            try:
                result=await loader()
                with self.connection() as c: c.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)',(key,json.dumps(result),time.time()+ttl))
                return result
            except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError,ET.ParseError,ZeroDivisionError):
                if row and json.loads(row['payload']).get('mode') != 'unavailable':
                    result=json.loads(row['payload']); result.update(mode='stale',warning='Upstream unavailable; showing previously retrieved data')
                else:
                    result={**empty,'mode':'unavailable','warning':'Provider unavailable, quota exceeded or credentials missing. No synthetic fallback.'}
                # Back off even after failure; do not hammer an unavailable provider.
                with self.connection() as c: c.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)',(key,json.dumps(result),time.time()+60))
                return result
