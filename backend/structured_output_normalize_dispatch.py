"""Normalize structured output payloads by agent number."""

from __future__ import annotations

from typing import Any, Optional

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_sequence_items, safe_text
from recommendation_labels import normalize_recommendation_label
from structured_output_normalizer_basic import (
    _MANAGEMENT_GUIDANCE_TONES,
    _MOAT_SCORE_ALIASES,
    _PRICE_TARGET_ALIASES,
    _coerce_number,
    _display_line,
    _has_string_key,
    _normalized_analysis_markdown,
    _pick_mapping_value,
    _raw_structured_payload_is_complete_enough,
    _string_field_line,
    _string_field_text,
)
from structured_output_normalizer_core import (
    _coerce_confidence_basis,
    _coerce_moat_payload,
    _coerce_next_catalysts,
    _coerce_price_target_payload,
    _coerce_reasoning_steps,
    _coerce_downside_risks,
    _coerce_scenario_triggers,
    _derive_next_catalysts_from_scenario_triggers,
)
from structured_output_normalizer_payloads import (
    _coerce_bear_advocate_payload,
    _coerce_downside_risk_rows,
    _coerce_management_sentiment_payload,
    _coerce_recommendation_payload,
    _coerce_trade_setup_payload,
)
from structured_output_normalizer_text import _plain_jsonish
from structured_output_validation import validated_structured_payload


