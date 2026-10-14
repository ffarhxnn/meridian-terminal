import os, json, sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Annotated
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
app = FastAPI(title='Meridian personal terminal')
app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5173','http://localhost:5173'], allow_methods=['*'], allow_headers=['*'])
ASSETS = [
 ('SPY','S&P 500 ETF','Equities'),('QQQ','Nasdaq 100 ETF','Equities'),
 ('AAPL','Apple Inc.','Equities'),('MSFT','Microsoft Corp.','Equities'),
 ('NVDA','NVIDIA Corp.','Equities'),('BTC','Bitcoin','Crypto'),
 ('ETH','Ethereum','Crypto'),('EUR/USD','Euro / US Dollar','FX'),
 ('GBP/USD','British Pound / US Dollar','FX'),('DGS10','US 10Y Treasury par yield (Treasury)','Macro'),
 ('CPIAUCSL','US consumer price index','Macro'),('GLD','Gold ETF','Equities'),
 ('AUD/USD','Australian Dollar / US Dollar','FX'),('NZD/USD','New Zealand Dollar / US Dollar','FX'),
 ('USD/JPY','US Dollar / Japanese Yen','FX'),('USD/CHF','US Dollar / Swiss Franc','FX'),
 ('USD/CAD','US Dollar / Canadian Dollar','FX'),('EUR/GBP','Euro / British Pound','FX'),('EUR/JPY','Euro / Japanese Yen','FX'),
 ('^GSPC','S&P 500 Index','Indices'),('^IXIC','Nasdaq Composite','Indices'),('^DJI','Dow Jones Industrial Average','Indices'),
 ('^FTSE','FTSE 100','Indices'),('^GDAXI','DAX','Indices'),('^N225','Nikkei 225','Indices'),
 ('^HSI','Hang Seng Index','Indices'),('^STOXX50E','EURO STOXX 50','Indices')]

def db():
 c=sqlite3.connect(os.getenv('DB_PATH','terminal.sqlite3'), timeout=15)
 c.row_factory=sqlite3.Row
 c.executescript('CREATE TABLE IF NOT EXISTS instruments (symbol TEXT PRIMARY KEY, name TEXT, asset_class TEXT); CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, payload TEXT, expires REAL); CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY, symbol TEXT, qty REAL, price REAL, timestamp TEXT); CREATE TABLE IF NOT EXISTS fill_sources (trade_id INTEGER PRIMARY KEY, source TEXT, as_of TEXT, mode TEXT);')
 return c
def now(): return datetime.now(timezone.utc).isoformat()
def all_assets():
 with db() as c:extra=[tuple(r) for r in c.execute('SELECT * FROM instruments ORDER BY symbol')]
 return ASSETS+extra

def asset(symbol):
 for a in all_assets():
  if a[0]==symbol: return a
 raise HTTPException(404,'Unknown symbol')
from backend.feeds import Cache, quote_provider, history_provider, fundamentals_provider, feed_provider, FEEDS
import asyncio
cache=Cache(db)

def empty_quote(a):
 return dict(symbol=a[0],name=a[1],asset_class=a[2],price=None,change_pct=None,source='Not available',source_url=None,as_of=None,retrieved_at=None,unit='percent' if a[0]=='DGS10' else 'index' if a[2]=='Macro' else a[0].split('/')[1] if a[2]=='FX' else 'points' if a[2]=='Indices' else 'USD',freshness='Unavailable',change_period='unavailable')

async def quote(symbol,background=False):
 a=asset(symbol)
 return await cache.fetch('public:v3:quote:'+symbol,lambda:quote_provider(a),120 if a[2]=='Crypto' else 21600 if a[2] in ('Macro','FX') else 900,empty_quote(a),background=background)

@app.get('/api/health')
def health(): return {'ok':True,'mode':'public','refresh_seconds':120}

@app.get('/api/markets')
async def markets():
 # Bound concurrency while provider/cache layers deduplicate resources.
 semaphore=asyncio.Semaphore(3)
 async def read(a):
  async with semaphore:return await quote(a[0],background=True)
 return await asyncio.gather(*(read(a) for a in all_assets()))

