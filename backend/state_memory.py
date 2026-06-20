"""Shared AgentState initialization, merge, and view helpers."""

from __future__ import annotations

import copy
import math
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from agent_state import AgentReport, AgentState


STATE_VIEW_POLICY: dict[str, dict[str, list[str] | dict[str, list[str]]]] = {
    "11": {
        "root": ["validation_issues", "risk_flags", "macro_context"],
    },
    "13": {
        "normalized_financials": ["revenue_history", "net_income_history", "fcf_history", "cash_flow"],
        "quant_metrics": ["calculations", "unit_contract"],
        "root": ["validation_issues", "risk_flags", "alternative_data"],
    },
    "14": {
        "normalized_financials": ["revenue_history", "net_income_history", "fcf_history", "cash_flow"],
        "quant_metrics": ["calculations", "unit_contract"],
        "peer_context": ["selected_peers", "selection_policy", "dynamic_peer_metrics"],
        "root": ["risk_flags", "validation_issues", "tool_results", "alternative_data"],
    },
    "15": {
        "root": ["validation_issues", "risk_flags", "chip_context"],
    },
    "17": {
        "root": ["validation_issues", "risk_flags", "sentiment_context"],
    },
    "18": {
        "normalized_financials": ["revenue_history", "net_income_history", "fcf_history", "cash_flow"],
        "peer_context": ["dynamic_peer_metrics"],
        "root": ["validation_issues", "risk_flags", "chip_context"],
    },
    "20": {
        "root": ["validation_issues", "risk_flags", "earnings_call_context"],
    },
    "21": {
        "normalized_financials": ["revenue_history", "net_income_history", "fcf_history", "cash_flow"],
        "quant_metrics": ["calculations", "unit_contract"],
        "peer_context": ["selected_peers", "selection_policy", "dynamic_peer_metrics"],
        "root": ["risk_flags", "validation_issues", "tool_results", "agent_reports", "earnings_call_context"],
    },
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
    quant_metrics = copy.deepcopy(data.get("deterministic_financial_tool_results") or {})
    if isinstance(data.get("quant_metrics"), dict):
        quant_metrics.update(copy.deepcopy(data["quant_metrics"]))
    return AgentState(
        run_id=run_id or str(uuid.uuid4()),
        ticker=str(data.get("ticker") or ""),
        company_name=str(data.get("company_name") or data.get("name") or data.get("ticker") or ""),
        company_identity=copy.deepcopy(data.get("company_identity") or {}),
        raw_financial_data={"input": copy.deepcopy(data)},
        normalized_financials=copy.deepcopy(data),
        source_audit=copy.deepcopy(data.get("source_audit") or []),
        peer_context={"dynamic_peer_metrics": copy.deepcopy(data.get("dynamic_peer_metrics") or [])},
        quant_metrics=quant_metrics,
    )


def merge_agent_report(state: AgentState, report: AgentReport) -> AgentState:
    external_risk_flags = list(state.risk_flags)
    for managed_flag in (
        flag
        for current_report in state.agent_reports.values()
        for flag in current_report.risk_flags
    ):
        for index, existing_flag in enumerate(external_risk_flags):
            if existing_flag == managed_flag:
                external_risk_flags.pop(index)
                break

    stored_report = report.model_copy(deep=True)
    state.agent_reports[stored_report.agent_id] = stored_report
    state.risk_flags = external_risk_flags + [
        flag
        for current_report in state.agent_reports.values()
        for flag in current_report.risk_flags
    ]
    return state


def sync_context_from_state(context: dict[str, Any], state: AgentState) -> dict[str, Any]:
    context["agent_state"] = state
    analyses: dict[str | int, str] = {}
    structured_outputs: dict[str | int, dict[str, Any]] = {}
    for agent_id, report in state.agent_reports.items():
        legacy_agent_id = _legacy_agent_key(agent_id)
        analyses[legacy_agent_id] = report.markdown
        if report.structured_output is not None:
            structured_outputs[legacy_agent_id] = copy.deepcopy(report.structured_output)
    context["analyses"] = analyses
    context["structured_outputs"] = structured_outputs
    return context


def _pick(mapping: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: _jsonable(mapping[key]) for key in keys if key in mapping}


def _legacy_agent_key(agent_id: str) -> str | int:
    return int(agent_id) if agent_id.isdecimal() else agent_id


def state_view_for(role: str | int, state: AgentState) -> dict[str, Any]:
    role_key = str(role)
    if role_key == "4":
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
            external_context = _external_context_for_state(state)
            for key in keys:
                if key in external_context:
                    value = external_context[key]
                else:
                    value = getattr(state, key)
                view[key] = _jsonable(value)
            continue
        value = getattr(state, section)
        if isinstance(value, dict):
            view[section] = _pick(value, list(keys))
    return view


def _external_context_for_state(state: AgentState) -> dict[str, Any]:
    data = state.normalized_financials if isinstance(state.normalized_financials, dict) else {}
    return {
        "macro_context": copy.deepcopy(data.get("macro_indicators") or data.get("macro_context") or {}),
        "chip_context": copy.deepcopy(data.get("chip_data") or {}),
        "alternative_data": copy.deepcopy(data.get("alternative_data") or {}),
        "sentiment_context": copy.deepcopy(data.get("sentiment_context") or {}),
        "earnings_call_context": copy.deepcopy(data.get("earnings_call") or {}),
    }


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(mode="json"))
    if isinstance(value, Decimal):
        if value.is_nan():
            return None
        if value.is_infinite():
            return "Infinity" if value > 0 else "-Infinity"
        return float(value)
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return None
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return [_jsonable(item) for item in sorted(value, key=repr)]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {_jsonable_key(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return copy.deepcopy(value)


def _jsonable_key(value: Any) -> str:
    jsonable = _jsonable(value)
    if isinstance(jsonable, str):
        return jsonable
    return str(jsonable)
