"""Recommendation structured output schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from mapping_fields import safe_mapping_dict
from trade_price_inputs import optional_execution_text
from structured_output_model_base import _safe_string_text, StructuredModel
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


class PositionPlan(StructuredModel):
    action: Literal["進場", "續抱", "減碼", "等待"]
    entry_zone: str = Field(..., min_length=1)
    position_size: str = Field(..., min_length=1)
    stop_loss: str = Field(..., min_length=1)
    risk_reward: str = Field(..., min_length=1)
    invalidation_condition: str = Field(..., min_length=1)
    target_price: str | None = Field(default=None, description="與部位計畫同一交易期間的可驗證目標價；未知保留 null，不套用其他期間的投資目標。")
    transaction_cost: str | None = Field(default=None, description="每股來回交易成本的金額，含手續費、稅及滑價；未知保留 null，明確免費才填 0，不填百分比。")
    horizon_trading_days: int | None = Field(default=None, strict=True, ge=1, le=252, description="部位計畫與目標價共同適用的交易日數，僅能明確指定 1 到 252 的整數；無法確定為 null。")

    @model_validator(mode="before")
    @classmethod
    def sanitize_fields(cls, payload):
        plan = safe_mapping_dict(payload) or {}
        action = _safe_string_text(plan.get("action"))
        return {
            **plan,
            "action": action if action in {"進場", "續抱", "減碼", "等待"} else "資料不足",
            "entry_zone": _safe_string_text(plan.get("entry_zone"), "資料不足，等待可驗證進場條件"),
            "position_size": _safe_string_text(plan.get("position_size"), "資料不足"),
            "stop_loss": _safe_string_text(plan.get("stop_loss"), "資料不足，暫不建立部位"),
            "risk_reward": _safe_string_text(plan.get("risk_reward"), "資料不足"),
            "invalidation_condition": _safe_string_text(plan.get("invalidation_condition"), "資料不足"),
            "target_price": optional_execution_text(plan.get("target_price")),
            "transaction_cost": optional_execution_text(plan.get("transaction_cost")),
            "horizon_trading_days": plan.get("horizon_trading_days"),
        }


class ShortSetup(StructuredModel):
    entry_trigger: str = Field(..., min_length=1)
    downside_target: str = Field(..., min_length=1)
    cover_stop: str = Field(..., min_length=1)
    squeeze_risk: str = Field(..., min_length=1)
    thesis_invalidation: str = Field(..., min_length=1)
    transaction_cost: str | None = Field(default=None, description="每股來回空單交易成本金額，含借券、費稅及滑價；未知為 null，明確免費才為 0。")
    horizon_trading_days: int | None = Field(default=None, strict=True, ge=1, le=252, description="空方交易計畫與目標價共同適用的交易日數，僅能明確指定 1 到 252 的整數；無法確定為 null。")

    @model_validator(mode="before")
    @classmethod
    def sanitize_fields(cls, payload):
        setup = safe_mapping_dict(payload) or {}
        return {
            **setup,
            "entry_trigger": _safe_string_text(setup.get("entry_trigger"), "資料不足，等待可驗證做空觸發"),
            "downside_target": _safe_string_text(setup.get("downside_target"), "資料不足"),
            "cover_stop": _safe_string_text(setup.get("cover_stop"), "資料不足，暫不建立空方部位"),
            "squeeze_risk": _safe_string_text(setup.get("squeeze_risk"), "資料不足"),
            "thesis_invalidation": _safe_string_text(setup.get("thesis_invalidation"), "資料不足"),
            "transaction_cost": optional_execution_text(setup.get("transaction_cost")),
            "horizon_trading_days": setup.get("horizon_trading_days"),
        }


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


class TradingDecisionStructuredOutput(RecommendationStructuredOutput):
    position_plan: PositionPlan

    @model_validator(mode="before")
    @classmethod
    def populate_position_plan(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            root = _recommendation_root_fallback()
        if "position_plan" not in root:
            root = {**root, "position_plan": {}}
        return root


class PositionPlanCompatibility(PositionPlan):
    action: Literal["進場", "續抱", "減碼", "等待", "資料不足"]


class TradingDecisionCompatibilityOutput(TradingDecisionStructuredOutput):
    position_plan: PositionPlanCompatibility


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
    short_setup: ShortSetup
    analysis_markdown: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def populate_next_catalysts_from_scenario_triggers(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return {**_recommendation_root_fallback("避免"), "short_setup": {}}
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
        if "short_setup" not in normalized_root:
            normalized_root = {**normalized_root, "short_setup": {}}
        return normalized_root
