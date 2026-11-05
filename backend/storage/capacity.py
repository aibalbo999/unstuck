"""Native bounded-write admission through the existing shared volume ledger.

No OS allocation, cleanup, cache reset, or network request is performed here.
Reader paths never call this module. Portable non-Mac storage stays unchanged;
this Mac's writes must remain on its configured external volume.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import asyncio
import os
import threading
from functools import wraps
import importlib
from pathlib import Path
import sys

VOLUME = Path('/Volumes/X10 Pro Mac')
SHARED = VOLUME / 'project-system-tools/work'
PROJECT = Path(__file__).resolve().parents[2]
_ACTIVE = ContextVar('stock_bounded_storage_claim', default=None)


class StorageCapacityUnavailable(RuntimeError):
    """No dependent write or provider request may begin after this refusal."""


def _shared():
    path = SHARED / 'shared_capacity.py'
    if path.is_symlink() or path.resolve() != path or not path.is_file():
        raise StorageCapacityUnavailable('Shared storage admission is unavailable')
    sys.path.insert(0, str(SHARED))
    try:
        module = importlib.import_module('shared_capacity')
    finally:
        sys.path.remove(str(SHARED))
    if (Path(module.__file__).resolve() != path or
            hashlib.sha256(path.read_bytes()).hexdigest() != module.IMPLEMENTATION_SHA256):
        raise StorageCapacityUnavailable('Shared storage admission changed; reload at a safe boundary')
    return module



def validate_write_target(target):
    """Check an actual destination before a multi-path phase changes anything."""
    target = Path(target).expanduser().absolute()
    if sys.platform != 'darwin' and not target.is_relative_to(VOLUME):
        return target
    try:
        module = _shared()
        module.volume_guard()
        return module.external(target)
    except (OSError, RuntimeError, ValueError) as error:
        raise StorageCapacityUnavailable('Storage destination is outside the admitted external volume') from error


def sqlite_write_bytes(path, payload_bytes=0):
    """Conservative journal/copy allowance, not a forecast of actual DB growth."""
    if type(payload_bytes) is not int or payload_bytes < 0:
        raise ValueError('Explicit nonnegative payload bytes required')
    path = Path(path)
    existing = sum(p.stat().st_size for p in (path, Path(str(path)+'-wal')) if p.is_file())
    # Existing pages can be journaled/copied; new payload can occupy both WAL and
    # database pages. Include schema/index/page overhead before the shared 20%.
    return existing + 2 * payload_bytes + 128 * 1024


def _owner():
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    return (os.getpid(), threading.get_ident(), task)



def _allocated_bytes(path):
    try:
        info = Path(path).stat(follow_symlinks=False)
    except FileNotFoundError:
        return 0
    return max(info.st_size, getattr(info, 'st_blocks', 0) * 512)


def _remaining(active):
    # These UUID metadata files belong exclusively to this lease. Ordinary
    # shared DB/WAL growth is never attributed to us or deducted from our claim.
    receipt = active['lease'].receipt()
    metadata = sum(_allocated_bytes(Path(directory)/(receipt['id']+'.json'))
                   for directory in receipt.get('registries', ()))
    # Shared claims only decrease. The enclosing estimate already includes
    # original-byte recovery; rollback frees space without reclaiming slots.
    return min(active['lease'].remaining, max(0, active['peak'] - max(0, active['materialized']) - metadata))


@contextmanager
def account_materialized(paths):
    """Use INSIDE the native exclusive writer lock, only for our atomic files.

    Successful allocation deltas reduce future demand; original-byte rollback
    allowance stays in the enclosing estimate. Never use shared SQLite/WAL or another writer's file growth.
    """
    from .capacity_delegation import current_readonly_capacity
    delegated = current_readonly_capacity()
    if delegated is not None:
        with delegated.account_materialized(paths):
            yield
        return
    active = _ACTIVE.get()
    if active is None or active['owner'] != _owner():
        yield
        return
    paths = tuple(dict.fromkeys(Path(path) for path in paths))
    before = sum(_allocated_bytes(path) for path in paths)
    yield
    active['materialized'] += sum(_allocated_bytes(path) for path in paths) - before


@contextmanager
def reserve_write(target, known_bytes, reason, *, allow_nested_readmission=False):
    if type(known_bytes) is not int or known_bytes < 0:
        raise ValueError('Explicit bounded write bytes required')
    from .capacity_delegation import current_readonly_capacity
    delegated = current_readonly_capacity()
    if delegated is not None:
        with delegated.reserve(target, known_bytes) as lease:
            yield lease
        return
    target = Path(target).absolute()
    if not target.is_relative_to(VOLUME):
        if sys.platform == 'darwin':
            raise StorageCapacityUnavailable('Storage write leaves the required external volume')
        yield None  # The shared Mac volume policy does not govern another host.
        return
    module = _shared()
    try:
        module.external(target)
        peak = module.estimate_peak(known_bytes + 64 * 1024)
        active = _ACTIVE.get()
        if active is not None and active['owner'] != _owner():
            active = None  # A copied ContextVar does not transfer a writer's claim.
        if active is not None and module.estimate_peak(known_bytes) > _remaining(active):
            if active['allow_nested_readmission']:
                active = None  # Keep the outer forecast claimed; count a new actual writer too.
            else:
                raise StorageCapacityUnavailable('Nested write exceeds its enclosing declared budget')
        if active is not None:
            active['lease'].check(remaining_bytes=_remaining(active))
            lease = active['lease']
        else:
            lease = module.Reservation(peak, None, reason, project_root=PROJECT)
            lease.__enter__()
    except (OSError, RuntimeError, ValueError) as error:
        if isinstance(error, StorageCapacityUnavailable):
            raise
        raise StorageCapacityUnavailable('Shared storage capacity admission refused') from error
    if active is not None:
        yield lease
        return
    token = _ACTIVE.set({'lease': lease, 'peak': peak, 'owner': _owner(),
                         'allow_nested_readmission': allow_nested_readmission, 'materialized': 0})
    try:
        yield lease
    finally:
        _ACTIVE.reset(token)
        lease.__exit__(*sys.exc_info())


@contextmanager
def reserve_report_bundle(storage, contents, previous=(), repository=None):
    from .report_storage import LocalFileStorage
    if not isinstance(storage, LocalFileStorage):
        yield None
        return
    payloads = list(contents)
    old = sum(len(item.content) + len(item.metadata.content_type.encode('utf-8')) + 160
              for item in previous if item is not None)
    known = sum(len(data) for data in payloads) + old + (len(payloads) + 2) * 8192
    from report_repository import ReportRepository
    if isinstance(repository, ReportRepository):
        from report_index import CACHE_DB_PATH
        # The native index derives bounded fields from these same source bytes.
        # Allow repeated normalized/JSON fields plus DB/WAL and schema pages
        # before any content mutation. The index also checks its actual row.
        known += sqlite_write_bytes(CACHE_DB_PATH, 8 * sum(map(len, payloads)) + 64 * 1024)
    with reserve_write(storage._root, known, 'Report bundle bytes, metadata, index DB/WAL and exact prior-byte recovery allowance') as lease:
        yield lease


def model_storage_forecast_bytes():
    """Disk-increment forecast, never an LLM response or quality size limit.

    Default: 16 MiB, rounded above four coexisting copies of the observed
    maximum native HTML/MD/snapshot/sidecar bundle (10,539,452 bytes).
    Actual serialized writers obtain their own admission after this phase.
    """
    raw = os.environ.get('STOCK_AGENT_MODEL_STORAGE_FORECAST_BYTES', str(16 * 1024 * 1024))
    if not raw.isascii() or not raw.isdecimal() or int(raw) <= 0:
        raise StorageCapacityUnavailable('Model disk forecast must be an explicit positive integer')
    return int(raw)


def reserve_model_phase(function):
    """Admission precedes key/usage/event effects; each attempt owns its claim."""
    def phase():
        from runtime_paths import current_runtime_paths
        paths = current_runtime_paths()
        forecast = model_storage_forecast_bytes()
        # Native transport may persist its optional semantic response cache before
        # returning. Admit its existing DB/WAL and new forecast payload up front.
        cache_bytes = sqlite_write_bytes(paths.json_cache_db or paths.report_index_db, forecast)
        return reserve_write(paths.output_dir, forecast + cache_bytes,
                             'Model disk forecast plus native JSON cache DB/WAL; not a response limit; actual writers re-admit',
                             allow_nested_readmission=True)
    if asyncio.iscoroutinefunction(function):
        @wraps(function)
        async def asynchronous(*args, **kwargs):
            with phase():
                return await function(*args, **kwargs)
        return asynchronous
    @wraps(function)
    def synchronous(*args, **kwargs):
        with phase():
            return function(*args, **kwargs)
    return synchronous


def write_text(path, text, *, encoding='utf-8', parents=False):
    """Admit exact encoded bytes before the caller's existing direct write."""
    target = Path(path)
    with reserve_write(target, len(text.encode(encoding)), 'Exact serialized native text artifact'):
        if parents:
            target.parent.mkdir(parents=True, exist_ok=True)
        return target.write_text(text, encoding=encoding)
