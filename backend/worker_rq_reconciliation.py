"""RQ registry inspection helpers for worker reconciliation."""

from __future__ import annotations

import os
import socket
from datetime import datetime, timezone


RQ_WORKER_HEARTBEAT_GRACE_SECONDS = 300.0


def rq_active_job_ids(rq_queues) -> set[str]:
    return set(rq_job_states(rq_queues))


def rq_job_states(rq_queues) -> dict[str, str]:
    from rq.registry import DeferredJobRegistry, ScheduledJobRegistry, StartedJobRegistry

    if not isinstance(rq_queues, (list, tuple, set)):
        rq_queues = [rq_queues]
    states: dict[str, str] = {}
    for rq_queue in rq_queues:
        states.update({str(job_id): "queued" for job_id in getattr(rq_queue, "job_ids", [])})
        started_registry = StartedJobRegistry(queue=rq_queue)
        started_job_ids = {str(job_id) for job_id in started_registry.get_job_ids()}
        states.update({job_id: "started" for job_id in rq_live_started_job_ids(rq_queue, started_job_ids)})
        for registry_class, state in ((DeferredJobRegistry, "deferred"), (ScheduledJobRegistry, "scheduled")):
            registry = registry_class(queue=rq_queue)
            for job_id in registry.get_job_ids():
                states.setdefault(str(job_id), state)
    return states


def rq_reconciliation_job_lists(rq_states: dict[str, str], active_jobs: list[dict]) -> tuple[list[str], list[str]]:
    rq_job_ids = set(rq_states)
    abandoned: list[str] = []
    retrying: list[str] = []
    for job in active_jobs:
        job_id = str(job.get("job_id") or "")
        if not job_id:
            continue
        if not _sqlite_job_has_active_rq_job(job, rq_job_ids):
            abandoned.append(job_id)
        if job.get("status") == "running" and rq_states.get(_rq_task_id_for_sqlite_job(job)) in {"queued", "deferred", "scheduled"}:
            retrying.append(job_id)
    return abandoned, retrying


def _rq_task_id_for_sqlite_job(job: dict) -> str:
    prefix = "report-rerun:" if str(job.get("pipeline_id") or "").startswith("rerun:") else "analysis:"
    return f"{prefix}{str(job.get('job_id') or '')}"


def _sqlite_job_has_active_rq_job(job: dict, rq_job_ids: set[str]) -> bool:
    job_id = str(job.get("job_id") or "")
    if not job_id:
        return False
    prefix = "report-rerun:" if str(job.get("pipeline_id") or "").startswith("rerun:") else "analysis:"
    return f"{prefix}{job_id}" in rq_job_ids


def rq_live_started_job_ids(rq_queue, started_job_ids: set[str]) -> set[str]:
    try:
        from rq import Worker

        workers = Worker.all(connection=getattr(rq_queue, "connection", None))
    except Exception:
        return set(started_job_ids)

    live_job_ids: set[str] = set()
    for worker in workers:
        current_job_id = rq_worker_current_job_id(worker)
        # SimpleWorker can expose a live current job before StartedJobRegistry
        # has replicated it; the worker claim is the stronger local signal.
        if current_job_id and rq_worker_appears_live(worker):
            live_job_ids.add(current_job_id)
    return live_job_ids


def rq_worker_current_job_id(worker) -> str:
    getter = getattr(worker, "get_current_job_id", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:
            value = None
    else:
        value = getattr(worker, "current_job_id", None)
    return str(value or "")


def rq_worker_appears_live(worker) -> bool:
    pid = rq_worker_pid(worker)
    if pid > 0:
        if pid_exists(pid):
            return True
        if rq_worker_is_local(worker):
            return False
    return rq_worker_heartbeat_is_fresh(worker)


def rq_worker_pid_exists(worker) -> bool:
    return pid_exists(rq_worker_pid(worker))


def rq_worker_pid(worker) -> int:
    try:
        return int(getattr(worker, "pid", None) or 0)
    except (TypeError, ValueError):
        return 0


def pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def rq_worker_is_local(worker) -> bool:
    hostname = str(getattr(worker, "hostname", "") or "").strip().lower()
    if not hostname:
        return False
    local_names = {
        str(value or "").strip().lower()
        for value in (socket.gethostname(), socket.getfqdn(), "localhost")
        if str(value or "").strip()
    }
    local_short_names = {name.split(".", 1)[0] for name in local_names if name}
    return hostname in local_names or hostname.split(".", 1)[0] in local_short_names


def rq_worker_heartbeat_is_fresh(worker) -> bool:
    heartbeat = coerce_datetime(getattr(worker, "last_heartbeat", None))
    if heartbeat is None:
        return False
    age_seconds = (datetime.now(timezone.utc) - heartbeat).total_seconds()
    return age_seconds <= RQ_WORKER_HEARTBEAT_GRACE_SECONDS


def coerce_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
