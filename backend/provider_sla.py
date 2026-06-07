"""SQLite-backed provider SLA aggregation from source audit entries."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from config import TASK_DB_PATH
from storage.migrations import MigrationRunner


PROVIDER_SLA_SCHEMA_VERSION = 1
SLA_WARNING_SUCCESS_RATE = 0.8
SLA_CRITICAL_SUCCESS_RATE = 0.5


def _connect():
    path = Path(TASK_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    MigrationRunner(conn, "provider_sla").run(PROVIDER_SLA_SCHEMA_VERSION, {1: _migrate_v1})
    conn.execute("CREATE INDEX IF NOT EXISTS idx_provider_sla_source_provider ON provider_sla_stats(source, provider)")
    return conn


def _migrate_v1(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS provider_sla_stats (
            source TEXT NOT NULL,
            provider TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            unavailable_count INTEGER NOT NULL DEFAULT 0,
            skipped_fresh_cache_count INTEGER NOT NULL DEFAULT 0,
            total_duration_ms INTEGER NOT NULL DEFAULT 0,
            total_records INTEGER NOT NULL DEFAULT 0,
            last_status TEXT,
            last_message TEXT,
            last_at REAL NOT NULL,
            PRIMARY KEY (source, provider)
        )
        """
    )


def record_source_audit_entries(entries: list[dict] | tuple[dict, ...]) -> None:
    if not entries:
        return
    now = time.time()
    rows = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "unknown")
        provider = str(entry.get("provider") or "unknown")
        status = str(entry.get("status") or "unknown")
        duration_ms = int(entry.get("duration_ms") or 0)
        record_count = int(entry.get("record_count") or 0)
        rows.append((source, provider, status, duration_ms, record_count, str(entry.get("message") or "")[:240], now))
    if not rows:
        return
    with _connect() as conn:
        for source, provider, status, duration_ms, record_count, message, timestamp in rows:
            conn.execute(
                """
                INSERT INTO provider_sla_stats (
                    source, provider, attempts, success_count, error_count, unavailable_count,
                    skipped_fresh_cache_count, total_duration_ms, total_records,
                    last_status, last_message, last_at
                )
                VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, provider) DO UPDATE SET
                    attempts = attempts + 1,
                    success_count = success_count + excluded.success_count,
                    error_count = error_count + excluded.error_count,
                    unavailable_count = unavailable_count + excluded.unavailable_count,
                    skipped_fresh_cache_count = skipped_fresh_cache_count + excluded.skipped_fresh_cache_count,
                    total_duration_ms = total_duration_ms + excluded.total_duration_ms,
                    total_records = total_records + excluded.total_records,
                    last_status = excluded.last_status,
                    last_message = excluded.last_message,
                    last_at = excluded.last_at
                """,
                (
                    source,
                    provider,
                    1 if status == "success" else 0,
                    1 if status == "error" else 0,
                    1 if status == "unavailable" else 0,
                    1 if status == "skipped_fresh_cache" else 0,
                    max(duration_ms, 0),
                    max(record_count, 0),
                    status,
                    message,
                    timestamp,
                ),
            )


def get_provider_sla_summary(limit: int = 100) -> list[dict]:
    safe_limit = max(1, min(int(limit or 100), 1000))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM provider_sla_stats
            ORDER BY last_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    summary = []
    for row in rows:
        attempts = int(row["attempts"] or 0)
        success_count = int(row["success_count"] or 0)
        total_duration_ms = int(row["total_duration_ms"] or 0)
        item = {
            "source": row["source"],
            "provider": row["provider"],
            "attempts": attempts,
            "success_count": success_count,
            "error_count": int(row["error_count"] or 0),
            "unavailable_count": int(row["unavailable_count"] or 0),
            "skipped_fresh_cache_count": int(row["skipped_fresh_cache_count"] or 0),
            "success_rate": round(success_count / attempts, 4) if attempts else 0.0,
            "avg_duration_ms": round(total_duration_ms / attempts, 2) if attempts else 0.0,
            "total_records": int(row["total_records"] or 0),
            "last_status": row["last_status"],
            "last_message": row["last_message"],
            "last_at": row["last_at"],
        }
        item.update(_provider_alert_fields(item))
        summary.append(item)
    return summary


def _provider_alert_fields(item: dict) -> dict:
    attempts = int(item.get("attempts") or 0)
    success_rate = float(item.get("success_rate") or 0.0)
    error_count = int(item.get("error_count") or 0)
    last_status = str(item.get("last_status") or "")

    if attempts >= 3 and (success_rate < SLA_CRITICAL_SUCCESS_RATE or error_count >= 3):
        return {
            "alert_level": "critical",
            "alert_message": f"{item.get('provider')} 成功率偏低（{success_rate:.0%}），最近狀態：{last_status or 'unknown'}",
        }
    if last_status in {"error", "unavailable"} or (attempts >= 3 and success_rate < SLA_WARNING_SUCCESS_RATE):
        return {
            "alert_level": "warning",
            "alert_message": f"{item.get('provider')} 最近有來源異常或成功率低於 {SLA_WARNING_SUCCESS_RATE:.0%}",
        }
    return {"alert_level": "ok", "alert_message": ""}


def get_provider_sla_alerts(limit: int = 100) -> list[dict]:
    summary = get_provider_sla_summary(limit)
    return [
        {
            "source": item["source"],
            "provider": item["provider"],
            "alert_level": item["alert_level"],
            "alert_message": item["alert_message"],
            "success_rate": item["success_rate"],
            "last_status": item["last_status"],
        }
        for item in summary
        if item.get("alert_level") in {"warning", "critical"}
    ]
