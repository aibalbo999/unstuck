"""Queue state inspection helpers for analysis jobs."""

from __future__ import annotations

from typing import Any

from job_store import sanitize_error_message
from mapping_fields import safe_text


ACTIVE_RQ_JOB_STATUSES = {"queued", "started", "deferred", "scheduled"}
UNREADABLE_ATTR = object()


def task_queue_has_task(task_queue: Any, task_id: str) -> bool | None:
    """Return None when the queue implementation cannot inspect existing jobs."""
    safe_task_id = safe_text(task_id).strip()
    queues = []
    queue_map = _safe_getattr(task_queue, "queues")
    if queue_map is UNREADABLE_ATTR:
        return None
    if isinstance(queue_map, dict):
        queues.extend(queue for queue in queue_map.values() if queue is not None)
    queue = _safe_getattr(task_queue, "queue")
    if queue is UNREADABLE_ATTR:
        return None
    if queue is not None and all(existing is not queue for existing in queues):
        queues.append(queue)
    fetch_job = _safe_getattr(task_queue, "fetch_job")
    if fetch_job is UNREADABLE_ATTR:
        return None
    if not queues and fetch_job is not None:
        queues.append(task_queue)

    inspected = False
    for queue in queues:
        fetch_job = _safe_getattr(queue, "fetch_job")
        if fetch_job is UNREADABLE_ATTR:
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
    if get_status is UNREADABLE_ATTR:
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
        if status is UNREADABLE_ATTR:
            return None
    if status is None:
        return True
    return safe_text(status).strip().lower() in ACTIVE_RQ_JOB_STATUSES


def _safe_getattr(value: Any, name: str) -> Any:
    try:
        return getattr(value, name, None)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return UNREADABLE_ATTR


def _looks_like_duplicate_queue_job(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    message = safe_text(exc).lower()
    return "duplicate" in name or "already" in message or "exists" in message


def _queue_exception_message(prefix: str, exc: Exception) -> str:
    detail = safe_text(exc).strip()
    raw_message = f"{prefix}：{detail}" if detail else prefix
    return sanitize_error_message(raw_message) or prefix


__all__ = [
    "task_queue_has_task",
]
