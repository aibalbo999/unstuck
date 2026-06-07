"""Retry errors, waits, and logging for agent model calls."""

from __future__ import annotations

from typing import Optional

from tenacity import wait_exponential

from analysis_types import AnalysisContext
from llm_client import (
    KeyRotator,
    describe_quota_or_rate_error,
    is_missing_model_error,
    is_quota_or_rate_error,
    retry_delay_seconds,
)
from runtime_events import emit_context_event, emit_log, make_runtime_event


class AgentRetryableError(Exception):
    """Base class for errors that should be retried by tenacity."""


class AgentShortResponseError(AgentRetryableError):
    """Raised when the model returns content too short to be report-ready."""


class AgentTransientError(AgentRetryableError):
    """Raised for provider-side transient failures such as 503/timeouts."""


class AgentRateLimitError(AgentRetryableError):
    """Raised for quota/rate-limit responses with provider-aware wait time."""

    def __init__(self, detail: str, retry_wait_seconds: float, key_cooldown_seconds: float):
        super().__init__(detail)
        self.detail = detail
        self.retry_wait_seconds = retry_wait_seconds
        self.key_cooldown_seconds = key_cooldown_seconds


class AgentMissingModelError(Exception):
    """Raised when the selected model is unavailable and should not be retried."""


BASE_AGENT_RETRY_WAIT = wait_exponential(multiplier=2, min=1, max=30)


def _is_transient_provider_error(error_msg: str) -> bool:
    normalized = (error_msg or "").lower()
    return any(
        marker in normalized
        for marker in [
            "503",
            "500",
            "unavailable",
            "deadline",
            "timeout",
            "temporarily",
            "connection",
        ]
    )


def _agent_retry_wait(retry_state) -> float:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, AgentRateLimitError):
        return max(float(exc.retry_wait_seconds), 1.0)
    return BASE_AGENT_RETRY_WAIT(retry_state)


def _retry_log_message(retry_state) -> tuple[str, str, str]:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    sleep = getattr(retry_state.next_action, "sleep", 0) or 0
    attempt = retry_state.attempt_number
    if isinstance(exc, AgentRateLimitError):
        return (
            "llm_rate_limit_retry",
            "warning",
            f"配額/速率限制：{exc.detail[:150]}... "
            f"該 Key 冷卻 {exc.key_cooldown_seconds:.1f} 秒，{sleep:.1f} 秒後改試其他 Key（第 {attempt} 次）",
        )
    if isinstance(exc, AgentShortResponseError):
        return ("llm_short_response_retry", "warning", f"回應過短，等待 {sleep:.1f} 秒後重試（第 {attempt} 次）")
    return ("llm_transient_retry", "warning", f"暫時性錯誤：{str(exc)[:120]}... 等待 {sleep:.1f} 秒後重試（第 {attempt} 次）")


def _log_agent_retry(retry_state):
    _phase, _level, message = _retry_log_message(retry_state)
    emit_log(f"    {'⏭️' if '配額' in message else '⚠️' if '回應過短' in message else '❌'}  {message}")


def make_agent_retry_logger(context: AnalysisContext, agent_num: int, model_id: str):
    def _logger(retry_state):
        phase, level, message = _retry_log_message(retry_state)
        emit_log(f"    {'⏭️' if phase == 'llm_rate_limit_retry' else '⚠️' if phase == 'llm_short_response_retry' else '❌'}  {message}")
        emit_context_event(
            context,
            make_runtime_event(
                "status",
                phase=phase,
                level=level,
                message=message,
                current=(context.get("agent_positions", {}) or {}).get(agent_num, agent_num),
                total=context.get("agent_total"),
                name=f"Agent {agent_num}",
                agent_num=agent_num,
                pipeline_id=context.get("pipeline_id"),
                pipeline_label=context.get("pipeline_label"),
                metadata={
                    "model_id": model_id,
                    "attempt": getattr(retry_state, "attempt_number", None),
                    "sleep_seconds": getattr(getattr(retry_state, "next_action", None), "sleep", None),
                    "error_kind": (retry_state.outcome.exception().__class__.__name__ if retry_state.outcome and retry_state.outcome.exception() else None),
                },
            ),
        )
    return _logger


def _raise_agent_call_error(exc: Exception, api_key: Optional[str], model_id: str, rotator: KeyRotator, quota_default: float):
    error_msg = str(exc)
    if is_quota_or_rate_error(error_msg):
        key_cooldown = retry_delay_seconds(exc, default=quota_default)
        if api_key:
            rotator.penalize(api_key, model_id, key_cooldown)
        retry_wait = 1.0 if len(getattr(rotator, "keys", []) or []) > 1 else key_cooldown
        raise AgentRateLimitError(describe_quota_or_rate_error(exc), retry_wait, key_cooldown) from exc

    if is_missing_model_error(error_msg):
        raise AgentMissingModelError(error_msg) from exc

    if _is_transient_provider_error(error_msg):
        raise AgentTransientError(error_msg) from exc

    raise AgentTransientError(error_msg) from exc


def _agent_error_category(exc: Exception) -> str:
    error_msg = str(exc)
    if is_quota_or_rate_error(error_msg):
        return "quota"
    if is_missing_model_error(error_msg):
        return "missing_model"
    if _is_transient_provider_error(error_msg):
        return "timeout" if "timeout" in error_msg.lower() or "deadline" in error_msg.lower() else "provider"
    return "provider"
