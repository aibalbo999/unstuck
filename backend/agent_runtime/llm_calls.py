"""Single-attempt agent LLM calls.

Retry policy and generation config live in focused sibling modules; this module
keeps the provider call attempt and compatibility re-exports used by older tests.
"""

from __future__ import annotations

import asyncio

from analysis_types import AnalysisContext
from config import LLM_AGENT_CALL_TIMEOUT_SECONDS
from llm_client import KeyRotator, estimate_text_tokens
from llm_response_diagnostics import response_kind
from llm_tool_rate_guard import tool_request_scope
from runtime_events import (
    emit_context_error,
    emit_context_error_async,
    emit_context_event,
    emit_context_event_async,
)
from structured_output_runtime import process_agent_response

from .generation_config import (
    _generate_content,
    _generate_content_async,
    _generate_content_stream_async,
    _response_text,
    build_generation_config, estimate_agent_input_tokens, agent_request_budget_options,
)
from .retry_policy import (
    AgentAuthError,
    AgentConfigurationError,
    AgentMissingModelError,
    AgentRateLimitError,
    AgentRetryableError,
    AgentShortResponseError,
    AgentTransientError,
    _agent_error_category,
    _agent_retry_wait,
    _is_transient_provider_error,
    _log_agent_retry,
    _raise_agent_call_error,
    _retry_log_message,
    make_agent_retry_logger,
)
from .llm_call_events import (
    _key_slot_fields,
    _model_event_fields,
    _record_llm_token_usage,
    _should_stream_llm_response,
    llm_model_call_event,
    llm_model_error_fields,
    llm_model_response_event,
    llm_provider_request_event,
    llm_stream_delta_event,
)


async def _await_with_agent_timeout(coro, *, model_id: str, timeout_seconds: float | None = None):
    """Compatibility timeout seam; tests may monkeypatch the module constant."""
    timeout = float(LLM_AGENT_CALL_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds)
    if timeout <= 0:
        return await coro
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise AgentTransientError(f"LLM timeout after {timeout:.1f}s for model {model_id}") from exc


def _run_agent_once(
    agent_num: int,
    context: AnalysisContext,
    rotator: KeyRotator,
    model_id: str,
    prompt: str,
    quota_default: float = 65,
    timeout_seconds: float | None = None,
) -> str:
    api_key = None
    response = result = None
    try:
        emit_context_event(
            context,
            llm_model_call_event(context, agent_num, model_id, prompt, timeout_seconds=timeout_seconds),
        )
        budget = agent_request_budget_options(agent_num)
        api_key = rotator.get_key(model_id, estimate_agent_input_tokens(agent_num, model_id, prompt), **budget)
        emit_context_event(
            context,
            llm_provider_request_event(
                context,
                agent_num,
                model_id,
                prompt,
                rotator,
                api_key,
                timeout_seconds=timeout_seconds,
            ),
        )
        with tool_request_scope(rotator, api_key, model_id, **budget):
            response = _generate_content(api_key, model_id, agent_num, prompt)
        _record_llm_token_usage(context, agent_num, response)
        result = process_agent_response(agent_num, _response_text(response), context)
        _validate_agent_result(result)
    except Exception as exc:
        emit_context_error(
            context,
            "llm_model_error",
            exc,
            message=f"Agent {agent_num} 模型 {model_id} 呼叫失敗。",
            level="warning",
            error_category=_agent_error_category(exc),
            **llm_model_error_fields(
                context,
                agent_num,
                model_id,
                prompt,
                rotator,
                api_key,
                timeout_seconds=timeout_seconds,
                response=response,
                error=exc,
                result=result,
            ),
        )
        if isinstance(exc, AgentShortResponseError):
            raise
        _raise_agent_call_error(exc, api_key, model_id, rotator, quota_default)

    emit_context_event(
        context,
        llm_model_response_event(
            context,
            agent_num,
            model_id,
            prompt,
            result,
            rotator,
            api_key,
            timeout_seconds=timeout_seconds,
            response=response,
        ),
    )
    return result


async def _run_agent_once_async(
    agent_num: int,
    context: AnalysisContext,
    rotator: KeyRotator,
    model_id: str,
    prompt: str,
    quota_default: float = 1,
    timeout_seconds: float | None = None,
) -> str:
    api_key = None
    response = result = None
    try:
        await emit_context_event_async(
            context,
            llm_model_call_event(context, agent_num, model_id, prompt, timeout_seconds=timeout_seconds),
        )
        budget = agent_request_budget_options(agent_num)
        api_key = await rotator.async_get_key(model_id, estimate_agent_input_tokens(agent_num, model_id, prompt), **budget)
        await emit_context_event_async(
            context,
            llm_provider_request_event(
                context,
                agent_num,
                model_id,
                prompt,
                rotator,
                api_key,
                timeout_seconds=timeout_seconds,
            ),
        )
        async with tool_request_scope(rotator, api_key, model_id, **budget):
            if _should_stream_llm_response(context):
                stream_sequence = 0

                async def on_delta(delta: str) -> None:
                    nonlocal stream_sequence
                    if not delta:
                        return
                    stream_sequence += 1
                    await emit_context_event_async(
                        context,
                        llm_stream_delta_event(
                            context, agent_num, model_id, prompt, delta, stream_sequence,
                            rotator, api_key, timeout_seconds=timeout_seconds,
                        ),
                        store=False,
                    )

                response = await _await_with_agent_timeout(
                    _generate_content_stream_async(api_key, model_id, agent_num, prompt, on_delta=on_delta),
                    model_id=model_id,
                    timeout_seconds=timeout_seconds,
                )
            else:
                response = await _await_with_agent_timeout(
                    _generate_content_async(api_key, model_id, agent_num, prompt),
                    model_id=model_id,
                    timeout_seconds=timeout_seconds,
                )
        _record_llm_token_usage(context, agent_num, response)
        result = process_agent_response(agent_num, _response_text(response), context)
        _validate_agent_result(result)
    except (Exception, asyncio.CancelledError) as exc:
        await emit_context_error_async(
            context,
            "llm_model_error",
            exc,
            message=f"Agent {agent_num} 模型 {model_id} 呼叫失敗。",
            level="warning",
            error_category="cancelled" if isinstance(exc, asyncio.CancelledError) else _agent_error_category(exc),
            **llm_model_error_fields(
                context,
                agent_num,
                model_id,
                prompt,
                rotator,
                api_key,
                timeout_seconds=timeout_seconds,
                response=response,
                error=exc,
                result=result,
            ),
        )
        if isinstance(exc, (AgentShortResponseError, asyncio.CancelledError)):
            raise
        _raise_agent_call_error(exc, api_key, model_id, rotator, quota_default)

    await emit_context_event_async(
        context,
        llm_model_response_event(
            context,
            agent_num,
            model_id,
            prompt,
            result,
            rotator,
            api_key,
            timeout_seconds=timeout_seconds,
            response=response,
        ),
    )
    return result


def _validate_agent_result(result: str) -> None:
    kind = response_kind(result)
    if kind == "empty":
        raise AgentShortResponseError("模型未回傳可用文字，無法形成正式報告段落")
    if kind == "short":
        raise AgentShortResponseError("模型回應過短，無法形成正式報告段落")
