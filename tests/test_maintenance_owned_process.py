"""Real private children: persistent attempts must never turn timeout into retry."""
import importlib.util
import inspect
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    spec = importlib.util.spec_from_file_location("owned_process_tested", ROOT / "scripts/maintenance_owned_process.py")
    value = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


CHILD = r'''
import os, signal, sys, time
from pathlib import Path
root = Path(sys.argv[1])
count = 0
def stopping(signum, frame):
    global count
    count += 1
    (root / "signals.json").write_text(str(count))
signal.signal(signal.SIGTERM, stopping)
(root / "ready").touch()
while not (root / "finish").exists():
    time.sleep(.01)
(root / "cleanup").touch()
'''


def wait_path(path, process, seconds=5):
    deadline = time.monotonic() + seconds
    while not path.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(.01)
    assert path.exists()


def binding():
    return {"operation_id": "private-api", "control_sha256": "a" * 64, "backend_revision": "b" * 40}


def test_slow_owned_child_receives_one_term_and_is_not_relaunched_on_timeout(tmp_path):
    adapter = module()
    namespace = tmp_path / "owner"
    namespace.mkdir(mode=0o700)
    controller = adapter.OwnedProcess(namespace, binding())
    process = None
    try:
        controller.start([sys.executable, "-I", "-B", "-c", CHILD, str(tmp_path)],
                         env={"PATH": "/usr/bin:/bin"}, cwd=tmp_path)
        process = controller.process
        wait_path(tmp_path / "ready", process)
        controller.request_stop()
        wait_path(tmp_path / "signals.json", process)
        first = controller.wait_for_exit(0)
        assert first["process_exited"] is False and first["stop_requested"] is True
        assert first["cleanup_verified"] is False and first["handover_verified"] is False
        controller.request_stop()
        assert controller.wait_for_exit(.03)["process_exited"] is False
        with pytest.raises(adapter.ProcessUnavailable):
            adapter.OwnedProcess(namespace, binding())
        assert (tmp_path / "signals.json").read_text() == "1"
        (tmp_path / "finish").touch()
        final = controller.wait_for_exit(5)
        assert final["process_exited"] is True and final["returncode"] == 0
        assert final["cleanup_verified"] is False  # lifecycle receipt is a separate app contract
        assert (tmp_path / "cleanup").exists()
        assert adapter.read_process_record(namespace)["process_exited"] is True
        assert (tmp_path / "signals.json").read_text() == "1"
    finally:
        (tmp_path / "finish").touch()
        if process is not None:
            process.wait(timeout=5)
        controller.close()


@pytest.fixture
def owned(tmp_path):
    adapter = module()
    namespace = tmp_path / "owner"
    namespace.mkdir(mode=0o700)
    controller = adapter.OwnedProcess(namespace, binding())
    yield adapter, controller, namespace
    (tmp_path / "finish").touch()
    if controller.process is not None:
        controller.process.wait(timeout=5)
    controller.close()


def start_private(controller, tmp_path):
    controller.start([sys.executable, "-I", "-B", "-c", CHILD, str(tmp_path)],
                     env={"PATH": "/usr/bin:/bin"}, cwd=tmp_path)
    wait_path(tmp_path / "ready", controller.process)


def test_reentrant_stop_at_claim_boundary_cannot_send_second_signal(owned, tmp_path, monkeypatch):
    adapter, controller, _ = owned
    start_private(controller, tmp_path)
    calls = []
    original = controller.process.send_signal
    def sending(signum):
        calls.append(signum)
        return original(signum)
    monkeypatch.setattr(controller.process, "send_signal", sending)
    method = adapter.OwnedProcess.request_stop
    source, first = inspect.getsourcelines(method)
    target = next(first + index for index, line in enumerate(source) if 'self._stop_attempted = True' in line)
    triggered = False
    previous = sys.gettrace()
    def trace(frame, event, arg):
        nonlocal triggered
        if frame.f_code is method.__code__ and event == "line" and frame.f_lineno == target and not triggered:
            triggered = True
            try:
                controller.request_stop()
            except adapter.ProcessUnavailable:
                pass  # Rejecting reentry is permitted; sending twice is not.
        return trace
    try:
        sys.settrace(trace)
        try:
            controller.request_stop()
        except adapter.ProcessUnavailable:
            pass
    finally:
        sys.settrace(previous)
    assert triggered
    assert calls == [signal.SIGTERM]