@app.get('/api/history/{symbol:path}')
async def history(symbol: str, days: Annotated[int, Query(ge=7,le=365)] = 90):
 a=asset(symbol)
 return await cache.fetch('public:v5:history:'+symbol+':'+str(days),lambda:history_provider(a,days),21600 if a[2]=='Macro' else 3600,{'points':[],'source':'Not available','as_of':None,'source_url':None})

@app.get('/api/fundamentals/{symbol:path}')
async def fundamentals(symbol: str):
 a=asset(symbol)
 return await cache.fetch('public:v3:fundamentals:'+symbol,lambda:fundamentals_provider(a),86400 if os.getenv('ALPHA_VANTAGE_API_KEY') else 900,{'metrics':{'Coverage':'Unavailable; an Alpha Vantage key is required for company data'},'source':'Not available','as_of':None})

@app.get('/api/news')
async def news(symbol: str | None = None):
 results=await asyncio.gather(*[cache.fetch('public:v3:news:'+publisher,lambda p=publisher,u=url,d=domain:feed_provider(p,u,d),300,{'items':[],'source':publisher,'as_of':None},background=True) for publisher,url,domain in FEEDS])
 items=[]; seen=set()
 for result in results:
  for entry in result['items'][:10]:
   if entry['url'] not in seen:
    items.append({**entry,'mode':result['mode']});seen.add(entry['url'])
 items.sort(key=lambda x:x['published_at'] or '',reverse=True)
 items=[{**entry,'id':i+1} for i,entry in enumerate(items[:40])]
 if symbol is not None:
  asset(symbol)
  from backend.analytics import rank_news
  items=rank_news(items,symbol,name=asset(symbol)[1])
 return {'mode':'provider' if all(r['mode']=='provider' for r in results) else 'partial','refreshing':any(r.get('refreshing',False) for r in results),'items':items,'feeds':[{'publisher':r['source'],'mode':r['mode'],'warning':r.get('warning'),'refreshing':r.get('refreshing',False)} for r in results],'as_of':now(),'note':'Publisher RSS headlines and summaries; full articles not fetched. Refreshed every five minutes.'}

class Question(BaseModel):
 question: str=Field(min_length=1,max_length=2000)
 symbol: str='SPY'

@app.post('/api/research')
async def research(body: Question):
 q=await quote(body.symbol); wire=await news()
 sources=[]
 if q['price'] is not None:
  sources.append({'id':1,'title':q['symbol']+' — '+q['source'],'url':q['source_url'],'published_at':q['as_of'],'summary':f"Observed price {q['price']} {q['unit']}; mode {q['mode']}; {q['freshness']}. Change period: {q['change_period']}.",'publisher':q['source'],'evidence_scope':'Retrieved market observation'})
 from backend import statements as sec_statements
 if body.symbol in sec_statements.CIKS and any(term in body.question.lower() for term in ('revenue','earnings','financial','balance sheet','cash flow','fundamental','income','assets','profit','statement')):
  financials=await cache.fetch('public:v1:statements:'+body.symbol,lambda:sec_statements.provider(body.symbol),21600,{'metrics':[],'source':'SEC EDGAR','as_of':None})
  for metric in financials.get('metrics',[])[:6]:
   if metric.get('value') is None:continue
   sources.append({'id':len(sources)+1,'title':body.symbol+' — SEC annual '+metric['label'],'url':metric['source_url'],
    'published_at':metric.get('filed'),'publisher':'SEC EDGAR','mode':financials['mode'],'evidence_scope':'Selected reported annual US-GAAP fact',
    'summary':f"{metric['label']}: {metric['value']} {metric['unit']}; period {metric.get('start') or 'balance at'} to {metric['end']}; filed {metric.get('filed')}; {metric['tag']}; source state {financials['mode']}. Annual reported fact, not a current quote or TTM estimate."})
 from backend.analytics import rank_news
 for article in rank_news(wire['items'],body.symbol,body.question,q['name'])[:5]: sources.append({**article,'id':len(sources)+1})
 context=json.dumps(sources,ensure_ascii=False)
 answer=('Available evidence for '+body.symbol+':\n'+'\n'.join(f"[{s['id']}] {s['title']} ({s.get('published_at') or 'publication time unavailable'}). {s['summary']}" for s in sources)+'\nThese are retrieved observations and publisher feed summaries and any identified SEC annual facts, not full articles. The market/policy news feed is not a company-specific causal analysis and does not establish causes of price moves.') if sources else 'No retrievable evidence is currently available. No research conclusion can be supported.'
 engine='Retrieved evidence digest (no model configured)'
 try:
  from backend.research import synthesize
  synthesis,provider=await synthesize(body.question,body.symbol,sources)
  if synthesis:
   answer=synthesis;engine=provider.title()+' synthesis • retrieved evidence with citations'
 except (httpx.HTTPError,KeyError,IndexError,TypeError,ValueError):engine='Retrieved evidence digest • AI unavailable or citations invalid'
 return {'answer':answer,'sources':sources,'engine':engine,'as_of':now()}

