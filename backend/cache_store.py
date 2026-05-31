"""Small SQLite-backed JSON cache for network-heavy data fetches."""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from config import CACHE_DB_PATH


_CACHE_LOCK = threading.Lock()


def _json_default(value):
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def _connect():
    path = Path(CACHE_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
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
    return conn


def get_cache_json(cache_key: str) -> Optional[dict]:
    now = time.time()
    with _CACHE_LOCK, _connect() as conn:
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
