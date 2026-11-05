"""Create-once process attempts for the maintenance controller, not release.

Only this object's Popen child can receive one SIGTERM. No PID adoption, process
discovery, escalation, implicit cleanup, backend import, or .env loading. A new
controller cannot resume a recorded attempt or assume an orphan is stopped.
The caller owns authorization, exact code/environment qualification, descendant
and application cleanup, legacy settlement, and the overall handover sequence.
"""
import fcntl
from contextlib import contextmanager
import hashlib
import json
import math
import os
import signal
import stat
import subprocess
import sys
import threading
import time

from maintenance_state import MaintenanceError, _directory, _identifier, _identity, _private, _root


LIMIT = 32768
JOURNAL = 'process-attempt.jsonl'
SCHEMA = 'stock-agent.owned-process-attempt.v1'
MAX_READONLY_FDS = 8


class ProcessUnavailable(RuntimeError):
    """Attempt state is unavailable; never automatically retry or release."""


class ProcessBusy(ProcessUnavailable):
    """No operation began. Only this contention may be observed again."""


def _raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def _sha(value):
    return hashlib.sha256(_raw(value)).hexdigest()


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ProcessUnavailable('Duplicate attempt field')
        value[key] = item
    return value


def _binding(value):
    if (type(value) is not dict or set(value) != {'operation_id', 'control_sha256', 'backend_revision'}
            or not _identifier(value['operation_id'])):
        raise ProcessUnavailable('Exact operation binding required')
    for key, count in (('control_sha256', 64), ('backend_revision', 40)):
        text = value[key]
        if type(text) is not str or len(text) != count or any(c not in '0123456789abcdef' for c in text):
            raise ProcessUnavailable('Explicit revision hashes required')
    return dict(value)


def admission_pipe_identity(fd):
    """Only a caller-owned read end may be inherited; never a file/socket."""
    if type(fd) is not int or not 3 <= fd < 1048576:
        raise ProcessUnavailable('Explicit admission pipe required')
    info = os.fstat(fd)
    # macOS anonymous pipes are kernel 0660/dev=0/nlink=0 objects and reject
    # fchmod. This exception must never authorize a named 0660 FIFO or file.
    private_mode = stat.S_IMODE(info.st_mode) == 0o600 or (sys.platform == 'darwin'
        and stat.S_IMODE(info.st_mode) == 0o660 and info.st_dev == 0 and info.st_nlink == 0)
    if (not stat.S_ISFIFO(info.st_mode) or info.st_uid != os.geteuid()
            or not private_mode
            or fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY):
        raise ProcessUnavailable('Private read-only admission pipe required')
    return _identity(info)


def readonly_descriptor_identity(fd):
    """Bound a private read-only claim or lifetime pipe, never writable state.

    The caller still validates the claim's job/budget binding and retains its
    guardian until cleanup. This descriptor check grants no business authority.
    """
    if type(fd) is not int or not 3 <= fd < 1048576:
        raise ProcessUnavailable('Explicit read-only descriptor required')
    info = os.fstat(fd)
    if fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY:
        raise ProcessUnavailable('Writable capacity descriptors cannot reach the child')
    if stat.S_ISFIFO(info.st_mode):
        identity, kind = admission_pipe_identity(fd), 'pipe'
    elif (stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
            and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
            and info.st_size == 0):
        identity, kind = _identity(info), 'regular'
    else:
        raise ProcessUnavailable('Private empty claim file or read-only lifetime pipe required')
    return {'fd': fd, 'kind': kind, **identity}


def _readonly_rows(rows):
    if type(rows) is not list or not 1 <= len(rows) <= MAX_READONLY_FDS:
        raise ProcessUnavailable('Bounded read-only descriptor identities required')
    descriptors, identities = set(), set()
    for row in rows:
        if (type(row) is not dict or set(row) != {'fd', 'kind', 'device', 'inode'}
                or type(row['fd']) is not int or not 3 <= row['fd'] < 1048576
                or row['kind'] not in ('regular', 'pipe')
                or any(type(row[key]) is not int or row[key] < 0 for key in ('device', 'inode'))):
            raise ProcessUnavailable('Invalid read-only descriptor identity')
        identity = (row['kind'], row['device'], row['inode'])
        if row['fd'] in descriptors or identity in identities:
            raise ProcessUnavailable('Duplicate read-only descriptor identity')
        descriptors.add(row['fd']); identities.add(identity)
    return rows


