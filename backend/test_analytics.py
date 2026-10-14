import pytest
from backend.analytics import aligned_comparison,cost_basis,rank_news

def record(points,mode='provider'):
    return {'mode':mode,'source':'Test','points':[{'date':d,'value':v} for d,v in points]}

def test_alignment_uses_shared_dates_without_forward_fill():
    a=record([('2026-10-01',100),('2026-10-02',110),('2026-10-03',105),('2026-10-05',121)])
    b=record([('2026-10-01',200),('2026-10-02',220),('2026-10-04',222),('2026-10-05',242)])
    result=aligned_comparison({'A':a,'B':b})
    assert result['dates']==['2026-10-01','2026-10-02','2026-10-05']
    assert result['series'][0]['return_pct']==pytest.approx(21)
    assert result['series'][0]['normalized']==[100,110,121]
    assert result['series'][0]['max_drawdown_pct']==0

def test_comparison_handles_constant_prices_and_sparse_data():
    a=record([('2026-10-01',100),('2026-10-02',100),('2026-10-03',100)])
    result=aligned_comparison({'A':a,'B':a})
    assert all(c['value'] is None for c in result['correlations'])
    assert aligned_comparison({'A':a,'B':record([])})['mode']=='unavailable'

def test_weighted_average_cost_partial_sale_and_reentry():
    trades=[{'symbol':'A','qty':10,'price':100},{'symbol':'A','qty':10,'price':120},{'symbol':'A','qty':-5,'price':150},{'symbol':'A','qty':-15,'price':90},{'symbol':'A','qty':2,'price':80}]
    result=cost_basis(trades);p=result['positions'][0]
    assert result['realized_pnl']==pytest.approx(-100)
    assert p['quantity']==2 and p['cost']==160 and p['average_cost']==80

def test_news_ranking_matches_words_not_substrings():
    articles=[{'title':'Weather improves in the ether','summary':''},{'title':'NVIDIA earnings and GPU demand','summary':''},{'title':'General markets','summary':''}]
    assert rank_news(articles,'NVDA')[0]['title']=='NVIDIA earnings and GPU demand'
    assert rank_news([{'title':'Whether consumers spend','summary':''}],'ETH')[0]['relevance_score']==0

def test_dynamic_company_name_informs_news_ranking():
    articles=[{'title':'Broad markets','summary':''},{'title':'Tesla publishes deliveries','summary':''}]
    assert rank_news(articles,'TSLA',name='Tesla, Inc.')[0]['title']=='Tesla publishes deliveries'
