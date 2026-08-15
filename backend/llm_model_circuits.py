"""Job-local model circuit state shared by concurrent agent calls."""

from __future__ import annotations

import threading
import time

from config import LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS


class ModelCircuitOpenError(RuntimeError):
    """Raised before a provider call while the model quota circuit is open."""

    def __init__(self, model: str, retry_wait_seconds: float):
        super().__init__(f"模型 {model} 的 quota circuit 已開啟，約 {retry_wait_seconds:.1f} 秒後再試。")
        self.model = model
        self.retry_wait_seconds = retry_wait_seconds


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


def open_shared_model_circuit(limiter, model: str, *, cooldown_seconds=None, opened_until=None) -> None:
    opener = getattr(limiter, "open_model_circuit", None) if limiter else None
    if callable(opener):
        opener(model, cooldown_seconds=cooldown_seconds, opened_until=opened_until)


def shared_model_circuit_wait(limiter, model: str) -> float:
    waiter = getattr(limiter, "model_circuit_wait", None) if limiter else None
    return max(float(waiter(model) or 0.0), 0.0) if callable(waiter) else 0.0


def is_shared_model_circuit_open(limiter, model: str) -> bool:
    return shared_model_circuit_wait(limiter, model) > 0.0
