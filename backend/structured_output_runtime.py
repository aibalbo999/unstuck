"""Runtime handling for structured agent responses."""

from __future__ import annotations

import re
from analysis_types import AnalysisContext
from json_utils import extract_json_payload
from structured_output_models import STRUCTURED_AGENT_INSTRUCTIONS
from structured_output_normalizer import (
    normalize_structured_output,
    price_targets_have_unit_error,
    structured_output_to_report_text,
    warn_high_confidence_with_low_trust,
)


def _sanitize_text(text: str) -> str:
    """Sanitize text to prevent structured JSON keys from leaking into the report."""
    if not text:
        return ""
    return re.sub(
        r'\b(peer_reasoning|dcf_reasoning|scenario_reasoning|analysis_markdown|moat_scores|price_targets|reasoning_steps)\b',
        r'\1_filtered',
        text
    )


def process_agent_response(agent_num: int, raw_text: str, context: AnalysisContext) -> str:
    """Persist JSON structured output and return report-ready text."""
    if agent_num not in STRUCTURED_AGENT_INSTRUCTIONS:
        return _sanitize_text(raw_text or "")

    payload = extract_json_payload(raw_text or "")
    if payload is None:
        return _sanitize_text(raw_text or "")
    structured = normalize_structured_output(agent_num, payload)
    if not structured:
        if isinstance(payload, dict) and "analysis_markdown" in payload:
            fallback = str(payload.get("analysis_markdown", "")).strip()
            if fallback:
                return _sanitize_text(fallback)

        return _sanitize_text(raw_text or "")

    if agent_num in {4, 14}:
        current_price = context.get("data", {}).get("current_price")
        targets = structured.get("price_targets", {})
        if price_targets_have_unit_error(targets, current_price):
            warning = (
                "## 系統品質檢查警示\n"
                "- Agent 4 結構化目標價疑似發生單位縮寫錯誤，已拒絕寫入圖表資料。"
                "請重跑或檢查估值正文中的完整股價數字。"
            )
            body = structured.get("analysis_markdown") or raw_text or ""
            return _sanitize_text(f"{body}\n\n{warning}".strip())

    warn_high_confidence_with_low_trust(agent_num, structured, context)
    context.setdefault("structured_outputs", {})[agent_num] = structured
    final_text = structured_output_to_report_text(agent_num, structured, raw_text)
    return _sanitize_text(final_text)
