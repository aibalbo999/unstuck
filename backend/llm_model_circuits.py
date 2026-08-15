"""Job-local model circuit state shared by concurrent agent calls."""

from __future__ import annotations

import threading
import time

from config import LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS


class ModelCircuitStore:
    """Keep temporary model circuit state isolated to one rotator/job."""

    def __init__(self) -> None:
        self._opened_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def open(self, model: str, *, cooldown_seconds: float | None = None, opened_until: float | None = None) -> None:
        target = float(opened_until or 0.0)
        if target <= time.time():
            target = time.time() + max(
                1.0,
                float(cooldown_seconds if cooldown_seconds is not None else LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS or 1),
            )
        with self._lock:
            self._opened_until[model] = max(float(self._opened_until.get(model) or 0.0), target)

    def is_open(self, model: str) -> bool:
        now = time.time()
        with self._lock:
            opened_until = float(self._opened_until.get(model) or 0.0)
            if opened_until <= now:
                self._opened_until.pop(model, None)
                return False
            return True