def test_none_namespace_never_falls_back_to_environment(tmp_path, monkeypatch):
    adapter = module()
    implicit = tmp_path / "implicit"
    implicit.mkdir(mode=0o700)
    monkeypatch.setenv("STOCK_AGENT_MAINTENANCE_DIR", str(implicit))
    value = None
    try:
        with pytest.raises(adapter.ProcessUnavailable):
            value = adapter.OwnedProcess(None, binding())
        assert list(implicit.iterdir()) == []
    finally:
        if value is not None: value.close()


def test_none_cwd_never_falls_back_to_environment(owned, tmp_path, monkeypatch):
    adapter, controller, namespace = owned
    monkeypatch.setenv("STOCK_AGENT_MAINTENANCE_DIR", str(namespace))
    with pytest.raises(adapter.ProcessUnavailable):
        controller.start([sys.executable, "-I", "-B", "-c", "pass"], env={}, cwd=None)
    assert controller.process is None


def test_none_readback_namespace_never_uses_environment(owned, monkeypatch):
    adapter, controller, namespace = owned
    monkeypatch.setenv("STOCK_AGENT_MAINTENANCE_DIR", str(namespace))
    with pytest.raises(adapter.ProcessUnavailable):
        adapter.read_process_record(None)


@pytest.mark.parametrize("timing", ["before", "after"])
def test_cancelled_signal_never_resends_and_retains_uncertainty(owned, tmp_path, monkeypatch, timing):
    adapter, controller, namespace = owned
    start_private(controller, tmp_path)
    original, calls = controller.process.send_signal, []
    def cancelled(signum):
        calls.append(signum)
        # The exact attempt is durable BEFORE even an uncertain OS send.
        assert adapter.read_process_record(namespace)["stop_requested"] is True
        if timing == "after": original(signum)
        raise KeyboardInterrupt()
    monkeypatch.setattr(controller.process, "send_signal", cancelled)
    with pytest.raises(KeyboardInterrupt):
        controller.request_stop()
    receipt = controller.request_stop()
    assert calls == [signal.SIGTERM]
    assert receipt["phase"] == "stop_unconfirmed" and receipt["signal_call_returned"] is False
    assert receipt["process_exited"] is False and receipt["resume_authorized"] is False
    assert controller.wait_for_exit(0)["process_exited"] is False


def test_failed_intent_fsync_cannot_send_signal_or_retry(owned, tmp_path, monkeypatch):
    adapter, controller, _ = owned
    start_private(controller, tmp_path)
    calls = []
    def failed(fd):
        raise OSError("private-secret-path")
    with monkeypatch.context() as scoped:
        scoped.setattr(adapter.os, "fsync", failed)
        scoped.setattr(controller.process, "send_signal", calls.append)
        with pytest.raises(adapter.ProcessUnavailable) as error:
            controller.request_stop()
        assert "private-secret-path" not in str(error.value)
    with pytest.raises(adapter.ProcessUnavailable):
        controller.request_stop()
    assert calls == [] and controller.process.poll() is None


