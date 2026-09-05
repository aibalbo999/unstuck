"""Versioned trading evaluations, separate from legacy calendar-month rows."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import decision_tracking_store
from trade_path_backtest import SCHEMA_VERSION


def _path() -> Path:
    return Path(decision_tracking_store.DECISION_TRACKING_DB_PATH).resolve()


def save_result(result: dict) -> None:
    filename = str(result.get("report_filename") or "")
    horizon = result.get("horizon_trading_days")
    if not filename or result.get("schema_version") != SCHEMA_VERSION or isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 252:
        raise ValueError("versioned filename and explicit trading horizon are required")
    payload = json.dumps(result, ensure_ascii=False, allow_nan=False)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=15)) as conn, conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS trade_evaluation_results_v1 (
            report_filename TEXT NOT NULL, horizon_trading_days INTEGER NOT NULL,
            schema_version TEXT NOT NULL, ticker TEXT NOT NULL, pipeline_id TEXT NOT NULL,
            evaluation_date TEXT NOT NULL, payload_json TEXT NOT NULL,
            PRIMARY KEY (report_filename, horizon_trading_days, schema_version)
        )""")
        conn.execute("""INSERT INTO trade_evaluation_results_v1 VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_filename, horizon_trading_days, schema_version) DO UPDATE SET
            evaluation_date=excluded.evaluation_date, payload_json=excluded.payload_json""",
            (filename, horizon, SCHEMA_VERSION, str(result.get("ticker") or ""),
             str(result.get("pipeline_id") or ""), str(result.get("evaluation_date") or ""), payload))


def list_results(*, report_filename: str | None = None, ticker: str | None = None, limit: int = 2000) -> list[dict]:
    path = _path()
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=15)) as conn:
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='trade_evaluation_results_v1'").fetchone() is None:
            return []
        clauses, params = ["schema_version = ?"], [SCHEMA_VERSION]
        for key, value in (("report_filename", report_filename), ("ticker", ticker)):
            if value is not None:
                clauses.append(f"{key} = ?")
                params.append(str(value))
        rows = conn.execute(
            "SELECT payload_json FROM trade_evaluation_results_v1 WHERE " + " AND ".join(clauses)
            + " ORDER BY evaluation_date DESC, report_filename, horizon_trading_days LIMIT ?",
            [*params, max(1, min(int(limit), 2000))],
        ).fetchall()
    return [json.loads(row[0]) for row in rows]
