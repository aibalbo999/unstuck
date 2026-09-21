"""Bounded attribution for current jobs/fetches; never infer historical ownership."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import inspect
import re
from uuid import uuid4

_CURRENT = ContextVar("provider_correlation", default=None)
_ATTEMPTS = ContextVar("provider_attempts", default=None)
_SOURCE = ContextVar("provider_source_identity", default=None)
_TEXT_KEYS = ("job_id", "ticker", "fetch_id", "operation_id", "attempt_id", "event_kind")


def correlation_metadata(entry=None):
    """Allowlist IDs only; callers must supply a real fingerprint, never a guess."""
    entry = entry if isinstance(entry, dict) else {}
    result = {key: entry[key][:160] for key in _TEXT_KEYS
              if isinstance(entry.get(key), str) and entry[key]}
    fingerprint = entry.get("data_fingerprint")
    if isinstance(fingerprint, str) and re.fullmatch(r"[0-9a-fA-F]{64}", fingerprint):
        result["data_fingerprint"] = fingerprint
    if isinstance(entry.get("provider_sla_event_id"), int):
        result["provider_sla_event_id"] = entry["provider_sla_event_id"]
    attempts = entry.get("provider_attempts")
    if isinstance(attempts, list):
        result["provider_attempts"] = [
            {key: value[:160] if isinstance(value, str) else value for key, value in attempt.items()
             if key in {"attempt_id", "source", "provider", "attempt_number", "status"}
             and isinstance(value, (str, int))}
            for attempt in attempts[:50] if isinstance(attempt, dict)
        ]
        result["provider_attempt_count"] = len(attempts)
    return result


def current_correlation():
    return dict(_CURRENT.get() or {})


@contextmanager
def correlation_scope(*, replace=False, **values):
    current = {} if replace else current_correlation()
    current.update(correlation_metadata(values))
    token = _CURRENT.set(current)
    attempts_token = _ATTEMPTS.set(None) if replace else None
    source_token = _SOURCE.set(None) if replace else None
    try:
        yield current
    finally:
        if source_token is not None:
            _SOURCE.reset(source_token)
        if attempts_token is not None:
            _ATTEMPTS.reset(attempts_token)
        _CURRENT.reset(token)


def current_audit_correlation():
    metadata = current_correlation()
    if metadata:
        metadata["event_kind"] = "aggregate"
    attempts = _ATTEMPTS.get()
    if attempts is not None:
        metadata["provider_attempts"] = list(attempts)
    return metadata


def correlate_job(function):
    signature = inspect.signature(function)

    @wraps(function)
    async def wrapped(*args, **kwargs):
        arguments = signature.bind_partial(*args, **kwargs).arguments
        with correlation_scope(replace=True, job_id=arguments.get("job_id"), ticker=arguments.get("ticker")):
            return await function(*args, **kwargs)
    return wrapped


def correlate_fetch(function):
    @wraps(function)
    async def wrapped(self, request, *args, **kwargs):
        # Only job identity is inherited. A new fetch cannot reuse a prior attempt.
        job = current_correlation().get("job_id")
        with correlation_scope(replace=True, job_id=job, ticker=request.ticker.strip().upper(),
                               fetch_id=uuid4().hex, event_kind="aggregate"):
            return await function(self, request, *args, **kwargs)
    return wrapped


@contextmanager
def source_operation(source, provider):
    values = current_correlation()
    values.pop("attempt_id", None)
    values.setdefault("fetch_id", uuid4().hex)
    values.update(operation_id=uuid4().hex, event_kind="aggregate")
    token = _CURRENT.set(values)
    attempts_token = _ATTEMPTS.set([])
    source_token = _SOURCE.set((str(source), str(provider)))
    try:
        yield
    finally:
        _SOURCE.reset(source_token)
        _ATTEMPTS.reset(attempts_token)
        _CURRENT.reset(token)


def correlate_source(function):
    signature = inspect.signature(function)

    def arguments(args, kwargs):
        bound = signature.bind_partial(*args, **kwargs).arguments
        return bound.get("source", "unknown"), bound.get("provider", "unknown")

    if inspect.iscoroutinefunction(function):
        @wraps(function)
        async def async_wrapped(*args, **kwargs):
            with source_operation(*arguments(args, kwargs)):
                return await function(*args, **kwargs)
        return async_wrapped

    @wraps(function)
    def sync_wrapped(*args, **kwargs):
        with source_operation(*arguments(args, kwargs)):
            return function(*args, **kwargs)
    return sync_wrapped


@contextmanager
def provider_attempt(provider, attempt_number):
    """Observe actual callback invocations without changing retry/circuit behavior."""
    attempt_id = uuid4().hex
    source = (_SOURCE.get() or ("unknown", provider))[0]
    status = "success"
    with correlation_scope(attempt_id=attempt_id):
        try:
            yield
        except BaseException as exc:
            status = "cancelled" if exc.__class__.__name__ == "CancelledError" else "error"
            raise
        finally:
            attempts = _ATTEMPTS.get()
            if attempts is not None:
                attempts.append({"attempt_id": attempt_id, "source": source,
                                 "provider": str(provider)[:160], "attempt_number": int(attempt_number),
                                 "status": status})
