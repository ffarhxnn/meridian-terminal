from datetime import datetime,timedelta,timezone
from backend.feeds import get,number

AUCTION_URL='https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query'
AUCTION_SOURCE='https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/'

def parse_auctions(data):
    items=[]
    for row in data['data']:
        rate_key='high_yield' if row.get('high_yield') not in (None,'null','') else 'high_investment_rate'
        rate=row.get(rate_key)
        coverage=row.get('bid_to_cover_ratio')
        items.append({'cusip':row['cusip'],'auction_date':row['auction_date'],'issue_date':row.get('issue_date'),'maturity_date':row.get('maturity_date'),
                      'security_type':row['security_type'],'security_term':row['security_term'],
                      'rate':number(rate) if rate not in (None,'null','') else None,'rate_type':rate_key,
                      'bid_to_cover':number(coverage) if coverage not in (None,'null','') else None,
                      'competitive_close':row.get('closing_time_comp'),'noncompetitive_close':row.get('closing_time_noncomp'),
                      'source_url':AUCTION_SOURCE})
    return items

async def auction_provider():
    start=(datetime.now(timezone.utc)-timedelta(days=30)).date().isoformat()
    response=await get(AUCTION_URL,{'filter':'auction_date:gte:'+start,'sort':'-auction_date','page[size]':100})
    items=parse_auctions(response.json())
    return {'items':items,'mode':'provider','source':'U.S. Treasury Fiscal Data','source_url':AUCTION_SOURCE,'as_of':datetime.now(timezone.utc).isoformat(),
            'note':'Announced auctions and reported results from the latest 30-day lookback; future entries only when already announced. Not a tentative long-term auction schedule. Rates retain their source definitions (high yield versus high investment rate). Closing times are shown as published; confirm on TreasuryDirect.'}

def register(app,cache):
    @app.get('/api/calendar/auctions')
    async def auctions():
        return await cache.fetch('public:v5:auction-calendar',auction_provider,3600,{'items':[],'source':'U.S. Treasury Fiscal Data','as_of':None})
