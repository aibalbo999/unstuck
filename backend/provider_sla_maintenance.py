"""Maintenance helpers for provider SLA event retention."""

from __future__ import annotations

import time
from typing import Optional

from config import PROVIDER_SLA_RETENTION_DAYS
from provider_sla import _connect


def cleanup_provider_sla_events(retention_days: Optional[int] = None) -> dict:
    days = int(retention_days or PROVIDER_SLA_RETENTION_DAYS)
    cutoff = time.time() - max(days, 1) * 24 * 60 * 60
    with _connect() as conn:
        before = conn.execute("SELECT COUNT(*) FROM provider_sla_events").fetchone()[0]
        conn.execute("DELETE FROM provider_sla_events WHERE created_at < ?", (cutoff,))
        after = conn.execute("SELECT COUNT(*) FROM provider_sla_events").fetchone()[0]
        _rebuild_provider_sla_stats(conn)
    return {
        "retention_days": days,
        "deleted": int(before - after),
        "remaining": int(after),
    }


def _rebuild_provider_sla_stats(conn) -> None:
    conn.execute("DELETE FROM provider_sla_stats")
    rows = conn.execute(
        """
        SELECT source, provider,
               COUNT(*) AS attempts,
               SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
               SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count,
               SUM(CASE WHEN status = 'unavailable' THEN 1 ELSE 0 END) AS unavailable_count,
               SUM(CASE WHEN status = 'skipped_fresh_cache' THEN 1 ELSE 0 END) AS skipped_fresh_cache_count,
               SUM(duration_ms) AS total_duration_ms,
               SUM(record_count) AS total_records,
               MAX(created_at) AS last_at
        FROM provider_sla_events
        GROUP BY source, provider
        """
    ).fetchall()
    for row in rows:
        last = conn.execute(
            """
            SELECT status, message
            FROM provider_sla_events
            WHERE source = ? AND provider = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (row["source"], row["provider"]),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO provider_sla_stats (
                source, provider, attempts, success_count, error_count, unavailable_count,
                skipped_fresh_cache_count, total_duration_ms, total_records,
                last_status, last_message, last_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["source"],
                row["provider"],
                int(row["attempts"] or 0),
                int(row["success_count"] or 0),
                int(row["error_count"] or 0),
                int(row["unavailable_count"] or 0),
                int(row["skipped_fresh_cache_count"] or 0),
                int(row["total_duration_ms"] or 0),
                int(row["total_records"] or 0),
                last["status"] if last else "",
                last["message"] if last else "",
                float(row["last_at"] or time.time()),
            ),
        )
