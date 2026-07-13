"""Persistent audit store for notification delivery results."""

from __future__ import annotations

from collections.abc import Mapping
import math
import sqlite3
import time
from pathlib import Path
from typing import Any

from notification_delivery_audit_context import attention_contexts_from_records, context_from_json, context_json_from_outbox, safe_dict, safe_float, safe_int, safe_text, safe_timestamp
from notification_delivery_reason import failure_reason_bucket
from mapping_fields import mapping_field as _field, safe_dict_list, safe_mapping_dict
from runtime_paths import current_runtime_paths

TASK_DB_PATH = str(current_runtime_paths().task_db)
VALID_DELIVERY_STATUSES = {"pending", "sent", "failed", "skipped"}
DEFAULT_MAX_DELIVERY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 900

def _connect() -> sqlite3.Connection:
    path = Path(TASK_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_delivery_audit (
            delivery_key TEXT PRIMARY KEY,
            channel_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            dedupe_key TEXT NOT NULL,
            delivery_status TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            first_seen_at REAL NOT NULL,
            last_attempt_at REAL NOT NULL,
            last_success_at REAL,
            last_error TEXT NOT NULL DEFAULT '',
            last_response_id TEXT NOT NULL DEFAULT '',
            context_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(notification_delivery_audit)").fetchall()}
    if "context_json" not in columns:
        conn.execute("ALTER TABLE notification_delivery_audit ADD COLUMN context_json TEXT NOT NULL DEFAULT '{}'")


def reset_notification_delivery_audit_for_tests() -> None:
    path = Path(TASK_DB_PATH)
    if path.exists():
        with _connect() as conn:
            conn.execute("DROP TABLE IF EXISTS notification_delivery_audit")
            _init_schema(conn)


def record_delivery_attempt(
    outbox_entry: Mapping[str, Any],
    *,
    status: str,
    error: str = "",
    response_id: str = "",
    now: float | None = None,
) -> dict[str, Any]:
    outbox_entry = safe_mapping_dict(outbox_entry) or {}
    delivery_key = _required_text(outbox_entry, "delivery_key")
    channel_id = _required_text(outbox_entry, "channel_id")
    message_id = _required_text(outbox_entry, "message_id")
    dedupe_key = _required_text(outbox_entry, "dedupe_key")
    delivery_status = _normalize_status(status)
    context_json = context_json_from_outbox(outbox_entry)
    timestamp = safe_timestamp(now)
    last_error = "" if delivery_status == "sent" else safe_text(error)
    last_response_id = safe_text(response_id)
    last_success_at = timestamp if delivery_status == "sent" else None

    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM notification_delivery_audit WHERE delivery_key = ? OR CAST(delivery_key AS TEXT) = ? OR TRIM(CAST(delivery_key AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32)) = ?",
            (delivery_key, delivery_key, delivery_key),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO notification_delivery_audit (
                    delivery_key, channel_id, message_id, dedupe_key, delivery_status,
                    attempt_count, first_seen_at, last_attempt_at, last_success_at,
                    last_error, last_response_id, context_json
                )
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                """,
                (
                    delivery_key,
                    channel_id,
                    message_id,
                    dedupe_key,
                    delivery_status,
                    timestamp,
                    timestamp,
                    last_success_at,
                    last_error,
                    last_response_id,
                    context_json,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE notification_delivery_audit
                SET channel_id = CASE WHEN LOWER(TRIM(CAST(delivery_status AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32))) = 'sent' THEN channel_id ELSE ? END,
                    message_id = CASE WHEN LOWER(TRIM(CAST(delivery_status AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32))) = 'sent' THEN message_id ELSE ? END,
                    dedupe_key = CASE WHEN LOWER(TRIM(CAST(delivery_status AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32))) = 'sent' THEN dedupe_key ELSE ? END,
                    delivery_status = CASE WHEN LOWER(TRIM(CAST(delivery_status AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32))) = 'sent' THEN delivery_status ELSE ? END,
                    attempt_count = attempt_count + 1,
                    last_attempt_at = ?,
                    last_success_at = COALESCE(?, last_success_at),
                    last_error = CASE WHEN LOWER(TRIM(CAST(delivery_status AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32))) = 'sent' THEN last_error ELSE ? END,
                    last_response_id = CASE WHEN LOWER(TRIM(CAST(delivery_status AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32))) = 'sent' THEN last_response_id ELSE COALESCE(NULLIF(?, ''), last_response_id) END,
                    context_json = CASE WHEN LOWER(TRIM(CAST(delivery_status AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32))) = 'sent' THEN context_json ELSE COALESCE(NULLIF(?, '{}'), context_json) END
                WHERE delivery_key = ? OR CAST(delivery_key AS TEXT) = ? OR TRIM(CAST(delivery_key AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32)) = ?
                """,
                (
                    channel_id,
                    message_id,
                    dedupe_key,
                    delivery_status,
                    timestamp,
                    last_success_at,
                    last_error,
                    last_response_id,
                    context_json,
                    delivery_key, delivery_key, delivery_key,
                ),
            )
        saved = conn.execute(
            "SELECT * FROM notification_delivery_audit WHERE delivery_key = ? OR CAST(delivery_key AS TEXT) = ? OR TRIM(CAST(delivery_key AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32)) = ? ORDER BY CASE WHEN LOWER(TRIM(CAST(delivery_status AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32))) = 'sent' THEN 1 ELSE 0 END DESC",
            (delivery_key, delivery_key, delivery_key),
        ).fetchone()
    return _row_to_record(saved)


def list_delivery_records(limit: int = 100) -> list[dict[str, Any]]:
    requested_limit = 100 if limit is None else safe_int(limit)
    safe_limit = max(1, min(requested_limit, 1000))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM notification_delivery_audit
            ORDER BY last_attempt_at DESC, delivery_key ASC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [_row_to_record(row) for row in rows]


def reconcile_outbox_with_audit(
    outbox_entries: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None,
    *,
    max_attempts: int | None = DEFAULT_MAX_DELIVERY_ATTEMPTS,
    now: float | None = None,
    retry_backoff_seconds: float | None = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> list[dict[str, Any]]:
    entries = safe_dict_list(outbox_entries)
    delivery_keys = [safe_text(_field(entry, "delivery_key")).strip() for entry in entries]
    delivery_keys = [key for key in delivery_keys if key]
    audit_by_key = _records_by_delivery_key(delivery_keys)
    timestamp = safe_timestamp(now)
    safe_backoff_seconds = DEFAULT_RETRY_BACKOFF_SECONDS if retry_backoff_seconds is None else max(0.0, safe_float(retry_backoff_seconds))
    return [
        _reconciled_outbox_entry(
            entry,
            audit_by_key.get(safe_text(_field(entry, "delivery_key")).strip()),
            max_attempts=DEFAULT_MAX_DELIVERY_ATTEMPTS if max_attempts is None else max_attempts,
            now=timestamp,
            retry_backoff_seconds=safe_backoff_seconds,
        )
        for entry in entries
    ]


def get_delivery_audit_summary() -> dict[str, Any]:
    records = list_delivery_records(limit=1000)
    channel_counts: dict[str, int] = {}
    failure_reason_counts: dict[str, int] = {}
    for record in records:
        channel_id = safe_text(_field(record, "channel_id")).strip() or "unknown"
        channel_counts[channel_id] = channel_counts.get(channel_id, 0) + 1
        if safe_text(_field(record, "delivery_status")).strip().lower() == "failed":
            reason = failure_reason_bucket(_field(record, "last_error"))
            failure_reason_counts[reason] = failure_reason_counts.get(reason, 0) + 1
    return {
        "total_count": len(records),
        "sent_count": sum(1 for record in records if safe_text(_field(record, "delivery_status")).strip().lower() == "sent"),
        "failed_count": sum(1 for record in records if safe_text(_field(record, "delivery_status")).strip().lower() == "failed"),
        "pending_count": sum(1 for record in records if safe_text(_field(record, "delivery_status")).strip().lower() == "pending"),
        "retry_exhausted_count": sum(1 for record in records if _retry_exhausted(record)),
        "channel_counts": channel_counts,
        "failure_reason_counts": dict(sorted(failure_reason_counts.items())),
        "attention_contexts": attention_contexts_from_records(records),
    }


def _records_by_delivery_key(delivery_keys: list[str]) -> dict[str, dict[str, Any]]:
    if not delivery_keys:
        return {}
    placeholders = ", ".join("?" for _ in delivery_keys)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM notification_delivery_audit
            WHERE delivery_key IN ({placeholders}) OR CAST(delivery_key AS TEXT) IN ({placeholders}) OR TRIM(CAST(delivery_key AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32)) IN ({placeholders}) ORDER BY CASE WHEN LOWER(TRIM(CAST(delivery_status AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32))) = 'sent' THEN 1 ELSE 0 END, last_attempt_at, attempt_count
            """,
            (*delivery_keys, *delivery_keys, *delivery_keys),
        ).fetchall()
    return {safe_text(row["delivery_key"]).strip(): _row_to_record(row) for row in rows}


def _reconciled_outbox_entry(
    entry: dict[str, Any],
    audit_record: dict[str, Any] | None,
    *,
    max_attempts: int,
    now: float,
    retry_backoff_seconds: float,
) -> dict[str, Any]:
    if not audit_record:
        return {
            **entry,
            "audit_status": "not_seen",
            "audit_attempt_count": 0,
            "already_sent": False,
            "should_send": True,
            "retry_exhausted": False,
            "retry_wait_seconds": 0,
            "next_retry_at": None,
            "next_attempt_count": 1,
            "skip_reason": "",
            "last_error": "",
            "last_response_id": "",
            "last_success_at": None,
            "audit_context": {},
        }
    attempt_count = safe_int(_field(audit_record, "attempt_count"))
    audit_status = safe_text(_field(audit_record, "delivery_status")).strip().lower() or "unknown"
    already_sent = audit_status == "sent"
    retry_exhausted = _retry_exhausted(audit_record, max_attempts=max_attempts)
    next_retry_at = _next_retry_at(
        audit_record,
        retry_exhausted=retry_exhausted,
        retry_backoff_seconds=retry_backoff_seconds,
    )
    retry_wait_seconds = _retry_wait_seconds(next_retry_at, now=now)
    retry_wait = retry_wait_seconds > 0
    return {
        **entry,
        "audit_status": audit_status,
        "audit_attempt_count": attempt_count,
        "already_sent": already_sent,
        "should_send": not already_sent and not retry_exhausted and not retry_wait,
        "retry_exhausted": retry_exhausted,
        "retry_wait_seconds": retry_wait_seconds,
        "next_retry_at": next_retry_at,
        "next_attempt_count": attempt_count + 1,
        "skip_reason": _skip_reason(
            already_sent=already_sent,
            retry_exhausted=retry_exhausted,
            retry_wait=retry_wait,
        ),
        "last_error": safe_text(_field(audit_record, "last_error")),
        "last_response_id": safe_text(_field(audit_record, "last_response_id")).strip(),
        "last_success_at": safe_float(_field(audit_record, "last_success_at")) if _field(audit_record, "last_success_at") is not None else None,
        "audit_context": safe_dict(_field(audit_record, "context")),
    }


def _retry_exhausted(record: dict[str, Any], *, max_attempts: int = DEFAULT_MAX_DELIVERY_ATTEMPTS) -> bool:
    return safe_text(_field(record, "delivery_status")).strip().lower() == "failed" and safe_int(_field(record, "attempt_count")) >= max(1, safe_int(max_attempts))


def _next_retry_at(
    record: dict[str, Any],
    *,
    retry_exhausted: bool,
    retry_backoff_seconds: float,
) -> float | None:
    if safe_text(_field(record, "delivery_status")).strip().lower() != "failed" or retry_exhausted:
        return None
    return safe_float(_field(record, "last_attempt_at")) + retry_backoff_seconds


def _retry_wait_seconds(next_retry_at: float | None, *, now: float) -> int:
    if next_retry_at is None:
        return 0
    return max(0, int(math.ceil(next_retry_at - now)))


def _skip_reason(*, already_sent: bool, retry_exhausted: bool, retry_wait: bool) -> str:
    if already_sent:
        return "already_sent"
    if retry_exhausted:
        return "retry_exhausted"
    if retry_wait:
        return "retry_wait"
    return ""


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = safe_text(_field(payload, key)).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _normalize_status(status: str) -> str:
    value = safe_text(status).strip().lower()
    if value not in VALID_DELIVERY_STATUSES:
        raise ValueError(f"unsupported delivery status: {status}")
    return value


def _row_to_record(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "delivery_key": safe_text(row["delivery_key"]).strip(),
        "channel_id": safe_text(row["channel_id"]).strip(),
        "message_id": safe_text(row["message_id"]).strip(),
        "dedupe_key": safe_text(row["dedupe_key"]).strip(),
        "delivery_status": safe_text(row["delivery_status"]).strip().lower(),
        "attempt_count": safe_int(row["attempt_count"]),
        "first_seen_at": safe_float(row["first_seen_at"]),
        "last_attempt_at": safe_float(row["last_attempt_at"]),
        "last_success_at": safe_float(row["last_success_at"]) if row["last_success_at"] is not None else None,
        "last_error": safe_text(row["last_error"]),
        "last_response_id": safe_text(row["last_response_id"]).strip(),
        "context": context_from_json(row["context_json"]),
    }
__all__ = ["DEFAULT_RETRY_BACKOFF_SECONDS", "get_delivery_audit_summary", "list_delivery_records", "record_delivery_attempt", "reconcile_outbox_with_audit", "reset_notification_delivery_audit_for_tests"]
