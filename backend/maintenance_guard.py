"""Version-independent, stdlib-only cooperative maintenance gate.

Import performs no I/O. Only explicit initialize creates a namespace; absence
or corruption never means normal. This does not protect already-running legacy
code, prove S4 acceptance, or authorize release. A synchronous admission must
cover the actual create/claim/enqueue operation (inside its worker thread).
"""

import asyncio
from contextlib import contextmanager
import fcntl
import json
import math
import os
import threading
import time
import uuid

from maintenance_state import (
    MaintenanceError, MaintenanceBlocked, MaintenanceUnavailable, MaintenanceBusy,
    _SCHEMA, _LOCKS, _root, _directory, _anchor_name, _anchor_data, _identity,
    _namespace, _read, _write, _plan,
)


_LOCAL = threading.local()


class AdmissionLease:
    """Borrowed shared lease FD; do not close it or unlock it yourself.

    A caller may explicitly dup/pass this FD to an owned startup child. Closing
    this handle on context exit does not unlock those duplicates. The caller
    must wait for their cleanup; descendants must not accidentally inherit them.
    """

    def __init__(self, fd):
        self._fd = fd

    @property
    def fd(self):
        return self.fileno()

    def fileno(self):
        if self._fd is None:
            raise MaintenanceUnavailable('Admission lease is closed')
        return self._fd


def initialize(root):
    """Explicit create-once bootstrap; existing or lost state never resets.

    A private sibling bootstrap anchor is claimed/fsynced before the namespace.
    Losing the whole namespace cannot turn the same path into a new normal gate.
    Replacing its entire parent storage is outside this local identity boundary.
    """
    path = _root(root)
    parent = None
    try:
        parent_path, name = os.path.split(path)
        parent = _directory(parent_path)
        try:
            os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            return read_state(path)
        try:
            anchor_fd = os.open(_anchor_name(name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                0o600, dir_fd=parent)
        except FileExistsError:
            return read_state(path)
        try:
            os.fchmod(anchor_fd, 0o600)
            payload = json.dumps({'schema': 'stock-agent.maintenance-bootstrap.v1',
                'namespace_name': name, 'namespace_id': uuid.uuid4().hex}, separators=(',', ':')).encode()
            while payload:
                count = os.write(anchor_fd, payload)
                if not count: raise MaintenanceUnavailable('Incomplete maintenance bootstrap write')
                payload = payload[count:]
            os.fsync(anchor_fd)
        finally:
            os.close(anchor_fd)
        os.fsync(parent)
        os.mkdir(name, 0o700, dir_fd=parent)
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            os.fchmod(fd, 0o700)
            for lock in _LOCKS:
                lock_fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                try: os.fchmod(lock_fd, 0o600); os.fsync(lock_fd)
                finally: os.close(lock_fd)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(parent)
        with _namespace(path) as ns:
            anchor = _anchor_data(ns.parent, ns.name, ns.bootstrap)
            state = {'schema': _SCHEMA, 'namespace_id': anchor['namespace_id'],
                'namespace': _identity(os.fstat(ns.directory)),
                'bootstrap': _identity(os.fstat(ns.bootstrap)),
                'locks': {name: _identity(os.fstat(fd)) for name, fd in ns.locks.items()},
                'generation': 0, 'phase': 'normal', 'plan': None}
            _write(ns, state)
            return _read(ns)[0]
    except OSError as error:
        raise MaintenanceUnavailable('Cannot initialize maintenance namespace') from error
    finally:
        if parent is not None: os.close(parent)


def read_state(root=None):
    """Return a validated fresh copy; never initialize or reset missing state."""
    with _namespace(root) as ns:
        return _read(ns)[0]


def _owner():
    try: task = asyncio.current_task()
    except RuntimeError: task = None
    return os.getpid(), threading.get_ident(), task


@contextmanager
def admission(root=None):
    """Hold SH across a synchronous operation, reentrant only for its owner."""
    path, owner = _root(root), _owner()
    held = getattr(_LOCAL, 'held', None)
    if held is None: held = _LOCAL.held = {}
    key = (path, owner)
    if key in held:
        ns, lease = held[key]
        try: ns.verify()
        except OSError as error: raise MaintenanceUnavailable('Admission namespace drift') from error
        yield lease
        return
    with _namespace(path) as ns:
        fd = ns.locks['admission.lock']
        fcntl.flock(fd, fcntl.LOCK_SH)
        state = _read(ns)[0]
        if state['phase'] != 'normal':
            raise MaintenanceBlocked('Maintenance phase: ' + state['phase'])
        lease = AdmissionLease(fd)
        held[key] = (ns, lease)
        try:
            yield lease
        finally:
            held.pop(key, None)
            lease._fd = None
            # Close-only in _namespace: dup/pass_fds must keep the SH lease.


def arm(root, plan):
    """Durably block new admissions without waiting for existing SH holders."""
    registered = _plan(plan)
    try:
        with _namespace(root) as ns:
            try:
                fcntl.flock(ns.locks['control.lock'], fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise MaintenanceBusy('Maintenance controller is busy') from error
            state, previous = _read(ns)
            if state['phase'] != 'normal':
                if state['plan'] != registered:
                    raise MaintenanceBlocked('Maintenance plan is already fixed')
                return state
            state.update(phase='arming', plan=registered, generation=1)
            # No admission EX lock here: publish intent before waiting to drain.
            _write(ns, state, previous)
            return _read(ns)[0]
    except OSError as error:
        raise MaintenanceUnavailable('Cannot persist maintenance intent') from error


def wait_drained(root, timeout_seconds):
    """Wait for cooperative leases only; never assert legacy/S4 protection.

    Timeout includes controller contention and keeps the existing arming state.
    It never force-unlocks another process, clears the plan, or releases service.
    """
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or timeout_seconds < 0):
        raise MaintenanceUnavailable('Finite nonnegative drain timeout required')
    deadline = time.monotonic() + timeout_seconds
    try:
        with _namespace(root) as ns:
            for name in ('control.lock', 'admission.lock'):
                while True:
                    ns.verify()
                    try:
                        fcntl.flock(ns.locks[name], fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0: return False
                        time.sleep(min(remaining, 0.01))
                if name == 'control.lock':
                    state, previous = _read(ns)
                    if state['phase'] == 'normal':
                        raise MaintenanceBlocked('Maintenance must be armed before drain')
                    if state['phase'] == 'cooperatively_drained': return True
            # All SH leases have ended; controller remains exclusive until fsync.
            state.update(phase='cooperatively_drained', generation=2)
            _write(ns, state, previous)
            _read(ns)
            return True
    except OSError as error:
        raise MaintenanceUnavailable('Cannot verify cooperative drain') from error
