"""Management guidance sentiment report adapter for Agent 20."""

from __future__ import annotations

from agent_state import AgentReport, RiskFlag, Severity


class SentimentAnalysisAgent:
    agent_id = "20"
    role = "管理層語氣與法說會分析"

    @classmethod
    def build_report(cls, payload: dict) -> AgentReport:
        tone = str(payload.get("guidance_tone") or "資料不足")
        confidence = _confidence(payload.get("confidence"))
        highlights = list(payload.get("highlights") or [])[:3]
        flags = []
        if tone == "保守":
            flags.append(RiskFlag(
                id="management_guidance_conservative",
                severity=Severity.warning,
                category="sentiment",
                title="管理層展望語氣偏保守",
                evidence_refs=[str(item.get("quote") or item.get("keyword") or "") for item in highlights],
                source_agents=[cls.agent_id],
                impact="管理層對需求、供應鏈或獲利展望的措辭偏保守，成長假設應下修。",
                confidence=confidence,
            ))
        return AgentReport(
            agent_id=cls.agent_id,
            role=cls.role,
            markdown=str(payload.get("analysis_markdown") or ""),
            extracted_facts={"guidance_tone": tone, "confidence": confidence, "highlights": highlights},
            structured_output=dict(payload),
            risk_flags=flags,
        )


def _confidence(value) -> float:
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.0
