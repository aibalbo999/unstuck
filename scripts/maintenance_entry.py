"""Existing launcher maintenance admission; no daemon, provider or Redis API.

The shared descriptor survives an owned startup-parent failure. Readiness only
ends startup admission; it is not proof of legacy drain, S4 or safe rollback.
Control files and backend revision are separate evidence identities.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import time
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
CONTROL_FILES = ('backend/canary_release_policy.py', 'start_mac.command', 'scripts/maintenance_entry.py',
                 'backend/maintenance_state.py', 'backend/maintenance_guard.py',
                 'scripts/maintenance_readiness.py', 'scripts/maintenance_legacy_inventory.py',
                 'scripts/maintenance_owned_process.py', 'scripts/maintenance_canary_claim.py',
                 'scripts/maintenance_canary_enrollment.py', 'scripts/maintenance_canary_settlement.py',
                 'scripts/maintenance_canary_dispatch.py', 'scripts/maintenance_control_sources.py') + tuple(
                     'backend/storage/' + name + '.py' for name in ('__init__', 'capacity', 'capacity_delegation', 'capacity_companion', 'migrations', 'report_storage', '_local_file_operations', '_report_keys', 'memory_report_storage')) + tuple(
                     'tests/quality_campaign_' + name + '.py'
                     for name in ('runner', 'budget', 'wire', 'transport', 'watchdog', 'safety', 'graph'))


class _LazyGuard:
    """Legacy library seam; the public CLI loads a bound bundle before use."""
    def __getattr__(self, attribute):
        bundle = globals().get('_CONTROL_BUNDLE')
        if bundle is not None:
            return getattr(bundle.module('maintenance_guard'), attribute)
        for name in ('maintenance_state', 'maintenance_guard'):
            if name not in sys.modules:
                path = ROOT / 'backend' / (name + '.py')
                spec = importlib.util.spec_from_file_location(name, path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                exec(compile(_control_source(path), str(path), 'exec'), module.__dict__)
        return getattr(sys.modules['maintenance_guard'], attribute)


guard = _LazyGuard()
_CONTROL_LOAD_ATTEMPTED = False


class EntryError(RuntimeError):
    pass


def control_root():
    value = os.environ.get('STOCK_AGENT_MAINTENANCE_DIR')
    if not value:
        value = str(Path(os.environ.get('CACHE_DIR') or ROOT / 'backend' / 'cache') / 'maintenance')
    path = Path(value)
    if not path.is_absolute() or path.resolve() != path:
        raise EntryError('Explicit nonsymlink maintenance directory required')
    return path


def _control_source(path):
    if path.resolve() != path:
        raise EntryError('Nonsymlink control source required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        limit = 2 * 1024 * 1024
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise EntryError('Bounded regular control source required')
        chunks, size = [], 0
        while part := os.read(fd, limit + 1 - size):
            chunks.append(part)
            size += len(part)
            if size > limit:
                raise EntryError('Control source grew beyond bound')
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_uid,
            value.st_gid, value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        if (identity(os.fstat(fd)) != identity(info) or size != info.st_size
                or identity(path.stat(follow_symlinks=False)) != identity(info)):
            raise EntryError('Control source changed during capture')
        return b''.join(chunks)
    finally:
        os.close(fd)


def _control_sources():
    return {name: _control_source(ROOT / name) for name in CONTROL_FILES}


def _sources_digest(sources):
    values = {name: hashlib.sha256(source).hexdigest() for name, source in sources.items()}
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def control_digest():
    return _sources_digest(_control_sources())


def load_control_bundle(expected_sha256):
    """One fresh-controller attempt, validating bytes before executing them."""
    global _CONTROL_LOAD_ATTEMPTED
    if _CONTROL_LOAD_ATTEMPTED:
        raise EntryError('Never reload or resume a control bundle attempt')
    _CONTROL_LOAD_ATTEMPTED = True
    sources = _control_sources()
    if type(expected_sha256) is not str or _sources_digest(sources) != expected_sha256:
        raise EntryError('Approved control digest mismatch before load')
    relative = 'scripts/maintenance_control_sources.py'
    loader = ModuleType('maintenance_control_sources_bound')
    loader.__file__ = str(ROOT / relative)
    exec(compile(sources[relative], loader.__file__, 'exec'), loader.__dict__)
    return loader.load_controls(ROOT, sources, expected_sha256, sys.modules.get(__name__))


def _read_plan(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value: raise EntryError('Duplicate plan JSON key')
            value[key] = item
        return value
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path:
        raise EntryError('Explicit nonsymlink plan required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 32768:
            raise EntryError('Bounded regular maintenance plan required')
        raw = os.read(fd, 32769)
        if len(raw) > 32768: raise EntryError('Maintenance plan exceeded limit')
    finally:
        os.close(fd)
    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict) or value.get('control_sha256') != control_digest():
        raise EntryError('Maintenance plan does not bind this control implementation')
    return value


def _legacy_inventory(manifest):
    bundle = globals().get('_CONTROL_BUNDLE')
    if bundle is not None:
        if bundle.verify()['control_sha256'] != manifest['control_sha256']:
            raise EntryError('Inventory controls are not bound to the manifest')
        result = bundle.module('maintenance_legacy_inventory').read_legacy_inventory(manifest)
        bundle.verify()
        return result
    # Compile the bound source bytes, not an arbitrary/stale sys.modules entry
    # or timestamp-based pyc for the legacy library seam only. The public CLI
    # above keeps the same bundle. Temporary names are restored on failure.
    sources = _control_sources()
    if manifest['control_sha256'] != _sources_digest(sources):
        raise EntryError('Inventory source buffers are not bound to the manifest')
    names = ('maintenance_readiness', 'maintenance_legacy_inventory')
    previous = {name: sys.modules.get(name) for name in names}
    try:
        for name in names:
            path = ROOT / 'scripts' / (name + '.py')
            source = sources['scripts/' + name + '.py']
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            exec(compile(source, str(path), 'exec'), module.__dict__)
            module._loaded_source_sha256 = hashlib.sha256(source).hexdigest()
        if manifest['control_sha256'] != control_digest():
            raise EntryError('Control implementation changed while loading inventory')
        for name in names:
            current = hashlib.sha256((ROOT / 'scripts' / (name + '.py')).read_bytes()).hexdigest()
            if current != sys.modules[name]._loaded_source_sha256:
                raise EntryError('Loaded inventory source mismatch')
        return sys.modules['maintenance_legacy_inventory'].read_legacy_inventory(manifest)
    finally:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def validate_owned_start(parent_pid):
    """Reject accidental/direct internal invocation before legacy side effects.

    These inherited descriptors are lifecycle capabilities, not an OS sandbox
    against a host owner deliberately forging environment or process state.
    """
    if str(parent_pid) != os.environ.get('STOCK_AGENT_STARTUP_PARENT_PID'):
        raise EntryError('Owned startup parent required')
    fds = []
    for name, kind in (('STOCK_AGENT_STARTUP_LEASE_FD', stat.S_ISREG),
                       ('STOCK_AGENT_STARTUP_READY_FD', stat.S_ISFIFO)):
        text = os.environ.get(name, '')
        if not text.isascii() or not text.isdecimal() or not 3 <= int(text) < 1048576:
            raise EntryError('Owned startup descriptors required')
        fd = int(text)
        info = os.fstat(fd)
        if not kind(info.st_mode) or info.st_uid != os.getuid():
            raise EntryError('Owned startup descriptor identity mismatch')
        fds.append(fd)
    if fds[0] == fds[1]: raise EntryError('Distinct startup descriptors required')
    state = guard.read_state(control_root())  # Valid state, not a new normal admission.
    inherited = os.fstat(fds[0])
    if ({'device': inherited.st_dev, 'inode': inherited.st_ino} != state['locks']['admission.lock']
            or stat.S_IMODE(inherited.st_mode) != 0o600 or inherited.st_size != 0 or inherited.st_nlink != 1):
        raise EntryError('Owned startup lease identity mismatch')


def run_normal_start(root, command, *, env, ready_timeout_seconds=None):
    """Hold admission until an owned startup reports ready or finishes cleanup.

    Production CLI chooses the existing shell entry, never an operator-supplied
    command. Tests use harmless owned children through this process seam.
    Descendants must close both startup descriptors before execing services.
    """
    if ready_timeout_seconds is not None and (type(ready_timeout_seconds) not in (int, float)
            or not math.isfinite(ready_timeout_seconds) or ready_timeout_seconds < 0):
        raise EntryError('Finite nonnegative readiness timeout required')
    process, read_fd, write_fd = None, None, None
    forwarded, previous, pending_signum, cleanup_attempted = False, {}, None, False
    def forward(signum, _frame):
        nonlocal forwarded, pending_signum
        if pending_signum is None:
            pending_signum = signum
        if process is not None and process.poll() is None and not forwarded:
            forwarded = True
            process.send_signal(pending_signum)  # Once, only the Popen-owned launcher.
    def stop_owned():
        nonlocal forwarded, cleanup_attempted
        if process is None or cleanup_attempted:
            return
        cleanup_attempted = True
        if process.poll() is None and not forwarded:
            forwarded = True
            process.send_signal(pending_signum or signal.SIGTERM)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            raise EntryError('Owned startup cleanup unconfirmed; retained child lease must not be reset') from None
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, forward)
        with guard.admission(root) as lease:
            try:
                read_fd, write_fd = os.pipe()
                child_env = dict(env)
                child_env.update(STOCK_AGENT_MAINTENANCE_DIR=str(root),
                    STOCK_AGENT_STARTUP_LEASE_FD=str(lease.fileno()),
                    STOCK_AGENT_STARTUP_READY_FD=str(write_fd), STOCK_AGENT_STARTUP_PARENT_PID=str(os.getpid()))
                if pending_signum is not None:
                    raise EntryError('Owned startup cancelled before launch')
                process = subprocess.Popen(command, env=child_env, pass_fds=(lease.fileno(), write_fd))
                if pending_signum is not None:
                    raise EntryError('Owned startup cancelled during launch')
                os.close(write_fd)
                write_fd = None
                # Normal interactive setup keeps its original waiting behavior.
                # Only an explicit bounded caller supplies a readiness deadline.
                deadline = None if ready_timeout_seconds is None else time.monotonic() + ready_timeout_seconds
                ready = False
                while deadline is None or time.monotonic() < deadline:
                    if pending_signum is not None:
                        raise EntryError('Owned startup cancelled before readiness')
                    pause = .1 if deadline is None else min(.1, max(0, deadline - time.monotonic()))
                    if select.select([read_fd], [], [], pause)[0]:
                        data = os.read(read_fd, 2)
                        ready = data == b'R'
                        break
                    if process.poll() is not None: break
                if pending_signum is not None:
                    raise EntryError('Owned startup cancelled before readiness')
                if not ready:
                    raise EntryError('Owned startup ended without verified readiness')
            except BaseException:
                # Keep the parent lease through verified cleanup, including
                # readiness-observer errors, not only the expected timeout path.
                stop_owned()
                raise
        return process.wait()
    except BaseException:
        stop_owned()
        raise
    finally:
        for fd in (read_fd, write_fd):
            if fd is not None: os.close(fd)
        for signum, handler in previous.items(): signal.signal(signum, handler)


def _parser():
    parser = argparse.ArgumentParser(description='Persistent maintenance controls on the existing Mac entry')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--maintenance-status', action='store_true')
    group.add_argument('--maintenance-init', action='store_true')
    group.add_argument('--maintenance-arm', metavar='ABSOLUTE_PLAN_JSON')
    group.add_argument('--maintenance-drain', action='store_true')
    group.add_argument('--maintenance-control-digest', action='store_true')
    group.add_argument('--maintenance-legacy-inventory', metavar='ABSOLUTE_MANIFEST_JSON',
                       help='Read-only legacy dispatch metadata; never authorizes handover')
    group.add_argument('--validate-owned-start', metavar='PARENT_PID', help=argparse.SUPPRESS)
    parser.add_argument('--timeout-seconds', type=float, default=30)
    return parser


def main(argv=None):
    bundle = globals().get('_CONTROL_BUNDLE')
    if bundle is not None:
        bundle.verify()
    args = _parser().parse_args(argv)
    try:
        if args.maintenance_arm:
            # No plan read or namespace transition in this engineering-only release.
            if bundle is not None:
                bundle.module('canary_release_policy').require_canary_enabled()
            else:
                path = ROOT / 'backend' / 'canary_release_policy.py'
                scope = {'__name__': '_entry_canary_release_policy'}
                exec(compile(_control_source(path), str(path), 'exec'), scope)
                scope['require_canary_enabled']()
        if args.maintenance_legacy_inventory:
            manifest = _read_plan(args.maintenance_legacy_inventory)
            result = _legacy_inventory(manifest)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
            return 0 if result['readback_complete'] else 75
        root = control_root()
        if args.validate_owned_start:
            validate_owned_start(args.validate_owned_start)
            return 0
        if args.maintenance_control_digest:
            print(json.dumps(bundle.verify() if bundle is not None else {'control_sha256': control_digest()}))
            return 0
        if args.maintenance_status:
            bootstrap = root.with_name('.' + root.name + '.bootstrap')
            exists = root.exists() or root.is_symlink() or bootstrap.exists() or bootstrap.is_symlink()
            state = guard.read_state(root) if exists else {'phase': 'uninitialized'}
        elif args.maintenance_init:
            state = guard.initialize(root)
        elif args.maintenance_arm:
            state = guard.arm(root, _read_plan(args.maintenance_arm))
        elif args.maintenance_drain:
            drained = guard.wait_drained(root, args.timeout_seconds)
            state = {'cooperative_drained': drained, 'state': guard.read_state(root), 'legacy_handover_verified': False}
        else:
            if not root.exists() and not root.is_symlink():
                root.parent.mkdir(parents=True, exist_ok=True)
                guard.initialize(root)
            return run_normal_start(root, ['/bin/bash', str(ROOT / 'start_mac.command'), '--maintenance-owned-start'], env=os.environ)
        print(json.dumps(state, ensure_ascii=False, sort_keys=True))
        return 0
    except (RuntimeError, guard.MaintenanceError, OSError, ValueError, TypeError):
        print('維護狀態或啟動收據未通過驗證；不自動重試或解除維護，請檢查原啟動程序。', file=sys.stderr)
        return 75


if __name__ == '__main__':
    try:
        args = _parser().parse_args()
        if args.maintenance_arm:
            print('此工程版本停用 canary；不讀取計畫、不啟用維護。', file=sys.stderr)
            raise SystemExit(75)
        expected = control_digest()
        plan_path = args.maintenance_legacy_inventory
        if plan_path:
            expected = _read_plan(plan_path)['control_sha256']
        bound = load_control_bundle(expected)
        code = bound.module('maintenance_entry').main()
    except (RuntimeError, OSError, ValueError, TypeError):
        print('控制程式來源或載入身分未通過驗證；不啟動、不重試或解除維護。', file=sys.stderr)
        code = 75
    raise SystemExit(code)
