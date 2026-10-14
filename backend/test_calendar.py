from backend.calendar import parse_auctions

def test_announced_auctions_do_not_fabricate_results():
    d={'data':[{'cusip':'X','auction_date':'2026-10-15','security_type':'Bill','security_term':'8-Week','high_yield':'null','high_investment_rate':'null','bid_to_cover_ratio':'null'}]}
    result=parse_auctions(d)[0]
    assert result['rate'] is None and result['bid_to_cover'] is None

def test_result_rate_retains_instrument_definition():
    d={'data':[{'cusip':'X','auction_date':'2026-10-14','security_type':'Bill','security_term':'4-Week','high_yield':'null','high_investment_rate':'4.13','bid_to_cover_ratio':'2.5'}]}
    result=parse_auctions(d)[0]
    assert result['rate']==4.13 and result['rate_type']=='high_investment_rate' and result['bid_to_cover']==2.5
