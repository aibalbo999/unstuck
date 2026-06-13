"""Local task queue abstraction using asyncio for long-running report jobs.

This completely replaces the old ThreadPoolExecutor to prevent "Database is locked"
issues and significantly reduce overhead for I/O bound LLM agent workflows.
"""

import asyncio
import inspect
import logging

from config import REDIS_URL, TASK_QUEUE_BACKEND, TASK_QUEUE_NAME

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
    return LocalAsyncQueue(max_concurrent=5)
