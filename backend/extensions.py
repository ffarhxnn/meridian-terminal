import csv
import io
import json
import math
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,Field
from backend.analytics import aligned_comparison,cost_basis
from backend.feeds import get,TREASURY_URL,TREASURY_DOC,number

class Comparison(BaseModel):
    symbols:list[str]=Field(min_length=2,max_length=5)
    days:int=Field(default=90,ge=7,le=100)

class AlertRule(BaseModel):
    symbol:str
    direction:str
    threshold:float=Field(gt=0,allow_inf_nan=False)

class Note(BaseModel):
    symbol:str
    question:str=Field(max_length=2000)
    content:str=Field(min_length=1,max_length=20000)
    sources:list[dict]=Field(default_factory=list,max_length=20)

async def treasury_curve():
    year=datetime.now(timezone.utc).year
    ns={'m':'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata','d':'http://schemas.microsoft.com/ado/2007/08/dataservices'}
    response=await get(TREASURY_URL,{'data':'daily_treasury_yield_curve','field_tdr_date_value':str(year)})
    root=ET.fromstring(response.content)
    rows=root.findall('.//m:properties',ns)
    rows=sorted(rows,key=lambda p:p.findtext('d:NEW_DATE',default='',namespaces=ns))
    if not rows:
        response=await get(TREASURY_URL,{'data':'daily_treasury_yield_curve','field_tdr_date_value':str(year-1)})
        root=ET.fromstring(response.content);rows=sorted(root.findall('.//m:properties',ns),key=lambda p:p.findtext('d:NEW_DATE',default='',namespaces=ns))
    latest=rows[-1]
    tenors=[('1M','BC_1MONTH',1/12),('2M','BC_2MONTH',2/12),('3M','BC_3MONTH',.25),('6M','BC_6MONTH',.5),('1Y','BC_1YEAR',1),('2Y','BC_2YEAR',2),('3Y','BC_3YEAR',3),('5Y','BC_5YEAR',5),('7Y','BC_7YEAR',7),('10Y','BC_10YEAR',10),('20Y','BC_20YEAR',20),('30Y','BC_30YEAR',30)]
    points=[]
    for label,tag,years in tenors:
        value=latest.findtext('d:'+tag,namespaces=ns)
        if value:points.append({'tenor':label,'years':years,'yield_pct':number(value)})
    values={p['tenor']:p['yield_pct'] for p in points}
    return {'points':points,'mode':'provider','source':'U.S. Treasury daily par yield curve','source_url':TREASURY_DOC,
            'as_of':latest.findtext('d:NEW_DATE',namespaces=ns)[:10],
            'spread_10y_2y_bps':(values['10Y']-values['2Y'])*100 if '10Y' in values and '2Y' in values else None,
            'methodology':'Published par yields, not executable bond prices or a bootstrapped spot curve. Tenor spacing is linear in years.'}

