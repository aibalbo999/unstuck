"""Scenario trigger and catalyst mixins for recommendation schemas."""

from __future__ import annotations

from pydantic import Field, model_validator

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_sequence_items, safe_text
from recommendation_labels import normalize_recommendation_label
from structured_output_model_base import (
    AnalysisMarkdownMixin,
    _safe_mapping_has_key,
    _safe_mapping_value,
    _safe_required_text_list,
)
from structured_output_recommendation_types import (
    _MAX_SCENARIO_TRIGGERS,
    _MIN_SCENARIO_TRIGGERS,
    _NEXT_CATALYST_IMPACT_DIRECTIONS,
    _RECOMMENDATION_KEY_ALIASES,
    _RECOMMENDATION_TEXT_DEFAULTS,
    _SCENARIO_TRIGGER_DIRECTIONS,
    _SCENARIO_TRIGGER_FALLBACK,
    _safe_string_text,
    _scenario_triggers_fallback,
    Catalyst,
)


class ReasoningStepsMixin(AnalysisMarkdownMixin):
    @model_validator(mode="before")
    @classmethod
    def sanitize_reasoning_steps(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return payload
        raw_steps = root.get("reasoning_steps")
        if not isinstance(raw_steps, (list, tuple)):
            return {**root, "reasoning_steps": ["待補推論步驟", "待補推論步驟", "待補推論步驟"]}
        return {**root, "reasoning_steps": _safe_required_text_list(raw_steps, 3, "待補推論步驟")}


def _safe_scenario_triggers(payload) -> list[dict]:
    root = safe_mapping_dict(payload)
    if root is None:
        return []
    raw_trigger_items = _safe_mapping_value(root, "scenario_triggers")
    if _safe_mapping_has_key(root, "scenario_triggers") and not isinstance(raw_trigger_items, (list, tuple)):
        return _scenario_triggers_fallback()
    trigger_items = safe_sequence_items(raw_trigger_items)
    safe_triggers = []
    fallbacks = []
    for item in trigger_items:
        trigger = safe_mapping_dict(item)
        if trigger is None:
            fallbacks.append(dict(_SCENARIO_TRIGGER_FALLBACK))
            continue
        condition = _safe_string_text(_safe_mapping_value(trigger, "trigger_condition"))
        action = _safe_string_text(_safe_mapping_value(trigger, "action"))
        direction = _safe_string_text(_safe_mapping_value(trigger, "direction"))
        if direction not in _SCENARIO_TRIGGER_DIRECTIONS:
            direction = "neutral_review"
        if len(condition) < 10 or len(action) < 5:
            fallbacks.append({
                "trigger_condition": (
                    condition if len(condition) >= 10 else _SCENARIO_TRIGGER_FALLBACK["trigger_condition"]
                ),
                "action": action if len(action) >= 5 else _SCENARIO_TRIGGER_FALLBACK["action"],
                "direction": direction,
            })
            continue
        safe_triggers.append({
            "trigger_condition": condition,
            "action": action,
            "direction": direction,
        })
        if len(safe_triggers) >= _MAX_SCENARIO_TRIGGERS:
            break
    while len(trigger_items) >= _MIN_SCENARIO_TRIGGERS and len(safe_triggers) < _MIN_SCENARIO_TRIGGERS and fallbacks:
        safe_triggers.append(fallbacks.pop(0))
    return safe_triggers


def _catalysts_from_scenario_triggers(payload) -> list[dict]:
    catalysts = []
    for idx, trigger in enumerate(_safe_scenario_triggers(payload)[:3], start=1):
        condition = trigger["trigger_condition"]
        direction = trigger["direction"]
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


def _should_derive_next_catalysts(root: dict, safe_existing_catalysts: list[dict]) -> bool:
    if not _safe_mapping_has_key(root, "next_catalysts"):
        return True
    raw_next_catalysts = _safe_mapping_value(root, "next_catalysts")
    if raw_next_catalysts is None:
        return True
    if not isinstance(raw_next_catalysts, (list, tuple)):
        return True
    return bool(raw_next_catalysts) and not safe_existing_catalysts


def _safe_existing_next_catalysts(root: dict) -> list[dict]:
    raw_next_catalysts = _safe_mapping_value(root, "next_catalysts")
    if not isinstance(raw_next_catalysts, (list, tuple)):
        return []
    safe_rows = []
    for catalyst in safe_dict_list(raw_next_catalysts):
        event_name = _safe_string_text(_safe_mapping_value(catalyst, "event_name"))
        expected_timeframe = _safe_string_text(_safe_mapping_value(catalyst, "expected_timeframe"))
        impact_direction = _safe_string_text(_safe_mapping_value(catalyst, "impact_direction"))
        trigger_condition = _safe_string_text(_safe_mapping_value(catalyst, "trigger_condition"))
        if (
            not event_name
            or not expected_timeframe
            or impact_direction not in _NEXT_CATALYST_IMPACT_DIRECTIONS
            or len(trigger_condition) < 5
        ):
            continue
        safe_rows.append({
            "event_name": event_name,
            "expected_timeframe": expected_timeframe,
            "impact_direction": impact_direction,
            "trigger_condition": trigger_condition,
        })
    return safe_rows


def _populate_safe_next_catalysts(payload):
    root = safe_mapping_dict(payload)
    if root is None:
        return payload
    safe_triggers = _safe_scenario_triggers(root)
    if not safe_triggers:
        return payload
    normalized_payload = {**root, "scenario_triggers": safe_triggers}
    safe_existing_catalysts = _safe_existing_next_catalysts(root)
    if safe_existing_catalysts:
        normalized_payload = {**normalized_payload, "next_catalysts": safe_existing_catalysts}
    elif _should_derive_next_catalysts(root, safe_existing_catalysts):
        catalysts = _catalysts_from_scenario_triggers(normalized_payload)
        if catalysts:
            normalized_payload = {**normalized_payload, "next_catalysts": catalysts}
    return normalized_payload


class NextCatalystsMixin(ReasoningStepsMixin):
    next_catalysts: list[Catalyst] = Field(default_factory=list, min_length=1)

    @model_validator(mode="before")
    @classmethod
    def populate_next_catalysts_from_scenario_triggers(cls, payload):
        return _populate_safe_next_catalysts(payload)


def _normalize_recommendation_field(payload, default_label: str):
    recommendation = safe_mapping_dict(payload)
    if recommendation is None:
        return payload
    normalized = {**recommendation}
    for raw_key, raw_value in recommendation.items():
        if not isinstance(raw_key, str):
            continue
        key_text = safe_text(raw_key).strip()
        key = _RECOMMENDATION_KEY_ALIASES.get(key_text, key_text)
        if key == "建議":
            label_text = _safe_string_text(raw_value)
            normalized[key] = (
                normalize_recommendation_label(label_text)
                if label_text
                else default_label
            )
        elif key in _RECOMMENDATION_TEXT_DEFAULTS:
            normalized[key] = _safe_string_text(raw_value, _RECOMMENDATION_TEXT_DEFAULTS[key])
    label_text = _safe_string_text(normalized.get("建議"))
    normalized["建議"] = (
        normalize_recommendation_label(label_text)
        if label_text
        else default_label
    )
    if not normalized["建議"] or normalized["建議"] == "N/A":
        normalized["建議"] = default_label
    for key, default in _RECOMMENDATION_TEXT_DEFAULTS.items():
        normalized[key] = _safe_string_text(normalized.get(key), default)
    return normalized
