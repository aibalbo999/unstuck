"""SQLite connection opening for the report metadata index."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Callable


_TRANSIENT_OPEN_ERRORS = (
    "unable to open database file",
    "database is locked",
)


def connect_report_index_sqlite(
    db_path: str | Path,
    connect_fn: Callable = sqlite3.connect,
    *,
    attempts: int = 3,
    initialize: Callable[[sqlite3.Connection], None] | None = None,
) -> sqlite3.Connection:
    path = Path(db_path).expanduser().resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(max(1, attempts)):
        conn = None
        try:
            conn = connect_fn(path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=5000")
            _enable_wal_best_effort(conn)
            if initialize is not None:
                initialize(conn)
            return conn
        except sqlite3.OperationalError as exc:
            if conn is not None:
                conn.close()
            if attempt >= attempts - 1 or not _is_transient_open_error(exc):
                raise
            time.sleep(0.05 * (attempt + 1))
    raise sqlite3.OperationalError("unable to open report index database")


def _is_transient_open_error(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    return any(fragment in message for fragment in _TRANSIENT_OPEN_ERRORS)


def _enable_wal_best_effort(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError as exc:
        if not _is_transient_open_error(exc):
            raise
