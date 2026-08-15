"""Explicit maintenance actions for stale task-queue failures."""

from __future__ import annotations

import time
from typing import Any

from queue_observability import FAILED_JOB_STALE_AFTER_SECONDS, _job_age_seconds


def cleanup_stale_failed_jobs(
    task_queue: Any,
    *,
    stale_after_seconds: int = FAILED_JOB_STALE_AFTER_SECONDS,
    write: bool = False,
    now: float | None = None,
) -> dict[str, Any]:
    """Plan or remove failed RQ jobs whose age is explicitly classifiable as stale."""
    threshold = max(1, int(stale_after_seconds or FAILED_JOB_STALE_AFTER_SECONDS))
    current_time = time.time() if now is None else float(now)
    queues = _queue_map(task_queue)
    result: dict[str, Any] = {
        "dry_run": not write,
        "stale_after_seconds": threshold,
        "queues_scanned": len(queues),
        "failed_jobs_scanned": 0,
        "stale_failed_jobs": 0,
        "unclassified_jobs": 0,
        "deleted_jobs": 0,
        "errors": 0,
        "queues": {},
    }
    for queue_name, queue in queues.items():
        queue_result = _cleanup_queue(
            queue,
            stale_after_seconds=threshold,
            write=write,
            now=current_time,
        )
        result["queues"][queue_name] = queue_result
        for key in ("failed_jobs_scanned", "stale_failed_jobs", "unclassified_jobs", "deleted_jobs", "errors"):
            result[key] += queue_result[key]
    return result


def _cleanup_queue(queue: Any, *, stale_after_seconds: int, write: bool, now: float) -> dict[str, int]:
    result = {
        "failed_jobs_scanned": 0,
        "stale_failed_jobs": 0,
        "unclassified_jobs": 0,
        "deleted_jobs": 0,
        "errors": 0,
    }
    registry = getattr(queue, "failed_job_registry", None)
    get_job_ids = getattr(registry, "get_job_ids", None)
    fetch_job = getattr(queue, "fetch_job", None)
    if not callable(get_job_ids) or not callable(fetch_job):
        return result
    try:
        job_ids = list(get_job_ids())
    except Exception:
        result["errors"] += 1
        return result
    for job_id in job_ids:
        result["failed_jobs_scanned"] += 1
        try:
            job = fetch_job(job_id)
            timestamp = getattr(job, "ended_at", None) or getattr(job, "created_at", None)
            age = _job_age_seconds(timestamp, now)
        except Exception:
            result["unclassified_jobs"] += 1
            continue
        if age is None:
            result["unclassified_jobs"] += 1
            continue
        if age <= stale_after_seconds:
            continue
        result["stale_failed_jobs"] += 1
        if not write:
            continue
        try:
            registry.remove(job, delete_job=True)
            result["deleted_jobs"] += 1
        except Exception:
            result["errors"] += 1
    return result


def _queue_map(task_queue: Any) -> dict[str, Any]:
    queues = getattr(task_queue, "queues", None)
    if isinstance(queues, dict) and queues:
        return {str(name): queue for name, queue in queues.items() if queue is not None}
    queue = getattr(task_queue, "queue", None)
    if queue is None:
        return {}
    return {str(getattr(queue, "name", "default")): queue}


__all__ = ["cleanup_stale_failed_jobs"]
