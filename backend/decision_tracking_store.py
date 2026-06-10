"""SQLite storage for operator-selected decision tracking tickers."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import CACHE_DB_PATH
from storage.sqlite_resource import ThreadLocalSqliteResource


TAIPEI = ZoneInfo("Asia/Taipei")
DECISION_TRACKING_DB_PATH = os.getenv("DECISION_TRACKING_DB_PATH", str(Path(CACHE_DB_PATH).parent / "decision_tracking.sqlite3"))


def _db_path() -> Path:
    return Path(DECISION_TRACKING_DB_PATH)


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_tracking_items (
            ticker TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            last_refresh_date TEXT NOT NULL DEFAULT '',
            last_refresh_at TEXT NOT NULL DEFAULT '',
            last_refresh_status TEXT NOT NULL DEFAULT '',
            last_refresh_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


_resource = ThreadLocalSqliteResource(_db_path, init_schema=_init_schema, row_factory=sqlite3.Row)


def reset_decision_tracking_store_for_tests() -> None:
    _resource.reset()


def _connect() -> sqlite3.Connection:
    return _resource.connect()


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(TAIPEI)).isoformat(timespec="seconds")


def _normalize_ticker(value: str) -> str:
    return str(value or "").strip().upper()


def _row_to_item(row: sqlite3.Row) -> dict:
    return {
        "ticker": row["ticker"],
        "enabled": bool(row["enabled"]),
        "last_refresh_date": row["last_refresh_date"],
        "last_refresh_at": row["last_refresh_at"],
        "last_refresh_status": row["last_refresh_status"],
        "last_refresh_message": row["last_refresh_message"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_items() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT ticker, enabled, last_refresh_date, last_refresh_at,
                   last_refresh_status, last_refresh_message, created_at, updated_at
            FROM decision_tracking_items
            ORDER BY enabled DESC, ticker ASC
            """
        ).fetchall()
    return [_row_to_item(row) for row in rows]


def upsert_item(payload: dict) -> dict:
    ticker = _normalize_ticker((payload or {}).get("ticker"))
    if not ticker:
        raise ValueError("ticker is required")
    enabled = bool((payload or {}).get("enabled", True))
    now = _now_iso()
    with _connect() as conn:
        row = conn.execute("SELECT created_at FROM decision_tracking_items WHERE ticker = ?", (ticker,)).fetchone()
        conn.execute(
            """
            INSERT INTO decision_tracking_items (
                ticker, enabled, last_refresh_date, last_refresh_at,
                last_refresh_status, last_refresh_message, created_at, updated_at
            )
            VALUES (?, ?, '', '', '', '', ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (ticker, 1 if enabled else 0, row["created_at"] if row else now, now),
        )
    return {"items": list_items()}


def delete_item(ticker: str) -> dict:
    ticker = _normalize_ticker(ticker)
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM decision_tracking_items WHERE ticker = ?", (ticker,))
    return {"success": True, "deleted": cursor.rowcount, "items": list_items()}


def mark_refresh(ticker: str, *, status: str, message: str = "", now: datetime | None = None) -> None:
    ticker = _normalize_ticker(ticker)
    refresh_at = _now_iso(now)
    refresh_date = (now or datetime.now(TAIPEI)).date().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE decision_tracking_items
            SET last_refresh_date = ?, last_refresh_at = ?,
                last_refresh_status = ?, last_refresh_message = ?, updated_at = ?
            WHERE ticker = ?
            """,
            (refresh_date, refresh_at, str(status or "")[:32], str(message or "")[:240], refresh_at, ticker),
        )
