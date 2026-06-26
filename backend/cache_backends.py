"""Pluggable JSON cache backends used by the stock-agent runtime."""

from __future__ import annotations

import copy
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

from storage.migrations import MigrationRunner
from storage.sqlite_resource import ThreadLocalSqliteResource


CACHE_STORE_SCHEMA_VERSION = 1


@runtime_checkable
class CacheBackend(Protocol):
    def get_json(self, key: str) -> object | None:
        """Return cached JSON-compatible data, or ``None`` on miss/expiry."""

    def set_json(self, key: str, value: object, *, ttl_seconds: int) -> None:
        """Store JSON-compatible data for ``ttl_seconds``."""

    def delete(self, key: str) -> bool:
        """Delete one cache key and report whether anything was removed."""

    def cleanup_expired(self) -> int:
        """Delete expired cache rows and return the number removed."""

    def close(self) -> None:
        """Release backend resources owned by the current process/thread."""


def _json_default(value: object) -> object:
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def _serialize_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=_json_default)


def _deserialize_json(payload: str | bytes) -> object:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    return json.loads(payload)


def _validate_ttl(ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cache_entries (
            cache_key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            expires_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    MigrationRunner(conn, "cache_store").run(
        CACHE_STORE_SCHEMA_VERSION,
        {
            1: lambda migration_conn: migration_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at ON cache_entries(expires_at)"
            )
        },
    )


class SqliteCacheBackend:
    """SQLite-backed cache for local-first deployments."""

    def __init__(self, db_path: str | Path):
        self._lock = threading.Lock()
        self._resource = ThreadLocalSqliteResource(lambda: db_path, init_schema=_init_schema)

    def get_json(self, key: str) -> object | None:
        now = time.time()
        with self._resource.connect() as conn:
            row = conn.execute(
                "SELECT value, expires_at, updated_at FROM cache_entries WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if not row:
                return None

            value, expires_at, updated_at = row
            if expires_at <= now:
                self._delete_if_unchanged(conn, key, value, expires_at, updated_at)
                return None

            try:
                return _deserialize_json(value)
            except json.JSONDecodeError:
                self._delete_if_unchanged(conn, key, value, expires_at, updated_at)
                return None

    def set_json(self, key: str, value: object, *, ttl_seconds: int) -> None:
        _validate_ttl(ttl_seconds)
        now = time.time()
        serialized = _serialize_json(value)
        with self._lock, self._resource.connect() as conn:
            conn.execute(
                """
                INSERT INTO cache_entries (cache_key, value, expires_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    value = excluded.value,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at
                """,
                (key, serialized, now + ttl_seconds, now),
            )

    def delete(self, key: str) -> bool:
        with self._lock, self._resource.connect() as conn:
            cursor = conn.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))
            return cursor.rowcount > 0

    def cleanup_expired(self) -> int:
        with self._lock, self._resource.connect() as conn:
            cursor = conn.execute("DELETE FROM cache_entries WHERE expires_at <= ?", (time.time(),))
            return cursor.rowcount

    def close(self) -> None:
        self._resource.close_current_thread()

    def reset(self) -> None:
        self._resource.reset()

    def _delete_if_unchanged(
        self,
        conn: sqlite3.Connection,
        key: str,
        value: str,
        expires_at: float,
        updated_at: float,
    ) -> None:
        with self._lock:
            conn.execute(
                """
                DELETE FROM cache_entries
                WHERE cache_key = ?
                  AND value = ?
                  AND expires_at = ?
                  AND updated_at = ?
                """,
                (key, value, expires_at, updated_at),
            )


class InMemoryCache:
    """Thread-safe in-memory cache for tests and short-lived local tooling."""

    def __init__(self):
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[object, float]] = {}

    def get_json(self, key: str) -> object | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at <= time.time():
                self._entries.pop(key, None)
                return None
            return copy.deepcopy(value)

    def set_json(self, key: str, value: object, *, ttl_seconds: int) -> None:
        _validate_ttl(ttl_seconds)
        with self._lock:
            self._entries[key] = (copy.deepcopy(value), time.time() + ttl_seconds)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._entries.pop(key, None) is not None

    def cleanup_expired(self) -> int:
        now = time.time()
        with self._lock:
            expired = [key for key, (_, expires_at) in self._entries.items() if expires_at <= now]
            for key in expired:
                self._entries.pop(key, None)
            return len(expired)

    def close(self) -> None:
        return None

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()


class LocalRedisCache:
    """Redis-backed cache suitable for local multi-worker deployments."""

    def __init__(
        self,
        redis_url: str | None = "redis://localhost:6379/0",
        *,
        redis_client: object | None = None,
        namespace: str = "stock-agent",
    ):
        if redis_client is None:
            from redis import Redis

            redis_client = Redis.from_url(redis_url or "redis://localhost:6379/0")
        self._redis = redis_client
        self._namespace = namespace.strip(":")

    def get_json(self, key: str) -> object | None:
        payload = self._redis.get(self._cache_key(key))
        if payload is None:
            return None
        return _deserialize_json(payload)

    def set_json(self, key: str, value: object, *, ttl_seconds: int) -> None:
        _validate_ttl(ttl_seconds)
        self._redis.set(self._cache_key(key), _serialize_json(value), ex=ttl_seconds)

    def delete(self, key: str) -> bool:
        return bool(self._redis.delete(self._cache_key(key)))

    def cleanup_expired(self) -> int:
        return 0

    def close(self) -> None:
        close = getattr(self._redis, "close", None)
        if callable(close):
            close()

    def _cache_key(self, key: str) -> str:
        if not self._namespace:
            return key
        return f"{self._namespace}:{key}"
