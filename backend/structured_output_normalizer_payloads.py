"""Payload-specific coercers for structured output normalization."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_sequence_items
from recommendation_labels import normalize_recommendation_label
from structured_output_normalizer_basic import (
    _MANAGEMENT_GUIDANCE_TONES,
    _TRADE_DIRECTIONS,
    _TRADE_RISK_LEVELS,
    _coerce_number,
    _display_text,
    _string_field_line,
    _string_field_text,
)


_POSITION_ACTIONS = {"進場", "續抱", "減碼", "等待"}


def _coerce_position_plan_payload(value: Any) -> dict[str, str]:
    plan = safe_mapping_dict(value) or {}
    action = _string_field_line(plan.get("action"))
    return {
        "action": action if action in _POSITION_ACTIONS else "資料不足",
        "entry_zone": _string_field_line(plan.get("entry_zone"), "資料不足，等待可驗證進場條件"),
        "position_size": _string_field_line(plan.get("position_size"), "資料不足"),
        "stop_loss": _string_field_line(plan.get("stop_loss"), "資料不足，暫不建立部位"),
        "risk_reward": _string_field_line(plan.get("risk_reward"), "資料不足"),
        "invalidation_condition": _string_field_line(plan.get("invalidation_condition"), "資料不足"),
    }


def _coerce_short_setup_payload(value: Any) -> dict[str, str]:
    setup = safe_mapping_dict(value) or {}
    return {
        "entry_trigger": _string_field_line(setup.get("entry_trigger"), "資料不足，等待可驗證做空觸發"),
        "downside_target": _string_field_line(setup.get("downside_target"), "資料不足"),
        "cover_stop": _string_field_line(setup.get("cover_stop"), "資料不足，暫不建立空方部位"),
        "squeeze_risk": _string_field_line(setup.get("squeeze_risk"), "資料不足"),
        "thesis_invalidation": _string_field_line(setup.get("thesis_invalidation"), "資料不足"),
    }


def _coerce_downside_risk_rows(value: Any, minimum: int = 3, maximum: int = 5) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return [
            {
                "title": "下行風險",
                "evidence": "資料不足",
                "impact": "",
                "severity": "warning",
                "confidence": 0.7,
            }
            for _ in range(minimum)
        ]
    risks = []
    fallbacks = []
    for item in safe_sequence_items(value):
        row = safe_mapping_dict(item)
        if row is None:
            fallbacks.append({
                "title": "下行風險",
                "evidence": "資料不足",
                "impact": "",
                "severity": "warning",
                "confidence": 0.7,
            })
            continue
        title = _string_field_line(row.get("title"))
        evidence = _string_field_line(row.get("evidence"))
        severity = _string_field_line(row.get("severity"), "warning")
        if severity not in {"warning", "high", "critical"}:
            severity = "warning"
        confidence = _coerce_number(row.get("confidence"), 0, 1)
        risk = {
            **row,
            "title": title or "下行風險",
            "evidence": evidence or "資料不足",
            "impact": _string_field_line(row.get("impact")),
            "severity": severity,
            "confidence": confidence if confidence is not None else 0.7,
        }
        if title and evidence:
            risks.append(risk)
        else:
            fallbacks.append(risk)
    while len(risks) < minimum and fallbacks:
        risks.append(fallbacks.pop(0))
    while len(risks) < minimum:
        risks.append({
            "title": "下行風險",
            "evidence": "資料不足",
            "impact": "",
            "severity": "warning",
            "confidence": 0.7,
        })
    return risks[:maximum]


def _coerce_bear_advocate_payload(value: Any) -> Any:
    payload = safe_mapping_dict(value)
    if payload is None:
        return value

    return {
        **payload,
        "thesis_summary": _string_field_text(payload.get("thesis_summary"), "資料不足"),
        "downside_risks": _coerce_downside_risk_rows(payload.get("downside_risks")),
        "analysis_markdown": _display_text(payload.get("analysis_markdown"), "資料不足"),
    }


def _coerce_management_highlights(value: Any, required: int = 3) -> list[dict[str, str]]:
    if not isinstance(value, (list, tuple)):
        return [{"keyword": "亮點", "quote": "資料不足"} for _ in range(required)]
    highlights = []
    fallbacks = []
    for item in safe_sequence_items(value):
        row = safe_mapping_dict(item)
        if row is None:
            fallbacks.append({"keyword": "亮點", "quote": "資料不足"})
            continue
        keyword = _string_field_line(row.get("keyword"))
        quote = _string_field_line(row.get("quote"))
        highlight = {
            **row,
            "keyword": keyword or "亮點",
            "quote": quote or "資料不足",
        }
        if keyword and quote:
            highlights.append(highlight)
        else:
            fallbacks.append(highlight)
    while len(highlights) < required and fallbacks:
        highlights.append(fallbacks.pop(0))
    while len(highlights) < required:
        highlights.append({"keyword": "亮點", "quote": "資料不足"})
    return highlights[:required]


def _coerce_management_sentiment_payload(value: Any) -> Any:
    payload = safe_mapping_dict(value)
    if payload is None:
        return value

    guidance_tone = _string_field_line(payload.get("guidance_tone"), "資料不足")
    if guidance_tone not in _MANAGEMENT_GUIDANCE_TONES:
        guidance_tone = "資料不足"

    confidence = _coerce_number(payload.get("confidence"), 0, 1)

    return {
        **payload,
        "guidance_tone": guidance_tone,
        "confidence": confidence if confidence is not None else 0.0,
        "highlights": _coerce_management_highlights(payload.get("highlights")),
        "analysis_markdown": _display_text(payload.get("analysis_markdown"), "資料不足"),
    }


def _coerce_trade_setup_payload(value: Any) -> Any:
    payload = safe_mapping_dict(value)
    if payload is None:
        return value

    trade_direction = _string_field_line(payload.get("trade_direction"))
    risk_level = _string_field_line(payload.get("risk_level"))
    if trade_direction not in _TRADE_DIRECTIONS:
        trade_direction = "Neutral"
    if risk_level not in _TRADE_RISK_LEVELS:
        risk_level = "High"
    return {
        **payload,
        "trade_direction": trade_direction,
        "entry_zone": _string_field_line(payload.get("entry_zone"), "N/A"),
        "target_price": _string_field_line(payload.get("target_price"), "N/A"),
        "stop_loss": _string_field_line(payload.get("stop_loss"), "N/A"),
        "core_catalyst": _string_field_line(payload.get("core_catalyst"), "N/A"),
        "risk_level": risk_level,
    }


def _coerce_recommendation_payload(value: Any, default_label: str = "持有") -> Any:
    payload = safe_mapping_dict(value)
    if payload is None:
        return value
    recommendation = safe_mapping_dict(payload.get("recommendation"))
    if recommendation is None:
        return payload

    key_aliases = {
        "recommendation": "建議",
        "target_3m": "短期目標（3個月）",
        "target_6m": "中期目標（6個月）",
        "target_12m": "長期目標（12個月）",
        "long_term_potential_5y": "長期潛力（5年）",
        "confidence": "信心指數",
    }
    defaults = {
        "建議": default_label,
        "短期目標（3個月）": "N/A",
        "中期目標（6個月）": "N/A",
        "長期目標（12個月）": "N/A",
        "長期潛力（5年）": "N/A",
        "信心指數": "N/A",
    }
    normalized = {}
    for raw_key, raw_value in recommendation.items():
        if not isinstance(raw_key, str):
            continue
        key_text = _string_field_line(raw_key)
        key = key_aliases.get(key_text, key_text)
        if not key:
            continue
        if key == "建議":
            if isinstance(raw_value, str):
                label = normalize_recommendation_label(raw_value)
                normalized[key] = label if label in {"買入", "持有", "避免", "放空"} else defaults[key]
            elif key not in normalized:
                normalized[key] = defaults[key]
        elif key in defaults:
            normalized[key] = _string_field_line(raw_value, defaults[key])
        else:
            normalized[key] = _string_field_text(raw_value)

    return {
        **payload,
        "recommendation": {**recommendation, **normalized},
        "analysis_markdown": _display_text(payload.get("analysis_markdown"), "資料不足"),
    }
