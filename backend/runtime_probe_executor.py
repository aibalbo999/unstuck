"""A single-worker, zero-queue lane for one critical read-only probe.

Timed-out or cancelled callers do not free a running worker's slot. Repeated
requests fail fast until the original work ends, instead of accumulating work
in ThreadPoolExecutor's otherwise unbounded queue.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager
from contextvars import copy_context
from threading import Lock
from typing import Callable, TypeVar


T = TypeVar("T")


class ProbeUnavailable(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class BoundedProbeExecutor:
    def __init__(self, name: str):
        self._name = name
        self._lock = Lock()
        self._executor: ThreadPoolExecutor | None = None
        self._inflight: Future | None = None
        self._closed = False

    @asynccontextmanager
    async def lifespan(self, _app):
        with self._lock:
            if self._inflight is not None and not self._inflight.done():
                raise RuntimeError("The previous probe lifespan still has running work.")
            self._closed = False
        try:
            yield
        finally:
            self.close()

    async def run(self, operation: Callable[[], T], *, timeout_seconds: float) -> T:
        with self._lock:
            if self._closed:
                raise ProbeUnavailable("probe_closed")
            if self._inflight is not None and not self._inflight.done():
                raise ProbeUnavailable("probe_busy")
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=self._name)
            future = self._executor.submit(copy_context().run, operation)
            self._inflight = future

        wrapped = asyncio.wrap_future(future)
        # A disconnected/expired caller may never collect a later exception.
        # Consume it without logging request data; normal awaiting still raises.
        wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        deadline = asyncio.timeout(timeout_seconds)
        try:
            async with deadline:
                return await asyncio.shield(wrapped)
        except TimeoutError as exc:
            if deadline.expired():
                raise ProbeUnavailable("probe_timeout") from exc
            raise

    def close(self) -> None:
        with self._lock:
            self._closed = True
            executor, self._executor = self._executor, None
        if executor is not None:
            # Python cannot interrupt a running blocking call. Shut admission
            # now; the one worker exits when its already-started work finishes.
            executor.shutdown(wait=False, cancel_futures=True)