def _explicit_root(value):
    if value is None:
        raise ProcessUnavailable('Explicit process path required; no environment fallback')
    try:
        return _root(value)
    except (MaintenanceError, TypeError, ValueError):
        raise ProcessUnavailable('Explicit nonsymlink process path required') from None


def _read(fd):
    info = os.fstat(fd)
    _private(info)
    os.lseek(fd, 0, os.SEEK_SET)
    raw = os.read(fd, LIMIT + 1)
    if not raw or len(raw) > LIMIT or len(raw) != info.st_size or not raw.endswith(b'\n'):
        raise ProcessUnavailable('Incomplete attempt journal')
    return raw


def _decode(raw, namespace):
    previous, phase, pid, stopped, returned, code = '0' * 64, None, None, False, False, None
    binding = owner_pid = admission_pipe = started_sha = None
    readonly_descriptors = []
    owned_session = group_absent = False
    prefix = b''
    for index, line in enumerate(raw.splitlines()):
        row = json.loads(line, object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ProcessUnavailable('Nonfinite attempt value')))
        if (type(row) is not dict or set(row) != {'schema', 'sequence', 'previous_sha256', 'event', 'data'}
                or row['schema'] != SCHEMA or type(row['sequence']) is not int or row['sequence'] != index
                or row['previous_sha256'] != previous or type(row['data']) is not dict):
            raise ProcessUnavailable('Invalid attempt chain')
        event, data = row['event'], row['data']
        prefix += line + b'\n'
        if index == 0:
            if event != 'reserved' or set(data) != {'binding', 'namespace', 'owner_pid'} or data['namespace'] != namespace:
                raise ProcessUnavailable('Attempt namespace mismatch')
            binding = _binding(data['binding'])
            if type(data['owner_pid']) is not int or data['owner_pid'] <= 0:
                raise ProcessUnavailable('Invalid attempt owner')
            owner_pid = data['owner_pid']
            phase = 'reserved'
        elif event == 'launch_intent' and phase == 'reserved':
            fields = {'command_sha256', 'environment_sha256', 'cwd_identity'}
            if not fields <= set(data) <= fields | {'admission_pipe_identity', 'owned_session', 'readonly_descriptor_identities'}:
                raise ProcessUnavailable('Invalid launch intent')
            if 'owned_session' in data and data['owned_session'] is not True:
                raise ProcessUnavailable('Invalid owned session intent')
            owned_session = data.get('owned_session', False)
            admission_pipe = data.get('admission_pipe_identity')
            if admission_pipe is not None and (type(admission_pipe) is not dict
                    or set(admission_pipe) != {'device', 'inode'}
                    or any(type(value) is not int or value < 0 for value in admission_pipe.values())):
                raise ProcessUnavailable('Invalid admission pipe identity')
            if 'readonly_descriptor_identities' in data:
                readonly_descriptors = _readonly_rows(data['readonly_descriptor_identities'])
                if admission_pipe is not None and any(row['kind'] == 'pipe'
                        and {key: row[key] for key in ('device', 'inode')} == admission_pipe
                        for row in readonly_descriptors):
                    raise ProcessUnavailable('Admission and capacity pipe must be distinct')
            phase = 'launch_unconfirmed'
        elif event == 'started' and phase == 'launch_unconfirmed':
            pid = data.get('pid')
            if set(data) != {'pid'} or type(pid) is not int or pid <= 0:
                raise ProcessUnavailable('Invalid owned process identity')
            phase = 'running'
            started_sha = hashlib.sha256(prefix).hexdigest()
        elif event == 'stop_intent' and phase == 'running' and data == {'signal': 'SIGTERM'}:
            stopped, phase = True, 'stop_unconfirmed'
        elif event == 'signal_returned' and phase == 'stop_unconfirmed' and not returned and data == {}:
            returned = True
        elif event == 'exited' and phase in ('running', 'stop_unconfirmed'):
            code = data.get('returncode')
            if set(data) != {'returncode'} or type(code) is not int:
                raise ProcessUnavailable('Invalid exit observation')
            phase = 'exited'
        elif (event == 'group_absent' and phase == 'exited' and owned_session and not group_absent
                and set(data) == {'pgid'} and type(data['pgid']) is int and data['pgid'] == pid):
            group_absent = True
        else:
            raise ProcessUnavailable('Invalid attempt transition')
        previous = hashlib.sha256(line).hexdigest()
    if phase is None:
        raise ProcessUnavailable('Empty attempt journal')
    return {'schema_version': SCHEMA, 'binding': binding, 'phase': phase, 'pid': pid,
        'owner_pid': owner_pid, 'admission_pipe_identity': admission_pipe, 'started_journal_sha256': started_sha,
        'readonly_descriptor_identities': readonly_descriptors,
        'owned_session': owned_session, 'process_group_id': pid if owned_session else None,
        'process_group_absence_verified': group_absent,
        'stop_requested': stopped, 'signal_call_returned': returned,
        'process_exited': phase == 'exited', 'returncode': code,
        'journal_sha256': hashlib.sha256(raw).hexdigest(), 'recorded_events': index + 1,
        'process_liveness_verified': False, 'cleanup_verified': False,
        'descendant_settlement_verified': False, 'handover_verified': False,
        'resume_authorized': False}


