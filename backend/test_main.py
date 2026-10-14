import asyncio
import json
import pytest
import httpx
from fastapi.testclient import TestClient
from backend import main, feeds

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DB_PATH',str(tmp_path/'test.sqlite3'))
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    monkeypatch.delenv('AI_PROVIDER',raising=False)
    main.cache=feeds.Cache(main.db)
    async def quote(a):
        if a[0]=='SPY': raise ValueError('Missing credentials')
        return {**main.empty_quote(a),'price':100.0,'mode':'provider','source':'Mock exchange','source_url':'https://example.com/quote','as_of':'2026-10-14T12:00:00Z','freshness':'last trade','change_pct':2,'change_period':'24h'}
    async def feed(*args):
        return {'source':args[0],'mode':'provider','as_of':feeds.now(),'items':[{'title':'Policy announcement','url':'https://www.federalreserve.gov/newsevents/pressreleases/test.htm','publisher':args[0],'published_at':'2026-10-14T12:00:00+00:00','summary':'The board published an announcement.','evidence_scope':'RSS only'}]}
    monkeypatch.setattr(main,'quote_provider',quote)
    monkeypatch.setattr(main,'feed_provider',feed)
    return TestClient(main.app)

def test_public_quotes_never_fabricate(client):
    quotes=client.get('/api/markets').json()
    assert len(quotes)==12
    missing=next(q for q in quotes if q['symbol']=='SPY')
    assert missing['price'] is None and missing['mode']=='unavailable'
    assert all(q['mode']!='demo' for q in quotes)
    assert client.post('/api/orders',json={'symbol':'SPY','side':'buy','quantity':1}).status_code==409

def test_accounting_persists_fill_sources(client):
    def order(side,qty): return client.post('/api/orders',json={'symbol':'BTC','side':side,'quantity':qty})
    assert order('sell',1).status_code==400
    assert order('buy',100000).status_code==400
    assert order('buy',-1).status_code==422
    buy=order('buy',2).json()
    assert buy['cash']==99800 and buy['trades'][0]['source']=='Mock exchange'
    assert buy['positions'][0]['quantity']==2
    assert order('sell',3).status_code==400
    assert order('sell',2).json()['cash']==100000
    assert client.get('/api/portfolio').json()['positions']==[]

def test_research_uses_returned_evidence_ids(client):
    r=client.post('/api/research',json={'question':'What happened?','symbol':'BTC'}).json()
    assert r['sources'][0]['title']=='BTC — Mock exchange'
    assert r['sources'][1]['title']=='Policy announcement'
    assert '[1]' in r['answer'] and '[2]' in r['answer']
    assert 'not full articles' in r['answer']

def test_news_deduplicates_links(client):
    r=client.get('/api/news').json()
    assert len(r['items'])==1 and r['items'][0]['mode']=='provider'
    assert len(r['feeds'])==len(feeds.FEEDS)

def test_feed_parser_rejects_unsafe_links_and_strips_html():
    xml=b'''<rss><channel><item><title>Rate &amp; policy</title><link>https://www.federalreserve.gov/test.htm</link><pubDate>Wed, 14 Oct 2026 12:00:00 GMT</pubDate><description>&lt;b&gt;Board update&lt;/b&gt;</description></item><item><title>Bad</title><link>javascript:alert(1)</link></item><item><title>Wrong host</title><link>https://evil.test/a</link></item></channel></rss>'''
    entries=feeds.parse_feed(xml,'Fed','federalreserve.gov')
    assert len(entries)==1 and entries[0]['summary']=='Board update'
    assert entries[0]['published_at']=='2026-10-14T12:00:00+00:00'

def test_stale_cache_and_backoff(client):
    with main.db() as c:
        q={**main.empty_quote(main.asset('SPY')),'price':123,'mode':'provider','source':'Previous provider'}
        c.execute('INSERT INTO cache VALUES (?,?,?)',('public:v3:quote:SPY',json.dumps(q),0))
    q=asyncio.run(main.quote('SPY'))
    assert q['mode']=='stale' and q['price']==123

