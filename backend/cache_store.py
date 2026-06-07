"""Small SQLite-backed JSON cache for network-heavy data fetches."""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from config import CACHE_DB_PATH
from storage.migrations import MigrationRunner


_CACHE_LOCK = threading.Lock()
CACHE_STORE_SCHEMA_VERSION = 1


def _json_default(value):
    if hasattr(value, "item"):
        return value.item()
    return str(value)


_local = threading.local()
_schema_initialized = False
_SCHEMA_LOCK = threading.Lock()


def _init_schema(conn: sqlite3.Connection):
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


def _connect():
    global _schema_initialized
    if hasattr(_local, "conn"):
        return _local.conn

    path = Path(CACHE_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    if not _schema_initialized:
        with _SCHEMA_LOCK:
            if not _schema_initialized:
                _init_schema(conn)
                _schema_initialized = True

    _local.conn = conn
    return conn


def get_cache_json(cache_key: str) -> Optional[dict]:
    now = time.time()
    with _connect() as conn:
        row = conn.execute(
            "SELECT value, expires_at FROM cache_entries WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if not row:
            return None

        value, expires_at = row
        if expires_at <= now:
            conn.execute("DELETE FROM cache_entries WHERE cache_key = ?", (cache_key,))
            return None

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            conn.execute("DELETE FROM cache_entries WHERE cache_key = ?", (cache_key,))
            return None



def set_cache_json(cache_key: str, value: dict, ttl_seconds: int) -> None:
    expires_at = time.time() + ttl_seconds
    serialized = json.dumps(value, ensure_ascii=False, default=_json_default)
    with _CACHE_LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO cache_entries (cache_key, value, expires_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                value = excluded.value,
                expires_at = excluded.expires_at,
                updated_at = excluded.updated_at
            """,
            (cache_key, serialized, expires_at, time.time()),
        )


def cleanup_expired_cache_entries() -> int:
    """Delete expired entries from the cache to prevent unbounded growth."""
    now = time.time()
    with _CACHE_LOCK, _connect() as conn:
        cursor = conn.execute("DELETE FROM cache_entries WHERE expires_at < ?", (now,))
        return cursor.rowcount
