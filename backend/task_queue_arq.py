"""ARQ task queue producer and worker bindings."""

from __future__ import annotations

import asyncio
import inspect
import threading
from concurrent.futures import Future
from typing import Any, Callable

from config import REDIS_URL, RQ_JOB_TIMEOUT_SECONDS, TASK_QUEUE_NAME


class ARQTaskQueue:
    """ARQ producer adapter with the same sync enqueue surface as RQTaskQueue."""

    backend_name = "arq"

    def __init__(
        self,
        *,
        redis_url: str = REDIS_URL,
        queue_name: str = TASK_QUEUE_NAME,
        pool: Any | None = None,
        loop_runner: "_AsyncLoopRunner | None" = None,
    ):
        self.redis_url = redis_url
        self.queue_name = queue_name
        self._pool = pool
        self._runner = loop_runner or _AsyncLoopRunner()
        self._closed = False

    @property
    def redis_settings(self):
        from arq.connections import RedisSettings

        return RedisSettings.from_dsn(self.redis_url)

    def submit(self, task_id: str, fn):
        return self.enqueue(task_id, fn)

    def enqueue(self, task_id: str, fn, *args, queue_name: str | None = None, **kwargs):
        function_name = _arq_function_name(fn)
        return self._runner.run(
            self._enqueue_async(
                function_name,
                task_id,
                args,
                kwargs,
                queue_name=str(queue_name or self.queue_name),
            )
        )

    def cancel(self, task_id: str) -> bool:
        return bool(self._runner.run(self._cancel_async(task_id)))

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._pool is not None:
            self._runner.run(_close_async_pool(self._pool))
        self._runner.close()

    async def _enqueue_async(self, function_name: str, task_id: str, args: tuple, kwargs: dict, *, queue_name: str):
        pool = await self._pool_async()
        return await pool.enqueue_job(
            function_name,
            *args,
            _job_id=task_id,
            _queue_name=queue_name,
            _expires=RQ_JOB_TIMEOUT_SECONDS,
            **kwargs,
        )

    async def _cancel_async(self, task_id: str) -> bool:
        from arq.jobs import Job

        pool = await self._pool_async()
        job = Job(task_id, redis=pool, _queue_name=self.queue_name)
        try:
            return bool(await job.abort(timeout=1))
        except Exception:
            return False

    async def _pool_async(self):
        if self._pool is None:
            from arq import create_pool

            self._pool = await create_pool(self.redis_settings, default_queue_name=self.queue_name)
        return self._pool


class _AsyncLoopRunner:
    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def run(self, coro):
        loop = self._ensure_loop()
        future: Future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    def close(self) -> None:
        with self._lock:
            loop = self._loop
            thread = self._thread
            self._loop = None
            self._thread = None
        if loop is None:
            return
        loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5)

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is not None:
                return self._loop
            ready = threading.Event()
            loop = asyncio.new_event_loop()

            def run_loop():
                asyncio.set_event_loop(loop)
                ready.set()
                loop.run_forever()
                loop.close()

            thread = threading.Thread(target=run_loop, name="stock-agent-arq-producer", daemon=True)
            thread.start()
            ready.wait(timeout=5)
            self._loop = loop
            self._thread = thread
            return loop


async def _close_async_pool(pool) -> None:
    aclose = getattr(pool, "aclose", None)
    if callable(aclose):
        await aclose()
        return
    close = getattr(pool, "close", None)
    if callable(close):
        result = close()
        if inspect.isawaitable(result):
            await result


async def arq_run_stock_analysis_job(_ctx, job_id: str, ticker: str, pipeline_id: str = "v1") -> str:
    from analysis_jobs import run_stock_analysis_job_async

    return await run_stock_analysis_job_async(job_id, ticker, pipeline_id)


async def arq_run_report_rerun_job(
    _ctx,
    job_id: str,
    filename: str,
    scope: str = "final_recommendation",
) -> str:
    from report_rerun_jobs import run_report_rerun_job_async

    return await run_report_rerun_job_async(job_id, filename, scope)


def arq_worker_functions() -> list[Callable[..., Any]]:
    return [arq_run_stock_analysis_job, arq_run_report_rerun_job]


def _arq_function_name(fn) -> str:
    if isinstance(fn, str):
        return fn
    module = str(getattr(fn, "__module__", "") or "")
    name = str(getattr(fn, "__name__", "") or "")
    if module == "analysis_jobs" and name == "run_stock_analysis_job":
        return arq_run_stock_analysis_job.__name__
    if module == "report_rerun_jobs" and name == "run_report_rerun_job":
        return arq_run_report_rerun_job.__name__
    raise ValueError(f"ARQ task queue only supports registered job functions, got {module}.{name}")
