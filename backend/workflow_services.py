"""Process-local service adapters for the LangGraph analysis workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from agent_runtime.audit_repair import finalize_final_audit_async
from agent_runtime.state_report_adapter import record_agent_state_report
from config import EMBEDDING_MODEL, LLM_API_KEYS_BY_PROVIDER
from data_financial_metric_validator import load_provider_values_from_payload, validate_state_provider_values
from data_reconciliation import build_reconciliation_plan, reconcile_with_official_filing
from llm_client import KeyRotator
from pipeline_modes import normalize_pipeline_id
from prompt_loader import load_agent_prompt_config
from rag_runtime import build_rag_index_async
from runtime_code_identity import runtime_code_identity
from runtime_events import emit_log
from state_memory import initialize_agent_state
from tear_sheet_tasks import ensure_tear_sheet_summary_async
from workflow_chief_editor import run_chief_editor_synthesis
from workflow_context import (
    copy_json,
    graph_agent_mapping,
    graph_delta_from_legacy_context,
    input_data_from_state,
    legacy_context_from_graph,
)
from workflow_quarters import latest_closed_quarter_for_reconciliation
from workflow_state import (
    AgentGraphState,
    agent_state_from_graph,
    agent_state_to_graph,
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
    chief_editor: Callable[[AgentGraphState], Awaitable[dict[str, Any]]]
    tear_sheet: Callable[[AgentGraphState], Awaitable[dict[str, Any]]]
    persist_report: Callable[[AgentGraphState], Awaitable[dict[str, Any]]]
    progress_callback: Callable[..., Any] | None = None
    cancel_check: Callable[[], None] | None = None
    telemetry_callback: Callable[[dict[str, Any]], Any] | None = None


def create_default_workflow_services(
    *,
    rotator: Any | None = None,
    progress_callback: Callable[..., Any] | None = None,
    cancel_check: Callable[[], None] | None = None,
    telemetry_callback: Callable[[dict[str, Any]], Any] | None = None,
) -> WorkflowServices:
    active_rotator = rotator if rotator is not None else KeyRotator(LLM_API_KEYS_BY_PROVIDER)
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

    async def chief_editor(state: AgentGraphState) -> dict[str, Any]:
        context = legacy_context_from_graph(state, holder["services"])
        return run_chief_editor_synthesis(context)

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
        chief_editor=chief_editor,
        tear_sheet=tear_sheet,
        persist_report=persist_report,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
        telemetry_callback=telemetry_callback,
    )
    holder["services"] = services
    return services


def initialize_graph_state(data: dict[str, Any], *, pipeline_id: str) -> AgentGraphState:
    domain_state = initialize_agent_state(data)
    load_provider_values_from_payload(domain_state, data)
    validate_state_provider_values(domain_state)
    graph_state = agent_state_to_graph(domain_state, pipeline_id=normalize_pipeline_id(pipeline_id))
    prompt_config = load_agent_prompt_config()
    code_identity = runtime_code_identity()
    graph_state["prompt_version"] = str(prompt_config.get("prompt_version") or "agents:unversioned")
    graph_state["prompt_fingerprint"] = str(prompt_config.get("prompt_fingerprint") or "")
    graph_state["code_commit"] = str(code_identity.get("commit") or "")
    graph_state["code_dirty"] = (
        code_identity.get("dirty") if isinstance(code_identity.get("dirty"), bool) else None
    )
    graph_state["analyses"] = {}
    graph_state["structured_outputs"] = {}
    graph_state["blocking_issues"] = []
    graph_state["repair_attempt_counts"] = {}
    graph_state["agent_quality_retry_counts"] = {}
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
    data = input_data_from_state(state)
    year, season = latest_closed_quarter_for_reconciliation(data)
    reconciliation = reconcile_with_official_filing(domain_state, year=year, season=season)
    validate_state_provider_values(domain_state)
    graph_state = agent_state_to_graph(domain_state, pipeline_id=state.get("pipeline_id", "v1"))
    graph_state["tool_results"] = {
        "official_reconciliation": reconciliation,
        "data_reconciliation_plan": build_reconciliation_plan(domain_state),
    }
    return graph_state


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
    token_usage = (context.get("llm_token_usage") or {}).get(
        completed_agent_num,
        (context.get("llm_token_usage") or {}).get(str(completed_agent_num)),
    )
    if isinstance(token_usage, dict):
        delta["llm_token_usage"] = {str(completed_agent_num): copy_json(token_usage)}
    if report is not None:
        delta["agent_reports"] = {str(completed_agent_num): report.model_dump(mode="json")}
        if report.risk_flags:
            delta["risk_flags"] = [flag.model_dump(mode="json") for flag in report.risk_flags]

    new_blocking = [issue for issue in list(context.get("blocking_issues", []) or []) if issue not in before_blocking]
    if new_blocking:
        delta["blocking_issues"] = new_blocking
    agent_quality_retry_counts = context.get("agent_quality_retry_counts") or {}
    if agent_quality_retry_counts:
        delta["agent_quality_retry_counts"] = graph_agent_mapping(agent_quality_retry_counts)
    return delta
