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
