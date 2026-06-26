"""LangGraph workflow topology for durable stock analysis runs."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from agent_catalog import AGENT_NAMES
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from agent_runtime.audit_repair import finalize_final_audit_async
from agent_runtime.cancellation import attach_cancel_check
from agent_runtime.retry_policy import AgentRateLimitError, AgentServerError, AgentTransientError
from agent_runtime.state_report_adapter import record_agent_state_report
from analysis_types import AnalysisContext, StockData
from company_display import company_display_name
from config import API_KEYS, EMBEDDING_MODEL
from data_financial_metric_validator import (
    load_provider_values_from_payload,
    validate_state_provider_values,
)
from data_reconciliation import build_reconciliation_plan, reconcile_with_official_filing
from llm_client import KeyRotator
from pipeline_modes import get_pipeline_definition, normalize_pipeline_id
from rag_runtime import build_rag_index_async
from runtime_events import RUNTIME_EVENT_CALLBACK_KEY, emit_log
from state_memory import initialize_agent_state
from tear_sheet_tasks import ensure_tear_sheet_summary_async
from workflow_state import (
    AgentGraphState,
    agent_state_from_graph,
    agent_state_to_graph,
    rag_index_from_payload,
    rag_index_to_payload,
)


async def run_agent_with_quality_gates_async(*args, **kwargs):
    """Lazy shim kept patchable for tests while avoiding import cycles."""

    from agent_runtime.quality_gates import run_agent_with_quality_gates_async as _run_agent

    return await _run_agent(*args, **kwargs)


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


def create_default_workflow_services(
    *,
    rotator: Any | None = None,
    progress_callback: Callable[..., Any] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> WorkflowServices:
    """Create production graph-node services with process-local dependencies."""

    active_rotator = rotator if rotator is not None else KeyRotator(API_KEYS)
    holder: dict[str, WorkflowServices] = {}

    def initialize(data: dict[str, Any], pipeline_id: str) -> AgentGraphState:
        return initialize_graph_state(data, pipeline_id=pipeline_id)

    def validate(state: AgentGraphState) -> AgentGraphState:
        return validate_graph_state(state)

    async def repair(state: AgentGraphState) -> AgentGraphState:
        return repair_graph_state(state)

    async def prepare(state: AgentGraphState) -> dict[str, Any]:
        context = legacy_context_from_graph(state, holder["services"])
        rag_index = await build_rag_index_async(context.get("data", {}) or {}, active_rotator)
        if rag_index is None:
            return {}
        rag_status = {
            "model": EMBEDDING_MODEL,
            "chunks": len(getattr(rag_index, "chunks", []) or []),
            "embedded": bool(getattr(rag_index, "has_embeddings", False)),
        }
        emit_log(f"  🔎 RAG 長文本索引完成：{rag_status['chunks']} 個片段。")
        return {
            "tool_results": {"rag_index": rag_index_to_payload(rag_index)},
            "rag_status": rag_status,
        }

    async def run_agent(agent_num: int, state: AgentGraphState) -> dict[str, Any]:
        return await run_agent_node_adapter(
            agent_num,
            state,
            holder["services"],
            active_rotator,
        )

    async def final_audit(state: AgentGraphState) -> dict[str, Any]:
        context = legacy_context_from_graph(state, holder["services"])
        await finalize_final_audit_async(context, active_rotator, progress_callback=progress_callback)
        return graph_delta_from_legacy_context(context)

    async def tear_sheet(state: AgentGraphState) -> dict[str, Any]:
        context = legacy_context_from_graph(state, holder["services"])
        await ensure_tear_sheet_summary_async(context, active_rotator, progress_callback=progress_callback)
        return graph_delta_from_legacy_context(context)

    async def persist_report(_state: AgentGraphState) -> dict[str, Any]:
        # Report persistence stays in analysis_jobs until Task 5 moves it behind
        # stable checkpointed filenames.
        return {}

    services = WorkflowServices(
        initialize=initialize,
        validate=validate,
        repair=repair,
        prepare=prepare,
        run_agent=run_agent,
        final_audit=final_audit,
        tear_sheet=tear_sheet,
        persist_report=persist_report,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )
    holder["services"] = services
    return services


def initialize_graph_state(data: dict[str, Any], *, pipeline_id: str) -> AgentGraphState:
    domain_state = initialize_agent_state(data)
    load_provider_values_from_payload(domain_state, data)
    validate_state_provider_values(domain_state)
    graph_state = agent_state_to_graph(domain_state, pipeline_id=normalize_pipeline_id(pipeline_id))
    graph_state["analyses"] = {}
    graph_state["structured_outputs"] = {}
    graph_state["blocking_issues"] = []
    graph_state["tool_results"] = {
        "data_reconciliation_plan": build_reconciliation_plan(domain_state)
    }
    return graph_state


def validate_graph_state(state: AgentGraphState) -> AgentGraphState:
    domain_state = agent_state_from_graph(state)
    return {
        "provider_values": {
            field: [value.model_dump(mode="json") for value in values]
            for field, values in domain_state.provider_values.items()
        },
        "validation_issues": [
            issue.model_dump(mode="json") for issue in domain_state.validation_issues
        ],
        "circuit_breaker": domain_state.circuit_breaker.model_dump(mode="json"),
        "risk_flags": [flag.model_dump(mode="json") for flag in domain_state.risk_flags],
    }


def repair_graph_state(state: AgentGraphState) -> AgentGraphState:
    domain_state = agent_state_from_graph(state)
    data = _input_data_from_state(state)
    year, season = _latest_closed_quarter_for_reconciliation(data)
    reconciliation = reconcile_with_official_filing(domain_state, year=year, season=season)
    validate_state_provider_values(domain_state)
    graph_state = agent_state_to_graph(domain_state, pipeline_id=state.get("pipeline_id", "v1"))
    graph_state["tool_results"] = {
        "official_reconciliation": reconciliation,
        "data_reconciliation_plan": build_reconciliation_plan(domain_state),
    }
    return graph_state


def legacy_context_from_graph(
    state: AgentGraphState,
    services: WorkflowServices,
) -> AnalysisContext:
    pipeline_def = get_pipeline_definition(normalize_pipeline_id(state.get("pipeline_id", "v1")))
    data = _input_data_from_state(state)
    ticker = str(state.get("ticker") or data.get("ticker") or "")
    company_name = str(
        state.get("company_name")
        or company_display_name(data, data.get("company_name", ticker))
        or ticker
    )
    agent_sequence = pipeline_def["agents"]
    context: AnalysisContext = {
        "ticker": ticker,
        "company_name": company_name,
        "data": data,
        "analyses": _legacy_agent_mapping(state.get("analyses") or {}),
        "structured_outputs": _legacy_agent_mapping(state.get("structured_outputs") or {}),
        "parsed": copy_json(state.get("parsed") or {}),
        "context_digests": _legacy_agent_mapping(state.get("context_digests") or {}),
        "rag_context": _legacy_agent_mapping(state.get("rag_context") or {}),
        "rag_status": copy_json(state.get("rag_status") or {}),
        "blocking_issues": list(state.get("blocking_issues") or []),
        "audit_repair_log": list(state.get("audit_repair_log") or []),
        "final_audit": copy_json(state.get("final_audit") or {}),
        "tear_sheet_summary": str(state.get("tear_sheet_summary") or ""),
        "report_cover": copy_json(state.get("report_cover") or {}),
        "report_filename": str(state.get("report_filename") or ""),
        "start_time": float(state.get("started_at") or time.time()),
        "execution_mode": "langgraph",
        "pipeline_id": pipeline_def["id"],
        "pipeline_label": pipeline_def["label"],
        "agent_sequence": agent_sequence,
        "agent_positions": {agent_num: idx + 1 for idx, agent_num in enumerate(agent_sequence)},
        "agent_total": len(agent_sequence),
        "agent_state": agent_state_from_graph(state),
    }
    rag_payload = ((state.get("tool_results") or {}).get("rag_index"))
    if isinstance(rag_payload, dict):
        context["rag_index"] = rag_index_from_payload(rag_payload)
    if services.progress_callback:
        context[RUNTIME_EVENT_CALLBACK_KEY] = services.progress_callback
    attach_cancel_check(context, services.cancel_check)
    return context


async def run_agent_node_adapter(
    agent_num: int,
    state: AgentGraphState,
    services: WorkflowServices,
    rotator: Any,
) -> dict[str, Any]:
    context = legacy_context_from_graph(state, services)
    before_blocking = list(context.get("blocking_issues", []) or [])
    completed_agent_num, markdown = await run_agent_with_quality_gates_async(
        agent_num,
        context["data"],
        context,
        rotator,
        services.progress_callback,
    )
    structured_outputs = context.get("structured_outputs", {}) or {}
    structured_output = structured_outputs.get(
        completed_agent_num,
        structured_outputs.get(str(completed_agent_num)),
    )
    domain_state = context.get("agent_state")
    record_agent_state_report(domain_state, completed_agent_num, markdown, structured_output)
    report = domain_state.agent_reports.get(str(completed_agent_num)) if domain_state else None

    delta: dict[str, Any] = {
        "analyses": {str(completed_agent_num): markdown},
        "execution_trace": [
            {
                "id": f"agent:{completed_agent_num}",
                "node": f"agent_{completed_agent_num}",
                "agent_num": completed_agent_num,
            }
        ],
    }
    if structured_output is not None:
        delta["structured_outputs"] = {str(completed_agent_num): copy_json(structured_output)}
    if report is not None:
        delta["agent_reports"] = {str(completed_agent_num): report.model_dump(mode="json")}
        if report.risk_flags:
            delta["risk_flags"] = [flag.model_dump(mode="json") for flag in report.risk_flags]

    new_blocking = [
        issue
        for issue in list(context.get("blocking_issues", []) or [])
        if issue not in before_blocking
    ]
    if new_blocking:
        delta["blocking_issues"] = new_blocking
    return delta


def graph_delta_from_legacy_context(context: AnalysisContext) -> dict[str, Any]:
    delta: dict[str, Any] = {
        "analyses": _graph_agent_mapping(context.get("analyses") or {}),
        "structured_outputs": _graph_agent_mapping(context.get("structured_outputs") or {}),
        "parsed": copy_json(context.get("parsed") or {}),
        "context_digests": _graph_agent_mapping(context.get("context_digests") or {}),
        "rag_context": _graph_agent_mapping(context.get("rag_context") or {}),
        "rag_status": copy_json(context.get("rag_status") or {}),
        "blocking_issues": list(context.get("blocking_issues") or []),
        "audit_repair_log": list(context.get("audit_repair_log") or []),
        "final_audit": copy_json(context.get("final_audit") or {}),
        "tear_sheet_summary": str(context.get("tear_sheet_summary") or ""),
        "report_cover": copy_json(context.get("report_cover") or {}),
    }
    if context.get("report_filename"):
        delta["report_filename"] = str(context.get("report_filename"))
    domain_state = context.get("agent_state")
    if domain_state is not None:
        delta["agent_reports"] = {
            agent_id: report.model_dump(mode="json")
            for agent_id, report in domain_state.agent_reports.items()
        }
        delta["risk_flags"] = [flag.model_dump(mode="json") for flag in domain_state.risk_flags]
    return delta


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


@asynccontextmanager
async def open_sqlite_checkpointer(path: str | Path):
    target = Path(path).expanduser().resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(target)) as saver:
        await saver.conn.execute("PRAGMA journal_mode=WAL")
        await saver.conn.execute("PRAGMA busy_timeout=30000")
        await saver.conn.execute("PRAGMA synchronous=NORMAL")
        await saver.setup()
        yield saver


async def execute_persistent_graph(
    *,
    graph_builder: StateGraph,
    initial_state: AgentGraphState,
    thread_id: str,
    checkpoint_path: str | Path,
) -> AgentGraphState:
    config = {"configurable": {"thread_id": thread_id}}
    async with open_sqlite_checkpointer(checkpoint_path) as saver:
        graph = graph_builder.compile(checkpointer=saver)
        snapshot = await graph.aget_state(config)
        if snapshot.values and not snapshot.next:
            return dict(snapshot.values)
        graph_input = None if snapshot.values else initial_state
        result = await graph.ainvoke(graph_input, config=config)
        return dict(result)


async def execute_persistent_workflow(
    *,
    initial_state: AgentGraphState,
    pipeline_id: str,
    thread_id: str,
    checkpoint_path: str | Path,
    services: WorkflowServices,
) -> AgentGraphState:
    return await execute_persistent_graph(
        graph_builder=build_analysis_graph_builder(pipeline_id, services),
        initial_state=initial_state,
        thread_id=thread_id,
        checkpoint_path=checkpoint_path,
    )


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


def _input_data_from_state(state: AgentGraphState) -> dict[str, Any]:
    raw = state.get("raw_financial_data") or {}
    if isinstance(raw.get("input"), dict):
        return copy_json(raw["input"])
    normalized = state.get("normalized_financials")
    return copy_json(normalized if isinstance(normalized, dict) else {})


def _legacy_agent_mapping(mapping: dict[Any, Any]) -> dict[Any, Any]:
    return {_legacy_agent_key(key): copy_json(value) for key, value in mapping.items()}


def _graph_agent_mapping(mapping: dict[Any, Any]) -> dict[str, Any]:
    return {str(key): copy_json(value) for key, value in mapping.items()}


def _legacy_agent_key(value: Any) -> Any:
    text = str(value)
    return int(text) if text.isdecimal() else value


def copy_json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return copy_json(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): copy_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [copy_json(item) for item in value]
    if isinstance(value, tuple):
        return [copy_json(item) for item in value]
    return value


def _latest_closed_quarter_for_reconciliation(data: dict[str, Any]) -> tuple[int, int]:
    from datetime import date

    year = data.get("year") or data.get("fiscal_year")
    season = data.get("season") or data.get("quarter")
    try:
        year_int = int(year)
        season_int = int(season)
    except (TypeError, ValueError):
        today = date.today()
        current_quarter = (today.month - 1) // 3 + 1
        closed_quarter = current_quarter - 1
        closed_year = today.year
        if closed_quarter == 0:
            closed_quarter = 4
            closed_year -= 1
        return closed_year, closed_quarter
    if season_int not in {1, 2, 3, 4}:
        return _latest_closed_quarter_for_reconciliation({})
    return year_int, season_int
