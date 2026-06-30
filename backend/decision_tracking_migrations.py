"""SQLite migrations for decision tracking storage."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path


def ensure_legacy_sqlite_migrated(
    conn: sqlite3.Connection,
    *,
    target_path: Path,
    legacy_path: Path,
    now: Callable[[], str],
) -> None:
    """Copy legacy standalone decision tracking DB rows into the operational DB once."""
    target_path = target_path.expanduser().resolve(strict=False)
    legacy_path = legacy_path.expanduser().resolve(strict=False)
    migration_key = f"legacy_sqlite_migrated:{legacy_path}"
    if _meta_value(conn, migration_key):
        return
    if target_path == legacy_path or target_path.parent != legacy_path.parent or not legacy_path.exists():
        _set_meta(conn, migration_key, now())
        return

    try:
        with sqlite3.connect(legacy_path) as source:
            source.row_factory = sqlite3.Row
            copied_items = _copy_legacy_items(conn, source)
            copied_backtests = _copy_legacy_backtests(conn, source)
    except sqlite3.Error:
        return
    _set_meta(conn, migration_key, f"{now()}:items={copied_items}:backtests={copied_backtests}")


def _meta_value(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM decision_tracking_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO decision_tracking_meta (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _copy_legacy_items(conn: sqlite3.Connection, source: sqlite3.Connection) -> int:
    if not _table_exists(source, "decision_tracking_items"):
        return 0
    rows = source.execute(
        """
        SELECT ticker, enabled, last_refresh_date, last_refresh_at,
               last_refresh_status, last_refresh_message, created_at, updated_at
        FROM decision_tracking_items
        """
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            INSERT OR IGNORE INTO decision_tracking_items (
                ticker, enabled, last_refresh_date, last_refresh_at,
                last_refresh_status, last_refresh_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["ticker"],
                row["enabled"],
                row["last_refresh_date"],
                row["last_refresh_at"],
                row["last_refresh_status"],
                row["last_refresh_message"],
                row["created_at"],
                row["updated_at"],
            ),
        )
    return len(rows)


def _copy_legacy_backtests(conn: sqlite3.Connection, source: sqlite3.Connection) -> int:
    if not _table_exists(source, "decision_backtest_results"):
        return 0
    rows = source.execute(
        """
        SELECT report_filename, ticker, pipeline_id, horizon_months,
               generated_date, evaluation_date, initial_price, actual_price,
               target_price, recommendation, market_return_pct, strategy_roi_pct,
               target_error_pct, outcome, reason, evaluated_at
        FROM decision_backtest_results
        """
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            INSERT OR IGNORE INTO decision_backtest_results (
                report_filename, ticker, pipeline_id, horizon_months,
                generated_date, evaluation_date, initial_price, actual_price,
                target_price, recommendation, market_return_pct, strategy_roi_pct,
                target_error_pct, outcome, reason, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["report_filename"],
                row["ticker"],
                row["pipeline_id"],
                row["horizon_months"],
                row["generated_date"],
                row["evaluation_date"],
                row["initial_price"],
                row["actual_price"],
                row["target_price"],
                row["recommendation"],
                row["market_return_pct"],
                row["strategy_roi_pct"],
                row["target_error_pct"],
                row["outcome"],
                row["reason"],
                row["evaluated_at"],
            ),
        )
    return len(rows)
