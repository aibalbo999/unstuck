"""Admission around actual Google calls; observed congestion is not a quota claim."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import threading
import uuid

import config
from llm_errors import is_requests_per_day_error, retry_delay_seconds
from llm_model_circuits import ModelCircuitOpenError
from llm_provider_routes import split_model_provider

_store = None
_store_lock = threading.Lock()
_active = ContextVar("llm_provider_congestion_attempt", default=None)


class ProviderCongestionError(ModelCircuitOpenError):
    reason_code = "observed_model_congestion"


def _identity(model_id):
    provider, model = split_model_provider(model_id)
    if provider != "google":
        return None
    return "google:" + model.removeprefix("models/")


def _enabled():
    return bool(getattr(config, "LLM_CONGESTION_GUARD_ENABLED", False))


def _get_store():
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                from llm_congestion_store import CongestionStore
                from shared_runtime_guards import create_redis_client, shared_guard_enabled
                _store = CongestionStore(
                    redis_client=create_redis_client("LLM_RATE_LIMIT_BACKEND"),
                    shared_required=shared_guard_enabled("LLM_RATE_LIMIT_BACKEND"),
                )
    return _store


def congestion_wait(model_id):
    """Read-only availability check: never claim or renew a recovery probe."""
    model = _identity(model_id)
    if not _enabled() or model is None:
        return 0.0
    return max(0.0, float(_get_store().operate(model, "peek")["wait"]))


def _is_actual_429(exc):
    for value in (getattr(exc, "status_code", None), getattr(exc, "code", None),
                  getattr(getattr(exc, "response", None), "status_code", None)):
        try:
            if int(value) == 429:
                return not is_requests_per_day_error(exc)
        except (TypeError, ValueError, OverflowError):
            pass
    return False


@dataclass
class _Attempt:
    store: object
    model: str
    key_hash: str
    owner: str
    generation: int
    lease: float
    completed: bool = False

    def finish(self, error=None):
        if self.completed:
            return
        self.completed = True
        action = "success" if error is None else "failure" if _is_actual_429(error) else "release"
        delay = max(0.0, retry_delay_seconds(error, default=0)) if action == "failure" else 0.0
        self.store.operate(self.model, action, key_hash=self.key_hash, owner=self.owner,
                           generation=self.generation, delay=delay, lease=self.lease)

    def close(self):
        if not self.completed:
            self.completed = True
            self.store.operate(self.model, "release", key_hash=self.key_hash, owner=self.owner,
                               generation=self.generation, lease=self.lease)


@contextmanager
def provider_attempt_scope(model_id, api_key, *, record_outcome=True):
    """Join nested Agent/transport scopes and count only raw provider outcomes.

    Outer Agent scopes reserve admission before request telemetry. Transport scopes
    count success only after a complete response; cache hits never clear a probe.
    """
    model = _identity(model_id)
    if not _enabled() or model is None:
        yield None
        return
    key_hash = hashlib.sha256(str(api_key).encode()).hexdigest()
    parent = _active.get()
    joined = (parent is not None and not parent.completed
              and parent.model == model and parent.key_hash == key_hash)
    token = None
    if joined:
        attempt = parent
    else:
        store = _get_store()
        owner = uuid.uuid4().hex
        lease = max(60.0, *(float(getattr(config, name, 0) or 0) for name in (
            "LLM_AGENT_CALL_TIMEOUT_SECONDS", "PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS",
            "FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS"))) + 30.0
        result = store.operate(model, "admit", key_hash=key_hash, owner=owner, lease=lease)
        if not result["admitted"]:
            raise ProviderCongestionError(model_id, max(float(result["wait"]), 1.0))
        attempt = _Attempt(store, model, key_hash, owner, result["generation"], lease)
        token = _active.set(attempt)
    try:
        yield attempt
    except BaseException as exc:
        if record_outcome:
            attempt.finish(exc)
        raise
    else:
        if record_outcome:
            attempt.finish()
    finally:
        if not joined:
            try:
                attempt.close()
            finally:
                _active.reset(token)
