"""Persistent API usage ledger for quota dashboards."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import TASK_DB_PATH
from storage.sqlite_resource import ThreadLocalSqliteResource


API_USAGE_DB_PATH = os.getenv("API_USAGE_DB_PATH")


def _db_path() -> Path:
    if API_USAGE_DB_PATH:
        return Path(API_USAGE_DB_PATH)
    for module_name in ("job_store", "provider_sla"):
        module = sys.modules.get(module_name)
        task_db_path = getattr(module, "TASK_DB_PATH", None)
        if task_db_path:
            return Path(task_db_path)
    return Path(TASK_DB_PATH)


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS api_usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service TEXT NOT NULL,
            provider TEXT NOT NULL,
            operation TEXT NOT NULL,
            model_id TEXT,
            status TEXT NOT NULL,
            units INTEGER NOT NULL DEFAULT 1,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_service_created ON api_usage_events(service, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_provider_created ON api_usage_events(provider, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_operation_created ON api_usage_events(operation, created_at)")


_resource = ThreadLocalSqliteResource(_db_path, init_schema=_init_schema, row_factory=sqlite3.Row)


def _connect() -> sqlite3.Connection:
    return _resource.connect()


def _connect_for_path(db_path: str | Path | None = None) -> sqlite3.Connection:
    if db_path is None:
        return _connect()
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    _init_schema(conn)
    return conn


def reset_api_usage_store_for_tests() -> None:
    _resource.reset()


def _since_timestamp(value: datetime | float | int) -> float:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
    return float(value)


def _json_default(value: Any) -> str:
    return str(value)


def record_api_usage(
    *,
    service: str,
    provider: str,
    operation: str,
    status: str = "attempt",
    units: int = 1,
    model_id: str | None = None,
    metadata: dict | None = None,
    created_at: float | None = None,
    db_path: str | Path | None = None,
) -> None:
    timestamp = float(created_at if created_at is not None else time.time())
    with _connect_for_path(db_path) as conn:
        conn.execute(
            """
            INSERT INTO api_usage_events (
                service, provider, operation, model_id, status, units, metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(service or "unknown"),
                str(provider or "unknown"),
                str(operation or "unknown"),
                str(model_id) if model_id else None,
                str(status or "attempt"),
                max(int(units or 0), 0),
                json.dumps(metadata or {}, ensure_ascii=False, default=_json_default),
                timestamp,
            ),
        )


def _metadata_from_row(row: sqlite3.Row) -> dict:
    try:
        value = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _error_like_status(status: str) -> bool:
    return status in {"error", "quota_error", "rate_limited", "unavailable"}


def summarize_llm_usage_since(since_utc: datetime | float | int) -> dict:
    since_ts = _since_timestamp(since_utc)
    with _connect() as conn:
        call_row = conn.execute(
            """
            SELECT COALESCE(SUM(units), 0) AS calls
            FROM api_usage_events
            WHERE service = 'Gemini / Google AI'
              AND operation = 'llm_model_call'
              AND created_at >= ?
            """,
            (since_ts,),
        ).fetchone()
        model_rows = conn.execute(
            """
            SELECT COALESCE(model_id, 'unknown') AS model_id, COALESCE(SUM(units), 0) AS calls
            FROM api_usage_events
            WHERE service = 'Gemini / Google AI'
              AND operation = 'llm_model_call'
              AND created_at >= ?
            GROUP BY COALESCE(model_id, 'unknown')
            ORDER BY calls DESC, model_id ASC
            """,
            (since_ts,),
        ).fetchall()
        quota_rows = conn.execute(
            """
            SELECT *
            FROM api_usage_events
            WHERE service = 'Gemini / Google AI'
              AND status IN ('quota_error', 'rate_limited')
              AND created_at >= ?
            ORDER BY created_at DESC, id DESC
            LIMIT 5
            """,
            (since_ts,),
        ).fetchall()
        quota_count_row = conn.execute(
            """
            SELECT COUNT(*) AS quota_errors
            FROM api_usage_events
            WHERE service = 'Gemini / Google AI'
              AND status IN ('quota_error', 'rate_limited')
              AND created_at >= ?
            """,
            (since_ts,),
        ).fetchone()
    return {
        "observed_calls_since_reset": int(call_row["calls"] or 0),
        "observed_model_calls": {row["model_id"]: int(row["calls"] or 0) for row in model_rows},
        "observed_quota_errors_since_reset": int(quota_count_row["quota_errors"] or 0),
        "recent_quota_events": [
            {
                "at": row["created_at"],
                "model_id": row["model_id"] or "unknown",
                "message": str(_metadata_from_row(row).get("message") or "")[:180],
            }
            for row in quota_rows
        ],
        "ledger_source": "api_usage_events",
    }


def summarize_provider_usage_since(since_utc: datetime | float | int, provider_names: set[str]) -> dict:
    since_ts = _since_timestamp(since_utc)
    if not provider_names:
        return {
            "observed_attempts_since_reset": 0,
            "observed_errors_since_reset": 0,
            "observed_24h_attempts": 0,
            "observed_24h_errors": 0,
            "ledger_source": "api_usage_events",
        }
    placeholders = ",".join("?" for _ in provider_names)
    params = [*sorted(provider_names), since_ts]
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT status, COALESCE(SUM(units), 0) AS units, COUNT(*) AS events
            FROM api_usage_events
            WHERE provider IN ({placeholders}) AND created_at >= ?
            GROUP BY status
            """,
            params,
        ).fetchall()
    attempts = 0
    errors = 0
    for row in rows:
        status = str(row["status"] or "")
        units = int(row["units"] or 0)
        attempts += units
        if _error_like_status(status):
            errors += int(row["events"] or 0)
    return {
        "observed_attempts_since_reset": attempts,
        "observed_errors_since_reset": errors,
        "observed_24h_attempts": attempts,
        "observed_24h_errors": errors,
        "ledger_source": "api_usage_events",
    }


def record_runtime_event_usage(*args, **kwargs) -> None:
    from api_usage_recorders import record_runtime_event_usage as recorder

    recorder(*args, **kwargs)


def record_provider_audit_usage(*args, **kwargs) -> None:
    from api_usage_recorders import record_provider_audit_usage as recorder

    recorder(*args, **kwargs)


__all__ = [
    "record_api_usage",
    "record_provider_audit_usage",
    "record_runtime_event_usage",
    "reset_api_usage_store_for_tests",
    "summarize_llm_usage_since",
    "summarize_provider_usage_since",
]
