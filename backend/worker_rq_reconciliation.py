"""RQ registry inspection helpers for worker reconciliation."""

from __future__ import annotations

import os
import socket
from datetime import datetime, timezone


RQ_WORKER_HEARTBEAT_GRACE_SECONDS = 300.0


def rq_active_job_ids(rq_queues) -> set[str]:
    from rq.registry import DeferredJobRegistry, ScheduledJobRegistry, StartedJobRegistry

    if not isinstance(rq_queues, (list, tuple, set)):
        rq_queues = [rq_queues]
    job_ids: set[str] = set()
    for rq_queue in rq_queues:
        job_ids.update(str(job_id) for job_id in getattr(rq_queue, "job_ids", []))
        started_registry = StartedJobRegistry(queue=rq_queue)
        started_job_ids = {str(job_id) for job_id in started_registry.get_job_ids()}
        job_ids.update(rq_live_started_job_ids(rq_queue, started_job_ids))
        for registry_class in (DeferredJobRegistry, ScheduledJobRegistry):
            registry = registry_class(queue=rq_queue)
            job_ids.update(str(job_id) for job_id in registry.get_job_ids())
    return job_ids


def rq_live_started_job_ids(rq_queue, started_job_ids: set[str]) -> set[str]:
    if not started_job_ids:
        return set()
    try:
        from rq import Worker

        workers = Worker.all(connection=getattr(rq_queue, "connection", None))
    except Exception:
        return set(started_job_ids)

    live_job_ids: set[str] = set()
    for worker in workers:
        current_job_id = rq_worker_current_job_id(worker)
        if current_job_id in started_job_ids and rq_worker_appears_live(worker):
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
