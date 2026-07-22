"""Runtime event helpers for single-attempt LLM calls."""

from __future__ import annotations

from analysis_types import AnalysisContext
from llm_client import estimate_text_tokens, extract_usage
from runtime_events import RUNTIME_EVENT_CALLBACK_KEY, make_runtime_event


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
            **{key: value for key, value in metadata.items() if value is not None},
        },
    }


def _key_slot_fields(rotator, api_key: str | None) -> dict:
    keys = list(getattr(rotator, "keys", []) or [])
    if not keys:
        return {}
    fields = {"key_count": len(keys)}
    if api_key:
        try:
            fields["key_slot"] = keys.index(api_key) + 1
        except ValueError:
            pass
    return fields


def _record_llm_token_usage(context: AnalysisContext, agent_num: int, response) -> None:
    usage = extract_usage(response)
    if not usage:
        return
    context.setdefault("llm_token_usage", {})[agent_num] = usage


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
    context: AnalysisContext, agent_num: int, model_id: str, prompt: str, rotator, api_key: str | None, *, timeout_seconds
) -> dict:
    return _model_event_fields(
        context,
        agent_num,
        model_id,
        prompt,
        timeout_seconds=timeout_seconds,
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
