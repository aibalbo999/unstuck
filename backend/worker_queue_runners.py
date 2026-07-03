"""Queue worker launchers shared by worker_main wrappers."""

from __future__ import annotations

from collections.abc import Callable

from config import RQ_JOB_TIMEOUT_SECONDS
from runtime_dependencies import WorkerRuntime
from runtime_events import emit_log as default_emit_log
from worker_shutdown import install_shutdown_quiet_pubsub, rq_worker_shutdown_requested


def run_rq_worker(
    runtime: WorkerRuntime,
    *,
    burst: bool = False,
    max_jobs: int | None = None,
    emit: Callable[[str], None] = default_emit_log,
) -> None:
    task_queue = runtime.task_queue
    rq_queue = getattr(task_queue, "queue", None)
    redis = getattr(task_queue, "redis", None)
    if rq_queue is None or redis is None:
        raise RuntimeError("RQ worker requires an RQ task queue with queue and redis attributes.")

    from rq import SimpleWorker
    from redis.exceptions import ConnectionError as RedisConnectionError

    rq_queues = list(getattr(task_queue, "queues", {}).values()) or [rq_queue]
    worker = SimpleWorker(rq_queues, connection=redis)
    install_shutdown_quiet_pubsub(worker)
    try:
        worker.work(
            burst=burst,
            max_jobs=max_jobs,
            # RQ retries are stored in ScheduledJobRegistry; without the RQ
            # scheduler they stay there forever and the UI appears silent.
            with_scheduler=True,
        )
    except RedisConnectionError:
        if rq_worker_shutdown_requested(worker):
            emit("queue worker stopped after Redis shutdown.")
            return
        raise


def run_arq_worker(
    runtime: WorkerRuntime,
    *,
    burst: bool = False,
    max_jobs: int | None = None,
) -> None:
    task_queue = runtime.task_queue
    redis_settings = getattr(task_queue, "redis_settings", None)
    queue_name = getattr(task_queue, "queue_name", None)
    if redis_settings is None or not queue_name:
        raise RuntimeError("ARQ worker requires an ARQ task queue with redis_settings and queue_name attributes.")

    from arq.worker import Worker
    from task_queue_arq import arq_worker_functions

    worker = Worker(
        arq_worker_functions(),
        redis_settings=redis_settings,
        queue_name=queue_name,
        burst=burst,
        max_burst_jobs=max_jobs if max_jobs is not None else -1,
        job_timeout=RQ_JOB_TIMEOUT_SECONDS,
        keep_result=7 * 24 * 60 * 60,
    )
    worker.run()
