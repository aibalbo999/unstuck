"""Runtime handling for structured agent responses."""

from __future__ import annotations

import re
from analysis_types import AnalysisContext
from google_prompt_safety import GOOGLE_SCHEMA_VALUE_REPLACEMENTS
from json_utils import extract_json_payload
from llm_provider_routes import provider_for_model
from recommendation_labels import CANONICAL_RECOMMENDATIONS
from structured_output_models import STRUCTURED_AGENT_INSTRUCTIONS
from structured_output_normalizer import (
    normalize_structured_output,
    price_targets_have_unit_error,
    structured_output_to_report_text,
    warn_high_confidence_with_low_trust,
)
from valuation_output_contract import canonicalize_valuation_output
from trade_source_contract import missing_trade_fields, bind_trade_payload, trade_json_incomplete


def _sanitize_text(text: str) -> str:
    """Sanitize text to prevent structured JSON keys from leaking into the report."""
    if not text:
        return ""
    return re.sub(
        r'\b(peer_reasoning|dcf_reasoning|scenario_reasoning|analysis_markdown|moat_scores|price_targets|reasoning_steps)\b',
        r'\1_filtered',
        text
    )


def _decode_google_recommendation(agent_num: int, payload, model_id: str | None):
    """Reverse exact schema wire enums only at an identified Google response boundary."""
    if (
        agent_num not in {7, 16, 19}
        or not model_id
        or provider_for_model(model_id) != "google"
        or not isinstance(payload, dict)
        or not isinstance(payload.get("recommendation"), dict)
    ):
        return payload
    wire_to_product = {
        GOOGLE_SCHEMA_VALUE_REPLACEMENTS[label]: label
        for label in CANONICAL_RECOMMENDATIONS
    }
    recommendation = dict(payload["recommendation"])
    for field in ("建議", "recommendation"):
        value = recommendation.get(field)
        if isinstance(value, str) and value in wire_to_product:
            recommendation[field] = wire_to_product[value]
    return {**payload, "recommendation": recommendation}


def process_agent_response(
    agent_num: int, raw_text: str, context: AnalysisContext, *, model_id: str | None = None,
) -> str:
    """Persist JSON structured output and return report-ready text."""
    if agent_num not in STRUCTURED_AGENT_INSTRUCTIONS:
        return _sanitize_text(raw_text or "")

    if agent_num == 24:
        context.setdefault("structured_outputs", {}).pop(24, None)
        context["structured_outputs"].pop("24", None)
    if agent_num == 24 and trade_json_incomplete(raw_text):
        context["_trade_incomplete_fields"] = ["truncated_json"]
        return _sanitize_text(raw_text or "")
    payload = extract_json_payload(raw_text or "")
    if payload is None:
        if agent_num == 24:
            context["_trade_incomplete_fields"] = ["invalid_json"]
        return _sanitize_text(raw_text or "")
    trade_assessment = None
    if agent_num == 24:
        outputs = context.setdefault("structured_outputs", {})
        outputs.pop(24, None)
        outputs.pop("24", None)
        missing = missing_trade_fields(payload)
        if missing:
            context["_trade_incomplete_fields"] = missing
            return _sanitize_text(raw_text or "")
        context.pop("_trade_incomplete_fields", None)
        payload, trade_assessment = bind_trade_payload(payload, context)
    payload = _decode_google_recommendation(agent_num, payload, model_id)
    structured = normalize_structured_output(agent_num, payload)
    if not structured:
        if isinstance(payload, dict) and "analysis_markdown" in payload:
            fallback = str(payload.get("analysis_markdown", "")).strip()
            if fallback:
                return _sanitize_text(fallback)

        return _sanitize_text(raw_text or "")

    if trade_assessment is not None:
        structured["source_assessment"] = trade_assessment

    if agent_num in {4, 14}:
        structured = canonicalize_valuation_output(structured, context.get("data", {}))
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