class Order(BaseModel):
 symbol: str
 side: str
 quantity: float=Field(gt=0,le=100000,allow_inf_nan=False)
def portfolio_data(c):
 rows=c.execute("SELECT trades.*, COALESCE(fill_sources.source, 'Legacy synthetic fill') AS source, fill_sources.as_of AS observation_at FROM trades LEFT JOIN fill_sources ON trades.id=fill_sources.trade_id ORDER BY trades.id").fetchall(); positions={}; cash=100000.0
 for r in rows:
  positions[r['symbol']]=positions.get(r['symbol'],0)+r['qty']; cash-=r['qty']*r['price']
 return {'cash':cash,'positions':[{'symbol':s,'quantity':q} for s,q in positions.items() if q>1e-8],'trades':[dict(r) for r in rows]}
@app.get('/api/portfolio')
def portfolio():
 with db() as c: return portfolio_data(c)
@app.post('/api/orders')
async def order(body: Order):
 a=asset(body.symbol)
 if a[2]=='Macro': raise HTTPException(400,'Economic series cannot be traded')
 if body.side not in ['buy','sell']: raise HTTPException(400,'Side must be buy or sell')
 q=await quote(body.symbol)
 if q.get('unit')!='USD':raise HTTPException(400,'USD paper account supports USD-quoted instruments only; cross-currency accounting is not implemented')
 if q['price'] is None or q['mode']!='provider': raise HTTPException(409,'A currently available provider observation is required for a paper fill')
 price=q['price']; qty=body.quantity*(1 if body.side=='buy' else -1)
 with db() as c:
  c.execute('BEGIN IMMEDIATE'); p=portfolio_data(c)
  held=next((r['quantity'] for r in p['positions'] if r['symbol']==body.symbol),0)
  if qty>0 and qty*price>p['cash']+1e-8: raise HTTPException(400,'Insufficient paper cash')
  if qty<0 and -qty>held+1e-8: raise HTTPException(400,'Insufficient paper holdings; shorting disabled')
  result=c.execute('INSERT INTO trades(symbol,qty,price,timestamp) VALUES (?,?,?,?)',(body.symbol,qty,price,now()))
  c.execute('INSERT INTO fill_sources VALUES (?,?,?,?)',(result.lastrowid,q['source'],q['as_of'],q['mode']))
  return {**portfolio_data(c),'execution_mode':'paper observation','fill_price':price,'source':q['source'],'as_of':q['as_of']}

from backend.extensions import register
register(app,db,cache,quote,history,asset,now)

from backend.calculators import register as register_calculators
register_calculators(app)

from backend.catalog import register as register_catalog
register_catalog(app,db,asset,all_assets)

from backend.calendar import register as register_calendar
register_calendar(app,cache)

from backend.status import register as register_status
register_status(app,db,all_assets)

from backend.statements import register as register_statements
register_statements(app,cache,asset)
