"""Local task queue abstraction for long-running report jobs.

This keeps raw thread management out of the FastAPI route and gives us one
place to swap in RQ/Celery later when Redis is available.
"""

from concurrent.futures import ThreadPoolExecutor
import logging
import threading


logger = logging.getLogger(__name__)


class LocalTaskQueue:
    def __init__(self, max_workers: int = 2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="analysis-worker")
        self.lock = threading.Lock()
        self.futures = {}

    def submit(self, task_id: str, fn):
        with self.lock:
            old_future = self.futures.get(task_id)
            if old_future and not old_future.done():
                return old_future

            future = self.executor.submit(self._run, task_id, fn)
            self.futures[task_id] = future

        future.add_done_callback(lambda finished: self._forget(task_id, finished))
        return future

    def _run(self, task_id: str, fn):
        try:
            return fn()
        except Exception:
            logger.exception("Task failed: %s", task_id)
            raise

    def _forget(self, task_id: str, finished_future):
        with self.lock:
            if self.futures.get(task_id) is finished_future:
                self.futures.pop(task_id, None)
