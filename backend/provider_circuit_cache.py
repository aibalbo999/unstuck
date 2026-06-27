"""SQLite-backed persistence for provider circuit-breaker state."""

from __future__ import annotations

import time
from typing import Protocol


class CircuitLike(Protocol):
    recovery_timeout: float
    failure_threshold: int
    failures: int
    last_failure_time: float
    last_error: str
    state: str


_PERSISTED_CIRCUIT_PREFIX = "provider_circuit:"


def _cache_key(provider: str) -> str:
    return f"{_PERSISTED_CIRCUIT_PREFIX}{provider}"


def load_persisted_circuit(provider: str, breaker: CircuitLike) -> None:
    try:
        from cache_store import get_cache_json

        payload = get_cache_json(_cache_key(provider))
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    opened_until = float(payload.get("opened_until") or 0.0)
    state = str(payload.get("state") or "").upper()
    if state == "OPEN" and opened_until > time.time():
        breaker.state = "OPEN"
        breaker.failures = int(payload.get("failures") or breaker.failure_threshold)
        breaker.last_failure_time = opened_until - breaker.recovery_timeout
        breaker.last_error = str(payload.get("last_error") or "")[:240]


def persist_circuit_state(provider: str, breaker: CircuitLike) -> None:
    opened_until = (
        breaker.last_failure_time + breaker.recovery_timeout
        if breaker.state == "OPEN" and breaker.last_failure_time
        else 0.0
    )
    payload = {
        "state": breaker.state,
        "failures": int(breaker.failures),
        "opened_until": opened_until,
        "last_error": breaker.last_error,
    }
    try:
        from cache_store import set_cache_json

        set_cache_json(_cache_key(provider), payload, ttl_seconds=max(int(breaker.recovery_timeout), 1))
    except Exception:
        return


__all__ = ["load_persisted_circuit", "persist_circuit_state"]
