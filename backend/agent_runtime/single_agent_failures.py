"""Retryable route-failure handling for single-agent orchestration."""

from __future__ import annotations

from analysis_types import AnalysisContext
from llm_client import KeyRotator
from runtime_events import emit_log

from .deferred import record_route_failure
from .single_agent_events import emit_async_model_event, emit_sync_model_event


def record_retryable_failure_sync(
    context: AnalysisContext,
    rotator: KeyRotator,
    agent_num: int,
    model_id: str,
    error: Exception,
    deferred_routes: list[dict],
) -> str:
    last_error = str(error)
    circuit_state = record_route_failure(context, rotator, model_id, error, deferred_routes)
    message = f"{model_id} 多次重試後仍失敗：{last_error[:120]}"
    emit_log(f"    ❌ {message}")
    emit_sync_model_event(
        context,
        agent_num,
        "model_failed",
        "error",
        message,
        model_id,
        error_kind=error.__class__.__name__,
        circuit_open=bool(circuit_state.get("opened_until")),
        shared_circuit_open=bool(getattr(error, "parallel_circuit_open", False)),
    )
    return last_error


async def record_retryable_failure_async(
    context: AnalysisContext,
    rotator: KeyRotator,
    agent_num: int,
    model_id: str,
    error: Exception,
    deferred_routes: list[dict],
) -> str:
    last_error = str(error)
    circuit_state = record_route_failure(context, rotator, model_id, error, deferred_routes)
    message = f"{model_id} 多次重試後仍失敗：{last_error[:120]}"
    emit_log(f"    ❌ {message}")
    await emit_async_model_event(
        context,
        agent_num,
        "model_failed",
        "error",
        message,
        model_id,
        error_kind=error.__class__.__name__,
        circuit_open=bool(circuit_state.get("opened_until")),
        shared_circuit_open=bool(getattr(error, "parallel_circuit_open", False)),
    )
    return last_error


__all__ = ["record_retryable_failure_async", "record_retryable_failure_sync"]
