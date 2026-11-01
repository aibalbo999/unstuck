"""Explicit parent helper for ONE already-reserved private campaign job.

Imports are inert. The caller owns authorization, the fixed ledger/manifest,
frozen inputs, reviewed argv/env and transport/socket guards. This is not an
OS sandbox, live launcher or billing verifier. Commands must not daemonize,
change session/process group, or escape the guardian. Parent SIGKILL/host loss
cannot be cleaned up here. A retained start claim prevents relaunch; after
storage/host failure the caller must audit ledger and processes, never reset.

No ambient environment/stdin or stdout/stderr is inherited or captured. The
caller must separately guard any raw artifacts written by its command. Return
codes and cleanup receipts do not certify report quality. No ledger finish,
refund, settlement or pass_stage is performed, including on cancellation.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import select
import signal
import stat
import subprocess
import sys
import threading
import time


class WatchdogError(RuntimeError):
    pass


class CleanupUnconfirmed(WatchdogError):
    """No cleanup evidence may be issued; leave the ledger reservation held."""


def _positive(value, maximum):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
        raise WatchdogError('invalid bounded watchdog interval')
    return float(value)


def _private_directory(value):
    path = Path(value)
    if not path.is_absolute() or path.resolve() != path:
        raise WatchdogError('explicit nonsymlink private output required')
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.geteuid():
        raise WatchdogError('output must be an owned 0700 directory')
    return path


def _private_json(path, payload):
    encoded = (json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return hashlib.sha256(encoded).hexdigest()


class _OwnedGroup:
    def __init__(self, term_grace, kill_grace):
        self.process, self.pgid = None, None
        self.term_grace, self.kill_grace = term_grace, kill_grace
        self.lock, self.finished = threading.Lock(), threading.Event()
        self.reason, self.error, self.proof = None, None, None
        self.phase = 'created'
        self.signal_denials = []

    def stop(self, reason):
        with self.lock:
            if self.finished.is_set():
                return
            self.reason = reason
            try:
                # Only this start_new_session child owns pgid. Never poll/reap
                # its guardian before the last signal, preventing PID reuse.
                if self.pgid <= 1 or self.pgid == os.getpgrp():
                    raise CleanupUnconfirmed('unsafe owned process group')
                for sig, delay in ((signal.SIGTERM, self.term_grace), (signal.SIGKILL, 0)):
                    self.phase = 'signal_' + str(int(sig))
                    try:
                        os.killpg(self.pgid, sig)
                    except ProcessLookupError:
                        pass
                    except PermissionError:
                        # macOS can return EPERM for a just-terminated group.
                        # This is not proof of cleanup: still attempt escalation,
                        # reap only our guardian and require group disappearance.
                        self.signal_denials.append(int(sig))
                    if delay:
                        time.sleep(delay)
                self.phase = 'reap_guardian'
                self.process.wait(timeout=self.kill_grace)
                deadline = time.monotonic() + self.kill_grace
                while True:
                    try:
                        self.phase = 'confirm_group_absent'
                        os.killpg(self.pgid, 0)
                    except ProcessLookupError:
                        break
                    if time.monotonic() >= deadline:
                        raise CleanupUnconfirmed('owned process group disappearance unconfirmed')
                    time.sleep(0.01)
                self.proof = {'pgid': self.pgid, 'guardian_reaped': True,
                              'process_group_absent': True, 'stop_reason': reason,
                              'signal_permission_denials': list(self.signal_denials)}
            except BaseException as error:
                self.error = error
            finally:
                self.finished.set()


def _guardian(fd, argv):
    """Keep the session leader unreaped while parent cleans all descendants."""
    signal.signal(signal.SIGTERM, lambda *_: None)
    signal.signal(signal.SIGINT, lambda *_: None)
    try:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, close_fds=True)
        payload = {'returncode': child.wait()}
    except BaseException:
        payload = {'start_failed': True}
    os.write(fd, (json.dumps(payload) + '\n').encode())
    os.close(fd)
    while True:
        signal.pause()


def run_reserved_process(ledger, job_id, argv, *, env, output_dir, cancel_check=None,
                         poll_seconds=0.05, term_grace=0.3, kill_grace=1.0):
    """Run once; return safe cleanup evidence or raise after verified cleanup.

    ``cancel_check`` is a nonblocking parent callback: true requests stop;
    raised BaseException is re-raised after cleanup. ledger.check may block, so
    an independent monotonic timer terminates the group at the frozen deadline.
    CleanupUnconfirmed never produces a successful cleanup artifact.
    """
    from quality_campaign_budget import BudgetDenied
    if os.name != 'posix' or not hasattr(os, 'killpg'):
        raise WatchdogError('POSIX owned process groups required')
    if not isinstance(job_id, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', job_id):
        raise WatchdogError('invalid reserved job identifier')
    if (type(argv) not in (list, tuple) or not argv or any(type(item) is not str or '\0' in item for item in argv)
            or not Path(argv[0]).is_absolute()):
        raise WatchdogError('explicit absolute executable and argv required; no shell')
    if type(env) is not dict or any(type(key) is not str or type(value) is not str or not key
            or '=' in key or '\0' in key + value for key, value in env.items()):
        raise WatchdogError('explicit minimal string environment required')
    if cancel_check is not None and not callable(cancel_check):
        raise WatchdogError('invalid cancellation callback')
    poll_seconds = _positive(poll_seconds, 1)
    term_grace, kill_grace = _positive(term_grace, 5), _positive(kill_grace, 5)
    output = _private_directory(output_dir)
    ledger.check()
    state = ledger.snapshot()
    job = state['jobs'].get(job_id)
    if not isinstance(job, dict) or job.get('status') != 'active':
        raise WatchdogError('an active reserved job is required')
    deadline_ms = job.get('deadline_ms')
    wall, mono = ledger.clock(), time.monotonic()
    if (type(deadline_ms) is not int or type(wall) not in (int, float)
            or not math.isfinite(wall) or deadline_ms <= wall * 1000):
        raise WatchdogError('reserved job deadline has elapsed or is invalid')
    hard_deadline = mono + (deadline_ms / 1000 - wall)
    prefix = output / ('watchdog-' + job_id)
    ledger_directory = _private_directory(ledger.path.parent)
    claim = ledger_directory / (ledger.path.name + '.' + job_id + '.watchdog-started.json')
    _private_json(claim, {
        'job_id': job_id, 'ledger_binding_sha256': ledger.binding,
        'deadline_ms': deadline_ms, 'actual_hashes': job.get('actual_hashes')})
    # Start claims are exclusive and never removed, even when spawn fails.
    # Allocate cleanup state before any child exists; constructor failure cannot
    # strand a Popen handle between process creation and owner assignment.
    owner = _OwnedGroup(term_grace, kill_grace)
    process = timer = None
    exception, returncode, reason = None, None, 'parent_exception'
    cancel_timer = threading.Event()
    requested_reason = ['parent_exception']
    reader, writer = os.pipe()
    try:
        # Claim fsync may outlast a concurrent durable denial/job completion.
        # Revalidate the same active reservation immediately before Popen.
        ledger.check()
        latest = ledger.snapshot()
        if latest['blocked'] or latest['jobs'].get(job_id) != job:
            raise WatchdogError('reserved job admission changed before spawn')
        if time.monotonic() >= hard_deadline:
            raise WatchdogError('deadline elapsed before spawn')
        process = subprocess.Popen([sys.executable, '-I', '-B', str(Path(__file__).resolve()),
            '--owned-child', str(writer), *argv], cwd=output, env=dict(env),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True, pass_fds=(writer,), start_new_session=True)
        owner.process, owner.pgid = process, process.pid
        os.close(writer)
        writer = None
        def expire():
            requested = cancel_timer.wait(max(0, hard_deadline - time.monotonic()))
            owner.stop(requested_reason[0] if requested else 'monotonic_deadline')
        timer = threading.Thread(target=expire, name='campaign-owned-deadline', daemon=True)
        timer.start()
        received = b''
        while not owner.finished.is_set():
            if cancel_check is not None and cancel_check():
                reason = 'cancelled'
                break
            try:
                ledger.check()
            except BudgetDenied:
                reason = 'ledger_denied'
                break
            if select.select([reader], [], [], poll_seconds)[0]:
                chunk = os.read(reader, 1024)
                received += chunk
                if not chunk or b'\n' in received:
                    try:
                        message = json.loads(received)
                        returncode = message.get('returncode')
                        if type(returncode) is not int:
                            raise ValueError('missing command status')
                    except (ValueError, TypeError, AttributeError):
                        reason = 'child_start_failed'
                    else:
                        reason = 'exited'
                    break
                if len(received) > 1024:
                    raise WatchdogError('invalid guardian status')
    except BaseException as error:
        exception = error
    finally:
        if process is not None:
            owner.process, owner.pgid = process, process.pid
            requested_reason[0] = reason
            cancel_timer.set()
            if timer is None or timer.ident is None:
                owner.stop(reason)
            else:
                cleanup_deadline = time.monotonic() + term_grace + 2 * kill_grace + 1
                while timer.is_alive() and time.monotonic() < cleanup_deadline:
                    try:
                        timer.join(timeout=0.05)
                    except BaseException as error:
                        exception = exception or error
        os.close(reader)
        if writer is not None:
            os.close(writer)
    if process is None:
        raise WatchdogError('child not started; reservation and start claim retained') from None
    if owner.error is not None or not owner.proof or (timer is not None and timer.is_alive()):
        kind = type(owner.error).__name__ if owner.error is not None else 'deadline_thread_unconfirmed'
        raise CleanupUnconfirmed('owned cleanup unconfirmed; no cleanup receipt: ' + owner.phase + ':' + kind) from None
    cleanup = {'version': 1, 'job_id': job_id, 'ledger_binding_sha256': ledger.binding,
               'deadline_ms': deadline_ms, 'command_returncode': returncode, **owner.proof}
    path = Path(str(prefix) + '.cleanup.json')
    digest = _private_json(path, cleanup)
    if exception is not None:
        raise exception
    return {'status': 'exited' if owner.reason == 'exited' else 'stopped', 'returncode': returncode,
            'cleanup_verified': True, 'cleanup': cleanup, 'cleanup_path': str(path),
            'cleanup_evidence_sha256': digest}


if __name__ == '__main__':
    if len(sys.argv) < 4 or sys.argv[1] != '--owned-child':
        raise SystemExit(2)
    _guardian(int(sys.argv[2]), sys.argv[3:])
