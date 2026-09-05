"""Runtime event helpers for single-attempt LLM calls."""

from __future__ import annotations

from analysis_types import AnalysisContext
from llm_client import estimate_text_tokens
from llm_response_diagnostics import response_diagnostics, response_kind
from llm_errors import extract_quota_details
from llm_input_capacity import InputCapacityExceededError
from runtime_events import RUNTIME_EVENT_CALLBACK_KEY, make_runtime_event
from .generation_config import estimate_agent_input_tokens
from .llm_call_metadata import _key_slot_fields, _record_llm_token_usage


def _model_event_fields(context: AnalysisContext, agent_num: int, model_id: str, prompt: str, **metadata) -> dict:
    return {
        "current": (context.get("agent_positions", {}) or {}).get(agent_num, agent_num),
        "total": context.get("agent_total"),
        "name": f"Agent {agent_num}",
        "agent_num": agent_num,
        "pipeline_id": context.get("pipeline_id"),
        "pipeline_label": context.get("pipeline_label"),
        "metadata": {
            "model_id": model_id,
            "estimated_tokens": estimate_text_tokens(prompt, response_budget=8192),
            "estimated_input_tokens": estimate_agent_input_tokens(agent_num, model_id, prompt),
            "input_estimate_basis": "mixed_language_with_system_and_schema",
            **{key: value for key, value in metadata.items() if value is not None},
        },
    }


def _should_stream_llm_response(context: AnalysisContext) -> bool:
    return bool((context or {}).get(RUNTIME_EVENT_CALLBACK_KEY))


def llm_model_call_event(context: AnalysisContext, agent_num: int, model_id: str, prompt: str, *, timeout_seconds) -> dict:
    return make_runtime_event(
        "status",
        phase="llm_model_call",
        level="info",
        message=f"Agent {agent_num} 正在呼叫模型 {model_id}...",
        **_model_event_fields(context, agent_num, model_id, prompt, timeout_seconds=timeout_seconds),
    )


def llm_provider_request_event(
    context: AnalysisContext, agent_num: int, model_id: str, prompt: str, rotator, api_key: str | None, *, timeout_seconds
) -> dict:
    return make_runtime_event(
        "status",
        phase="llm_provider_request",
        level="info",
        message=f"Agent {agent_num} 已取得 API key，送出模型請求。",
        **_model_event_fields(
            context,
            agent_num,
            model_id,
            prompt,
            timeout_seconds=timeout_seconds,
            **_key_slot_fields(rotator, api_key),
        ),
    )


def llm_model_error_fields(
    context: AnalysisContext, agent_num: int, model_id: str, prompt: str, rotator, api_key: str | None, *,
    timeout_seconds, response=None, error=None, result=None,
) -> dict:
    diagnostics = response_diagnostics(response, error=error)
    if diagnostics:
        _record_llm_token_usage(context, agent_num, {"usage": diagnostics.get("usage")})
    return _model_event_fields(
        context, agent_num, model_id, prompt,
        timeout_seconds=timeout_seconds,
        response_diagnostics=diagnostics,
        response_kind=response_kind(result) if result is not None else None,
        output_chars=len(result) if result is not None else None,
        # Provider exception strings can embed request bodies and credentials.
        error_message="LLM call failed." if error is not None else None,
        provider_quota=extract_quota_details(error) if error is not None else None,
        input_capacity={"estimated_input_tokens": error.estimated_input_tokens, "limit": error.limit, "basis": error.basis}
        if isinstance(error, InputCapacityExceededError) else None,
        **_key_slot_fields(rotator, api_key),
    )


def llm_model_response_event(
    context: AnalysisContext,
    agent_num: int,
    model_id: str,
    prompt: str,
    result: str,
    rotator,
    api_key: str | None,
    *,
    timeout_seconds,
    response=None,
) -> dict:
    return make_runtime_event(
        "status",
        phase="llm_model_response",
        level="info",
        message=f"Agent {agent_num} 模型 {model_id} 回應完成。",
        **_model_event_fields(
            context,
            agent_num,
            model_id,
            prompt,
            timeout_seconds=timeout_seconds,
            response_diagnostics=response_diagnostics(response),
            response_kind=response_kind(result),
            output_chars=len(result),
            **_key_slot_fields(rotator, api_key),
        ),
    )


def llm_stream_delta_event(
    context: AnalysisContext,
    agent_num: int,
    model_id: str,
    prompt: str,
    delta: str,
    stream_sequence: int,
    rotator,
    api_key: str | None,
    *,
    timeout_seconds,
) -> dict:
    return make_runtime_event(
        "llm_stream_delta",
        phase="llm_stream_delta",
        level="info",
        message=f"Agent {agent_num} 正在串流模型輸出...",
        delta=delta,
        **_model_event_fields(
            context,
            agent_num,
            model_id,
            prompt,
            timeout_seconds=timeout_seconds,
            stream_sequence=stream_sequence,
            delta_chars=len(delta),
            **_key_slot_fields(rotator, api_key),
        ),
    )
