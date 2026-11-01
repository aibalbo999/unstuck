"""Real RQ/Redis adapter integration, deliberately not the worker_main CLI smoke."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
CHILD = Path(__file__).with_name('test_maintenance_rq_private_integration_child.py')
BOOTSTRAP = Path(__file__).with_name('test_maintenance_rq_private_integration_bootstrap.py')
REDIS_SERVER = Path('/opt/homebrew/bin/redis-server')


def private_test_base():
    volume=Path('/Volumes/X10 Pro Mac')
    archive=Path(os.environ['STOCK_AGENT_ARCHIVE_DIR']).resolve(strict=True)
    if not os.path.ismount(volume) or not archive.is_relative_to(volume) or archive.stat().st_dev!=volume.stat().st_dev:
        raise RuntimeError('Private integration evidence requires the mounted external archive')
    base=archive/'rq-tests'
    base.mkdir(exist_ok=True,mode=0o700)
    if base.is_symlink() or base.stat().st_dev!=volume.stat().st_dev:
        raise RuntimeError('Private Redis test directory escaped the external archive')
    return base


@pytest.fixture
def record_evidence(request):
    def record(kind, value):
        request.node.user_properties.append((kind, json.dumps(value, sort_keys=True)))
    return record


@contextmanager
def private_redis(record):
    """No inherited endpoints, TCP port, daemon, FLUSHDB or forceful cleanup."""
    if not REDIS_SERVER.is_file():
        pytest.skip('The explicitly inspected local redis-server is unavailable')
    with tempfile.TemporaryDirectory(prefix='rq-', dir=private_test_base()) as directory:
        root = Path(directory).resolve()
        root.chmod(0o700)
        sock = root / 'redis.sock'
        assert len(os.fsencode(sock))<104, 'Private Unix socket path is too long'
        # Relative server-side name avoids spaces in CLIENT LIST's addr field;
        # cwd still binds the socket to this exact external, private directory.
        process = subprocess.Popen([str(REDIS_SERVER), '--port', '0', '--unixsocket', sock.name,
            '--unixsocketperm', '700', '--dir', str(root), '--save', '', '--appendonly', 'no',
            '--daemonize', 'no', '--protected-mode', 'yes'],
            env={'PATH': '/usr/bin:/bin', 'TMPDIR': str(root)}, cwd=root,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 5
            while not sock.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.01)
            assert sock.exists() and process.poll() is None, 'Private Redis failed before socket readiness'
            yield root, sock
        finally:
            sent_term = process.poll() is None
            if process.poll() is None:
                process.terminate()  # Exactly our Popen handle, once. Never SIGKILL.
            logs, _ = process.communicate(timeout=10)
            record('private_redis_cleanup', {'pid': process.pid, 'term_sent': sent_term,
                'returncode': process.returncode, 'tcp_port': 0})
            assert process.returncode == 0, 'Private Redis did not complete graceful shutdown: ' + logs.decode(errors='replace')[-3000:]


def scenario(root, sock, name, record, *, unguarded=False):
    output = root / (name + '.json')
    env = {'PATH': '/usr/bin:/bin', 'TMPDIR': str(root), 'PYTHONDONTWRITEBYTECODE': '1',
        'STOCK_AGENT_PRIVATE_RQ_ROOT': str(root), 'STOCK_AGENT_PRIVATE_RQ_SOCKET': str(sock),
        'STOCK_AGENT_MAINTENANCE_DIR': str(root / 'maintenance')}
    process = subprocess.Popen([sys.executable, '-I', '-B', str(CHILD), name, str(output),
        'unguarded' if unguarded else 'guarded'], env=env, cwd=root,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = process.communicate(timeout=25)
        assert process.returncode == 0, (stdout + stderr).decode(errors='replace')[-6000:]
        assert output.is_file(), 'Child exited without real Redis readback'
        value = json.loads(output.read_text())
        record('private_rq_' + name, value)
        return value
    finally:
        if process.poll() is None:
            process.terminate()  # One graceful owned-child cancellation, no repeated signals.
            process.communicate(timeout=5)


def test_armed_real_rq_preserves_queued_job_without_scheduler_or_execution(record_evidence):
    with private_redis(record_evidence) as (root, sock):
        result = scenario(root, sock, 'armed', record_evidence)
        assert result['statuses'] == ['queued']
        assert result['queue_ids'] == result['job_ids']
        assert result['pause'] == 'MaintenanceBlocked'
        assert result['scheduler'] is None
        assert result['failed_count'] == 0
        assert result['tcp_port'] == 0
        assert result['forbidden_network_denied'] == 3


def assert_owned_teardown(result):
    assert result['controller_errors'] == []
    assert result['failed_count'] == 0
    assert result['children_alive'] == [] and result['pubsub_alive'] is False
    assert result['scheduler']['alive'] is False
    # RQ's one TERM can arrive before macOS spawn installs its graceful handler.
    # Preserve that raw -15 receipt; require a stopped/reaped exact owned child,
    # not an invented claim that its scheduler lock cleanup already ran.
    assert result['scheduler']['exitcode'] in (0, -15)
    assert result['scheduler_signals'] == [{'pid': result['scheduler']['pid'], 'signal': 15}]
    assert result['drained'] is True


@pytest.mark.parametrize('pop', ['single', 'multi'])
def test_real_accepted_job_finishes_after_arm_but_next_job_stays_queued(pop, record_evidence):
    with private_redis(record_evidence) as (root, sock):
        result = scenario(root, sock, 'accepted-' + pop, record_evidence)
        assert result['statuses'] == ['finished', 'queued']
        assert result['results'] == ['accepted-before-arm', None]
        assert result['queue_ids'] == result['job_ids'][1:]
        assert result['events'] == [{'point': 'job', 'drained': False}]
        assert result['pause'] == 'MaintenanceBlocked'
        assert result['pop_calls'] == [{'kind': 'lmove' if pop == 'single' else 'lpop', 'timeout': 5}]
        assert_owned_teardown(result)


@pytest.mark.parametrize('pop', ['single', 'multi'])
def test_real_stale_id_retry_releases_lease_and_cannot_take_next_job(pop, record_evidence):
    with private_redis(record_evidence) as (root, sock):
        result = scenario(root, sock, 'stale-' + pop, record_evidence)
        assert result['statuses'] == ['queued']
        assert result['queue_ids'] == result['job_ids']
        assert result['before_ids'][1:] == result['job_ids']
        assert result['events'] == [{'point': 'stale', 'drained': False}]
        assert result['pop_calls'] == [{'kind': 'lmove' if pop == 'single' else 'lpop', 'timeout': 5}]
        assert result['pause'] == 'MaintenanceBlocked'
        assert_owned_teardown(result)


def test_real_empty_blocking_pop_is_bounded_and_arming_can_drain(record_evidence):
    with private_redis(record_evidence) as (root, sock):
        result = scenario(root, sock, 'empty', record_evidence)
        assert result['statuses'] == [] and result['queue_ids'] == []
        assert result['events'] == [{'point': 'empty-pop', 'drained': False}]
        assert result['pop_calls'] == [{'kind': 'lmove', 'timeout': 5}]
        assert 4.5 <= result['elapsed'] < 7.5
        assert result['pause'] == 'MaintenanceBlocked'
        assert_owned_teardown(result)


def test_normal_private_real_rq_still_publishes_its_math_result(record_evidence):
    with private_redis(record_evidence) as (root, sock):
        result = scenario(root, sock, 'normal', record_evidence)
        assert result['statuses'] == ['finished'] and result['results'] == [9.0]
        assert result['queue_ids'] == [] and result['failed_count'] == 0
        assert result['children_alive'] == [] and result['pubsub_alive'] is False


def test_unguarded_installed_rq_is_a_real_negative_control_not_a_fake_queue(record_evidence):
    with private_redis(record_evidence) as (root, sock):
        result = scenario(root, sock, 'armed', record_evidence, unguarded=True)
        assert result['statuses'] == ['finished'] and result['results'] == [9.0]
        assert result['queue_ids'] == [] and result['pause'] is None


def cli_environment(root, sock):
    bootstrap = root / 'bootstrap'
    bootstrap.mkdir(mode=0o700)
    source = '''import importlib.util, os, sys
try:
    spec = importlib.util.spec_from_file_location('private_cli_startup_boundary', SOURCE)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.install()
except BaseException as error:
    sys.stderr.write('Private startup guard unavailable: ' + type(error).__name__ + '\\n')
    os._exit(75)
'''.replace('SOURCE', repr(str(BOOTSTRAP)))
    (bootstrap / 'sitecustomize.py').write_text(source)
    env = {'PATH': '/usr/bin:/bin', 'TMPDIR': str(root), 'PYTHONPATH': str(bootstrap),
        'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
        'STOCK_AGENT_PRIVATE_RQ_ROOT': str(root), 'STOCK_AGENT_PRIVATE_RQ_SOCKET': str(sock),
        'STOCK_AGENT_MAINTENANCE_DIR': str(root / 'maintenance'),
        'REDIS_TEST_URL': 'unix://' + str(sock) + '?socket_timeout=5&socket_connect_timeout=2',
        'REDIS_URL': 'unix://' + str(sock) + '?socket_timeout=5&socket_connect_timeout=2',
        'TASK_QUEUE_BACKEND': 'rq', 'TASK_QUEUE_NAME': root.name, 'TASK_QUEUE_NAMES': root.name,
        'REPORT_STORAGE_BACKEND': 'memory', 'CACHE_BACKEND': 'memory',
        'LANGGRAPH_CHECKPOINT_BACKEND': 'sqlite', 'LANGGRAPH_CHECKPOINT_POSTGRES_DSN': 'isolated-postgres-disabled'}
    for key, name in {'OUTPUT_DIR': 'output', 'CACHE_DIR': 'cache', 'CACHE_DB_PATH': 'cache.sqlite3',
        'TASK_DB_PATH': 'operational.sqlite3', 'OPERATIONAL_DB_PATH': 'operational.sqlite3',
        'LANGGRAPH_CHECKPOINT_PATH': 'checkpoints.sqlite3', 'WATCHLIST_PATH': 'watchlist.json',
        'WATCHLIST_DB_PATH': 'watchlist.sqlite3', 'SQLITE_BACKUP_DIR': 'backups',
        'MARKET_CALENDAR_DIR': 'market-calendars', 'MPLCONFIGDIR': 'matplotlib', 'XDG_CACHE_HOME': '.cache'}.items():
        env[key] = str(root / name)
    for role in ('ANALYSIS', 'REPORT_RERUN', 'WATCHLIST', 'MAINTENANCE', 'LLM_RETRY'):
        env['TASK_QUEUE_ROUTE_' + role] = root.name
    return env


def startup_case(root, env, command, record):
    output = root / ('cli-' + command + '.json')
    process = subprocess.Popen([sys.executable, '-B', str(BOOTSTRAP), command, str(output)],
        env=env, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = process.communicate(timeout=25)
        if process.returncode != 0 and output.is_file():
            value = json.loads(output.read_text())
            record('private_original_cli_failure', value)
            pytest.fail(json.dumps(value, ensure_ascii=False)[-8000:])
        assert process.returncode == 0, (stdout + stderr).decode(errors='replace')[-6000:]
        value = json.loads(output.read_text())
        record('private_original_cli_' + command, value)
        return value
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=5)


def test_original_cli_smoke_runs_only_after_startup_guard_canary_passes(record_evidence):
    assert all(not path.exists() and not path.is_symlink() for path in (ROOT / '.env', ROOT / 'backend/.env'))
    with private_redis(record_evidence) as (root, sock):
        env = cli_environment(root, sock)
        canary = startup_case(root, env, 'canary', record_evidence)
        assert canary['denied'] == ['TCP', 'DNS', '.env', 'formal_SQLite', 'external_write', 'external_dir_fd']
        assert canary['private_unix_sqlite_write_allowed'] is True
        # Never start the original function until the preceding actual fresh
        # interpreter has proved the startup boundary works, not just PYTHONPATH.
        result = startup_case(root, env, 'original', record_evidence)
        assert len(result['children']) == 2 and all(child['returncode'] == 0 for child in result['children'])
        assert all(child['queue_name'] == child['queue_names'] for child in result['children'])
        assert any(row['status'] == 'queued' and row['result'] is None for row in result['job_receipts'])
        assert any(row['status'] == 'finished' and row['result'] == 9.0 for row in result['job_receipts'])


def test_original_cli_refuses_to_run_without_loaded_startup_guard(tmp_path):
    output = tmp_path / 'must-not-exist.json'
    process = subprocess.Popen([sys.executable, '-I', '-B', str(BOOTSTRAP), 'original', str(output)],
        env={'PATH': '/usr/bin:/bin'}, cwd=tmp_path,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _, stderr = process.communicate(timeout=5)
        assert process.returncode != 0
        assert b'Startup guard was not installed' in stderr
        assert not output.exists() and not (tmp_path / 'maintenance').exists()
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=5)
