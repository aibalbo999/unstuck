"""Queue runtime observability helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any

from security_sanitizer import sanitize_error_message

FAILED_JOB_STALE_AFTER_SECONDS = 7 * 24 * 60 * 60


def snapshot_task_queue(task_queue: Any) -> dict:
    """Return a best-effort, side-effect-light queue health snapshot."""
    if task_queue is None:
        return {
            "backend": "unknown",
            "available": False,
            "queue_name": None,
            "depth": None,
            "registries": {},
            "error": "task queue is not configured",
        }

    queue = getattr(task_queue, "queue", None)
    redis_client = getattr(task_queue, "redis", None)
    if redis_client is not None or _looks_like_rq_queue(queue):
        return _snapshot_rq_queue(task_queue, queue, redis_client)
    return _snapshot_local_queue(task_queue)


def _snapshot_rq_queue(task_queue: Any, queue: Any, redis_client: Any) -> dict:
    queues = dict(getattr(task_queue, "queues", {}) or {})
    if queues:
        queue_details = {
            name: _rq_queue_detail(item, redis_client)
            for name, item in queues.items()
        }
        depth_values = [value["depth"] for value in queue_details.values() if value["depth"] is not None]
        registries = _sum_registries([value["registries"] for value in queue_details.values()])
        queue_name = ",".join(queues)
        payload = {
            "backend": "rq",
            "available": True,
            "queue_name": queue_name,
            "depth": sum(depth_values) if depth_values else None,
            "registries": registries,
            "queues": queue_details,
        }
        payload.update(_aggregate_failed_registry_stats(queue_details, registries.get("failed", 0)))
    else:
        registries = _rq_registry_counts(queue)
        payload = {
            "backend": "rq",
            "available": True,
            "queue_name": getattr(queue, "name", None),
            "depth": _queue_depth(queue),
            "registries": registries,
        }
        payload.update(_failed_registry_stats(queue, redis_client, registries.get("failed", 0)))
    try:
        ping = getattr(redis_client, "ping", None)
        if callable(ping):
            ping()
    except Exception as exc:
        payload["available"] = False
        payload["error"] = sanitize_error_message(exc)
    oldest_age = _oldest_queued_age_seconds(queue)
    if oldest_age is not None:
        payload["oldest_queued_seconds"] = oldest_age
    timeout = getattr(task_queue, "timeout", None)
    if timeout is not None:
        payload["job_timeout_seconds"] = timeout
    return payload


def _rq_queue_detail(queue: Any, redis_client: Any) -> dict:
    registries = _rq_registry_counts(queue)
    detail = {"depth": _queue_depth(queue), "registries": registries}
    detail.update(_failed_registry_stats(queue, redis_client, registries.get("failed", 0)))
    return detail


def _aggregate_failed_registry_stats(queue_details: dict, failed_count: int) -> dict:
    stats = [detail for detail in queue_details.values() if "failed_recent" in detail]
    if not stats:
        return {}
    recent = sum(int(detail.get("failed_recent") or 0) for detail in stats)
    stale = sum(int(detail.get("failed_stale") or 0) for detail in stats)
    return {"failed_recent": recent + max(0, int(failed_count) - recent - stale), "failed_stale": stale}


def _failed_registry_stats(queue: Any, redis_client: Any, failed_count: int) -> dict:
    if failed_count <= 0:
        return {}
    registry = getattr(queue, "failed_job_registry", None)
    connection = getattr(queue, "connection", None) or redis_client
    zrange = getattr(connection, "zrange", None)
    key = getattr(registry, "key", None)
    if not callable(zrange) or not key:
        return {"failed_recent": failed_count}
    try:
        job_ids = zrange(key, 0, -1)
    except Exception:
        return {"failed_recent": failed_count}
    fetch_job = getattr(queue, "fetch_job", None)
    if not callable(fetch_job):
        return {"failed_recent": failed_count}
    recent = 0
    stale = 0
    now = time.time()
    for job_id in job_ids:
        try:
            if isinstance(job_id, (bytes, bytearray)):
                job_id = job_id.decode("utf-8", "replace")
            job = fetch_job(job_id)
            timestamp = getattr(job, "ended_at", None) or getattr(job, "created_at", None)
            age = _job_age_seconds(timestamp, now)
        except Exception:
            recent += 1
            continue
        if age is None:
            recent += 1
            continue
        if age > FAILED_JOB_STALE_AFTER_SECONDS:
            stale += 1
        else:
            recent += 1
    recent += max(0, int(failed_count) - recent - stale)
    return {"failed_recent": recent, "failed_stale": stale}


def _job_age_seconds(timestamp: Any, now: float) -> float | None:
    if timestamp is None:
        return None
    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return max(0.0, now - timestamp.timestamp())
    try:
        return max(0.0, now - float(timestamp))
    except (TypeError, ValueError, OverflowError):
        return None


def _sum_registries(registry_counts: list[dict]) -> dict:
    keys = ("started", "deferred", "failed", "scheduled")
    return {
        key: sum(int(item.get(key) or 0) for item in registry_counts)
        for key in keys
    }


def _snapshot_local_queue(task_queue: Any) -> dict:
    queue = getattr(task_queue, "queue", None)
    qsize = getattr(queue, "qsize", None)
    active_tasks = getattr(task_queue, "active_tasks", None)
    return {
        "backend": "local",
        "available": True,
        "queue_name": None,
        "depth": qsize() if callable(qsize) else None,
        "active_tasks": len(active_tasks or []),
        "registries": {},
    }


def _looks_like_rq_queue(queue: Any) -> bool:
    if queue is None:
        return False
    return hasattr(queue, "enqueue_call") or hasattr(queue, "started_job_registry") or hasattr(queue, "failed_job_registry")


def _queue_depth(queue: Any) -> int | None:
    if queue is None:
        return None
    count = getattr(queue, "count", None)
    if callable(count):
        try:
            return int(count())
        except Exception:
            return None
    if count is not None:
        try:
            return int(count)
        except (TypeError, ValueError):
            return None
    try:
        return len(queue)
    except Exception:
        return None


def _rq_registry_counts(queue: Any) -> dict:
    if queue is None:
        return {}
    return {
        "started": _registry_count(getattr(queue, "started_job_registry", None)),
        "deferred": _registry_count(getattr(queue, "deferred_job_registry", None)),
        "failed": _registry_count(getattr(queue, "failed_job_registry", None)),
        "scheduled": _registry_count(getattr(queue, "scheduled_job_registry", None)),
    }


def _registry_count(registry: Any) -> int:
    if registry is None:
        return 0
    count = getattr(registry, "count", None)
    if callable(count):
        try:
            return int(count())
        except Exception:
            return 0
    if count is not None:
        try:
            return int(count)
        except (TypeError, ValueError):
            return 0
    get_job_ids = getattr(registry, "get_job_ids", None)
    if callable(get_job_ids):
        try:
            return len(get_job_ids())
        except Exception:
            return 0
    return 0


def _oldest_queued_age_seconds(queue: Any) -> float | None:
    get_jobs = getattr(queue, "get_jobs", None)
    if not callable(get_jobs):
        return None
    try:
        jobs = get_jobs(0, 1)
    except Exception:
        return None
    if not jobs:
        return None
    enqueued_at = getattr(jobs[0], "enqueued_at", None)
    if enqueued_at is None:
        return None
    if enqueued_at.tzinfo is None:
        enqueued_at = enqueued_at.replace(tzinfo=timezone.utc)
    return round(max(0.0, (datetime.now(timezone.utc) - enqueued_at).total_seconds()), 1)
