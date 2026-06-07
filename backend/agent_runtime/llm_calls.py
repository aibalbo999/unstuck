# Split from legacy_agent_runner.py. Keep this module logic-only; root compatibility lives in backend/agent_runner.py.

import asyncio
from typing import Optional

from google.genai import types
from tenacity import retry_if_exception_type, wait_exponential

from analysis_types import AnalysisContext
from config import LLM_AGENT_CALL_TIMEOUT_SECONDS
from llm_client import (
    KeyRotator,
    describe_quota_or_rate_error,
    estimate_text_tokens,
    generate_content,
    generate_content_async,
    is_missing_model_error,
    is_quota_or_rate_error,
    response_text,
    retry_delay_seconds,
)
from runtime_events import emit_context_error, emit_context_error_async, emit_context_event, emit_context_event_async, emit_log, make_runtime_event
from structured_outputs import (
    STRUCTURED_AGENT_INSTRUCTIONS,
    get_structured_response_schema,
    process_agent_response,
)

from .prompt_config import SYSTEM_PROMPTS
from .routing import get_agent_function_tools

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


def _generate_config_supports(field_name: str) -> bool:
    fields = getattr(types.GenerateContentConfig, "model_fields", {}) or {}
    return field_name in fields


def build_generation_config(agent_num: int, system_instruction: Optional[str] = None):
    """Build Google GenAI generation config, using JSON MIME type where supported."""
    config_kwargs = {
        "temperature": 0.7,
        "top_p": 0.95,
        "max_output_tokens": 8192,
    }
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if agent_num in STRUCTURED_AGENT_INSTRUCTIONS:
        config_kwargs["response_mime_type"] = "application/json"
        response_schema = get_structured_response_schema(agent_num)
        if response_schema and _generate_config_supports("response_schema"):
            config_kwargs["response_schema"] = response_schema
    function_tools = get_agent_function_tools(agent_num)
    if function_tools:
        config_kwargs["tools"] = function_tools
        config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(maximum_remote_calls=6)

    try:
        return types.GenerateContentConfig(**config_kwargs)
    except TypeError:
        if "response_schema" in config_kwargs:
            config_kwargs.pop("response_schema", None)
            try:
                return types.GenerateContentConfig(**config_kwargs)
            except TypeError:
                pass
        config_kwargs.pop("response_mime_type", None)
        config_kwargs.pop("automatic_function_calling", None)
        config_kwargs.pop("tools", None)
        return types.GenerateContentConfig(**config_kwargs)


def _response_text(response) -> str:
    return response_text(response)


def _generate_content(api_key: str, model_id: str, agent_num: int, prompt: str):
    config = build_generation_config(agent_num, SYSTEM_PROMPTS[agent_num])
    return generate_content(api_key, model_id, prompt, config)


async def _generate_content_async(api_key: str, model_id: str, agent_num: int, prompt: str):
    config = build_generation_config(agent_num, SYSTEM_PROMPTS[agent_num])
    return await generate_content_async(api_key, model_id, prompt, config)


async def _await_with_agent_timeout(coro, *, model_id: str):
    timeout = float(LLM_AGENT_CALL_TIMEOUT_SECONDS or 0)
    if timeout <= 0:
        return await coro
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise AgentTransientError(f"LLM timeout after {timeout:.1f}s for model {model_id}") from exc


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


