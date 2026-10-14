import asyncio
import json
import sqlite3
from backend.feeds import Cache

def connection(path):
    def db():
        c=sqlite3.connect(path)
        c.row_factory=sqlite3.Row
        c.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY,payload TEXT,expires REAL)')
        return c
    return db

def test_stale_while_revalidate_keeps_one_refresh_and_original_timestamp(tmp_path):
    db=connection(tmp_path/'cache.sqlite3')
    with db() as c:
        c.execute('INSERT INTO cache VALUES (?,?,?)',('quote',json.dumps({'mode':'provider','price':100,'as_of':'2026-01-01'}),0))
    cache=Cache(db)
    async def run():
        started=asyncio.Event();release=asyncio.Event();calls=[]
        async def loader():
            calls.append(1);started.set();await release.wait()
            return {'mode':'provider','price':110,'as_of':'2026-01-02'}
        stale=await cache.fetch('quote',loader,60,{},background=True)
        assert stale['mode']=='stale' and stale['refreshing']
        assert stale['price']==100 and stale['as_of']=='2026-01-01'
        await cache.fetch('quote',loader,60,{},background=True)
        await started.wait()
        # A second reader must return while the upstream loader is blocked.
        second=await asyncio.wait_for(cache.fetch('quote',loader,60,{},background=True),timeout=.2)
        assert second['mode']=='stale'
        assert len(calls)==1 and len(cache.tasks)==1
        release.set();await asyncio.gather(*cache.tasks.values())
        fresh=await cache.fetch('quote',loader,60,{})
        assert fresh['mode']=='provider' and fresh['price']==110
        assert fresh['as_of']=='2026-01-02' and len(calls)==1
    asyncio.run(run())

def test_background_failure_retains_stale_data_and_backoff(tmp_path):
    db=connection(tmp_path/'cache.sqlite3')
    with db() as c:
        c.execute('INSERT INTO cache VALUES (?,?,?)',('quote',json.dumps({'mode':'provider','price':100,'as_of':'2026-01-01'}),0))
    cache=Cache(db)
    async def run():
        calls=[]
        async def loader():calls.append(1);raise ValueError('Provider unavailable')
        await cache.fetch('quote',loader,60,{},background=True)
        await asyncio.gather(*cache.tasks.values())
        result=await cache.fetch('quote',loader,60,{})
        assert result['mode']=='stale' and result['price']==100
        assert result['as_of']=='2026-01-01' and len(calls)==1
        assert 'refreshing' not in result
    asyncio.run(run())
