"""Service layer for analysis job lifecycle APIs."""

from __future__ import annotations

import math
import re
import time
import uuid
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from typing import Any, Callable

from job_store import (
    append_event,
    create_or_attach_active_job,
    get_job,
    list_node_telemetry,
    request_job_cancel,
    sanitize_error_message,
    update_job,
)
from mapping_fields import safe_mapping_dict, safe_text


_STATUS_MAP = {
    "queued": "queued",
    "running": "running",
    "waiting_retry": "running",
    "done": "completed",
    "error": "failed",
    "cancelled": "cancelled",
}
RQ_ABANDONED_JOB_REASON = "Redis/RQ 已無執行中或等待中的對應任務，判定前一次 Worker 已中斷；請重新送出分析或重跑。"
ACTIVE_RQ_JOB_STATUSES = {"queued", "started", "deferred", "scheduled"}
_UNSAFE_PERCENT_ENCODED_URL_TOKENS = ("%00", "%09", "%0a", "%0d", "%23", "%2f", "%3f", "%5c", "%7f")


def create_or_attach_analysis_job(
    *,
    ticker: str,
    pipeline_id: str,
    force: bool = False,
    resume: bool = True,
    task_queue: Any,
    run_stock_analysis_job: Callable[[str, str, str], str],
) -> dict:
    normalized_ticker = safe_text(ticker).strip().upper()
    normalized_pipeline = safe_text(pipeline_id).strip() or "v1"
    if not normalized_ticker:
        return serialize_analysis_job({"pipeline_id": normalized_pipeline})
    force_flag = _safe_bool_flag(force)
    resume_flag = _safe_bool_flag(resume, default=True)
    job_id = build_analysis_job_id(normalized_ticker, normalized_pipeline, force=force_flag)
    result = safe_mapping_dict(
        create_or_attach_active_job(
            normalized_ticker,
            normalized_pipeline,
            force=force_flag,
            resume=resume_flag,
            job_id=job_id,
        )
    ) or {}
    job = safe_mapping_dict(result.get("job"))
    job_id = safe_text(job.get("job_id")).strip() if job else ""
    if not job or not job_id:
        return serialize_analysis_job(job or {})

    task_id = analysis_task_id(job_id)
    created = result.get("created")
    if created is False:
        if safe_text(job.get("status")) == "queued" and task_queue_has_task(task_queue, task_id) is False:
            try:
                task_queue.enqueue(
                    task_id,
                    run_stock_analysis_job,
                    job_id,
                    normalized_ticker,
                    normalized_pipeline,
                )
            except Exception as exc:
                message = _queue_exception_message("分析任務重新排入佇列失敗", exc)
                update_job(job_id, "error", error=message)
                append_event(job_id, {"type": "error", "message": message, "pipeline_id": normalized_pipeline})
                job = safe_mapping_dict(get_job(job_id)) or job
            else:
                append_event(
                    job_id,
                    {
                        "type": "status",
                        "phase": "queue_recovered",
                        "level": "warning",
                        "message": "佇列中已找不到此分析任務，已重新排入分析佇列。",
                        "pipeline_id": normalized_pipeline,
                    },
                )
                job = safe_mapping_dict(get_job(job_id)) or job
        return serialize_analysis_job(job)
    if created is not True:
        return serialize_analysis_job(job)

    try:
        if task_queue_has_task(task_queue, task_id) is not True:
            _enqueue_analysis_job(
                task_queue,
                task_id,
                run_stock_analysis_job,
                job_id,
                normalized_ticker,
                normalized_pipeline,
                force_refresh=force_flag,
            )
    except Exception as exc:
        if _looks_like_duplicate_queue_job(exc):
            append_event(
                job_id,
                {
                    "type": "status",
                    "phase": "queue_attach",
                    "message": "佇列中已有相同任務，已附加到既有 RQ job。",
                    "pipeline_id": normalized_pipeline,
                },
            )
        else:
            message = _queue_exception_message("分析任務送入佇列失敗", exc)
            update_job(job_id, "error", error=message)
            append_event(job_id, {"type": "error", "message": message, "pipeline_id": normalized_pipeline})
            job = safe_mapping_dict(get_job(job_id)) or job
    else:
        job = safe_mapping_dict(get_job(job_id)) or job
    return serialize_analysis_job(job)


def cancel_analysis_job(job_id: str, *, task_queue: Any | None = None) -> dict | None:
    safe_job_id = safe_text(job_id).strip()
    job = safe_mapping_dict(get_job(safe_job_id))
    if not job:
        return None

    if safe_text(job.get("status")) == "queued" and task_queue is not None:
        cancel = _safe_getattr(task_queue, "cancel")
        if callable(cancel):
            try:
                cancel(f"analysis:{safe_job_id}")
            except Exception:
                pass
    request_job_cancel(safe_job_id, "使用者要求取消分析任務。")
    updated_job = safe_mapping_dict(get_job(safe_job_id)) or job
    return serialize_analysis_job(updated_job)


