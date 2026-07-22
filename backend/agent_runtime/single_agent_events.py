"""Runtime event helpers for single-agent orchestration."""

from __future__ import annotations

from analysis_types import AnalysisContext
from runtime_events import emit_context_event, emit_context_event_async, make_runtime_event


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
