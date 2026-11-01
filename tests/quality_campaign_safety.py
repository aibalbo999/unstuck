"""Explicit child guards; importing does not install guards or inspect runtime.

Application-level defense for reviewed Python/SQLite paths, NOT an OS sandbox.
The parent owns authorization, private directories, ledger identity handoff,
fresh child/no inherited writable descriptors, and outer process cleanup. Native
code/raw syscalls and a hostile process modifying files concurrently are not
contained here. Install before importing application services or opening DBs.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import stat
import sys
import threading
from urllib.parse import unquote, urlsplit

from quality_campaign_wire import ReplayAbort


def _path(value):
    if isinstance(value, int):
        raise ReplayAbort('Unscoped file descriptor rejected')
    path = Path(os.fsdecode(value))
    if not path.is_absolute() or '..' in path.parts or path.resolve() != path:
        raise ReplayAbort('Absolute nonsymlink path without traversal required')
    return path


def _regular(path, *, private=False, missing=False, unlinked_is_missing=False):
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing:
            return None
        raise ReplayAbort('Required regular file is missing') from None
    if (not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1 and not (unlinked_is_missing and missing and private and info.st_nlink == 0)
            or info.st_uid != os.geteuid()
            or private and stat.S_IMODE(info.st_mode) != 0o600):
        raise ReplayAbort('Owned unlinked regular file with private mode required')
    return None if info.st_nlink == 0 else info


def _directory(value):
    path = _path(value)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.geteuid():
        raise ReplayAbort('Existing owned 0700 directory required')
    return path


def private_path(root, value):
    path = _path(value)
    if path == root or not path.is_relative_to(root):
        raise ReplayAbort('Write outside private job directory rejected')
    if path.exists() and not path.is_dir():
        _regular(path)
    return path


class _Scope:
    def __init__(self, output, ledger_path):
        self.output, self.ledger = _directory(output), _path(ledger_path)
        _directory(self.ledger.parent)
        if self.ledger.is_relative_to(self.output):
            raise ReplayAbort('Shared ledger must be outside the single job output')
        info = _regular(self.ledger, private=True)
        self.pin = (info.st_dev, info.st_ino)
        self.sidecars = {Path(str(self.ledger) + suffix) for suffix in ('-journal', '-wal', '-shm')}
        self.http = self.ledger.with_suffix('.http.jsonl')

    def check(self):
        info = _regular(_path(self.ledger), private=True)
        if (info.st_dev, info.st_ino) != self.pin:
            raise ReplayAbort('Pinned ledger file identity changed')
        for path in self.sidecars:
            # macOS lstat can observe SQLite's just-unlinked journal inode
            # (nlink=0) during another owner's COMMIT. It is absent, not a
            # hardlink or a writable target. Still require the exact type,
            # owner and 0600 mode. Main ledger/HTTP/artifact/write checks keep
            # their strict nlink=1 requirement; never retry or unlink here.
            _regular(_path(path), private=True, missing=True, unlinked_is_missing=True)
        _regular(_path(self.http), private=True, missing=True)

    def database(self, value):
        self.check()
        if value == ':memory:':
            return None
        if str(value).startswith('file:'):
            raise ReplayAbort('SQLite URI is forbidden')
        path = _path(value)
        if path != self.ledger:
            private_path(self.output, path)
            _regular(path, missing=True)
        return path

    def descriptor(self, fd):
        # macOS F_GETPATH=50 from the platform SDK; Linux uses its fd symlink.
        try:
            raw = (fcntl.fcntl(fd, 50, b'\0' * 1024).split(b'\0', 1)[0]
                   if sys.platform == 'darwin' else os.readlink('/proc/self/fd/' + str(fd)))
            path = _path(raw)
            held, current = os.fstat(fd), _regular(path)
            if (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino):
                raise ReplayAbort('Descriptor identity does not match its current path')
            return path, fcntl.fcntl(fd, fcntl.F_GETFL)
        except OSError:
            raise ReplayAbort('Unverified file descriptor rejected') from None


def sqlite_guard(output, original, *, ledger_path):
    scope = _Scope(output, ledger_path)
    def connect(database, *args, **kwargs):
        if kwargs.get('uri') or len(args) > 6 and args[6]:
            raise ReplayAbort('SQLite URI is forbidden')
        path = scope.database(os.fsdecode(database))
        # Re-authorize every statement; cached prepared SQL must not hide drift.
        if len(args) > 5:
            args = (*args[:5], 0, *args[6:])
        else:
            kwargs['cached_statements'] = 0
        connection = original(database, *args, **kwargs)
        def authorize(action, first, second, db_name, trigger):
            try:
                scope.check()
                if action == sqlite3.SQLITE_ATTACH:
                    if first != ':memory:':
                        private_path(scope.output, _path(first))
                        _regular(_path(first), missing=True)
                if action == sqlite3.SQLITE_FUNCTION and second == 'load_extension':
                    return sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_PRAGMA and second is not None:
                    if str(first).lower() in {'temp_store_directory', 'data_store_directory'}:
                        return sqlite3.SQLITE_DENY
                    if str(first).lower() == 'temp_store' and str(second).lower() not in {'memory', '2'}:
                        return sqlite3.SQLITE_DENY
                if path == scope.ledger:
                    allowed = {sqlite3.SQLITE_READ, sqlite3.SQLITE_SELECT, sqlite3.SQLITE_TRANSACTION,
                               sqlite3.SQLITE_INSERT, sqlite3.SQLITE_PRAGMA, sqlite3.SQLITE_FUNCTION}
                    if action not in allowed or action == sqlite3.SQLITE_INSERT and first != 'campaign_events':
                        return sqlite3.SQLITE_DENY
                    if action == sqlite3.SQLITE_PRAGMA and second is not None:
                        permitted = {'synchronous': {'full', '2'}, 'journal_mode': {'delete', 'wal'}}
                        if str(second).lower() not in permitted.get(str(first).lower(), set()):
                            return sqlite3.SQLITE_DENY
            except (ReplayAbort, OSError, TypeError, ValueError):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        try:
            connection.execute('PRAGMA temp_store=MEMORY')
            connection.set_authorizer(authorize)
        except BaseException:
            connection.close()
            raise
        return connection
    return connect


def install_owned_process_boundary():
    """Deny Python process creation from admission until interpreter exit.

    No readonly Git exception here. Native/raw-syscall escapes and hostile code
    are outside this reviewed-Python application boundary, not an OS sandbox.
    Installation is explicit and irreversible in the disposable owned child.
    """
    import _posixsubprocess
    import multiprocessing.process
    import multiprocessing.util
    import subprocess

    denied, lock = 0, threading.Lock()
    def reject(*args, **kwargs):
        nonlocal denied
        with lock: denied += 1
        raise ReplayAbort('Owned child cannot create or replace processes')
    def audit(event, args):
        if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn', 'os.fork', 'os.forkpty'):
            reject()
    sys.addaudithook(audit)
    # CPython 3.13's multiprocessing spawn/forkserver/resource tracker use
    # fork_exec without an audit event. Deny public admission before resource
    # allocation and both stdlib low-level entrypoints before app imports.
    # This is not tamper protection against code restoring saved references.
    multiprocessing.process.BaseProcess.start = reject
    multiprocessing.util.spawnv_passfds = reject
    _posixsubprocess.fork_exec = reject
    subprocess._fork_exec = reject
    def observe():
        with lock:
            return {'policy': 'deny-python-process-creation-v1', 'denied': denied}
    return observe


def write_audit_guard(output, code_root=None, *, ledger_path):
    scope = _Scope(output, ledger_path)
    code_root = _path(code_root) if code_root is not None else None
    creating = threading.local()
    def ensure_private(path):
        if _regular(path, private=True, missing=True) is None:
            # Python's open audit omits creation mode. Precreate the exact file
            # privately so the pending O_CREAT cannot use a caller's 0666 mode.
            creating.path = path
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                os.close(fd)
            except FileExistsError:
                pass
            finally:
                creating.path = None
            _regular(path, private=True)
    def audit(event, args):
        if event == 'open':
            value, mode, flags = args
            writing = (mode and any(char in mode for char in 'wax+')) or flags & (
                os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
            if not writing:
                return
            if not isinstance(value, int) and getattr(creating, 'path', None) == Path(os.fsdecode(value)):
                return
            scope.check()
            path, held_flags = scope.descriptor(value) if isinstance(value, int) else (_path(value), flags)
            if path in scope.sidecars | {scope.ledger, scope.http} and not isinstance(value, int):
                if not flags & os.O_NOFOLLOW:
                    raise ReplayAbort('External writable file requires O_NOFOLLOW')
            if path == scope.ledger:
                if (isinstance(value, int) or mode is not None or flags & (os.O_TRUNC | os.O_APPEND | os.O_EXCL)
                        or flags & (os.O_ACCMODE | os.O_CREAT) != os.O_RDWR | os.O_CREAT):
                    raise ReplayAbort('Main ledger reset or descriptor write forbidden')
            elif path == scope.http:
                if not held_flags & os.O_APPEND or flags & os.O_TRUNC or mode and 'a' not in mode:
                    raise ReplayAbort('Shared HTTP journal only permits append')
                ensure_private(path)
            elif path in scope.sidecars:
                ensure_private(path)
            else:
                private_path(scope.output, path)
        elif event == 'sqlite3.connect':
            scope.database(args[0])
        elif event == 'sqlite3.enable_load_extension':
            raise ReplayAbort('SQLite extensions forbidden')
        elif event in ('os.symlink', 'os.link'):
            raise ReplayAbort('Creating links is forbidden')
        elif event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.chown', 'os.truncate', 'os.utime'):
            scope.check()
            path = scope.descriptor(args[0])[0] if isinstance(args[0], int) else _path(args[0])
            private_path(scope.output, path)
        elif event == 'os.rename':
            scope.check()
            private_path(scope.output, args[0])
            private_path(scope.output, args[1])
        elif event == 'subprocess.Popen' and code_root is not None:
            allowed = [['git', '-C', str(code_root), 'rev-parse', 'HEAD'],
                       ['git', '-C', str(code_root), 'status', '--porcelain=v1', '--untracked-files=normal']]
            if args[0] != 'git' or args[1] not in allowed:
                raise ReplayAbort('Subprocess outside exact readonly Git provenance boundary')
        elif event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn', 'os.fork', 'os.forkpty'):
            raise ReplayAbort('Subprocesses are forbidden')
    return audit


SAFE_TOKEN_COUNTERS = {'max_output_tokens', 'input_tokens', 'output_tokens', 'total_tokens', 'reasoning_tokens',
    'cached_input_tokens', 'tool_prompt_tokens', 'prompt_token_count', 'candidates_token_count', 'total_token_count',
    'thoughts_token_count', 'cached_content_token_count', 'maxOutputTokens', 'promptTokenCount', 'candidatesTokenCount',
    'totalTokenCount', 'thoughtsTokenCount', 'cachedContentTokenCount', 'toolUsePromptTokenCount'}


def credential_values(environment, provider_keys):
    secrets = list(provider_keys)
    for key, value in environment.items():
        if value and re.search(r'(?i)(api.?keys?$|secret|password|auth_token$|access_token$|refresh_token$)', key):
            secrets.append(value)
    redis_url = environment.get('REDIS_URL', '')
    if redis_url:
        secrets.append(redis_url)
        password = urlsplit(redis_url).password
        if password:
            secrets.extend([password, unquote(password)])
    return tuple(dict.fromkeys(value for value in secrets if isinstance(value, str) and value))


def redact(value, secrets=()):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key = str(key)
            sensitive = re.search(r'(?i)(api.?key|authorization|password|secret|credential|key_fingerprint|key_preview|token)', key)
            safe_counter = key in SAFE_TOKEN_COUNTERS and (item is None or type(item) is int and item >= 0)
            safe_container = key in {'llm_token_usage', 'token_usage'} and isinstance(item, dict)
            result[redact(key, secrets)] = ('[redacted]' if sensitive and not (safe_counter or safe_container)
                                            else redact(item, secrets))
        return result
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets) for item in value]
    if value is not None and not isinstance(value, (str, int, float, bool)):
        value = str(value)
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, '[redacted]')
                if len(secret) > 12:
                    value = value.replace(secret[:8] + '...' + secret[-4:], '[anonymous-key-slot]')
        return re.sub(r'AIza[\w-]{20,}', '[redacted]', value)
    return value


class Evidence:
    def __init__(self, root, secrets=(), maximum_bytes=64 * 1024 * 1024):
        self.root, self.secrets = _directory(root), tuple(secrets)
        if type(maximum_bytes) is not int or maximum_bytes <= 0:
            raise ReplayAbort('Positive evidence byte budget required')
        self.maximum_bytes, self.written = maximum_bytes, 0
        self.final_reserve = min(4 * 1024 * 1024, maximum_bytes // 4)
        self.lock = threading.RLock()

    def _write(self, name, value, append):
        path = private_path(self.root, self.root / name)
        payload = (json.dumps(redact(value, self.secrets), ensure_ascii=False, allow_nan=False) + '\n').encode()
        with self.lock:
            final = name in {'outcome.json', 'metrics.json', 'cleanup-error.json'}
            limit = self.maximum_bytes if final else self.maximum_bytes - self.final_reserve
            if self.written + len(payload) > limit:
                raise ReplayAbort('Evidence byte budget exhausted; partial files retained')
            flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | (os.O_APPEND if append else os.O_EXCL)
            fd = os.open(path, flags, 0o600)
            with os.fdopen(fd, 'ab' if append else 'wb') as stream:
                _regular(path, private=True)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            self.written += len(payload)

    def save(self, name, value):
        self._write(name, value, False)

    def append(self, name, value):
        self._write(name, value, True)


class StrictSharedQuota:
    def __init__(self, limiter):
        self.limiter = limiter

    def assert_available(self):
        if self.limiter is None or getattr(self.limiter, '_client', None) is None:
            raise ReplayAbort('Shared quota guard unavailable; no local fallback allowed')

    def __getattr__(self, name):
        self.assert_available()
        value = getattr(self.limiter, name)
        if not callable(value):
            return value
        def checked(*args, **kwargs):
            self.assert_available()
            result = value(*args, **kwargs)
            self.assert_available()
            return result
        return checked


def install_socket_boundary(redis_url):
    """Explicitly resolve approved hosts then constrain TCP connect/connect_ex.

    Caller retains HTTP host/route/credential guards; this is not a native/UDP
    sandbox. No endpoint is resolved until this explicit installation call.
    """
    try:
        redis = urlsplit(redis_url)
        if redis.scheme not in ('redis', 'rediss') or not redis.hostname:
            raise ValueError('invalid endpoint')
        endpoints = [('generativelanguage.googleapis.com', 443), (redis.hostname, redis.port or 6379)]
    except (TypeError, ValueError):
        raise ReplayAbort('Explicit shared Redis endpoint required') from None
    addresses = set()
    for host, port in endpoints:
        addresses.add((host, port))
        for family, socktype, proto, canon, address in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
            addresses.add((address[0], address[1]))
    original, original_ex = socket.socket.connect, socket.socket.connect_ex
    def check(address):
        if not isinstance(address, tuple) or len(address) < 2 or (address[0], address[1]) not in addresses:
            raise ReplayAbort('Socket endpoint outside Gemini/shared Redis boundary')
    def connect(sock, address):
        check(address)
        return original(sock, address)
    def connect_ex(sock, address):
        check(address)
        return original_ex(sock, address)
    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
