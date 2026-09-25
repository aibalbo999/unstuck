"""Shared provider observations using the existing JSON store and bounded single flight.

Acquisition time stays separate from the provider's observation date. Failures retain
last-good data only within the caller's retention window and are never fresh hits.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import threading
import time
from typing import Callable

_LOCKS = tuple(threading.RLock() for _ in range(64))
_PREFIX = 'shared_provider:v1:'


def shared_fetch(key: str, fetch: Callable, *, freshness_seconds: int,
                 retention_seconds: int | None = None, error_retry_seconds: int = 60,
                 use_cache: bool = True, result_ttl: Callable | None = None,
                 lock_wait_seconds: float | None = None) -> tuple[object, dict]:
    """Return payload and acquisition metadata, preserving errors and stale state.

    A supplied lock budget bounds both thread and process waiting together; zero
    makes both locks nonwaiting. None preserves the existing waiting behavior.
    The caller's HTTP budget remains separate from this acquisition wait budget.
    """
    if not use_cache or freshness_seconds <= 0:
        return _uncached(fetch)
    from cache_store import get_cache_json, set_cache_json
    digest = hashlib.sha256(key.encode()).hexdigest()
    cache_key = _PREFIX + digest
    retention = max(freshness_seconds, retention_seconds or freshness_seconds)
    with _shared_lock(digest, lock_wait_seconds) as acquired:
        if not acquired:
            return None, {"cache_hit": False, "stale": False, "error_kind": "single_flight_busy", "fetched_at_epoch": None}
        now = time.time()
        try:
            row = get_cache_json(cache_key)
        except Exception:
            row = None
        row = row if isinstance(row, dict) else {}
        fetched_at = row.get('fetched_at_epoch')
        value = row.get('value')
        if value is not None and now < float(row.get('fresh_until_epoch') or 0):
            return deepcopy(value), {'cache_hit': True, 'stale': False, 'fetched_at_epoch': fetched_at}
        if now < float(row.get('retry_after_epoch') or 0):
            stale = value is not None and now < float(row.get('retained_until_epoch') or 0)
            return deepcopy(value) if stale else None, {
                'cache_hit': stale, 'stale': stale, 'fetched_at_epoch': fetched_at,
                'error_kind': row.get('error_kind'), 'cooldown': True,
                'retry_after_epoch': row['retry_after_epoch'],
            }
        value_new, meta = _uncached(fetch)
        now = time.time()
        if 'error_kind' not in meta:
            fresh_ttl = max(1, min(freshness_seconds, int(result_ttl(value_new)))) if result_ttl else freshness_seconds
            row = {'value': value_new, 'fetched_at_epoch': meta['fetched_at_epoch'],
                   'fresh_until_epoch': now + fresh_ttl,
                   'retained_until_epoch': now + retention}
            ttl = retention
        else:
            retained = row.get('value') is not None and now < float(row.get('retained_until_epoch') or 0)
            if not retained:
                row = {}
            row.update(error_kind=meta['error_kind'], retry_after_epoch=now + error_retry_seconds)
            ttl = max(error_retry_seconds, int(float(row.get('retained_until_epoch') or now) - now))
            meta.update(cache_hit=retained, stale=retained,
                        fetched_at_epoch=row.get('fetched_at_epoch'), retry_after_epoch=row['retry_after_epoch'])
            value_new = deepcopy(row.get('value')) if retained else None
        try:
            set_cache_json(cache_key, row, ttl_seconds=max(1, int(ttl)))
        except Exception:
            pass  # Cache availability must not discard a completed provider result.
        return value_new, meta


@contextmanager
def _shared_lock(digest: str, lock_wait_seconds: float | None):
    local = _LOCKS[int(digest[:8], 16) % len(_LOCKS)]
    if lock_wait_seconds is None:
        with local, _process_lock(digest) as acquired:
            yield acquired
        return
    seconds = float(lock_wait_seconds)
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError('lock_wait_seconds must be finite and nonnegative')
    deadline = time.monotonic() + seconds
    acquired = local.acquire(timeout=min(max(0, deadline - time.monotonic()), threading.TIMEOUT_MAX))
    if not acquired:
        yield False
        return
    try:
        remaining = max(0, deadline - time.monotonic())
        if seconds > 0 and remaining == 0:
            yield False
            return
        with _process_lock(digest, blocking_timeout=remaining) as process_acquired:
            yield bool(process_acquired and (seconds == 0 or time.monotonic() <= deadline))
    finally:
        local.release()


def _uncached(fetch: Callable) -> tuple[object, dict]:
    try:
        value = fetch()
        if value is None:
            raise ValueError('Provider did not return an observation')
        return value, {'cache_hit': False, 'stale': False, 'fetched_at_epoch': time.time()}
    except Exception as exc:
        # Exception text can contain signed URLs or credentials; persist only type.
        return None, {'cache_hit': False, 'stale': False, 'error_kind': type(exc).__name__, 'fetched_at_epoch': None}


@contextmanager
def _process_lock(digest: str, *, blocking_timeout: float = 30, lease_timeout: float = 900, ownership_check: dict | None = None):
    from cache_store import get_cache_backend
    from cache_backends import LocalRedisCache, SqliteCacheBackend
    backend = get_cache_backend()
    if isinstance(backend, LocalRedisCache):
        try:
            lock = backend._redis.lock(backend._cache_key("provider_lock:" + digest),
                                       timeout=lease_timeout, blocking_timeout=blocking_timeout)
            acquired = lock.acquire()
        except Exception:
            acquired = False
        if ownership_check is not None:
            ownership_check["owns"] = lambda: bool(acquired and lock.owned())
        try:
            yield bool(acquired)
        finally:
            if acquired:
                try:
                    lock.release()
                except Exception:
                    pass  # Lost/expired lock must not hide a completed fetch.
        return
    if not isinstance(backend, SqliteCacheBackend):
        if ownership_check is not None:
            ownership_check['owns'] = lambda: True
        yield True
        return
    try:
        import fcntl
    except ImportError:
        if ownership_check is not None:
            ownership_check['owns'] = lambda: True
        yield True  # Non-POSIX SQLite hosts retain in-process single flight.
        return
    from config import CACHE_DB_PATH
    lock_dir = Path(CACHE_DB_PATH).parent / 'provider_locks'
    try:
        lock_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        handle = (lock_dir / (digest + '.lock')).open('a')
    except OSError:
        yield False
        return
    with handle:
        acquired = False
        deadline = time.monotonic() + max(0, blocking_timeout)
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(min(0.05, max(0, deadline - time.monotonic())))
            except OSError:
                break
        if ownership_check is not None:
            ownership_check['owns'] = lambda: acquired
        try:
            yield acquired
        finally:
            if acquired:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
