"""Payload helpers for analysis routes."""

from __future__ import annotations

import math
from typing import Any

from mapping_fields import safe_int, safe_mapping_dict, safe_sequence_items, safe_text


def _serialize_job(deps: Any, job: dict) -> dict:
    if deps.serialize_analysis_job is not None:
        return deps.serialize_analysis_job(job)
    return dict(job)


def _serialize_create_result(deps: Any, created: dict, pipeline_id: str) -> dict:
    serialized = safe_mapping_dict(_serialize_job(deps, created))
    if serialized is None:
        return _safe_json_response_mapping({"pipeline_id": pipeline_id})
    if serialized.get("report_path") is None:
        report_path = _safe_optional_response_text(created.get("report_path"))
        if report_path:
            serialized["report_path"] = report_path
    payload = _safe_json_response_mapping(serialized)
    if not safe_text(payload.get("pipeline_id")).strip():
        payload["pipeline_id"] = pipeline_id
    return payload


def _legacy_create_and_enqueue_via_deps(deps: Any, ticker: str, pipeline_id: str) -> dict:
    job_id = safe_text(deps.create_job(ticker, pipeline_id)).strip()
    if not job_id:
        return _serialize_create_result(deps, {"pipeline_id": pipeline_id}, pipeline_id)
    try:
        deps.get_analysis_task_queue().enqueue(
            f"analysis:{job_id}",
            deps.run_stock_analysis_job,
            job_id,
            ticker,
            pipeline_id,
        )
    except Exception as exc:
        detail = safe_text(exc).strip()
        message = f"分析任務送入佇列失敗：{detail}" if detail else "分析任務送入佇列失敗"
        deps.update_job(job_id, "error", error=message)
        deps.append_event(job_id, {"type": "error", "message": message})
    return _serialize_create_result(deps, safe_mapping_dict(deps.get_job(job_id)) or {"pipeline_id": pipeline_id}, pipeline_id)


def _safe_bool_result(value: Any) -> bool:
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return False


def _safe_api_key_ready(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return False
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"", "0", "false", "no", "off", "none", "null"}:
            return False
        return False
    if isinstance(value, int):
        try:
            return value == 1
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return False
    return False


def _safe_pipeline_id(value: Any) -> str:
    return safe_text(value).strip() or "v1"


def _safe_optional_response_text(value: Any) -> str | None:
    text = safe_text(value).strip()
    return text or None


def _safe_json_response_mapping(payload: dict) -> dict:
    return {
        key_text: safe_child
        for key, value in payload.items()
        if (key_text := safe_text(key).strip())
        for safe_child in [_safe_json_response_value(value)]
    }


def _safe_json_response_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    if isinstance(value, (list, tuple)):
        return [_safe_json_response_value(item) for item in safe_sequence_items(value)]
    value_map = safe_mapping_dict(value)
    if value_map is not None:
        return _safe_json_response_mapping(value_map)
    text = safe_text(value)
    return text if text else None


def _safe_intro_count(value: Any) -> int:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0
    return safe_int(value)
