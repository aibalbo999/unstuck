"""SQLite storage for operator-selected decision tracking tickers."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import TASK_DB_PATH
from storage.sqlite_resource import ThreadLocalSqliteResource


TAIPEI = ZoneInfo("Asia/Taipei")
DECISION_TRACKING_DB_PATH = os.getenv("DECISION_TRACKING_DB_PATH", TASK_DB_PATH)


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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_backtest_results (
            report_filename TEXT NOT NULL,
            ticker TEXT NOT NULL,
            pipeline_id TEXT NOT NULL,
            horizon_months INTEGER NOT NULL,
            generated_date TEXT NOT NULL,
            evaluation_date TEXT NOT NULL,
            initial_price REAL NOT NULL,
            actual_price REAL NOT NULL,
            target_price REAL,
            recommendation TEXT NOT NULL,
            market_return_pct REAL NOT NULL,
            strategy_roi_pct REAL NOT NULL,
            target_error_pct REAL,
            outcome TEXT NOT NULL,
            reason TEXT NOT NULL,
            evaluated_at TEXT NOT NULL,
            PRIMARY KEY (report_filename, horizon_months)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_decision_backtests_ticker_date "
        "ON decision_backtest_results (ticker, evaluation_date DESC)"
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


def upsert_backtest_result(result: dict) -> dict:
    evaluated_at = str(result.get("evaluated_at") or _now_iso())
    values = (
        str(result.get("report_filename") or ""),
        _normalize_ticker(result.get("ticker")),
        str(result.get("pipeline_id") or "v1"),
        int(result.get("horizon_months") or 0),
        str(result.get("generated_date") or ""),
        str(result.get("evaluation_date") or ""),
        float(result.get("initial_price")),
        float(result.get("actual_price")),
        float(result["target_price"]) if result.get("target_price") is not None else None,
        str(result.get("recommendation") or ""),
        float(result.get("market_return_pct") or 0),
        float(result.get("strategy_roi_pct") or 0),
        float(result["target_error_pct"]) if result.get("target_error_pct") is not None else None,
        str(result.get("outcome") or "miss"),
        str(result.get("reason") or ""),
        evaluated_at,
    )
    if not values[0] or values[3] not in {3, 6, 12}:
        raise ValueError("report_filename and valid horizon_months are required")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO decision_backtest_results (
                report_filename, ticker, pipeline_id, horizon_months,
                generated_date, evaluation_date, initial_price, actual_price,
                target_price, recommendation, market_return_pct, strategy_roi_pct,
                target_error_pct, outcome, reason, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_filename, horizon_months) DO UPDATE SET
                ticker = excluded.ticker,
                pipeline_id = excluded.pipeline_id,
                evaluation_date = excluded.evaluation_date,
                initial_price = excluded.initial_price,
                actual_price = excluded.actual_price,
                target_price = excluded.target_price,
                recommendation = excluded.recommendation,
                market_return_pct = excluded.market_return_pct,
                strategy_roi_pct = excluded.strategy_roi_pct,
                target_error_pct = excluded.target_error_pct,
                outcome = excluded.outcome,
                reason = excluded.reason,
                evaluated_at = excluded.evaluated_at
            """,
            values,
        )
    return result


def backtest_result_exists(report_filename: str, horizon_months: int) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM decision_backtest_results WHERE report_filename = ? AND horizon_months = ?",
            (str(report_filename or ""), int(horizon_months)),
        ).fetchone()
    return row is not None


def list_backtest_results(*, ticker: str | None = None, limit: int = 200) -> list[dict]:
    clauses = []
    params: list[object] = []
    if ticker:
        clauses.append("ticker = ?")
        params.append(_normalize_ticker(ticker))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM decision_backtest_results {where} "
            "ORDER BY evaluation_date DESC, report_filename DESC, horizon_months ASC LIMIT ?",
            [*params, max(1, min(int(limit), 2000))],
        ).fetchall()
    return [dict(row) for row in rows]


def list_backtests_for_report(report_filename: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM decision_backtest_results WHERE report_filename = ? ORDER BY horizon_months ASC",
            (str(report_filename or ""),),
        ).fetchall()
    return [dict(row) for row in rows]
