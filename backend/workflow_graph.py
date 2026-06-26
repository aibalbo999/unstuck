"""LangGraph workflow topology for durable stock analysis runs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from agent_runtime.retry_policy import AgentRateLimitError, AgentServerError, AgentTransientError
from pipeline_modes import get_pipeline_definition, normalize_pipeline_id
from workflow_state import AgentGraphState


@dataclass(frozen=True)
class WorkflowServices:
    """Process-local services used by graph nodes.

    These callables may close over API clients, rotators, callbacks, or storage
    instances. None of those objects should be stored in ``AgentGraphState``.
    """

    initialize: Callable[[dict[str, Any], str], AgentGraphState]
    validate: Callable[[AgentGraphState], AgentGraphState]
    repair: Callable[[AgentGraphState], Awaitable[AgentGraphState]]
    prepare: Callable[[AgentGraphState], Awaitable[dict[str, Any]]]
    run_agent: Callable[[int, AgentGraphState], Awaitable[dict[str, Any]]]
    final_audit: Callable[[AgentGraphState], Awaitable[dict[str, Any]]]
    tear_sheet: Callable[[AgentGraphState], Awaitable[dict[str, Any]]]
    persist_report: Callable[[AgentGraphState], Awaitable[dict[str, Any]]]
    progress_callback: Callable[..., Any] | None = None
    cancel_check: Callable[[], None] | None = None


def is_retryable_workflow_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            AgentRateLimitError,
            AgentTransientError,
            AgentServerError,
            TimeoutError,
            ConnectionError,
        ),
    )


AGENT_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    initial_interval=2.0,
    backoff_factor=2.0,
    max_interval=30.0,
    jitter=True,
    retry_on=is_retryable_workflow_error,
)


def route_after_validation(state: AgentGraphState) -> Literal["repair_data", "prepare_analysis"]:
    if (state.get("circuit_breaker") or {}).get("status") == "open":
        return "repair_data"
    return "prepare_analysis"


def route_after_repair_validation(state: AgentGraphState) -> Literal["blocked_finalize", "prepare_analysis"]:
    if (state.get("circuit_breaker") or {}).get("status") == "open":
        return "blocked_finalize"
    return "prepare_analysis"


def build_analysis_graph_builder(pipeline_id: str, services: WorkflowServices) -> StateGraph:
    pipeline_def = get_pipeline_definition(normalize_pipeline_id(pipeline_id))
    graph = StateGraph(AgentGraphState)

    graph.add_node("initialize", _initialize_node_factory(pipeline_def["id"]))
    graph.add_node("validate_data", services.validate)
    graph.add_node("repair_data", services.repair, retry_policy=AGENT_RETRY_POLICY)
    graph.add_node("validate_repaired_data", services.validate)
    graph.add_node("prepare_analysis", services.prepare, retry_policy=AGENT_RETRY_POLICY)
    graph.add_node("blocked_finalize", _blocked_finalize)
    graph.add_node("final_audit", services.final_audit, retry_policy=AGENT_RETRY_POLICY)
    graph.add_node("tear_sheet", services.tear_sheet, retry_policy=AGENT_RETRY_POLICY)
    graph.add_node("persist_report", services.persist_report, retry_policy=AGENT_RETRY_POLICY)
    graph.add_node("finalize", _finalize)

    for agent_num in pipeline_def["agents"]:
        graph.add_node(
            f"agent_{agent_num}",
            _agent_node_factory(services, agent_num),
            retry_policy=AGENT_RETRY_POLICY,
        )

    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "validate_data")
    graph.add_conditional_edges(
        "validate_data",
        route_after_validation,
        {
            "repair_data": "repair_data",
            "prepare_analysis": "prepare_analysis",
        },
    )
    graph.add_edge("repair_data", "validate_repaired_data")
    graph.add_conditional_edges(
        "validate_repaired_data",
        route_after_repair_validation,
        {
            "blocked_finalize": "blocked_finalize",
            "prepare_analysis": "prepare_analysis",
        },
    )
    graph.add_edge("blocked_finalize", END)

    _add_agent_group_edges(graph, pipeline_def["groups"])

    graph.add_edge("final_audit", "tear_sheet")
    graph.add_edge("tear_sheet", "persist_report")
    graph.add_edge("persist_report", "finalize")
    graph.add_edge("finalize", END)
    return graph


async def run_analysis_workflow(
    *,
    initial_state: AgentGraphState,
    pipeline_id: str,
    services: WorkflowServices,
    checkpointer: Any | None = None,
    thread_id: str | None = None,
) -> AgentGraphState:
    graph = build_analysis_graph_builder(pipeline_id, services).compile(checkpointer=checkpointer)
    config = None
    if checkpointer is not None:
        config = {
            "configurable": {
                "thread_id": thread_id or initial_state.get("run_id") or f"{pipeline_id}:default"
            }
        }
    result = await graph.ainvoke(initial_state, config=config)
    return dict(result)


def _initialize_node_factory(pipeline_id: str) -> Callable[[AgentGraphState], AgentGraphState]:
    def initialize(state: AgentGraphState) -> AgentGraphState:
        started_at = state.get("started_at") or time.time()
        return {
            "pipeline_id": pipeline_id,
            "started_at": started_at,
            "status": "running",
            "execution_trace": [{"id": "initialize", "node": "initialize", "at": started_at}],
        }

    return initialize


def _agent_node_factory(
    services: WorkflowServices,
    agent_num: int,
) -> Callable[[AgentGraphState], Awaitable[dict[str, Any]]]:
    async def run_agent_node(state: AgentGraphState) -> dict[str, Any]:
        return await services.run_agent(agent_num, state)

    return run_agent_node


def _add_agent_group_edges(graph: StateGraph, groups: tuple[tuple[int, ...], ...]) -> None:
    if not groups:
        graph.add_edge("prepare_analysis", "final_audit")
        return

    for group_index, group in enumerate(groups, start=1):
        group_nodes = [f"agent_{agent_num}" for agent_num in group]
        join_name = f"group_{group_index}_join"
        graph.add_node(join_name, _join_node_factory(join_name))

        if group_index == 1:
            for node_name in group_nodes:
                graph.add_edge("prepare_analysis", node_name)

        graph.add_edge(group_nodes, join_name)

        if group_index < len(groups):
            next_group = groups[group_index]
            for next_agent_num in next_group:
                graph.add_edge(join_name, f"agent_{next_agent_num}")
        else:
            graph.add_edge(join_name, "final_audit")


def _join_node_factory(join_name: str) -> Callable[[AgentGraphState], AgentGraphState]:
    def join(_state: AgentGraphState) -> AgentGraphState:
        return {"execution_trace": [{"id": join_name, "node": join_name}]}

    return join


def _blocked_finalize(state: AgentGraphState) -> AgentGraphState:
    fields = list((state.get("circuit_breaker") or {}).get("blocking_fields") or [])
    if not fields:
        fields = [
            str(issue.get("field"))
            for issue in state.get("validation_issues", []) or []
            if isinstance(issue, dict) and issue.get("field")
        ]
    if not fields:
        fields = ["data_validation"]
    now = time.time()
    return {
        "status": "blocked",
        "blocking_issues": [f"validation:{field}" for field in fields],
        "total_time": max(0.0, now - float(state.get("started_at") or now)),
        "execution_trace": [{"id": "blocked_finalize", "node": "blocked_finalize", "at": now}],
    }


def _finalize(state: AgentGraphState) -> AgentGraphState:
    now = time.time()
    return {
        "status": "done",
        "total_time": max(0.0, now - float(state.get("started_at") or now)),
        "execution_trace": [{"id": "finalize", "node": "finalize", "at": now}],
    }

