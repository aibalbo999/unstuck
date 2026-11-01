"""Native RDB final-save proof, not formal launcher/handover acceptance."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import pytest
from test_maintenance_rq_private_integration import private_test_base


SERVER = Path('/opt/homebrew/bin/redis-server')
CHILD = Path(__file__).with_name('test_maintenance_redis_preservation_child.py')


def record(request, label, value):
    request.node.user_properties.append((label, json.dumps(value, sort_keys=True)))


def client(root, mode, serial):
    output = root / (str(serial) + '-' + mode + '.json')
    env = {'PATH': '/usr/bin:/bin', 'TMPDIR': str(root), 'PYTHONDONTWRITEBYTECODE': '1',
        'STOCK_AGENT_PRIVATE_RQ_ROOT': str(root), 'STOCK_AGENT_PRIVATE_RQ_SOCKET': str(root / 'redis.sock')}
    child = subprocess.Popen([sys.executable, '-I', '-B', str(CHILD), mode, str(output)],
        env=env, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = child.communicate(timeout=8)
        assert child.returncode == 0, (stdout + stderr).decode(errors='replace')[-6000:]
        return json.loads(output.read_text())
    finally:
        if child.poll() is None:
            child.terminate()
            child.communicate(timeout=5)


@contextmanager
def owned_server(root, request, generation):
    assert root.is_dir() and not root.is_symlink() and root.stat().st_mode & 0o777 == 0o700
    assert SERVER.is_file(), 'The exact previously inspected Redis binary is required'
    binary = SERVER.resolve()
    identity = {'path': str(binary), 'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
    process = subprocess.Popen([str(binary), '--port', '0', '--unixsocket', str(root / 'redis.sock'),
        '--unixsocketperm', '700', '--dir', str(root), '--dbfilename', 'dump.rdb',
        '--save', '', '--appendonly', 'no', '--daemonize', 'no', '--protected-mode', 'yes'],
        env={'PATH': '/usr/bin:/bin', 'TMPDIR': str(root)}, cwd=root,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    state = {'shutdown_sent': False, 'cleanup_confirmed': False}
    try:
        deadline = time.monotonic() + 5
        while not (root / 'redis.sock').exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.01)
        assert process.poll() is None and (root / 'redis.sock').exists(), 'Private socket unavailable'
        yield process, state, identity
    finally:
        sent_term = process.poll() is None and not state['shutdown_sent']
        if sent_term: process.terminate()
        logs, _ = process.communicate(timeout=8)
        record(request, 'owned_redis_' + str(generation), {**identity, 'pid': process.pid,
            'shutdown_sent': state['shutdown_sent'], 'fallback_term_sent': sent_term,
            'returncode': process.returncode, 'tcp_port': 0})
        assert process.returncode == 0, logs.decode(errors='replace')[-3000:]
        state['cleanup_confirmed'] = True


def stop(root, process, state, mode, serial):
    assert not state['shutdown_sent'] and process.poll() is None
    state['shutdown_sent'] = True
    try:
        receipt = client(root, mode, serial)
    except BaseException:
        # A child failing before the explicit send marker has not stopped Redis.
        # Once the marker exists, never retry an uncertain shutdown or add TERM.
        state['shutdown_sent'] = (root / ('shutdown-attempt-' + str(serial))).exists()
        raise
    assert receipt['server_pid'] == process.pid
    assert receipt['shutdown_commands'] == [['SHUTDOWN', 'SAVE' if mode == 'shutdown-save' else 'NOSAVE']]
    process.wait(timeout=8)
    assert process.returncode == 0
    return receipt


def round_trip(request, *, final_save):
    root = Path(tempfile.mkdtemp(prefix='rdb-', dir=private_test_base())).resolve()
    states = []
    try:
        root.chmod(0o700)
        with owned_server(root, request, 1) as (process, state, binary):
            states.append(state)
            before = client(root, 'seed', 1)
            assert before['server_pid'] == process.pid
            assert before['late_enqueue_started_ms'] > before['initial_save_completed_ms']
            initial_dump = hashlib.sha256((root / 'dump.rdb').read_bytes()).hexdigest()
            stop_receipt = stop(root, process, state, 'shutdown-save' if final_save else 'shutdown-nosave', 2)
            assert stop_receipt['command_ms'] < before['expire_during_downtime_ms']
            final_dump = hashlib.sha256((root / 'dump.rdb').read_bytes()).hexdigest()
        deadline = time.monotonic() + 3
        while time.time() * 1000 <= before['expire_during_downtime_ms'] + 30:
            assert time.monotonic() < deadline
            time.sleep(.01)
        with owned_server(root, request, 2) as (process, state, binary2):
            states.append(state)
            after = client(root, 'snapshot', 3)
            assert after['readback_ms'] > before['expire_during_downtime_ms']
            assert after['server_pid'] == process.pid and binary2 == binary
            assert after['redis_run_id'] != before['redis_run_id']
            assert after['redis_version'] == before['redis_version'] == '8.8.0'
            assert after['redis_build_id'] == before['redis_build_id']
            stop(root, process, state, 'shutdown-nosave', 4)
        evidence = {'before': before, 'after': after, 'initial_dump_sha256': initial_dump,
            'final_dump_sha256': final_dump, 'binary': binary, 'final_save': final_save,
            'final_stop': stop_receipt}
        record(request, 'preservation_evidence', evidence)
        return evidence
    finally:
        if states and all(state['cleanup_confirmed'] for state in states):
            shutil.rmtree(root)
        else:
            record(request, 'unconfirmed_cleanup_directory_retained', str(root))


def without_expired(rows, expired_key):
    return {key: value for key, value in rows.items() if key != expired_key}


def test_initial_save_then_late_enqueue_nosave_loses_late_state(request):
    value = round_trip(request, final_save=False)
    before, after = value['before'], value['after']['snapshot']
    assert value['initial_dump_sha256'] == value['final_dump_sha256']
    assert after == without_expired(before['initial'], before['expired_key'])
    assert after != without_expired(before['final'], before['expired_key'])
    assert before['late_guard_key'] not in after
    for label in ('late-last', 'late-front'):
        assert 'rq:job:' + before['job_ids'][label] not in after


def test_final_shutdown_save_preserves_every_payload_order_schedule_and_absolute_expiry(request):
    value = round_trip(request, final_save=True)
    before, after = value['before'], value['after']['snapshot']
    assert after == without_expired(before['final'], before['expired_key'])
    assert value['initial_dump_sha256'] != value['final_dump_sha256']
    assert before['queue_ids'] == [before['job_ids'][name]
        for name in ('late-front', 'first', 'second', 'late-last')]
    assert before['expired_key'] not in after
    assert after[before['late_guard_key']]['absolute_expiry_ms'] > 0
    assert value['after']['semantic'] == before['semantic']
    jobs = before['semantic']['jobs']
    assert {label: jobs[label]['status'] for label in jobs} == {
        'first': 'queued', 'second': 'queued', 'late-front': 'queued', 'late-last': 'queued',
        'scheduled': 'scheduled', 'late-scheduled': 'scheduled',
        'deferred': 'deferred', 'late-deferred': 'deferred'}
    assert [row[1] for row in before['semantic']['scheduled']] == [
        before['scheduled_epoch'] - 30, before['scheduled_epoch']]
    # Installed RQ 1.16.2 uses BaseRegistry.add(ttl=0): registration epoch,
    # not infinity. Deferred.cleanup is a no-op; raw scores must not be rewritten.
    assert len(before['semantic']['deferred']) == 2
    assert all(before['seed_started_ms'] // 1000 <= row[1] <= before['seed_completed_ms'] // 1000
        for row in before['semantic']['deferred'])