def serialize_analysis_job(job: dict) -> dict:
    job = safe_mapping_dict(job) or {}
    job_id = safe_text(job.get("job_id")).strip()
    job_url_id = _safe_public_url_segment(job_id)
    filename = _safe_report_filename(job.get("filename"))
    pipeline_id = safe_text(job.get("pipeline_id")).strip() or "v1"
    ticker = safe_text(job.get("ticker")).strip()
    status = safe_text(job.get("status")).strip()
    status_key = status.lower()
    return {
        "job_id": job_id,
        "ticker": ticker,
        "pipeline_id": pipeline_id,
        "status": _STATUS_MAP.get(status_key, status),
        "created_at": _iso_timestamp(job.get("created_at")),
        "updated_at": _iso_timestamp(job.get("updated_at")),
        "started_at": _iso_timestamp(job.get("started_at")),
        "finished_at": _iso_timestamp(job.get("finished_at")),
        "report_path": f"/api/report/{filename}" if filename else None,
        "error": sanitize_error_message(job.get("error")),
        "events_url": f"/api/analysis-jobs/{job_url_id}/events" if job_url_id else None,
        "status_url": f"/api/analysis-jobs/{job_url_id}" if job_url_id else None,
    }


def _safe_report_filename(value: Any) -> str:
    return _safe_public_url_segment(value)


def _safe_public_url_segment(value: Any) -> str:
    segment = safe_text(value).strip()
    if not segment or segment in {".", ".."}:
        return ""
    if any(character.isspace() for character in segment):
        return ""
    if any(ord(character) < 32 or ord(character) == 127 for character in segment):
        return ""
    if "/" in segment or "\\" in segment:
        return ""
    lowered = segment.lower()
    if "?" in segment or "#" in segment:
        return ""
    if "%25" in lowered:
        return ""
    if any(token in lowered for token in _UNSAFE_PERCENT_ENCODED_URL_TOKENS):
        return ""
    return segment


def serialize_node_telemetry(job_id: str) -> dict:
    safe_job_id = safe_text(job_id).strip()
    rows = _safe_telemetry_rows(list_node_telemetry(safe_job_id))
    return {
        "job_id": safe_job_id,
        "telemetry": [_serialize_telemetry_row(row) for row in rows],
    }


def build_analysis_job_id(ticker: str, pipeline_id: str, *, force: bool = False) -> str:
    ticker_text = safe_text(ticker).strip()
    pipeline_text = safe_text(pipeline_id).strip()
    ticker_slug = _slug(ticker_text.replace(".TW", "tw"))
    pipeline_slug = _slug(pipeline_text)
    timestamp_ms = int(time.time() * 1000)
    force_flag = _safe_bool_flag(force)
    suffix = uuid.uuid4().hex[:8] if force_flag else uuid.uuid5(uuid.NAMESPACE_URL, f"{ticker_text}:{pipeline_text}:{timestamp_ms}").hex[:8]
    return f"analysis-{ticker_slug}-{pipeline_slug}-{timestamp_ms}-{suffix}"


def analysis_task_id(job_id: str) -> str:
    return f"analysis:{_safe_public_url_segment(job_id)}"


def _safe_bool_flag(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return default
    if isinstance(value, Mapping) or isinstance(value, (list, tuple, set, frozenset)):
        return default
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"", "0", "false", "no", "off", "none", "null"}:
            return False
        return default
    if isinstance(value, complex):
        return default
    if isinstance(value, Decimal):
        try:
            if not value.is_finite():
                return default
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
        if value == 1:
            return True
        if value == 0:
            return False
        return default
    if isinstance(value, Fraction):
        if value == 1:
            return True
        if value == 0:
            return False
        return default
    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
        if not math.isfinite(number):
            return default
        if number == 1:
            return True
        if number == 0:
            return False
        return default
    return default


def _enqueue_analysis_job(
    task_queue: Any,
    task_id: str,
    run_stock_analysis_job: Callable[[str, str, str], str],
    job_id: str,
    ticker: str,
    pipeline_id: str,
    *,
    force_refresh: bool = False,
) -> None:
    args = [task_id, run_stock_analysis_job, job_id, ticker, pipeline_id]
    if force_refresh:
        args.append(True)
    task_queue.enqueue(*args)


def _serialize_telemetry_row(row: dict) -> dict:
    serialized = safe_mapping_dict(row) or {}
    for key in ("job_id", "ticker", "pipeline_id", "node_name", "model", "status"):
        if key in serialized:
            serialized[key] = safe_text(serialized.get(key)).strip()
    serialized["started_at"] = _iso_timestamp(serialized.get("started_at"))
    serialized["finished_at"] = _iso_timestamp(serialized.get("finished_at"))
    for key in ("id", "latency_ms", "input_tokens", "output_tokens"):
        if key in serialized:
            serialized[key] = _safe_optional_int(serialized.get(key))
    if "retry_count" in serialized:
        serialized["retry_count"] = _safe_int(serialized.get("retry_count"))
    for key in ("cache_hit", "quality_gate_pass"):
        if key in serialized:
            serialized[key] = _safe_bool_field(serialized.get(key))
    serialized["error"] = sanitize_error_message(serialized.get("error"))
    return serialized


