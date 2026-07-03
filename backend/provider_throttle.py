"""Local pacing and cooldown helpers for external data providers."""

from __future__ import annotations

import asyncio
import os
import time


class ProviderRateLimitOpenError(RuntimeError):
    """Raised when a provider is temporarily rate-limited by local throttling."""


_THROTTLES: dict[str, dict[str, float]] = {}


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except ValueError:
        return max(minimum, default)


def _provider_key(provider: str) -> str:
    return str(provider or "unknown").strip() or "unknown"


def _provider_env_prefix(provider: str) -> str:
    token = "".join(ch if ch.isalnum() else "_" for ch in _provider_key(provider).upper())
    while "__" in token:
        token = token.replace("__", "_")
    return token.strip("_") or "UNKNOWN"


def _provider_env_float(provider: str, suffix: str, default: float, minimum: float = 0.0) -> float:
    provider_name = f"PROVIDER_RATE_LIMIT_{_provider_env_prefix(provider)}_{suffix}"
    if provider_name in os.environ:
        return _env_float(provider_name, default, minimum=minimum)
    return _env_float(f"PROVIDER_RATE_LIMIT_{suffix}", default, minimum=minimum)


def _rate_limit_min_interval_seconds(provider: str) -> float:
    return _provider_env_float(provider, "MIN_INTERVAL_SECONDS", 0.0, minimum=0.0)


def _rate_limit_cooldown_seconds(provider: str) -> float:
    return _provider_env_float(provider, "COOLDOWN_SECONDS", 300.0, minimum=0.0)


def _restricted_status_codes() -> set[int]:
    raw = os.getenv("PROVIDER_RATE_LIMIT_STATUS_CODES", "429,403,402")
    codes: set[int] = set()
    for part in raw.split(","):
        try:
            codes.add(int(part.strip()))
        except ValueError:
            continue
    return codes or {429}


def _throttle_state(provider: str) -> dict[str, float]:
    key = _provider_key(provider)
    if key not in _THROTTLES:
        _THROTTLES[key] = {"last_call_at": 0.0, "cooldown_until": 0.0}
    return _THROTTLES[key]


def enforce_provider_throttle(provider: str) -> None:
    state = _throttle_state(provider)
    now = time.time()
    cooldown_until = float(state.get("cooldown_until") or 0.0)
    if cooldown_until > now:
        remaining = cooldown_until - now
        raise ProviderRateLimitOpenError(f"Provider rate limit cooldown is active. Retry in {remaining:.1f}s")

    min_interval = _rate_limit_min_interval_seconds(provider)
    last_call_at = float(state.get("last_call_at") or 0.0)
    wait_seconds = last_call_at + min_interval - now if min_interval > 0 and last_call_at else 0.0
    if wait_seconds > 0:
        time.sleep(wait_seconds)
        now = time.time()
    state["last_call_at"] = now


async def enforce_provider_throttle_async(provider: str) -> None:
    state = _throttle_state(provider)
    now = time.time()
    cooldown_until = float(state.get("cooldown_until") or 0.0)
    if cooldown_until > now:
        remaining = cooldown_until - now
        raise ProviderRateLimitOpenError(f"Provider rate limit cooldown is active. Retry in {remaining:.1f}s")

    min_interval = _rate_limit_min_interval_seconds(provider)
    last_call_at = float(state.get("last_call_at") or 0.0)
    wait_seconds = last_call_at + min_interval - now if min_interval > 0 and last_call_at else 0.0
    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)
        now = time.time()
    state["last_call_at"] = now


def _exception_status_code(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code is None:
        status_code = getattr(exc, "status_code", None)
    try:
        return int(status_code)
    except (TypeError, ValueError):
        return None


def mark_rate_limit_cooldown(provider: str, exc: BaseException) -> None:
    status_code = _exception_status_code(exc)
    if status_code not in _restricted_status_codes():
        return
    cooldown_seconds = _rate_limit_cooldown_seconds(provider)
    if cooldown_seconds <= 0:
        return
    state = _throttle_state(provider)
    state["cooldown_until"] = max(float(state.get("cooldown_until") or 0.0), time.time() + cooldown_seconds)


def provider_throttle_state(provider: str) -> dict[str, float | bool]:
    """Return current provider throttle state for observability and tests."""
    state = _throttle_state(provider)
    now = time.time()
    cooldown_until = float(state.get("cooldown_until") or 0.0)
    return {
        "open": cooldown_until > now,
        "last_call_at": float(state.get("last_call_at") or 0.0),
        "cooldown_until": cooldown_until,
        "retry_after_seconds": max(0.0, cooldown_until - now),
        "min_interval_seconds": _rate_limit_min_interval_seconds(provider),
    }


def clear_provider_throttles(provider: str | None = None) -> None:
    """Clear one provider throttle or all local provider throttles."""
    if provider is None:
        _THROTTLES.clear()
        return
    _THROTTLES.pop(_provider_key(provider), None)
