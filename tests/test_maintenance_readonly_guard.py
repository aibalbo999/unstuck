"""Permanent fresh-process regressions from independent exact-URI review."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest


BOOTSTRAP = str(Path(__file__).with_name('test_maintenance_rq_private_integration_bootstrap.py'))
CHILD = r'''
import importlib.util,json,os,sqlite3,sys
from pathlib import Path
root=Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT'])
case=sys.argv[1]
spec=importlib.util.spec_from_file_location('independent_readonly_guard',sys.argv[2])
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
registered=root/'registered.sqlite3'
guard.install(readonly_sqlite_paths=() if case=='unregistered_default' else (registered,))
uri=registered.as_uri()+'?mode=ro'
if case=='rw':uri=registered.as_uri()+'?mode=rw'
elif case=='rwc':uri=registered.as_uri()+'?mode=rwc'
elif case=='extra_query':uri+='&cache=shared'
elif case=='outside':uri=(root.parent/'outside.sqlite3').as_uri()+'?mode=ro'
elif case=='unregistered_path':uri=(root/'unregistered.sqlite3').as_uri()+'?mode=ro'
elif case=='bytes_registered':uri=uri.encode()
elif case=='bytes_outside':uri=((root.parent/'outside.sqlite3').as_uri()+'?mode=ro').encode()
elif case=='bytes_rw':uri=(registered.as_uri()+'?mode=rw').encode()
elif case=='pathlike_registered':uri=Path(uri)
result={'case':case,'denied':False,'read':False,'write_denied':False}
try:
 connection=sqlite3.connect(uri,uri=True)
except (PermissionError,sqlite3.Error) as exc:
 result['denied']=True;result['error_type']=type(exc).__name__
else:
 try:
  result['read']=connection.execute('SELECT value FROM sentinel').fetchone()==('private',)
  try:
   connection.execute("UPDATE sentinel SET value='changed'")
  except sqlite3.Error:result['write_denied']=True
  finally:connection.rollback()
 finally:connection.close()
print(json.dumps(result))
'''


@pytest.mark.parametrize('case', ['exact', 'unregistered_default', 'rw', 'rwc', 'extra_query',
    'outside', 'unregistered_path', 'bytes_registered', 'bytes_outside', 'bytes_rw', 'pathlike_registered'])
def test_only_registered_exact_text_ro_uri_is_admitted(tmp_path, case, record_property):
    private = tmp_path / 'private'; private.mkdir(mode=0o700)
    paths = (private / 'registered.sqlite3', private / 'unregistered.sqlite3', tmp_path / 'outside.sqlite3')
    for path in paths:
        with sqlite3.connect(path) as connection:
            connection.execute('CREATE TABLE sentinel(value TEXT)')
            connection.execute("INSERT INTO sentinel VALUES ('private')")
    env = {'PATH': '/usr/bin:/bin', 'TMPDIR': str(private),
        'STOCK_AGENT_PRIVATE_RQ_ROOT': str(private),
        'STOCK_AGENT_PRIVATE_RQ_SOCKET': str(private / 'redis.sock')}
    child = subprocess.Popen([sys.executable, '-I', '-B', '-c', CHILD, case, BOOTSTRAP],
        cwd=private, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = child.communicate(timeout=10)
        assert child.returncode == 0, stderr
    finally:
        if child.poll() is None:
            child.terminate()  # This exact test-owned process once; no timeout SIGKILL.
            child.communicate(timeout=5)
    result = json.loads(stdout)
    record_property('guard_case', json.dumps(result))
    if case == 'exact':
        assert result['denied'] is False and result['read'] is True and result['write_denied'] is True
    else:
        assert result['denied'] is True, result
    for path in paths:
        with sqlite3.connect(path) as connection:
            assert connection.execute('SELECT value FROM sentinel').fetchall() == [('private',)]