def normalize_structured_output(agent_num: int, payload: Any) -> Optional[dict]:
    """Validate and normalize JSON payloads from structured agents."""
    payload = _plain_jsonish(payload)
    raw_payload = payload if isinstance(payload, dict) else {}
    if not _raw_structured_payload_is_complete_enough(agent_num, payload):
        return None
    if isinstance(payload, dict):
        if "reasoning_steps" in payload:
            payload = {**payload, "reasoning_steps": _coerce_reasoning_steps(payload.get("reasoning_steps"), minimum=3)}
        if "scenario_triggers" in payload:
            payload = {**payload, "scenario_triggers": _coerce_scenario_triggers(payload.get("scenario_triggers"))}
        if "confidence_basis" in payload:
            payload = {**payload, "confidence_basis": _coerce_confidence_basis(payload.get("confidence_basis"))}
        if "next_catalysts" in payload:
            next_catalysts = _coerce_next_catalysts(payload.get("next_catalysts"))
            if not next_catalysts:
                scenario_triggers = payload.get("scenario_triggers")
                if not safe_dict_list(scenario_triggers):
                    scenario_triggers = _coerce_scenario_triggers([])
                    payload = {**payload, "scenario_triggers": scenario_triggers}
                next_catalysts = _derive_next_catalysts_from_scenario_triggers(scenario_triggers)
            payload = {**payload, "next_catalysts": next_catalysts}
        if agent_num in {3, 12}:
            payload = _coerce_moat_payload(payload)
        if agent_num in {4, 14}:
            payload = _coerce_price_target_payload(payload)
        if agent_num in {7, 16, 19}:
            payload = _coerce_recommendation_payload(payload, default_label="避免" if agent_num == 19 else "持有")
            payload = _normalize_recommendation_payload_aliases(payload)
        if agent_num == 20:
            payload = _coerce_management_sentiment_payload(payload)
        if agent_num == 21:
            payload = _coerce_bear_advocate_payload(payload)
        if agent_num == 24:
            payload = _coerce_trade_setup_payload(payload)
    payload = validated_structured_payload(agent_num, payload)
    if payload is None:
        return None

    if agent_num in {3, 12}:
        raw_scores = safe_mapping_dict(raw_payload.get("moat_scores")) or {}
        reasoning_steps = _coerce_reasoning_steps(payload.get("reasoning_steps"))
        scores = {}
        for key, aliases in _MOAT_SCORE_ALIASES.items():
            score = _coerce_number(_pick_mapping_value(raw_scores, *aliases), 1, 10)
            if score is not None:
                scores[key] = score
        if not scores:
            validated_scores = safe_mapping_dict(payload.get("moat_scores")) or {}
            for key, aliases in _MOAT_SCORE_ALIASES.items():
                score = _coerce_number(_pick_mapping_value(validated_scores, *aliases), 1, 10)
                if score is not None:
                    scores[key] = score
        if not scores:
            return None
        return {
            "reasoning_steps": reasoning_steps,
            "moat_scores": scores,
            "analysis_markdown": _normalized_analysis_markdown(raw_payload, payload),
        }

    if agent_num in {4, 14}:
        raw_targets = safe_mapping_dict(raw_payload.get("price_targets")) or {}
        validated_targets = safe_mapping_dict(payload.get("price_targets")) or {}
        valuation_reasoning = {
            "dcf_reasoning": _string_field_text(_pick_mapping_value(raw_targets, "dcf_reasoning", "DCF推論", "DCF 推論"))
            or _string_field_text(validated_targets.get("dcf_reasoning")),
            "peer_reasoning": _string_field_text(_pick_mapping_value(raw_targets, "peer_reasoning", "同業推論", "同業比較推論"))
            or _string_field_text(validated_targets.get("peer_reasoning")),
            "scenario_reasoning": _string_field_text(_pick_mapping_value(raw_targets, "scenario_reasoning", "情境推論", "情境差異推論"))
            or _string_field_text(validated_targets.get("scenario_reasoning")),
        }
        raw_root_reasoning = payload.get("valuation_reasoning")
        if isinstance(raw_root_reasoning, dict):
            for key in ("dcf_reasoning", "peer_reasoning", "scenario_reasoning"):
                if not valuation_reasoning.get(key):
                    valuation_reasoning[key] = _string_field_text(raw_root_reasoning.get(key))
        valuation_reasoning = {key: value for key, value in valuation_reasoning.items() if value}
        target_map = {
            "熊": "熊市情境",
            "bear": "熊市情境",
            "基本": "基本情境",
            "base": "基本情境",
            "Base": "基本情境",
            "牛": "牛市情境",
            "bull": "牛市情境",
        }
        targets = {}
        for raw_key, raw_value in raw_targets.items():
            key_text = _display_line(raw_key)
            if not key_text:
                continue
            canonical = None
            for marker, mapped in target_map.items():
                if marker in key_text:
                    canonical = mapped
                    break
            if not canonical:
                continue
            price = _coerce_number(raw_value, 0, None)
            if price is not None:
                targets[canonical] = price
        if not targets:
            for canonical, aliases in _PRICE_TARGET_ALIASES.items():
                price = _coerce_number(_pick_mapping_value(validated_targets, *aliases), 0, None)
                if price is not None:
                    targets[canonical] = price
        if not targets:
            return None
        return {
            "price_targets": targets,
            "valuation_reasoning": valuation_reasoning,
            "valuation_summary": payload.get("valuation_summary", {}) if isinstance(payload.get("valuation_summary"), dict) else {},
            "dcf_scenarios": payload.get("dcf_scenarios", []) if isinstance(payload.get("dcf_scenarios"), list) else [],
            "analysis_markdown": _normalized_analysis_markdown(raw_payload, payload),
        }

    if agent_num == 20:
        guidance_tone = _string_field_text(payload.get("guidance_tone"), "資料不足")
        if guidance_tone not in _MANAGEMENT_GUIDANCE_TONES:
            guidance_tone = "資料不足"
        return {
            "guidance_tone": guidance_tone,
            "confidence": _coerce_number(raw_payload.get("confidence"), 0, 1) or 0.0,
            "highlights": list(payload.get("highlights") or [])[:3],
            "analysis_markdown": _normalized_analysis_markdown(raw_payload, payload),
        }

    if agent_num == 21:
        return {
            "thesis_summary": _string_field_text(payload.get("thesis_summary")),
            "downside_risks": _coerce_downside_risks(raw_payload.get("downside_risks"), payload.get("downside_risks")),
            "analysis_markdown": _normalized_analysis_markdown(raw_payload, payload),
        }

    if agent_num == 24:
        trade_setup = {
            "trade_direction": _string_field_text(payload.get("trade_direction"), "Neutral"),
            "entry_zone": _string_field_text(payload.get("entry_zone"), "N/A"),
            "target_price": _string_field_text(payload.get("target_price"), "N/A"),
            "stop_loss": _string_field_text(payload.get("stop_loss"), "N/A"),
            "core_catalyst": _string_field_text(payload.get("core_catalyst"), "N/A"),
            "risk_level": _string_field_text(payload.get("risk_level"), "High"),
        }
        if "analysis_markdown" in raw_payload or "analysis_markdown" in payload:
            trade_setup["analysis_markdown"] = _normalized_analysis_markdown(raw_payload, payload)
        return trade_setup

    if agent_num in {7, 16, 19}:
        raw_rec = payload.get("recommendation", {})
        reasoning_steps = _coerce_reasoning_steps(payload.get("reasoning_steps"))
        if not isinstance(raw_rec, dict) or not raw_rec:
            return None
        key_aliases = {
            "recommendation": "建議",
            "target_3m": "短期目標（3個月）",
            "target_6m": "中期目標（6個月）",
            "target_12m": "長期目標（12個月）",
            "long_term_potential_5y": "長期潛力（5年）",
            "confidence": "信心指數",
        }
        field_defaults = {
            "短期目標（3個月）": "N/A",
            "中期目標（6個月）": "N/A",
            "長期目標（12個月）": "N/A",
            "長期潛力（5年）": "N/A",
            "信心指數": "N/A",
        }
        normalized_rec = {}
        for key, value in raw_rec.items():
            if not isinstance(key, str):
                continue
            key_text = _string_field_line(key)
            normalized_key = key_aliases.get(key_text, key_text)
            if normalized_key == "建議":
                default_label = "避免" if agent_num == 19 else "持有"
                label_text = _string_field_text(value)
                if label_text:
                    label = normalize_recommendation_label(label_text)
                    normalized_value = label if label in {"買入", "持有", "避免", "放空"} else default_label
                elif normalized_key in normalized_rec:
                    continue
                else:
                    normalized_value = default_label
            else:
                normalized_value = _string_field_text(value, field_defaults.get(normalized_key, ""))
            normalized_rec[normalized_key] = normalized_value

        confidence_basis = payload.get("confidence_basis")
        if isinstance(confidence_basis, dict):
            normalized_rec["confidence_basis"] = confidence_basis

        return {
            "reasoning_steps": reasoning_steps,
            "recommendation": normalized_rec,
            "scenario_triggers": payload.get("scenario_triggers", []),
            "next_catalysts": payload.get("next_catalysts", []),
            "analysis_markdown": _normalized_analysis_markdown(raw_payload, payload),
        }

    return None


def _normalize_recommendation_payload_aliases(payload: dict) -> dict:
    recommendation = safe_mapping_dict(payload.get("recommendation"))
    if recommendation is None:
        return payload
    normalized = dict(recommendation)
    for key in ("建議", "recommendation"):
        if key in normalized and isinstance(normalized[key], str):
            label_text = _string_field_text(normalized[key])
            normalized[key] = normalize_recommendation_label(label_text) if label_text else "N/A"
    return {**payload, "recommendation": normalized}
