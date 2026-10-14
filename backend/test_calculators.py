import math
import pytest
from backend.calculators import black_scholes,bond_price

def test_option_known_value_and_put_call_parity():
    r=black_scholes(100,100,1,.2,.05)
    assert r['call']['price']==pytest.approx(10.45058357)
    assert r['put']['price']==pytest.approx(5.57352602)
    assert r['call']['price']-r['put']['price']==pytest.approx(100-100*math.exp(-.05))

def test_option_greeks_against_finite_differences():
    r=black_scholes(100,110,.5,.3,.04,.01)['call'];h=.01
    plus=black_scholes(100+h,110,.5,.3,.04,.01)['call']['price'];minus=black_scholes(100-h,110,.5,.3,.04,.01)['call']['price']
    assert r['delta']==pytest.approx((plus-minus)/(2*h),rel=1e-5)
    assert r['gamma']==pytest.approx((plus-2*r['price']+minus)/h**2,rel=1e-5)

def test_bond_par_zero_coupon_and_duration():
    r=bond_price(100,.04,.04,5,2)
    assert r['price']==pytest.approx(100)
    z=bond_price(100,0,.04,5,2)
    assert z['price']==pytest.approx(100/(1.02**10))
    assert z['macaulay_duration_years']==pytest.approx(5)
    assert bond_price(100,.04,.05,5,2)['price']<r['price']
    h=1e-5;up=bond_price(100,.04,.04+h,5,2)['price'];down=bond_price(100,.04,.04-h,5,2)['price']
    assert r['modified_duration']==pytest.approx((down-up)/(2*h*r['price']),rel=1e-6)

def test_bond_rejects_irregular_periods():
    with pytest.raises(ValueError):bond_price(100,.04,.04,1.3,2)