def test_crypto_history_excludes_open_candle(client,monkeypatch):
    from datetime import datetime,timezone,timedelta
    today=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    async def get(*args,**kwargs):
        return httpx.Response(200,json=[[today.timestamp(),90,110,95,105,1],[(today-timedelta(days=1)).timestamp(),80,100,85,95,1]],request=httpx.Request('GET','https://example.com'))
    monkeypatch.setattr(feeds,'get',get)
    h=client.get('/api/history/BTC').json()
    assert len(h['points'])==1 and h['points'][0]['value']==95 and h['mode']=='provider'
    assert client.get('/api/history/UNKNOWN').status_code==404

def test_unavailable_history_has_no_points(client,monkeypatch):
    async def unavailable(a,days=100): raise ValueError('Unavailable')
    monkeypatch.setattr(main,'history_provider',unavailable)
    h=client.get('/api/history/SPY').json()
    assert h['points']==[] and h['mode']=='unavailable'

def test_bls_skips_unpublished_months_and_annual_average():
    d={'status':'REQUEST_SUCCEEDED','Results':{'series':[{'seriesID':'CUSR0000SA0','data':[{'year':'2026','period':'M10','value':'-'},{'year':'2026','period':'M09','value':'336.298'},{'year':'2026','period':'M13','value':'333'}]}]}}
    assert feeds.parse_bls(d)==[{'date':'2026-09-01','value':336.298}]

def test_treasury_namespaces_and_missing_tenor():
    d=b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"><entry><m:properties><d:NEW_DATE>2026-10-14T00:00:00</d:NEW_DATE><d:BC_10YEAR>5.19</d:BC_10YEAR></m:properties></entry><entry><m:properties><d:NEW_DATE>2026-10-13T00:00:00</d:NEW_DATE></m:properties></entry></feed>'''
    assert feeds.parse_treasury(d)==[{'date':'2026-10-14','value':5.19}]

def test_equity_chart_handles_missing_closes_and_exchange_dates():
    d={'chart':{'error':None,'result':[{'meta':{'symbol':'AAPL','currency':'USD','exchangeTimezoneName':'America/New_York'},'timestamp':[1791936000,1792022400],'indicators':{'quote':[{'close':[342.96,None]}]}}]}}
    meta,points=feeds.parse_equity_chart(d,'AAPL')
    assert points==[{'date':'2026-10-13','value':342.96}]
    with pytest.raises(ValueError): feeds.parse_equity_chart(d,'MSFT')

def test_bbc_feed_accepts_only_publisher_domains():
    xml=b'''<rss><channel><item><title>Markets</title><link>https://www.bbc.com/news/test</link></item><item><title>Business</title><link>https://www.bbc.co.uk/news/test</link></item><item><title>Bad</title><link>https://bbc.com.evil.test/news</link></item></channel></rss>'''
    assert len(feeds.parse_feed(xml,'BBC News Business',('bbc.com','bbc.co.uk')))==2

def test_persistent_alert_lifecycle_and_missing_quote(client):
    body={'symbol':'BTC','direction':'above','threshold':90}
    rules=client.post('/api/alerts',json=body).json();identifier=rules[0]['id']
    assert len(client.post('/api/alerts/evaluate',json={}).json()['triggered'])==1
    assert client.post('/api/alerts/evaluate',json={}).json()['triggered']==[]
    assert client.get('/api/alerts').json()[0]['active']==1
    client.post(f'/api/alerts/{identifier}/toggle',json={})
    assert client.get('/api/alerts').json()[0]['enabled']==0
    assert client.post('/api/alerts',json={**body,'threshold':-1}).status_code==422
    client.post('/api/alerts',json={**body,'symbol':'SPY'})
    assert client.post('/api/alerts/evaluate',json={}).json()['triggered']==[]

def test_notebook_preserves_evidence_snapshot(client):
    sources=[{'id':1,'url':'https://example.com','title':'Original evidence'}]
    result=client.post('/api/notes',json={'symbol':'BTC','question':'Thesis?','content':'Saved analysis [1]','sources':sources})
    assert result.status_code==200
    assert client.get('/api/notes').json()[0]['sources']==sources

