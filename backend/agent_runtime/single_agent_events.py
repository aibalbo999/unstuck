"""Runtime event helpers for single-agent orchestration."""

from __future__ import annotations

import re
import sys

from analysis_types import AnalysisContext
from runtime_events import emit_context_event, emit_context_event_async, make_runtime_event, emit_log
from llm_input_capacity import InputCapacityExceededError
from .retry_policy import AgentConfigurationError
from .cancellation import raise_if_cancelled


_CACHE_DECISION_REASONS = frozenset({
    ("miss", "no_entry"), ("bypass", "repair_bypass"), ("bypass", "disabled"),
    ("error", "read_error"), ("reject", "invalid_entry"),
    ("reject", "a7_known_assessment_failure"), ("reject", "a7_invalid_entry"),
    ("reject", "context_contract_mismatch"),
})


def _cache_decision_metadata(cache_key, observation):
    decision, reason = observation.get("decision"), observation.get("reason")
    if (not isinstance(cache_key, str) or re.fullmatch(r"agent_step:[0-9a-f]{64}", cache_key) is None
            or not isinstance(decision, str) or not isinstance(reason, str)
            or (decision, reason) not in _CACHE_DECISION_REASONS):
        return None
    return {"cache_key": cache_key, "decision": decision, "reason": reason}


def _preserve_cache_event_cancellation(context, error):
    from llm_key_admission import propagate_admission_cancel
    propagate_admission_cancel(error)
    # Job entrypoints import the runtime. Inspect an already loaded exception
    # type instead of importing their service objects back into event handling.
    for module, name in (("analysis_jobs", "AnalysisJobCancelled"),
                         ("report_rerun_jobs", "ReportRerunJobCancelled")):
        cancellation = getattr(sys.modules.get(module), name, None)
        if isinstance(cancellation, type) and isinstance(error, cancellation):
            raise error
    raise_if_cancelled(context)


def emit_sync_cache_decision(context, agent_num, model_id, cache_key, observation):
    """Non-hit diagnostics are best effort and never count as provider calls."""
    try:
        metadata = _cache_decision_metadata(cache_key, observation)
        if metadata:
            emit_sync_model_event(context, agent_num, "agent_step_cache_decision", "info",
                                  f"Agent {agent_num} 本次未使用步驟快取。", model_id, **metadata)
    except Exception as exc:
        _preserve_cache_event_cancellation(context, exc)


async def emit_async_cache_decision(context, agent_num, model_id, cache_key, observation):
    try:
        metadata = _cache_decision_metadata(cache_key, observation)
        if metadata:
            await emit_async_model_event(context, agent_num, "agent_step_cache_decision", "info",
                                         f"Agent {agent_num} 本次未使用步驟快取。", model_id, **metadata)
    except Exception as exc:
        _preserve_cache_event_cancellation(context, exc)


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


def reject_sync_model(context, agent_num, model_id, error):
    phase, message, metadata = route_rejection_event(model_id, error)
    emit_log(f"    ❌ {message}")
    emit_sync_model_event(context, agent_num, phase, "warning", message, model_id, **metadata)
    return str(error)


async def reject_async_model(context, agent_num, model_id, error):
    phase, message, metadata = route_rejection_event(model_id, error)
    emit_log(f"    ❌ {message}")
    await emit_async_model_event(context, agent_num, phase, "warning", message, model_id, **metadata)
    return str(error)
