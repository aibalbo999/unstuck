"""LangGraph node telemetry wrapper."""

from __future__ import annotations

import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Any

from runtime_events import emit_log
from security_sanitizer import sanitize_error_message
from workflow_state import AgentGraphState
from workflow_telemetry_attribution import node_telemetry_scope, result_telemetry


def with_node_telemetry(
    node_name: str,
    node_func: Callable[[AgentGraphState], Any],
    services: Any,
    *,
    agent_num: int | None = None,
) -> Callable[[AgentGraphState], Awaitable[Any]]:
    async def wrapped(state: AgentGraphState) -> Any:
        with node_telemetry_scope(node_name, agent_num):
            return await run_node(state)

    async def run_node(state: AgentGraphState) -> Any:
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
                result=None,
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
            result=result,
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
    result: Any | None,
) -> None:
    callback = getattr(services, "telemetry_callback", None)
    if not callable(callback):
        return
    payload = {
        "job_id": str(state.get("job_id") or state.get("run_id") or ""),
        "ticker": str(state.get("ticker") or ""),
        "pipeline_id": str(state.get("pipeline_id") or "v1"),
        "node_name": node_name,
        "started_at": started_at,
        "finished_at": finished_at,
        "latency_ms": max(0, int(round((finished_at - started_at) * 1000))),
        "status": status,
        **result_telemetry(result, node_name, agent_num),
        "error": error,
    }
    try:
        result = callback(payload)
        if inspect.isawaitable(result):
            await result
    except Exception as exc:
        emit_log(f"telemetry callback failed for {node_name}: {sanitize_error_message(exc)}")
