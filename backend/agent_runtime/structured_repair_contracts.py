"""Structured-output completeness checks used by the repair loop."""

from __future__ import annotations

from analysis_types import AnalysisContext
from final_audit_mode_contracts import (
    v2_position_plan_contract_issues,
    v3_short_setup_contract_issues,
    v4_trade_setup_contract_issues,
)
from pipeline_modes import get_structured_agent_num


_NESTED_SECTIONS = {
    "moat": "moat_scores",
    "valuation": "price_targets",
    "recommendation": "recommendation",
}


def structured_output_missing(context: AnalysisContext, agent_num: int) -> bool:
    assigned_kinds = {
        kind
        for kind in (*_NESTED_SECTIONS, "position_plan", "short_setup", "trade_setup")
        if get_structured_agent_num(kind, context) == agent_num
    }
    if not assigned_kinds:
        return False

    outputs = context.get("structured_outputs", {}) or {}
    structured = outputs.get(agent_num, outputs.get(str(agent_num)))
    if not isinstance(structured, dict):
        return True

    if any(not structured.get(_NESTED_SECTIONS[kind]) for kind in assigned_kinds & _NESTED_SECTIONS.keys()):
        return True
    if "position_plan" in assigned_kinds:
        if v2_position_plan_contract_issues(structured.get("position_plan", {}) or {}):
            return True
    if "short_setup" in assigned_kinds:
        if v3_short_setup_contract_issues(structured.get("short_setup", {}) or {}):
            return True
    if "trade_setup" in assigned_kinds and v4_trade_setup_contract_issues(structured):
        return True
    return False


__all__ = ["structured_output_missing"]
