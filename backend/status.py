import json
import os
import time
from datetime import datetime,timezone

CAPABILITIES=[
 {'workflow':'Security lookup / watchlists','state':'Working','detail':'Local catalog plus best-effort U.S. equity/ETF lookup; USD quote validation before adding.'},
 {'workflow':'Charts / technical overlay','state':'Working','detail':'Source OHLC where available, 20-observation SMA, up to one year; source-specific history limits apply.'},
 {'workflow':'Relative value / correlation','state':'Working','detail':'Aligned calendar-date returns, drawdown, observation volatility and correlations; no causality claims.'},
 {'workflow':'Rates / Treasury auctions','state':'Working','detail':'Official daily par curve and announced auction/result data, source-dated.'},
 {'workflow':'News / research / notebook','state':'Working','detail':'Publisher RSS with direct citations, keyword relevance and saved evidence. AI optional.'},
 {'workflow':'Paper portfolio / alerts','state':'Working','detail':'Weighted-average cost and P/L, CSV ledger, active-session threshold rules; no live execution.'},
 {'workflow':'Bond / option scenarios','state':'Working','detail':'Transparent fixed-coupon and European option math, not live price/chain feeds.'},
 {'workflow':'Company financial statements','state':'Needs data provider','detail':'Alpha Vantage overview optional; keyless market-reference metadata does not replace statements.'},
 {'workflow':'Corporate bonds / credit / CDS','state':'Not implemented','detail':'Requires appropriate reference/pricing data and instrument-specific conventions.'},
 {'workflow':'Futures / options chains / volatility surfaces','state':'Not implemented','detail':'No exchange-entitled chains or derivatives market feed is connected.'},
 {'workflow':'Full news archives / analyst research / estimates','state':'Not implemented','detail':'Not supplied by the public RSS sources; licensing and retrieval coverage are separate.'},
 {'workflow':'Broker trading / Bloomberg messaging','state':'Not implemented','detail':'No broker connection or proprietary network access. This is an independent personal terminal.'},
]

def register(app,db,all_assets):
    @app.get('/api/status')
    def status():
        snapshots=[]
        with db() as c:
            rows=c.execute("SELECT * FROM cache WHERE key LIKE 'public:v3:quote:%' ORDER BY key").fetchall()
            for row in rows:
                payload=json.loads(row['payload'])
                snapshots.append({key:payload.get(key) for key in ['symbol','source','mode','as_of','retrieved_at','warning']})
                snapshots[-1]['cache_refresh_due']=row['expires']<=time.time()
        return {'as_of':datetime.now(timezone.utc).isoformat(),'instruments':len(all_assets()),'snapshots':snapshots,'capabilities':CAPABILITIES,
                'ai':{'selection':os.getenv('AI_PROVIDER','auto'),'openai_key_configured':bool(os.getenv('OPENAI_API_KEY')),'gemini_key_configured':bool(os.getenv('GEMINI_API_KEY'))},
                'note':'Status reflects cached provider responses, not a live connectivity or latency guarantee. Provider mode identifies origin, not real-time exchange entitlement. API keys are never returned.'}
