"""Chief editor synthesis for post-audit report smoothing."""

from __future__ import annotations

import copy
from typing import Any

from analysis_types import AnalysisContext


def run_chief_editor_synthesis(context: AnalysisContext) -> dict[str, Any]:
    """Synthesize a single editorial thesis without introducing new facts."""
    parsed = context.get("parsed", {}) or {}
    data = context.get("data", {}) or {}
    recommendation = parsed.get("recommendation", {}) or {}
    price_targets = parsed.get("price_targets", {}) or {}
    agent_reports = context.get("agent_state").agent_reports if context.get("agent_state") is not None else {}
    analyses = context.get("analyses", {}) or {}
    catalysts = _collect_context_catalysts(context)

    rec_text = _first_mapping_value(recommendation, "建議") or "持有"
    confidence = _first_mapping_value(recommendation, "信心") or "N/A"
    target_12m = _first_mapping_value(recommendation, "12個月") or price_targets.get("基本情境") or "N/A"
    risk_summary = _summarize_final_audit(context.get("final_audit") or {})
    thesis = (
        f"{data.get('ticker') or context.get('ticker') or '本標的'} 的核心投資論點為「{rec_text}」，"
        f"12 個月參考目標為 {target_12m}，信心 {confidence}。"
        f"多方主要依據估值、護城河與催化條件是否能互相驗證；空方焦點在財務品質、資料限制與下行情境。"
        f"{risk_summary}"
    )
    thesis = _cap_words(thesis, 300)

    resolved = []
    if price_targets and recommendation:
        resolved.append("估值與最終建議已收斂為以三情境區間約束建議目標。")
    if context.get("final_audit", {}).get("warnings"):
        resolved.append("最終稽核警示保留為信心折讓與後續追蹤條件。")
    if not resolved:
        resolved.append("未偵測到需要額外揭露的重大跨 Agent 矛盾。")

    lead_sections = []
    for agent_id, report in list(agent_reports.items())[:4]:
        lead_sections.append(f"- Agent {agent_id}：{_first_sentence(report.markdown)}")
    if not lead_sections:
        for agent_id, text in list(analyses.items())[:4]:
            lead_sections.append(f"- Agent {agent_id}：{_first_sentence(str(text))}")

    smoothed_markdown = "\n".join([
        "## Executive Thesis",
        thesis,
        "",
        "## 論點收斂",
        *[f"- {item}" for item in resolved],
        "",
        "## 部門觀點摘要",
        *(lead_sections or ["- 前序 Agent 報告不足，請查看各章節原文。"]),
    ]).strip()

    domain_state = context.get("agent_state")
    if domain_state is not None:
        domain_state.executive_thesis = thesis
        domain_state.smoothed_markdown = smoothed_markdown
        domain_state.next_catalysts = catalysts

    return {
        "executive_thesis": thesis,
        "smoothed_markdown": smoothed_markdown,
        "next_catalysts": catalysts,
        "structured_outputs": {
            "chief_editor": {
                "core_thesis": thesis,
                "bull_case_summary": "多方取決於成長、估值與催化條件能否同步驗證。",
                "bear_case_summary": "空方取決於財務品質、估值折讓與資料限制是否擴大。",
                "resolved_contradictions": resolved,
                "smoothed_markdown": smoothed_markdown,
            }
        },
        "agent_reports": {
            "chief_editor": {
                "agent_id": "chief_editor",
                "role": "Chief Editor / Synthesizer",
                "markdown": smoothed_markdown,
                "extracted_facts": {},
                "structured_output": {
                    "core_thesis": thesis,
                    "resolved_contradictions": resolved,
                },
                "risk_flags": [],
                "citations": [],
                "token_usage": {},
            }
        },
        "execution_trace": [{"id": "chief_editor", "node": "chief_editor"}],
    }


def _first_mapping_value(mapping: dict, needle: str) -> Any:
    for key, value in (mapping or {}).items():
        if needle in str(key):
            return value
    return None


def _summarize_final_audit(audit: dict) -> str:
    warnings = list(audit.get("warnings") or []) if isinstance(audit, dict) else []
    critical = list(audit.get("critical") or []) if isinstance(audit, dict) else []
    if critical:
        return f" 最終稽核仍有需注意事項：{str(critical[0])[:90]}。"
    if warnings:
        return f" 需留意非阻斷警示：{str(warnings[0])[:90]}。"
    return " 最終稽核未留下阻斷問題。"


def _first_sentence(text: str, limit: int = 120) -> str:
    cleaned = " ".join(str(text or "").replace("#", " ").split())
    if not cleaned:
        return "未提供可摘要內容。"
    for sep in ("。", ".", "；", ";"):
        if sep in cleaned:
            cleaned = cleaned.split(sep, 1)[0] + sep
            break
    return cleaned[:limit]


def _cap_words(text: str, max_words: int) -> str:
    words = str(text or "").split()
    if len(words) <= max_words:
        return str(text)
    return " ".join(words[:max_words]).rstrip() + "..."


def _collect_context_catalysts(context: AnalysisContext) -> list[dict[str, Any]]:
    catalysts = []
    for payload in (context.get("structured_outputs") or {}).values():
        if not isinstance(payload, dict):
            continue
        for item in payload.get("next_catalysts", []) or []:
            if isinstance(item, dict) and item.get("trigger_condition"):
                catalysts.append(copy.deepcopy(item))
    return catalysts[:5]
