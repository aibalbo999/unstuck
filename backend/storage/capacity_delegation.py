"""Explicit readonly capacity capability for an already supervised private job.

The parent/guardian own the shared kernel lease. This child capability is only
application admission; it cannot reserve physical bytes or weaken audit hooks.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import threading

from .capacity import StorageCapacityUnavailable, _shared, _owner

_DELEGATED = ContextVar('stock_guarded_job_capacity', default=None)
COMPONENTS = {'source', 'artifacts', 'evidence', 'sqlite', 'temporary'}
REGISTRY = Path('/Volumes/X10 Pro Mac/project-system-tools/work/capacity-reservations')


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def reviewed_budget(reference, *, manifest_sha256, job_id, source_bytes):
    """A separately pinned review is required for a NEW guarded launch."""
    if not isinstance(reference, dict) or set(reference) != {'path', 'sha256'}:
        raise StorageCapacityUnavailable('Explicit reviewed storage budget reference required before launch')
    path = Path(reference['path'])
    if not path.is_absolute() or path.resolve() != path or path.is_symlink() or path.stat().st_size > 65536:
        raise StorageCapacityUnavailable('Invalid reviewed storage budget path')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference['sha256']:
        raise StorageCapacityUnavailable('Reviewed storage budget changed')
    row = json.loads(raw)
    if (set(row) != {'schema', 'decision', 'manifest_sha256', 'job_id', 'components', 'maximum_files', 'basis'}
            or row['schema'] != 'stock.storage-budget-review.v1' or row['decision'] != 'reviewed'
            or row['manifest_sha256'] != manifest_sha256 or row['job_id'] != job_id
            or type(row['components']) is not dict or set(row['components']) != COMPONENTS
            or any(type(v) is not int or v <= 0 for v in row['components'].values())
            or type(row['maximum_files']) is not int or not 0 < row['maximum_files'] <= 100000
            or type(row['basis']) is not dict or set(row['basis']) != COMPONENTS
            or any(type(v) is not str or not v.strip() for v in row['basis'].values())
            or type(source_bytes) is not int or source_bytes < 0 or row['components']['source'] < source_bytes):
        raise StorageCapacityUnavailable('Incomplete or mismatched reviewed storage estimate')
    return row


def prepare_parent_claim(output, job_id, manifest_sha256, review, *, lifetime_identity=None):
    module = _shared()
    root = module.external(output)
    limit = sum(review['components'].values())
    binding = {'schema': 'stock.readonly-capacity.v1', 'output': str(root), 'job_id': job_id,
               'manifest_sha256': manifest_sha256, 'limit_bytes': limit,
               'maximum_files': review['maximum_files']}
    if lifetime_identity is not None:
        binding['lifetime_pipe'] = dict(lifetime_identity)
    digest = hashlib.sha256(_encoded(binding)).hexdigest()
    lease = module.Reservation(module.estimate_peak(limit + 65536), None,
        'Guarded stock job storage binding ' + digest, project_root=Path(__file__).resolve().parents[2])
    lease.__enter__()
    path = module.REGISTRY / (lease.id + '.lock')
    try:
        readonly_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except BaseException:
        lease.__exit__(*__import__('sys').exc_info())
        raise
    info = os.fstat(readonly_fd)
    capability = {**binding, 'binding_sha256': digest, 'claim_id': lease.id,
                  'claim_device': info.st_dev, 'claim_inode': info.st_ino}
    return lease, readonly_fd, capability


class ReadonlyCapacity:
    def __init__(self, fd, capability, *, output, job_id, manifest_sha256, lifetime_fd=None):
        if type(fd) is not int or type(capability) is not dict:
            raise StorageCapacityUnavailable('Explicit readonly storage capability required')
        keys = {'schema', 'output', 'job_id', 'manifest_sha256', 'limit_bytes', 'maximum_files',
                'binding_sha256', 'claim_id', 'claim_device', 'claim_inode'}
        if 'lifetime_pipe' in capability:
            keys.add('lifetime_pipe')
        if set(capability) != keys:
            raise StorageCapacityUnavailable('Invalid readonly storage capability fields')
        self.row = dict(capability)
        self.root = Path(output)
        if (capability['schema'] != 'stock.readonly-capacity.v1' or capability['output'] != str(self.root)
                or capability['job_id'] != job_id or capability['manifest_sha256'] != manifest_sha256
                or type(capability['limit_bytes']) is not int or capability['limit_bytes'] <= 0
                or type(capability['maximum_files']) is not int or capability['maximum_files'] <= 0):
            raise StorageCapacityUnavailable('Storage capability does not match this exact job')
        binding = {key: capability[key] for key in ('schema','output','job_id','manifest_sha256','limit_bytes','maximum_files')}
        if 'lifetime_pipe' in capability:
            binding['lifetime_pipe'] = capability['lifetime_pipe']
        if hashlib.sha256(_encoded(binding)).hexdigest() != capability['binding_sha256']:
            raise StorageCapacityUnavailable('Storage capability binding changed')
        if ('lifetime_pipe' in capability) != (lifetime_fd is not None):
            raise StorageCapacityUnavailable('Explicit readonly lifetime pipe does not match the capacity binding')
        self.lifetime_fd = lifetime_fd
        self.fd, self.pid = fd, os.getpid()
        self.lock, self.active = threading.RLock(), {}
        self.materialized = {}
        self.root_pin = self.root.stat().st_dev, self.root.stat().st_ino
        self.check()

    def check(self):
        # No subprocess, registry mutation, credential/environment access or
        # additional writable descriptor is permitted inside the child guard.
        from .capacity import VOLUME, SHARED
        import re
        if os.getpid() != self.pid or not os.path.ismount(VOLUME):
            raise StorageCapacityUnavailable('Readonly capacity owner or mount changed')
        if not re.fullmatch('[a-f0-9]{32}', self.row['claim_id']):
            raise StorageCapacityUnavailable('Invalid shared claim identifier')
        path = REGISTRY / (self.row['claim_id'] + '.lock')
        metadata = path.with_suffix('.json')
        info, current = os.fstat(self.fd), path.lstat()
        root_info = self.root.stat()
        if (fcntl.fcntl(self.fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY
                or not stat.S_ISREG(info.st_mode) or not stat.S_ISREG(current.st_mode)
                or (info.st_dev,info.st_ino) != (self.row['claim_device'],self.row['claim_inode'])
                or (current.st_dev,current.st_ino) != (info.st_dev,info.st_ino)
                or self.root.resolve() != self.root or self.root.is_symlink()
                or (root_info.st_dev,root_info.st_ino) != self.root_pin
                or root_info.st_dev != info.st_dev or info.st_dev != VOLUME.stat().st_dev
                or metadata.is_symlink() or metadata.stat().st_size > 65536):
            raise StorageCapacityUnavailable('Readonly storage capability identity changed')
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            raise StorageCapacityUnavailable('Parent and guardian no longer hold storage capacity')
        if self.lifetime_fd is not None:
            life = os.fstat(self.lifetime_fd)
            if (not stat.S_ISFIFO(life.st_mode)
                    or fcntl.fcntl(self.lifetime_fd,fcntl.F_GETFL)&os.O_ACCMODE != os.O_RDONLY
                    or self.row['lifetime_pipe'] != {'device':life.st_dev,'inode':life.st_ino}):
                raise StorageCapacityUnavailable('Readonly lifetime pipe identity changed')
        row = json.loads(metadata.read_bytes())
        if (row.get('schema') != 'storage-reservation-v1' or row.get('state') != 'active'
                or row.get('id') != self.row['claim_id']
                or row.get('reason') != 'Guarded stock job storage binding ' + self.row['binding_sha256']
                or row.get('remaining_bytes',0) < self.row['limit_bytes']
                or row.get('implementation_sha256') != hashlib.sha256((SHARED / 'shared_capacity.py').read_bytes()).hexdigest()):
            raise StorageCapacityUnavailable('Active shared storage capability no longer matches')

    def used_bytes(self):
        # Allocated blocks plus conservative directory-entry/inode allowance.
        # Logical one-byte files must not become effectively free after a scope
        # closes. This observation remains admission, never an OS disk quota.
        total, count = 4096, 0
        for parent, directories, names in os.walk(self.root, followlinks=False):
            for name in directories + names:
                path = Path(parent) / name
                info = path.lstat()
                if path.is_symlink() or info.st_dev != self.root_pin[0]:
                    raise StorageCapacityUnavailable('Guarded output contains an invalid storage path')
                if stat.S_ISREG(info.st_mode):
                    if info.st_nlink != 1:
                        raise StorageCapacityUnavailable('Guarded output hardlink is not independently budgeted')
                    total += max(info.st_size, getattr(info, 'st_blocks', 0) * 512, 4096) + 4096
                    count += 1
                    # Observed count is checked at each write/stage admission;
                    # callers do not declare a hard prewrite new-file count.
                    if count > self.row['maximum_files']:
                        raise StorageCapacityUnavailable('Reviewed output file count exceeded')
                elif stat.S_ISDIR(info.st_mode):
                    total += max(getattr(info, 'st_blocks', 0) * 512, 4096)
                else:
                    raise StorageCapacityUnavailable('Guarded output contains a nonregular entry')
        return total

    @contextmanager
    def account_materialized(self, paths):
        # Native caller already holds its exclusive artifact writer lock. Only
        # this owner's successful exact paths can reduce its pending amount.
        owner = _owner()
        paths = tuple(dict.fromkeys(Path(path) for path in paths))
        def allocated():
            total = 0
            for path in paths:
                if path.resolve() != path or not path.is_relative_to(self.root):
                    raise StorageCapacityUnavailable('Materialized path leaves the guarded output')
                try: info = path.lstat()
                except FileNotFoundError: continue
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise StorageCapacityUnavailable('Materialized file is not independently owned')
                total += max(info.st_size, getattr(info,'st_blocks',0)*512,4096)+4096
            return total
        with self.lock:
            if owner not in self.active:
                raise StorageCapacityUnavailable('Materialized writer has no active guarded scope')
            before = allocated()
        yield
        with self.lock:
            delta = allocated() - before
            self.materialized[owner] = self.materialized.get(owner,0) + delta
            self.active[owner] = max(0,self.active[owner] - delta)

    @contextmanager
    def reserve(self, target, known_bytes):
        if type(known_bytes) is not int or known_bytes < 0:
            raise StorageCapacityUnavailable('Unknown guarded write size')
        target = Path(target).absolute()
        if target.resolve() != target or not target.is_relative_to(self.root):
            raise StorageCapacityUnavailable('Write is outside the reviewed private job output')
        owner = _owner()
        peak = ((known_bytes + 65536) * 6 + 4) // 5
        with self.lock:
            self.check()
            had_previous = owner in self.active
            previous = self.active.get(owner, 0)
            materialized_before = self.materialized.get(owner,0)
            # Nested scopes reuse the outer metadata/staging allowance.
            proposed = max(previous, (known_bytes*6+4)//5 if had_previous else peak)
            active = sum(self.active.values()) - previous + proposed
            if self.used_bytes() + active > self.row['limit_bytes']:
                raise StorageCapacityUnavailable('Reviewed guarded storage budget exceeded before write')
            self.active[owner] = proposed
        try:
            yield self
        finally:
            with self.lock:
                if had_previous:
                    delta = self.materialized.get(owner,0) - materialized_before
                    self.active[owner] = max(0,previous-delta)
                else:
                    self.active.pop(owner, None)
                    self.materialized.pop(owner, None)


def install_readonly_capacity(fd, capability, *, output, job_id, manifest_sha256, lifetime_fd=None):
    """Call once in a fresh owned child before installing its permanent guard."""
    if _DELEGATED.get() is not None:
        raise StorageCapacityUnavailable('Readonly job capacity already installed')
    capacity = ReadonlyCapacity(fd, capability, output=output, job_id=job_id, manifest_sha256=manifest_sha256, lifetime_fd=lifetime_fd)
    _DELEGATED.set(capacity)
    return capacity


def current_readonly_capacity():
    return _DELEGATED.get()
