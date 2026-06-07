"""Prompt and payload helpers for context digest tasks."""

from __future__ import annotations

import json

from agent_catalog import AGENT_NAMES
from assistant_context import _format_previous, _format_structured_outputs_for_context
from structured_outputs import _extract_json_payload


def _build_context_digest_prompt(current_agent: int, context: dict) -> str:
    target = AGENT_NAMES.get(current_agent, f"Agent {current_agent}")
    previous = _format_previous(context, current_agent, include_digest=False, max_total_chars=16000)
    return (
        "請擔任投資研究提煉 Agent，將前序分析整理成給下一位分析師使用的結構化摘要。\n"
        f"下一位分析師：Agent {current_agent} {target}\n\n"
        "輸出請使用合法 JSON，不要 Markdown code fence。JSON schema:\n"
        "{\n"
        '  "decision_relevant_facts": ["..."],\n'
        '  "hard_metrics": {\n'
        '    "agent_2_fcf_conversion_rate": "精準數字、年度/期間、來源或 null",\n'
        '    "agent_2_normalized_fcf": "精準數字、單位、來源或 null",\n'
        '    "agent_2_margin_or_roe_flags": ["..."],\n'
        '    "agent_3_weakest_moat_factor": "弱項名稱、分數與原因或 null",\n'
        '    "agent_3_moat_score_matrix": {"品牌影響力": "分數或 null", "網路效應": "分數或 null", "轉換成本": "分數或 null", "成本優勢": "分數或 null", "專利技術": "分數或 null", "整體護城河": "分數或 null"},\n'
        '    "agent_4_price_target_band": {"熊市情境": "價格或 null", "基本情境": "價格或 null", "牛市情境": "價格或 null"},\n'
        '    "agent_5_growth_scenarios": ["情境、年營收、CAGR、資料限制或 null"],\n'
        '    "agent_14_price_target_band": {"熊市情境": "價格或 null", "基本情境": "價格或 null", "牛市情境": "價格或 null"},\n'
        '    "agent_15_chip_momentum": "外資/投信/自營商買賣超、P/E 河流圖位階與短線動能或 null"\n'
        "  },\n"
        '  "moat_weakness_matrix": [{"factor": "...", "score": "...", "weakness": "...", "evidence": "..."}],\n'
        '  "financial_cross_checks": ["..."],\n'
        '  "valuation_or_recommendation_implications": ["..."],\n'
        '  "risks_and_counterarguments": ["..."],\n'
        '  "open_data_quality_issues": ["..."]\n'
        "}\n\n"
        "已解析的結構化輸出：\n"
        f"{_format_structured_outputs_for_context(context)}\n\n"
        "前序分析精選片段（非全文，請只根據片段與結構化輸出提煉）：\n"
        f"{previous}"
    )


def _normalize_digest_text(text: str, current_agent: int, context: dict) -> str:
    payload = _extract_json_payload(text or "")
    if isinstance(payload, dict):
        payload = _ensure_digest_payload_shape(payload)
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return json.dumps(
        _fallback_context_digest_payload(current_agent, context, reason="提煉 Agent 未回傳可解析 JSON"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _fallback_context_digest_payload(current_agent: int, context: dict, reason: str) -> dict:
    completed = sorted(context.get("analyses", {}).keys())
    payload = {
        "digest_type": "deterministic_fallback",
        "reason": reason,
        "target_agent": current_agent,
        "completed_agents": completed,
        "structured_outputs": context.get("structured_outputs", {}),
        "instruction": "提煉摘要不可用時，下一個 Agent 必須優先使用結構化輸出與系統提供的前序精選片段，不應假設已讀全文。",
    }
    return _ensure_digest_payload_shape(payload)


def _ensure_digest_payload_shape(payload: dict) -> dict:
    """Keep digest JSON stable so downstream agents receive hard data slots."""
    payload = dict(payload)
    payload.setdefault("decision_relevant_facts", [])
    payload.setdefault("financial_cross_checks", [])
    payload.setdefault("valuation_or_recommendation_implications", [])
    payload.setdefault("risks_and_counterarguments", [])
    payload.setdefault("open_data_quality_issues", [])
    payload.setdefault("moat_weakness_matrix", [])

    hard_metrics = payload.get("hard_metrics")
    if not isinstance(hard_metrics, dict):
        hard_metrics = {}
    hard_metrics.setdefault("agent_2_fcf_conversion_rate", None)
    hard_metrics.setdefault("agent_2_normalized_fcf", None)
    hard_metrics.setdefault("agent_2_margin_or_roe_flags", [])
    hard_metrics.setdefault("agent_3_weakest_moat_factor", None)
    hard_metrics.setdefault("agent_3_moat_score_matrix", {})
    hard_metrics.setdefault("agent_4_price_target_band", {})
    hard_metrics.setdefault("agent_5_growth_scenarios", [])
    hard_metrics.setdefault("agent_14_price_target_band", {})
    hard_metrics.setdefault("agent_15_chip_momentum", None)
    payload["hard_metrics"] = hard_metrics
    return payload
