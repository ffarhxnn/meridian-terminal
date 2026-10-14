import pytest
from backend.statements import parse_statements, valid_fact

def fact(value,start='2024-01-01',end='2024-12-31',filed='2025-02-01',accn='0000320193-25-000001'):
    return dict(val=value,start=start,end=end,filed=filed,accn=accn,form='10-K')

def test_annual_facts_keep_periods_units_and_restated_citations():
    annual=fact(100)
    amended=fact(110,filed='2026-02-01',accn='0000320193-26-000001')
    quarter=fact(30,start='2024-10-01')
    balance=fact(500);balance.pop('start')
    data={'cik':320193,'entityName':'Apple','facts':{'us-gaap':{
        'Revenues':{'units':{'USD':[annual,amended,quarter]}},
        'Assets':{'units':{'USD':[balance]}},
        'EarningsPerShareDiluted':{'units':{'USD':[fact(999)],'USD/shares':[fact(2.5)]}},
    }}}
    result=parse_statements(data,'0000320193','AAPL')
    metrics={m['label']:m for m in result['metrics']}
    assert result['as_of']=='2024-12-31'
    assert metrics['Revenue']['value']==110
    assert metrics['Revenue']['filed']=='2026-02-01'
    assert '000032019326000001' in metrics['Revenue']['source_url']
    assert metrics['Total assets']['value']==500
    assert metrics['Diluted EPS']['value']==2.5
    assert metrics['Net income']['value'] is None

def test_invalid_issuer_duration_or_accession_is_rejected():
    assert not valid_fact(fact(float('nan')),True)
    assert not valid_fact(fact(1,start='2024-10-01'),True)
    assert not valid_fact(fact(1,accn='../../escape'),True)
    with pytest.raises(ValueError,match='identifier'):
        parse_statements({'cik':1},'0000320193','AAPL')
    with pytest.raises(ValueError,match='annual'):
        parse_statements({'cik':320193},'0000320193','AAPL')
