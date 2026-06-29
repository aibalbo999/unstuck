"""Local task queue abstraction using asyncio for long-running report jobs.

This completely replaces the old ThreadPoolExecutor to prevent "Database is locked"
issues and significantly reduce overhead for I/O bound LLM agent workflows.
"""

import asyncio
import inspect
import logging

from config import (
    REDIS_URL,
    RQ_JOB_MAX_RETRIES,
    RQ_JOB_RETRY_INTERVALS,
    RQ_JOB_TIMEOUT_SECONDS,
    TASK_QUEUE_BACKEND,
    TASK_QUEUE_NAME,
    TASK_QUEUE_NAMES,
    TASK_QUEUE_ROUTES,
)

logger = logging.getLogger(__name__)


class LocalAsyncQueue:
    def __init__(self, max_concurrent: int = 5):
        self.queue = asyncio.Queue()
        self.max_concurrent = max_concurrent
        self.workers = []
        self._running = False
        self.active_tasks = set()

    async def _worker(self):
        while self._running:
            try:
                task_id, fn, args, kwargs = await self.queue.get()
                self.active_tasks.add(task_id)
                try:
                    result = fn(*args, **kwargs)
                    if inspect.isawaitable(result):
                        await result
                except Exception:
                    logger.exception(f"Async task failed: {task_id}")
                finally:
                    self.active_tasks.discard(task_id)
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Worker encountered unexpected error.")

    def start_workers(self):
        if self._running:
            return
        self._running = True
        for _ in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker())
            self.workers.append(worker)

    async def stop_workers(self):
        self._running = False
        for worker in self.workers:
            worker.cancel()
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()

    def submit(self, task_id: str, fn):
        return self.enqueue(task_id, fn)

    def enqueue(self, task_id: str, fn, *args, **kwargs):
        if task_id in self.active_tasks:
            return
        try:
            self.queue.put_nowait((task_id, fn, args, kwargs))
        except asyncio.QueueFull:
            logger.error("Local async queue is full.")
            raise

    def cancel(self, task_id: str) -> bool:
        retained = []
        removed = False
        while True:
            try:
                item = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            queued_task_id = item[0]
            if queued_task_id == task_id:
                removed = True
                self.queue.task_done()
            else:
                retained.append(item)
        for item in retained:
            self.queue.put_nowait(item)
        return removed


class RQTaskQueue:
    """Thin RQ adapter for deployments that provide Redis workers."""

    def __init__(
        self,
        redis_client=None,
        queue=None,
        queues=None,
        redis_url: str = REDIS_URL,
        queue_name: str = TASK_QUEUE_NAME,
        queue_names: tuple[str, ...] = TASK_QUEUE_NAMES,
        queue_routes: dict[str, str] = TASK_QUEUE_ROUTES,
    ):
        self.redis = redis_client
        self.queue_routes = dict(queue_routes or {})
        if queues is not None:
            self.queues = dict(queues)
            self.queue = self.queues.get(queue_name) or next(iter(self.queues.values()))
        elif queue is None:
            from redis import Redis
            from rq import Queue

            if self.redis is None:
                self.redis = Redis.from_url(redis_url)
            normalized_names = _normalize_queue_names(queue_names, queue_name)
            self.queues = {
                name: Queue(name, connection=self.redis)
                for name in normalized_names
            }
            self.queue = self.queues.get(queue_name) or next(iter(self.queues.values()))
        else:
            self.queue = queue
            self.queues = {getattr(queue, "name", queue_name): queue}

    def submit(self, task_id: str, fn):
        return self.enqueue(task_id, fn)

    def close(self):
        close = getattr(self.redis, "close", None)
        if callable(close):
            close()

    def enqueue(self, task_id: str, fn, *args, queue_name: str | None = None, **kwargs):
        from rq import Retry

        queue = self._queue_for_task(task_id, queue_name=queue_name)
        return queue.enqueue_call(
            func=fn,
            args=args,
            kwargs=kwargs,
            job_id=task_id,
            timeout=RQ_JOB_TIMEOUT_SECONDS,
            retry=Retry(max=RQ_JOB_MAX_RETRIES, interval=list(RQ_JOB_RETRY_INTERVALS)),
            result_ttl=7 * 24 * 60 * 60,
            failure_ttl=7 * 24 * 60 * 60,
        )

    def cancel(self, task_id: str) -> bool:
        job = None
        for queue in self.queues.values():
            fetch_job = getattr(queue, "fetch_job", None)
            job = fetch_job(task_id) if callable(fetch_job) else None
            if job is not None:
                break
        if job is None:
            return False
        cancel = getattr(job, "cancel", None)
        delete = getattr(job, "delete", None)
        if callable(cancel):
            cancel()
        if callable(delete):
            delete()
        return True

    def _queue_for_task(self, task_id: str, *, queue_name: str | None = None):
        requested = str(queue_name or "").strip()
        if requested and requested in self.queues:
            return self.queues[requested]
        prefix = str(task_id or "").split(":", 1)[0]
        routed = str(self.queue_routes.get(prefix) or "").strip()
        if routed and routed in self.queues:
            return self.queues[routed]
        return self.queue


def _normalize_queue_names(queue_names: tuple[str, ...] | list[str] | None, default_queue_name: str) -> tuple[str, ...]:
    names = []
    for name in (queue_names or (default_queue_name,)):
        normalized = str(name or "").strip()
        if normalized and normalized not in names:
            names.append(normalized)
    if default_queue_name not in names:
        names.insert(0, default_queue_name)
    return tuple(names)


def create_api_task_queue():
    if TASK_QUEUE_BACKEND != "rq":
        raise RuntimeError("API task queue requires Redis and RQ; set TASK_QUEUE_BACKEND=rq.")
    return RQTaskQueue()


def create_task_queue():
    if TASK_QUEUE_BACKEND == "rq":
        return RQTaskQueue()
    if TASK_QUEUE_BACKEND != "local":
        logger.warning("Unknown TASK_QUEUE_BACKEND=%s; falling back to local", TASK_QUEUE_BACKEND)
    return LocalAsyncQueue(max_concurrent=5)