def register(app,db,cache,quote,history,asset,now):
    def initialize():
        with db() as c:
            c.executescript('CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, symbol TEXT, direction TEXT, threshold REAL, enabled INTEGER DEFAULT 1, active INTEGER DEFAULT 0, triggered_at TEXT, observation_at TEXT); CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, symbol TEXT, question TEXT, content TEXT, sources TEXT, created_at TEXT);')

    @app.post('/api/compare')
    async def compare(body:Comparison):
        symbols=list(dict.fromkeys(body.symbols))
        if len(symbols)<2:raise HTTPException(400,'Select at least two different instruments')
        records={}
        for symbol in symbols:
            if asset(symbol)[2]=='Macro':raise HTTPException(400,'Yield levels and monthly economic indexes cannot be compared as investable price returns')
            records[symbol]=await history(symbol,body.days)
        result=aligned_comparison(records,body.days)
        result['unavailable_symbols']=[s for s,r in records.items() if r['mode']=='unavailable']
        return result

    @app.get('/api/yield-curve')
    async def curve():
        return await cache.fetch('public:v4:treasury-curve',treasury_curve,21600,{'points':[],'source':'U.S. Treasury','as_of':None})

    @app.get('/api/portfolio/analysis')
    async def portfolio_analysis():
        with db() as c:trades=[dict(r) for r in c.execute('SELECT * FROM trades ORDER BY id')]
        analysis=cost_basis(trades);cash=100000-sum(t['qty']*t['price'] for t in trades);total=0;unrealized=0;complete=True
        for position in analysis['positions']:
            if not position['quantity']:continue
            q=await quote(position['symbol']);price=q['price']
            position.update(mark=price,source=q['source'],as_of=q['as_of'],mode=q['mode'])
            position['market_value']=price*position['quantity'] if price is not None else None
            position['unrealized_pnl']=position['market_value']-position['cost'] if price is not None else None
            if price is None:complete=False
            else:total+=position['market_value'];unrealized+=position['unrealized_pnl']
        return {**analysis,'cash':cash,'complete_marks':complete,'equity':cash+total if complete else None,'unrealized_pnl':unrealized if complete else None}

    @app.get('/api/export/portfolio.csv')
    def export_portfolio():
        with db() as c:
            rows=c.execute("SELECT trades.id,symbol,qty,price,timestamp,COALESCE(source,'Legacy synthetic fill') AS source,as_of FROM trades LEFT JOIN fill_sources ON trades.id=fill_sources.trade_id ORDER BY trades.id").fetchall()
        output=io.StringIO();writer=csv.writer(output)
        writer.writerow(['id','symbol','signed_quantity','price_usd','executed_at','source','observation_at'])
        writer.writerows(tuple(r) for r in rows)
        return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="meridian-paper-ledger.csv"'})

    @app.get('/api/alerts')
    def alerts():
        initialize()
        with db() as c:return [dict(r) for r in c.execute('SELECT * FROM alerts ORDER BY id DESC')]

    @app.post('/api/alerts')
    def create_alert(body:AlertRule):
        asset(body.symbol)
        if body.direction not in ('above','below'):raise HTTPException(400,'Direction must be above or below')
        initialize()
        with db() as c:
            if c.execute('SELECT COUNT(*) FROM alerts').fetchone()[0]>=100:raise HTTPException(400,'100-rule limit reached')
            c.execute('INSERT INTO alerts(symbol,direction,threshold) VALUES (?,?,?)',(body.symbol,body.direction,body.threshold))
        return alerts()

    @app.post('/api/alerts/{rule_id}/toggle')
    def toggle(rule_id:int):
        initialize()
        with db() as c:
            row=c.execute('SELECT * FROM alerts WHERE id=?',(rule_id,)).fetchone()
            if not row:raise HTTPException(404,'Rule not found')
            c.execute('UPDATE alerts SET enabled=?,active=0 WHERE id=?',(0 if row['enabled'] else 1,rule_id))
        return alerts()

    @app.post('/api/alerts/evaluate')
    async def evaluate():
        initialize()
        with db() as c:rules=[dict(r) for r in c.execute('SELECT * FROM alerts WHERE enabled=1')]
        quotes={};triggered=[]
        for rule in rules:
            symbol=rule['symbol']
            if symbol not in quotes:quotes[symbol]=await quote(symbol)
            q=quotes[symbol]
            if q['price'] is None or q['mode']!='provider':continue
            reached=q['price']>=rule['threshold'] if rule['direction']=='above' else q['price']<=rule['threshold']
            with db() as c:
                if reached and not rule['active']:
                    stamp=now();updated=c.execute('UPDATE alerts SET active=1,triggered_at=?,observation_at=? WHERE id=? AND enabled=1 AND active=0',(stamp,q['as_of'],rule['id']))
                    if updated.rowcount:triggered.append({**rule,'price':q['price'],'source':q['source'],'as_of':q['as_of'],'triggered_at':stamp})
                elif not reached:c.execute('UPDATE alerts SET active=0 WHERE id=?',(rule['id'],))
        return {'triggered':triggered,'rules':alerts(),'note':'Evaluated only while this local terminal is open or Evaluate is clicked. Uses delayed/indicative published observations. No background or external notification service.'}

    @app.get('/api/notes')
    def notes():
        initialize()
        with db() as c:rows=[dict(r) for r in c.execute('SELECT * FROM notes ORDER BY id DESC LIMIT 100')]
        return [{**row,'sources':json.loads(row['sources'])} for row in rows]

    @app.post('/api/notes')
    def save_note(body:Note):
        asset(body.symbol);initialize()
        sources=json.dumps(body.sources)
        if len(sources)>100000:raise HTTPException(400,'Evidence snapshot too large')
        with db() as c:c.execute('INSERT INTO notes(symbol,question,content,sources,created_at) VALUES (?,?,?,?,?)',(body.symbol,body.question,body.content,sources,now()))
        return notes()
