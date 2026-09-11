"""Render the same source-validated assessment without replacing model evidence."""

from __future__ import annotations

from market_context_assessment import assess_final_market_context, market_assessment_text
from market_context_manifest import CONTRACT_VERSION, FINAL_AGENTS
from structured_output_report_text import structured_output_to_report_text


def final_market_report_text(context: dict, agent_num: int, raw_text: str) -> str:
    if agent_num not in FINAL_AGENTS or context.get("market_context_contract_version") != CONTRACT_VERSION:
        return raw_text
    current = assess_final_market_context(context)
    recorded = (context.get("final_audit") or {}).get("market_context")
    projection = recorded if recorded == current else current
    outputs = context.get("structured_outputs") or {}
    output = outputs.get(agent_num, outputs.get(str(agent_num)))
    if isinstance(output, dict):
        display = {**output, "market_context_assessment": projection["assessment"]}
        return structured_output_to_report_text(agent_num, display, raw_text)
    return raw_text + market_assessment_text(projection["assessment"])
