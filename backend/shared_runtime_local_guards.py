"""Thread-safe local fallback implementations for shared runtime guards."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any

from shared_runtime_guard_utils import guard_hash, seconds_until_next_pacific_midnight


class LocalFixedWindowRateLimiter:
    """Thread-safe fallback that preserves API quotas when Redis is unavailable."""

    def __init__(self):
        self._lock = threading.Lock()
        self._windows: dict[tuple[str, str, int], dict[str, float]] = {}
        self._cooldowns: dict[tuple[str, str], float] = {}
        self._rpd_disabled_until: dict[tuple[str, str], float] = {}

    def reserve(
        self,
        api_key: str,
        model: str,
        *,
        rpm_limit: int | float,
        tpm_limit: int | float | None = None,
        estimated_tokens: int = 0,
    ) -> float:
        now = time.time()
        identity = (guard_hash(api_key), guard_hash(model))
        window = int(now // 60)
        window_key = (*identity, window)
        with self._lock:
            cooldown_until = self._cooldowns.get(identity, 0.0)
            if cooldown_until > now:
                return cooldown_until - now
            self._cooldowns.pop(identity, None)
            counters = self._windows.setdefault(window_key, {"rpm": 0.0, "tpm": 0.0})
            rpm = max(int(rpm_limit), 1)
            tpm = max(int(tpm_limit or 0), 0)
            tokens = max(int(estimated_tokens or 0), 1)
            if counters["rpm"] >= rpm or (tpm > 0 and counters["tpm"] + tokens > tpm):
                return max(60.0 - (now % 60.0), 0.001)
            counters["rpm"] += 1
            if tpm > 0:
                counters["tpm"] += tokens
            if len(self._windows) > 2_048:
                self._windows = {key: value for key, value in self._windows.items() if key[2] >= window - 1}
            return 0.0

    def penalize(self, api_key: str, model: str, wait_seconds: float) -> None:
        identity = (guard_hash(api_key), guard_hash(model))
        with self._lock:
            self._cooldowns[identity] = max(
                self._cooldowns.get(identity, 0.0),
                time.time() + max(float(wait_seconds), 0.001),
            )

    def disable_rpd_until_reset(self, api_key: str, model: str, *, now: datetime | None = None) -> float:
        wait_seconds = seconds_until_next_pacific_midnight(now)
        base_now = now.timestamp() if now is not None else time.time()
        identity = (guard_hash(api_key), guard_hash(model))
        with self._lock:
            self._rpd_disabled_until[identity] = max(
                self._rpd_disabled_until.get(identity, 0.0),
                base_now + wait_seconds,
            )
        return wait_seconds

    def rpd_disabled_wait(self, api_key: str, model: str, *, now: datetime | None = None) -> float:
        base_now = now.timestamp() if now is not None else time.time()
        identity = (guard_hash(api_key), guard_hash(model))
        with self._lock:
            disabled_until = self._rpd_disabled_until.get(identity, 0.0)
            if disabled_until <= base_now:
                self._rpd_disabled_until.pop(identity, None)
                return 0.0
            return disabled_until - base_now


class LocalProviderCircuitStore:
    """Thread-safe local provider circuit used when Redis cannot be reached."""

    def __init__(self):
        self._lock = threading.Lock()
        self._states: dict[str, dict[str, Any]] = {}

    def state(self, provider: str) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            state = dict(self._states.get(provider, {}))
        opened_until = float(state.get("opened_until") or 0.0)
        return {
            "open": opened_until > now, "failures": int(state.get("failures") or 0),
            "opened_until": opened_until, "last_error": str(state.get("last_error") or ""),
        }

    def record_success(self, provider: str) -> None:
        with self._lock:
            self._states.pop(provider, None)

    def record_failure(self, provider: str, error: str, threshold: int, cooldown_seconds: float) -> None:
        with self._lock:
            state = self._states.setdefault(provider, {"failures": 0, "opened_until": 0.0})
            state["failures"] = int(state["failures"]) + 1
            state["last_error"] = str(error or "")[:240]
            if state["failures"] >= max(int(threshold), 1):
                state["opened_until"] = time.time() + max(float(cooldown_seconds), 1.0)

    def clear(self, provider: str | None = None) -> None:
        with self._lock:
            if provider is None:
                self._states.clear()
            else:
                self._states.pop(provider, None)
