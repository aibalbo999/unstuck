"""Request admission is shared, bounded and does not stall another source."""
import asyncio
import time

import httpx
import pytest

import search_provider_runtime as runtime


@pytest.fixture
def state(monkeypatch):
    rows = {}
    monkeypatch.setattr(runtime, 'get_cache_json', lambda key: rows.get(key))
    monkeypatch.setattr(runtime, 'set_cache_json', lambda key, value, ttl_seconds: rows.__setitem__(key, value))
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda entries: None)
    monkeypatch.setattr(runtime, 'provider_circuit_state', lambda key: {})
    return rows


def failure(status=429, retry=None):
    response = httpx.Response(status, headers={'Retry-After': str(retry)} if retry else {}, request=httpx.Request('GET', 'https://test.invalid'))
    return httpx.HTTPStatusError('unavailable', request=response.request, response=response)


def test_consecutive_failures_back_off_after_expiry_and_success_resets(state, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(runtime.time, 'time', lambda: now[0])
    key = runtime.scope_key('serpapi', 'credential')
    first = runtime.remember_failure(key, failure())
    now[0] = first['retry_at'] + 1
    second = runtime.remember_failure(key, failure())
    assert second['retry_at'] - now[0] == 600
    assert second['consecutive_failures'] == 2
    now[0] = second['retry_at'] + 1
    async def success(): return ['ok']
    assert asyncio.run(runtime.fetch_search_upstream('serpapi', 'credential', success)) == ['ok']
    now[0] += 2
    assert runtime.remember_failure(key, failure())['consecutive_failures'] == 1


def test_retry_after_is_an_earliest_time_even_beyond_one_day(state, monkeypatch):
    monkeypatch.setattr(runtime.time, 'time', lambda: 1000.0)
    saved = runtime.remember_failure(runtime.scope_key('test'), failure(retry=172800))
    assert saved['retry_at'] >= 173800.0


def test_only_one_expired_endpoint_probe_and_other_provider_continues(state):
    key = runtime.scope_key('test', 'same')
    state[key] = {'retry_at': time.time() - 1, 'consecutive_failures': 1}
    called = []
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def slow():
            called.append('slow')
            entered.set()
            await release.wait()
            return [1]
        async def fast():
            called.append('fast')
            return [2]
        first = asyncio.create_task(runtime.fetch_search_upstream('test', 'same', slow))
        await entered.wait()
        assert await runtime.fetch_search_upstream('test', 'same', fast) == []
        assert await runtime.fetch_search_upstream('other', '', fast) == [2]
        release.set()
        assert await first == [1]
    asyncio.run(scenario())
    assert called == ['slow', 'fast']


def test_endpoint_permission_does_not_block_quote(state):
    key = runtime.scope_key('fmp', 'same', endpoint='news')
    runtime.remember_failure(key, failure(402))
    async def success(): return [1]
    assert asyncio.run(runtime.fetch_search_upstream('fmp', 'same', success, endpoint='news')) == []
    assert asyncio.run(runtime.fetch_search_upstream('fmp', 'same', success, endpoint='quote')) == [1]


def test_stalled_callback_has_total_budget_and_releases_admission(state):
    async def stuck(): await asyncio.sleep(10)
    with pytest.raises(TimeoutError):
        asyncio.run(runtime.fetch_search_upstream('test', '', stuck, timeout_seconds=0.01))
    assert runtime.cooldown_state(runtime.scope_key('test'))['error_kind'] == 'timeout'


def test_gdelt_failure_is_shared_with_international_news_and_rss_survives(state, monkeypatch):
    import external_data_gdelt as gdelt
    calls = []
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
    async def direct():
        calls.append('search')
        raise httpx.ConnectTimeout('unavailable')
    async def unexpected(*a, **k):
        calls.append('gdelt')
        return {'articles': []}
    async def rss(*a):
        calls.append('rss')
        return [{'headline': 'public fallback', 'url': 'https://example.test/1'}]
    monkeypatch.setattr(gdelt, 'async_client', Client)
    monkeypatch.setattr(gdelt, 'async_json_get', unexpected)
    monkeypatch.setattr(gdelt, '_fetch_google_news_rss_fallback', rss)
    monkeypatch.setattr(gdelt, '_gdelt_cooldown_until', 0)
    with pytest.raises(httpx.ConnectTimeout):
        asyncio.run(runtime.fetch_search_upstream('gdelt', '', direct))
    result = asyncio.run(gdelt.fetch_gdelt_international_news_context(max_topics=2, request_spacing_seconds=0))
    assert calls == ['search', 'rss', 'rss']
    assert result['topics'][0]['headline'] == 'public fallback'


def test_guard_storage_failure_sends_no_http_and_keeps_other_endpoints(state, monkeypatch):
    def unavailable(key): raise OSError('cache offline')
    monkeypatch.setattr(runtime, 'get_cache_json', unavailable)
    called = []
    async def fetch():
        called.append(1)
        return [1]
    assert asyncio.run(runtime.fetch_search_upstream('test', '', fetch)) == []
    assert not called


def test_redis_lost_lease_cannot_overwrite_a_new_cooldown(state, monkeypatch):
    import cache_store
    from cache_backends import LocalRedisCache
    key = runtime.scope_key('test')
    class Lock:
        held = True
        def acquire(self): return True
        def owned(self): return self.held
        def release(self): pass
    lock = Lock()
    class Redis:
        def lock(self, name, **kwargs):
            assert kwargs['blocking_timeout'] == 0
            assert kwargs['timeout'] > 20
            return lock
    backend = LocalRedisCache(redis_client=Redis(), namespace='isolated')
    monkeypatch.setattr(cache_store, 'get_cache_backend', lambda: backend)
    async def fetched_after_expired_lease():
        state[key] = {'error_kind': 'rate_limited', 'retry_at': time.time() + 600, 'consecutive_failures': 3}
        lock.held = False
        return ['acquired evidence']
    assert asyncio.run(runtime.fetch_search_upstream('test', '', fetched_after_expired_lease)) == ['acquired evidence']
    assert state[key]['consecutive_failures'] == 3
    assert state[key]['error_kind'] == 'rate_limited'


def test_sqlite_expired_endpoint_admits_one_request_across_processes(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    db = tmp_path / 'cache.sqlite3'
    calls = tmp_path / 'calls.txt'
    backend_dir = str(Path(__file__).resolve().parents[1] / 'backend')
    script = '''import asyncio,sys,time
sys.path.insert(0,sys.argv[1])
import config,cache_store,search_provider_runtime as runtime
from cache_backends import SqliteCacheBackend
config.CACHE_DB_PATH=sys.argv[2]
cache_store.set_cache_backend(SqliteCacheBackend(sys.argv[2]))
runtime.record_source_audit_entries=lambda entries:None
runtime.provider_circuit_state=lambda key:{}
async def fetch():
    with open(sys.argv[3],'a') as stream: stream.write('request\\n')
    await asyncio.sleep(0.2)
    return [1]
print(asyncio.run(runtime.fetch_search_upstream('cross-process','',fetch)))
'''
    processes = [subprocess.Popen([sys.executable, '-c', script, backend_dir, str(db), str(calls)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(3)]
    try:
        results = []
        for process in processes:
            out, err = process.communicate(timeout=15)
            assert process.returncode == 0, err
            results.append(out.strip())
        assert calls.read_text().splitlines() == ['request']
        assert sorted(results) == ['[1]', '[]', '[]']
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait()
