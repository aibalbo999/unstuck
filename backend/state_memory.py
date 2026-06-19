"""Shared AgentState initialization, merge, and view helpers."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from agent_state import AgentReport, AgentState


STATE_VIEW_POLICY: dict[str, dict[str, list[str] | dict[str, list[str]]]] = {
    "valuation": {
        "normalized_financials": ["revenue_history", "net_income_history", "fcf_history", "cash_flow"],
        "quant_metrics": ["calculations", "unit_contract"],
        "peer_context": ["selected_peers", "selection_policy", "dynamic_peer_metrics"],
        "root": ["risk_flags", "validation_issues", "tool_results"],
    },
    "final_risk_memo": {
        "normalized_financials": ["revenue_history", "net_income_history", "fcf_history", "cash_flow"],
        "quant_metrics": ["calculations", "unit_contract"],
        "peer_context": ["selected_peers", "selection_policy"],
        "root": ["risk_flags", "validation_issues", "tool_results", "agent_reports"],
    },
}


def initialize_agent_state(data: dict[str, Any], *, run_id: str | None = None) -> AgentState:
    return AgentState(
        run_id=run_id or str(uuid.uuid4()),
        ticker=str(data.get("ticker") or ""),
        company_name=str(data.get("company_name") or data.get("name") or data.get("ticker") or ""),
        company_identity=dict(data.get("company_identity") or {}),
        raw_financial_data={"input": copy.deepcopy(data)},
        normalized_financials=copy.deepcopy(data),
        source_audit=list(data.get("source_audit") or []),
        peer_context={"dynamic_peer_metrics": list(data.get("dynamic_peer_metrics") or [])},
        quant_metrics=dict(data.get("deterministic_financial_tool_results") or {}),
    )


def merge_agent_report(state: AgentState, report: AgentReport) -> AgentState:
    state.agent_reports[report.agent_id] = report
    state.risk_flags.extend(report.risk_flags)
    return state


def sync_context_from_state(context: dict[str, Any], state: AgentState) -> dict[str, Any]:
    context["agent_state"] = state
    analyses = context.setdefault("analyses", {})
    structured_outputs = context.setdefault("structured_outputs", {})
    for agent_id, report in state.agent_reports.items():
        analyses[agent_id] = report.markdown
        if report.structured_output is not None:
            structured_outputs[agent_id] = report.structured_output
    return context


def _pick(mapping: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: copy.deepcopy(mapping[key]) for key in keys if key in mapping}


def state_view_for(role: str | int, state: AgentState) -> dict[str, Any]:
    role_key = str(role)
    if role_key in {"4", "14"}:
        role_key = "valuation"
    if role_key in {"7", "16", "19"}:
        role_key = "final_risk_memo"

    policy = STATE_VIEW_POLICY.get(role_key, {"root": ["validation_issues", "risk_flags"]})
    view: dict[str, Any] = {
        "run_id": state.run_id,
        "ticker": state.ticker,
        "company_name": state.company_name,
        "circuit_breaker": state.circuit_breaker.model_dump(mode="json"),
    }
    for section, keys in policy.items():
        if section == "root":
            for key in keys:
                value = getattr(state, key)
                view[key] = _jsonable(value)
            continue
        value = getattr(state, section)
        if isinstance(value, dict):
            view[section] = _pick(value, list(keys))
    return view


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return copy.deepcopy(value)
