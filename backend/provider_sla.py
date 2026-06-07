"""SQLite-backed provider SLA aggregation from source audit entries."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from config import TASK_DB_PATH
from storage.migrations import MigrationRunner


PROVIDER_SLA_SCHEMA_VERSION = 2
SLA_WARNING_SUCCESS_RATE = 0.8
SLA_CRITICAL_SUCCESS_RATE = 0.5
SLA_WINDOWS = {
    "last_1h": 60 * 60,
    "last_24h": 24 * 60 * 60,
    "last_7d": 7 * 24 * 60 * 60,
}


def _connect():
    path = Path(TASK_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    MigrationRunner(conn, "provider_sla").run(PROVIDER_SLA_SCHEMA_VERSION, {1: _migrate_v1, 2: _migrate_v2})
    conn.execute("CREATE INDEX IF NOT EXISTS idx_provider_sla_source_provider ON provider_sla_stats(source, provider)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_provider_sla_events_lookup ON provider_sla_events(source, provider, created_at)")
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


def _migrate_v2(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS provider_sla_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            provider TEXT NOT NULL,
            status TEXT NOT NULL,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            record_count INTEGER NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
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
                INSERT INTO provider_sla_events (
                    source, provider, status, duration_ms, record_count, message, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    provider,
                    status,
                    max(duration_ms, 0),
                    max(record_count, 0),
                    message,
                    timestamp,
                ),
            )
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
        now = time.time()
        windows_by_provider = {
            (row["source"], row["provider"]): _window_stats_for_provider(conn, row["source"], row["provider"], now)
            for row in rows
        }
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
            "windows": windows_by_provider.get((row["source"], row["provider"]), {}),
        }
        item.update(_provider_alert_fields(item))
        summary.append(item)
    return summary


def _empty_window_stats() -> dict:
    return {
        "attempts": 0,
        "success_count": 0,
        "error_count": 0,
        "unavailable_count": 0,
        "skipped_fresh_cache_count": 0,
        "success_rate": 0.0,
        "avg_duration_ms": 0.0,
        "total_records": 0,
    }


def _window_stats_for_provider(conn: sqlite3.Connection, source: str, provider: str, now: float) -> dict:
    windows = {}
    for label, seconds in SLA_WINDOWS.items():
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS attempts,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count,
                SUM(CASE WHEN status = 'unavailable' THEN 1 ELSE 0 END) AS unavailable_count,
                SUM(CASE WHEN status = 'skipped_fresh_cache' THEN 1 ELSE 0 END) AS skipped_fresh_cache_count,
                SUM(duration_ms) AS total_duration_ms,
                SUM(record_count) AS total_records
            FROM provider_sla_events
            WHERE source = ? AND provider = ? AND created_at >= ?
            """,
            (source, provider, now - seconds),
        ).fetchone()
        attempts = int(row["attempts"] or 0)
        if attempts <= 0:
            windows[label] = _empty_window_stats()
            continue
        success_count = int(row["success_count"] or 0)
        total_duration_ms = int(row["total_duration_ms"] or 0)
        windows[label] = {
            "attempts": attempts,
            "success_count": success_count,
            "error_count": int(row["error_count"] or 0),
            "unavailable_count": int(row["unavailable_count"] or 0),
            "skipped_fresh_cache_count": int(row["skipped_fresh_cache_count"] or 0),
            "success_rate": round(success_count / attempts, 4),
            "avg_duration_ms": round(total_duration_ms / attempts, 2),
            "total_records": int(row["total_records"] or 0),
        }
    return windows


def _provider_alert_fields(item: dict) -> dict:
    basis = _alert_basis(item)
    attempts = int(basis.get("attempts") or 0)
    success_rate = float(basis.get("success_rate") or 0.0)
    error_count = int(basis.get("error_count") or 0)
    last_status = str(item.get("last_status") or "")
    basis_label = basis.get("label") or "累積"

    if attempts >= 3 and (success_rate < SLA_CRITICAL_SUCCESS_RATE or error_count >= 3):
        return {
            "alert_level": "critical",
            "alert_message": f"{item.get('provider')} {basis_label}成功率偏低（{success_rate:.0%}），最近狀態：{last_status or 'unknown'}",
            "alert_basis": basis_label,
        }
    if last_status in {"error", "unavailable"} or (attempts >= 3 and success_rate < SLA_WARNING_SUCCESS_RATE):
        return {
            "alert_level": "warning",
            "alert_message": f"{item.get('provider')} 最近有來源異常或 {basis_label}成功率低於 {SLA_WARNING_SUCCESS_RATE:.0%}",
            "alert_basis": basis_label,
        }
    return {"alert_level": "ok", "alert_message": "", "alert_basis": basis_label}


def _alert_basis(item: dict) -> dict:
    windows = item.get("windows") if isinstance(item.get("windows"), dict) else {}
    for label in ("last_1h", "last_24h", "last_7d"):
        stats = dict(windows.get(label) or {})
        if int(stats.get("attempts") or 0) >= 3:
            stats["label"] = label
            return stats
    return {
        "label": "累積",
        "attempts": int(item.get("attempts") or 0),
        "success_rate": float(item.get("success_rate") or 0.0),
        "error_count": int(item.get("error_count") or 0),
    }


def get_provider_sla_alerts(limit: int = 100) -> list[dict]:
    summary = get_provider_sla_summary(limit)
    return [
        {
            "source": item["source"],
            "provider": item["provider"],
            "alert_level": item["alert_level"],
            "alert_message": item["alert_message"],
            "success_rate": item["success_rate"],
            "attempts": item["attempts"],
            "last_status": item["last_status"],
            "alert_basis": item.get("alert_basis"),
            "windows": item.get("windows", {}),
        }
        for item in summary
        if item.get("alert_level") in {"warning", "critical"}
    ]
