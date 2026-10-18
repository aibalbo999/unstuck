import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))

@pytest.fixture(autouse=True)
def memory_cache():
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    yield
    cache_store.reset_cache_store_for_tests()


def test_singleflight_across_threads_and_defensive_copy():
    from shared_provider_cache import shared_fetch
    calls=[]
    def acquire():
        calls.append(1)
        return {'date':'2026-09-22','nested':{'rate':31}}
    with ThreadPoolExecutor(max_workers=8) as executor:
        results=list(executor.map(lambda n: shared_fetch('global',acquire,freshness_seconds=60),range(8)))
    assert len(calls) == 1
    assert sum(meta['cache_hit'] for _,meta in results) == 7
    results[0][0]['nested']['rate']=99
    assert shared_fetch('global',acquire,freshness_seconds=60)[0]['nested']['rate'] == 31


def test_partial_recovery_keeps_last_good_date_and_cooldown(monkeypatch):
    import shared_provider_cache as shared
    now=[1000.]
    monkeypatch.setattr(shared.time,'time',lambda:now[0])
    first,meta=shared.shared_fetch('series',lambda:{'value':4.2,'date':'2026-09-21'},freshness_seconds=10,retention_seconds=100)
    now[0]=1011
    attempts=[]
    def fail():
        attempts.append(1)
        raise TimeoutError('credentials must never be persisted')
    stale,meta=shared.shared_fetch('series',fail,freshness_seconds=10,retention_seconds=100,error_retry_seconds=20)
    assert stale == first and stale['date'] == '2026-09-21'
    assert meta['stale'] is True and meta['fetched_at_epoch'] == 1000
    now[0]=1015
    cached,meta=shared.shared_fetch('series',fail,freshness_seconds=10,retention_seconds=100,error_retry_seconds=20)
    assert len(attempts) == 1 and meta['cooldown'] is True
    now[0]=1032
    fresh,meta=shared.shared_fetch('series',lambda:{'value':4.3,'date':'2026-09-22'},freshness_seconds=10,retention_seconds=100)
    assert fresh['value'] == 4.3 and not meta['stale']


def test_stale_not_retained_past_limit(monkeypatch):
    import shared_provider_cache as shared
    now=[1000.]
    monkeypatch.setattr(shared.time,'time',lambda:now[0])
    shared.shared_fetch('series',lambda:{'value':1},freshness_seconds=10,retention_seconds=20)
    now[0]=1030
    value,meta=shared.shared_fetch('series',lambda:(_ for _ in ()).throw(TimeoutError()),freshness_seconds=10,retention_seconds=20)
    assert value is None and meta['stale'] is False


def test_redis_backend_acquires_named_lock(monkeypatch):
    import cache_store
    from cache_backends import LocalRedisCache
    from shared_provider_cache import shared_fetch
    class Redis:
        def __init__(self): self.data={}; self.locks=[]
        def get(self,key): return self.data.get(key)
        def set(self,key,value,**kwargs): self.data[key]=value
        def lock(self,name,**kwargs):
            self.locks.append((name,kwargs))
            return Lock()
    class Lock:
        def acquire(self): return True
        def release(self): pass
    redis=Redis()
    cache_store.set_cache_backend(LocalRedisCache(redis_client=redis,namespace='isolated'))
    shared_fetch('macro',lambda:{'value':1},freshness_seconds=60)
    assert len(redis.locks) == 1
    assert redis.locks[0][0].startswith('isolated:')
    assert 0 < redis.locks[0][1]['blocking_timeout'] <= 30


def test_busy_singleflight_does_not_issue_duplicate_request(monkeypatch):
    import shared_provider_cache as shared
    @contextmanager
    def busy(key): yield False
    monkeypatch.setattr(shared,'_process_lock',busy)
    calls=[]
    value,meta=shared.shared_fetch('macro',lambda:calls.append(1),freshness_seconds=60)
    assert not calls and value is None
    assert meta['error_kind'] == 'single_flight_busy'


