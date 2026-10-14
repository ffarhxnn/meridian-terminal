"""Bounded public-feed requests and sanitized process-local provider health."""
import asyncio
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
import httpx

_health = {}
_limits = {}
_sec_gate = None
_sec_last_started = 0.0

class ProviderCoolingDown(httpx.HTTPError):
    pass

def retry_seconds(value, wall_time=None):
    if not value:
        return 0
    try:
        return max(0, min(86400, float(value)))
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            return max(0, min(86400, date.timestamp() - (time.time() if wall_time is None else wall_time)))
        except (ValueError, TypeError, OverflowError):
            return 0

def health_snapshot():
    now = time.monotonic()
    return [dict(host=host, failures=row['failures'], last_status=row.get('status'),
                 last_attempt_at=row.get('attempt'), last_success_at=row.get('success'),
                 latency_ms=row.get('latency'), cooldown_seconds=round(max(0,row.get('until',0)-now)))
            for host,row in sorted(_health.items())]

async def get(url, params=None):
    host = urlparse(url).hostname
    if not host or urlparse(url).scheme != 'https':
        raise ValueError('Public feed requests require HTTPS')
    # SEC fair access is aggregate across its hosts: at most five starts/sec.
    if host == 'sec.gov' or host.endswith('.sec.gov'):
        global _sec_gate, _sec_last_started
        if _sec_gate is None:
            _sec_gate = asyncio.Lock()
        async with _sec_gate:
            await asyncio.sleep(max(0, .2-(time.monotonic()-_sec_last_started)))
            _sec_last_started = time.monotonic()
    async with _limits.setdefault(host, asyncio.Semaphore(4)):
        row = _health.setdefault(host, {'failures':0,'until':0})
        if time.monotonic() < row['until']:
            raise ProviderCoolingDown('Provider temporarily cooling down; cached observations may be available')
        start = time.monotonic()
        row['attempt'] = datetime.now(timezone.utc).isoformat()
        row['status'] = None
        response = None
        try:
            async with httpx.AsyncClient(timeout=18, follow_redirects=True,
                headers={'User-Agent':'MeridianPersonalTerminal/0.6 (public data research)'}) as client:
                response = await client.get(url, params=params)
            row['status'] = response.status_code
            response.raise_for_status()
        except (httpx.HTTPError, OSError):
            row['failures'] += 1
            delay = min(300, 5 * 2 ** min(row['failures']-1,6))
            if row.get('status') in (401,403):
                delay = 900
            if response is not None and response.status_code in (429,503):
                delay = max(delay,retry_seconds(response.headers.get('Retry-After')))
            row['until'] = time.monotonic()+delay
            raise
        else:
            row.update(failures=0,until=0,success=datetime.now(timezone.utc).isoformat())
            return response
        finally:
            row['latency'] = round((time.monotonic()-start)*1000)
