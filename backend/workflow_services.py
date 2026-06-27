"""Process-local service adapters for the LangGraph analysis workflow."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from agent_runtime.audit_repair import finalize_final_audit_async
from agent_runtime.cancellation import attach_cancel_check
from agent_runtime.state_report_adapter import record_agent_state_report
from analysis_types import AnalysisContext
from company_display import company_display_name
from config import API_KEYS, EMBEDDING_MODEL
from data_financial_metric_validator import load_provider_values_from_payload, validate_state_provider_values
from data_reconciliation import build_reconciliation_plan, reconcile_with_official_filing
from llm_client import KeyRotator
from pipeline_modes import get_pipeline_definition, normalize_pipeline_id
from rag_runtime import build_rag_index_async
from runtime_events import RUNTIME_EVENT_CALLBACK_KEY, emit_log
from state_memory import initialize_agent_state
from tear_sheet_tasks import ensure_tear_sheet_summary_async
from workflow_quarters import latest_closed_quarter_for_reconciliation
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
    """Process-local services used by graph nodes."""

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
    active_rotator = rotator if rotator is not None else KeyRotator(API_KEYS)
    holder: dict[str, WorkflowServices] = {}

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
        return {"tool_results": {"rag_index": rag_index_to_payload(rag_index)}, "rag_status": rag_status}

    async def run_agent(agent_num: int, state: AgentGraphState) -> dict[str, Any]:
        return await run_agent_node_adapter(agent_num, state, holder["services"], active_rotator)

    async def final_audit(state: AgentGraphState) -> dict[str, Any]:
        context = legacy_context_from_graph(state, holder["services"])
        await finalize_final_audit_async(context, active_rotator, progress_callback=progress_callback)
        return graph_delta_from_legacy_context(context)

    async def tear_sheet(state: AgentGraphState) -> dict[str, Any]:
        context = legacy_context_from_graph(state, holder["services"])
        await ensure_tear_sheet_summary_async(context, active_rotator, progress_callback=progress_callback)
        return graph_delta_from_legacy_context(context)

    async def persist_report(_state: AgentGraphState) -> dict[str, Any]:
        return {}

    services = WorkflowServices(
        initialize=lambda data, pipeline_id: initialize_graph_state(data, pipeline_id=pipeline_id),
        validate=validate_graph_state,
        repair=repair_graph_state,
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
    graph_state["repair_attempt_counts"] = {}
    graph_state["tool_results"] = {"data_reconciliation_plan": build_reconciliation_plan(domain_state)}
    return graph_state


def validate_graph_state(state: AgentGraphState) -> AgentGraphState:
    previous_circuit = state.get("circuit_breaker") or {}
    domain_state = agent_state_from_graph(state)
    previous_opened = bool(previous_circuit.get("_ever_opened")) or previous_circuit.get("status") == "open"
    validate_state_provider_values(domain_state)
    circuit = domain_state.circuit_breaker.model_dump(mode="json")
    if previous_opened:
        circuit["_ever_opened"] = True
    return {
        "provider_values": {
            field: [value.model_dump(mode="json") for value in values]
            for field, values in domain_state.provider_values.items()
        },
        "validation_issues": [issue.model_dump(mode="json") for issue in domain_state.validation_issues],
        "circuit_breaker": circuit,
        "risk_flags": [flag.model_dump(mode="json") for flag in domain_state.risk_flags],
    }


def repair_graph_state(state: AgentGraphState) -> AgentGraphState:
    domain_state = agent_state_from_graph(state)
    data = _input_data_from_state(state)
    year, season = latest_closed_quarter_for_reconciliation(data)
    reconciliation = reconcile_with_official_filing(domain_state, year=year, season=season)
    validate_state_provider_values(domain_state)
    graph_state = agent_state_to_graph(domain_state, pipeline_id=state.get("pipeline_id", "v1"))
    graph_state["tool_results"] = {
        "official_reconciliation": reconciliation,
        "data_reconciliation_plan": build_reconciliation_plan(domain_state),
    }
    return graph_state


def legacy_context_from_graph(state: AgentGraphState, services: WorkflowServices) -> AnalysisContext:
    pipeline_def = get_pipeline_definition(normalize_pipeline_id(state.get("pipeline_id", "v1")))
    data = _input_data_from_state(state)
    ticker = str(state.get("ticker") or data.get("ticker") or "")
    company_name = str(state.get("company_name") or company_display_name(data, data.get("company_name", ticker)) or ticker)
    agent_sequence = pipeline_def["agents"]
    context: AnalysisContext = {
        "ticker": ticker,
        "company_name": company_name,
        "data": data,
        "analyses": _legacy_agent_mapping(state.get("analyses") or {}),
        "structured_outputs": _legacy_agent_mapping(state.get("structured_outputs") or {}),
        "parsed": copy_json(state.get("parsed") or {}),
        "circuit_breaker": copy_json(state.get("circuit_breaker") or {}),
        "context_digests": _legacy_agent_mapping(state.get("context_digests") or {}),
        "rag_context": _legacy_agent_mapping(state.get("rag_context") or {}),
        "rag_status": copy_json(state.get("rag_status") or {}),
        "blocking_issues": list(state.get("blocking_issues") or []),
        "audit_repair_log": list(state.get("audit_repair_log") or []),
        "repair_attempt_counts": copy_json(state.get("repair_attempt_counts") or {}),
        "repair_iteration_count": int(state.get("repair_iteration_count") or 0),
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
    rag_payload = (state.get("tool_results") or {}).get("rag_index")
    if isinstance(rag_payload, dict):
        context["rag_index"] = rag_index_from_payload(rag_payload)
    if services.progress_callback:
        context[RUNTIME_EVENT_CALLBACK_KEY] = services.progress_callback
    attach_cancel_check(context, services.cancel_check)
    return context


async def run_agent_node_adapter(agent_num: int, state: AgentGraphState, services: WorkflowServices, rotator: Any) -> dict[str, Any]:
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
    structured_output = structured_outputs.get(completed_agent_num, structured_outputs.get(str(completed_agent_num)))
    domain_state = context.get("agent_state")
    record_agent_state_report(domain_state, completed_agent_num, markdown, structured_output)
    report = domain_state.agent_reports.get(str(completed_agent_num)) if domain_state else None

    delta: dict[str, Any] = {
        "analyses": {str(completed_agent_num): markdown},
        "execution_trace": [{"id": f"agent:{completed_agent_num}", "node": f"agent_{completed_agent_num}", "agent_num": completed_agent_num}],
    }
    if structured_output is not None:
        delta["structured_outputs"] = {str(completed_agent_num): copy_json(structured_output)}
    if report is not None:
        delta["agent_reports"] = {str(completed_agent_num): report.model_dump(mode="json")}
        if report.risk_flags:
            delta["risk_flags"] = [flag.model_dump(mode="json") for flag in report.risk_flags]

    new_blocking = [issue for issue in list(context.get("blocking_issues", []) or []) if issue not in before_blocking]
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
        "repair_attempt_counts": copy_json(context.get("repair_attempt_counts") or {}),
        "repair_iteration_count": int(context.get("repair_iteration_count") or 0),
        "final_audit": copy_json(context.get("final_audit") or {}),
        "tear_sheet_summary": str(context.get("tear_sheet_summary") or ""),
        "report_cover": copy_json(context.get("report_cover") or {}),
    }
    if context.get("report_filename"):
        delta["report_filename"] = str(context.get("report_filename"))
    if context.get("status"):
        delta["status"] = str(context.get("status"))
    domain_state = context.get("agent_state")
    if domain_state is not None:
        delta["agent_reports"] = {agent_id: report.model_dump(mode="json") for agent_id, report in domain_state.agent_reports.items()}
        delta["risk_flags"] = [flag.model_dump(mode="json") for flag in domain_state.risk_flags]
    return delta


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