def test_sqlite_singleflight_across_processes(tmp_path):
    import subprocess
    import json
    db=tmp_path/'cache.sqlite3'
    calls=tmp_path/'calls.txt'
    backend_dir=str(Path(__file__).resolve().parents[1]/'backend')
    script='''import sys,time,json
sys.path.insert(0,sys.argv[1])
import config,cache_store
from cache_backends import SqliteCacheBackend
from shared_provider_cache import shared_fetch
config.CACHE_DB_PATH=sys.argv[2]
cache_store.set_cache_backend(SqliteCacheBackend(sys.argv[2]))
def fetch():
    with open(sys.argv[3],'a') as stream: stream.write('request\\n')
    time.sleep(0.15)
    return {'date':'2026-09-22'}
print(json.dumps(shared_fetch('cross-process',fetch,freshness_seconds=60)))
'''
    processes=[subprocess.Popen([sys.executable,'-c',script,backend_dir,str(db),str(calls)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(3)]
    try:
        results=[]
        for process in processes:
            out,err=process.communicate(timeout=15)
            assert process.returncode == 0,err
            results.append(json.loads(out))
        assert calls.read_text().splitlines() == ['request']
        assert sum(meta['cache_hit'] for _,meta in results) == 2
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait()


def test_zero_wait_budget_returns_busy_while_another_thread_fetches():
    import threading
    import time
    from shared_provider_cache import shared_fetch
    entered, release = threading.Event(), threading.Event()
    calls = []
    def slow_fetch():
        entered.set()
        assert release.wait(3)
        return {'date': '2026-09-24'}
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(shared_fetch, 'held-thread', slow_fetch, freshness_seconds=60)
        try:
            assert entered.wait(2)
            started = time.monotonic()
            value, meta = shared_fetch('held-thread', lambda: calls.append('unexpected'),
                                       freshness_seconds=60, lock_wait_seconds=0)
            assert time.monotonic() - started < 0.5
            assert value is None and meta['error_kind'] == 'single_flight_busy'
            assert calls == []
        finally:
            release.set()
        assert first.result(timeout=2)[0] == {'date': '2026-09-24'}


def test_zero_wait_budget_returns_busy_for_held_sqlite_process_lock(tmp_path, monkeypatch):
    import hashlib
    import subprocess
    import time
    import cache_store
    import config
    from cache_backends import SqliteCacheBackend
    from shared_provider_cache import shared_fetch
    db = tmp_path / 'cache.sqlite3'
    monkeypatch.setattr(config, 'CACHE_DB_PATH', str(db))
    cache_store.set_cache_backend(SqliteCacheBackend(str(db)))
    backend_dir = str(Path(__file__).resolve().parents[1] / 'backend')
    script = '''import sys
sys.path.insert(0,sys.argv[1])
import config,cache_store
from cache_backends import SqliteCacheBackend
from shared_provider_cache import _process_lock
config.CACHE_DB_PATH=sys.argv[2]
cache_store.set_cache_backend(SqliteCacheBackend(sys.argv[2]))
with _process_lock(sys.argv[3]) as acquired:
    print('held' if acquired else 'failed',flush=True)
    sys.stdin.readline()
'''
    digest = hashlib.sha256(b'held-process').hexdigest()
    process = subprocess.Popen([sys.executable, '-c', script, backend_dir, str(db), digest],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    calls = []
    try:
        assert process.stdout.readline().strip() == 'held'
        started = time.monotonic()
        value, meta = shared_fetch('held-process', lambda: calls.append('unexpected'),
                                   freshness_seconds=60, lock_wait_seconds=0)
        assert time.monotonic() - started < 0.5
        assert value is None and meta['error_kind'] == 'single_flight_busy'
        assert calls == []
    finally:
        process.communicate('\n', timeout=5)
        if process.poll() is None:
            process.kill()
            process.wait()


def test_thread_and_process_wait_share_one_deadline(monkeypatch):
    import shared_provider_cache as shared
    now = [100.0]
    waits = []
    class Lock:
        def acquire(self, *, timeout):
            waits.append(timeout)
            now[0] += 0.75
            return True
        def release(self): pass
    @contextmanager
    def process_lock(digest, *, blocking_timeout):
        waits.append(blocking_timeout)
        now[0] += blocking_timeout
        yield False
    monkeypatch.setattr(shared, '_LOCKS', (Lock(),))
    monkeypatch.setattr(shared.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(shared, '_process_lock', process_lock)
    calls = []
    _, meta = shared.shared_fetch('budget', lambda: calls.append(1), freshness_seconds=60, lock_wait_seconds=1)
    assert waits == [1, 0.25]
    assert now[0] == 101.0
    assert meta['error_kind'] == 'single_flight_busy' and not calls
def test_explicit_force_refresh_updates_the_shared_value_without_changing_other_keys():
    import cache_store
    from cache_backends import InMemoryCache
    from shared_provider_cache import shared_fetch
    cache_store.set_cache_backend(InMemoryCache());calls=[]
    def acquire(value):
        def read():calls.append(value);return {'value':value}
        return read
    try:
        shared_fetch('force-write-through-target',acquire(1),freshness_seconds=3600)
        shared_fetch('force-write-through-other',acquire(8),freshness_seconds=3600)
        value,meta=shared_fetch('force-write-through-target',acquire(2),freshness_seconds=3600,force_refresh=True)
        assert value=={'value':2} and meta['cache_hit'] is False
        value,meta=shared_fetch('force-write-through-target',acquire(3),freshness_seconds=3600)
        assert value=={'value':2} and meta['cache_hit'] is True
        other,_=shared_fetch('force-write-through-other',acquire(9),freshness_seconds=3600)
        assert other=={'value':8} and calls==[1,8,2]
    finally:cache_store.reset_cache_store_for_tests()


def test_failed_forced_refresh_cannot_hide_error_as_fresh_old_cache(monkeypatch):
    import shared_provider_cache as shared
    import cache_store
    from cache_backends import InMemoryCache
    now=[1000.];monkeypatch.setattr(shared.time,'time',lambda:now[0]);cache_store.set_cache_backend(InMemoryCache())
    calls=[]
    try:
        first,_=shared.shared_fetch('forced-failure',lambda:{'value':1},freshness_seconds=3600,retention_seconds=7200,error_retry_seconds=60)
        other,othermeta=shared.shared_fetch('unchanged-other',lambda:{'value':9},freshness_seconds=3600)
        now[0]=1001
        def fail():
            calls.append('force');raise TimeoutError('timeout')
        forced,forcedmeta=shared.shared_fetch('forced-failure',fail,freshness_seconds=3600,retention_seconds=7200,error_retry_seconds=60,force_refresh=True)
        assert forced==first and forcedmeta['stale'] is True and forcedmeta['error_kind']=='TimeoutError'
        now[0]=1002
        normal,normalmeta=shared.shared_fetch('forced-failure',lambda:pytest.fail('retry before cooldown'),freshness_seconds=3600,retention_seconds=7200,error_retry_seconds=60)
        assert normal==first and calls==['force']
        assert normalmeta.get('stale') is True and normalmeta.get('cooldown') is True and normalmeta.get('error_kind')=='TimeoutError',normalmeta
        assert normalmeta['fetched_at_epoch']==1000
        value,meta=shared.shared_fetch('unchanged-other',lambda:pytest.fail('other key invalidated'),freshness_seconds=3600)
        assert value==other and meta['cache_hit'] is True and meta['stale'] is False and meta['fetched_at_epoch']==othermeta['fetched_at_epoch']
    finally:cache_store.reset_cache_store_for_tests()


def test_busy_lock_can_reuse_only_an_unexpired_cache_without_fetching(monkeypatch):
    import shared_provider_cache as shared
    from contextlib import contextmanager

    calls=[]
    shared.shared_fetch('busy-fresh-cache',lambda:{'value':'last-good'},freshness_seconds=60)

    @contextmanager
    def busy(_digest, _wait):
        yield False

    monkeypatch.setattr(shared,'_shared_lock',busy)
    value,meta=shared.shared_fetch(
        'busy-fresh-cache',lambda:calls.append('unexpected'),
        freshness_seconds=60,lock_wait_seconds=0,
    )

    assert value=={'value':'last-good'}
    assert meta['cache_hit'] is True and meta['stale'] is False
    assert meta['fetched_at_epoch'] is not None
    assert calls==[]


def test_busy_lock_does_not_return_stale_or_force_refresh_cache(monkeypatch):
    import shared_provider_cache as shared
    from contextlib import contextmanager

    now=[1000.]
    monkeypatch.setattr(shared.time,'time',lambda:now[0])
    shared.shared_fetch('busy-stale-cache',lambda:{'value':'old'},freshness_seconds=10,retention_seconds=100)
    now[0]=1011

    @contextmanager
    def busy(_digest, _wait):
        yield False

    monkeypatch.setattr(shared,'_shared_lock',busy)
    calls=[]
    stale,stale_meta=shared.shared_fetch(
        'busy-stale-cache',lambda:calls.append('stale-fetch'),
        freshness_seconds=10,retention_seconds=100,lock_wait_seconds=0,
    )
    forced,forced_meta=shared.shared_fetch(
        'busy-stale-cache',lambda:calls.append('forced-fetch'),
        freshness_seconds=10,retention_seconds=100,lock_wait_seconds=0,force_refresh=True,
    )

    assert stale is None and stale_meta['error_kind']=='single_flight_busy'
    assert forced is None and forced_meta['error_kind']=='single_flight_busy'
    assert calls==[]
