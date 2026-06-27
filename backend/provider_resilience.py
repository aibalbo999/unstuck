"""Retry/backoff and circuit-breaker helpers for data providers."""

from __future__ import annotations

import inspect
import os
import time
from typing import Any, Callable

from tenacity import (
    AsyncRetrying,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
    wait_random,
)

from provider_circuit_cache import load_persisted_circuit, persist_circuit_state


class ProviderCircuitOpenError(RuntimeError):
    """Raised when a provider is temporarily circuit-open."""


class CircuitBreaker:
    """A pure-Python Circuit Breaker implementation."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self.failure_threshold = int(failure_threshold)
        self.recovery_timeout = float(recovery_timeout)
        self.failures = 0
        self.last_failure_time = 0.0
        self.last_error = ""
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN

    def record_success(self) -> None:
        self.failures = 0
        self.last_error = ""
        self.state = "CLOSED"

    def record_failure(self, error: object = "") -> None:
        self.failures += 1
        self.last_failure_time = time.time()
        self.last_error = str(error or "")[:240]
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"

    def check_state(self) -> None:
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF-OPEN"
            else:
                remaining = self.recovery_timeout - (time.time() - self.last_failure_time)
                raise ProviderCircuitOpenError(f"Circuit is OPEN. Fast failing. Retry in {remaining:.1f}s")

    def snapshot(self) -> dict[str, Any]:
        self.check_state()
        opened_until = (
            self.last_failure_time + self.recovery_timeout
            if self.state == "OPEN" and self.last_failure_time
            else 0.0
        )
        return {
            "open": self.state == "OPEN",
            "state": self.state,
            "failures": int(self.failures),
            "opened_until": opened_until,
            "last_error": self.last_error,
        }


_CIRCUITS: dict[str, CircuitBreaker] = {}
_SHARED_CIRCUIT_STORE: Any = None


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return max(minimum, default)


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except ValueError:
        return max(minimum, default)


def _retry_attempts() -> int:
    return _env_int("PROVIDER_RETRY_ATTEMPTS", 3, minimum=1)


def _retry_backoff_seconds() -> float:
    return _env_float("PROVIDER_RETRY_BACKOFF_SECONDS", 1.0, minimum=0.0)


def _retry_backoff_max_seconds() -> float:
    return _env_float("PROVIDER_RETRY_BACKOFF_MAX_SECONDS", 10.0, minimum=0.0)


def _retry_jitter_seconds() -> float:
    return _env_float("PROVIDER_RETRY_JITTER_SECONDS", 0.5, minimum=0.0)


def _circuit_threshold() -> int:
    return _env_int("PROVIDER_CIRCUIT_BREAKER_THRESHOLD", 3, minimum=1)


def _circuit_cooldown_seconds() -> float:
    return _env_float("PROVIDER_CIRCUIT_BREAKER_COOLDOWN_SECONDS", 60.0, minimum=1.0)


def _provider_key(provider: str) -> str:
    return str(provider or "unknown").strip() or "unknown"


def _shared_store() -> Any | None:
    store = _SHARED_CIRCUIT_STORE
    if store is not None and bool(getattr(store, "enabled", True)):
        return store
    return None


def get_circuit_breaker(provider: str) -> CircuitBreaker:
    key = _provider_key(provider)
    if key not in _CIRCUITS:
        _CIRCUITS[key] = CircuitBreaker()
    breaker = _CIRCUITS[key]
    breaker.failure_threshold = _circuit_threshold()
    breaker.recovery_timeout = _circuit_cooldown_seconds()
    load_persisted_circuit(key, breaker)
    return breaker


def _check_provider_state(provider: str) -> None:
    store = _shared_store()
    if store is not None:
        state = store.state(_provider_key(provider))
        if state.get("open"):
            opened_until = float(state.get("opened_until") or 0.0)
            remaining = max(0.0, opened_until - time.time()) if opened_until else _circuit_cooldown_seconds()
            raise ProviderCircuitOpenError(f"Circuit is OPEN. Fast failing. Retry in {remaining:.1f}s")
        return
    get_circuit_breaker(provider).check_state()


def _record_provider_success(provider: str) -> None:
    store = _shared_store()
    if store is not None:
        store.record_success(_provider_key(provider))
        return
    breaker = get_circuit_breaker(provider)
    breaker.record_success()
    persist_circuit_state(_provider_key(provider), breaker)


def _record_provider_failure(provider: str, exc: BaseException) -> None:
    error = str(exc or "")[:240]
    store = _shared_store()
    if store is not None:
        store.record_failure(
            _provider_key(provider),
            error,
            _circuit_threshold(),
            _circuit_cooldown_seconds(),
        )
        return
    breaker = get_circuit_breaker(provider)
    breaker.record_failure(error)
    persist_circuit_state(_provider_key(provider), breaker)


def _retry_wait_strategy():
    base = _retry_backoff_seconds()
    jitter = _retry_jitter_seconds()
    max_wait = max(_retry_backoff_max_seconds(), base)
    if base <= 0:
        strategy = wait_fixed(0)
    else:
        strategy = wait_exponential(multiplier=base, min=base, max=max_wait)
    if jitter > 0:
        strategy = strategy + wait_random(0, jitter)
    return strategy


def _should_retry(exc: BaseException) -> bool:
    return not isinstance(exc, ProviderCircuitOpenError)


def provider_circuit_state(provider: str) -> dict[str, Any]:
    """Return current circuit state for observability and tests."""
    store = _shared_store()
    key = _provider_key(provider)
    if store is not None:
        return dict(store.state(key))
    try:
        return get_circuit_breaker(key).snapshot()
    except ProviderCircuitOpenError:
        breaker = get_circuit_breaker(key)
        return {
            "open": True,
            "state": breaker.state,
            "failures": int(breaker.failures),
            "opened_until": breaker.last_failure_time + breaker.recovery_timeout,
            "last_error": breaker.last_error,
        }


def clear_provider_circuits(provider: str | None = None) -> None:
    """Clear one provider circuit or all local/shared provider circuits."""
    store = _shared_store()
    if store is not None:
        store.clear(_provider_key(provider) if provider else None)
    if provider is None:
        _CIRCUITS.clear()
    else:
        key = _provider_key(provider)
        breaker = _CIRCUITS.pop(key, None) or CircuitBreaker(_circuit_threshold(), _circuit_cooldown_seconds())
        breaker.record_success()
        persist_circuit_state(key, breaker)


def call_provider_with_resilience(provider: str, func: Callable, args: tuple = (), kwargs: dict | None = None) -> Any:
    """Sync wrapper combining Circuit Breaker and Tenacity Retries."""
    _check_provider_state(provider)

    try:
        for attempt in Retrying(
            stop=stop_after_attempt(_retry_attempts()),
            wait=_retry_wait_strategy(),
            retry=retry_if_exception(_should_retry),
            reraise=True,
        ):
            with attempt:
                result = func(*args, **(kwargs or {}))
                _record_provider_success(provider)
                return result
    except Exception as exc:
        _record_provider_failure(provider, exc)
        raise exc


async def call_provider_with_resilience_async(provider: str, func_or_awaitable, args: tuple = (), kwargs: dict | None = None) -> Any:
    """Async wrapper combining Circuit Breaker and Tenacity Retries."""
    _check_provider_state(provider)

    async def invoke() -> Any:
        if inspect.isawaitable(func_or_awaitable):
            return await func_or_awaitable
        result = func_or_awaitable(*args, **(kwargs or {}))
        if inspect.isawaitable(result):
            return await result
        return result

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(1 if inspect.isawaitable(func_or_awaitable) else _retry_attempts()),
            wait=_retry_wait_strategy(),
            retry=retry_if_exception(_should_retry),
            reraise=True,
        ):
            with attempt:
                result = await invoke()
                _record_provider_success(provider)
                return result
    except Exception as exc:
        _record_provider_failure(provider, exc)
        raise exc
