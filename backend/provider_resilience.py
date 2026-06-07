"""Retry/backoff and circuit-breaker helpers for data providers."""

from __future__ import annotations

import asyncio
import inspect
import os
import time
from dataclasses import dataclass
from typing import Any, Callable


class ProviderCircuitOpenError(RuntimeError):
    """Raised when a provider is temporarily circuit-open."""


@dataclass
class ProviderCircuitState:
    failures: int = 0
    opened_until: float = 0.0
    last_error: str = ""


_CIRCUITS: dict[str, ProviderCircuitState] = {}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def provider_retry_attempts() -> int:
    return max(1, _env_int("PROVIDER_RETRY_ATTEMPTS", 1))


def provider_retry_backoff_seconds() -> float:
    return max(0.0, _env_float("PROVIDER_RETRY_BACKOFF_SECONDS", 0.0))


def provider_circuit_threshold() -> int:
    return max(1, _env_int("PROVIDER_CIRCUIT_BREAKER_THRESHOLD", 3))


def provider_circuit_cooldown_seconds() -> float:
    return max(0.0, _env_float("PROVIDER_CIRCUIT_BREAKER_COOLDOWN_SECONDS", 60.0))


def clear_provider_circuits(provider: str | None = None) -> None:
    if provider is None:
        _CIRCUITS.clear()
        return
    _CIRCUITS.pop(str(provider), None)


def provider_circuit_state(provider: str) -> dict:
    state = _CIRCUITS.get(str(provider))
    if not state:
        return {"open": False, "failures": 0}
    return {
        "open": state.opened_until > time.time(),
        "failures": state.failures,
        "opened_until": state.opened_until,
        "last_error": state.last_error,
    }


def _ensure_circuit_closed(provider: str) -> None:
    state = _CIRCUITS.get(str(provider))
    if state and state.opened_until > time.time():
        raise ProviderCircuitOpenError(
            f"{provider} circuit open for {max(0.0, state.opened_until - time.time()):.1f}s; last_error={state.last_error[:160]}"
        )


def _record_success(provider: str) -> None:
    _CIRCUITS.pop(str(provider), None)


def _record_failure(provider: str, exc: BaseException) -> None:
    state = _CIRCUITS.setdefault(str(provider), ProviderCircuitState())
    state.failures += 1
    state.last_error = str(exc)[:240]
    if state.failures >= provider_circuit_threshold():
        state.opened_until = time.time() + provider_circuit_cooldown_seconds()


def call_provider_with_resilience(provider: str, func: Callable, args: tuple = (), kwargs: dict | None = None) -> Any:
    _ensure_circuit_closed(provider)
    attempts = provider_retry_attempts()
    last_exc = None
    for attempt in range(attempts):
        try:
            value = func(*args, **(kwargs or {}))
            _record_success(provider)
            return value
        except Exception as exc:
            last_exc = exc
            if attempt < attempts - 1 and provider_retry_backoff_seconds() > 0:
                time.sleep(provider_retry_backoff_seconds() * (attempt + 1))
    _record_failure(provider, last_exc)
    raise last_exc


async def call_provider_with_resilience_async(provider: str, func_or_awaitable, args: tuple = (), kwargs: dict | None = None) -> Any:
    _ensure_circuit_closed(provider)
    attempts = provider_retry_attempts()
    if inspect.isawaitable(func_or_awaitable):
        attempts = 1

    last_exc = None
    for attempt in range(attempts):
        try:
            if inspect.isawaitable(func_or_awaitable):
                value = await func_or_awaitable
            else:
                value = func_or_awaitable(*args, **(kwargs or {}))
                if inspect.isawaitable(value):
                    value = await value
            _record_success(provider)
            return value
        except Exception as exc:
            last_exc = exc
            if attempt < attempts - 1 and provider_retry_backoff_seconds() > 0:
                await asyncio.sleep(provider_retry_backoff_seconds() * (attempt + 1))
    _record_failure(provider, last_exc)
    raise last_exc
