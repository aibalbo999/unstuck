"""429-only guard for final-audit repair fallback."""

from __future__ import annotations

import os
import re
import sqlite3
import threading
import time
from pathlib import Path

import config
from storage.migrations import MigrationRunner


_HTTP_429_RE = re.compile(r"(?:\b429\b|too many requests|resource_exhausted)", re.IGNORECASE)
_LOCK = threading.Lock()
_SCHEMA_VERSION = 1


def is_repair_429_error(message: object) -> bool:
    """Return true only for quota/rate-limit failures that map to HTTP 429."""
    return bool(_HTTP_429_RE.search(str(message or "")))


def _threshold() -> int:
    try:
        return max(1, int(os.getenv("REPAIR_429_CIRCUIT_BREAKER_THRESHOLD", "1")))
    except ValueError:
        return 1


def _cooldown_seconds() -> int:
    try:
        return max(1, int(os.getenv("REPAIR_429_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "900")))
    except ValueError:
        return 900


def _now() -> float:
    return time.time()


def _connect() -> sqlite3.Connection:
    path = Path(config.TASK_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    def migrate_v1(migration_conn: sqlite3.Connection) -> None:
        migration_conn.execute(
            """
            CREATE TABLE IF NOT EXISTS repair_429_circuit_breakers (
                agent_num INTEGER PRIMARY KEY,
                open INTEGER NOT NULL DEFAULT 0,
                failures INTEGER NOT NULL DEFAULT 0,
                last_error TEXT NOT NULL DEFAULT '',
                last_failure_at REAL,
                opened_at REAL,
                updated_at REAL NOT NULL
            )
            """
        )

    MigrationRunner(conn, "repair_429_circuit").run(_SCHEMA_VERSION, {1: migrate_v1})
    return conn


def _row_to_state(row: sqlite3.Row | None) -> dict:
    if row is None:
        return {"open": False, "failures": 0}
    state = {
        "open": bool(row["open"]),
        "failures": int(row["failures"] or 0),
        "last_error": row["last_error"] or "",
        "last_failure_at": row["last_failure_at"],
    }
    if row["opened_at"]:
        state["opened_at"] = row["opened_at"]
    return state


def repair_429_circuit_state(agent_num: int) -> dict:
    agent_key = int(agent_num)
    with _LOCK, _connect() as conn:
        row = conn.execute(
            """
            SELECT agent_num, open, failures, last_error, last_failure_at, opened_at, updated_at
            FROM repair_429_circuit_breakers
            WHERE agent_num = ?
            """,
            (agent_key,),
        ).fetchone()
        state = _row_to_state(row)
        if not row:
            return state

    opened_at = float(state.get("opened_at") or 0)
    if state.get("open") and _now() - opened_at > _cooldown_seconds():
        with _LOCK, _connect() as conn:
            conn.execute("DELETE FROM repair_429_circuit_breakers WHERE agent_num = ?", (agent_key,))
        return {"open": False, "failures": 0}
    return state


def record_repair_429_failure(agent_num: int, message: object = "") -> dict:
    agent_key = int(agent_num)
    state = repair_429_circuit_state(agent_key)
    failures = int(state.get("failures") or 0) + 1
    open_now = failures >= _threshold()
    now = _now()
    updated = {
        "open": open_now,
        "failures": failures,
        "last_error": str(message or "")[:240],
        "last_failure_at": now,
    }
    if open_now:
        updated["opened_at"] = updated["last_failure_at"]
    else:
        updated["opened_at"] = state.get("opened_at")

    with _LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO repair_429_circuit_breakers (
                agent_num, open, failures, last_error, last_failure_at, opened_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_num) DO UPDATE SET
                open = excluded.open,
                failures = excluded.failures,
                last_error = excluded.last_error,
                last_failure_at = excluded.last_failure_at,
                opened_at = excluded.opened_at,
                updated_at = excluded.updated_at
            """,
            (
                agent_key,
                1 if updated["open"] else 0,
                updated["failures"],
                updated["last_error"],
                updated["last_failure_at"],
                updated.get("opened_at"),
                now,
            ),
        )
    return dict(updated)


def clear_repair_429_circuit(agent_num: int | None = None) -> None:
    with _LOCK, _connect() as conn:
        if agent_num is None:
            conn.execute("DELETE FROM repair_429_circuit_breakers")
        else:
            conn.execute("DELETE FROM repair_429_circuit_breakers WHERE agent_num = ?", (int(agent_num),))
