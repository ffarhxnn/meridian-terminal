import asyncio
import httpx
import pytest
from backend import transport

@pytest.fixture(autouse=True)
def clean():
    transport._health.clear()
    transport._limits.clear()
    yield
    transport._health.clear()
    transport._limits.clear()

def test_retry_after_numeric_and_dates():
    assert transport.retry_seconds('30') == 30
    assert transport.retry_seconds('-1') == 0
    assert transport.retry_seconds('bad') == 0
    assert transport.retry_seconds('Thu, 01 Jan 1970 00:01:00 GMT', 0) == 60
    assert transport.retry_seconds('9999999') == 86400

def test_denial_cools_down_without_retry_or_leaking_parameters(monkeypatch):
    calls=[]
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def get(self,url,params=None):
            calls.append(url)
            return httpx.Response(403,request=httpx.Request('GET',url))
    monkeypatch.setattr(transport.httpx,'AsyncClient',Client)
    async def run():
        with pytest.raises(httpx.HTTPStatusError):
            await transport.get('https://provider.example/data',{'apikey':'secret'})
        with pytest.raises(transport.ProviderCoolingDown):
            await transport.get('https://provider.example/data')
    asyncio.run(run())
    assert len(calls)==1
    snapshot=transport.health_snapshot()
    assert snapshot[0]['cooldown_seconds']>=899
    assert 'secret' not in str(snapshot) and '/data' not in str(snapshot)

def test_success_clears_failure_state(monkeypatch):
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def get(self,url,params=None):
            return httpx.Response(200,json={'value':1},request=httpx.Request('GET',url))
    monkeypatch.setattr(transport.httpx,'AsyncClient',Client)
    transport._health['provider.example']={'failures':2,'until':0}
    response=asyncio.run(transport.get('https://provider.example/data'))
    assert response.json()=={'value':1}
    assert transport.health_snapshot()[0]['failures']==0
    assert transport.health_snapshot()[0]['last_success_at']

def test_rate_limit_honors_retry_after_and_allows_later_recovery(monkeypatch):
    calls=[]
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def get(self,url,params=None):
            calls.append(url)
            return httpx.Response(429 if len(calls)==1 else 200,
                headers={'Retry-After':'120'},request=httpx.Request('GET',url))
    monkeypatch.setattr(transport.httpx,'AsyncClient',Client)
    async def run():
        with pytest.raises(httpx.HTTPStatusError):
            await transport.get('https://provider.example/data')
        assert transport.health_snapshot()[0]['cooldown_seconds']>=119
        with pytest.raises(transport.ProviderCoolingDown):
            await transport.get('https://provider.example/data')
        assert len(calls)==1
        transport._health['provider.example']['until']=0
        assert (await transport.get('https://provider.example/data')).status_code==200
    asyncio.run(run())
    assert len(calls)==2
    assert transport.health_snapshot()[0]['failures']==0
