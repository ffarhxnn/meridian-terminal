import re
from fastapi import HTTPException,Query
from pydantic import BaseModel,Field
from backend.feeds import get,quote_provider

class Instrument(BaseModel):
    symbol:str=Field(pattern=r'^[A-Z][A-Z0-9.-]{0,14}$')

def register(app,db,asset,all_assets):
    @app.get('/api/search')
    async def search(q:str=Query(min_length=1,max_length=60)):
        local=[{'symbol':a[0],'name':a[1],'type':a[2],'covered':True} for a in all_assets() if q.lower() in (a[0]+' '+a[1]).lower()]
        try:
            data=(await get('https://query1.finance.yahoo.com/v1/finance/search',{'q':q,'quotesCount':10,'newsCount':0})).json()
            covered={a[0] for a in all_assets()};results=local;seen={r['symbol'] for r in local}
            for row in data.get('quotes',[]):
                symbol=row.get('symbol','')
                if row.get('quoteType') not in ('EQUITY','ETF') or row.get('exchange') not in ('NMS','NYQ','PCX','NGM','NCM','BTS','ASE'):continue
                if symbol in seen or not re.fullmatch(r'[A-Z][A-Z0-9.-]{0,14}',symbol):continue
                results.append({'symbol':symbol,'name':row.get('shortname') or row.get('longname') or symbol,'type':row['quoteType'],'covered':symbol in covered});seen.add(symbol)
            return {'items':results,'source':'Local catalog + Yahoo Finance public website search','warning':'Best-effort website search. Only U.S.-listed equities/ETFs are eligible; USD coverage is validated before adding.'}
        except Exception as e:
            import httpx
            if not isinstance(e,(httpx.HTTPError,ValueError,KeyError,TypeError)):raise
            return {'items':local,'source':'Local catalog','warning':'External website search unavailable; showing local matches only.'}

    @app.post('/api/universe')
    async def add(body:Instrument):
        try:
            existing=asset(body.symbol)
            return {'symbol':existing[0],'name':existing[1],'added':False}
        except HTTPException as e:
            if e.status_code!=404:raise
        with db() as c:
            if c.execute('SELECT COUNT(*) FROM instruments').fetchone()[0]>=30:raise HTTPException(400,'30 additional instruments limit keeps public-provider traffic bounded')
        # Validate symbol, USD currency and a real price using the existing provider.
        try:q=await quote_provider((body.symbol,body.symbol,'Equities'))
        except Exception as e:
            import httpx
            if not isinstance(e,(httpx.HTTPError,ValueError,KeyError,IndexError,TypeError)):raise
            raise HTTPException(422,'No supported USD equity quote available; instrument was not added')
        name=body.symbol
        try:
            data=(await get('https://query1.finance.yahoo.com/v1/finance/search',{'q':body.symbol,'quotesCount':3,'newsCount':0})).json()
            name=next((r.get('shortname') or r.get('longname') or body.symbol for r in data.get('quotes',[]) if r.get('symbol')==body.symbol),body.symbol)
        except Exception:name=body.symbol
        with db() as c:c.execute('INSERT OR IGNORE INTO instruments VALUES (?,?,?)',(body.symbol,name,'Equities'))
        return {'symbol':body.symbol,'name':name,'added':True,'validated_quote':q}
