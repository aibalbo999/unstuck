"""Retry/backoff and circuit-breaker helpers for data providers.
Refactored to use `tenacity` for robust Exponential Backoff and pure Python state machine for Circuit Breaking.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from functools import wraps
from typing import Any, Callable

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    AsyncRetrying,
    Retrying
)

class ProviderCircuitOpenError(RuntimeError):
    """Raised when a provider is temporarily circuit-open."""


class CircuitBreaker:
    """A pure-Python Circuit Breaker implementation."""
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0.0
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF-OPEN

    def record_success(self):
        self.failures = 0
        self.state = 'CLOSED'

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = 'OPEN'

    def check_state(self):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF-OPEN'
            else:
                remaining = self.recovery_timeout - (time.time() - self.last_failure_time)
                raise ProviderCircuitOpenError(f"Circuit is OPEN. Fast failing. Retry in {remaining:.1f}s")


# Global dictionary holding circuit breakers per provider
_CIRCUITS: dict[str, CircuitBreaker] = {}

def get_circuit_breaker(provider: str) -> CircuitBreaker:
    if provider not in _CIRCUITS:
        _CIRCUITS[provider] = CircuitBreaker()
    return _CIRCUITS[provider]


def call_provider_with_resilience(provider: str, func: Callable, args: tuple = (), kwargs: dict | None = None) -> Any:
    """Sync wrapper combining Circuit Breaker and Tenacity Retries."""
    breaker = get_circuit_breaker(provider)
    breaker.check_state()

    try:
        for attempt in Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            reraise=True
        ):
            with attempt:
                result = func(*args, **(kwargs or {}))
                breaker.record_success()
                return result
    except Exception as exc:
        breaker.record_failure()
        raise exc


async def call_provider_with_resilience_async(provider: str, func_or_awaitable, args: tuple = (), kwargs: dict | None = None) -> Any:
    """Async wrapper combining Circuit Breaker and Tenacity Retries."""
    breaker = get_circuit_breaker(provider)
    breaker.check_state()

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            reraise=True
        ):
            with attempt:
                if inspect.isawaitable(func_or_awaitable):
                    result = await func_or_awaitable
                else:
                    result = func_or_awaitable(*args, **(kwargs or {}))
                    if inspect.isawaitable(result):
                        result = await result
                breaker.record_success()
                return result
    except Exception as exc:
        breaker.record_failure()
        raise exc
