"""Transparent descriptive analytics, with explicit date alignment and no forecasts."""
import math
import statistics

def aligned_comparison(series, days=90):
    available={s:record for s,record in series.items() if record.get('mode') in ('provider','stale') and len(record.get('points',[]))>=2}
    if len(available)<2:
        return {'mode':'unavailable','reason':'At least two instruments with history are required','dates':[],'series':[],'correlations':[]}
    maps={s:{p['date']:p['value'] for p in record['points'] if p['value']>0} for s,record in available.items()}
    common=sorted(set.intersection(*(set(p) for p in maps.values())))
    from datetime import date,timedelta
    if common:
        cutoff=(date.fromisoformat(common[-1])-timedelta(days=days-1)).isoformat()
        common=[d for d in common if d>=cutoff]
    if len(common)<3:
        return {'mode':'unavailable','reason':'Fewer than three common observation dates','dates':common,'series':[],'correlations':[]}
    rows=[]; returns={}
    for symbol,values in maps.items():
        prices=[values[d] for d in common]
        logreturns=[math.log(b/a) for a,b in zip(prices,prices[1:])]
        returns[symbol]=logreturns
        peak=prices[0]; drawdown=0
        for price in prices:
            peak=max(peak,price);drawdown=min(drawdown,(price/peak-1)*100)
        rows.append({'symbol':symbol,'normalized':[round(p/prices[0]*100,4) for p in prices],
                     'return_pct':(prices[-1]/prices[0]-1)*100,'max_drawdown_pct':drawdown,
                     'observation_volatility_pct':statistics.stdev(logreturns)*100 if len(logreturns)>1 else None,
                     'source':available[symbol]['source'],'source_url':available[symbol].get('source_url'),'mode':available[symbol]['mode']})
    correlations=[]
    for a in maps:
        for b in maps:
            x,y=returns[a],returns[b]
            value=statistics.correlation(x,y) if statistics.pstdev(x)>0 and statistics.pstdev(y)>0 else None
            correlations.append({'a':a,'b':b,'value':value})
    return {'mode':'stale' if any(r['mode']=='stale' for r in rows) else 'provider','dates':common,'series':rows,'correlations':correlations,
            'observations':len(common),'methodology':'Intersection of published calendar dates; no forward fill. Returns are close-to-close on those dates. Sessions/time zones differ. Volatility is sample log-return standard deviation per aligned observation, not annualized. Price returns exclude dividends and corporate-action adjustments may differ. Correlation is descriptive, not causation.'}

def cost_basis(trades):
    positions={};realized=0
    for trade in trades:
        symbol=trade['symbol'];p=positions.setdefault(symbol,{'symbol':symbol,'quantity':0.0,'cost':0.0,'realized_pnl':0.0})
        qty,price=trade['qty'],trade['price']
        if qty>0:
            p['cost']+=qty*price;p['quantity']+=qty
        else:
            sold=-qty;average=p['cost']/p['quantity'] if p['quantity']>0 else 0
            gain=sold*(price-average);realized+=gain;p['realized_pnl']+=gain
            p['quantity']-=sold;p['cost']-=sold*average
            if abs(p['quantity'])<1e-8:p['quantity']=0;p['cost']=0
    for p in positions.values():p['average_cost']=p['cost']/p['quantity'] if p['quantity'] else None
    return {'positions':list(positions.values()),'realized_pnl':realized,'method':'Weighted average cost, USD, excluding fees/dividends/taxes. Legacy fills retain their original simulated prices.'}

NEWS_TERMS={
 'SPY':['s&p','stock market','stocks','wall street','equities','federal reserve','inflation'],
 'QQQ':['nasdaq','technology','tech stocks','ai','artificial intelligence'],
 'AAPL':['apple','iphone','aapl'], 'MSFT':['microsoft','azure','msft'],
 'NVDA':['nvidia','gpu','semiconductor','nvda'], 'BTC':['bitcoin','crypto','cryptocurrency','btc'],
 'ETH':['ethereum','ether','crypto','eth'], 'EUR/USD':['euro','ecb','european central bank','dollar'],
 'GBP/USD':['pound','sterling','bank of england','dollar'], 'DGS10':['treasury','yields','rates','federal reserve','inflation'],
 'CPIAUCSL':['inflation','consumer price','cpi'], 'GLD':['gold','bullion','precious metal']}

def rank_news(items,symbol,question='',name=''):
    import re
    terms=list(NEWS_TERMS.get(symbol,[symbol.lower()]))
    terms.extend(w for w in re.findall(r'[a-z]{3,}',name.lower()) if w not in {'inc','corp','corporation','company','the','fund','trust','etf','group','holdings','common','stock','class','usd','dollar','index','treasury','yield','year','consumer','price'})
    question_terms=[w for w in re.findall(r'[a-z]{4,}',question.lower()) if w not in {'what','should','about','this','investigate','asset','please','research','there','which','with','from','have'}]
    def score(item):
        title=item['title'].lower();text=title+' '+item.get('summary','').lower()
        def matches(term,content):return bool(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',content))
        return sum(4 if matches(t,title) else 1 if matches(t,text) else 0 for t in terms)+sum(1 for t in question_terms if matches(t,text))
    ranked=sorted(enumerate(items),key=lambda pair:(-score(pair[1]),pair[0]))
    return [{**item,'relevance_score':score(item),'relevance':'keyword match' if score(item)>0 else 'general market context'} for _,item in ranked]
