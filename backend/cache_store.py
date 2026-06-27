"""Process-wide JSON cache facade for network-heavy data fetches."""

from __future__ import annotations

import threading

from cache_backends import CacheBackend, SqliteCacheBackend
from config import CACHE_DB_PATH


_BACKEND_LOCK = threading.RLock()
_backend: CacheBackend | None = None


def get_cache_backend() -> CacheBackend:
    """Return the configured cache backend, lazily creating the local SQLite one."""
    global _backend
    with _BACKEND_LOCK:
        if _backend is None:
            _backend = SqliteCacheBackend(CACHE_DB_PATH)
        return _backend


def set_cache_backend(backend: CacheBackend) -> None:
    """Replace the process-wide cache backend."""
    global _backend
    with _BACKEND_LOCK:
        previous = _backend
        _backend = backend
    if previous is not None and previous is not backend:
        previous.close()


def close_cache_store() -> None:
    with _BACKEND_LOCK:
        backend = _backend
    if backend is not None:
        backend.close()


def reset_cache_store_for_tests() -> None:
    """Reset test state and clear the lazy backend.

    Clearing the singleton is important because tests monkeypatch ``CACHE_DB_PATH``
    and expect the next cache operation to open a fresh SQLite database.
    """
    global _backend
    with _BACKEND_LOCK:
        backend = _backend
        _backend = None
    if backend is None:
        return
    reset = getattr(backend, "reset", None)
    if callable(reset):
        reset()
    backend.close()


def get_cache_json(cache_key: str) -> object | None:
    return get_cache_backend().get_json(cache_key)


def set_cache_json(cache_key: str, value: object, ttl_seconds: int) -> None:
    get_cache_backend().set_json(cache_key, value, ttl_seconds=ttl_seconds)


def cleanup_expired_cache_entries() -> int:
    """Delete expired entries from the configured cache backend."""
    return get_cache_backend().cleanup_expired()
