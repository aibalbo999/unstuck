"""429-only guard for final-audit repair fallback."""

from __future__ import annotations

import os
import re
import time


_HTTP_429_RE = re.compile(r"(?:\b429\b|too many requests|resource_exhausted)", re.IGNORECASE)
_REPAIR_429_BREAKERS: dict[int, dict] = {}


def is_repair_429_error(message: object) -> bool:
    """Return true only for quota/rate-limit failures that map to HTTP 429."""
    return bool(_HTTP_429_RE.search(str(message or "")))


def _threshold() -> int:
    try:
        return max(1, int(os.getenv("REPAIR_429_CIRCUIT_BREAKER_THRESHOLD", "1")))
    except ValueError:
        return 1


def _cooldown_seconds() -> int:
    try:
        return max(1, int(os.getenv("REPAIR_429_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "900")))
    except ValueError:
        return 900


def _now() -> float:
    return time.time()


def repair_429_circuit_state(agent_num: int) -> dict:
    state = dict(_REPAIR_429_BREAKERS.get(int(agent_num), {}))
    if not state:
        return {"open": False, "failures": 0}
    opened_at = float(state.get("opened_at") or 0)
    if state.get("open") and _now() - opened_at > _cooldown_seconds():
        _REPAIR_429_BREAKERS.pop(int(agent_num), None)
        return {"open": False, "failures": 0}
    return state


def record_repair_429_failure(agent_num: int, message: object = "") -> dict:
    agent_key = int(agent_num)
    state = repair_429_circuit_state(agent_key)
    failures = int(state.get("failures") or 0) + 1
    open_now = failures >= _threshold()
    updated = {
        "open": open_now,
        "failures": failures,
        "last_error": str(message or "")[:240],
        "last_failure_at": _now(),
    }
    if open_now:
        updated["opened_at"] = updated["last_failure_at"]
    _REPAIR_429_BREAKERS[agent_key] = updated
    return dict(updated)


def clear_repair_429_circuit(agent_num: int | None = None) -> None:
    if agent_num is None:
        _REPAIR_429_BREAKERS.clear()
    else:
        _REPAIR_429_BREAKERS.pop(int(agent_num), None)