def test_launch_intent_failure_never_calls_popen(owned, tmp_path, monkeypatch):
    adapter, controller, _ = owned
    calls = []
    def failed(fd):
        raise OSError("cannot confirm fsync")
    monkeypatch.setattr(adapter.os, "fsync", failed)
    monkeypatch.setattr(adapter.subprocess, "Popen", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(adapter.ProcessUnavailable):
        controller.start([sys.executable, "-c", "pass"], env={}, cwd=tmp_path)
    with pytest.raises(adapter.ProcessUnavailable):
        controller.start([sys.executable, "-c", "pass"], env={}, cwd=tmp_path)
    assert calls == [] and controller.process is None


def test_cancelled_spawn_with_unknown_return_never_relaunches_or_adopts_pid(owned, tmp_path, monkeypatch):
    adapter, controller, namespace = owned
    original, children = subprocess.Popen, []
    def interrupted(*args, **kwargs):
        assert adapter.read_process_record(namespace)["phase"] == "launch_unconfirmed"
        children.append(original(*args, **kwargs))
        raise KeyboardInterrupt()
    monkeypatch.setattr(adapter.subprocess, "Popen", interrupted)
    try:
        with pytest.raises(KeyboardInterrupt):
            start_private(controller, tmp_path)
        assert controller.process is None and len(children) == 1
        with pytest.raises(adapter.ProcessUnavailable):
            start_private(controller, tmp_path)
        with pytest.raises(adapter.ProcessUnavailable):
            controller.request_stop()
        assert len(children) == 1
        assert adapter.read_process_record(namespace)["process_exited"] is False
    finally:
        (tmp_path / "finish").touch()
        for child in children: child.wait(timeout=5)


def test_reentrant_launch_does_not_start_a_second_child(owned, tmp_path, monkeypatch):
    adapter, controller, _ = owned
    original, children = subprocess.Popen, []
    def spawn(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(adapter.subprocess, "Popen", spawn)
    method = adapter.OwnedProcess.start
    source, first = inspect.getsourcelines(method)
    target = next(first + index for index, line in enumerate(source) if 'self._launch_attempted = True' in line)
    triggered = False
    previous = sys.gettrace()
    def trace(frame, event, arg):
        nonlocal triggered
        if frame.f_code is method.__code__ and event == "line" and frame.f_lineno == target and not triggered:
            triggered = True
            try: start_private(controller, tmp_path)
            except adapter.ProcessUnavailable: pass
        return trace
    try:
        sys.settrace(trace)
        try: start_private(controller, tmp_path)
        except adapter.ProcessUnavailable: pass
        assert triggered and len(children) == 1
    finally:
        sys.settrace(previous)
        (tmp_path / "finish").touch()
        for child in children: child.wait(timeout=5)


def test_close_during_signal_cannot_close_controller_fds(owned, tmp_path, monkeypatch):
    adapter, controller, _ = owned
    start_private(controller, tmp_path)
    original = controller.process.send_signal
    def send(signum):
        with pytest.raises(adapter.ProcessUnavailable):
            controller.close()
        return original(signum)
    monkeypatch.setattr(controller.process, "send_signal", send)
    assert controller.request_stop()["signal_call_returned"] is True
    assert controller.wait_for_exit(0)["process_exited"] is False


@pytest.mark.parametrize("value", [-1, True, None, float("nan"), float("inf"), 61])
def test_invalid_wait_does_not_signal_or_claim_exit(owned, value):
    adapter, controller, _ = owned
    with pytest.raises(adapter.ProcessUnavailable):
        controller.wait_for_exit(value)
    assert controller.snapshot()["phase"] == "reserved"


@pytest.mark.parametrize("mutation", ["truncated", "garbage", "symlink", "hardlink", "permissions", "replaced"])
def test_corrupt_attempt_never_relaunches_or_claims_cleanup(owned, tmp_path, mutation):
    adapter, controller, namespace = owned
    path = namespace / adapter.JOURNAL
    if mutation == "truncated": path.write_bytes(path.read_bytes()[:-1])
    if mutation == "garbage": path.write_bytes(b"not-a-journal\n")
    if mutation == "permissions": path.chmod(0o644)
    if mutation == "hardlink": os.link(path, tmp_path / "alias")
    if mutation in ("symlink", "replaced"):
        saved = tmp_path / "retained-original"
        path.rename(saved)
        if mutation == "symlink": path.symlink_to(saved)
        else: path.write_bytes(b"foreign object\n"); path.chmod(0o600)
    with pytest.raises(adapter.ProcessUnavailable):
        controller.snapshot()
    with pytest.raises(adapter.ProcessUnavailable):
        adapter.read_process_record(namespace)
    with pytest.raises(adapter.ProcessUnavailable):
        adapter.OwnedProcess(namespace, binding())
    assert controller.process is None


def test_exited_nonzero_is_not_cleanup_and_existing_record_is_never_reused(owned, tmp_path):
    adapter, controller, namespace = owned
    controller.start([sys.executable, "-I", "-B", "-c", "raise SystemExit(7)"], env={}, cwd=tmp_path)
    value = controller.wait_for_exit(5)
    assert value["returncode"] == 7 and value["process_exited"] is True
    assert value["stop_requested"] is False and value["cleanup_verified"] is False
    assert controller.request_stop()["returncode"] == 7
    with pytest.raises(adapter.ProcessUnavailable):
        start_private(controller, tmp_path)
    with pytest.raises(adapter.ProcessUnavailable):
        adapter.OwnedProcess(namespace, binding())


def test_journal_hashes_command_environment_and_does_not_copy_secret_values(owned, tmp_path):
    adapter, controller, namespace = owned
    controller.start([sys.executable, "-I", "-B", "-c", "pass", "PRIVATE-ARGUMENT-SECRET"],
        env={"PRIVATE_TOKEN": "PRIVATE-ENV-SECRET"}, cwd=tmp_path)
    controller.wait_for_exit(5)
    raw = (namespace / adapter.JOURNAL).read_text()
    assert "PRIVATE-ARGUMENT-SECRET" not in raw and "PRIVATE-ENV-SECRET" not in raw
    assert "PRIVATE_TOKEN" not in raw
    assert adapter.read_process_record(namespace)["process_liveness_verified"] is False


def test_real_owner_exit_retains_attempt_without_stopping_or_readopting_child(tmp_path):
    import psutil  # Existing locked test dependency; only observe this private PID.

    adapter = module()
    namespace = tmp_path / "owner"
    namespace.mkdir(mode=0o700)
    script = r'''
import importlib.util, json, os, sys
from pathlib import Path
repo, root, child_code, registration = sys.argv[1:]
sys.path.insert(0, str(Path(repo) / "backend"))
spec = importlib.util.spec_from_file_location("owned_process_owner", Path(repo) / "scripts/maintenance_owned_process.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
root = Path(root)
controller = adapter.OwnedProcess(root / "owner", json.loads(registration))
controller.start([sys.executable, "-I", "-B", "-c", child_code, str(root)], env={"PATH": "/usr/bin:/bin"}, cwd=root)
os._exit(0)  # No library close/finally: emulate controller loss after real Popen.
'''
    parent = subprocess.Popen([sys.executable, "-I", "-B", "-c", script,
        str(ROOT), str(tmp_path), CHILD, json.dumps(binding())],
        env={"PATH": "/usr/bin:/bin"}, cwd=tmp_path, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    orphan = None
    try:
        stdout, stderr = parent.communicate(timeout=5)
        assert parent.returncode == 0, (stdout + stderr).decode(errors="replace")
        receipt = adapter.read_process_record(namespace)
        orphan = psutil.Process(receipt["pid"])
        assert orphan.is_running() and orphan.status() != psutil.STATUS_ZOMBIE
        assert receipt["phase"] == "running" and receipt["process_liveness_verified"] is False
        assert receipt["process_exited"] is False and receipt["resume_authorized"] is False
        with pytest.raises(adapter.ProcessUnavailable):
            adapter.OwnedProcess(namespace, binding())
        assert not (tmp_path / "signals.json").exists()
        assert not (tmp_path / "cleanup").exists()
    finally:
        (tmp_path / "finish").touch()  # Only this private fixture's cooperative completion.
        if parent.poll() is None:
            parent.terminate()  # This test owns the parent; at most one TERM.
            parent.communicate(timeout=5)
        if orphan is not None:
            assert orphan.wait(timeout=5) is None  # Nonchild: do not invent an exit code.
    assert (tmp_path / "cleanup").exists()
    final = adapter.read_process_record(namespace)
    assert final["process_exited"] is False  # No surviving controller recorded an exit.
    assert final["cleanup_verified"] is False and final["handover_verified"] is False
    with pytest.raises(adapter.ProcessUnavailable):
        adapter.OwnedProcess(namespace, binding())