def _safe_telemetry_rows(rows: Any) -> tuple[Any, ...]:
    if rows is None or isinstance(rows, (str, bytes, bytearray, memoryview, Mapping)):
        return ()
    if not isinstance(rows, Iterable):
        return ()
    try:
        iterator = iter(rows)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return ()
    safe_rows = []
    while True:
        try:
            safe_rows.append(next(iterator))
        except StopIteration:
            break
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            break
    return tuple(safe_rows)


def _safe_int(value: Any, *, default: int = 0) -> int:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return default
    if isinstance(value, int):
        if value < 0:
            return default
        return value
    if isinstance(value, Fraction):
        if value.denominator != 1:
            return default
        if value < 0:
            return default
        try:
            return int(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
    if isinstance(value, Decimal):
        try:
            if not value.is_finite():
                return default
            integral = value.to_integral_value()
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
        if value != integral:
            return default
        if integral < 0:
            return default
        try:
            return int(integral)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer() or value < 0:
            return default
        try:
            return int(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
    if isinstance(value, str):
        try:
            integer = int(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return default
        if integer < 0:
            return default
        return integer
    return default


def _safe_optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, (bool, bytes, bytearray, memoryview)):
        return None
    if isinstance(value, int):
        if value < 0:
            return None
        return value
    if isinstance(value, Fraction):
        if value.denominator != 1:
            return None
        if value < 0:
            return None
        try:
            return int(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return None
    if isinstance(value, Decimal):
        try:
            if not value.is_finite():
                return None
            integral = value.to_integral_value()
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return None
        if value != integral:
            return None
        if integral < 0:
            return None
        try:
            return int(integral)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return None
    if not isinstance(value, (float, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None
    if not math.isfinite(number) or not number.is_integer() or number < 0:
        return None
    try:
        return int(number)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None


def _safe_bool_field(value: Any) -> bool:
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
    if isinstance(value, Decimal):
        try:
            if not value.is_finite():
                return False
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return False
        if value == 1:
            return True
        if value == 0:
            return False
        return False
    if isinstance(value, Fraction):
        if value == 1:
            return True
        if value == 0:
            return False
        return False
    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return False
        if not math.isfinite(number):
            return False
        if number == 1:
            return True
        if number == 0:
            return False
        return False
    return False


def _iso_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    if not isinstance(value, (int, float, str, Decimal, Fraction)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None
    if not math.isfinite(number):
        return None
    try:
        return datetime.fromtimestamp(number, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return None


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug or "job"


def task_queue_has_task(task_queue: Any, task_id: str) -> bool | None:
    """Return None when the queue implementation cannot inspect existing jobs."""
    safe_task_id = safe_text(task_id).strip()
    queues = []
    queue_map = _safe_getattr(task_queue, "queues")
    if queue_map is _UNREADABLE_ATTR:
        return None
    if isinstance(queue_map, dict):
        queues.extend(queue for queue in queue_map.values() if queue is not None)
    queue = _safe_getattr(task_queue, "queue")
    if queue is _UNREADABLE_ATTR:
        return None
    if queue is not None and all(existing is not queue for existing in queues):
        queues.append(queue)
    fetch_job = _safe_getattr(task_queue, "fetch_job")
    if fetch_job is _UNREADABLE_ATTR:
        return None
    if not queues and fetch_job is not None:
        queues.append(task_queue)

    inspected = False
    for queue in queues:
        fetch_job = _safe_getattr(queue, "fetch_job")
        if fetch_job is _UNREADABLE_ATTR:
            return None
        if not callable(fetch_job):
            continue
        inspected = True
        try:
            job = fetch_job(safe_task_id)
        except Exception:
            return None
        if job is not None:
            active = _rq_job_is_active(job)
            if active is None:
                return None
            if active:
                return True
    return False if inspected else None


def _rq_job_is_active(job: Any) -> bool | None:
    get_status = _safe_getattr(job, "get_status")
    if get_status is _UNREADABLE_ATTR:
        return None
    if callable(get_status):
        try:
            status = get_status(refresh=True)
        except TypeError:
            try:
                status = get_status()
            except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
                return None
        except (ValueError, ArithmeticError, RuntimeError, AttributeError):
            return None
    else:
        status = _safe_getattr(job, "status")
        if status is _UNREADABLE_ATTR:
            return None
    if status is None:
        return True
    return safe_text(status).strip().lower() in ACTIVE_RQ_JOB_STATUSES


_UNREADABLE_ATTR = object()


def _safe_getattr(value: Any, name: str) -> Any:
    try:
        return getattr(value, name, None)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return _UNREADABLE_ATTR


def _looks_like_duplicate_queue_job(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    message = safe_text(exc).lower()
    return "duplicate" in name or "already" in message or "exists" in message


def _queue_exception_message(prefix: str, exc: Exception) -> str:
    detail = safe_text(exc).strip()
    raw_message = f"{prefix}：{detail}" if detail else prefix
    return sanitize_error_message(raw_message) or prefix
