"""Selected annual US-GAAP company facts, not a normalized financial database."""
from datetime import date
import re
from backend.feeds import get, now

# Stable public issuer identifiers; API submissions validate ticker membership.
CIKS = {'AAPL':'0000320193','MSFT':'0000789019','NVDA':'0001045810','TSLA':'0001318605'}
METRICS = [
    ('Revenue', ['RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet'], 'USD', True),
    ('Net income', ['NetIncomeLoss'], 'USD', True),
    ('Operating income', ['OperatingIncomeLoss'], 'USD', True),
    ('Operating cash flow', ['NetCashProvidedByUsedInOperatingActivities'], 'USD', True),
    ('Capital expenditures', ['PaymentsToAcquirePropertyPlantAndEquipment'], 'USD', True),
    ('Diluted EPS', ['EarningsPerShareDiluted'], 'USD/shares', True),
    ('Total assets', ['Assets'], 'USD', False),
    ('Total liabilities', ['Liabilities'], 'USD', False),
    ('Stockholders equity', ['StockholdersEquity'], 'USD', False),
    ('Cash and equivalents', ['CashAndCashEquivalentsAtCarryingValue'], 'USD', False),
]

def valid_fact(row, duration):
    if row.get('form') not in ('10-K','10-K/A') or not re.fullmatch(r'\d{10}-\d{2}-\d{6}',row.get('accn','')):
        return False
    value = row.get('val')
    import math
    if not isinstance(value,(int,float)) or not math.isfinite(value):
        return False
    try:
        end = date.fromisoformat(row['end'])
        if duration:
            return 330 <= (end-date.fromisoformat(row['start'])).days <= 400
        return not row.get('start')
    except (ValueError,KeyError,TypeError):
        return False

def parse_statements(data, cik, symbol):
    if str(data.get('cik','')).zfill(10) != cik:
        raise ValueError('Unexpected SEC issuer identifier')
    facts = data.get('facts',{}).get('us-gaap',{})
    candidates = {}
    for label,tags,unit,duration in METRICS:
        rows=[]
        for priority,tag in enumerate(tags):
            for row in facts.get(tag,{}).get('units',{}).get(unit,[]):
                if valid_fact(row,duration):
                    rows.append({**row,'tag':tag,'priority':priority,'unit':unit})
        candidates[label]=rows
    anchors = candidates['Revenue'] or candidates['Net income']
    if not anchors:
        raise ValueError('No supported annual US-GAAP statement observations')
    end=max(row['end'] for row in anchors)
    metrics=[]
    for label,_,unit,duration in METRICS:
        rows=[row for row in candidates[label] if row['end']==end]
        if not rows:
            metrics.append({'label':label,'value':None,'unit':unit,'end':end,'reason':'Standard tag unavailable for this fiscal year'})
            continue
        # Prefer the latest filed observation, then the listed standard-tag priority.
        row=max(rows,key=lambda r:(r.get('filed',''),-r['priority']))
        accession=row['accn']
        metrics.append({'label':label,'value':row['val'],'unit':unit,'start':row.get('start'),
                        'end':row['end'],'filed':row.get('filed'),'form':row['form'],'tag':'us-gaap:'+row['tag'],
                        'accession':accession,'source_url':f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-","")}/{accession}-index.html',
                        'period_type':'Annual duration' if duration else 'Fiscal year-end balance'})
    return {'symbol':symbol,'entity':data.get('entityName',symbol),'cik':cik,'as_of':end,
            'metrics':metrics,'source':'SEC EDGAR Company Facts','source_url':f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json',
            'mode':'provider','retrieved_at':now(),
            'warning':'Selected annual standard US-GAAP tags only; not a full statement or TTM model. Values can reflect later comparative filings or restatements. Compare fiscal dates, units and filing links. Missing custom tags remain unavailable.'}

async def provider(symbol):
    cik=CIKS[symbol]
    identity=(await get(f'https://data.sec.gov/submissions/CIK{cik}.json')).json()
    if symbol not in identity.get('tickers',[]):
        raise ValueError('SEC ticker mapping no longer matches issuer')
    data=(await get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json')).json()
    return parse_statements(data,cik,symbol)

def register(app,cache,asset):
    @app.get('/api/statements/{symbol}')
    async def statements(symbol:str):
        asset(symbol)
        fallback={'symbol':symbol,'metrics':[],'source':'SEC EDGAR Company Facts','source_url':'https://www.sec.gov/search-filings/edgar-application-programming-interfaces',
                  'as_of':None,'warning':'No supported SEC annual statements available. Current issuer mappings: AAPL, MSFT, NVDA, TSLA. ETFs and non-company assets are outside this view.'}
        if symbol not in CIKS:
            return {**fallback,'mode':'unavailable'}
        return await cache.fetch('public:v1:statements:'+symbol,lambda:provider(symbol),21600,fallback)
