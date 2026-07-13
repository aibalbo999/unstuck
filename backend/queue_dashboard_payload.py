"""Queue dashboard payload shaping helpers."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_mapping_items, safe_text
from notification_delivery_audit_context import safe_float, safe_int


def normalize_ops_queue_payload(queue: Any) -> dict[str, Any]:
    source = _payload_dict(queue)
    backend = safe_text(source.get("backend")).strip() or "unknown"
    payload: dict[str, Any] = {
        "backend": backend,
        "available": _safe_bool(source.get("available")),
        "queue_name": safe_text(source.get("queue_name")).strip() or backend,
        "depth": _safe_int(source.get("depth")),
        "queues": {
            safe_text(name).strip() or "unknown": _named_queue_detail(details)
            for name, details in safe_mapping_items(_payload_dict(source.get("queues")))
        },
    }
    _copy_queue_supplemental_fields(payload, source)
    return payload


def _copy_queue_supplemental_fields(payload: dict[str, Any], source: dict[str, Any]) -> None:
    if "registries" in source:
        payload["registries"] = _registry_counts(source.get("registries"))
    if "active_tasks" in source:
        payload["active_tasks"] = _safe_int(source.get("active_tasks"))
    if "oldest_queued_seconds" in source:
        payload["oldest_queued_seconds"] = _safe_finite_float(source.get("oldest_queued_seconds"))
    if "job_timeout_seconds" in source:
        payload["job_timeout_seconds"] = _safe_int(source.get("job_timeout_seconds"))
    if "error" in source:
        payload["error"] = safe_text(source.get("error")).strip()
    for key, value in source.items():
        safe_key = safe_text(key).strip()
        if safe_key and safe_key not in payload and safe_key not in {"backend", "available", "queue_name", "depth", "queues"}:
            payload[safe_key] = safe_text(value)


def _named_queue_detail(details: Any) -> dict[str, Any]:
    detail = _payload_dict(details)
    if not detail:
        return {}
    payload = {safe_text(key).strip() or "unknown": safe_text(value) for key, value in detail.items()}
    if "depth" in detail:
        payload["depth"] = _safe_int(detail.get("depth"))
    if "registries" in detail:
        payload["registries"] = _registry_counts(detail.get("registries"))
    return payload


def _registry_counts(registries: Any) -> dict[str, int]:
    return {
        safe_text(registry).strip() or "unknown": _safe_int(count)
        for registry, count in safe_mapping_items(_payload_dict(registries))
    }


def _payload_dict(value: Any) -> dict[Any, Any]:
    return safe_mapping_dict(value) or {}


def _safe_finite_float(value: Any) -> float:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0.0
    number = safe_float(value)
    return 0.0 if number != number or number in {float("inf"), float("-inf")} else number


def _safe_int(value: Any) -> int:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0
    return safe_int(value)


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = safe_text(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "available"}:
        return True
    if normalized in {"", "0", "false", "no", "n", "off", "unavailable"}:
        return False
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return False
