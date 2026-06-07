"""Reusable SQLite connection lifecycle helpers."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import suppress
from pathlib import Path
from typing import Callable


class ThreadLocalSqliteResource:
    """Path-aware thread-local SQLite connection manager."""

    def __init__(
        self,
        path_getter: Callable[[], str | Path],
        *,
        init_schema: Callable[[sqlite3.Connection], None] | None = None,
        row_factory=None,
        timeout_seconds: int = 30,
        busy_timeout_ms: int = 5000,
        journal_mode: str = "WAL",
    ):
        self._path_getter = path_getter
        self._init_schema = init_schema
        self._row_factory = row_factory
        self._timeout_seconds = timeout_seconds
        self._busy_timeout_ms = busy_timeout_ms
        self._journal_mode = journal_mode
        self._local = threading.local()
        self._schema_paths: set[Path] = set()
        self._schema_lock = threading.Lock()

    def connect(self) -> sqlite3.Connection:
        path = self._current_path()
        conn = getattr(self._local, "conn", None)
        if conn is not None and getattr(self._local, "path", None) == path:
            return conn
        if conn is not None:
            self.close_current_thread()

        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=self._timeout_seconds)
        if self._row_factory is not None:
            conn.row_factory = self._row_factory
        if self._journal_mode:
            conn.execute(f"PRAGMA journal_mode={self._journal_mode}")
        conn.execute(f"PRAGMA busy_timeout={int(self._busy_timeout_ms)}")
        try:
            self._ensure_schema(conn, path)
        except Exception:
            with suppress(Exception):
                conn.close()
            raise
        self._local.conn = conn
        self._local.path = path
        return conn

    def close_current_thread(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            with suppress(Exception):
                conn.close()
        for attr in ("conn", "path"):
            with suppress(AttributeError):
                delattr(self._local, attr)

    def reset(self) -> None:
        self.close_current_thread()
        with self._schema_lock:
            self._schema_paths.clear()

    def _current_path(self) -> Path:
        return Path(self._path_getter()).expanduser().resolve(strict=False)

    def _ensure_schema(self, conn: sqlite3.Connection, path: Path) -> None:
        if self._init_schema is None or path in self._schema_paths:
            return
        with self._schema_lock:
            if path not in self._schema_paths:
                self._init_schema(conn)
                self._schema_paths.add(path)