def _run_agent_once(
    agent_num: int,
    context: AnalysisContext,
    rotator: KeyRotator,
    model_id: str,
    prompt: str,
    quota_default: float = 65,
) -> str:
    api_key = None
    try:
        emit_context_event(
            context,
            make_runtime_event(
                "status",
                phase="llm_model_call",
                level="info",
                message=f"Agent {agent_num} 正在呼叫模型 {model_id}...",
                current=(context.get("agent_positions", {}) or {}).get(agent_num, agent_num),
                total=context.get("agent_total"),
                name=f"Agent {agent_num}",
                agent_num=agent_num,
                pipeline_id=context.get("pipeline_id"),
                pipeline_label=context.get("pipeline_label"),
                metadata={"model_id": model_id, "estimated_tokens": estimate_text_tokens(prompt, response_budget=8192)},
            ),
        )
        api_key = rotator.get_key(model_id, estimate_text_tokens(prompt, response_budget=8192))
        response = _generate_content(api_key, model_id, agent_num, prompt)
        result = process_agent_response(agent_num, _response_text(response), context)
    except Exception as exc:
        emit_context_error(
            context,
            "llm_model_error",
            exc,
            message=f"Agent {agent_num} 模型 {model_id} 呼叫失敗。",
            level="warning",
            error_category=_agent_error_category(exc),
            current=(context.get("agent_positions", {}) or {}).get(agent_num, agent_num),
            total=context.get("agent_total"),
            name=f"Agent {agent_num}",
            agent_num=agent_num,
            pipeline_id=context.get("pipeline_id"),
            pipeline_label=context.get("pipeline_label"),
            metadata={"model_id": model_id},
        )
        _raise_agent_call_error(exc, api_key, model_id, rotator, quota_default)

    if result and len(result) > 100:
        emit_context_event(
            context,
            make_runtime_event(
                "status",
                phase="llm_model_response",
                level="info",
                message=f"Agent {agent_num} 模型 {model_id} 回應完成。",
                current=(context.get("agent_positions", {}) or {}).get(agent_num, agent_num),
                total=context.get("agent_total"),
                name=f"Agent {agent_num}",
                agent_num=agent_num,
                pipeline_id=context.get("pipeline_id"),
                pipeline_label=context.get("pipeline_label"),
                metadata={"model_id": model_id, "output_chars": len(result)},
            ),
        )
        return result
    raise AgentShortResponseError("模型回應過短，無法形成正式報告段落")


async def _run_agent_once_async(
    agent_num: int,
    context: AnalysisContext,
    rotator: KeyRotator,
    model_id: str,
    prompt: str,
    quota_default: float = 1,
) -> str:
    api_key = None
    try:
        await emit_context_event_async(
            context,
            make_runtime_event(
                "status",
                phase="llm_model_call",
                level="info",
                message=f"Agent {agent_num} 正在呼叫模型 {model_id}...",
                current=(context.get("agent_positions", {}) or {}).get(agent_num, agent_num),
                total=context.get("agent_total"),
                name=f"Agent {agent_num}",
                agent_num=agent_num,
                pipeline_id=context.get("pipeline_id"),
                pipeline_label=context.get("pipeline_label"),
                metadata={
                    "model_id": model_id,
                    "estimated_tokens": estimate_text_tokens(prompt, response_budget=8192),
                    "timeout_seconds": float(LLM_AGENT_CALL_TIMEOUT_SECONDS or 0),
                },
            ),
        )
        api_key = await rotator.async_get_key(model_id, estimate_text_tokens(prompt, response_budget=8192))
        response = await _await_with_agent_timeout(
            _generate_content_async(api_key, model_id, agent_num, prompt),
            model_id=model_id,
        )
        result = process_agent_response(agent_num, _response_text(response), context)
    except Exception as exc:
        await emit_context_error_async(
            context,
            "llm_model_error",
            exc,
            message=f"Agent {agent_num} 模型 {model_id} 呼叫失敗。",
            level="warning",
            error_category=_agent_error_category(exc),
            current=(context.get("agent_positions", {}) or {}).get(agent_num, agent_num),
            total=context.get("agent_total"),
            name=f"Agent {agent_num}",
            agent_num=agent_num,
            pipeline_id=context.get("pipeline_id"),
            pipeline_label=context.get("pipeline_label"),
            metadata={"model_id": model_id},
        )
        _raise_agent_call_error(exc, api_key, model_id, rotator, quota_default)

    if result and len(result) > 100:
        await emit_context_event_async(
            context,
            make_runtime_event(
                "status",
                phase="llm_model_response",
                level="info",
                message=f"Agent {agent_num} 模型 {model_id} 回應完成。",
                current=(context.get("agent_positions", {}) or {}).get(agent_num, agent_num),
                total=context.get("agent_total"),
                name=f"Agent {agent_num}",
                agent_num=agent_num,
                pipeline_id=context.get("pipeline_id"),
                pipeline_label=context.get("pipeline_label"),
                metadata={"model_id": model_id, "output_chars": len(result)},
            ),
        )
        return result
    raise AgentShortResponseError("模型回應過短，無法形成正式報告段落")
