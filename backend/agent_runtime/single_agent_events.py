"""Runtime event helpers for single-agent orchestration."""

from __future__ import annotations

from analysis_types import AnalysisContext
from runtime_events import emit_context_event, emit_context_event_async, make_runtime_event
from llm_input_capacity import InputCapacityExceededError
from .retry_policy import AgentConfigurationError


def route_rejection_event(model_id, error):
    metadata = {"error_kind": error.__class__.__name__}
    if isinstance(error, InputCapacityExceededError):
        return "model_input_capacity", str(error), {**metadata, "input_limit": error.limit, "input_basis": error.basis}
    if isinstance(error, AgentConfigurationError):
        return "model_config_error", f"模型 {model_id} 請求設定不相容，改試下一個備援模型...", metadata
    return "model_fallback", f"模型 {model_id} 不可用，改試下一個備援模型...", metadata


def single_agent_event_fields(context: AnalysisContext, agent_num: int, model_id: str, **metadata) -> dict:
    return {
        "current": (context.get("agent_positions", {}) or {}).get(agent_num, agent_num),
        "total": context.get("agent_total"),
        "name": f"Agent {agent_num}",
        "agent_num": agent_num,
        "pipeline_id": context.get("pipeline_id"),
        "pipeline_label": context.get("pipeline_label"),
        "metadata": {"model_id": model_id, **{k: v for k, v in metadata.items() if v is not None}},
    }


def emit_sync_model_event(
    context: AnalysisContext,
    agent_num: int,
    phase: str,
    level: str,
    message: str,
    model_id: str,
    **metadata,
) -> None:
    emit_context_event(
        context,
        make_runtime_event(
            "status",
            phase=phase,
            level=level,
            message=message,
            **single_agent_event_fields(context, agent_num, model_id, **metadata),
        ),
    )


async def emit_async_model_event(
    context: AnalysisContext,
    agent_num: int,
    phase: str,
    level: str,
    message: str,
    model_id: str,
    **metadata,
) -> None:
    await emit_context_event_async(
        context,
        make_runtime_event(
            "status",
            phase=phase,
            level=level,
            message=message,
            **single_agent_event_fields(context, agent_num, model_id, **metadata),
        ),
    )
