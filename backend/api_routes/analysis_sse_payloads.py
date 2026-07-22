"""Payload sanitation helpers for analysis SSE replay events."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from data_trust import sanitize_for_snapshot
from mapping_fields import safe_int, safe_mapping_dict, safe_text


TEXT_FIELDS = (
    "message",
    "phase",
    "level",
    "filename",
    "md_filename",
    "data_filename",
    "pipeline_id",
    "last_pipeline_id",
    "thread_id",
    "name",
    "detail",
    "pipeline_label",
    "node_name",
    "model",
    "status",
    "error",
)
COUNT_FIELDS = (
    "current",
    "total",
    "agent_num",
    "pipeline_current",
    "pipeline_total",
    "pipeline_index",
    "agent_total",
    "agent_offset",
)
STRUCTURED_FIELDS = ("metadata", "data_trust", "audit", "filenames", "reports", "pipeline_sequence")


def malformed_replay_payload(job_id: str) -> dict:
    return {
        "type": "status",
        "level": "warning",
        "message": "略過格式異常的分析任務事件",
        "job_id": job_id,
    }


def sanitize_replay_payload(value: Any, *, job_id: str) -> dict:
    payload = safe_mapping_dict(value)
    if payload is None:
        return malformed_replay_payload(job_id)
    payload_type = replay_payload_type(payload.get("type"))
    if not payload_type:
        return malformed_replay_payload(job_id)

    sanitized = {**payload, "type": payload_type}
    for field in TEXT_FIELDS:
        if field in sanitized:
            sanitized[field] = replay_text_field(sanitized.get(field))
    for field in COUNT_FIELDS:
        if field in sanitized:
            sanitized[field] = replay_count_field(sanitized.get(field))
    if "latency_ms" in sanitized:
        sanitized["latency_ms"] = replay_float_field(sanitized.get("latency_ms"))
    if "retry_count" in sanitized:
        sanitized["retry_count"] = replay_count_field(sanitized.get("retry_count"))
    if "quality_gate_pass" in sanitized:
        sanitized["quality_gate_pass"] = replay_bool_field(sanitized.get("quality_gate_pass"))
    for field in STRUCTURED_FIELDS:
        if field in sanitized:
            sanitized[field] = sanitize_for_snapshot(sanitized.get(field))
    return sanitized


def replay_event_id(value: Any) -> int:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0
    return safe_int(value)


def replay_count_field(value: Any) -> int:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0
    return safe_int(value)


def replay_float_field(value: Any) -> float:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0.0
    try:
        number = float(0.0 if value is None else value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def replay_bool_field(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return False
    if isinstance(value, Mapping) or isinstance(value, (list, tuple, set, frozenset)):
        return False
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"", "0", "false", "no", "off", "none", "null"}:
            return False
        return False
    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return False
        if not math.isfinite(number):
            return False
        return number == 1
    return False


def replay_text_field(value: Any) -> str:
    if isinstance(value, Mapping) or isinstance(value, (list, tuple, set, frozenset)):
        return ""
    return safe_text(value).strip()


def replay_payload_type(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return safe_text(value).strip()
