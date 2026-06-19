"""Pipeline V3 final-report contract checks."""

from __future__ import annotations

import re

from structured_output_normalizer import structured_output_to_report_text
from validators import strip_generated_audit_sections


def _recommendation_block_at_tail(text: str) -> bool:
    return bool(re.search(r"\[投資建議\].*?\[/投資建議\]\s*$", text or "", re.DOTALL))


def v3_recommendation_contract_issues(
    analyses: dict,
    structured_outputs: dict,
    recommendation_agent: int | None,
    completed_agents: set[int],
) -> list[str]:
    if recommendation_agent is None:
        return []

    final_text = strip_generated_audit_sections(str(analyses.get(recommendation_agent, "")))
    structured = structured_outputs.get(recommendation_agent)
    if isinstance(structured, dict):
        final_text = strip_generated_audit_sections(
            structured_output_to_report_text(recommendation_agent, structured, final_text)
        )

    issues = []
    if "做空觸發條件（Catalyst for crash）" not in final_text:
        issues.append("缺少做空觸發條件（Catalyst for crash）章節。")
    if "防軋空停損點（Stop-loss level）" not in final_text:
        issues.append("缺少防軋空停損點（Stop-loss level）章節。")
    if recommendation_agent in completed_agents and not _recommendation_block_at_tail(final_text):
        issues.append("最終 [投資建議] 區塊未位於 Agent 19 輸出尾端。")
    return issues
