"""Scenario math only: no executable market quotes or valuation recommendations."""
import math
from fastapi import HTTPException
from pydantic import BaseModel,Field

class OptionScenario(BaseModel):
    spot:float=Field(gt=0,le=1e7,allow_inf_nan=False)
    strike:float=Field(gt=0,le=1e7,allow_inf_nan=False)
    days:float=Field(gt=0,le=3650,allow_inf_nan=False)
    volatility_pct:float=Field(gt=0,le=500,allow_inf_nan=False)
    rate_pct:float=Field(ge=-20,le=100,allow_inf_nan=False)
    dividend_pct:float=Field(default=0,ge=0,le=100,allow_inf_nan=False)

def black_scholes(spot,strike,years,sigma,rate,dividend=0):
    cdf=lambda x:(1+math.erf(x/math.sqrt(2)))/2
    pdf=lambda x:math.exp(-x*x/2)/math.sqrt(2*math.pi)
    sqrt=math.sqrt(years);d1=(math.log(spot/strike)+(rate-dividend+sigma*sigma/2)*years)/(sigma*sqrt);d2=d1-sigma*sqrt
    eq=math.exp(-dividend*years);er=math.exp(-rate*years)
    common=-spot*eq*pdf(d1)*sigma/(2*sqrt)
    call={'price':spot*eq*cdf(d1)-strike*er*cdf(d2),'delta':eq*cdf(d1),
          'theta_per_day':(common-rate*strike*er*cdf(d2)+dividend*spot*eq*cdf(d1))/365,
          'rho_per_rate_point':strike*years*er*cdf(d2)/100}
    put={'price':strike*er*cdf(-d2)-spot*eq*cdf(-d1),'delta':eq*(cdf(d1)-1),
         'theta_per_day':(common+rate*strike*er*cdf(-d2)-dividend*spot*eq*cdf(-d1))/365,
         'rho_per_rate_point':-strike*years*er*cdf(-d2)/100}
    for value in (call,put):
        value.update(gamma=eq*pdf(d1)/(spot*sigma*sqrt),vega_per_vol_point=spot*eq*pdf(d1)*sqrt/100)
    return {'call':call,'put':put}

class BondScenario(BaseModel):
    face:float=Field(default=100,gt=0,le=1e9,allow_inf_nan=False)
    coupon_pct:float=Field(ge=0,le=100,allow_inf_nan=False)
    yield_pct:float=Field(ge=-20,le=100,allow_inf_nan=False)
    years:float=Field(gt=0,le=100,allow_inf_nan=False)
    frequency:int=Field(default=2)

def bond_price(face,coupon,yield_rate,years,frequency):
    n=round(years*frequency)
    if frequency not in (1,2,4) or n<1 or abs(n-years*frequency)>1e-8:raise ValueError('Maturity must be a whole number of coupon periods; frequency must be 1, 2 or 4')
    base=1+yield_rate/frequency
    if base<=0:raise ValueError('Yield produces an invalid discount factor')
    cashflows=[(i,face*coupon/frequency+(face if i==n else 0)) for i in range(1,n+1)]
    pv=[(i,cash/base**i) for i,cash in cashflows];price=sum(value for _,value in pv)
    macaulay=sum(i/frequency*value for i,value in pv)/price
    convexity=sum(i*(i+1)*value for i,value in pv)/(price*frequency**2*base**2)
    return {'price':price,'price_per_100':price/face*100,'macaulay_duration_years':macaulay,'modified_duration':macaulay/base,'convexity':convexity}

def register(app):
    @app.post('/api/calculators/options')
    def options(body:OptionScenario):
        result=black_scholes(body.spot,body.strike,body.days/365,body.volatility_pct/100,body.rate_pct/100,body.dividend_pct/100)
        payoff=[]
        for i in range(41):
            s=body.spot*(.5+i/40)
            payoff.append({'spot':s,'long_call_pnl_per_unit':max(s-body.strike,0)-result['call']['price'],'long_put_pnl_per_unit':max(body.strike-s,0)-result['put']['price']})
        return {**result,'payoff':payoff,'inputs':body.model_dump(),'source':'User-supplied scenario inputs; Black–Scholes–Merton model',
                'reference':'https://prd-web.optionseducation.org/advancedconcepts/black-scholes-formula',
                'assumptions':'European exercise, constant volatility/rates, continuous dividend yield, ACT/365 time. Price/Greeks are per unit of underlying, not per contract. Vega/rho are per one percentage point; theta per calendar day. Does not model American exercise, discrete dividends, smile, bid/ask or transaction costs. Expiry payoff subtracts theoretical premium without financing. No live option chain.'}

    @app.post('/api/calculators/bonds')
    def bonds(body:BondScenario):
        try:
            result=bond_price(body.face,body.coupon_pct/100,body.yield_pct/100,body.years,body.frequency)
            scenarios=[{'shock_bps':bps,**bond_price(body.face,body.coupon_pct/100,body.yield_pct/100+bps/10000,body.years,body.frequency)} for bps in (-100,-50,0,50,100)]
        except ValueError as e:raise HTTPException(400,str(e))
        return {**result,'scenarios':scenarios,'inputs':body.model_dump(),'source':'User-supplied regular fixed-coupon bond scenario',
                'reference':'https://syndication.finra.org/content/duration-what-interest-rate-hike-could-do-your-bond-portfolio',
                'assumptions':'Valuation on a coupon date with regular full periods, no accrued interest. Nominal annual yield compounded at coupon frequency. No default/call/put/indexation/tax effects or market liquidity. Scenario results reprice exact cash flows under a parallel yield shock; not a traded bond quote.'}
