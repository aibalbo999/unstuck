"""Per-job LLM model retry, timeout, and circuit policy."""

from __future__ import annotations

import time
from dataclasses import dataclass

from config import (
    FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS,
    LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS,
    LLM_MODEL_CIRCUIT_THRESHOLD,
    PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS,
    PRIMARY_MODEL_QUOTA_MAX_ATTEMPTS,
    PRIMARY_MODEL_TRANSIENT_MAX_ATTEMPTS,
)

from .retry_policy import AgentRateLimitError, AgentShortResponseError, AgentTransientError


MODEL_CIRCUITS_KEY = "_llm_model_circuits"


@dataclass
class ModelAttemptPolicy:
    transient_attempts: int
    quota_attempts: int
    short_response_attempts: int


def model_attempt_policy(model_index: int, has_fallback: bool, max_retries: int, key_count: int) -> ModelAttemptPolicy:
    """Return exception-aware attempt limits for the current model route."""
    key_count = max(1, int(key_count or 1))
    if model_index == 0 and has_fallback:
        return ModelAttemptPolicy(
            transient_attempts=max(1, int(PRIMARY_MODEL_TRANSIENT_MAX_ATTEMPTS)),
            quota_attempts=max(1, min(key_count, int(PRIMARY_MODEL_QUOTA_MAX_ATTEMPTS))),
            short_response_attempts=max(1, int(max_retries or 1)),
        )
    return ModelAttemptPolicy(
        transient_attempts=max(1, int(max_retries or 1)),
        quota_attempts=max(1, int(max_retries or 1)),
        short_response_attempts=max(1, int(max_retries or 1)),
    )


def should_stop_retry(retry_state, policy: ModelAttemptPolicy) -> bool:
    """Tenacity stop predicate that treats quota and transient failures differently."""
    attempt = int(getattr(retry_state, "attempt_number", 1) or 1)
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, AgentRateLimitError):
        return attempt >= policy.quota_attempts
    if isinstance(exc, AgentShortResponseError):
        return attempt >= policy.short_response_attempts
    if isinstance(exc, AgentTransientError):
        return attempt >= policy.transient_attempts
    return attempt >= policy.transient_attempts


def timeout_for_model_call(model_index: int, has_fallback: bool) -> float:
    """Use the shortest primary timeout when a fallback route exists."""
    if model_index == 0 and has_fallback:
        return max(1.0, float(PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS or 0))
    return max(0.0, float(FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS or 0))


def is_model_circuit_open(context: dict, model_id: str) -> bool:
    state = _model_circuit_state(context).get(model_id)
    if not state:
        return False
    opened_until = float(state.get("opened_until") or 0.0)
    if opened_until > time.time():
        return True
    _model_circuit_state(context).pop(model_id, None)
    return False


def record_model_success(context: dict, model_id: str) -> None:
    _model_circuit_state(context).pop(model_id, None)


def record_model_failure(context: dict, model_id: str, exc: BaseException) -> dict:
    state = _model_circuit_state(context).setdefault(model_id, {"failures": 0, "opened_until": 0.0, "last_error": ""})
    state["failures"] = int(state.get("failures") or 0) + 1
    state["last_error"] = str(exc)[:240]
    if state["failures"] >= max(1, int(LLM_MODEL_CIRCUIT_THRESHOLD)):
        state["opened_until"] = time.time() + max(1.0, float(LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS or 1))
    return dict(state)


def model_circuit_summary(context: dict) -> dict:
    now = time.time()
    summary = {}
    for model_id, state in _model_circuit_state(context).items():
        opened_until = float(state.get("opened_until") or 0.0)
        summary[model_id] = {
            "open": opened_until > now,
            "failures": int(state.get("failures") or 0),
            "opened_until": opened_until,
            "last_error": state.get("last_error") or "",
        }
    return summary


def _model_circuit_state(context: dict) -> dict:
    circuits = context.setdefault(MODEL_CIRCUITS_KEY, {})
    return circuits if isinstance(circuits, dict) else {}
