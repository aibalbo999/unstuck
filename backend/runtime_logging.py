"""Runtime logging sink backed by stdlib logging."""

from __future__ import annotations

import asyncio
import contextvars
import functools
import logging
import sys
import time
import uuid
from contextlib import contextmanager
from collections.abc import Callable, Iterator, Mapping
from typing import Any


LOGGER_NAME = "stock_agent.runtime"
TRACE_ID_CONTEXT_KEY = "runtime.trace_id"

_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(TRACE_ID_CONTEXT_KEY, default="")

try:  # pragma: no cover - exercised only when optional dependency is installed
    from opentelemetry import trace as otel_trace
    from opentelemetry.trace import Status, StatusCode
except Exception:  # pragma: no cover - default local test environment has no otel
    otel_trace = None
    Status = None
    StatusCode = None


def get_runtime_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def log_runtime_message(message: str, *, level: str = "info") -> None:
    logger = get_runtime_logger()
    log_method = getattr(logger, str(level or "info").lower(), logger.info)
    log_method(str(message)[:500])


def get_current_trace_id() -> str:
    """Return the current runtime trace id propagated through asyncio tasks."""
    return _trace_id_var.get()


@contextmanager
def runtime_trace_context(trace_id: str | None = None) -> Iterator[str]:
    """Set a trace id for the current request/task context."""
    active_trace_id = str(trace_id or uuid.uuid4().hex)
    token = _trace_id_var.set(active_trace_id)
    try:
        yield active_trace_id
    finally:
        _trace_id_var.reset(token)


def _get_tracer() -> Any:
    if otel_trace is None:
        return _NoOpTracer()
    return otel_trace.get_tracer("stock_agent.runtime")


class _NoOpSpan:
    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, exc_type: Any, exc: BaseException | None, tb: Any) -> bool:
        return False

    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def record_exception(self, exc: BaseException) -> None:
        return None

    def set_status(self, status: Any) -> None:
        return None


class _NoOpTracer:
    def start_as_current_span(self, name: str, attributes: Mapping[str, Any] | None = None) -> _NoOpSpan:
        return _NoOpSpan()


def trace_runtime_operation(
    name: str,
    *,
    attributes: Mapping[str, Any] | None = None,
    token_usage_extractor: Callable[[Any], Mapping[str, Any] | None] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate sync or async operations with OpenTelemetry-compatible spans.

    Use ``attributes`` to label external API, LLM, or database operations. When
    a token usage extractor is supplied, returned usage keys are written as
    ``llm.<key>`` span attributes.
    """
    base_attributes = dict(attributes or {})

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await _run_traced_async(func, name, base_attributes, token_usage_extractor, *args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return _run_traced_sync(func, name, base_attributes, token_usage_extractor, *args, **kwargs)

        return wrapper

    return decorator


async def _run_traced_async(
    func: Callable[..., Any],
    span_name: str,
    attributes: Mapping[str, Any],
    token_usage_extractor: Callable[[Any], Mapping[str, Any] | None] | None,
    *args: Any,
    **kwargs: Any,
) -> Any:
    started = time.perf_counter()
    with _start_span(span_name, attributes) as span:
        try:
            result = await func(*args, **kwargs)
        except Exception as exc:
            _record_span_error(span, exc, started)
            raise
        _finalize_span(span, result, started, token_usage_extractor)
        return result


def _run_traced_sync(
    func: Callable[..., Any],
    span_name: str,
    attributes: Mapping[str, Any],
    token_usage_extractor: Callable[[Any], Mapping[str, Any] | None] | None,
    *args: Any,
    **kwargs: Any,
) -> Any:
    started = time.perf_counter()
    with _start_span(span_name, attributes) as span:
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            _record_span_error(span, exc, started)
            raise
        _finalize_span(span, result, started, token_usage_extractor)
        return result


def _start_span(span_name: str, attributes: Mapping[str, Any]):
    span_attributes = dict(attributes)
    trace_id = get_current_trace_id()
    if trace_id:
        span_attributes["runtime.trace_id"] = trace_id
    span_attributes.setdefault("runtime.operation", span_name)
    return _get_tracer().start_as_current_span(span_name, attributes=span_attributes)


def _finalize_span(
    span: Any,
    result: Any,
    started: float,
    token_usage_extractor: Callable[[Any], Mapping[str, Any] | None] | None,
) -> None:
    span.set_attribute("duration_ms", max(0, int(round((time.perf_counter() - started) * 1000))))
    trace_id = get_current_trace_id()
    if trace_id:
        span.set_attribute("runtime.trace_id", trace_id)
    if token_usage_extractor is None:
        return
    usage = token_usage_extractor(result) or {}
    for key, value in usage.items():
        if value is None:
            continue
        span.set_attribute(f"llm.{key}", value)


def _record_span_error(span: Any, exc: BaseException, started: float) -> None:
    span.set_attribute("duration_ms", max(0, int(round((time.perf_counter() - started) * 1000))))
    span.set_attribute("error.type", exc.__class__.__name__)
    span.set_attribute("error.message", str(exc)[:240])
    span.record_exception(exc)
    if Status is not None and StatusCode is not None:
        span.set_status(Status(StatusCode.ERROR, str(exc)[:240]))
