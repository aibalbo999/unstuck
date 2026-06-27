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


class DcfScenarioOutput(StructuredModel):
    scenario: Literal["bear", "base", "bull"]
    revenue_growth_bias_pct: float
    margin_bias_pct: float
    wacc_pct: float = Field(..., gt=0)
    intrinsic_value: float = Field(..., ge=0)


class PriceTargetStructuredOutput(StructuredModel):
    price_targets: PriceTargets
    valuation_summary: ValuationSummary
    dcf_scenarios: list[DcfScenarioOutput] = Field(default_factory=list, max_length=3)
    analysis_markdown: str = Field(..., min_length=1)


class ConfidenceBasis(StructuredModel):
    """信心依據：要求 AI 明確說明信心分數來自哪些具體佐證。"""
    evidence_items: list[str] = Field(
        ...,
        min_length=3,
        description=(
            "支持此信心分數的具體佐證，至少 3 項。每項需引用具體數據或事件，"
            "不可僅寫「因為AI趨勢」等泛泛措辭。例如："
            "['TTM 毛利率 52.3% 優於同業均值 38%（來源：財務JSON）',"
            " '近三年 FCF/淨利轉換率均超過 90%（來源：deterministic_tool_results）',"
            " '2024Q4 法說會法人共識上修目標價']。"
        ),
    )
    key_risks_acknowledged: list[str] = Field(
        ...,
        min_length=2,
        description="已納入信心評估的關鍵風險，至少 2 項。必須是具體風險，非通用語句。",
    )
    data_gaps: list[str] = Field(
        default_factory=list,
        description="已知資料缺口。若無缺口，可填空列表，但不可省略此欄位。",
    )


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


class BubbleSniperRecommendationFields(StructuredModel):
    recommendation: Literal["強烈放空", "避免", "持有", "買進"] = Field(..., alias="建議")
    target_3m: str = Field(..., min_length=1, alias="短期目標（3個月）")
    target_6m: str = Field(..., min_length=1, alias="中期目標（6個月）")
    target_12m: str = Field(..., min_length=1, alias="長期目標（12個月）")
    long_term_potential_5y: str = Field(..., min_length=1, alias="長期潛力（5年）")
    confidence: str = Field(..., min_length=1, alias="信心指數")


class BubbleSniperStructuredOutput(StructuredModel):
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
    analysis_markdown: str = Field(..., min_length=1)


class ManagementHighlight(StructuredModel):
    keyword: str = Field(..., min_length=1)
    quote: str = Field(..., min_length=1)


class ManagementSentimentStructuredOutput(StructuredModel):
    guidance_tone: Literal["樂觀", "中立", "保守", "資料不足"]
    confidence: float = Field(..., ge=0, le=1)
    highlights: list[ManagementHighlight] = Field(..., min_length=3, max_length=3)
    analysis_markdown: str = Field(..., min_length=1)


class DownsideRisk(StructuredModel):
    title: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    impact: str = ""
    severity: Literal["warning", "high", "critical"]
    confidence: float = Field(default=0.7, ge=0, le=1)


class BearAdvocateStructuredOutput(StructuredModel):
    thesis_summary: str = Field(..., min_length=1)
    downside_risks: list[DownsideRisk] = Field(..., min_length=3, max_length=5)
    analysis_markdown: str = Field(..., min_length=1)


class SwingTradeSetup(StructuredModel):
    """Strict 1-2 week trade plan emitted by the v4 decision agent."""

    model_config = ConfigDict(populate_by_name=True)

    trade_direction: Literal["Long", "Short", "Neutral"]
    entry_zone: str = Field(..., min_length=1)
    target_price: str = Field(..., min_length=1)
    stop_loss: str = Field(..., min_length=1)
    core_catalyst: str = Field(..., min_length=1)
    risk_level: Literal["High", "Medium", "Low"]


STRUCTURED_AGENT_RESPONSE_SCHEMAS: dict[int, type[StructuredModel]] = {
    3: MoatStructuredOutput,
    4: PriceTargetStructuredOutput,
    7: RecommendationStructuredOutput,
    12: MoatStructuredOutput,
    14: PriceTargetStructuredOutput,
    16: RecommendationStructuredOutput,
    19: BubbleSniperStructuredOutput,
    20: ManagementSentimentStructuredOutput,
    21: BearAdvocateStructuredOutput,
    24: SwingTradeSetup,
}


def get_structured_response_schema(agent_num: int) -> Optional[type[StructuredModel]]:
    """Return the native response schema model for structured agents."""
    return STRUCTURED_AGENT_RESPONSE_SCHEMAS.get(agent_num)


def build_structured_output_instruction(agent_num: int) -> str:
    """Return JSON-only output instructions for agents with machine-read fields."""
    return STRUCTURED_AGENT_INSTRUCTIONS.get(agent_num, "")


def _extract_json_payload(raw_text: str) -> Optional[dict]:
    return extract_json_payload(raw_text)
