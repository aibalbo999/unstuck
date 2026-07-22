"""Recommendation structured output schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from mapping_fields import safe_mapping_dict
from structured_output_model_base import StructuredModel
from structured_output_recommendation_mixins import NextCatalystsMixin, ReasoningStepsMixin, _normalize_recommendation_field, _populate_safe_next_catalysts
from structured_output_recommendation_types import (
    _confidence_basis_fallback,
    _recommendation_field_fallback,
    _recommendation_root_fallback,
    _scenario_triggers_fallback,
    Catalyst,
    ConfidenceBasis,
    ScenarioTrigger,
)


class RecommendationFields(StructuredModel):
    recommendation: Literal["買入", "持有", "避免", "放空"] = Field(..., alias="建議")
    target_3m: str = Field(..., min_length=1, alias="短期目標（3個月）")
    target_6m: str = Field(..., min_length=1, alias="中期目標（6個月）")
    target_12m: str = Field(..., min_length=1, alias="長期目標（12個月）")
    long_term_potential_5y: str = Field(..., min_length=1, alias="長期潛力（5年）")
    confidence: str = Field(..., min_length=1, alias="信心指數")

    @model_validator(mode="before")
    @classmethod
    def normalize_label(cls, payload):
        if safe_mapping_dict(payload) is None:
            return {
                "建議": "持有",
                "短期目標（3個月）": "N/A",
                "中期目標（6個月）": "N/A",
                "長期目標（12個月）": "N/A",
                "長期潛力（5年）": "N/A",
                "信心指數": "N/A",
            }
        return _normalize_recommendation_field(payload, "持有")


class RecommendationStructuredOutput(NextCatalystsMixin):
    reasoning_steps: list[str] = Field(
        ...,
        min_length=3,
        description="先列出 3-6 個決策推論步驟，逐步連結估值、財務、護城河、成長、風險與籌碼。",
    )
    recommendation: RecommendationFields
    confidence_basis: ConfidenceBasis = Field(
        ...,
        description="信心依據：必須列出至少 3 項具體佐證與 2 項已納入考量的風險。",
    )
    scenario_triggers: list[ScenarioTrigger] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="情境觸發器：列出 2-5 個需要重新評估投資結論的具體條件。",
    )
    analysis_markdown: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_root_payload(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return _recommendation_root_fallback()
        if "recommendation" not in root:
            root = {**root, "recommendation": _recommendation_field_fallback("持有")}
        if "confidence_basis" not in root:
            root = {**root, "confidence_basis": _confidence_basis_fallback()}
        if "scenario_triggers" not in root:
            root = {**root, "scenario_triggers": _scenario_triggers_fallback()}
        return root


class BubbleSniperRecommendationFields(StructuredModel):
    recommendation: Literal["買入", "持有", "避免", "放空"] = Field(..., alias="建議")
    target_3m: str = Field(..., min_length=1, alias="短期目標（3個月）")
    target_6m: str = Field(..., min_length=1, alias="中期目標（6個月）")
    target_12m: str = Field(..., min_length=1, alias="長期目標（12個月）")
    long_term_potential_5y: str = Field(..., min_length=1, alias="長期潛力（5年）")
    confidence: str = Field(..., min_length=1, alias="信心指數")

    @model_validator(mode="before")
    @classmethod
    def normalize_label(cls, payload):
        if safe_mapping_dict(payload) is None:
            return {
                "建議": "避免",
                "短期目標（3個月）": "N/A",
                "中期目標（6個月）": "N/A",
                "長期目標（12個月）": "N/A",
                "長期潛力（5年）": "N/A",
                "信心指數": "N/A",
            }
        return _normalize_recommendation_field(payload, "避免")


class BubbleSniperStructuredOutput(ReasoningStepsMixin):
    reasoning_steps: list[str] = Field(
        ...,
        min_length=3,
        description="先列出 3-6 個逆勢交易推論步驟，逐步連結市場泡沫、財務漏洞、籌碼派發、崩盤催化與停損風控。",
    )
    recommendation: BubbleSniperRecommendationFields
    confidence_basis: ConfidenceBasis = Field(
        ...,
        description="信心依據：必須列出至少 3 項具體佐證與 2 項已納入考量的軋空或資料風險。",
    )
    scenario_triggers: list[ScenarioTrigger] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="情境觸發器：列出 2-5 個崩盤催化、軋空停損或重新評估條件。",
    )
    next_catalysts: list[Catalyst] = Field(default_factory=list, min_length=1)
    analysis_markdown: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def populate_next_catalysts_from_scenario_triggers(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return _recommendation_root_fallback("避免")
        if "scenario_triggers" not in root:
            root = {**root, "scenario_triggers": _scenario_triggers_fallback()}
        normalized = _populate_safe_next_catalysts(root)
        normalized_root = safe_mapping_dict(normalized)
        if normalized_root is None:
            return normalized
        if "recommendation" not in normalized_root:
            normalized_root = {**normalized_root, "recommendation": _recommendation_field_fallback("避免")}
        if "confidence_basis" not in normalized_root:
            normalized_root = {**normalized_root, "confidence_basis": _confidence_basis_fallback()}
        return normalized_root
