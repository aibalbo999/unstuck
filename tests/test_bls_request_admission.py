"""Durable pre-send admission; no provider calls or formal databases."""
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import pytest
from bls_request_admission import BlsAdmissionStore, BlsAdmissionBlocked


def store(path, now):
    return BlsAdmissionStore(path_getter=lambda:path, clock=lambda:now)


def test_twenty_five_attempts_are_shared_across_instances(tmp_path):
    path=tmp_path/"quota.sqlite3"
    for i in range(25):
        receipt=store(path,100000+i).reserve()
        assert receipt["reserved"] and receipt["http_request_sent"] is False
    with pytest.raises(BlsAdmissionBlocked) as exc:store(path,100100).reserve()
    assert exc.value.reason == "rolling_24h_limit"
    assert exc.value.retry_after_seconds > 0
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM bls_unregistered_attempts").fetchone()[0]==25


def test_restart_or_failed_request_cannot_refund_attempt(tmp_path):
    path=tmp_path/"quota.sqlite3"
    first=store(path,100000);first.reserve();first.close_current_thread()
    next_store=store(path,100001)
    for _ in range(24):next_store.reserve()
    with pytest.raises(BlsAdmissionBlocked):store(path,100002).reserve()


def test_rolling_window_does_not_reset_at_calendar_midnight(tmp_path):
    path=tmp_path/"quota.sqlite3"
    for _ in range(25):store(path,172799).reserve()
    with pytest.raises(BlsAdmissionBlocked):store(path,172801).reserve()
    store(path,172799+86400).reserve()
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM bls_unregistered_attempts").fetchone()[0]==26


def test_clock_rollback_fails_closed(tmp_path):
    path=tmp_path/"quota.sqlite3";store(path,100000).reserve()
    with pytest.raises(BlsAdmissionBlocked) as exc:store(path,99999).reserve()
    assert exc.value.reason == "clock_rollback"


def test_competing_independent_connections_never_over_admit(tmp_path):
    path=tmp_path/"quota.sqlite3";initial=store(path,100000);initial.reserve();initial.close_current_thread()
    def attempt(_):
        instance=store(path,100001)
        try:instance.reserve();return True
        except BlsAdmissionBlocked:return False
        finally:instance.close_current_thread()
    with ThreadPoolExecutor(max_workers=12) as pool:
        results=list(pool.map(attempt,range(50)))
    assert sum(results)==24


def test_storage_failure_blocks_without_permission_to_send(tmp_path):
    path=tmp_path/"not-a-directory";path.write_text("retained")
    with pytest.raises(BlsAdmissionBlocked) as exc:store(path/"quota.sqlite3",100000).reserve()
    assert exc.value.reason == "admission_store_unavailable"
    assert path.read_text()=="retained"


def test_competing_processes_share_one_ceiling(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    path=tmp_path/"process-quota.sqlite3"
    initial=store(path,100000);initial.reserve();initial.close_current_thread()
    code="""import sys,json
sys.path.insert(0,sys.argv[2])
from bls_request_admission import BlsAdmissionStore,BlsAdmissionBlocked
s=BlsAdmissionStore(path_getter=lambda:sys.argv[1],clock=lambda:100001)
n=0
for _ in range(10):
 try:s.reserve();n+=1
 except BlsAdmissionBlocked:pass
s.close_current_thread()
print(json.dumps(n))
"""
    backend=str(Path(__file__).resolve().parents[1]/"backend")
    def child(_):
        result=subprocess.run([sys.executable,"-c",code,str(path),backend],capture_output=True,text=True,check=True,timeout=20)
        return json.loads(result.stdout)
    with ThreadPoolExecutor(max_workers=6) as pool:admitted=list(pool.map(child,range(8)))
    assert sum(admitted)==24
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM bls_unregistered_attempts").fetchone()[0]==25
