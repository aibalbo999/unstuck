"""One fresh, read-only performance computation outside API projection threads."""
from __future__ import annotations

import asyncio
import logging
import multiprocessing
import sqlite3
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from threading import Lock
from time import monotonic

LOGGER = logging.getLogger("uvicorn.error")
_CHILD_BOUNDARY_INSTALLED = False


class PerformanceReadUnavailable(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _install_readonly_boundary():
    global _CHILD_BOUNDARY_INSTALLED
    if _CHILD_BOUNDARY_INSTALLED:
        return
    import os
    import socket
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    connect = sqlite3.connect

    def readonly_connect(database, *args, **kwargs):
        name = os.fspath(database)
        if name.startswith('file:'):
            uri = urlsplit(name)
            query = dict(parse_qsl(uri.query))
            query['mode'] = 'ro'
            name = urlunsplit((uri.scheme, uri.netloc, uri.path, urlencode(query), uri.fragment))
        else:
            name = Path(name).resolve().as_uri() + '?mode=ro'
        kwargs['uri'] = True
        return connect(name, *args, **kwargs)

    def no_network(*args, **kwargs):
        raise OSError('Performance reads cannot contact providers, Redis or models')

    # Installed once in the dedicated child, never recursively wrapped per request.
    sqlite3.connect = readonly_connect
    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    socket.create_connection = no_network
    socket.getaddrinfo = no_network
    _CHILD_BOUNDARY_INSTALLED = True


def _compute_readonly_performance(output_dir: str) -> dict:
    _install_readonly_boundary()
    from decision_tracking_service import compute_tracking_performance_stats
    return compute_tracking_performance_stats(output_dir)


class PerformanceReadExecutor:
    """At most one running read; overlapping callers join, results are not cached."""
    def __init__(self, executor_factory=None, *, timeout_seconds=15.0, compute_fn=None, read_name="performance"):
        self._factory = executor_factory or (lambda: ProcessPoolExecutor(
            max_workers=1, mp_context=multiprocessing.get_context('spawn')))
        self._timeout_seconds = timeout_seconds
        self._compute_fn = compute_fn or _compute_readonly_performance
        self._read_name = read_name
        self._lock = Lock()
        self._executor = None
        self._inflight = None
        self._output_dir = None
        self._closed = False

    def open(self):
        with self._lock:
            if self._inflight is not None and not self._inflight.done():
                raise PerformanceReadUnavailable(f'{self._read_name}_reader_finishing_previous_lifespan')
            self._closed = False

    async def read(self, output_dir: str | tuple[str, str]) -> dict:
        with self._lock:
            if self._closed:
                raise PerformanceReadUnavailable(f'{self._read_name}_reader_closed')
            if self._inflight is not None and not self._inflight.done():
                if output_dir != self._output_dir:
                    raise PerformanceReadUnavailable(f'{self._read_name}_reader_busy')
                future = self._inflight
            else:
                cold_start = self._executor is None
                started = monotonic()
                if cold_start:
                    self._executor = self._factory()
                try:
                    future = self._executor.submit(self._compute_fn, output_dir)
                except BrokenProcessPool:
                    executor, self._executor = self._executor, None
                    executor.shutdown(wait=False, cancel_futures=False)
                    raise
                self._inflight, self._output_dir = future, output_dir
                future.add_done_callback(lambda done: LOGGER.info(
                    "%s_read_complete cold_start=%s seconds=%.3f status=%s",
                    self._read_name, cold_start, monotonic()-started,
                    "failed" if done.cancelled() or done.exception() else "ok"))
        wrapped = asyncio.wrap_future(future)
        wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        deadline = asyncio.timeout(self._timeout_seconds)
        try:
            async with deadline:
                return await asyncio.shield(wrapped)
        except TimeoutError as exc:
            if deadline.expired():
                raise PerformanceReadUnavailable(f'{self._read_name}_read_timeout') from exc
            raise
        except BrokenProcessPool:
            with self._lock:
                # Other callers of this failed read must not close a newer pool.
                executor = self._executor if self._inflight is future else None
                if executor is not None:
                    self._executor = None
            if executor is not None:
                executor.shutdown(wait=False, cancel_futures=False)
            raise

    def close(self):
        with self._lock:
            self._closed = True
            executor, self._executor = self._executor, None
        if executor is not None:
            # Already-started reads finish naturally; shutdown stops admission.
            executor.shutdown(wait=False, cancel_futures=False)


performance_reads = PerformanceReadExecutor()


async def read_performance_stats(output_dir: str) -> dict:
    try:
        return await performance_reads.read(output_dir)
    except PerformanceReadUnavailable as exc:
        reason = exc.reason
    except (BrokenProcessPool, sqlite3.Error, OSError):
        LOGGER.exception('Performance read failed; no saved result substituted')
        reason = 'performance_read_failed'
    return {'status': 'unavailable', 'reason': reason,
            'population': {'status': 'unavailable', 'reason': reason,
                           'credible_strategy_performance': False}}
