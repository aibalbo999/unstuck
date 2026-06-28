"""LangGraph node telemetry wrapper."""

from __future__ import annotations

import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Any

from runtime_events import emit_log
from security_sanitizer import sanitize_error_message
from workflow_state import AgentGraphState


def with_node_telemetry(
    node_name: str,
    node_func: Callable[[AgentGraphState], Any],
    services: Any,
    *,
    agent_num: int | None = None,
) -> Callable[[AgentGraphState], Awaitable[Any]]:
    async def wrapped(state: AgentGraphState) -> Any:
        started_at = time.time()
        try:
            result = node_func(state)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            finished_at = time.time()
            await _emit_node_telemetry(
                services,
                state,
                node_name=node_name,
                agent_num=agent_num,
                started_at=started_at,
                finished_at=finished_at,
                status="failed",
                error=f"{exc.__class__.__name__}: {sanitize_error_message(str(exc))}",
            )
            raise
        finished_at = time.time()
        await _emit_node_telemetry(
            services,
            state,
            node_name=node_name,
            agent_num=agent_num,
            started_at=started_at,
            finished_at=finished_at,
            status="success",
            error=None,
        )
        return result

    return wrapped


async def _emit_node_telemetry(
    services: Any,
    state: AgentGraphState,
    *,
    node_name: str,
    agent_num: int | None,
    started_at: float,
    finished_at: float,
    status: str,
    error: str | None,
) -> None:
    callback = getattr(services, "telemetry_callback", None)
    if not callable(callback):
        return
    payload = {
        "job_id": str(state.get("job_id") or state.get("run_id") or ""),
        "ticker": str(state.get("ticker") or ""),
        "pipeline_id": str(state.get("pipeline_id") or "v1"),
        "node_name": node_name,
        "model": _model_for_node(node_name, agent_num),
        "started_at": started_at,
        "finished_at": finished_at,
        "latency_ms": max(0, int(round((finished_at - started_at) * 1000))),
        "status": status,
        "retry_count": _retry_count_for_node(state, agent_num),
        "input_tokens": None,
        "output_tokens": None,
        "cache_hit": False,
        "quality_gate_pass": status == "success",
        "error": error,
    }
    try:
        result = callback(payload)
        if inspect.isawaitable(result):
            await result
    except Exception as exc:
        emit_log(f"telemetry callback failed for {node_name}: {sanitize_error_message(exc)}")


def _model_for_node(node_name: str, agent_num: int | None) -> str | None:
    try:
        from config import AGENT_MODELS, AUDIT_MODEL, EMBEDDING_MODEL, TEAR_SHEET_MODEL
    except Exception:
        return None
    if agent_num is not None and node_name.startswith("agent_"):
        return AGENT_MODELS.get(int(agent_num))
    if node_name == "prepare_analysis":
        return EMBEDDING_MODEL
    if node_name == "final_audit":
        return AUDIT_MODEL
    if node_name == "tear_sheet":
        return TEAR_SHEET_MODEL
    return None


def _retry_count_for_node(state: AgentGraphState, agent_num: int | None) -> int:
    if agent_num is None:
        return 0
    counts = state.get("agent_quality_retry_counts") or {}
    try:
        return int(counts.get(str(agent_num), counts.get(agent_num, 0)) or 0)
    except (TypeError, ValueError):
        return 0
