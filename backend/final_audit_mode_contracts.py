"""Mode-specific final-report contract checks."""

from __future__ import annotations

import re

from structured_output_normalizer import structured_output_to_report_text
from validators import strip_generated_audit_sections


REQUIRED_TRADE_SETUP_FIELDS = {
    "trade_direction",
    "entry_zone",
    "target_price",
    "stop_loss",
    "core_catalyst",
    "risk_level",
}


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


def v4_trade_setup_contract_issues(trade_setup: dict) -> list[str]:
    issues = []
    missing = sorted(
        key for key in REQUIRED_TRADE_SETUP_FIELDS if not str(trade_setup.get(key, "")).strip()
    )
    if missing:
        issues.append(f"缺少極短線交易欄位：{', '.join(missing)}")
    if trade_setup.get("trade_direction") not in {"Long", "Short", "Neutral"}:
        issues.append(f"trade_direction 不在允許值內：{trade_setup.get('trade_direction') or '空白'}")
    if trade_setup.get("risk_level") not in {"High", "Medium", "Low"}:
        issues.append(f"risk_level 不在允許值內：{trade_setup.get('risk_level') or '空白'}")
    return issues
