"""Shared recommendation structured output model primitives."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from mapping_fields import safe_mapping_dict, safe_sequence_items
from structured_output_confidence_basis import ConfidenceBasis
from structured_output_model_base import (
    _ANALYSIS_MARKDOWN_FALLBACK,
    _safe_mapping_has_key,
    _safe_mapping_value,
    _safe_string_text as _base_safe_string_text,
    AnalysisMarkdownMixin,
    StructuredModel,
)


def _safe_string_text(value: Any, default: str = "") -> str:
    if not isinstance(value, str):
        return default
    return _base_safe_string_text(value, default)


class ScenarioTrigger(StructuredModel):
    """情境觸發器：定義需重新評估投資結論的具體條件。"""
    trigger_condition: str = Field(
        ...,
        min_length=10,
        description="需要重新評估的具體觸發條件，例如：「季度毛利率低於 43%」或「競爭對手取得關鍵大客戶訂單」。",
    )
    action: str = Field(
        ...,
        min_length=5,
        description="觸發後建議的行動，例如：「下調至持有，重新評估目標價」。",
    )
    direction: Literal["bullish_upgrade", "bearish_downgrade", "neutral_review"] = Field(
        ...,
        description="觸發後對結論的影響方向。",
    )

    @model_validator(mode="before")
    @classmethod
    def sanitize_text_fields(cls, payload):
        trigger = safe_mapping_dict(payload)
        if trigger is None:
            return dict(_SCENARIO_TRIGGER_FALLBACK)
        condition = _safe_string_text(_safe_mapping_value(trigger, "trigger_condition"))
        action = _safe_string_text(_safe_mapping_value(trigger, "action"))
        direction = _safe_string_text(_safe_mapping_value(trigger, "direction"))
        return {
            **trigger,
            "trigger_condition": (
                condition if len(condition) >= 10 else _SCENARIO_TRIGGER_FALLBACK["trigger_condition"]
            ),
            "action": action if len(action) >= 5 else _SCENARIO_TRIGGER_FALLBACK["action"],
            "direction": direction if direction in _SCENARIO_TRIGGER_DIRECTIONS else "neutral_review",
        }


class Catalyst(StructuredModel):
    event_name: str = Field(..., min_length=1)
    expected_timeframe: str = Field(..., min_length=1, description="例如 Q3 2026、下個月法說會或下一次月營收。")
    impact_direction: Literal["bullish", "bearish", "volatile"]
    trigger_condition: str = Field(..., min_length=5)

    @model_validator(mode="before")
    @classmethod
    def sanitize_text_fields(cls, payload):
        catalyst = safe_mapping_dict(payload)
        if catalyst is None:
            return {
                "event_name": "待確認催化事件",
                "expected_timeframe": "待後續資料確認",
                "impact_direction": "volatile",
                "trigger_condition": "待後續資料確認",
            }
        impact_direction = _safe_string_text(_safe_mapping_value(catalyst, "impact_direction"))
        trigger_condition = _safe_string_text(_safe_mapping_value(catalyst, "trigger_condition"))
        return {
            **catalyst,
            "event_name": _safe_string_text(_safe_mapping_value(catalyst, "event_name"), "待確認催化事件"),
            "expected_timeframe": _safe_string_text(
                _safe_mapping_value(catalyst, "expected_timeframe"),
                "待後續資料確認",
            ),
            "impact_direction": (
                impact_direction if impact_direction in _NEXT_CATALYST_IMPACT_DIRECTIONS else "volatile"
            ),
            "trigger_condition": trigger_condition if len(trigger_condition) >= 5 else "待後續資料確認",
        }


class ExecutiveThesisOutput(StructuredModel):
    core_thesis: str = Field(..., min_length=1)
    bull_case_summary: str = Field(..., min_length=1)
    bear_case_summary: str = Field(..., min_length=1)
    resolved_contradictions: list[str] = Field(default_factory=list)
    smoothed_markdown: str = Field(default="", description="總編輯潤飾後的統一敘事 Markdown。")

    @model_validator(mode="before")
    @classmethod
    def sanitize_root_payload(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return {
                "core_thesis": "資料不足",
                "bull_case_summary": "資料不足",
                "bear_case_summary": "資料不足",
                "resolved_contradictions": [],
                "smoothed_markdown": _ANALYSIS_MARKDOWN_FALLBACK,
            }
        return {
            **root,
            "core_thesis": _safe_string_text(root.get("core_thesis"), "資料不足"),
            "bull_case_summary": _safe_string_text(root.get("bull_case_summary"), "資料不足"),
            "bear_case_summary": _safe_string_text(root.get("bear_case_summary"), "資料不足"),
            "resolved_contradictions": [
                _safe_string_text(item, "資料不足")
                for item in safe_sequence_items(root.get("resolved_contradictions"))
            ],
            "smoothed_markdown": _safe_string_text(root.get("smoothed_markdown"), _ANALYSIS_MARKDOWN_FALLBACK),
        }

    @field_validator("core_thesis")
    @classmethod
    def core_thesis_max_300_words(cls, value: str) -> str:
        if len(str(value).split()) > 300:
            raise ValueError("core_thesis must be 300 words or fewer")
        return value


_SCENARIO_TRIGGER_DIRECTIONS = {"bullish_upgrade", "bearish_downgrade", "neutral_review"}
_NEXT_CATALYST_IMPACT_DIRECTIONS = {"bullish", "bearish", "volatile"}
_MAX_SCENARIO_TRIGGERS = 5
_MIN_SCENARIO_TRIGGERS = 2
_SCENARIO_TRIGGER_FALLBACK = {
    "trigger_condition": "待後續資料確認觸發條件",
    "action": "重新檢查投資結論",
    "direction": "neutral_review",
}
_RECOMMENDATION_KEY_ALIASES = {
    "recommendation": "建議",
    "target_3m": "短期目標（3個月）",
    "target_6m": "中期目標（6個月）",
    "target_12m": "長期目標（12個月）",
    "long_term_potential_5y": "長期潛力（5年）",
    "confidence": "信心指數",
}
_RECOMMENDATION_TEXT_DEFAULTS = {
    "短期目標（3個月）": "N/A",
    "中期目標（6個月）": "N/A",
    "長期目標（12個月）": "N/A",
    "長期潛力（5年）": "N/A",
    "信心指數": "N/A",
}


def _recommendation_field_fallback(recommendation_label: str) -> dict:
    return {
        "建議": recommendation_label,
        "短期目標（3個月）": "N/A",
        "中期目標（6個月）": "N/A",
        "長期目標（12個月）": "N/A",
        "長期潛力（5年）": "N/A",
        "信心指數": "N/A",
    }


def _confidence_basis_fallback() -> dict:
    return {
        "evidence_items": ["待補具體佐證", "待補具體佐證", "待補具體佐證"],
        "key_risks_acknowledged": ["待補已納入風險", "待補已納入風險"],
        "data_gaps": [],
    }


def _scenario_triggers_fallback() -> list[dict]:
    return [dict(_SCENARIO_TRIGGER_FALLBACK), dict(_SCENARIO_TRIGGER_FALLBACK)]


def _recommendation_root_fallback(recommendation_label: str = "持有") -> dict:
    return {
        "reasoning_steps": ["待補推論步驟", "待補推論步驟", "待補推論步驟"],
        "recommendation": _recommendation_field_fallback(recommendation_label),
        "confidence_basis": _confidence_basis_fallback(),
        "scenario_triggers": _scenario_triggers_fallback(),
        "next_catalysts": [
            {
                "event_name": "Scenario trigger 1",
                "expected_timeframe": "待後續資料確認",
                "impact_direction": "volatile",
                "trigger_condition": _SCENARIO_TRIGGER_FALLBACK["trigger_condition"],
            }
        ],
        "analysis_markdown": _ANALYSIS_MARKDOWN_FALLBACK,
    }
