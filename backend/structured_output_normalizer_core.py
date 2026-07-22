"""Core coercion helpers for structured output normalization."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_sequence_items
from structured_output_list_coercion import (
    coerce_confidence_basis as _coerce_confidence_basis, coerce_reasoning_steps as _coerce_reasoning_steps,
    coerce_required_text_list as _coerce_required_text_list, coerce_string_text_list as _coerce_string_text_list,
)
from structured_output_normalizer_basic import (
    _MOAT_SCORE_ALIASES,
    _PRICE_TARGET_ALIASES,
    _SCENARIO_TRIGGER_FALLBACK,
    _coerce_bool,
    _coerce_number,
    _display_line,
    _display_text,
    _pick_mapping_value,
    _string_field_line,
    _string_field_text,
)


def _coerce_scenario_triggers(value: Any, minimum: int = 2, maximum: int = 5) -> list[dict[str, str]]:
    if value is None or not isinstance(value, (list, tuple)):
        return [dict(_SCENARIO_TRIGGER_FALLBACK) for _ in range(minimum)]
    items = safe_sequence_items(value)
    if isinstance(value, (list, tuple)) and not items:
        return [dict(_SCENARIO_TRIGGER_FALLBACK) for _ in range(minimum)]
    triggers = []
    fallbacks = []
    for item in items:
        row = safe_mapping_dict(item)
        if row is None:
            fallbacks.append(dict(_SCENARIO_TRIGGER_FALLBACK))
            continue
        condition = _string_field_line(row.get("trigger_condition"))
        action = _string_field_line(row.get("action"))
        direction = _string_field_line(row.get("direction"), "neutral_review")
        if direction not in {"bullish_upgrade", "bearish_downgrade", "neutral_review"}:
            direction = "neutral_review"
        if len(condition) < 10 or len(action) < 5:
            fallbacks.append({
                "trigger_condition": condition if len(condition) >= 10 else _SCENARIO_TRIGGER_FALLBACK["trigger_condition"],
                "action": action if len(action) >= 5 else _SCENARIO_TRIGGER_FALLBACK["action"],
                "direction": direction,
            })
            continue
        triggers.append({
            "trigger_condition": condition,
            "action": action,
            "direction": direction,
        })
    while len(items) >= minimum and len(triggers) < minimum and fallbacks:
        triggers.append(fallbacks.pop(0))
    return triggers[:maximum]


def _coerce_next_catalysts(value: Any) -> list[dict[str, str]]:
    catalysts = []
    fallbacks = []
    for item in safe_sequence_items(value):
        row = safe_mapping_dict(item)
        if row is None:
            fallbacks.append({
                "event_name": "待確認催化事件",
                "expected_timeframe": "待後續資料確認",
                "impact_direction": "volatile",
                "trigger_condition": "待後續資料確認",
            })
            continue
        impact_direction = _string_field_line(row.get("impact_direction"), "volatile")
        if impact_direction not in {"bullish", "bearish", "volatile"}:
            impact_direction = "volatile"
        event_name = _string_field_line(row.get("event_name"))
        expected_timeframe = _string_field_line(row.get("expected_timeframe"))
        trigger_condition = _string_field_line(row.get("trigger_condition"))
        catalyst = {
            "event_name": event_name or "待確認催化事件",
            "expected_timeframe": expected_timeframe or "待後續資料確認",
            "impact_direction": impact_direction,
            "trigger_condition": trigger_condition if len(trigger_condition) >= 5 else "待後續資料確認",
        }
        if event_name and expected_timeframe and len(trigger_condition) >= 5:
            catalysts.append(catalyst)
        else:
            fallbacks.append(catalyst)
    if not catalysts and fallbacks:
        catalysts.append(fallbacks[0])
    return catalysts


def _derive_next_catalysts_from_scenario_triggers(value: Any) -> list[dict[str, str]]:
    catalysts = []
    for idx, trigger in enumerate(safe_dict_list(value), start=1):
        condition = _string_field_line(trigger.get("trigger_condition"))
        if len(condition) < 5:
            continue
        direction = _string_field_line(trigger.get("direction"))
        if "bullish" in direction:
            impact = "bullish"
        elif "bearish" in direction:
            impact = "bearish"
        else:
            impact = "volatile"
        catalysts.append({
            "event_name": f"Scenario trigger {idx}",
            "expected_timeframe": "待後續資料確認",
            "impact_direction": impact,
            "trigger_condition": condition,
        })
    return catalysts


def _coerce_dcf_scenarios(value: Any) -> list[dict[str, float | str]]:
    scenarios = []
    for row in safe_dict_list(value):
        scenario = _display_line(row.get("scenario")).lower()
        if scenario not in {"bear", "base", "bull"}:
            continue
        revenue_growth_bias = _coerce_number(row.get("revenue_growth_bias_pct"))
        margin_bias = _coerce_number(row.get("margin_bias_pct"))
        wacc = _coerce_number(row.get("wacc_pct"), 0.01, None)
        intrinsic_value = _coerce_number(row.get("intrinsic_value"), 0, None)
        scenarios.append({
            "scenario": scenario,
            "revenue_growth_bias_pct": revenue_growth_bias if revenue_growth_bias is not None else 0.0,
            "margin_bias_pct": margin_bias if margin_bias is not None else 0.0,
            "wacc_pct": wacc if wacc is not None else 1.0,
            "intrinsic_value": intrinsic_value if intrinsic_value is not None else 0.0,
        })
        if len(scenarios) >= 3:
            break
    return scenarios


def _coerce_moat_payload(value: Any) -> Any:
    payload = safe_mapping_dict(value)
    if payload is None:
        return value
    scores = safe_mapping_dict(payload.get("moat_scores"))
    normalized = {
        **payload,
        "analysis_markdown": _display_text(payload.get("analysis_markdown"), "資料不足"),
    }
    if scores is None:
        return normalized

    normalized_scores = dict(scores)
    for key, aliases in _MOAT_SCORE_ALIASES.items():
        score = _coerce_number(_pick_mapping_value(scores, *aliases), 1, 10)
        normalized_scores[key] = score if score is not None else 1.0
    return {
        **normalized,
        "moat_scores": normalized_scores,
    }


def _coerce_downside_risks(raw_value: Any, validated_value: Any) -> list[dict[str, Any]]:
    risks = []
    for idx, risk in enumerate(safe_dict_list(validated_value)[:5]):
        normalized = dict(risk)
        confidence = _coerce_number(normalized.get("confidence"), 0, 1)
        normalized["confidence"] = confidence if confidence is not None else 0.7
        risks.append(normalized)
    return risks


def _coerce_price_target_payload(value: Any) -> Any:
    payload = safe_mapping_dict(value)
    if payload is None:
        return value
    targets = safe_mapping_dict(payload.get("price_targets"))
    if targets is None:
        return payload
    summary = safe_mapping_dict(payload.get("valuation_summary"))
    if summary is not None:
        primary_method = _string_field_line(summary.get("primary_method"), "blended")
        if primary_method not in {"normalized_dcf", "relative_valuation", "blended"}:
            primary_method = "blended"
        summary = {
            **summary,
            "primary_method": primary_method,
            "uses_market_value_wacc": _coerce_bool(summary.get("uses_market_value_wacc")),
            "uses_normalized_fcf": _coerce_bool(summary.get("uses_normalized_fcf")),
            "double_counting_check": _string_field_text(summary.get("double_counting_check"), "資料不足"),
        }

    normalized_targets = {
        **targets,
        "dcf_reasoning": _string_field_text(
            _pick_mapping_value(targets, "dcf_reasoning", "DCF推論", "DCF 推論"),
            "資料不足",
        ),
        "peer_reasoning": _string_field_text(
            _pick_mapping_value(targets, "peer_reasoning", "同業推論", "同業比較推論"),
            "資料不足",
        ),
        "scenario_reasoning": _string_field_text(
            _pick_mapping_value(targets, "scenario_reasoning", "情境推論", "情境差異推論"),
            "資料不足",
        ),
    }
    for key, aliases in _PRICE_TARGET_ALIASES.items():
        price = _coerce_number(_pick_mapping_value(targets, *aliases), 0, None)
        normalized_targets[key] = price if price is not None else 0.0

    normalized = {
        **payload,
        "price_targets": normalized_targets,
        "analysis_markdown": _display_text(payload.get("analysis_markdown"), "資料不足"),
    }
    if summary is not None:
        normalized["valuation_summary"] = summary
    if "dcf_scenarios" in payload:
        normalized["dcf_scenarios"] = _coerce_dcf_scenarios(payload.get("dcf_scenarios"))
    return normalized
