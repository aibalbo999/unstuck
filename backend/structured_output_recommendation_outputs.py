"""Recommendation structured output schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from mapping_fields import safe_mapping_dict
from trade_price_inputs import optional_execution_text
from structured_output_model_base import _safe_string_text, StructuredModel
from structured_output_position_sizing import PositionSizingEvidence
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
    planning_context: Literal["research", "actual", "unassessed"] = Field(default="unassessed", description="比例基於明確研究情境或真實輸入；未知為 unassessed，不能推定使用者持倉。")
    sizing_evidence: PositionSizingEvidence | None = Field(default=None, description="僅引用系統提供的資金、風險預算與持倉來源，保存 deterministic sizing 計算收據；不得自行設定預算。")

    @model_validator(mode="before")
    @classmethod
    def sanitize_fields(cls, payload):
        plan = safe_mapping_dict(payload) or {}
        action = _safe_string_text(plan.get("action"))
        action = action if action in {"進場", "續抱", "減碼", "等待"} else "資料不足"
        normalized = {
            **plan,
            "action": action,
            "entry_zone": _safe_string_text(plan.get("entry_zone"), "資料不足，等待可驗證進場條件"),
            "position_size": _safe_string_text(plan.get("position_size"), "資料不足"),
            "stop_loss": _safe_string_text(plan.get("stop_loss"), "資料不足，暫不建立部位"),
            "risk_reward": _safe_string_text(plan.get("risk_reward"), "資料不足"),
            "invalidation_condition": _safe_string_text(plan.get("invalidation_condition"), "資料不足"),
            "target_price": optional_execution_text(plan.get("target_price")),
            "transaction_cost": optional_execution_text(plan.get("transaction_cost")),
            "horizon_trading_days": plan.get("horizon_trading_days"),
        }
        if action == "等待":
            normalized.update({
                "entry_zone": "N/A",
                "position_size": "0%",
                "stop_loss": "N/A",
                "risk_reward": "N/A",
                "target_price": None,
                "transaction_cost": None,
            })
        return normalized


class ShortSetup(StructuredModel):
    entry_trigger: str = Field(..., min_length=1, description="SHORT 研究情境的進場條件與有本次來源依據的正數價格或單一明確價格區間；通用檢查名稱為 entry_zone，純事件或均線名稱不足以驗證價格。避免且確實不新增部位時，明示『本研究情境不建立空方部位』並列等待重新評估的條件；不可加入數字價位、條件開倉或已持倉主張。缺少來源不得補造價格，不是實際交易指令。")
    downside_target: str = Field(..., min_length=1, description="SHORT 研究情境中有本次來源依據的下行目標價格或單一明確價格區間；通用檢查名稱為 target_price，完整目標區間須低於完整進場區間。非放空分類依既有觀望契約；缺少來源不得補造價格。")
    cover_stop: str = Field(..., min_length=1, description="SHORT 研究情境中有本次來源依據的回補停損價格或單一明確價格區間；通用檢查名稱為 stop_loss，完整停損區間須高於完整進場區間，純事件條件不能代替價格。避免且確實不新增部位時，明示『本研究情境不建立空方部位，回補停損不適用』；此為研究政策，不代表使用者實際持倉為零。缺漏仍須揭露，不得補造無持倉聲明或價格，不是實際交易指令。")
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


class MarketSourceAssessment(StructuredModel):
    impact: Literal["affects_conclusion", "no_material_impact", "not_assessed"]
    reason: str = Field(..., min_length=1, description="對此次投資結論的具體影響理由或未評估限制。")
    source_refs: list[str] = Field(..., description="僅引用此次完整 market-source 區塊的系統 source_ref，禁止自行提供網址。")


class MarketContextAssessment(StructuredModel):
    global_market_context: MarketSourceAssessment | None = None
    international_news_context: MarketSourceAssessment | None = None


class RecommendationStructuredOutput(NextCatalystsMixin):
    market_context_assessment: MarketContextAssessment | None = None
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
    market_context_assessment: MarketContextAssessment | None = None
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
