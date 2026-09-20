"""Thread-safe local fallback implementations for shared runtime guards."""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime
from typing import Any

from shared_runtime_guard_utils import guard_hash, seconds_until_next_pacific_midnight
from llm_input_capacity import ensure_input_capacity


class LocalFixedWindowRateLimiter:
    """Rolling 60-second admission; the legacy class name remains compatible."""

    def __init__(self):
        self._lock = threading.Lock()
        self._reservations: dict[tuple[str, str], deque] = {}
        self._cooldowns: dict[tuple[str, str], float] = {}
        self._rpd_disabled_until: dict[tuple[str, str], float] = {}
        self._model_circuits: dict[str, float] = {}

    def reserve(
        self,
        api_key: str,
        model: str,
        *,
        rpm_limit: int | float,
        tpm_limit: int | float | None = None,
        estimated_tokens: int = 0,
    ) -> float:
        ensure_input_capacity(model, estimated_tokens, tpm_limit=tpm_limit)
        now = time.time()
        identity = (guard_hash(api_key), guard_hash(model))
        rpm = max(int(rpm_limit), 1)
        tpm = max(int(tpm_limit or 0), 0)
        tokens = max(int(estimated_tokens or 0), 1)
        with self._lock:
            cooldown_until = self._cooldowns.get(identity, 0.0)
            if cooldown_until > now:
                return cooldown_until - now
            self._cooldowns.pop(identity, None)
            events = self._active_events(identity, now)
            count, total = len(events), sum(amount for _, amount in events)
            if count + 1 > rpm or (tpm > 0 and total + tokens > tpm):
                for stamp, amount in events:
                    count -= 1
                    total -= amount
                    if count + 1 <= rpm and (tpm <= 0 or total + tokens <= tpm):
                        return max(stamp + 60.0 - now, 0.001)
                return 60.0
            self._append_event(events, now, tokens)
            return 0.0

    def _active_events(self, identity, now):
        events = self._reservations.setdefault(identity, deque())
        while events and events[0][0] <= now - 60.0:
            events.popleft()
        if len(self._reservations) > 2_048:
            self._reservations = {key: value for key, value in self._reservations.items()
                                  if (value and value[-1][0] > now - 60.0) or key == identity}
        return events

    @staticmethod
    def _append_event(events, now, tokens):
        # A backward wall-clock adjustment must not expire newer requests early.
        events.append((max(now, events[-1][0] if events else now), tokens))

    def remember_reservation(self, api_key: str, model: str, estimated_tokens: int) -> None:
        """Mirror an already admitted shared request without making a second decision."""
        now = time.time()
        identity = (guard_hash(api_key), guard_hash(model))
        with self._lock:
            self._append_event(self._active_events(identity, now), now, max(int(estimated_tokens or 0), 1))

    def cooldown_wait(self, api_key: str, model: str) -> float:
        identity = (guard_hash(api_key), guard_hash(model))
        with self._lock:
            return max(self._cooldowns.get(identity, 0.0) - time.time(), 0.0)

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

    def open_model_circuit(
        self,
        model: str,
        *,
        cooldown_seconds: float | None = None,
        opened_until: float | None = None,
    ) -> float:
        target = float(opened_until or 0.0)
        if target <= time.time():
            target = time.time() + max(float(cooldown_seconds or 900.0), 1.0)
        identity = guard_hash(model)
        with self._lock:
            self._model_circuits[identity] = max(self._model_circuits.get(identity, 0.0), target)
        return max(target - time.time(), 0.0)

    def model_circuit_wait(self, model: str) -> float:
        identity = guard_hash(model)
        now = time.time()
        with self._lock:
            opened_until = self._model_circuits.get(identity, 0.0)
            if opened_until <= now:
                self._model_circuits.pop(identity, None)
                return 0.0
            return opened_until - now

    def is_model_circuit_open(self, model: str) -> bool:
        return self.model_circuit_wait(model) > 0.0


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
