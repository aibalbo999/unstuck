"""Request-scoped deadlines and cooperative cancellation before key admission."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import math
import time


class KeyAdmissionTimeout(TimeoutError):
    reason_code = "local_admission_wait"

    def __init__(self, model, retry_wait_seconds):
        super().__init__(f"模型 {model} 的本機呼叫配額等待逾時，尚未送出請求。")
        self.model = model
        self.retry_wait_seconds = max(1.0, retry_wait_seconds)


class KeyAdmissionCancelled(Exception):
    def __init__(self, original):
        self.original = original
        super().__init__("模型請求已取消，尚未送出。")


@dataclass
class _Admission:
    model: str
    deadline: float | None
    cancel_check: object
    retry_at: float = 0.0

    def check(self):
        if callable(self.cancel_check):
            try:
                self.cancel_check()
            except Exception as exc:
                raise KeyAdmissionCancelled(exc) from exc
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise KeyAdmissionTimeout(self.model, self.retry_at - time.monotonic())


_active = ContextVar("llm_key_admission", default=None)


@contextmanager
def key_admission_scope(model, timeout_seconds, cancel_check=None):
    timeout = float(timeout_seconds or 0)
    deadline = time.monotonic() + timeout if math.isfinite(timeout) and timeout > 0 else None
    token = _active.set(_Admission(model, deadline, cancel_check))
    try:
        check_key_admission()
        yield
        check_key_admission()
    finally:
        _active.reset(token)


def check_key_admission():
    active = _active.get()
    if active is not None:
        active.check()


def key_wait_intervals(wait):
    """Poll cancellation without re-reserving buckets during one throttle wait."""
    active = _active.get()
    if active is None:
        yield wait
        return
    retry_at = time.monotonic() + wait
    active.retry_at = retry_at
    while True:
        active.check()
        remaining = retry_at - time.monotonic()
        if remaining <= 0:
            return
        if active.deadline is not None:
            remaining = min(remaining, active.deadline - time.monotonic())
        yield min(remaining, 1.0) if callable(active.cancel_check) else remaining


def propagate_admission_cancel(exc):
    if isinstance(exc, KeyAdmissionCancelled):
        raise exc.original from exc
