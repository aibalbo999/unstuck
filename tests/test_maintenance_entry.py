"""Existing-entry startup admission: harmless private children, no services."""
import importlib.util
import os
import json
import signal
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / 'scripts' / 'maintenance_entry.py'


def entry():
    spec = importlib.util.spec_from_file_location('maintenance_entry_under_test', ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_armed_entry_does_not_launch_any_command_or_reinitialize(tmp_path):
    # This is a normal user launch, not an internal bypass or partial shell test.
    module = entry()
    root = tmp_path / 'maintenance'
    module.guard.initialize(root)
    plan = {'campaign_id': 'offline-only', 'old_revision': 'a' * 40, 'new_revision': 'b' * 40,
        'control_sha256': 'c' * 64, 'queue_name': 'canary-offline',
        'canaries': [{'mode': mode, 'job_id': 'fixture-' + mode, 'manifest_sha256': 'd' * 64}
                     for mode in ('v1', 'v2', 'v3', 'v4')]}
    module.guard.arm(root, plan)
    marker = tmp_path / 'must-not-run'
    with pytest.raises(module.guard.MaintenanceError):
        module.run_normal_start(root, [sys.executable, '-I', '-c',
            'from pathlib import Path; import sys; Path(sys.argv[1]).touch()', str(marker)], env=dict(os.environ))
    assert not marker.exists()
    assert module.guard.read_state(root)['phase'] == 'arming'


def test_normal_start_holds_inherited_lease_until_owned_readiness(tmp_path):
    module = entry()
    root = tmp_path / 'maintenance'
    module.guard.initialize(root)
    child = r'''
import fcntl, os, stat
lease = int(os.environ['STOCK_AGENT_STARTUP_LEASE_FD'])
ready = int(os.environ['STOCK_AGENT_STARTUP_READY_FD'])
assert stat.S_ISREG(os.fstat(lease).st_mode)
assert stat.S_ISFIFO(os.fstat(ready).st_mode)
os.write(ready, b'R')
os.close(ready)
os.close(lease)
'''
    assert module.run_normal_start(root, [sys.executable, '-I', '-c', child], env=dict(os.environ)) == 0
    assert module.guard.read_state(root)['phase'] == 'normal'


def test_unannounced_startup_exit_is_not_readiness(tmp_path):
    module = entry()
    root = tmp_path / 'maintenance'
    module.guard.initialize(root)
    with pytest.raises(module.EntryError, match='readiness'):
        module.run_normal_start(root, [sys.executable, '-I', '-c', 'pass'], env=dict(os.environ))
    with module.guard.admission(root): pass


def test_public_launcher_dispatches_before_env_pip_traps_or_process_signals():
    source = (ROOT / 'start_mac.command').read_text()
    preamble = source.index('scripts/maintenance_entry.py')
    assert preamble < source.index('LAN_ACCESS=')
    assert preamble < source.index('trap cleanup')
    assert preamble < source.index('load_queue_environment()')
    assert preamble < source.index('-m pip install')
    assert 'signal_startup_ready' in source
    assert source.index('\nsignal_startup_ready\n') < source.index('echo "開啟瀏覽器..."')


def test_internal_shell_start_requires_owned_descriptors(tmp_path):
    source = (ROOT / 'start_mac.command').read_text()
    assert 'scripts/maintenance_entry.py' in source, 'Never execute the unguarded legacy entry as a safety probe'
    from test_maintenance_canary_dispatch_imports import copy_controller
    project = copy_controller(tmp_path)
    for relative in ('scripts/project_python.sh', 'scripts/check_runtime.py'):
        target = project / relative
        target.write_bytes((ROOT / relative).read_bytes())
        target.chmod(0o700)
    env = {'PATH': '/usr/bin:/bin', 'PYTHON_BIN': sys.executable,
           'STOCK_AGENT_MAINTENANCE_DIR': str(tmp_path / 'maintenance')}
    result = subprocess.run(['/bin/bash', str(project / 'start_mac.command'), '--maintenance-owned-start'],
        env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
    assert result.returncode != 0
    assert '維護狀態或啟動收據未通過驗證' in result.stderr, result.stderr
    assert '控制程式來源或載入身分未通過驗證' not in result.stderr
    assert not (tmp_path / 'maintenance').exists()
    assert 'pip' not in result.stdout and '啟動 Worker' not in result.stdout


def test_missing_previously_initialized_namespace_status_is_not_uninitialized(tmp_path, monkeypatch, capsys):
    module = entry()
    root = tmp_path / 'maintenance'
    module.guard.initialize(root)
    root.rename(tmp_path / 'recoverable-control')
    monkeypatch.setenv('STOCK_AGENT_MAINTENANCE_DIR', str(root))
    assert module.main(['--maintenance-status']) == 75
    output = capsys.readouterr()
    assert 'uninitialized' not in output.out and not root.exists()


def test_internal_descriptor_must_match_this_namespaces_admission_lock(tmp_path, monkeypatch):
    module = entry()
    root = tmp_path / 'maintenance'
    module.guard.initialize(root)
    wrong = tmp_path / 'unrelated-regular-file'
    wrong.touch(mode=0o600)
    with wrong.open('rb') as handle:
        reader, writer = os.pipe()
        try:
            monkeypatch.setenv('STOCK_AGENT_MAINTENANCE_DIR', str(root))
            monkeypatch.setenv('STOCK_AGENT_STARTUP_PARENT_PID', str(os.getpid()))
            monkeypatch.setenv('STOCK_AGENT_STARTUP_LEASE_FD', str(handle.fileno()))
            monkeypatch.setenv('STOCK_AGENT_STARTUP_READY_FD', str(writer))
            with pytest.raises(module.EntryError, match='identity'):
                module.validate_owned_start(os.getpid())
        finally:
            os.close(reader); os.close(writer)


def test_existing_public_control_commands_remain_offline_and_bind_control_digest(tmp_path, monkeypatch, capsys):
    module = entry()
    root = tmp_path / 'maintenance'
    monkeypatch.setenv('STOCK_AGENT_MAINTENANCE_DIR', str(root))
    assert module.main(['--maintenance-status']) == 0
    assert json.loads(capsys.readouterr().out)['phase'] == 'uninitialized'
    assert not root.exists()
    assert module.main(['--maintenance-init']) == 0
    assert json.loads(capsys.readouterr().out)['phase'] == 'normal'
    plan = {'campaign_id': 'private-entry', 'old_revision': 'a' * 40, 'new_revision': 'b' * 40,
        'control_sha256': module.control_digest(), 'queue_name': 'private-canary',
        'canaries': [{'mode': mode, 'job_id': mode, 'manifest_sha256': 'd' * 64}
                     for mode in ('v1', 'v2', 'v3', 'v4')]}
    path = tmp_path / 'plan.json'; path.write_text(json.dumps(plan))
    # This release's public entry refuses arming. Exercise the dormant state
    # machine directly with a private fixture, without enabling a CLI switch.
    assert module.main(['--maintenance-arm', str(path)]) == 75
    assert module.guard.read_state(root)['phase'] == 'normal'
    module.guard.arm(root, plan)
    capsys.readouterr()
    assert module.main(['--maintenance-drain', '--timeout-seconds', '0']) == 0
    state = json.loads(capsys.readouterr().out)
    assert state['cooperative_drained'] is True and state['legacy_handover_verified'] is False
    before = module.guard.read_state(root)
    plan['control_sha256'] = 'e' * 64; path.write_text(json.dumps(plan))
    assert module.main(['--maintenance-arm', str(path)]) == 75
    assert module.guard.read_state(root) == before


@pytest.mark.parametrize('failure', [OSError('readiness observer failed'), KeyboardInterrupt()])
def test_readiness_observer_exception_reaps_owned_child_before_return(tmp_path, monkeypatch, failure):
    module = entry()
    root = tmp_path / 'maintenance'; module.guard.initialize(root)
    children, signals = [], []
    real_popen = subprocess.Popen
    def spawn(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        real_signal = child.send_signal
        def send(signum):
            signals.append(signum)
            return real_signal(signum)
        child.send_signal = send
        return child
    monkeypatch.setattr(module.subprocess, 'Popen', spawn)
    monkeypatch.setattr(module.select, 'select', lambda *args: (_ for _ in ()).throw(failure))
    try:
        with pytest.raises(type(failure)) as caught:
            module.run_normal_start(root, [sys.executable, '-I', '-c', 'import time; time.sleep(30)'],
                env={'PATH': '/usr/bin:/bin'})
        assert caught.value is failure
        assert len(children) == 1 and children[0].poll() is not None
        assert signals == [signal.SIGTERM]
    finally:
        for child in children:
            if child.poll() is None: child.terminate()
            child.wait(timeout=5)


@pytest.mark.parametrize('timing', ['before_spawn', 'popen_handoff'])
def test_pending_cancel_cannot_be_lost_or_report_startup_success(tmp_path, monkeypatch, timing):
    module = entry()
    root = tmp_path / 'maintenance'; module.guard.initialize(root)
    children = []
    real_pipe, real_popen = os.pipe, subprocess.Popen
    def pipe():
        if timing == 'before_spawn': signal.raise_signal(signal.SIGTERM)
        return real_pipe()
    def spawn(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        if timing == 'popen_handoff': signal.raise_signal(signal.SIGTERM)
        return child
    monkeypatch.setattr(module.os, 'pipe', pipe)
    monkeypatch.setattr(module.subprocess, 'Popen', spawn)
    try:
        with pytest.raises(module.EntryError, match='cancelled'):
            module.run_normal_start(root, [sys.executable, '-I', '-c', 'import time; time.sleep(30)'],
                env={'PATH': '/usr/bin:/bin'})
        assert len(children) == (0 if timing == 'before_spawn' else 1)
        assert all(child.poll() is not None for child in children)
    finally:
        for child in children:
            if child.poll() is None: child.terminate()
            child.wait(timeout=5)


@pytest.mark.parametrize('value', [-1, True, float('nan'), float('inf')])
def test_invalid_explicit_readiness_timeout_cannot_start_child(tmp_path, value):
    module = entry()
    with pytest.raises(module.EntryError, match='timeout'):
        module.run_normal_start(tmp_path / 'not-initialized', ['must-not-execute'], env={},
            ready_timeout_seconds=value)
