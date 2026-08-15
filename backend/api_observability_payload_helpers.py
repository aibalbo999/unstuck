"""Shape-safe payload helpers for observability dashboards."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict
from notification_delivery_audit_context import safe_int


def _stuck_jobs_payload(value: Any) -> dict:
    payload = _payload_dict(value)
    if "count" in payload:
        payload["count"] = _strict_count(payload.get("count"))
    return payload


def _stuck_job_count(value: Any) -> int:
    return _strict_count(_payload_dict(value).get("count"))


def _strict_count(value: Any) -> int:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0
    return safe_int(value)


def _payload_dict(value: Any) -> dict[Any, Any]:
    return safe_mapping_dict(value) or {}
