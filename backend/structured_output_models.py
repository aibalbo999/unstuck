"""Pydantic schemas and prompt instructions for structured agents."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from json_utils import extract_json_payload
from prompt_rules import build_structured_agent_instructions


STRUCTURED_AGENT_INSTRUCTIONS = build_structured_agent_instructions()


class StructuredModel(BaseModel):
    """Base model for native Google GenAI response_schema payloads."""

    model_config = ConfigDict(populate_by_name=True)


class MoatScores(StructuredModel):
    brand_influence: float = Field(..., ge=1, le=10, alias="品牌影響力")
    network_effect: float = Field(..., ge=1, le=10, alias="網路效應")
    switching_cost: float = Field(..., ge=1, le=10, alias="轉換成本")
    cost_advantage: float = Field(..., ge=1, le=10, alias="成本優勢")
    patent_technology: float = Field(..., ge=1, le=10, alias="專利技術")
    overall_moat: float = Field(..., ge=1, le=10, alias="整體護城河")


class MoatStructuredOutput(StructuredModel):
    reasoning_steps: list[str] = Field(
        ...,
        min_length=3,
        description="先列出 3-6 個可稽核推論步驟，逐步連結證據、反證與評分邏輯。",
    )
    moat_scores: MoatScores
    analysis_markdown: str = Field(..., min_length=1)


class PriceTargets(StructuredModel):
    dcf_reasoning: str = Field(..., min_length=1, description="DCF 假設、normalized FCF、WACC 與終值推論摘要。")
    peer_reasoning: str = Field(..., min_length=1, description="同業本益比、P/B 或 EV/EBITDA 比較推論摘要。")
    scenario_reasoning: str = Field(..., min_length=1, description="熊市、基本與牛市情境差異及風險折讓推論摘要。")
    bear_case: float = Field(..., ge=0, alias="熊市情境")
    base_case: float = Field(..., ge=0, alias="基本情境")
    bull_case: float = Field(..., ge=0, alias="牛市情境")


class ValuationSummary(StructuredModel):
    primary_method: Literal["normalized_dcf", "relative_valuation", "blended"]
    uses_market_value_wacc: bool
    uses_normalized_fcf: bool
    double_counting_check: str = Field(..., min_length=1)


class PriceTargetStructuredOutput(StructuredModel):
    price_targets: PriceTargets
    valuation_summary: ValuationSummary
    analysis_markdown: str = Field(..., min_length=1)


class RecommendationFields(StructuredModel):
    recommendation: Literal["買入", "持有", "避免"] = Field(..., alias="建議")
    target_3m: str = Field(..., min_length=1, alias="短期目標（3個月）")
    target_6m: str = Field(..., min_length=1, alias="中期目標（6個月）")
    target_12m: str = Field(..., min_length=1, alias="長期目標（12個月）")
    long_term_potential_5y: str = Field(..., min_length=1, alias="長期潛力（5年）")
    confidence: str = Field(..., min_length=1, alias="信心指數")


class RecommendationStructuredOutput(StructuredModel):
    reasoning_steps: list[str] = Field(
        ...,
        min_length=3,
        description="先列出 3-6 個決策推論步驟，逐步連結估值、財務、護城河、成長、風險與籌碼。",
    )
    recommendation: RecommendationFields
    analysis_markdown: str = Field(..., min_length=1)


STRUCTURED_AGENT_RESPONSE_SCHEMAS: dict[int, type[StructuredModel]] = {
    3: MoatStructuredOutput,
    4: PriceTargetStructuredOutput,
    7: RecommendationStructuredOutput,
    12: MoatStructuredOutput,
    14: PriceTargetStructuredOutput,
    16: RecommendationStructuredOutput,
}


def get_structured_response_schema(agent_num: int) -> Optional[type[StructuredModel]]:
    """Return the native response schema model for structured agents."""
    return STRUCTURED_AGENT_RESPONSE_SCHEMAS.get(agent_num)


def build_structured_output_instruction(agent_num: int) -> str:
    """Return JSON-only output instructions for agents with machine-read fields."""
    return STRUCTURED_AGENT_INSTRUCTIONS.get(agent_num, "")


def _extract_json_payload(raw_text: str) -> Optional[dict]:
    return extract_json_payload(raw_text)
