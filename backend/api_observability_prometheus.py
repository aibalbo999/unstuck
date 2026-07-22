"""Prometheus label and metric value helpers for observability payloads."""

from __future__ import annotations

import re
from typing import Any

from mapping_fields import safe_text
from notification_delivery_audit_context import safe_float, safe_int


def _labels(**labels: Any) -> str:
    rendered = []
    for key, value in labels.items():
        safe_key = re.sub(r"[^a-zA-Z0-9_]", "_", safe_text(key).strip() or "label")
        safe_value = (safe_text(value).strip() or "unknown").replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
        rendered.append(f'{safe_key}="{safe_value}"')
    return "{" + ",".join(rendered) + "}"


def _metric_number(value: Any) -> float:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0.0
    number = safe_float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        return 0.0
    return number


def _metric_bool(value: Any) -> bool:
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


def _metric_int(value: Any) -> int:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0
    return safe_int(value)
