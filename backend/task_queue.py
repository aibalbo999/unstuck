"""Local task queue abstraction for long-running report jobs.

This keeps raw thread management out of the FastAPI route and gives us one
place to swap in RQ/Celery later when Redis is available.
"""

from concurrent.futures import ThreadPoolExecutor
import asyncio
import inspect
import logging
import threading

from config import ANALYSIS_WORKER_COUNT, REDIS_URL, TASK_QUEUE_BACKEND, TASK_QUEUE_NAME


logger = logging.getLogger(__name__)


class LocalTaskQueue:
    def __init__(self, max_workers: int = 2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="analysis-worker")
        self.lock = threading.Lock()
        self.futures = {}

    def submit(self, task_id: str, fn):
        return self.enqueue(task_id, fn)

    def enqueue(self, task_id: str, fn, *args, **kwargs):
        with self.lock:
            old_future = self.futures.get(task_id)
            if old_future and not old_future.done():
                return old_future

            future = self.executor.submit(self._run, task_id, fn, *args, **kwargs)
            self.futures[task_id] = future

        future.add_done_callback(lambda finished: self._forget(task_id, finished))
        return future

    def _run(self, task_id: str, fn, *args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            if inspect.isawaitable(result):
                return asyncio.run(result)
            return result
        except Exception:
            logger.exception("Task failed: %s", task_id)
            raise

    def _forget(self, task_id: str, finished_future):
        with self.lock:
            if self.futures.get(task_id) is finished_future:
                self.futures.pop(task_id, None)


class RQTaskQueue:
    """Thin RQ adapter for deployments that provide Redis workers."""

    def __init__(self, redis_url: str = REDIS_URL, queue_name: str = TASK_QUEUE_NAME):
        from redis import Redis
        from rq import Queue

        self.redis = Redis.from_url(redis_url)
        self.queue = Queue(queue_name, connection=self.redis)

    def submit(self, task_id: str, fn):
        return self.enqueue(task_id, fn)

    def enqueue(self, task_id: str, fn, *args, **kwargs):
        return self.queue.enqueue_call(
            func=fn,
            args=args,
            kwargs=kwargs,
            job_id=task_id,
            result_ttl=7 * 24 * 60 * 60,
            failure_ttl=7 * 24 * 60 * 60,
        )


def create_task_queue():
    if TASK_QUEUE_BACKEND == "rq":
        return RQTaskQueue()
    if TASK_QUEUE_BACKEND != "local":
        logger.warning("Unknown TASK_QUEUE_BACKEND=%s; falling back to local", TASK_QUEUE_BACKEND)
    return LocalTaskQueue(max_workers=ANALYSIS_WORKER_COUNT)
