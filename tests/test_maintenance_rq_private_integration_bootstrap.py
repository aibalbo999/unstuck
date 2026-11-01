"""Test-only startup boundary for the unmodified original CLI smoke function."""
import json
import os
from pathlib import Path
import socket
import sys
import threading


ROOT = Path(__file__).resolve().parents[1]


def install(*, readonly_sqlite_paths=()):
    private = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT'])
    target = private / 'redis.sock'
    if private.resolve() != private or not private.is_dir() or private.stat().st_mode & 0o777 != 0o700:
        raise RuntimeError('Private startup directory required')
    if os.environ['STOCK_AGENT_PRIVATE_RQ_SOCKET'] != str(target):
        raise RuntimeError('Exact private socket required')
    readonly_uris = set()
    # Current main performs read-only nightly ownership checks using the exact
    # task DB URI. Register only explicit private database paths, never a prefix.
    configured = [os.environ[key] for key in ('TASK_DB_PATH', 'OPERATIONAL_DB_PATH', 'CACHE_DB_PATH')
                  if os.environ.get(key)]
    for value in (*readonly_sqlite_paths, *configured):
        path = Path(value)
        if not path.is_absolute() or path.resolve() != path or not path.is_relative_to(private):
            raise RuntimeError('Exact private readonly SQLite path required')
        readonly_uris.add(path.as_uri() + '?mode=ro')
    for path in (ROOT / '.env', ROOT / 'backend/.env'):
        if path.exists() or path.is_symlink(): raise RuntimeError('CLI smoke refuses a checkout with .env')
    original, original_ex = socket.socket.connect, socket.socket.connect_ex
    def check(sock, address):
        if sock.family != socket.AF_UNIX or address != str(target):
            raise PermissionError('Private CLI denies every other socket')
    def connect(sock, address):
        check(sock, address)
        return original(sock, address)
    def connect_ex(sock, address):
        check(sock, address)
        return original_ex(sock, address)
    def deny(*args, **kwargs): raise PermissionError('Private CLI denies TCP, DNS and PostgreSQL')
    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
    socket.create_connection = socket.getaddrinfo = socket.gethostbyname = deny

    def own(path, dir_fd=None):
        if isinstance(path, int): return
        value = Path(os.fsdecode(path))
        if value == Path('/dev/null'): return
        if not value.is_absolute() and dir_fd not in (None, -1):
            import fcntl
            base = Path(os.fsdecode(fcntl.fcntl(dir_fd, fcntl.F_GETPATH, b'\0' * 1024).split(b'\0', 1)[0]))
            if not base.resolve().is_relative_to(private): raise PermissionError('Private CLI denies external directory FD')
            value = base / value
        if not value.resolve().is_relative_to(private): raise PermissionError('Private CLI denies external mutation')
        return value.resolve()
    # CPython's open audit omits dir_fd. Preserve the original descriptor-relative
    # syscall; bind just its synchronous audit to the resolved owned directory FD.
    opening = threading.local()
    original_open = os.open
    def scoped_open(path, flags, mode=0o777, *, dir_fd=None):
        previous = getattr(opening, 'target', None)
        writing = flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        opening.target = (os.fspath(path), own(path, dir_fd)) if dir_fd is not None and writing else None
        try:
            return original_open(path, flags, mode, dir_fd=dir_fd)
        finally:
            opening.target = previous
    os.open = scoped_open
    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes)):
            if Path(os.fsdecode(args[0])).name == '.env': raise PermissionError('Private CLI denies .env reads')
            if args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                target = getattr(opening, 'target', None)
                own(target[1] if target and target[0] == args[0] else args[0])
        elif event == 'sqlite3.connect':
            database = os.fspath(args[0])
            if not isinstance(database, str):
                raise PermissionError('Private CLI requires text SQLite paths')
            if database == ':memory:':
                return
            if database.startswith('file:'):
                if type(args[0]) is str and database in readonly_uris:
                    return
                raise PermissionError('Private CLI denies unregistered SQLite URI')
            own(database)
        elif event in ('os.mkdir', 'os.chmod'):
            own(args[0], args[2])
        elif event in ('os.remove', 'os.rmdir'):
            own(args[0], args[1])
        elif event == 'os.truncate': own(args[0])
        elif event in ('os.rename', 'os.link'):
            own(args[0], args[2]); own(args[1], args[3])
        elif event == 'os.symlink':
            own(args[0], args[2]); own(args[1], args[2])
        elif event == 'socket.connect': check(args[0], args[1])
        elif event in ('socket.getaddrinfo', 'socket.gethostbyname'): deny()
    sys.addaudithook(audit)
    try:
        import psycopg
    except ImportError:
        pass
    else:
        psycopg.connect = deny
        psycopg.Connection.connect = deny
        psycopg.AsyncConnection.connect = deny
    os.environ['STOCK_AGENT_PRIVATE_RQ_GUARD_PID'] = str(os.getpid())
    receipt = {'pid': os.getpid(), 'argv': sys.argv, 'loaded_before_application':
        not any(name in sys.modules for name in ('config', 'api', 'worker_main'))}
    fd = os.open(private / 'startup-receipts.jsonl', os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as stream: stream.write(json.dumps(receipt) + '\n')


def require_startup_guard():
    if os.environ.get('STOCK_AGENT_PRIVATE_RQ_GUARD_PID') != str(os.getpid()):
        raise RuntimeError('Startup guard was not installed in this fresh interpreter')


def canary():
    require_startup_guard()
    import sqlite3
    from redis import Redis
    private = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT'])
    connection = Redis(unix_socket_path=str(private / 'redis.sock'), socket_timeout=2)
    assert connection.ping() is True
    connection.close()
    permitted = sqlite3.connect(private / 'canary.sqlite3')
    permitted.execute('CREATE TABLE control (value TEXT)'); permitted.close()
    (private / 'allowed-output').write_text('private only')
    directory = os.open(private, os.O_RDONLY | os.O_DIRECTORY)
    previous = Path.cwd()
    try:
        os.chdir(ROOT)
        descriptor = os.open('owned-relative-file', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
        os.close(descriptor)
        os.rename('owned-relative-file', 'owned-relative-renamed', src_dir_fd=directory, dst_dir_fd=directory)
        os.unlink('owned-relative-renamed', dir_fd=directory)
    finally:
        os.chdir(previous)
        os.close(directory)
    denied = []
    def expect(label, action):
        try: action()
        except PermissionError: denied.append(label)
        else: raise RuntimeError('Startup boundary did not reject ' + label)
    with socket.socket(socket.AF_INET) as probe:
        expect('TCP', lambda: probe.connect(('127.0.0.1', 6379)))
    expect('DNS', lambda: socket.getaddrinfo('provider.invalid', 443))
    expect('.env', lambda: (ROOT / 'backend/.env').read_bytes())
    expect('formal_SQLite', lambda: sqlite3.connect('/Volumes/X10 Pro Mac/stock-agent/backend/cache/operational.sqlite3'))
    expect('external_write', lambda: (private.parent / (private.name + '-denied')).write_text('must not write'))
    directory = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        expect('external_dir_fd', lambda: os.open('must-not-create', os.O_WRONLY | os.O_CREAT, dir_fd=directory))
    finally:
        os.close(directory)
    return {'denied': denied, 'private_unix_sqlite_write_allowed': True}


def original_smoke():
    require_startup_guard()
    import hashlib
    import importlib.util
    import subprocess
    import maintenance_guard as guard
    from rq.job import Job
    private = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT'])
    guard.initialize(private / 'maintenance')
    source = ROOT / 'tests/test_worker_process_smoke.py'
    spec = importlib.util.spec_from_file_location('original_private_smoke', source)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    receipts, children = [], []
    refresh = Job.refresh
    def observed_refresh(job):
        result = refresh(job)
        receipts.append({'job_id': job.id, 'status': job.get_status(refresh=False), 'result': job.return_value()})
        return result
    Job.refresh = observed_refresh
    real_run = subprocess.run
    def owned_run(command, **kwargs):
        # Keep the original API/worker command and assertions. Replace only
        # subprocess.run's implicit SIGKILL-on-timeout with one TERM + reap.
        timeout, check = min(kwargs.pop('timeout', 20), 20), kwargs.pop('check', False)
        if command[0] != sys.executable: raise RuntimeError('Original smoke may only launch its exact Python')
        if command[1:2] != ['-c'] and command[1:] != [str(ROOT / 'backend/worker_main.py'), '--role', 'queue', '--burst', '--max-jobs', '1']:
            raise RuntimeError('Unexpected original smoke child command')
        child_env = kwargs['env']
        queue = child_env['TASK_QUEUE_NAME']
        if not queue.startswith('stock-analysis-smoke-'):
            raise RuntimeError('Original smoke did not choose its unique private queue')
        child_env['TASK_QUEUE_NAMES'] = queue
        for role in ('ANALYSIS', 'REPORT_RERUN', 'WATCHLIST', 'MAINTENANCE', 'LLM_RETRY'):
            child_env['TASK_QUEUE_ROUTE_' + role] = queue
        capture = kwargs.pop('capture_output', False)
        if capture: kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process = subprocess.Popen(command, **kwargs)
        try:
            out, err = process.communicate(timeout=timeout)
        except BaseException:
            if process.poll() is None: process.terminate()
            process.communicate(timeout=5)
            raise
        children.append({'pid': process.pid, 'returncode': process.returncode, 'command': command,
            'queue_name': queue, 'queue_names': child_env['TASK_QUEUE_NAMES'],
            'stdout': out[-6000:], 'stderr': err[-6000:]})
        value = subprocess.CompletedProcess(command, process.returncode, out, err)
        if check: value.check_returncode()
        return value
    subprocess.run = owned_run
    try:
        module.test_rq_worker_process_smoke_finishes_one_job_without_api_consuming_it()
    except BaseException as error:
        with open(sys.argv[2], 'x') as stream:
            json.dump({'exception': type(error).__name__, 'children': children, 'job_receipts': receipts}, stream)
        raise
    finally:
        subprocess.run, Job.refresh = real_run, refresh
    startup = [json.loads(line) for line in (private / 'startup-receipts.jsonl').read_text().splitlines()]
    for child in children:
        assert any(row['pid'] == child['pid'] and row['loaded_before_application'] for row in startup)
    return {'original_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'job_receipts': receipts, 'children': children, 'startup': startup}


if __name__ == '__main__':
    import signal
    def cancelled(signum, frame): raise InterruptedError('Private smoke parent cancelled')
    signal.signal(signal.SIGTERM, cancelled)
    sys.path.insert(0, str(ROOT / 'backend'))
    result = canary() if sys.argv[1] == 'canary' else original_smoke()
    with open(sys.argv[2], 'x') as stream: json.dump(result, stream)