def read_process_record(namespace):
    """Read recorded observations only; a journal is not a live process handle."""
    directory = fd = None
    try:
        directory = _directory(_explicit_root(namespace))
        _private(os.fstat(directory), directory=True)
        fd = os.open(JOURNAL, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        return _decode(_read(fd), _identity(os.fstat(directory)))
    except (MaintenanceError, OSError, ValueError, TypeError) as error:
        raise ProcessUnavailable('Process attempt readback unavailable') from error
    finally:
        if fd is not None: os.close(fd)
        if directory is not None: os.close(directory)


class OwnedProcess:
    """Controller-owned child with a durable, non-reusable attempt journal.

    The existing exact 0700 namespace is dedicated to this one operation. Close
    only closes controller FDs: it neither terminates nor claims cleanup. The
    caller must retain this object/handle through verified exit. A crash retains
    the attempt and blocks relaunch, even when no PID was durably recorded.
    """

    def __init__(self, namespace, binding):
        self.binding = _binding(binding)
        self.namespace = _explicit_root(namespace)
        self.owner_pid = os.getpid()
        self._process = None
        self._directory = self._fd = None
        self._bytes = b''
        self._lock = threading.Lock()
        self._launch_attempted = self._stop_attempted = self._exit_recorded = False
        self._supervisor = None
        try:
            self._directory = _directory(self.namespace)
            _private(os.fstat(self._directory), directory=True)
            self._namespace_identity = _identity(os.fstat(self._directory))
            self._fd = os.open(JOURNAL, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                               0o600, dir_fd=self._directory)
            os.fchmod(self._fd, 0o600)
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._file_identity = _identity(os.fstat(self._fd))
            self._append('reserved', {'binding': self.binding, 'namespace': self._namespace_identity,
                                     'owner_pid': self.owner_pid})
            os.fsync(self._directory)  # Attempt name durable before any Popen.
        except BaseException as error:
            self.close()
            if isinstance(error, (MaintenanceError, OSError, ValueError, TypeError)):
                raise ProcessUnavailable('A fresh private process attempt is required') from None
            raise

    @property
    def process(self):
        return self._process

    @contextmanager
    def _operation(self):
        # Nonblocking and non-reentrant, including same-thread Python signal
        # handlers. A check-then-set bool under RLock can send a second TERM.
        if not self._lock.acquire(blocking=False):
            raise ProcessBusy('Process operation already in progress')
        try:
            yield
        except (MaintenanceError, OSError, ValueError, TypeError):
            raise ProcessUnavailable('Owned process operation unavailable; do not retry') from None
        finally:
            self._lock.release()

    def _verify(self):
        if os.getpid() != self.owner_pid or self._fd is None or self._directory is None:
            raise ProcessUnavailable('Original live controller required')
        current = _directory(self.namespace)
        try:
            _private(os.fstat(current), directory=True)
            if _identity(os.fstat(current)) != self._namespace_identity:
                raise ProcessUnavailable('Process namespace identity changed')
        finally:
            os.close(current)
        info = os.stat(JOURNAL, dir_fd=self._directory, follow_symlinks=False)
        _private(info)
        if _identity(info) != self._file_identity or info.st_size != len(self._bytes):
            raise ProcessUnavailable('Process journal identity changed')
        os.lseek(self._fd, 0, os.SEEK_SET)
        if os.read(self._fd, LIMIT + 1) != self._bytes:
            raise ProcessUnavailable('Process journal content changed')

    def _append(self, event, data):
        self._verify()
        lines = self._bytes.splitlines()
        row = {'schema': SCHEMA, 'sequence': len(lines), 'event': event, 'data': data,
               'previous_sha256': hashlib.sha256(lines[-1]).hexdigest() if lines else '0' * 64}
        encoded = _raw(row) + b'\n'
        if len(self._bytes) + len(encoded) > LIMIT:
            raise ProcessUnavailable('Process journal bound exceeded')
        os.lseek(self._fd, 0, os.SEEK_END)
        view = memoryview(encoded)
        while view:
            written = os.write(self._fd, view)
            if not written: raise ProcessUnavailable('Incomplete attempt write')
            view = view[written:]
        os.fsync(self._fd)
        self._bytes += encoded
        self._verify()

    def start(self, command, *, env, cwd, admission_fd=None, owned_session=False, readonly_fds=()):
        with self._operation():
            self._verify()
            if self._launch_attempted:
                raise ProcessUnavailable('Never relaunch an attempted child')
            if (type(command) not in (list, tuple) or not command
                    or any(type(part) is not str or '\x00' in part for part in command)
                    or not command[0].startswith('/') or type(env) is not dict
                    or any(type(k) is not str or type(v) is not str or '\x00' in k + v or '=' in k for k, v in env.items())):
                raise ProcessUnavailable('Explicit command and environment required')
            command, env, cwd = tuple(command), dict(env), _explicit_root(cwd)
            if type(owned_session) is not bool or owned_session and os.name != 'posix':
                raise ProcessUnavailable('Explicit POSIX owned session required')
            pipe_identity = admission_pipe_identity(admission_fd) if admission_fd is not None else None
            if type(readonly_fds) not in (tuple, list) or len(readonly_fds) > MAX_READONLY_FDS:
                raise ProcessUnavailable('Bounded explicit read-only descriptors required')
            readonly_fds = tuple(readonly_fds)
            readonly_identities = [readonly_descriptor_identity(fd) for fd in readonly_fds]
            if readonly_identities:
                _readonly_rows(readonly_identities)
            if admission_fd in readonly_fds or pipe_identity is not None and any(
                    row['kind'] == 'pipe' and {key: row[key] for key in ('device', 'inode')} == pipe_identity
                    for row in readonly_identities):
                raise ProcessUnavailable('Admission and capacity descriptors must be distinct')
            if len(_raw([command, env])) > 1024 * 1024:
                raise ProcessUnavailable('Bounded process configuration required')
            fd = _directory(cwd)
            try: cwd_identity = _identity(os.fstat(fd))
            finally: os.close(fd)
            self._launch_attempted = True
            intent = {'command_sha256': _sha(command), 'environment_sha256': _sha(env), 'cwd_identity': cwd_identity}
            if pipe_identity is not None: intent['admission_pipe_identity'] = pipe_identity
            if readonly_identities: intent['readonly_descriptor_identities'] = readonly_identities
            if owned_session: intent['owned_session'] = True
            self._append('launch_intent', intent)
            if admission_fd is not None and admission_pipe_identity(admission_fd) != pipe_identity:
                raise ProcessUnavailable('Admission pipe identity changed before launch')
            if [readonly_descriptor_identity(fd) for fd in readonly_fds] != readonly_identities:
                raise ProcessUnavailable('Read-only descriptor identity changed before launch')
            self._process = subprocess.Popen(command, env=env, cwd=cwd, close_fds=True,
                pass_fds=(() if admission_fd is None else (admission_fd,)) + readonly_fds,
                start_new_session=owned_session,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if owned_session and (os.getpgid(self.process.pid) != self.process.pid
                    or os.getsid(self.process.pid) != self.process.pid):
                raise ProcessUnavailable('Original owned session launch unconfirmed')
            self._append('started', {'pid': self.process.pid})
            return self._snapshot()

    def snapshot(self):
        with self._operation():
            return self._snapshot()

    def _snapshot(self):
        self._verify()
        return _decode(self._bytes, self._namespace_identity)

    def _exited(self, code):
        if not self._exit_recorded:
            self._exit_recorded = True
            self._append('exited', {'returncode': code})
        return self._snapshot()

    def request_stop(self):
        with self._operation():
            self._verify()
            if self.process is None:
                raise ProcessUnavailable('No owned Popen handle; do not adopt a PID')
            code = self.process.poll()
            if code is not None:
                return self._exited(code)
            if self._stop_attempted:
                return self._snapshot()
            self._stop_attempted = True
            self._append('stop_intent', {'signal': 'SIGTERM'})
            self.process.send_signal(signal.SIGTERM)
            self._append('signal_returned', {})
            return self._snapshot()

    def wait_for_exit(self, timeout_seconds):
        if (type(timeout_seconds) not in (float, int) or not math.isfinite(timeout_seconds)
                or not 0 <= timeout_seconds <= 60):
            raise ProcessUnavailable('Finite observation interval of at most 60 seconds required')
        supervisor = self._supervisor
        if supervisor is not None and threading.current_thread() is not supervisor._thread:
            # Public original-owner callers must not hold the lifecycle lock
            # across a wait while its independent timer needs to send TERM.
            return supervisor.wait_for_exit(timeout_seconds)
        with self._operation():
            self._verify()
            if self.process is None:
                raise ProcessUnavailable('No owned handle to observe')
            try:
                code = self.process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                return self._snapshot()
            return self._exited(code)

    def close(self):
        with self._operation():
            if self._supervisor is not None and not self._supervisor.finished:
                raise ProcessUnavailable('Retain original owner until supervision finishes')
            for name in ('_fd', '_directory'):
                fd = getattr(self, name, None)
                if fd is not None:
                    setattr(self, name, None)
                    os.close(fd)

    def observe_process_group(self):
        """Only the original new-session owner may read kernel group absence.

        Signal 0 probes existence, never stops a process. A leader exit alone,
        EPERM/unknown state, or an inherited/ordinary group is not proof. Caller
        still qualifies code against daemon/session escape; this is not an OS
        sandbox or application/budget settlement. No descendant is signaled.
        """
        with self._operation():
            state = self._snapshot()
            if (not state['owned_session'] or self.process is None
                    or state['pid'] != self.process.pid or state['pid'] <= 1
                    or state['pid'] == os.getpgrp()):
                raise ProcessUnavailable('Original exclusive process group required')
            code = self.process.poll()
            if code is None: return state
            state = self._exited(code)
            if not state['process_group_absence_verified']:
                try:
                    os.killpg(state['pid'], 0)
                except ProcessLookupError:
                    self._append('group_absent', {'pgid': state['pid']})
                # Presence, including a lingering zombie, retains the attempt.
            return self._snapshot()


class OwnedProcessSupervisor:
    """One original-parent timer; no ledger/Redis/SDK operation on this thread.

    The absolute monotonic deadline is derived by the caller from an existing
    reservation, never from a fresh per-attempt duration. This is cooperative
    Python/OS scheduling, not a hard real-time guarantee or crash guardian.
    It only requests the owner's single TERM, then observes natural exit. A
    noncooperative child remains held indefinitely, never KILLed or requeued.
    """

    def __init__(self, owner, *, deadline_monotonic):
        if (type(owner) is not OwnedProcess or type(deadline_monotonic) not in (int, float)
                or not math.isfinite(deadline_monotonic)):
            raise ProcessUnavailable('Original owned process and finite deadline required')
        self._owner, self._pid = owner, os.getpid()
        self._deadline = deadline_monotonic
        self._lock, self._wake, self._done = threading.Lock(), threading.Event(), threading.Event()
        self._reason = self._error = None
        with owner._operation():
            state = owner._snapshot()
            if (owner._supervisor is not None or owner.process is None
                    or state['phase'] != 'running' or not state['owned_session']
                    or state['pid'] != owner.process.pid or state['owner_pid'] != self._pid):
                raise ProcessUnavailable('Fresh original exclusive process supervision required')
            owner._supervisor = self  # A failed thread launch retains this attempt.
        self._thread = threading.Thread(target=self._run, name='owned-process-deadline', daemon=True)
        try:
            self._thread.start()
        except BaseException:
            self._error = 'supervisor_start_failed'
            self._done.set()
            raise

    @property
    def finished(self):
        return self._done.is_set()

    def _original(self):
        if os.getpid() != self._pid or self._owner._supervisor is not self:
            raise ProcessUnavailable('Original process supervisor required')

    def request_stop(self):
        self._original()
        with self._lock:
            if not self._done.is_set() and self._reason is None:
                self._reason = 'deadline' if time.monotonic() >= self._deadline else 'cancelled'
            self._wake.set()
        return self.snapshot()

    def snapshot(self):
        self._original()
        # The timer's cached observations cannot authorize admission/settlement.
        # Decode the original verified journal each time: callers receive fresh
        # nested objects and post-exit file drift remains fail-closed. Retry only
        # bounded pre-operation lock contention, never uncertain I/O or signals.
        until = time.monotonic() + .05
        while True:
            try:
                state = self._owner.snapshot()
                break
            except ProcessBusy:
                if time.monotonic() >= until: raise
                time.sleep(.001)
        with self._lock:
            if self._error is not None:
                raise ProcessUnavailable('Original process supervision unconfirmed: ' + self._error)
            return {**state, 'deadline_monotonic': self._deadline, 'stop_reason': self._reason,
                    'supervision_complete': self._done.is_set() and state['process_exited']}

    def wait_for_exit(self, seconds):
        self._original()
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 <= seconds <= 60:
            raise ProcessUnavailable('Finite observation interval of at most 60 seconds required')
        self._done.wait(seconds)  # Never holds the process lock or delays TERM.
        if self._done.is_set(): self._thread.join()
        return self.snapshot()

    def _run(self):
        stop_observed = False
        try:
            while True:
                self._original()
                with self._lock:
                    if self._reason is None and time.monotonic() >= self._deadline:
                        self._reason = 'deadline'
                    stopping = self._reason is not None
                    self._wake.clear()
                try:
                    if stopping and not stop_observed:
                        self._owner.request_stop()
                        stop_observed = True
                    state = self._owner.wait_for_exit(0)
                    if state['process_exited']:
                        state = self._owner.observe_process_group()
                    with self._lock:
                        if state['process_exited']:
                            # Late cancellation remains visible, never a success
                            # merely because the process has already exited.
                            self._done.set()
                            return
                except ProcessBusy:
                    pass  # Safe pre-operation contention only; no I/O retry.
                self._wake.wait(.01)
        except BaseException as error:
            with self._lock:
                self._error = type(error).__name__
        finally:
            self._done.set()
