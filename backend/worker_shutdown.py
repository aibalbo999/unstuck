"""Shutdown helpers for worker processes."""

from __future__ import annotations

import asyncio
import inspect
import sys
from collections.abc import Awaitable, Callable
from types import MethodType


def install_shutdown_quiet_pubsub(worker: object) -> None:
    worker.subscribe = MethodType(_subscribe_with_shutdown_quiet_pubsub, worker)


def _subscribe_with_shutdown_quiet_pubsub(worker: object) -> None:
    worker.log.info("Subscribing to channel %s", worker.pubsub_channel_name)
    worker.pubsub = worker.connection.pubsub()
    worker.pubsub.subscribe(**{worker.pubsub_channel_name: worker.handle_payload})
    worker.pubsub_thread = worker.pubsub.run_in_thread(
        sleep_time=0.2,
        daemon=True,
        exception_handler=lambda exc, pubsub, thread: handle_rq_pubsub_thread_exception(
            worker,
            exc,
            pubsub,
            thread,
        ),
    )


def handle_rq_pubsub_thread_exception(
    worker: object,
    exc: BaseException,
    _pubsub: object,
    thread: object,
) -> None:
    from redis.exceptions import ConnectionError as RedisConnectionError

    if isinstance(exc, RedisConnectionError) and rq_worker_shutdown_requested(worker):
        stop = getattr(thread, "stop", None)
        if callable(stop):
            stop()
        return
    raise exc


def rq_worker_shutdown_requested(worker: object) -> bool:
    return getattr(worker, "_shutdown_requested_date", None) is not None or bool(
        getattr(worker, "_stop_requested", False)
    )


def run_async_process(coro_factory: Callable[[], Awaitable[None]]) -> None:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.set_exception_handler(_safe_asyncio_exception_handler)
        task = loop.create_task(coro_factory())
        try:
            loop.run_until_complete(task)
        except KeyboardInterrupt:
            task.cancel()
            loop.run_until_complete(asyncio.gather(task, return_exceptions=True))
        finally:
            _cancel_pending_async_tasks(loop)
            _run_cleanup_awaitable(loop, loop.shutdown_asyncgens)
            _run_cleanup_awaitable(loop, loop.shutdown_default_executor)
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def _cancel_pending_async_tasks(loop: asyncio.AbstractEventLoop) -> None:
    pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
    if not pending:
        return
    for task in pending:
        task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))


def _run_cleanup_awaitable(
    loop: asyncio.AbstractEventLoop,
    awaitable_factory: Callable[[], Awaitable[object]],
) -> None:
    awaitable = awaitable_factory()
    try:
        loop.run_until_complete(awaitable)
    except KeyboardInterrupt:
        _close_awaitable(awaitable)
        raise


def _close_awaitable(awaitable: Awaitable[object]) -> None:
    close = getattr(awaitable, "close", None)
    if callable(close) and inspect.iscoroutine(awaitable):
        close()


def _safe_asyncio_exception_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    sanitized = {key: _safe_exception_context_value(value) for key, value in dict(context or {}).items()}
    try:
        loop.default_exception_handler(sanitized)
    except Exception as exc:
        print(f"asyncio exception handler suppressed during shutdown: {type(exc).__name__}: {exc}", file=sys.stderr)


def _safe_exception_context_value(value):
    try:
        repr(value)
    except Exception as exc:
        return f"<unrepresentable {type(value).__name__}: {type(exc).__name__}: {exc}>"
    return value
