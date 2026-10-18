from pathlib import Path

def test_same_request_reuses_only_identical_bytes_and_archive(tmp_path,monkeypatch):
 from reporting.request_projection_reuse import projection_reuse_scope, reuse_projection
 from types import SimpleNamespace
 import runtime_paths
 monkeypatch.setattr(runtime_paths,'current_runtime_paths',lambda:SimpleNamespace(cache_dir=tmp_path))
 archive=tmp_path/'official-response-evidence'/('a'*64+'.gz');archive.parent.mkdir();archive.write_bytes(b'old')
 snapshot={'data':{'raw_evidence':{'raw_response_path':str(archive),'raw_response_sha256':'a'*64}}}
 calls=[]
 def compute():calls.append(1);return {'value':len(calls)}
 with projection_reuse_scope():
  assert reuse_projection(snapshot,'正文',compute)==reuse_projection(snapshot,'正文',compute)
  assert len(calls)==1
  archive.write_bytes(b'changed')
  assert reuse_projection(snapshot,'正文',compute)=={'value':2}
  assert reuse_projection(snapshot,'新正文',compute)=={'value':3}
 with projection_reuse_scope():
  assert reuse_projection(snapshot,'正文',compute)=={'value':4}
 assert reuse_projection(snapshot,'正文',compute)=={'value':5}

def test_reused_value_is_not_mutable_shared_state():
 from reporting.request_projection_reuse import projection_reuse_scope, reuse_projection
 with projection_reuse_scope():
  first=reuse_projection({},'same',lambda:{'items':[]});first['items'].append('mutation')
  assert reuse_projection({},'same',lambda:None)=={'items':[]}

def test_concurrent_thread_reads_compute_once_and_failures_do_not_survive():
 from reporting.request_projection_reuse import projection_reuse_scope, reuse_projection
 from concurrent.futures import ThreadPoolExecutor
 from contextvars import copy_context
 from threading import Event
 import pytest
 calls=[];started=Event();release=Event()
 def compute():
  calls.append(1);started.set();assert release.wait(5);return {'checked':True}
 with projection_reuse_scope(), ThreadPoolExecutor(max_workers=2) as pool:
  a=pool.submit(copy_context().run,reuse_projection,{},'same',compute)
  assert started.wait(5)
  b=pool.submit(copy_context().run,reuse_projection,{},'same',compute)
  release.set();assert a.result()==b.result()=={'checked':True}
  assert len(calls)==1
  with pytest.raises(ValueError):reuse_projection({},'error',lambda:(_ for _ in ()).throw(ValueError()))
  assert reuse_projection({},'error',lambda:{'recovered':True})=={'recovered':True}


def test_untrusted_archive_path_is_not_read_or_reused(tmp_path,monkeypatch):
 from reporting.request_projection_reuse import projection_reuse_scope, reuse_projection
 calls=[]
 def forbidden(*a,**k):raise AssertionError('Out-of-archive path was read')
 monkeypatch.setattr(Path,'read_bytes',forbidden)
 snapshot={'raw_response_path':str(tmp_path/'outside'),'raw_response_sha256':'a'*64}
 with projection_reuse_scope():
  for _ in range(2):reuse_projection(snapshot,'text',lambda:calls.append(1))
 assert calls==[1,1]