def test_portfolio_analysis_and_csv(client):
    client.post('/api/orders',json={'symbol':'BTC','side':'buy','quantity':2})
    analysis=client.get('/api/portfolio/analysis').json()
    assert analysis['cash']==99800 and analysis['equity']==100000
    assert analysis['positions'][0]['average_cost']==100
    assert analysis['unrealized_pnl']==0
    export=client.get('/api/export/portfolio.csv')
    assert export.status_code==200 and 'Mock exchange' in export.text and 'signed_quantity' in export.text

def test_compare_rejects_macro_and_duplicate_symbols(client):
    assert client.post('/api/compare',json={'symbols':['BTC','DGS10']}).status_code==400
    assert client.post('/api/compare',json={'symbols':['BTC','BTC']}).status_code==400

def test_global_search_filters_unsupported_listings_and_adds_usd_equity(client,monkeypatch):
    from backend import catalog
    async def get(*args,**kwargs):
        return httpx.Response(200,json={'quotes':[{'symbol':'TSLA','shortname':'Tesla, Inc.','quoteType':'EQUITY','exchange':'NMS'},{'symbol':'TSLA.TO','quoteType':'EQUITY','exchange':'TOR'},{'symbol':'BAD=F','quoteType':'FUTURE','exchange':'CME'}]},request=httpx.Request('GET','https://example.com'))
    async def quote(a):return {'symbol':a[0],'price':300,'mode':'provider'}
    monkeypatch.setattr(catalog,'get',get);monkeypatch.setattr(catalog,'quote_provider',quote)
    search=client.get('/api/search?q=Tesla').json()
    assert [r['symbol'] for r in search['items']]==['TSLA']
    assert client.post('/api/universe',json={'symbol':'TSLA'}).json()['added'] is True
    assert client.post('/api/universe',json={'symbol':'TSLA'}).json()['added'] is False
    assert main.asset('TSLA')==('TSLA','Tesla, Inc.','Equities')
    assert client.post('/api/universe',json={'symbol':'https://evil.test'}).status_code==422

def test_calculator_api_validates_inputs_and_labels_scenarios(client):
    o=client.post('/api/calculators/options',json={'spot':100,'strike':100,'days':365,'volatility_pct':20,'rate_pct':5}).json()
    assert o['call']['price']==pytest.approx(10.45058357)
    assert 'No live option chain' in o['assumptions']
    invalid=client.post('/api/calculators/options',json={'spot':100,'strike':100,'days':0,'volatility_pct':20,'rate_pct':5})
    assert invalid.status_code==422
    assert client.post('/api/calculators/bonds',json={'coupon_pct':4,'yield_pct':4,'years':1.3,'frequency':2}).status_code==400


def test_sec_statement_route_uses_cache_and_labels_unsupported(client,monkeypatch):
    from backend import statements
    calls=[]
    async def provider(symbol):
        calls.append(symbol)
        return {'symbol':symbol,'source':'Mock SEC','mode':'provider','as_of':'2025-12-31','metrics':[]}
    monkeypatch.setattr(statements,'provider',provider)
    assert client.get('/api/statements/AAPL').json()['source']=='Mock SEC'
    assert client.get('/api/statements/AAPL').json()['mode']=='provider'
    assert calls==['AAPL']
    assert client.get('/api/statements/SPY').json()['mode']=='unavailable'
    assert client.get('/api/statements/UNKNOWN').status_code==404


def test_research_financial_question_includes_exact_sec_period_and_citation(client,monkeypatch):
    from backend import statements
    async def provider(symbol):
        return {'mode':'provider','source':'SEC','as_of':'2025-12-31','metrics':[{'label':'Revenue','value':100,'unit':'USD','start':'2025-01-01','end':'2025-12-31','filed':'2026-02-01','tag':'us-gaap:Revenues','source_url':'https://www.sec.gov/Archives/test-index.html'}]}
    monkeypatch.setattr(statements,'provider',provider)
    data=client.post('/api/research',json={'question':'Explain reported revenue','symbol':'AAPL'}).json()
    source=next(s for s in data['sources'] if s['publisher']=='SEC EDGAR')
    assert '2025-01-01' in source['summary'] and '2025-12-31' in source['summary']
    assert 'not a current quote' in source['summary']
    assert source['url']=='https://www.sec.gov/Archives/test-index.html'
    assert '['+str(source['id'])+']' in data['answer']
