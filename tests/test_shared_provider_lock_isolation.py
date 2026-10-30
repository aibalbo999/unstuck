from hashlib import sha256
from concurrent.futures import ThreadPoolExecutor
import threading,gc
from test_shared_provider_cache import memory_cache


def collision():
 seen={}
 for i in range(1000):
  key=f'independent-source-{i}';digest=sha256(key.encode()).hexdigest();slot=int(digest[:8],16)%64
  if slot in seen:return seen[slot],key
  seen[slot]=key
 raise AssertionError('fixture must find one former striped-lock collision')


def test_distinct_source_keys_never_share_a_local_wait_budget():
 import shared_provider_cache as s
 a,b=collision();held=threading.Event();release=threading.Event();calls=[]
 def first():
  held.set();assert release.wait(3);calls.append(a);return {'source':a}
 with ThreadPoolExecutor(max_workers=2)as pool:
  running=pool.submit(s.shared_fetch,a,first,freshness_seconds=60)
  assert held.wait(1)
  try:value,meta=s.shared_fetch(b,lambda:(calls.append(b)or{'source':b}),freshness_seconds=60,lock_wait_seconds=0)
  finally:release.set();running.result(timeout=3)
 assert value=={'source':b}and not meta.get('error_kind')and set(calls)=={a,b}


def test_same_key_still_serializes_and_busy_reader_never_redownloads():
 import shared_provider_cache as s
 held=threading.Event();release=threading.Event();calls=[]
 def first():held.set();assert release.wait(3);calls.append(1);return {'value':1}
 with ThreadPoolExecutor(max_workers=2)as pool:
  running=pool.submit(s.shared_fetch,'same-exact-source',first,freshness_seconds=60);assert held.wait(1)
  try:value,meta=s.shared_fetch('same-exact-source',lambda:calls.append(2),freshness_seconds=60,lock_wait_seconds=0)
  finally:release.set();running.result(timeout=3)
 assert value is None and meta['error_kind']=='single_flight_busy'and calls==[1]
 assert s.shared_fetch('same-exact-source',lambda:calls.append(3),freshness_seconds=60)[0]=={'value':1}and calls==[1]


def test_idle_registry_entries_are_collectable_without_replacing_active_locks():
 import shared_provider_cache as s
 digest=sha256(b'registry-owner').hexdigest();a=s._local_lock(digest);b=s._local_lock(digest)
 assert a is b
 del b;gc.collect();assert s._local_lock(digest)is a
 del a;gc.collect();assert digest not in s._LOCAL_LOCKS
