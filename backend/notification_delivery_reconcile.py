"""Retry and sender preflight helpers for notification delivery audit rows."""

from __future__ import annotations

import math
from typing import Any

from mapping_fields import mapping_field as _field
from notification_delivery_audit_context import safe_dict, safe_float, safe_int, safe_text


def reconciled_outbox_entry(
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
    exhausted = retry_exhausted(audit_record, max_attempts=max_attempts)
    retry_at = next_retry_at(
        audit_record,
        retry_exhausted=exhausted,
        retry_backoff_seconds=retry_backoff_seconds,
    )
    wait_seconds = retry_wait_seconds(retry_at, now=now)
    retry_wait = wait_seconds > 0
    return {
        **entry,
        "audit_status": audit_status,
        "audit_attempt_count": attempt_count,
        "already_sent": already_sent,
        "should_send": not already_sent and not exhausted and not retry_wait,
        "retry_exhausted": exhausted,
        "retry_wait_seconds": wait_seconds,
        "next_retry_at": retry_at,
        "next_attempt_count": attempt_count + 1,
        "skip_reason": skip_reason(
            already_sent=already_sent,
            retry_exhausted=exhausted,
            retry_wait=retry_wait,
        ),
        "last_error": safe_text(_field(audit_record, "last_error")),
        "last_response_id": safe_text(_field(audit_record, "last_response_id")).strip(),
        "last_success_at": safe_float(_field(audit_record, "last_success_at")) if _field(audit_record, "last_success_at") is not None else None,
        "audit_context": safe_dict(_field(audit_record, "context")),
    }


def retry_exhausted(record: dict[str, Any], *, max_attempts: int) -> bool:
    return safe_text(_field(record, "delivery_status")).strip().lower() == "failed" and safe_int(_field(record, "attempt_count")) >= max(1, safe_int(max_attempts))


def next_retry_at(
    record: dict[str, Any],
    *,
    retry_exhausted: bool,
    retry_backoff_seconds: float,
) -> float | None:
    if safe_text(_field(record, "delivery_status")).strip().lower() != "failed" or retry_exhausted:
        return None
    return safe_float(_field(record, "last_attempt_at")) + retry_backoff_seconds


def retry_wait_seconds(next_retry_at: float | None, *, now: float) -> int:
    if next_retry_at is None:
        return 0
    return max(0, int(math.ceil(next_retry_at - now)))


def skip_reason(*, already_sent: bool, retry_exhausted: bool, retry_wait: bool) -> str:
    if already_sent:
        return "already_sent"
    if retry_exhausted:
        return "retry_exhausted"
    if retry_wait:
        return "retry_wait"
    return ""
