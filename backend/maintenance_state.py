"""Private filesystem/state contract for the cooperative maintenance gate.

No I/O on import. Public lifecycle/admission operations live in maintenance_guard.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat
import uuid


_SCHEMA = 'stock-agent.maintenance.v1'
_LIMIT = 32768
_LOCKS = ('admission.lock', 'control.lock')


class MaintenanceError(RuntimeError):
    """Maintenance state could not safely authorize this operation."""


class MaintenanceBlocked(MaintenanceError):
    """Maintenance is armed; no new cooperative admission is allowed."""


class MaintenanceUnavailable(MaintenanceError):
    """The persistent namespace is absent, invalid, or no longer the same."""


class MaintenanceBusy(MaintenanceError):
    """Another controller owns the exclusive control operation."""


def _root(root):
    if root is None:
        if 'STOCK_AGENT_MAINTENANCE_DIR' in os.environ:
            root = os.environ['STOCK_AGENT_MAINTENANCE_DIR']
        elif 'CACHE_DIR' in os.environ:
            cache = os.environ['CACHE_DIR']
            if not cache.strip():
                raise MaintenanceUnavailable('Empty CACHE_DIR')
            root = os.path.join(cache, 'maintenance')
        else:
            root = Path(__file__).absolute().parent / 'cache' / 'maintenance'
    raw = os.fspath(root)
    if (not isinstance(raw, str) or not raw.startswith('/') or '\x00' in raw
            or any(part in ('.', '..') for part in raw.split('/'))):
        raise MaintenanceUnavailable('Absolute nonsymlink namespace required')
    parts = [part for part in raw.split('/') if part]
    if not parts:
        raise MaintenanceUnavailable('A dedicated namespace is required')
    return '/' + '/'.join(parts)


def _identity(info):
    return {'device': info.st_dev, 'inode': info.st_ino}


def _private(info, *, directory=False):
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if (not kind(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
            or not directory and (info.st_nlink != 1 or info.st_size > _LIMIT)):
        raise MaintenanceUnavailable('Unsafe maintenance object')


def _directory(path):
    """Open every component without following even an ancestor symlink."""
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.strip('/').split('/') if path != '/' else ():
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise MaintenanceUnavailable('Duplicate maintenance JSON key')
        value[key] = item
    return value


def _integer(value):
    return type(value) is int and value >= 0


def _identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', value) is not None


def _hash(value, length):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is not None


def _anchor_name(name):
    return '.' + name + '.bootstrap'


def _anchor_data(parent, name, fd):
    info = os.fstat(fd)
    _private(info)
    current = os.stat(_anchor_name(name), dir_fd=parent, follow_symlinks=False)
    _private(current)
    if _identity(current) != _identity(info):
        raise MaintenanceUnavailable('Maintenance bootstrap inode drift')
    os.lseek(fd, 0, os.SEEK_SET)
    raw = os.read(fd, _LIMIT + 1)
    if len(raw) != info.st_size or len(raw) > _LIMIT:
        raise MaintenanceUnavailable('Invalid maintenance bootstrap size')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs)
    if (not isinstance(value, dict) or set(value) != {'schema', 'namespace_name', 'namespace_id'}
            or value['schema'] != 'stock-agent.maintenance-bootstrap.v1'
            or value['namespace_name'] != name or not _hash(value['namespace_id'], 32)):
        raise MaintenanceUnavailable('Invalid maintenance bootstrap')
    return value


def _plan(plan):
    fields = {'campaign_id', 'old_revision', 'new_revision', 'control_sha256', 'queue_name', 'canaries'}
    if (not isinstance(plan, dict) or set(plan) != fields or not _identifier(plan['campaign_id'])
            or not _identifier(plan['queue_name']) or not _hash(plan['old_revision'], 40)
            or not _hash(plan['new_revision'], 40) or not _hash(plan['control_sha256'], 64)
            or not isinstance(plan['canaries'], list) or len(plan['canaries']) != 4):
        raise MaintenanceUnavailable('Invalid maintenance plan')
    modes, jobs = set(), set()
    for row in plan['canaries']:
        if (not isinstance(row, dict) or set(row) != {'mode', 'job_id', 'manifest_sha256'}
                or row['mode'] not in ('v1', 'v2', 'v3', 'v4') or not _identifier(row['job_id'])
                or not _hash(row['manifest_sha256'], 64)):
            raise MaintenanceUnavailable('Invalid canary registration')
        modes.add(row['mode']); jobs.add(row['job_id'])
    if len(modes) != 4 or len(jobs) != 4:
        raise MaintenanceUnavailable('Canary identities must be unique')
    return json.loads(json.dumps(plan, allow_nan=False))


class _Namespace:
    def __init__(self, root):
        self.path = _root(root)
        self.parent = self.directory = self.bootstrap = None
        self.locks = {}
        try:
            parent, self.name = os.path.split(self.path)
            self.parent = _directory(parent)
            self.bootstrap = os.open(_anchor_name(self.name), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                     dir_fd=self.parent)
            _anchor_data(self.parent, self.name, self.bootstrap)
            self.directory = os.open(self.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.parent)
            _private(os.fstat(self.directory), directory=True)
            for name in _LOCKS:
                fd = os.open(name, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.directory)
                self.locks[name] = fd
                _private(os.fstat(fd))
                if os.fstat(fd).st_size:
                    raise MaintenanceUnavailable('Stable maintenance lock must be empty')
            self.verify()
        except BaseException:
            self.close()
            raise

    def verify(self):
        _anchor_data(self.parent, self.name, self.bootstrap)
        current = os.stat(self.name, dir_fd=self.parent, follow_symlinks=False)
        _private(current, directory=True)
        if _identity(current) != _identity(os.fstat(self.directory)):
            raise MaintenanceUnavailable('Maintenance namespace inode drift')
        # Re-open ancestors too: an open parent fd alone would hide its rename.
        parent = _directory(os.path.dirname(self.path))
        try:
            if _identity(os.fstat(parent)) != _identity(os.fstat(self.parent)):
                raise MaintenanceUnavailable('Maintenance ancestor inode drift')
        finally:
            os.close(parent)
        for name, fd in self.locks.items():
            item = os.stat(name, dir_fd=self.directory, follow_symlinks=False)
            _private(item)
            if _identity(item) != _identity(os.fstat(fd)) or item.st_size:
                raise MaintenanceUnavailable('Maintenance lock inode drift')

    def read(self):
        self.verify()
        fd = os.open('state.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.directory)
        try:
            info = os.fstat(fd)
            _private(info)
            data = b''
            while len(data) <= _LIMIT:
                part = os.read(fd, min(4096, _LIMIT + 1 - len(data)))
                if not part: break
                data += part
            current = os.stat('state.json', dir_fd=self.directory, follow_symlinks=False)
            _private(current)
            if (len(data) > _LIMIT or _identity(current) != _identity(info)
                    or os.fstat(fd).st_size != len(data)):
                raise MaintenanceUnavailable('Maintenance state changed during read')
            state = json.loads(data.decode('utf-8'), object_pairs_hook=_pairs,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
        finally:
            os.close(fd)
        anchor = _anchor_data(self.parent, self.name, self.bootstrap)
        keys = {'schema', 'namespace_id', 'namespace', 'bootstrap', 'locks', 'generation', 'phase', 'plan'}
        if (not isinstance(state, dict) or set(state) != keys or state['schema'] != _SCHEMA
                or not _hash(state['namespace_id'], 32) or not _integer(state['generation'])
                or state['namespace_id'] != anchor['namespace_id']
                or state['bootstrap'] != _identity(os.fstat(self.bootstrap))
                or state['namespace'] != _identity(os.fstat(self.directory))
                or state['locks'] != {name: _identity(os.fstat(fd)) for name, fd in self.locks.items()}
                or state['phase'] not in ('normal', 'arming', 'cooperatively_drained')):
            raise MaintenanceUnavailable('Invalid maintenance state')
        if state['phase'] == 'normal':
            if state['plan'] is not None or state['generation'] != 0:
                raise MaintenanceUnavailable('Invalid normal maintenance state')
        else:
            _plan(state['plan'])
            if state['generation'] != (1 if state['phase'] == 'arming' else 2):
                raise MaintenanceUnavailable('Invalid maintenance transition generation')
        self.verify()
        return state, _identity(info)

    def close(self):
        for fd in self.locks.values(): os.close(fd)
        self.locks.clear()
        for name in ('directory', 'bootstrap', 'parent'):
            fd = getattr(self, name)
            if fd is not None: os.close(fd); setattr(self, name, None)


@contextmanager
def _namespace(root):
    try:
        ns = _Namespace(root)
    except (OSError, ValueError, UnicodeError, TypeError, RecursionError) as error:
        raise MaintenanceUnavailable('Maintenance namespace unavailable: ' + type(error).__name__) from error
    try:
        yield ns
    finally:
        ns.close()


def _read(ns):
    try:
        return ns.read()
    except (OSError, ValueError, UnicodeError, TypeError, RecursionError) as error:
        raise MaintenanceUnavailable('Maintenance state unavailable: ' + type(error).__name__) from error


def _write(ns, state, previous=None):
    encoded = json.dumps(state, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(encoded) > _LIMIT:
        raise MaintenanceUnavailable('Maintenance state exceeds bound')
    temporary = '.state-' + uuid.uuid4().hex
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=ns.directory)
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if not written: raise MaintenanceUnavailable('Incomplete maintenance state write')
            view = view[written:]
        os.fsync(fd)
        ns.verify()
        if previous is None:
            os.link(temporary, 'state.json', src_dir_fd=ns.directory, dst_dir_fd=ns.directory, follow_symlinks=False)
            os.unlink(temporary, dir_fd=ns.directory)
        else:
            info = os.stat('state.json', dir_fd=ns.directory, follow_symlinks=False)
            _private(info)
            if _identity(info) != previous:
                raise MaintenanceUnavailable('Maintenance state inode drift before write')
            os.replace(temporary, 'state.json', src_dir_fd=ns.directory, dst_dir_fd=ns.directory)
        os.fsync(ns.directory)
    finally:
        os.close(fd)
        try: os.unlink(temporary, dir_fd=ns.directory)
        except FileNotFoundError: pass
