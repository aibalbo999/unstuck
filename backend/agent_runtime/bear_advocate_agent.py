"""Downside thesis report adapter for the Devil's Advocate Agent 21."""

from __future__ import annotations

from agent_state import AgentReport, RiskFlag, Severity


class BearAdvocateAgent:
    agent_id = "21"
    role = "紅軍與空頭反證"

    @classmethod
    def build_report(cls, payload: dict) -> AgentReport:
        risks = list(payload.get("downside_risks") or [])[:5]
        risk_flags = [
            RiskFlag(
                id=f"bear_case_{index}",
                severity=_severity(item.get("severity")),
                category="valuation",
                title=str(item.get("title") or f"空頭風險 {index}"),
                evidence_refs=[str(item.get("evidence") or "資料不足")],
                source_agents=[cls.agent_id],
                impact=str(item.get("impact") or item.get("evidence") or "可能造成估值或獲利下修。"),
                confidence=_confidence(item.get("confidence", 0.7)),
            )
            for index, item in enumerate(risks, 1)
            if isinstance(item, dict)
        ]
        return AgentReport(
            agent_id=cls.agent_id,
            role=cls.role,
            markdown=str(payload.get("analysis_markdown") or ""),
            extracted_facts={"thesis_summary": str(payload.get("thesis_summary") or ""), "downside_risks": risks},
            structured_output=dict(payload),
            risk_flags=risk_flags,
        )


def _severity(value) -> Severity:
    try:
        return Severity(str(value or "high"))
    except ValueError:
        return Severity.high


def _confidence(value) -> float:
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.7
