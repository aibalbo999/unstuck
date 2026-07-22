import sys
from types import MappingProxyType
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from structured_output_models import (  # noqa: E402
    BearAdvocateStructuredOutput,
    BubbleSniperRecommendationFields,
    BubbleSniperStructuredOutput,
    Catalyst,
    ConfidenceBasis,
    DcfScenarioOutput,
    DownsideRisk,
    ExecutiveThesisOutput,
    ManagementHighlight,
    ManagementSentimentStructuredOutput,
    MoatScores,
    MoatStructuredOutput,
    PriceTargets,
    PriceTargetStructuredOutput,
    RecommendationFields,
    RecommendationStructuredOutput,
    ScenarioTrigger,
    SwingTradeSetup,
    ValuationSummary,
)


_DEFAULT = object()


def _recommendation_payload(next_catalysts=_DEFAULT):
    if next_catalysts is _DEFAULT:
        next_catalysts = [
            {
                "event_name": "Q3 法說會",
                "expected_timeframe": "Q3 2026",
                "impact_direction": "bullish",
                "trigger_condition": "若管理層調升毛利率指引，重新評估上行情境。",
            }
        ]

    return {
        "reasoning_steps": ["估值支持中性", "風險限制上行", "催化劑決定再評估"],
        "recommendation": {
            "建議": "持有",
            "短期目標（3個月）": "NT$300",
            "中期目標（6個月）": "NT$330",
            "長期目標（12個月）": "NT$350",
            "長期潛力（5年）": "NT$420",
            "信心指數": "7/10",
        },
        "confidence_basis": {
            "evidence_items": ["估值接近基本情境", "FCF 維持正值", "同業估值未明顯折價"],
            "key_risks_acknowledged": ["毛利率下滑", "需求能見度不足"],
            "data_gaps": [],
        },
        "scenario_triggers": [
            {"trigger_condition": "季度毛利率低於 43% 且管理層未提出改善計畫", "action": "重新評估風險情境", "direction": "bearish_downgrade"},
            {"trigger_condition": "法說會正式調升全年營收與毛利率展望", "action": "重新評估上行情境", "direction": "bullish_upgrade"},
        ],
        "next_catalysts": next_catalysts,
        "analysis_markdown": "正式報告正文",
    }


def _readonly(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _readonly(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_readonly(child) for child in value)
    return value


class MalformedStructuredText:
    def __str__(self):
        raise RuntimeError("structured text unavailable")


class MalformedStructuredNumber:
    def __float__(self):
        raise RuntimeError("structured number unavailable")


class FloatingStructuredNumber:
    def __float__(self):
        return 999.0


class StringifyingStructuredText:
    def __str__(self):
        return "bad-body-literal"


class StringifyingBearishDirection:
    def __str__(self):
        return "bearish_downgrade"


class StringifyingBearScenario:
    def __str__(self):
        return "bear"


class StringifyingTrueValue:
    def __str__(self):
        return "true"


class StringifyingNumberValue:
    def __str__(self):
        return "999"


class StringifyingRecommendationKey:
    def __str__(self):
        return "建議"


class StringifyingRecommendationTargetKey:
    def __str__(self):
        return "短期目標（3個月）"


class StringifyingBuyLabel:
    def __str__(self):
        return "買入"


class EqualToBaseCaseKey:
    def __hash__(self):
        return hash("基本情境")

    def __eq__(self, other):
        return other == "基本情境"


class EqualToDcfReasoningKey:
    def __hash__(self):
        return hash("dcf_reasoning")

    def __eq__(self, other):
        return other == "dcf_reasoning"


class EqualToOverallMoatKey:
    def __hash__(self):
        return hash("整體護城河")

    def __eq__(self, other):
        return other == "整體護城河"


class EqualToPrimaryMethodKey:
    def __hash__(self):
        return hash("primary_method")

    def __eq__(self, other):
        return other == "primary_method"


class EqualToMarketValueWaccKey:
    def __hash__(self):
        return hash("uses_market_value_wacc")

    def __eq__(self, other):
        return other == "uses_market_value_wacc"


class EqualToDoubleCountingCheckKey:
    def __hash__(self):
        return hash("double_counting_check")

    def __eq__(self, other):
        return other == "double_counting_check"


class EqualToDcfScenarioFieldKey:
    def __init__(self, field_name):
        self.field_name = field_name

    def __hash__(self):
        return hash(self.field_name)

    def __eq__(self, other):
        return other == self.field_name


class EqualToRecommendationTailFieldKey:
    def __init__(self, field_name):
        self.field_name = field_name

    def __hash__(self):
        return hash(self.field_name)

    def __eq__(self, other):
        return other == self.field_name


def test_scenario_trigger_uses_fallback_for_malformed_text_fields_before_validation():
    output = ScenarioTrigger.model_validate({
        "trigger_condition": MalformedStructuredText(),
        "action": MalformedStructuredText(),
        "direction": MalformedStructuredText(),
    })

    assert output.trigger_condition == "待後續資料確認觸發條件"
    assert output.action == "重新檢查投資結論"
    assert output.direction == "neutral_review"


def test_catalyst_uses_fallback_for_malformed_text_fields_before_validation():
    output = Catalyst.model_validate({
        "event_name": MalformedStructuredText(),
        "expected_timeframe": MalformedStructuredText(),
        "impact_direction": MalformedStructuredText(),
        "trigger_condition": MalformedStructuredText(),
    })

    assert output.event_name == "待確認催化事件"
    assert output.expected_timeframe == "待後續資料確認"
    assert output.impact_direction == "volatile"
    assert output.trigger_condition == "待後續資料確認"


def test_recommendation_tail_models_ignore_non_string_literals_before_validation():
    trigger = ScenarioTrigger.model_validate({
        "trigger_condition": StringifyingStructuredText(),
        "action": StringifyingStructuredText(),
        "direction": StringifyingStructuredText(),
    })
    catalyst = Catalyst.model_validate({
        "event_name": StringifyingStructuredText(),
        "expected_timeframe": StringifyingStructuredText(),
        "impact_direction": StringifyingStructuredText(),
        "trigger_condition": StringifyingStructuredText(),
    })

    assert trigger.trigger_condition == "待後續資料確認觸發條件"
    assert trigger.action == "重新檢查投資結論"
    assert trigger.direction == "neutral_review"
    assert catalyst.event_name == "待確認催化事件"
    assert catalyst.expected_timeframe == "待後續資料確認"
    assert catalyst.impact_direction == "volatile"
    assert catalyst.trigger_condition == "待後續資料確認"

    payload = _recommendation_payload(next_catalysts=[
        {
            "event_name": StringifyingStructuredText(),
            "expected_timeframe": StringifyingStructuredText(),
            "impact_direction": StringifyingStructuredText(),
            "trigger_condition": StringifyingStructuredText(),
        },
    ])
    payload["scenario_triggers"] = [
        {
            "trigger_condition": StringifyingStructuredText(),
            "action": StringifyingStructuredText(),
            "direction": StringifyingStructuredText(),
        },
        {
            "trigger_condition": "法說會正式調升全年營收與毛利率展望",
            "action": "重新評估上行情境",
            "direction": "bullish_upgrade",
        },
    ]

    recommendation = RecommendationStructuredOutput.model_validate(payload)

    assert [row.trigger_condition for row in recommendation.scenario_triggers] == [
        "法說會正式調升全年營收與毛利率展望",
        "待後續資料確認觸發條件",
    ]
    assert recommendation.next_catalysts[0].trigger_condition == "法說會正式調升全年營收與毛利率展望"
    assert "bad-body-literal" not in repr(recommendation)


def test_schema_recommendation_tail_fields_ignore_non_string_equal_keys_before_validation():
    trigger = ScenarioTrigger.model_validate({
        EqualToRecommendationTailFieldKey("trigger_condition"): "季度毛利率低於 43% 且管理層未提出改善計畫",
        EqualToRecommendationTailFieldKey("action"): "下調至持有並重估目標價",
        EqualToRecommendationTailFieldKey("direction"): "bearish_downgrade",
    })
    catalyst = Catalyst.model_validate({
        EqualToRecommendationTailFieldKey("event_name"): "Q4 法說會",
        EqualToRecommendationTailFieldKey("expected_timeframe"): "Q4 2026",
        EqualToRecommendationTailFieldKey("impact_direction"): "bullish",
        EqualToRecommendationTailFieldKey("trigger_condition"): "若管理層調升毛利率指引，重新評估上行情境。",
    })

    assert trigger.trigger_condition == "待後續資料確認觸發條件"
    assert trigger.action == "重新檢查投資結論"
    assert trigger.direction == "neutral_review"
    assert catalyst.event_name == "待確認催化事件"
    assert catalyst.expected_timeframe == "待後續資料確認"
    assert catalyst.impact_direction == "volatile"
    assert catalyst.trigger_condition == "待後續資料確認"

    payload = _recommendation_payload(next_catalysts=[
        {
            EqualToRecommendationTailFieldKey("event_name"): "Q4 法說會",
            EqualToRecommendationTailFieldKey("expected_timeframe"): "Q4 2026",
            EqualToRecommendationTailFieldKey("impact_direction"): "bullish",
            EqualToRecommendationTailFieldKey("trigger_condition"): "若管理層調升毛利率指引，重新評估上行情境。",
        },
        {
            "event_name": "月營收公布",
            "expected_timeframe": "下個月",
            "impact_direction": "volatile",
            "trigger_condition": "若營收連續兩個月回升，重新評估上行情境。",
        },
    ])
    payload["scenario_triggers"] = [
        {
            EqualToRecommendationTailFieldKey("trigger_condition"): "季度毛利率低於 43% 且管理層未提出改善計畫",
            EqualToRecommendationTailFieldKey("action"): "下調至持有並重估目標價",
            EqualToRecommendationTailFieldKey("direction"): "bearish_downgrade",
        },
        {
            "trigger_condition": "法說會正式調升全年營收與毛利率展望",
            "action": "上調至買入並重估上行情境",
            "direction": "bullish_upgrade",
        },
    ]

    recommendation = RecommendationStructuredOutput.model_validate(payload)

    assert [row.trigger_condition for row in recommendation.scenario_triggers] == [
        "法說會正式調升全年營收與毛利率展望",
        "待後續資料確認觸發條件",
    ]
    assert [row.event_name for row in recommendation.next_catalysts] == ["月營收公布"]


def test_executive_thesis_output_caps_core_thesis_to_300_words():
    output = ExecutiveThesisOutput(
        core_thesis=" ".join(["word"] * 300),
        bull_case_summary="毛利率回升與需求改善。",
        bear_case_summary="估值偏高且 FCF 轉換率惡化。",
        resolved_contradictions=["估值 Agent 偏多，但法證 Agent 的現金流警示降低信心。"],
    )

    assert output.core_thesis.startswith("word")

    with pytest.raises(ValidationError):
        ExecutiveThesisOutput(
            core_thesis=" ".join(["word"] * 301),
            bull_case_summary="bull",
            bear_case_summary="bear",
            resolved_contradictions=[],
        )


def test_executive_thesis_output_uses_fallback_for_malformed_root_before_validation():
    output = ExecutiveThesisOutput.model_validate(MalformedStructuredText())

    assert output.core_thesis == "資料不足"
    assert output.bull_case_summary == "資料不足"
    assert output.bear_case_summary == "資料不足"
    assert output.resolved_contradictions == []
    assert output.smoothed_markdown == "資料不足"


def test_executive_thesis_output_uses_fallback_for_malformed_text_fields_before_validation():
    output = ExecutiveThesisOutput.model_validate({
        "core_thesis": MalformedStructuredText(),
        "bull_case_summary": MalformedStructuredText(),
        "bear_case_summary": MalformedStructuredText(),
        "resolved_contradictions": [],
        "smoothed_markdown": MalformedStructuredText(),
    })

    assert output.core_thesis == "資料不足"
    assert output.bull_case_summary == "資料不足"
    assert output.bear_case_summary == "資料不足"
    assert output.resolved_contradictions == []
    assert output.smoothed_markdown == "資料不足"


def test_executive_thesis_output_ignores_non_string_literals_before_validation():
    output = ExecutiveThesisOutput.model_validate({
        "core_thesis": StringifyingStructuredText(),
        "bull_case_summary": StringifyingStructuredText(),
        "bear_case_summary": StringifyingStructuredText(),
        "resolved_contradictions": [
            "有效矛盾整理",
            StringifyingStructuredText(),
        ],
        "smoothed_markdown": StringifyingStructuredText(),
    })

    assert output.core_thesis == "資料不足"
    assert output.bull_case_summary == "資料不足"
    assert output.bear_case_summary == "資料不足"
    assert output.resolved_contradictions == ["有效矛盾整理", "資料不足"]
    assert output.smoothed_markdown == "資料不足"
    assert "bad-body-literal" not in repr(output)


def test_executive_thesis_output_uses_fallback_for_malformed_resolved_contradictions_before_validation():
    output = ExecutiveThesisOutput.model_validate({
        "core_thesis": "核心論點保留。",
        "bull_case_summary": "多方摘要保留。",
        "bear_case_summary": "空方摘要保留。",
        "resolved_contradictions": [
            "估值 Agent 偏多，但法證 Agent 的現金流警示降低信心。",
            MalformedStructuredText(),
        ],
        "smoothed_markdown": "總編輯摘要保留。",
    })

    assert output.resolved_contradictions == [
        "估值 Agent 偏多，但法證 Agent 的現金流警示降低信心。",
        "資料不足",
    ]


def test_moat_output_uses_fallback_for_malformed_analysis_markdown_before_validation():
    output = MoatStructuredOutput.model_validate({
        "reasoning_steps": ["品牌證據可量化", "技術優勢仍需折價", "整體分數需保留"],
        "moat_scores": {
            "品牌影響力": 8,
            "網路效應": 7,
            "轉換成本": 6,
            "成本優勢": 5,
            "專利技術": 4,
            "整體護城河": 6,
        },
        "analysis_markdown": MalformedStructuredText(),
    })

    assert output.analysis_markdown == "資料不足"


def test_structured_output_schema_analysis_markdown_ignores_non_string_literals_before_validation():
    moat = MoatStructuredOutput.model_validate({
        "reasoning_steps": ["品牌證據可量化", "技術優勢仍需折價", "整體分數需保留"],
        "moat_scores": {
            "品牌影響力": 8,
            "網路效應": 7,
            "轉換成本": 6,
            "成本優勢": 5,
            "專利技術": 4,
            "整體護城河": 6,
        },
        "analysis_markdown": StringifyingStructuredText(),
    })
    valuation = PriceTargetStructuredOutput.model_validate({
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": StringifyingStructuredText(),
    })
    recommendation_payload = _recommendation_payload()
    recommendation_payload["analysis_markdown"] = StringifyingStructuredText()
    recommendation = RecommendationStructuredOutput.model_validate(recommendation_payload)
    bubble_payload = _recommendation_payload()
    bubble_payload["analysis_markdown"] = StringifyingStructuredText()
    bubble = BubbleSniperStructuredOutput.model_validate(bubble_payload)
    management = ManagementSentimentStructuredOutput.model_validate({
        "guidance_tone": "中立",
        "confidence": 0.7,
        "highlights": [
            {"keyword": "需求回溫", "quote": "AI 訂單恢復成長"},
            {"keyword": "毛利率", "quote": "管理層維持全年展望"},
            {"keyword": "資本支出", "quote": "供應鏈投資保持紀律"},
        ],
        "analysis_markdown": StringifyingStructuredText(),
    })
    downside = BearAdvocateStructuredOutput.model_validate({
        "thesis_summary": "下行風險仍需折價。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值倍數下修",
                "severity": "high",
                "confidence": 0.8,
            },
            {
                "title": "現金流轉弱",
                "evidence": "營運資金需求上升使 FCF 轉換率下滑。",
                "impact": "DCF 折價",
                "severity": "warning",
                "confidence": 0.6,
            },
            {
                "title": "客戶集中",
                "evidence": "主要客戶拉貨節奏可能放大營收波動。",
                "impact": "營收能見度下降",
                "severity": "warning",
                "confidence": 0.5,
            },
        ],
        "analysis_markdown": StringifyingStructuredText(),
    })

    outputs = [moat, valuation, recommendation, bubble, management, downside]

    assert [output.analysis_markdown for output in outputs] == ["資料不足"] * len(outputs)
    assert "bad-body-literal" not in "".join(repr(output) for output in outputs)


def test_moat_output_uses_minimum_fallback_for_malformed_reasoning_steps_before_validation():
    output = MoatStructuredOutput.model_validate({
        "reasoning_steps": ["品牌證據可量化", MalformedStructuredText(), "整體分數需保留"],
        "moat_scores": {
            "品牌影響力": 8,
            "網路效應": 7,
            "轉換成本": 6,
            "成本優勢": 5,
            "專利技術": 4,
            "整體護城河": 6,
        },
        "analysis_markdown": "護城河正文",
    })

    assert output.reasoning_steps == ["品牌證據可量化", "整體分數需保留", "待補推論步驟"]


def test_moat_output_uses_list_fallback_for_malformed_reasoning_step_collection_before_validation():
    output = MoatStructuredOutput.model_validate({
        "reasoning_steps": MalformedStructuredText(),
        "moat_scores": {
            "品牌影響力": 8,
            "網路效應": 7,
            "轉換成本": 6,
            "成本優勢": 5,
            "專利技術": 4,
            "整體護城河": 6,
        },
        "analysis_markdown": "護城河正文",
    })

    assert output.reasoning_steps == ["待補推論步驟", "待補推論步驟", "待補推論步驟"]
    assert output.moat_scores.overall_moat == 6


def test_moat_output_uses_fallback_for_malformed_score_numbers_before_validation():
    output = MoatStructuredOutput.model_validate({
        "reasoning_steps": ["品牌證據可量化", "技術優勢仍需折價", "整體分數需保留"],
        "moat_scores": {
            "品牌影響力": 8,
            "網路效應": MalformedStructuredNumber(),
            "轉換成本": 6,
            "成本優勢": 5,
            "專利技術": 4,
            "整體護城河": 7,
        },
        "analysis_markdown": "護城河正文",
    })

    assert output.moat_scores.brand_influence == 8
    assert output.moat_scores.network_effect == 1
    assert output.moat_scores.overall_moat == 7


def test_moat_output_uses_fallback_for_malformed_score_container_before_validation():
    output = MoatStructuredOutput.model_validate({
        "reasoning_steps": ["品牌證據可量化", "技術優勢仍需折價", "整體分數需保留"],
        "moat_scores": MalformedStructuredText(),
        "analysis_markdown": "護城河正文",
    })

    assert output.moat_scores.brand_influence == 1
    assert output.moat_scores.network_effect == 1
    assert output.moat_scores.switching_cost == 1
    assert output.moat_scores.cost_advantage == 1
    assert output.moat_scores.patent_technology == 1
    assert output.moat_scores.overall_moat == 1


def test_schema_moat_score_aliases_ignore_non_string_equal_keys_before_validation():
    output = MoatScores.model_validate({
        "品牌影響力": 8,
        "網路效應": 7,
        "轉換成本": 6,
        "成本優勢": 5,
        "專利技術": 4,
        EqualToOverallMoatKey(): 9,
    })

    assert output.brand_influence == 8
    assert output.network_effect == 7
    assert output.switching_cost == 6
    assert output.cost_advantage == 5
    assert output.patent_technology == 4
    assert output.overall_moat == 1


def test_moat_output_uses_fallback_for_missing_score_container_before_validation():
    output = MoatStructuredOutput.model_validate({
        "reasoning_steps": ["品牌證據可量化", "技術優勢仍需折價", "整體分數需保留"],
        "analysis_markdown": "護城河正文",
    })

    assert output.moat_scores.brand_influence == 1
    assert output.moat_scores.network_effect == 1
    assert output.moat_scores.switching_cost == 1
    assert output.moat_scores.cost_advantage == 1
    assert output.moat_scores.patent_technology == 1
    assert output.moat_scores.overall_moat == 1
    assert output.reasoning_steps == ["品牌證據可量化", "技術優勢仍需折價", "整體分數需保留"]
    assert output.analysis_markdown == "護城河正文"


def test_moat_output_uses_fallback_for_malformed_root_before_validation():
    output = MoatStructuredOutput.model_validate(MalformedStructuredText())

    assert output.reasoning_steps == ["待補推論步驟", "待補推論步驟", "待補推論步驟"]
    assert output.moat_scores.brand_influence == 1
    assert output.moat_scores.network_effect == 1
    assert output.moat_scores.switching_cost == 1
    assert output.moat_scores.cost_advantage == 1
    assert output.moat_scores.patent_technology == 1
    assert output.moat_scores.overall_moat == 1
    assert output.analysis_markdown == "資料不足"


def test_price_target_output_uses_fallback_for_malformed_root_before_validation():
    output = PriceTargetStructuredOutput.model_validate(MalformedStructuredText())

    assert output.price_targets.dcf_reasoning == "資料不足"
    assert output.price_targets.peer_reasoning == "資料不足"
    assert output.price_targets.scenario_reasoning == "資料不足"
    assert output.price_targets.bear_case == 0
    assert output.price_targets.base_case == 0
    assert output.price_targets.bull_case == 0
    assert output.valuation_summary.primary_method == "blended"
    assert output.valuation_summary.uses_market_value_wacc is False
    assert output.valuation_summary.uses_normalized_fcf is False
    assert output.valuation_summary.double_counting_check == "資料不足"
    assert output.dcf_scenarios == []
    assert output.analysis_markdown == "資料不足"


def test_price_targets_uses_fallback_for_malformed_root_before_validation():
    output = PriceTargets.model_validate(MalformedStructuredText())

    assert output.dcf_reasoning == "資料不足"
    assert output.peer_reasoning == "資料不足"
    assert output.scenario_reasoning == "資料不足"
    assert output.bear_case == 0
    assert output.base_case == 0
    assert output.bull_case == 0


def test_schema_valuation_and_recommendation_text_fields_ignore_non_string_literals_before_validation():
    price_targets = PriceTargets.model_validate({
        "dcf_reasoning": StringifyingStructuredText(),
        "peer_reasoning": "同業比較完整",
        "scenario_reasoning": StringifyingStructuredText(),
        "熊市情境": 90,
        "基本情境": 120,
        "牛市情境": 150,
    })
    valuation_summary = ValuationSummary.model_validate({
        "primary_method": StringifyingStructuredText(),
        "uses_market_value_wacc": True,
        "uses_normalized_fcf": True,
        "double_counting_check": StringifyingStructuredText(),
    })
    recommendation = RecommendationFields.model_validate({
        "建議": "持有",
        "短期目標（3個月）": StringifyingStructuredText(),
        "中期目標（6個月）": "NT$330",
        "長期目標（12個月）": StringifyingStructuredText(),
        "長期潛力（5年）": StringifyingStructuredText(),
        "信心指數": StringifyingStructuredText(),
    })
    bubble = BubbleSniperRecommendationFields.model_validate({
        "建議": "避免",
        "短期目標（3個月）": StringifyingStructuredText(),
        "中期目標（6個月）": "NT$190",
        "長期目標（12個月）": StringifyingStructuredText(),
        "長期潛力（5年）": StringifyingStructuredText(),
        "信心指數": StringifyingStructuredText(),
    })

    assert price_targets.dcf_reasoning == "資料不足"
    assert price_targets.peer_reasoning == "同業比較完整"
    assert price_targets.scenario_reasoning == "資料不足"
    assert valuation_summary.primary_method == "blended"
    assert valuation_summary.double_counting_check == "資料不足"
    assert recommendation.target_3m == "N/A"
    assert recommendation.target_6m == "NT$330"
    assert recommendation.target_12m == "N/A"
    assert recommendation.long_term_potential_5y == "N/A"
    assert recommendation.confidence == "N/A"
    assert bubble.target_3m == "N/A"
    assert bubble.target_6m == "NT$190"
    assert bubble.target_12m == "N/A"
    assert bubble.long_term_potential_5y == "N/A"
    assert bubble.confidence == "N/A"
    assert "bad-body-literal" not in (
        repr(price_targets) + repr(valuation_summary) + repr(recommendation) + repr(bubble)
    )


def test_price_target_output_uses_fallback_for_malformed_analysis_markdown_before_validation():
    output = PriceTargetStructuredOutput.model_validate({
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": MalformedStructuredText(),
    })

    assert output.analysis_markdown == "資料不足"


def test_price_target_output_uses_fallback_for_malformed_text_fields_before_validation():
    output = PriceTargetStructuredOutput.model_validate({
        "price_targets": {
            "dcf_reasoning": MalformedStructuredText(),
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": MalformedStructuredText(),
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": MalformedStructuredText(),
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": MalformedStructuredText(),
        },
        "analysis_markdown": "估值正文",
    })

    assert output.price_targets.dcf_reasoning == "資料不足"
    assert output.price_targets.peer_reasoning == "同業比較完整"
    assert output.price_targets.scenario_reasoning == "資料不足"
    assert output.valuation_summary.primary_method == "blended"
    assert output.valuation_summary.double_counting_check == "資料不足"
    assert output.price_targets.base_case == 120


def test_price_target_output_uses_fallback_for_malformed_price_targets_container_before_validation():
    output = PriceTargetStructuredOutput.model_validate({
        "price_targets": MalformedStructuredText(),
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": "估值正文",
    })

    assert output.price_targets.dcf_reasoning == "資料不足"
    assert output.price_targets.peer_reasoning == "資料不足"
    assert output.price_targets.scenario_reasoning == "資料不足"
    assert output.price_targets.bear_case == 0
    assert output.price_targets.base_case == 0
    assert output.price_targets.bull_case == 0
    assert output.valuation_summary.primary_method == "blended"


def test_price_target_output_uses_fallback_for_malformed_valuation_summary_booleans_before_validation():
    output = PriceTargetStructuredOutput.model_validate({
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": MalformedStructuredText(),
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": "估值正文",
    })

    assert output.valuation_summary.uses_market_value_wacc is False
    assert output.valuation_summary.uses_normalized_fcf is True
    assert output.price_targets.base_case == 120


def test_price_target_output_uses_fallback_for_malformed_valuation_summary_container_before_validation():
    output = PriceTargetStructuredOutput.model_validate({
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": MalformedStructuredText(),
        "analysis_markdown": "估值正文",
    })

    assert output.valuation_summary.primary_method == "blended"
    assert output.valuation_summary.uses_market_value_wacc is False
    assert output.valuation_summary.uses_normalized_fcf is False
    assert output.valuation_summary.double_counting_check == "資料不足"
    assert output.price_targets.base_case == 120


def test_price_target_output_uses_fallback_for_missing_price_targets_before_validation():
    output = PriceTargetStructuredOutput.model_validate({
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": "估值正文",
    })

    assert output.price_targets.dcf_reasoning == "資料不足"
    assert output.price_targets.peer_reasoning == "資料不足"
    assert output.price_targets.scenario_reasoning == "資料不足"
    assert output.price_targets.bear_case == 0
    assert output.price_targets.base_case == 0
    assert output.price_targets.bull_case == 0
    assert output.valuation_summary.primary_method == "blended"
    assert output.valuation_summary.uses_market_value_wacc is True
    assert output.analysis_markdown == "估值正文"


def test_price_target_output_uses_fallback_for_missing_valuation_summary_before_validation():
    output = PriceTargetStructuredOutput.model_validate({
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "analysis_markdown": "估值正文",
    })

    assert output.price_targets.base_case == 120
    assert output.valuation_summary.primary_method == "blended"
    assert output.valuation_summary.uses_market_value_wacc is False
    assert output.valuation_summary.uses_normalized_fcf is False
    assert output.valuation_summary.double_counting_check == "資料不足"
    assert output.analysis_markdown == "估值正文"


def test_valuation_summary_uses_fallback_for_malformed_root_before_validation():
    output = ValuationSummary.model_validate(MalformedStructuredText())

    assert output.primary_method == "blended"
    assert output.uses_market_value_wacc is False
    assert output.uses_normalized_fcf is False
    assert output.double_counting_check == "資料不足"


def test_valuation_summary_boolean_fields_ignore_non_string_literals_before_validation():
    output = ValuationSummary.model_validate({
        "primary_method": "blended",
        "uses_market_value_wacc": StringifyingTrueValue(),
        "uses_normalized_fcf": "yes",
        "double_counting_check": "未重複計算成長與多重評價。",
    })

    assert output.uses_market_value_wacc is False
    assert output.uses_normalized_fcf is True


def test_schema_valuation_summary_fields_ignore_non_string_equal_keys_before_validation():
    output = ValuationSummary.model_validate({
        EqualToPrimaryMethodKey(): "normalized_dcf",
        EqualToMarketValueWaccKey(): True,
        "uses_normalized_fcf": "yes",
        EqualToDoubleCountingCheckKey(): "未重複計算成長與多重評價。",
    })

    assert output.primary_method == "blended"
    assert output.uses_market_value_wacc is False
    assert output.uses_normalized_fcf is True
    assert output.double_counting_check == "資料不足"


def test_price_target_output_uses_fallback_for_malformed_target_numbers_before_validation():
    output = PriceTargetStructuredOutput.model_validate({
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": MalformedStructuredNumber(),
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": "估值正文",
    })

    assert output.price_targets.bear_case == 0
    assert output.price_targets.base_case == 120
    assert output.price_targets.bull_case == 150


def test_schema_numeric_fields_ignore_non_primitive_number_literals_before_validation():
    targets = PriceTargets.model_validate({
        "dcf_reasoning": "DCF 假設完整",
        "peer_reasoning": "同業比較完整",
        "scenario_reasoning": "三情境差異完整",
        "熊市情境": FloatingStructuredNumber(),
        "基本情境": StringifyingNumberValue(),
        "牛市情境": "150",
    })
    scenario = DcfScenarioOutput.model_validate({
        "scenario": "base",
        "revenue_growth_bias_pct": FloatingStructuredNumber(),
        "margin_bias_pct": "1.5",
        "wacc_pct": StringifyingNumberValue(),
        "intrinsic_value": 120,
    })

    assert targets.bear_case == 0
    assert targets.base_case == 0
    assert targets.bull_case == 150
    assert scenario.revenue_growth_bias_pct == 0
    assert scenario.margin_bias_pct == 1.5
    assert scenario.wacc_pct == 1.0
    assert scenario.intrinsic_value == 120


def test_schema_price_target_aliases_ignore_non_string_equal_keys_before_validation():
    targets = PriceTargets.model_validate({
        EqualToDcfReasoningKey(): "DCF 假設完整",
        "peer_reasoning": "同業比較完整",
        "scenario_reasoning": "三情境差異完整",
        EqualToBaseCaseKey(): 120,
    })

    assert targets.dcf_reasoning == "資料不足"
    assert targets.peer_reasoning == "同業比較完整"
    assert targets.scenario_reasoning == "三情境差異完整"
    assert targets.bear_case == 0
    assert targets.base_case == 0
    assert targets.bull_case == 0


def test_price_target_output_uses_fallback_for_malformed_dcf_scenario_numbers_before_validation():
    output = PriceTargetStructuredOutput.model_validate({
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "dcf_scenarios": [
            {
                "scenario": "base",
                "revenue_growth_bias_pct": MalformedStructuredNumber(),
                "margin_bias_pct": 1.5,
                "wacc_pct": MalformedStructuredNumber(),
                "intrinsic_value": MalformedStructuredNumber(),
            }
        ],
        "analysis_markdown": "估值正文",
    })

    scenario = output.dcf_scenarios[0]
    assert scenario.scenario == "base"
    assert scenario.revenue_growth_bias_pct == 0
    assert scenario.margin_bias_pct == 1.5
    assert scenario.wacc_pct == 1
    assert scenario.intrinsic_value == 0


def test_dcf_scenario_output_uses_fallback_for_malformed_root_before_validation():
    output = DcfScenarioOutput.model_validate(MalformedStructuredText())

    assert output.scenario == "base"
    assert output.revenue_growth_bias_pct == 0
    assert output.margin_bias_pct == 0
    assert output.wacc_pct == 1.0
    assert output.intrinsic_value == 0


def test_dcf_scenario_output_uses_fallback_for_invalid_scenario_name_before_validation():
    output = DcfScenarioOutput.model_validate({
        "scenario": "upside",
        "revenue_growth_bias_pct": 4.5,
        "margin_bias_pct": 2.0,
        "wacc_pct": 8.5,
        "intrinsic_value": 150,
    })

    assert output.scenario == "base"
    assert output.revenue_growth_bias_pct == 4.5
    assert output.margin_bias_pct == 2.0
    assert output.wacc_pct == 8.5
    assert output.intrinsic_value == 150


def test_dcf_scenario_schema_ignores_non_string_scenario_literals_before_validation():
    direct = DcfScenarioOutput.model_validate({
        "scenario": StringifyingBearScenario(),
        "revenue_growth_bias_pct": 4.5,
        "margin_bias_pct": 2.0,
        "wacc_pct": 8.5,
        "intrinsic_value": 150,
    })
    nested = PriceTargetStructuredOutput.model_validate({
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "dcf_scenarios": [
            {
                "scenario": StringifyingBearScenario(),
                "revenue_growth_bias_pct": -5.0,
                "margin_bias_pct": -2.0,
                "wacc_pct": 9.5,
                "intrinsic_value": 90,
            },
            {
                "scenario": "base",
                "revenue_growth_bias_pct": 2.5,
                "margin_bias_pct": 1.0,
                "wacc_pct": 9.5,
                "intrinsic_value": 120,
            },
        ],
        "analysis_markdown": "估值正文",
    })

    assert direct.scenario == "base"
    assert [scenario.scenario for scenario in nested.dcf_scenarios] == ["base"]
    assert nested.dcf_scenarios[0].intrinsic_value == 120


def test_schema_dcf_scenario_fields_ignore_non_string_equal_keys_before_validation():
    direct = DcfScenarioOutput.model_validate({
        EqualToDcfScenarioFieldKey("scenario"): "bull",
        EqualToDcfScenarioFieldKey("revenue_growth_bias_pct"): 4.5,
        "margin_bias_pct": 2.0,
        EqualToDcfScenarioFieldKey("wacc_pct"): 8.5,
        EqualToDcfScenarioFieldKey("intrinsic_value"): 150,
    })
    nested = PriceTargetStructuredOutput.model_validate({
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "dcf_scenarios": [
            {
                EqualToDcfScenarioFieldKey("scenario"): "bull",
                EqualToDcfScenarioFieldKey("intrinsic_value"): 90,
                "revenue_growth_bias_pct": -5.0,
                "margin_bias_pct": -2.0,
                "wacc_pct": 9.5,
            },
            {
                "scenario": "base",
                "revenue_growth_bias_pct": 2.5,
                "margin_bias_pct": 1.0,
                "wacc_pct": 9.5,
                "intrinsic_value": 120,
            },
        ],
        "analysis_markdown": "估值正文",
    })

    assert direct.scenario == "base"
    assert direct.revenue_growth_bias_pct == 0
    assert direct.margin_bias_pct == 2.0
    assert direct.wacc_pct == 1.0
    assert direct.intrinsic_value == 0
    assert [scenario.scenario for scenario in nested.dcf_scenarios] == ["base"]
    assert nested.dcf_scenarios[0].intrinsic_value == 120


def test_price_target_output_skips_malformed_dcf_scenario_rows_before_validation():
    output = PriceTargetStructuredOutput.model_validate({
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "dcf_scenarios": [
            MalformedStructuredText(),
            {
                "scenario": "base",
                "revenue_growth_bias_pct": 2.5,
                "margin_bias_pct": 1.0,
                "wacc_pct": 9.5,
                "intrinsic_value": 120,
            },
            {
                "scenario": "bull",
                "revenue_growth_bias_pct": 4.0,
                "margin_bias_pct": 2.0,
                "wacc_pct": 8.5,
                "intrinsic_value": 150,
            },
        ],
        "analysis_markdown": "估值正文",
    })

    assert [scenario.scenario for scenario in output.dcf_scenarios] == ["base", "bull"]
    assert [scenario.intrinsic_value for scenario in output.dcf_scenarios] == [120, 150]


def test_price_target_output_skips_invalid_dcf_scenario_names_before_validation():
    output = PriceTargetStructuredOutput.model_validate({
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "dcf_scenarios": [
            {
                "scenario": "upside",
                "revenue_growth_bias_pct": 6.0,
                "margin_bias_pct": 3.0,
                "wacc_pct": 8.0,
                "intrinsic_value": 180,
            },
            {
                "scenario": "base",
                "revenue_growth_bias_pct": 2.5,
                "margin_bias_pct": 1.0,
                "wacc_pct": 9.5,
                "intrinsic_value": 120,
            },
            {
                "scenario": "bull",
                "revenue_growth_bias_pct": 4.0,
                "margin_bias_pct": 2.0,
                "wacc_pct": 8.5,
                "intrinsic_value": 150,
            },
        ],
        "analysis_markdown": "估值正文",
    })

    assert [scenario.scenario for scenario in output.dcf_scenarios] == ["base", "bull"]
    assert [scenario.intrinsic_value for scenario in output.dcf_scenarios] == [120, 150]


def test_price_target_output_uses_empty_fallback_for_non_list_dcf_scenarios_before_validation():
    output = PriceTargetStructuredOutput.model_validate({
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "dcf_scenarios": MalformedStructuredText(),
        "analysis_markdown": "估值正文",
    })

    assert output.price_targets.base_case == 120
    assert output.dcf_scenarios == []


def test_management_sentiment_output_uses_fallback_for_malformed_analysis_markdown_before_validation():
    output = ManagementSentimentStructuredOutput.model_validate({
        "guidance_tone": "樂觀",
        "confidence": 0.7,
        "highlights": [
            {"keyword": "需求回溫", "quote": "AI 訂單恢復成長"},
            {"keyword": "毛利率", "quote": "管理層維持全年展望"},
            {"keyword": "資本支出", "quote": "供應鏈投資保持紀律"},
        ],
        "analysis_markdown": MalformedStructuredText(),
    })

    assert output.analysis_markdown == "資料不足"


def test_management_highlight_uses_fallback_for_malformed_root_before_validation():
    output = ManagementHighlight.model_validate(MalformedStructuredText())

    assert output.keyword == "亮點"
    assert output.quote == "資料不足"


def test_management_sentiment_output_uses_fallback_for_malformed_root_before_validation():
    output = ManagementSentimentStructuredOutput.model_validate(MalformedStructuredText())

    assert output.guidance_tone == "資料不足"
    assert output.confidence == 0.0
    assert [(row.keyword, row.quote) for row in output.highlights] == [
        ("亮點", "資料不足"),
        ("亮點", "資料不足"),
        ("亮點", "資料不足"),
    ]
    assert output.analysis_markdown == "資料不足"


def test_management_sentiment_output_uses_fallback_for_malformed_text_fields_before_validation():
    output = ManagementSentimentStructuredOutput.model_validate({
        "guidance_tone": MalformedStructuredText(),
        "confidence": 0.7,
        "highlights": [
            {"keyword": "需求回溫", "quote": "AI 訂單恢復成長"},
            {"keyword": MalformedStructuredText(), "quote": "管理層維持全年展望"},
            {"keyword": "資本支出", "quote": MalformedStructuredText()},
        ],
        "analysis_markdown": "管理層正文",
    })

    assert output.guidance_tone == "資料不足"
    assert output.highlights[0].keyword == "需求回溫"
    assert output.highlights[1].keyword == "亮點"
    assert output.highlights[1].quote == "管理層維持全年展望"
    assert output.highlights[2].keyword == "資本支出"
    assert output.highlights[2].quote == "資料不足"


def test_management_sentiment_output_uses_fallback_for_malformed_highlight_rows_before_validation():
    output = ManagementSentimentStructuredOutput.model_validate({
        "guidance_tone": "樂觀",
        "confidence": 0.7,
        "highlights": [
            {"keyword": "需求回溫", "quote": "AI 訂單恢復成長"},
            MalformedStructuredText(),
            {"keyword": "資本支出", "quote": "供應鏈投資保持紀律"},
        ],
        "analysis_markdown": "管理層正文",
    })

    assert output.highlights[0].keyword == "需求回溫"
    assert output.highlights[1].keyword == "亮點"
    assert output.highlights[1].quote == "資料不足"
    assert output.highlights[2].keyword == "資本支出"


def test_management_sentiment_output_uses_fallback_for_malformed_highlight_collection_before_validation():
    output = ManagementSentimentStructuredOutput.model_validate({
        "guidance_tone": "樂觀",
        "confidence": 0.7,
        "highlights": MalformedStructuredText(),
        "analysis_markdown": "管理層正文",
    })

    assert [(row.keyword, row.quote) for row in output.highlights] == [
        ("亮點", "資料不足"),
        ("亮點", "資料不足"),
        ("亮點", "資料不足"),
    ]
    assert output.guidance_tone == "樂觀"


def test_management_sentiment_output_uses_fallback_for_missing_highlights_before_validation():
    output = ManagementSentimentStructuredOutput.model_validate({
        "guidance_tone": "樂觀",
        "confidence": 0.7,
        "analysis_markdown": "管理層正文",
    })

    assert [(row.keyword, row.quote) for row in output.highlights] == [
        ("亮點", "資料不足"),
        ("亮點", "資料不足"),
        ("亮點", "資料不足"),
    ]
    assert output.guidance_tone == "樂觀"
    assert output.confidence == 0.7
    assert output.analysis_markdown == "管理層正文"


def test_management_sentiment_output_pads_short_highlight_collection_before_validation():
    output = ManagementSentimentStructuredOutput.model_validate({
        "guidance_tone": "樂觀",
        "confidence": 0.7,
        "highlights": [
            {"keyword": "需求回溫", "quote": "AI 訂單恢復成長"},
        ],
        "analysis_markdown": "管理層正文",
    })

    assert [(row.keyword, row.quote) for row in output.highlights] == [
        ("需求回溫", "AI 訂單恢復成長"),
        ("亮點", "資料不足"),
        ("亮點", "資料不足"),
    ]
    assert output.guidance_tone == "樂觀"


def test_management_sentiment_output_uses_fallback_for_malformed_confidence_before_validation():
    output = ManagementSentimentStructuredOutput.model_validate({
        "guidance_tone": "樂觀",
        "confidence": MalformedStructuredNumber(),
        "highlights": [
            {"keyword": "需求回溫", "quote": "AI 訂單恢復成長"},
            {"keyword": "毛利率", "quote": "管理層維持全年展望"},
            {"keyword": "資本支出", "quote": "供應鏈投資保持紀律"},
        ],
        "analysis_markdown": "管理層正文",
    })

    assert output.confidence == 0.0
    assert output.guidance_tone == "樂觀"


def test_bear_advocate_output_uses_fallback_for_malformed_analysis_markdown_before_validation():
    output = BearAdvocateStructuredOutput.model_validate({
        "thesis_summary": "下行風險仍需折價。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值倍數下修",
                "severity": "high",
                "confidence": 0.8,
            },
            {
                "title": "現金流轉弱",
                "evidence": "營運資金需求上升使 FCF 轉換率下滑。",
                "impact": "DCF 折價",
                "severity": "warning",
                "confidence": 0.6,
            },
            {
                "title": "客戶集中",
                "evidence": "主要客戶拉貨節奏可能放大營收波動。",
                "impact": "營收能見度下降",
                "severity": "warning",
                "confidence": 0.5,
            },
        ],
        "analysis_markdown": MalformedStructuredText(),
    })

    assert output.analysis_markdown == "資料不足"


def test_bear_advocate_output_uses_fallback_for_malformed_root_before_validation():
    output = BearAdvocateStructuredOutput.model_validate(MalformedStructuredText())

    assert output.thesis_summary == "資料不足"
    assert [
        (risk.title, risk.evidence, risk.impact, risk.severity, risk.confidence)
        for risk in output.downside_risks
    ] == [
        ("下行風險", "資料不足", "", "warning", 0.7),
        ("下行風險", "資料不足", "", "warning", 0.7),
        ("下行風險", "資料不足", "", "warning", 0.7),
    ]
    assert output.analysis_markdown == "資料不足"


def test_downside_risk_uses_fallback_for_malformed_root_before_validation():
    output = DownsideRisk.model_validate(MalformedStructuredText())

    assert output.title == "下行風險"
    assert output.evidence == "資料不足"
    assert output.impact == ""
    assert output.severity == "warning"
    assert output.confidence == 0.7


def test_bear_advocate_output_uses_fallback_for_malformed_text_fields_before_validation():
    output = BearAdvocateStructuredOutput.model_validate({
        "thesis_summary": MalformedStructuredText(),
        "downside_risks": [
            {
                "title": MalformedStructuredText(),
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": MalformedStructuredText(),
                "severity": MalformedStructuredText(),
                "confidence": 0.8,
            },
            {
                "title": "現金流轉弱",
                "evidence": MalformedStructuredText(),
                "impact": "DCF 折價",
                "severity": "high",
                "confidence": 0.6,
            },
            {
                "title": "客戶集中",
                "evidence": "主要客戶拉貨節奏可能放大營收波動。",
                "impact": "營收能見度下降",
                "severity": "warning",
                "confidence": 0.5,
            },
        ],
        "analysis_markdown": "空方正文",
    })

    assert output.thesis_summary == "資料不足"
    assert output.downside_risks[0].title == "下行風險"
    assert output.downside_risks[0].evidence == "同業報價下修且庫存去化慢於預期。"
    assert output.downside_risks[0].impact == ""
    assert output.downside_risks[0].severity == "warning"
    assert output.downside_risks[1].title == "現金流轉弱"
    assert output.downside_risks[1].evidence == "資料不足"
    assert output.downside_risks[1].impact == "DCF 折價"
    assert output.downside_risks[1].severity == "high"
    assert output.downside_risks[2].title == "客戶集中"
    assert output.downside_risks[2].evidence == "主要客戶拉貨節奏可能放大營收波動。"


def test_bear_advocate_output_uses_fallback_for_malformed_confidence_before_validation():
    output = BearAdvocateStructuredOutput.model_validate({
        "thesis_summary": "下行風險仍需折價。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值倍數下修",
                "severity": "high",
                "confidence": MalformedStructuredNumber(),
            },
            {
                "title": "現金流轉弱",
                "evidence": "營運資金需求上升使 FCF 轉換率下滑。",
                "impact": "DCF 折價",
                "severity": "warning",
                "confidence": 0.6,
            },
            {
                "title": "客戶集中",
                "evidence": "主要客戶拉貨節奏可能放大營收波動。",
                "impact": "營收能見度下降",
                "severity": "warning",
                "confidence": 0.5,
            },
        ],
        "analysis_markdown": "空方正文",
    })

    assert output.downside_risks[0].confidence == 0.7
    assert output.downside_risks[1].confidence == 0.6
    assert output.thesis_summary == "下行風險仍需折價。"


def test_bear_advocate_output_uses_fallback_for_malformed_risk_rows_before_validation():
    output = BearAdvocateStructuredOutput.model_validate({
        "thesis_summary": "下行風險仍需折價。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值倍數下修",
                "severity": "high",
                "confidence": 0.8,
            },
            MalformedStructuredText(),
            {
                "title": "客戶集中",
                "evidence": "主要客戶拉貨節奏可能放大營收波動。",
                "impact": "營收能見度下降",
                "severity": "warning",
                "confidence": 0.5,
            },
        ],
        "analysis_markdown": "空方正文",
    })

    assert output.downside_risks[0].title == "毛利率壓力"
    assert output.downside_risks[1].title == "下行風險"
    assert output.downside_risks[1].evidence == "資料不足"
    assert output.downside_risks[1].severity == "warning"
    assert output.downside_risks[1].confidence == 0.7
    assert output.downside_risks[2].title == "客戶集中"


def test_bear_advocate_output_uses_fallback_for_malformed_risk_collection_before_validation():
    output = BearAdvocateStructuredOutput.model_validate({
        "thesis_summary": "下行風險仍需折價。",
        "downside_risks": MalformedStructuredText(),
        "analysis_markdown": "空方正文",
    })

    assert [
        (risk.title, risk.evidence, risk.impact, risk.severity, risk.confidence)
        for risk in output.downside_risks
    ] == [
        ("下行風險", "資料不足", "", "warning", 0.7),
        ("下行風險", "資料不足", "", "warning", 0.7),
        ("下行風險", "資料不足", "", "warning", 0.7),
    ]
    assert output.thesis_summary == "下行風險仍需折價。"


def test_bear_advocate_output_uses_fallback_for_missing_downside_risks_before_validation():
    output = BearAdvocateStructuredOutput.model_validate({
        "thesis_summary": "下行風險仍需折價。",
        "analysis_markdown": "空方正文",
    })

    assert [
        (risk.title, risk.evidence, risk.impact, risk.severity, risk.confidence)
        for risk in output.downside_risks
    ] == [
        ("下行風險", "資料不足", "", "warning", 0.7),
        ("下行風險", "資料不足", "", "warning", 0.7),
        ("下行風險", "資料不足", "", "warning", 0.7),
    ]
    assert output.thesis_summary == "下行風險仍需折價。"
    assert output.analysis_markdown == "空方正文"


def test_bear_advocate_output_pads_short_risk_collection_before_validation():
    output = BearAdvocateStructuredOutput.model_validate({
        "thesis_summary": "下行風險仍需折價。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值倍數下修",
                "severity": "high",
                "confidence": 0.8,
            },
        ],
        "analysis_markdown": "空方正文",
    })

    assert [
        (risk.title, risk.evidence, risk.impact, risk.severity, risk.confidence)
        for risk in output.downside_risks
    ] == [
        ("毛利率壓力", "同業報價下修且庫存去化慢於預期。", "估值倍數下修", "high", 0.8),
        ("下行風險", "資料不足", "", "warning", 0.7),
        ("下行風險", "資料不足", "", "warning", 0.7),
    ]
    assert output.thesis_summary == "下行風險仍需折價。"


def test_swing_trade_setup_uses_fallback_for_malformed_text_fields_before_validation():
    output = SwingTradeSetup.model_validate({
        "trade_direction": MalformedStructuredText(),
        "entry_zone": MalformedStructuredText(),
        "target_price": "NT$112",
        "stop_loss": MalformedStructuredText(),
        "core_catalyst": MalformedStructuredText(),
        "risk_level": MalformedStructuredText(),
    })

    assert output.trade_direction == "Neutral"
    assert output.entry_zone == "N/A"
    assert output.target_price == "NT$112"
    assert output.stop_loss == "N/A"
    assert output.core_catalyst == "N/A"
    assert output.risk_level == "High"


def test_structured_display_models_ignore_non_string_literals_before_validation():
    highlight = ManagementHighlight.model_validate({
        "keyword": StringifyingStructuredText(),
        "quote": StringifyingStructuredText(),
    })
    management = ManagementSentimentStructuredOutput.model_validate({
        "guidance_tone": StringifyingStructuredText(),
        "confidence": 0.7,
        "highlights": [
            {"keyword": StringifyingStructuredText(), "quote": "有效引述"},
            {"keyword": "有效亮點", "quote": StringifyingStructuredText()},
        ],
        "analysis_markdown": "管理層正文",
    })
    downside_risk = DownsideRisk.model_validate({
        "title": StringifyingStructuredText(),
        "evidence": StringifyingStructuredText(),
        "impact": StringifyingStructuredText(),
        "severity": StringifyingStructuredText(),
        "confidence": 0.8,
    })
    downside = BearAdvocateStructuredOutput.model_validate({
        "thesis_summary": StringifyingStructuredText(),
        "downside_risks": [
            {
                "title": StringifyingStructuredText(),
                "evidence": "有效證據",
                "impact": StringifyingStructuredText(),
                "severity": StringifyingStructuredText(),
                "confidence": 0.8,
            },
            {
                "title": "有效風險",
                "evidence": StringifyingStructuredText(),
                "impact": "有效影響",
                "severity": "high",
                "confidence": 0.6,
            },
        ],
        "analysis_markdown": "空方正文",
    })
    trade = SwingTradeSetup.model_validate({
        "trade_direction": StringifyingStructuredText(),
        "entry_zone": StringifyingStructuredText(),
        "target_price": "NT$112",
        "stop_loss": StringifyingStructuredText(),
        "core_catalyst": StringifyingStructuredText(),
        "risk_level": StringifyingStructuredText(),
    })

    assert highlight.keyword == "亮點"
    assert highlight.quote == "資料不足"
    assert management.guidance_tone == "資料不足"
    assert [(row.keyword, row.quote) for row in management.highlights] == [
        ("亮點", "有效引述"),
        ("有效亮點", "資料不足"),
        ("亮點", "資料不足"),
    ]
    assert downside_risk.title == "下行風險"
    assert downside_risk.evidence == "資料不足"
    assert downside_risk.impact == ""
    assert downside_risk.severity == "warning"
    assert downside.thesis_summary == "資料不足"
    assert [
        (risk.title, risk.evidence, risk.impact, risk.severity, risk.confidence)
        for risk in downside.downside_risks
    ] == [
        ("下行風險", "有效證據", "", "warning", 0.8),
        ("有效風險", "資料不足", "有效影響", "high", 0.6),
        ("下行風險", "資料不足", "", "warning", 0.7),
    ]
    assert trade.trade_direction == "Neutral"
    assert trade.entry_zone == "N/A"
    assert trade.target_price == "NT$112"
    assert trade.stop_loss == "N/A"
    assert trade.core_catalyst == "N/A"
    assert trade.risk_level == "High"
    assert "bad-body-literal" not in (
        repr(highlight) + repr(management) + repr(downside_risk) + repr(downside) + repr(trade)
    )


def test_swing_trade_setup_uses_fallback_for_malformed_root_before_validation():
    output = SwingTradeSetup.model_validate(MalformedStructuredText())

    assert output.trade_direction == "Neutral"
    assert output.entry_zone == "N/A"
    assert output.target_price == "N/A"
    assert output.stop_loss == "N/A"
    assert output.core_catalyst == "N/A"
    assert output.risk_level == "High"


def test_recommendation_output_uses_fallback_for_malformed_root_before_validation():
    output = RecommendationStructuredOutput.model_validate(MalformedStructuredText())

    assert output.reasoning_steps == ["待補推論步驟", "待補推論步驟", "待補推論步驟"]
    assert output.recommendation.recommendation == "持有"
    assert output.recommendation.target_3m == "N/A"
    assert output.recommendation.target_6m == "N/A"
    assert output.recommendation.target_12m == "N/A"
    assert output.recommendation.long_term_potential_5y == "N/A"
    assert output.recommendation.confidence == "N/A"
    assert output.confidence_basis.evidence_items == ["待補具體佐證", "待補具體佐證", "待補具體佐證"]
    assert output.confidence_basis.key_risks_acknowledged == ["待補已納入風險", "待補已納入風險"]
    assert output.confidence_basis.data_gaps == []
    assert [row.trigger_condition for row in output.scenario_triggers] == [
        "待後續資料確認觸發條件",
        "待後續資料確認觸發條件",
    ]
    assert [row.action for row in output.scenario_triggers] == ["重新檢查投資結論", "重新檢查投資結論"]
    assert [row.direction for row in output.scenario_triggers] == ["neutral_review", "neutral_review"]
    assert [(row.event_name, row.impact_direction, row.trigger_condition) for row in output.next_catalysts] == [
        ("Scenario trigger 1", "volatile", "待後續資料確認觸發條件")
    ]
    assert output.analysis_markdown == "資料不足"


def test_recommendation_output_uses_fallback_for_missing_recommendation_object_before_validation():
    payload = _recommendation_payload()
    payload.pop("recommendation")

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.recommendation.recommendation == "持有"
    assert output.recommendation.target_3m == "N/A"
    assert output.reasoning_steps == ["估值支持中性", "風險限制上行", "催化劑決定再評估"]
    assert output.confidence_basis.evidence_items == ["估值接近基本情境", "FCF 維持正值", "同業估值未明顯折價"]


def test_recommendation_output_uses_fallback_for_missing_confidence_basis_object_before_validation():
    payload = _recommendation_payload()
    payload.pop("confidence_basis")

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.confidence_basis.evidence_items == ["待補具體佐證", "待補具體佐證", "待補具體佐證"]
    assert output.confidence_basis.key_risks_acknowledged == ["待補已納入風險", "待補已納入風險"]
    assert output.confidence_basis.data_gaps == []
    assert output.recommendation.recommendation == "持有"


def test_recommendation_fields_uses_fallback_for_malformed_root_before_validation():
    output = RecommendationFields.model_validate(MalformedStructuredText())

    assert output.recommendation == "持有"
    assert output.target_3m == "N/A"
    assert output.target_6m == "N/A"
    assert output.target_12m == "N/A"
    assert output.long_term_potential_5y == "N/A"
    assert output.confidence == "N/A"


def test_recommendation_schema_ignores_non_string_keys_and_labels_before_validation():
    standard = RecommendationFields.model_validate({
        StringifyingRecommendationKey(): "買入",
        "建議": StringifyingBuyLabel(),
        StringifyingRecommendationTargetKey(): "NT$999",
        "中期目標（6個月）": "NT$120",
        "長期目標（12個月）": "NT$130",
        "長期潛力（5年）": "NT$150",
        "信心指數": "7/10",
    })
    bubble = BubbleSniperRecommendationFields.model_validate({
        StringifyingRecommendationKey(): "買入",
        "建議": StringifyingBuyLabel(),
        StringifyingRecommendationTargetKey(): "NT$999",
        "中期目標（6個月）": "NT$100",
        "長期目標（12個月）": "NT$80",
        "長期潛力（5年）": "NT$60",
        "信心指數": "6/10",
    })

    assert standard.recommendation == "持有"
    assert standard.target_3m == "N/A"
    assert standard.target_6m == "NT$120"
    assert bubble.recommendation == "避免"
    assert bubble.target_3m == "N/A"
    assert bubble.target_6m == "NT$100"


def test_recommendation_output_requires_next_catalysts():
    payload = _recommendation_payload()

    output = RecommendationStructuredOutput.model_validate(payload)

    assert isinstance(output.next_catalysts[0], Catalyst)
    assert output.next_catalysts[0].impact_direction == "bullish"

    with pytest.raises(ValidationError):
        RecommendationStructuredOutput.model_validate(_recommendation_payload(next_catalysts=[]))


def test_recommendation_output_builds_next_catalysts_from_safe_scenario_triggers():
    payload = _recommendation_payload()
    payload.pop("next_catalysts")
    payload["scenario_triggers"] = [
        {
            "trigger_condition": MalformedStructuredText(),
            "action": "略過壞觸發條件",
            "direction": "bearish_downgrade",
        },
        {
            "trigger_condition": "法說會正式調升全年營收與毛利率展望",
            "action": "重新評估上行情境",
            "direction": "bullish_upgrade",
        },
        {
            "trigger_condition": "季度毛利率低於 43% 且管理層未提出改善計畫",
            "action": "重新評估風險情境",
            "direction": "bearish_downgrade",
        },
    ]

    output = RecommendationStructuredOutput.model_validate(payload)

    assert len(output.scenario_triggers) == 2
    assert len(output.next_catalysts) == 2
    assert output.next_catalysts[0].trigger_condition == "法說會正式調升全年營收與毛利率展望"
    assert output.next_catalysts[0].impact_direction == "bullish"


def test_recommendation_output_builds_next_catalysts_from_length_safe_scenario_triggers():
    payload = _recommendation_payload()
    payload.pop("next_catalysts")
    payload["scenario_triggers"] = [
        {"trigger_condition": "短", "action": "查", "direction": "neutral_review"},
        {
            "trigger_condition": "法說會正式調升全年營收與毛利率展望",
            "action": "重新評估上行情境",
            "direction": "bullish_upgrade",
        },
        {
            "trigger_condition": "季度毛利率低於 43% 且管理層未提出改善計畫",
            "action": "重新評估風險情境",
            "direction": "bearish_downgrade",
        },
    ]

    output = RecommendationStructuredOutput.model_validate(payload)

    assert len(output.scenario_triggers) == 2
    assert [row.trigger_condition for row in output.scenario_triggers] == [
        "法說會正式調升全年營收與毛利率展望",
        "季度毛利率低於 43% 且管理層未提出改善計畫",
    ]
    assert len(output.next_catalysts) == 2
    assert output.next_catalysts[0].trigger_condition == "法說會正式調升全年營收與毛利率展望"


def test_recommendation_output_uses_minimum_fallback_for_malformed_scenario_triggers_before_validation():
    payload = _recommendation_payload()
    payload.pop("next_catalysts")
    payload["scenario_triggers"] = [
        {
            "trigger_condition": "季度毛利率低於 43% 且管理層未提出改善計畫",
            "action": "重新評估風險情境",
            "direction": "bearish_downgrade",
        },
        {
            "trigger_condition": MalformedStructuredText(),
            "action": "重新檢查投資結論",
            "direction": "neutral_review",
        },
    ]

    output = RecommendationStructuredOutput.model_validate(payload)

    assert [row.trigger_condition for row in output.scenario_triggers] == [
        "季度毛利率低於 43% 且管理層未提出改善計畫",
        "待後續資料確認觸發條件",
    ]
    assert output.scenario_triggers[1].action == "重新檢查投資結論"
    assert output.scenario_triggers[1].direction == "neutral_review"
    assert [row.trigger_condition for row in output.next_catalysts] == [
        "季度毛利率低於 43% 且管理層未提出改善計畫",
        "待後續資料確認觸發條件",
    ]


def test_recommendation_output_uses_list_fallback_for_malformed_scenario_trigger_collection_before_validation():
    payload = _recommendation_payload()
    payload.pop("next_catalysts")
    payload["scenario_triggers"] = MalformedStructuredText()

    output = RecommendationStructuredOutput.model_validate(payload)

    assert [row.trigger_condition for row in output.scenario_triggers] == [
        "待後續資料確認觸發條件",
        "待後續資料確認觸發條件",
    ]
    assert [row.action for row in output.scenario_triggers] == [
        "重新檢查投資結論",
        "重新檢查投資結論",
    ]
    assert [row.direction for row in output.scenario_triggers] == ["neutral_review", "neutral_review"]
    assert [row.trigger_condition for row in output.next_catalysts] == [
        "待後續資料確認觸發條件",
        "待後續資料確認觸發條件",
    ]


def test_recommendation_output_uses_fallback_for_missing_scenario_triggers_before_validation():
    payload = _recommendation_payload()
    payload.pop("scenario_triggers")

    output = RecommendationStructuredOutput.model_validate(payload)

    assert [row.trigger_condition for row in output.scenario_triggers] == [
        "待後續資料確認觸發條件",
        "待後續資料確認觸發條件",
    ]
    assert [row.action for row in output.scenario_triggers] == [
        "重新檢查投資結論",
        "重新檢查投資結論",
    ]
    assert [row.direction for row in output.scenario_triggers] == ["neutral_review", "neutral_review"]
    assert output.next_catalysts[0].event_name == "Q3 法說會"
    assert output.recommendation.recommendation == "持有"


def test_recommendation_output_derives_next_catalysts_from_missing_scenario_trigger_fallback():
    payload = _recommendation_payload()
    payload.pop("scenario_triggers")
    payload.pop("next_catalysts")

    output = RecommendationStructuredOutput.model_validate(payload)

    assert [row.trigger_condition for row in output.scenario_triggers] == [
        "待後續資料確認觸發條件",
        "待後續資料確認觸發條件",
    ]
    assert [(row.event_name, row.impact_direction, row.trigger_condition) for row in output.next_catalysts] == [
        ("Scenario trigger 1", "volatile", "待後續資料確認觸發條件"),
        ("Scenario trigger 2", "volatile", "待後續資料確認觸發條件"),
    ]
    assert output.analysis_markdown == "正式報告正文"


def test_recommendation_output_truncates_overlong_scenario_triggers_before_catalyst_derivation():
    payload = _recommendation_payload()
    payload.pop("next_catalysts")
    payload["scenario_triggers"] = [
        {
            "trigger_condition": f"第 {idx} 個需要重新評估投資結論的具體觸發條件",
            "action": "重新評估情境",
            "direction": "neutral_review",
        }
        for idx in range(1, 7)
    ]

    output = RecommendationStructuredOutput.model_validate(payload)

    assert len(output.scenario_triggers) == 5
    assert output.scenario_triggers[-1].trigger_condition == "第 5 個需要重新評估投資結論的具體觸發條件"
    assert all("第 6 個" not in row.trigger_condition for row in output.scenario_triggers)
    assert [row.trigger_condition for row in output.next_catalysts] == [
        "第 1 個需要重新評估投資結論的具體觸發條件",
        "第 2 個需要重新評估投資結論的具體觸發條件",
        "第 3 個需要重新評估投資結論的具體觸發條件",
    ]


def test_recommendation_output_skips_malformed_confidence_basis_items_before_validation():
    payload = _recommendation_payload()
    payload["confidence_basis"] = {
        "evidence_items": ["估值接近基本情境", MalformedStructuredText(), "FCF 維持正值", "同業估值未明顯折價"],
        "key_risks_acknowledged": ["毛利率下滑", MalformedStructuredText(), "需求能見度不足"],
        "data_gaps": [MalformedStructuredText(), "月營收細項待補"],
    }

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.confidence_basis.evidence_items == ["估值接近基本情境", "FCF 維持正值", "同業估值未明顯折價"]
    assert output.confidence_basis.key_risks_acknowledged == ["毛利率下滑", "需求能見度不足"]
    assert output.confidence_basis.data_gaps == ["月營收細項待補"]


def test_recommendation_output_uses_minimum_fallback_for_malformed_confidence_basis_items_before_validation():
    payload = _recommendation_payload()
    payload["confidence_basis"] = {
        "evidence_items": ["估值接近基本情境", MalformedStructuredText(), "FCF 維持正值"],
        "key_risks_acknowledged": ["毛利率下滑", MalformedStructuredText()],
        "data_gaps": [MalformedStructuredText()],
    }

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.confidence_basis.evidence_items == ["估值接近基本情境", "FCF 維持正值", "待補具體佐證"]
    assert output.confidence_basis.key_risks_acknowledged == ["毛利率下滑", "待補已納入風險"]
    assert output.confidence_basis.data_gaps == []


def test_recommendation_output_uses_list_fallback_for_malformed_confidence_basis_required_collections_before_validation():
    payload = _recommendation_payload()
    payload["confidence_basis"] = {
        "evidence_items": MalformedStructuredText(),
        "key_risks_acknowledged": MalformedStructuredText(),
        "data_gaps": MalformedStructuredText(),
    }

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.confidence_basis.evidence_items == ["待補具體佐證", "待補具體佐證", "待補具體佐證"]
    assert output.confidence_basis.key_risks_acknowledged == ["待補已納入風險", "待補已納入風險"]
    assert output.confidence_basis.data_gaps == []
    assert output.recommendation.recommendation == "持有"


def test_recommendation_confidence_basis_ignores_non_string_literals_before_validation():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    basis_payload = {
        "evidence_items": ["估值接近基本情境", StringifyingStructuredText(), "FCF 維持正值"],
        "key_risks_acknowledged": ["毛利率下滑", StringifyingStructuredText()],
        "data_gaps": [StringifyingStructuredText(), "月營收細項待補"],
    }

    direct_basis = ConfidenceBasis.model_validate(basis_payload)

    assert direct_basis.evidence_items == ["估值接近基本情境", "FCF 維持正值", "待補具體佐證"]
    assert direct_basis.key_risks_acknowledged == ["毛利率下滑", "待補已納入風險"]
    assert direct_basis.data_gaps == ["月營收細項待補"]

    payload = _recommendation_payload()
    payload["confidence_basis"] = basis_payload

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    confidence_basis = normalized["recommendation"]["confidence_basis"]
    assert confidence_basis["evidence_items"] == ["估值接近基本情境", "FCF 維持正值", "待補具體佐證"]
    assert confidence_basis["key_risks_acknowledged"] == ["毛利率下滑", "待補已納入風險"]
    assert confidence_basis["data_gaps"] == ["月營收細項待補"]

    report_text = structured_output_to_report_text(7, normalized)

    assert "bad-body-literal" not in (repr(direct_basis) + repr(normalized) + report_text)


def test_confidence_basis_uses_fallback_for_malformed_root_before_validation():
    output = ConfidenceBasis.model_validate(MalformedStructuredText())

    assert output.evidence_items == ["待補具體佐證", "待補具體佐證", "待補具體佐證"]
    assert output.key_risks_acknowledged == ["待補已納入風險", "待補已納入風險"]
    assert output.data_gaps == []


def test_recommendation_output_skips_malformed_reasoning_steps_before_validation():
    payload = _recommendation_payload()
    payload["reasoning_steps"] = ["估值支持中性", MalformedStructuredText(), "風險限制上行", "催化劑決定再評估"]

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.reasoning_steps == ["估值支持中性", "風險限制上行", "催化劑決定再評估"]


def test_recommendation_output_uses_minimum_fallback_for_malformed_reasoning_steps_before_validation():
    payload = _recommendation_payload()
    payload["reasoning_steps"] = ["估值支持中性", MalformedStructuredText(), "催化劑決定再評估"]

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.reasoning_steps == ["估值支持中性", "催化劑決定再評估", "待補推論步驟"]


def test_recommendation_output_uses_list_fallback_for_malformed_reasoning_step_collection_before_validation():
    payload = _recommendation_payload()
    payload["reasoning_steps"] = MalformedStructuredText()

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.reasoning_steps == ["待補推論步驟", "待補推論步驟", "待補推論步驟"]


def test_recommendation_output_normalizes_recommendation_alias_before_validation():
    payload = _recommendation_payload()
    payload["recommendation"]["建議"] = "強烈放空"

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.recommendation.recommendation == "放空"


def test_recommendation_output_uses_fallback_for_missing_recommendation_label():
    payload = _recommendation_payload()
    payload["recommendation"].pop("建議")

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.recommendation.recommendation == "持有"
    assert output.recommendation.target_3m == "NT$300"


def test_recommendation_output_uses_fallback_for_malformed_recommendation_text_fields():
    payload = _recommendation_payload()
    payload["recommendation"]["短期目標（3個月）"] = MalformedStructuredText()
    payload["recommendation"]["信心指數"] = MalformedStructuredText()

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.recommendation.target_3m == "N/A"
    assert output.recommendation.target_6m == "NT$330"
    assert output.recommendation.confidence == "N/A"


def test_recommendation_output_uses_fallback_for_string_empty_tokens_before_validation():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    payload = _recommendation_payload(next_catalysts=[
        {
            "event_name": "NaN",
            "expected_timeframe": "Infinity",
            "impact_direction": "-Infinity",
            "trigger_condition": "N/A",
        },
    ])
    payload["reasoning_steps"] = ["估值支持中性", "NaN", "催化劑決定再評估"]
    payload["recommendation"] = {
        **payload["recommendation"],
        "建議": "NaN",
        "短期目標（3個月）": "NaN",
        "信心指數": "Infinity",
    }
    payload["confidence_basis"] = {
        "evidence_items": ["NaN", "估值接近基本情境", "Infinity"],
        "key_risks_acknowledged": ["-Infinity", "需求能見度不足"],
        "data_gaps": ["N/A", "月營收細項待補"],
    }
    payload["scenario_triggers"] = [
        {
            "trigger_condition": "NaN",
            "action": "Infinity",
            "direction": "-Infinity",
        },
        {
            "trigger_condition": "法說會正式調升全年營收與毛利率展望",
            "action": "重新評估上行情境",
            "direction": "bullish_upgrade",
        },
    ]
    payload["analysis_markdown"] = "-Infinity"

    output = RecommendationStructuredOutput.model_validate(payload)
    normalized = normalize_structured_output(7, payload)

    assert output.reasoning_steps == ["估值支持中性", "催化劑決定再評估", "待補推論步驟"]
    assert output.recommendation.recommendation == "持有"
    assert output.recommendation.target_3m == "N/A"
    assert output.recommendation.confidence == "N/A"
    assert output.confidence_basis.evidence_items == ["估值接近基本情境", "待補具體佐證", "待補具體佐證"]
    assert output.confidence_basis.key_risks_acknowledged == ["需求能見度不足", "待補已納入風險"]
    assert output.confidence_basis.data_gaps == ["月營收細項待補"]
    assert output.scenario_triggers[0].trigger_condition == "法說會正式調升全年營收與毛利率展望"
    assert output.scenario_triggers[1].action == "重新檢查投資結論"
    assert output.next_catalysts[0].event_name == "Scenario trigger 1"
    assert output.next_catalysts[0].trigger_condition == "法說會正式調升全年營收與毛利率展望"
    assert output.analysis_markdown == "資料不足"

    assert normalized is not None
    report_text = structured_output_to_report_text(7, normalized)
    assert "nan" not in (repr(normalized) + report_text).lower()
    assert "infinity" not in (repr(normalized) + report_text).lower()


def test_recommendation_output_uses_fallback_for_dash_and_missing_tokens_before_validation():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    payload = _recommendation_payload(next_catalysts=[
        {
            "event_name": "--",
            "expected_timeframe": "MISSING",
            "impact_direction": "NIL",
            "trigger_condition": "-",
        },
    ])
    payload["reasoning_steps"] = ["估值支持中性", "-", "催化劑決定再評估"]
    payload["recommendation"] = {
        **payload["recommendation"],
        "建議": "-",
        "短期目標（3個月）": "--",
        "信心指數": "MISSING",
    }
    payload["confidence_basis"] = {
        "evidence_items": ["--", "估值接近基本情境", "MISSING"],
        "key_risks_acknowledged": ["NIL", "需求能見度不足"],
        "data_gaps": ["-", "月營收細項待補"],
    }
    payload["scenario_triggers"] = [
        {
            "trigger_condition": "-",
            "action": "--",
            "direction": "MISSING",
        },
        {
            "trigger_condition": "法說會正式調升全年營收與毛利率展望",
            "action": "重新評估上行情境",
            "direction": "bullish_upgrade",
        },
    ]
    payload["analysis_markdown"] = "NIL"

    output = RecommendationStructuredOutput.model_validate(payload)
    normalized = normalize_structured_output(7, payload)

    assert output.reasoning_steps == ["估值支持中性", "催化劑決定再評估", "待補推論步驟"]
    assert output.recommendation.recommendation == "持有"
    assert output.recommendation.target_3m == "N/A"
    assert output.recommendation.confidence == "N/A"
    assert output.confidence_basis.evidence_items == ["估值接近基本情境", "待補具體佐證", "待補具體佐證"]
    assert output.confidence_basis.key_risks_acknowledged == ["需求能見度不足", "待補已納入風險"]
    assert output.confidence_basis.data_gaps == ["月營收細項待補"]
    assert output.scenario_triggers[0].trigger_condition == "法說會正式調升全年營收與毛利率展望"
    assert output.scenario_triggers[1].action == "重新檢查投資結論"
    assert output.next_catalysts[0].event_name == "Scenario trigger 1"
    assert output.analysis_markdown == "資料不足"

    assert normalized is not None
    report_text = structured_output_to_report_text(7, normalized)
    assert "missing" not in (repr(normalized) + report_text).lower()
    assert "nil" not in (repr(normalized) + report_text).lower()


def test_recommendation_output_uses_fallback_for_missing_recommendation_text_fields():
    payload = _recommendation_payload()
    payload["recommendation"].pop("短期目標（3個月）")
    payload["recommendation"].pop("信心指數")

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.recommendation.target_3m == "N/A"
    assert output.recommendation.target_6m == "NT$330"
    assert output.recommendation.confidence == "N/A"


def test_recommendation_output_uses_fallback_for_malformed_analysis_markdown_before_validation():
    payload = _recommendation_payload()
    payload["analysis_markdown"] = MalformedStructuredText()

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.analysis_markdown == "資料不足"


def test_recommendation_output_uses_fallback_for_missing_analysis_markdown_before_validation():
    payload = _recommendation_payload()
    payload.pop("analysis_markdown")

    output = RecommendationStructuredOutput.model_validate(payload)

    assert output.analysis_markdown == "資料不足"
    assert output.recommendation.recommendation == "持有"


def test_recommendation_output_builds_next_catalysts_from_readonly_mapping_payload():
    payload = _recommendation_payload()
    payload.pop("next_catalysts")

    output = RecommendationStructuredOutput.model_validate(_readonly(payload))

    assert len(output.next_catalysts) == 2
    assert output.next_catalysts[0].trigger_condition == "季度毛利率低於 43% 且管理層未提出改善計畫"
    assert output.next_catalysts[1].trigger_condition == "法說會正式調升全年營收與毛利率展望"


def test_recommendation_output_builds_next_catalysts_from_null_next_catalysts():
    payload = _recommendation_payload(next_catalysts=None)

    output = RecommendationStructuredOutput.model_validate(payload)

    assert len(output.next_catalysts) == 2
    assert output.next_catalysts[0].trigger_condition == "季度毛利率低於 43% 且管理層未提出改善計畫"
    assert output.next_catalysts[1].trigger_condition == "法說會正式調升全年營收與毛利率展望"


def test_recommendation_output_builds_next_catalysts_from_non_list_next_catalysts():
    payload = _recommendation_payload(next_catalysts="模型未提供催化事件清單")

    output = RecommendationStructuredOutput.model_validate(payload)

    assert len(output.next_catalysts) == 2
    assert output.next_catalysts[0].trigger_condition == "季度毛利率低於 43% 且管理層未提出改善計畫"
    assert output.next_catalysts[1].trigger_condition == "法說會正式調升全年營收與毛利率展望"


def test_recommendation_output_builds_next_catalysts_from_non_mapping_next_catalyst_rows():
    payload = _recommendation_payload(next_catalysts=["模型未提供催化事件清單"])

    output = RecommendationStructuredOutput.model_validate(payload)

    assert len(output.next_catalysts) == 2
    assert output.next_catalysts[0].trigger_condition == "季度毛利率低於 43% 且管理層未提出改善計畫"
    assert output.next_catalysts[1].trigger_condition == "法說會正式調升全年營收與毛利率展望"


def test_recommendation_output_preserves_valid_next_catalysts_from_mixed_rows():
    payload = _recommendation_payload(next_catalysts=[
        "模型未提供催化事件清單",
        {
            "event_name": "Q4 法說會",
            "expected_timeframe": "Q4 2026",
            "impact_direction": "bullish",
            "trigger_condition": "若管理層調升毛利率指引，重新評估上行情境。",
        },
    ])

    output = RecommendationStructuredOutput.model_validate(payload)

    assert len(output.next_catalysts) == 1
    assert output.next_catalysts[0].event_name == "Q4 法說會"
    assert output.next_catalysts[0].trigger_condition == "若管理層調升毛利率指引，重新評估上行情境。"


def test_recommendation_output_preserves_valid_next_catalysts_from_mixed_mapping_rows():
    payload = _recommendation_payload(next_catalysts=[
        {
            "event_name": "壞催化事件",
            "expected_timeframe": "Q4 2026",
            "impact_direction": "bullish",
            "trigger_condition": "短",
        },
        {
            "event_name": "Q4 法說會",
            "expected_timeframe": "Q4 2026",
            "impact_direction": "bullish",
            "trigger_condition": "若管理層調升毛利率指引，重新評估上行情境。",
        },
    ])

    output = RecommendationStructuredOutput.model_validate(payload)

    assert len(output.next_catalysts) == 1
    assert output.next_catalysts[0].event_name == "Q4 法說會"
    assert output.next_catalysts[0].trigger_condition == "若管理層調升毛利率指引，重新評估上行情境。"


def test_bubble_sniper_output_uses_fallback_for_malformed_root_before_validation():
    output = BubbleSniperStructuredOutput.model_validate(MalformedStructuredText())

    assert output.reasoning_steps == ["待補推論步驟", "待補推論步驟", "待補推論步驟"]
    assert output.recommendation.recommendation == "避免"
    assert output.recommendation.target_3m == "N/A"
    assert output.recommendation.target_6m == "N/A"
    assert output.recommendation.target_12m == "N/A"
    assert output.recommendation.long_term_potential_5y == "N/A"
    assert output.recommendation.confidence == "N/A"
    assert output.confidence_basis.evidence_items == ["待補具體佐證", "待補具體佐證", "待補具體佐證"]
    assert output.confidence_basis.key_risks_acknowledged == ["待補已納入風險", "待補已納入風險"]
    assert output.confidence_basis.data_gaps == []
    assert [row.trigger_condition for row in output.scenario_triggers] == [
        "待後續資料確認觸發條件",
        "待後續資料確認觸發條件",
    ]
    assert [row.action for row in output.scenario_triggers] == ["重新檢查投資結論", "重新檢查投資結論"]
    assert [row.direction for row in output.scenario_triggers] == ["neutral_review", "neutral_review"]
    assert [(row.event_name, row.impact_direction, row.trigger_condition) for row in output.next_catalysts] == [
        ("Scenario trigger 1", "volatile", "待後續資料確認觸發條件")
    ]
    assert output.analysis_markdown == "資料不足"


def test_bubble_sniper_output_uses_fallback_for_missing_recommendation_object_before_validation():
    payload = _recommendation_payload()
    payload.pop("recommendation")

    output = BubbleSniperStructuredOutput.model_validate(payload)

    assert output.recommendation.recommendation == "避免"
    assert output.recommendation.target_3m == "N/A"
    assert output.reasoning_steps == ["估值支持中性", "風險限制上行", "催化劑決定再評估"]
    assert output.confidence_basis.evidence_items == ["估值接近基本情境", "FCF 維持正值", "同業估值未明顯折價"]


def test_bubble_sniper_output_uses_fallback_for_missing_confidence_basis_object_before_validation():
    payload = _recommendation_payload()
    payload.pop("confidence_basis")

    output = BubbleSniperStructuredOutput.model_validate(payload)

    assert output.confidence_basis.evidence_items == ["待補具體佐證", "待補具體佐證", "待補具體佐證"]
    assert output.confidence_basis.key_risks_acknowledged == ["待補已納入風險", "待補已納入風險"]
    assert output.confidence_basis.data_gaps == []
    assert output.recommendation.recommendation == "持有"


def test_bubble_sniper_output_uses_fallback_for_missing_scenario_triggers_before_validation():
    payload = _recommendation_payload()
    payload.pop("scenario_triggers")

    output = BubbleSniperStructuredOutput.model_validate(payload)

    assert [row.trigger_condition for row in output.scenario_triggers] == [
        "待後續資料確認觸發條件",
        "待後續資料確認觸發條件",
    ]
    assert [row.direction for row in output.scenario_triggers] == ["neutral_review", "neutral_review"]
    assert output.next_catalysts[0].event_name == "Q3 法說會"


def test_bubble_sniper_output_derives_next_catalysts_from_missing_scenario_trigger_fallback():
    payload = _recommendation_payload()
    payload.pop("scenario_triggers")
    payload.pop("next_catalysts")

    output = BubbleSniperStructuredOutput.model_validate(payload)

    assert [row.trigger_condition for row in output.scenario_triggers] == [
        "待後續資料確認觸發條件",
        "待後續資料確認觸發條件",
    ]
    assert [(row.event_name, row.impact_direction, row.trigger_condition) for row in output.next_catalysts] == [
        ("Scenario trigger 1", "volatile", "待後續資料確認觸發條件"),
        ("Scenario trigger 2", "volatile", "待後續資料確認觸發條件"),
    ]
    assert output.analysis_markdown == "正式報告正文"


def test_bubble_sniper_recommendation_fields_uses_fallback_for_malformed_root_before_validation():
    output = BubbleSniperRecommendationFields.model_validate(MalformedStructuredText())

    assert output.recommendation == "避免"
    assert output.target_3m == "N/A"
    assert output.target_6m == "N/A"
    assert output.target_12m == "N/A"
    assert output.long_term_potential_5y == "N/A"
    assert output.confidence == "N/A"


def test_bubble_sniper_recommendation_fields_use_fallback_for_missing_label():
    output = BubbleSniperRecommendationFields.model_validate({
        "短期目標（3個月）": "NT$120",
        "中期目標（6個月）": "NT$100",
        "長期目標（12個月）": "NT$80",
        "長期潛力（5年）": "NT$60",
        "信心指數": "6/10",
    })

    assert output.recommendation == "避免"
    assert output.target_3m == "NT$120"


def test_normalize_structured_output_accepts_readonly_mapping_payloads():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    payload = _readonly({
        "reasoning_steps": ["題材過熱", "財務現實不支持", "籌碼派發"],
        "recommendation": {
            "建議": "強烈放空",
            "短期目標（3個月）": "NT$220",
            "中期目標（6個月）": "NT$190",
            "長期目標（12個月）": "NT$160",
            "長期潛力（5年）": "需重新驗證",
            "信心指數": "8/10",
        },
        "confidence_basis": {
            "evidence_items": ["P/E 河流圖高檔", "毛利率轉弱", "外資賣超"],
            "key_risks_acknowledged": ["軋空", "資料延遲"],
            "data_gaps": [],
        },
        "scenario_triggers": [
            {"trigger_condition": "財測下修幅度超過市場預期", "action": "提高空方權重", "direction": "bearish_downgrade"},
            {"trigger_condition": "股價放量突破前高且基本面改善", "action": "回補並重新評估", "direction": "neutral_review"},
        ],
        "next_catalysts": [
            {
                "event_name": "法說會",
                "expected_timeframe": "下一季",
                "impact_direction": "bearish",
                "trigger_condition": "公司財測下修",
            }
        ],
        "analysis_markdown": "## 做空觸發條件（Catalyst for crash）\n財測下修。",
    })

    normalized = normalize_structured_output(19, payload)

    assert normalized is not None
    assert normalized["recommendation"]["建議"] == "放空"
    assert normalized["recommendation"]["confidence_basis"]["evidence_items"][0] == "P/E 河流圖高檔"
    assert normalized["scenario_triggers"][0]["trigger_condition"] == "財測下修幅度超過市場預期"

    report_text = structured_output_to_report_text(19, _readonly(normalized))
    assert "建議：放空" in report_text
    assert "P/E 河流圖高檔" in report_text
    assert "財測下修幅度超過市場預期" in report_text
    assert "## 防軋空停損點（Stop-loss level）\n- 股價放量突破前高且基本面改善：回補並重新評估" in report_text
    assert "模型未提供足夠可量化停損價位" not in report_text


@pytest.mark.parametrize(
    ("agent_num", "expected_key", "expected_value"),
    [
        (3, "moat_scores", {"整體護城河": 1.0}),
        (4, "price_targets", {"基本情境": 0.0}),
        (7, "recommendation", {"建議": "持有"}),
        (20, "guidance_tone", "資料不足"),
        (21, "thesis_summary", "資料不足"),
        (24, "trade_direction", "Neutral"),
    ],
)
def test_normalize_structured_output_strict_schema_scalar_roots_use_schema_fallback_before_validation(
    agent_num,
    expected_key,
    expected_value,
):
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    normalized = normalize_structured_output(agent_num, "模型沒有提供結構化 JSON")

    assert normalized is not None
    if isinstance(expected_value, dict):
        for key, value in expected_value.items():
            assert normalized[expected_key][key] == value
    else:
        assert normalized[expected_key] == expected_value


def test_normalize_structured_output_skips_malformed_reasoning_step_text():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "reasoning_steps": ["題材過熱", MalformedStructuredText(), "籌碼派發", "停損風控明確"],
        "recommendation": {
            "建議": "強烈放空",
            "短期目標（3個月）": "NT$220",
            "中期目標（6個月）": "NT$190",
            "長期目標（12個月）": "NT$160",
            "長期潛力（5年）": "需重新驗證",
            "信心指數": "8/10",
        },
        "confidence_basis": {
            "evidence_items": ["P/E 河流圖高檔", "毛利率轉弱", "外資賣超"],
            "key_risks_acknowledged": ["軋空", "資料延遲"],
            "data_gaps": [],
        },
        "scenario_triggers": [
            {"trigger_condition": "財測下修幅度超過市場預期", "action": "提高空方權重", "direction": "bearish_downgrade"},
            {"trigger_condition": "股價放量突破前高且基本面改善", "action": "回補並重新評估", "direction": "neutral_review"},
        ],
        "next_catalysts": [
            {
                "event_name": "法說會",
                "expected_timeframe": "下一季",
                "impact_direction": "bearish",
                "trigger_condition": "公司財測下修",
            }
        ],
        "analysis_markdown": "## 做空觸發條件（Catalyst for crash）\n財測下修。",
    }

    normalized = normalize_structured_output(19, payload)

    assert normalized is not None
    assert normalized["reasoning_steps"] == ["題材過熱", "籌碼派發", "停損風控明確"]
    assert normalized["recommendation"]["建議"] == "放空"


def test_normalize_structured_output_reasoning_steps_use_minimum_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["reasoning_steps"] = ["估值支持中性", MalformedStructuredText(), "催化劑決定再評估"]

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["reasoning_steps"] == ["估值支持中性", "催化劑決定再評估", "待補推論步驟"]
    assert normalized["recommendation"]["建議"] == "持有"


def test_normalize_structured_output_empty_reasoning_steps_use_minimum_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["reasoning_steps"] = []

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["reasoning_steps"] == ["待補推論步驟", "待補推論步驟", "待補推論步驟"]
    assert normalized["recommendation"]["建議"] == "持有"
    assert normalized["next_catalysts"][0]["event_name"] == "Q3 法說會"


def test_normalize_structured_output_null_reasoning_steps_use_minimum_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["reasoning_steps"] = None

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["reasoning_steps"] == ["待補推論步驟", "待補推論步驟", "待補推論步驟"]
    assert normalized["recommendation"]["建議"] == "持有"
    assert normalized["next_catalysts"][0]["event_name"] == "Q3 法說會"


@pytest.mark.parametrize("agent_num", [3, 12])
def test_normalize_structured_output_moat_reasoning_step_scalar_objects_use_minimum_fallback_before_validation(
    agent_num,
):
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "reasoning_steps": MalformedStructuredText(),
        "moat_scores": {
            "品牌影響力": 8,
            "網路效應": 7,
            "轉換成本": 6,
            "成本優勢": 5,
            "專利技術": 4,
            "整體護城河": 7,
        },
        "analysis_markdown": "護城河正文",
    }

    normalized = normalize_structured_output(agent_num, payload)

    assert normalized is not None
    assert normalized["reasoning_steps"] == ["待補推論步驟", "待補推論步驟", "待補推論步驟"]
    assert normalized["moat_scores"]["整體護城河"] == 7.0


@pytest.mark.parametrize("agent_num", [7, 16, 19])
def test_normalize_structured_output_recommendation_reasoning_step_scalar_objects_use_minimum_fallback_before_validation(
    agent_num,
):
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["reasoning_steps"] = MalformedStructuredText()

    normalized = normalize_structured_output(agent_num, payload)

    assert normalized is not None
    assert normalized["reasoning_steps"] == ["待補推論步驟", "待補推論步驟", "待補推論步驟"]
    assert normalized["recommendation"]["建議"] == "持有"
    assert normalized["next_catalysts"][0]["event_name"] == "Q3 法說會"


def test_normalize_structured_output_reasoning_steps_ignore_non_string_literals():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    moat = normalize_structured_output(3, {
        "reasoning_steps": ["品牌證據可量化", StringifyingStructuredText(), "整體分數需保守"],
        "moat_scores": {
            "品牌影響力": 8,
            "網路效應": 7,
            "轉換成本": 6,
            "成本優勢": 5,
            "專利技術": 4,
            "整體護城河": 7,
        },
        "analysis_markdown": "護城河正文",
    })
    recommendation_payload = _recommendation_payload()
    recommendation_payload["reasoning_steps"] = [
        "估值支持中性",
        StringifyingStructuredText(),
        "催化劑決定再評估",
    ]
    recommendation = normalize_structured_output(7, recommendation_payload)

    assert moat is not None
    assert recommendation is not None
    assert moat["reasoning_steps"] == ["品牌證據可量化", "整體分數需保守", "待補推論步驟"]
    assert recommendation["reasoning_steps"] == ["估值支持中性", "催化劑決定再評估", "待補推論步驟"]
    combined = (
        repr(moat)
        + repr(recommendation)
        + structured_output_to_report_text(3, moat)
        + structured_output_to_report_text(7, recommendation)
    )
    assert "bad-body-literal" not in combined


def test_normalize_structured_output_skips_malformed_scenario_trigger_rows_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "reasoning_steps": ["題材過熱", "籌碼派發", "停損風控明確"],
        "recommendation": {
            "建議": "強烈放空",
            "短期目標（3個月）": "NT$220",
            "中期目標（6個月）": "NT$190",
            "長期目標（12個月）": "NT$160",
            "長期潛力（5年）": "需重新驗證",
            "信心指數": "8/10",
        },
        "confidence_basis": {
            "evidence_items": ["P/E 河流圖高檔", "毛利率轉弱", "外資賣超"],
            "key_risks_acknowledged": ["軋空", "資料延遲"],
            "data_gaps": [],
        },
        "scenario_triggers": [
            {"trigger_condition": "財測下修幅度超過市場預期", "action": "提高空方權重", "direction": "bearish_downgrade"},
            {"trigger_condition": MalformedStructuredText(), "action": "略過壞資料", "direction": "bearish_downgrade"},
            {"trigger_condition": "股價放量突破前高且基本面改善", "action": "回補並重新評估", "direction": "neutral_review"},
        ],
        "analysis_markdown": "## 做空觸發條件（Catalyst for crash）\n財測下修。",
    }

    normalized = normalize_structured_output(19, payload)

    assert normalized is not None
    assert [row["trigger_condition"] for row in normalized["scenario_triggers"]] == [
        "財測下修幅度超過市場預期",
        "股價放量突破前高且基本面改善",
    ]
    assert [row["trigger_condition"] for row in normalized["next_catalysts"]] == [
        "財測下修幅度超過市場預期",
        "股價放量突破前高且基本面改善",
    ]


def test_normalize_structured_output_malformed_scenario_trigger_rows_use_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "reasoning_steps": ["估值支持中性", "風險限制上行", "催化劑決定再評估"],
        "recommendation": {
            "建議": "持有",
            "短期目標（3個月）": "NT$300",
            "中期目標（6個月）": "NT$330",
            "長期目標（12個月）": "NT$350",
            "長期潛力（5年）": "NT$420",
            "信心指數": "7/10",
        },
        "confidence_basis": {
            "evidence_items": ["估值接近基本情境", "FCF 維持正值", "同業估值未明顯折價"],
            "key_risks_acknowledged": ["毛利率下滑", "需求能見度不足"],
            "data_gaps": [],
        },
        "scenario_triggers": [
            {
                "trigger_condition": "季度毛利率低於 43% 且管理層未提出改善計畫",
                "action": "重新評估風險情境",
                "direction": "bearish_downgrade",
            },
            MalformedStructuredText(),
        ],
        "analysis_markdown": "正式報告正文",
    }

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["scenario_triggers"][0]["trigger_condition"] == "季度毛利率低於 43% 且管理層未提出改善計畫"
    assert normalized["scenario_triggers"][1] == {
        "trigger_condition": "待後續資料確認觸發條件",
        "action": "重新檢查投資結論",
        "direction": "neutral_review",
    }
    assert normalized["next_catalysts"][1]["trigger_condition"] == "待後續資料確認觸發條件"


def test_normalize_structured_output_empty_scenario_trigger_lists_use_minimum_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["scenario_triggers"] = []

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["scenario_triggers"] == [
        {
            "trigger_condition": "待後續資料確認觸發條件",
            "action": "重新檢查投資結論",
            "direction": "neutral_review",
        },
        {
            "trigger_condition": "待後續資料確認觸發條件",
            "action": "重新檢查投資結論",
            "direction": "neutral_review",
        },
    ]
    assert normalized["recommendation"]["建議"] == "持有"
    assert normalized["next_catalysts"][0]["event_name"] == "Q3 法說會"


def test_normalize_structured_output_null_scenario_triggers_use_minimum_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["scenario_triggers"] = None

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["scenario_triggers"] == [
        {
            "trigger_condition": "待後續資料確認觸發條件",
            "action": "重新檢查投資結論",
            "direction": "neutral_review",
        },
        {
            "trigger_condition": "待後續資料確認觸發條件",
            "action": "重新檢查投資結論",
            "direction": "neutral_review",
        },
    ]
    assert normalized["recommendation"]["建議"] == "持有"
    assert normalized["next_catalysts"][0]["event_name"] == "Q3 法說會"


def test_normalize_structured_output_scalar_scenario_triggers_use_minimum_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["scenario_triggers"] = "模型沒有提供情境觸發清單"

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["scenario_triggers"] == [
        {
            "trigger_condition": "待後續資料確認觸發條件",
            "action": "重新檢查投資結論",
            "direction": "neutral_review",
        },
        {
            "trigger_condition": "待後續資料確認觸發條件",
            "action": "重新檢查投資結論",
            "direction": "neutral_review",
        },
    ]
    assert normalized["recommendation"]["建議"] == "持有"
    assert normalized["next_catalysts"][0]["event_name"] == "Q3 法說會"


def test_normalize_structured_output_scenario_trigger_fields_use_minimum_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "reasoning_steps": ["估值支持中性", "風險限制上行", "催化劑決定再評估"],
        "recommendation": {
            "建議": "持有",
            "短期目標（3個月）": "NT$300",
            "中期目標（6個月）": "NT$330",
            "長期目標（12個月）": "NT$350",
            "長期潛力（5年）": "NT$420",
            "信心指數": "7/10",
        },
        "confidence_basis": {
            "evidence_items": ["估值接近基本情境", "FCF 維持正值", "同業估值未明顯折價"],
            "key_risks_acknowledged": ["毛利率下滑", "需求能見度不足"],
            "data_gaps": [],
        },
        "scenario_triggers": [
            {
                "trigger_condition": "季度毛利率低於 43% 且管理層未提出改善計畫",
                "action": "重新評估風險情境",
                "direction": "bearish_downgrade",
            },
            {
                "trigger_condition": MalformedStructuredText(),
                "action": "重新檢查投資結論",
                "direction": "neutral_review",
            },
        ],
        "analysis_markdown": "正式報告正文",
    }

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["scenario_triggers"][1] == {
        "trigger_condition": "待後續資料確認觸發條件",
        "action": "重新檢查投資結論",
        "direction": "neutral_review",
    }
    assert normalized["next_catalysts"][1]["trigger_condition"] == "待後續資料確認觸發條件"


def test_normalize_structured_output_truncates_scenario_triggers_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["scenario_triggers"] = [
        {
            "trigger_condition": f"第 {idx} 個需要重新評估投資結論的具體觸發條件",
            "action": f"執行第 {idx} 個重新評估行動",
            "direction": "neutral_review",
        }
        for idx in range(1, 7)
    ]

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert len(normalized["scenario_triggers"]) == 5
    assert normalized["scenario_triggers"][-1]["trigger_condition"] == "第 5 個需要重新評估投資結論的具體觸發條件"
    assert all("第 6 個" not in row["trigger_condition"] for row in normalized["scenario_triggers"])


def test_normalize_structured_output_prefers_valid_scenario_triggers_over_fallback_rows():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["scenario_triggers"] = [MalformedStructuredText()] + [
        {
            "trigger_condition": f"第 {idx} 個有效且具體的投資結論重新評估觸發條件",
            "action": f"執行第 {idx} 個具體重新評估行動",
            "direction": "neutral_review",
        }
        for idx in range(1, 6)
    ]

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert len(normalized["scenario_triggers"]) == 5
    assert [row["trigger_condition"] for row in normalized["scenario_triggers"]] == [
        f"第 {idx} 個有效且具體的投資結論重新評估觸發條件"
        for idx in range(1, 6)
    ]


def test_normalize_structured_output_skips_short_scenario_trigger_fields_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["scenario_triggers"] = [
        {
            "trigger_condition": "短",
            "action": "查",
            "direction": "neutral_review",
        },
        {
            "trigger_condition": "季度毛利率低於 43% 且管理層未提出改善計畫",
            "action": "重新評估風險情境",
            "direction": "bearish_downgrade",
        },
        {
            "trigger_condition": "法說會正式調升全年營收與毛利率展望",
            "action": "重新評估上行情境",
            "direction": "bullish_upgrade",
        },
    ]

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert [row["trigger_condition"] for row in normalized["scenario_triggers"]] == [
        "季度毛利率低於 43% 且管理層未提出改善計畫",
        "法說會正式調升全年營收與毛利率展望",
    ]


def test_normalize_structured_output_short_scenario_trigger_fallback_uses_schema_safe_text():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["scenario_triggers"] = [
        {
            "trigger_condition": "季度毛利率低於 43% 且管理層未提出改善計畫",
            "action": "重新評估風險情境",
            "direction": "bearish_downgrade",
        },
        {
            "trigger_condition": "短",
            "action": "查",
            "direction": "neutral_review",
        },
    ]

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["scenario_triggers"][1] == {
        "trigger_condition": "待後續資料確認觸發條件",
        "action": "重新檢查投資結論",
        "direction": "neutral_review",
    }


def test_normalize_structured_output_skips_malformed_confidence_basis_items_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "reasoning_steps": ["題材過熱", "籌碼派發", "停損風控明確"],
        "recommendation": {
            "建議": "強烈放空",
            "短期目標（3個月）": "NT$220",
            "中期目標（6個月）": "NT$190",
            "長期目標（12個月）": "NT$160",
            "長期潛力（5年）": "需重新驗證",
            "信心指數": "8/10",
        },
        "confidence_basis": {
            "evidence_items": ["P/E 河流圖高檔", MalformedStructuredText(), "毛利率轉弱", "外資賣超"],
            "key_risks_acknowledged": ["軋空", MalformedStructuredText(), "資料延遲"],
            "data_gaps": [MalformedStructuredText(), "月營收細項待補"],
        },
        "scenario_triggers": [
            {"trigger_condition": "財測下修幅度超過市場預期", "action": "提高空方權重", "direction": "bearish_downgrade"},
            {"trigger_condition": "股價放量突破前高且基本面改善", "action": "回補並重新評估", "direction": "neutral_review"},
        ],
        "analysis_markdown": "## 做空觸發條件（Catalyst for crash）\n財測下修。",
    }

    normalized = normalize_structured_output(19, payload)

    assert normalized is not None
    confidence_basis = normalized["recommendation"]["confidence_basis"]
    assert confidence_basis["evidence_items"] == ["P/E 河流圖高檔", "毛利率轉弱", "外資賣超"]
    assert confidence_basis["key_risks_acknowledged"] == ["軋空", "資料延遲"]
    assert confidence_basis["data_gaps"] == ["月營收細項待補"]


def test_normalize_structured_output_confidence_basis_items_use_minimum_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "reasoning_steps": ["估值支持中性", "風險限制上行", "催化劑決定再評估"],
        "recommendation": {
            "建議": "持有",
            "短期目標（3個月）": "NT$300",
            "中期目標（6個月）": "NT$330",
            "長期目標（12個月）": "NT$350",
            "長期潛力（5年）": "NT$420",
            "信心指數": "7/10",
        },
        "confidence_basis": {
            "evidence_items": ["估值接近基本情境", MalformedStructuredText(), "FCF 維持正值"],
            "key_risks_acknowledged": ["毛利率下滑", MalformedStructuredText()],
            "data_gaps": [MalformedStructuredText(), "月營收細項待補"],
        },
        "scenario_triggers": [
            {"trigger_condition": "季度毛利率低於 43% 且管理層未提出改善計畫", "action": "重新評估風險情境", "direction": "bearish_downgrade"},
            {"trigger_condition": "法說會正式調升全年營收與毛利率展望", "action": "重新評估上行情境", "direction": "bullish_upgrade"},
        ],
        "analysis_markdown": "正式報告正文",
    }

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    confidence_basis = normalized["recommendation"]["confidence_basis"]
    assert confidence_basis["evidence_items"] == ["估值接近基本情境", "FCF 維持正值", "待補具體佐證"]
    assert confidence_basis["key_risks_acknowledged"] == ["毛利率下滑", "待補已納入風險"]
    assert confidence_basis["data_gaps"] == ["月營收細項待補"]


def test_normalize_structured_output_confidence_basis_empty_required_lists_use_minimum_fallback():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["confidence_basis"] = {
        "evidence_items": [],
        "key_risks_acknowledged": [],
        "data_gaps": [],
    }

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    confidence_basis = normalized["recommendation"]["confidence_basis"]
    assert confidence_basis["evidence_items"] == ["待補具體佐證", "待補具體佐證", "待補具體佐證"]
    assert confidence_basis["key_risks_acknowledged"] == ["待補已納入風險", "待補已納入風險"]
    assert confidence_basis["data_gaps"] == []
    assert normalized["recommendation"]["建議"] == "持有"


@pytest.mark.parametrize(
    ("agent_num", "field", "bad_value", "expected_evidence", "expected_risks"),
    [
        (
            7,
            "evidence_items",
            _DEFAULT,
            ["待補具體佐證", "待補具體佐證", "待補具體佐證"],
            ["毛利率下滑", "需求能見度不足"],
        ),
        (
            7,
            "evidence_items",
            None,
            ["待補具體佐證", "待補具體佐證", "待補具體佐證"],
            ["毛利率下滑", "需求能見度不足"],
        ),
        (
            7,
            "evidence_items",
            "模型只給一句信心依據",
            ["待補具體佐證", "待補具體佐證", "待補具體佐證"],
            ["毛利率下滑", "需求能見度不足"],
        ),
        (
            19,
            "key_risks_acknowledged",
            _DEFAULT,
            ["估值接近基本情境", "FCF 維持正值", "同業估值未明顯折價"],
            ["待補已納入風險", "待補已納入風險"],
        ),
        (
            19,
            "key_risks_acknowledged",
            None,
            ["估值接近基本情境", "FCF 維持正值", "同業估值未明顯折價"],
            ["待補已納入風險", "待補已納入風險"],
        ),
        (
            19,
            "key_risks_acknowledged",
            "模型只給一句風險提示",
            ["估值接近基本情境", "FCF 維持正值", "同業估值未明顯折價"],
            ["待補已納入風險", "待補已納入風險"],
        ),
    ],
)
def test_normalize_structured_output_confidence_basis_non_list_required_collections_use_minimum_fallback(
    agent_num,
    field,
    bad_value,
    expected_evidence,
    expected_risks,
):
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    if bad_value is _DEFAULT:
        payload["confidence_basis"].pop(field)
    else:
        payload["confidence_basis"][field] = bad_value

    normalized = normalize_structured_output(agent_num, payload)

    assert normalized is not None
    confidence_basis = normalized["recommendation"]["confidence_basis"]
    assert confidence_basis["evidence_items"] == expected_evidence
    assert confidence_basis["key_risks_acknowledged"] == expected_risks
    assert confidence_basis["data_gaps"] == []


def test_normalize_structured_output_recommendation_fields_use_safe_text_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["recommendation"] = {
        **payload["recommendation"],
        "短期目標（3個月）": MalformedStructuredText(),
    }

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["recommendation"]["建議"] == "持有"
    assert normalized["recommendation"]["短期目標（3個月）"] == "N/A"
    assert normalized["recommendation"]["中期目標（6個月）"] == "NT$330"


@pytest.mark.parametrize(
    ("agent_num", "expected_label"),
    [
        (7, "持有"),
        (19, "避免"),
    ],
)
def test_normalize_structured_output_recommendation_keys_and_labels_ignore_non_string_literals(
    agent_num,
    expected_label,
):
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["recommendation"] = {
        **payload["recommendation"],
        StringifyingRecommendationKey(): "買入",
        "建議": StringifyingBuyLabel(),
        "recommendation": StringifyingBuyLabel(),
        StringifyingRecommendationTargetKey(): "NT$999",
    }

    normalized = normalize_structured_output(agent_num, payload)

    assert normalized is not None
    assert normalized["recommendation"]["建議"] == expected_label
    assert normalized["recommendation"]["短期目標（3個月）"] == "NT$300"
    assert "bad-body-literal" not in repr(normalized)


@pytest.mark.parametrize(
    ("agent_num", "expected_label"),
    [
        (7, "持有"),
        (19, "避免"),
    ],
)
@pytest.mark.parametrize("label_key", ["建議", "recommendation"])
def test_normalize_structured_output_recommendation_label_fallback_matches_agent_bias_before_validation(
    agent_num,
    expected_label,
    label_key,
):
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload()
    payload["recommendation"] = {**payload["recommendation"]}
    payload["recommendation"].pop("建議", None)
    payload["recommendation"][label_key] = MalformedStructuredText()

    normalized = normalize_structured_output(agent_num, payload)

    assert normalized is not None
    assert normalized["recommendation"]["建議"] == expected_label


def test_normalize_structured_output_next_catalyst_fields_use_safe_text_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload(next_catalysts=[
        {
            "event_name": MalformedStructuredText(),
            "expected_timeframe": "Q4 2026",
            "impact_direction": "bullish",
            "trigger_condition": "若管理層調升毛利率指引，重新評估上行情境。",
        },
    ])

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["next_catalysts"][0]["event_name"] == "待確認催化事件"
    assert normalized["next_catalysts"][0]["expected_timeframe"] == "Q4 2026"
    assert normalized["next_catalysts"][0]["trigger_condition"] == "若管理層調升毛利率指引，重新評估上行情境。"


def test_normalize_structured_output_recommendation_tail_fields_ignore_non_string_literals():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    payload = _recommendation_payload(next_catalysts=[
        {
            "event_name": StringifyingStructuredText(),
            "expected_timeframe": StringifyingStructuredText(),
            "impact_direction": StringifyingStructuredText(),
            "trigger_condition": StringifyingStructuredText(),
        },
    ])
    payload["scenario_triggers"] = [
        {
            "trigger_condition": StringifyingStructuredText(),
            "action": StringifyingStructuredText(),
            "direction": StringifyingStructuredText(),
        },
        {
            "trigger_condition": "法說會正式調升全年營收與毛利率展望",
            "action": "重新評估上行情境",
            "direction": "bullish_upgrade",
        },
    ]

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["scenario_triggers"] == [
        {
            "trigger_condition": "法說會正式調升全年營收與毛利率展望",
            "action": "重新評估上行情境",
            "direction": "bullish_upgrade",
        },
        {
            "trigger_condition": "待後續資料確認觸發條件",
            "action": "重新檢查投資結論",
            "direction": "neutral_review",
        },
    ]
    assert normalized["next_catalysts"] == [
        {
            "event_name": "待確認催化事件",
            "expected_timeframe": "待後續資料確認",
            "impact_direction": "volatile",
            "trigger_condition": "待後續資料確認",
        }
    ]
    report_text = structured_output_to_report_text(7, normalized)
    assert "法說會正式調升全年營收與毛利率展望" in report_text
    assert "bad-body-literal" not in (repr(normalized) + report_text)


def test_normalize_structured_output_next_catalyst_rows_use_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload(next_catalysts=[MalformedStructuredText()])

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["next_catalysts"] == [
        {
            "event_name": "待確認催化事件",
            "expected_timeframe": "待後續資料確認",
            "impact_direction": "volatile",
            "trigger_condition": "待後續資料確認",
        }
    ]
    assert normalized["recommendation"]["建議"] == "持有"


def test_normalize_structured_output_empty_next_catalyst_lists_derive_from_scenario_triggers_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload(next_catalysts=[])

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert [(row["event_name"], row["impact_direction"], row["trigger_condition"]) for row in normalized["next_catalysts"]] == [
        (
            "Scenario trigger 1",
            "bearish",
            "季度毛利率低於 43% 且管理層未提出改善計畫",
        ),
        (
            "Scenario trigger 2",
            "bullish",
            "法說會正式調升全年營收與毛利率展望",
        ),
    ]
    assert normalized["recommendation"]["建議"] == "持有"


def test_normalize_structured_output_empty_next_catalysts_derive_from_missing_scenario_trigger_fallback():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload(next_catalysts=[])
    payload.pop("scenario_triggers")

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["scenario_triggers"] == [
        {
            "trigger_condition": "待後續資料確認觸發條件",
            "action": "重新檢查投資結論",
            "direction": "neutral_review",
        },
        {
            "trigger_condition": "待後續資料確認觸發條件",
            "action": "重新檢查投資結論",
            "direction": "neutral_review",
        },
    ]
    assert [(row["event_name"], row["impact_direction"], row["trigger_condition"]) for row in normalized["next_catalysts"]] == [
        ("Scenario trigger 1", "volatile", "待後續資料確認觸發條件"),
        ("Scenario trigger 2", "volatile", "待後續資料確認觸發條件"),
    ]
    assert normalized["recommendation"]["建議"] == "持有"


def test_normalize_structured_output_prefers_valid_next_catalysts_over_fallback_rows():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload(next_catalysts=[
        MalformedStructuredText(),
        {
            "event_name": "Q4 法說會",
            "expected_timeframe": "Q4 2026",
            "impact_direction": "bullish",
            "trigger_condition": "若管理層調升全年毛利率指引，重新評估上行情境。",
        },
        {
            "event_name": "月營收公布",
            "expected_timeframe": "下個月",
            "impact_direction": "volatile",
            "trigger_condition": "若月營收連續兩月低於同業均值，重新檢查需求風險。",
        },
    ])

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert [row["event_name"] for row in normalized["next_catalysts"]] == ["Q4 法說會", "月營收公布"]
    assert all(row["event_name"] != "待確認催化事件" for row in normalized["next_catalysts"])


def test_normalize_structured_output_skips_short_next_catalyst_triggers_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload(next_catalysts=[
        {
            "event_name": "短觸發事件",
            "expected_timeframe": "Q4 2026",
            "impact_direction": "bullish",
            "trigger_condition": "短",
        },
        {
            "event_name": "月營收公布",
            "expected_timeframe": "下個月",
            "impact_direction": "volatile",
            "trigger_condition": "若月營收連續兩月低於同業均值，重新檢查需求風險。",
        },
    ])

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert [row["event_name"] for row in normalized["next_catalysts"]] == ["月營收公布"]


def test_normalize_structured_output_short_next_catalyst_fallback_uses_schema_safe_trigger():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = _recommendation_payload(next_catalysts=[
        {
            "event_name": "短觸發事件",
            "expected_timeframe": "Q4 2026",
            "impact_direction": "bullish",
            "trigger_condition": "短",
        },
    ])

    normalized = normalize_structured_output(7, payload)

    assert normalized is not None
    assert normalized["next_catalysts"] == [
        {
            "event_name": "短觸發事件",
            "expected_timeframe": "Q4 2026",
            "impact_direction": "bullish",
            "trigger_condition": "待後續資料確認",
        }
    ]


def test_normalize_structured_output_skips_boolean_price_targets():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    payload = {
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": True,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": "估值正文",
    }

    normalized = normalize_structured_output(4, payload)

    assert normalized is not None
    assert normalized["price_targets"] == {"熊市情境": 90.0, "牛市情境": 150.0}
    report_text = structured_output_to_report_text(4, normalized)
    assert "基本情境: NT$1" not in report_text


def test_normalize_structured_output_skips_malformed_price_targets_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": MalformedStructuredNumber(),
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": "估值正文",
    }

    normalized = normalize_structured_output(4, payload)

    assert normalized is not None
    assert normalized["price_targets"] == {"基本情境": 120.0, "牛市情境": 150.0}
    assert normalized["valuation_reasoning"]["dcf_reasoning"] == "DCF 假設完整"


def test_normalize_structured_output_price_target_aliases_ignore_non_string_equal_keys_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            EqualToBaseCaseKey(): 120,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": "估值正文",
    }

    normalized = normalize_structured_output(4, payload)

    assert normalized is not None
    assert normalized["price_targets"] == {"熊市情境": 0.0, "基本情境": 0.0, "牛市情境": 0.0}


def test_normalize_structured_output_numeric_fields_ignore_non_primitive_number_literals():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": FloatingStructuredNumber(),
            "基本情境": "120",
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "dcf_scenarios": [
            {
                "scenario": "base",
                "revenue_growth_bias_pct": FloatingStructuredNumber(),
                "margin_bias_pct": "1.5",
                "wacc_pct": FloatingStructuredNumber(),
                "intrinsic_value": 120,
            }
        ],
        "analysis_markdown": "估值正文",
    }

    normalized = normalize_structured_output(4, payload)

    assert normalized is not None
    assert normalized["price_targets"] == {"基本情境": 120.0, "牛市情境": 150.0}
    assert normalized["dcf_scenarios"] == [
        {
            "scenario": "base",
            "revenue_growth_bias_pct": 0.0,
            "margin_bias_pct": 1.5,
            "wacc_pct": 1.0,
            "intrinsic_value": 120.0,
        }
    ]


def test_normalize_structured_output_missing_price_targets_use_schema_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    payload = {
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": False,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": "估值正文",
    }

    normalized = normalize_structured_output(4, payload)

    assert normalized is not None
    assert normalized["price_targets"] == {"熊市情境": 0.0, "基本情境": 0.0, "牛市情境": 0.0}
    assert normalized["valuation_reasoning"] == {
        "dcf_reasoning": "資料不足",
        "peer_reasoning": "資料不足",
        "scenario_reasoning": "資料不足",
    }
    assert normalized["valuation_summary"]["double_counting_check"] == "未重複計算成長與多重評價。"
    assert normalized["analysis_markdown"] == "估值正文"
    report_text = structured_output_to_report_text(4, normalized)
    assert "基本情境: NT$0" in report_text


def test_normalize_structured_output_valuation_summary_uses_safe_text_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": MalformedStructuredText(),
        },
        "analysis_markdown": "估值正文",
    }

    normalized = normalize_structured_output(4, payload)

    assert normalized is not None
    assert normalized["valuation_summary"]["double_counting_check"] == "資料不足"
    assert normalized["price_targets"] == {"熊市情境": 90.0, "基本情境": 120.0, "牛市情境": 150.0}


def test_normalize_structured_output_boolean_fields_ignore_numeric_literals_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": 1,
            "uses_normalized_fcf": "yes",
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": "估值正文",
    }

    normalized = normalize_structured_output(4, payload)

    assert normalized is not None
    assert normalized["valuation_summary"]["uses_market_value_wacc"] is False
    assert normalized["valuation_summary"]["uses_normalized_fcf"] is True


def test_normalize_structured_output_valuation_display_fields_ignore_non_string_literals():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    payload = {
        "price_targets": {
            "dcf_reasoning": StringifyingStructuredText(),
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": StringifyingStructuredText(),
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": StringifyingStructuredText(),
        },
        "analysis_markdown": "估值正文",
    }

    normalized = normalize_structured_output(4, payload)

    assert normalized is not None
    assert normalized["valuation_reasoning"]["dcf_reasoning"] == "資料不足"
    assert normalized["valuation_reasoning"]["peer_reasoning"] == "同業比較完整"
    assert normalized["valuation_reasoning"]["scenario_reasoning"] == "資料不足"
    assert normalized["valuation_summary"]["double_counting_check"] == "資料不足"
    report_text = structured_output_to_report_text(4, normalized)
    assert "同業比較完整" in report_text
    assert "bad-body-literal" not in (repr(normalized) + report_text)


def test_normalize_structured_output_valuation_summary_booleans_use_safe_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": MalformedStructuredText(),
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": "估值正文",
    }

    normalized = normalize_structured_output(4, payload)

    assert normalized is not None
    assert normalized["valuation_summary"]["uses_market_value_wacc"] is False
    assert normalized["valuation_summary"]["uses_normalized_fcf"] is True
    assert normalized["price_targets"]["基本情境"] == 120.0


def test_normalize_structured_output_dcf_scenarios_use_safe_number_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "dcf_scenarios": [
            {
                "scenario": "base",
                "revenue_growth_bias_pct": 2.5,
                "margin_bias_pct": 1.0,
                "wacc_pct": 9.5,
                "intrinsic_value": 120,
            },
            {
                "scenario": "bull",
                "revenue_growth_bias_pct": MalformedStructuredNumber(),
                "margin_bias_pct": 3.0,
                "wacc_pct": 8.5,
                "intrinsic_value": 150,
            },
        ],
        "analysis_markdown": "估值正文",
    }

    normalized = normalize_structured_output(4, payload)

    assert normalized is not None
    assert normalized["dcf_scenarios"] == [
        {
            "scenario": "base",
            "revenue_growth_bias_pct": 2.5,
            "margin_bias_pct": 1.0,
            "wacc_pct": 9.5,
            "intrinsic_value": 120.0,
        },
        {
            "scenario": "bull",
            "revenue_growth_bias_pct": 0.0,
            "margin_bias_pct": 3.0,
            "wacc_pct": 8.5,
            "intrinsic_value": 150.0,
        }
    ]
    assert normalized["price_targets"]["基本情境"] == 120.0


def test_normalize_structured_output_skips_boolean_moat_scores():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    payload = {
        "reasoning_steps": ["品牌證據可量化", "技術優勢仍需折價", "整體分數需排除旗標值"],
        "moat_scores": {
            "品牌影響力": 8,
            "網路效應": 7,
            "轉換成本": 6,
            "成本優勢": 5,
            "專利技術": 4,
            "整體護城河": True,
        },
        "analysis_markdown": "護城河正文",
    }

    normalized = normalize_structured_output(3, payload)

    assert normalized is not None
    assert normalized["moat_scores"]["品牌影響力"] == 8.0
    assert "整體護城河" not in normalized["moat_scores"]
    report_text = structured_output_to_report_text(3, normalized)
    assert "品牌影響力: 8.0" in report_text
    assert "整體護城河: 1.0" not in report_text


def test_normalize_structured_output_skips_malformed_moat_scores_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "reasoning_steps": ["品牌證據可量化", "技術優勢仍需折價", "整體分數需保留有效項"],
        "moat_scores": {
            "品牌影響力": 8,
            "網路效應": MalformedStructuredNumber(),
            "轉換成本": 6,
            "成本優勢": 5,
            "專利技術": 4,
            "整體護城河": 7,
        },
        "analysis_markdown": "護城河正文",
    }

    normalized = normalize_structured_output(3, payload)

    assert normalized is not None
    assert normalized["moat_scores"]["品牌影響力"] == 8.0
    assert "網路效應" not in normalized["moat_scores"]
    assert normalized["moat_scores"]["整體護城河"] == 7.0


def test_normalize_structured_output_missing_moat_scores_use_schema_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    payload = {
        "reasoning_steps": ["品牌證據待補", "技術證據待補", "整體分數採保守 fallback"],
        "analysis_markdown": "護城河正文",
    }

    normalized = normalize_structured_output(3, payload)

    assert normalized is not None
    assert normalized["reasoning_steps"] == ["品牌證據待補", "技術證據待補", "整體分數採保守 fallback"]
    assert normalized["moat_scores"] == {
        "品牌影響力": 1.0,
        "網路效應": 1.0,
        "轉換成本": 1.0,
        "成本優勢": 1.0,
        "專利技術": 1.0,
        "整體護城河": 1.0,
    }
    assert normalized["analysis_markdown"] == "護城河正文"
    report_text = structured_output_to_report_text(3, normalized)
    assert "整體護城河: 1" in report_text


def test_normalize_structured_output_moat_analysis_markdown_uses_safe_text_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "reasoning_steps": ["品牌證據可量化", "技術優勢仍需折價", "整體分數需保留"],
        "moat_scores": {
            "品牌影響力": 8,
            "網路效應": 7,
            "轉換成本": 6,
            "成本優勢": 5,
            "專利技術": 4,
            "整體護城河": 6,
        },
        "analysis_markdown": MalformedStructuredText(),
    }

    normalized = normalize_structured_output(3, payload)

    assert normalized is not None
    assert normalized["moat_scores"]["品牌影響力"] == 8.0
    assert normalized["analysis_markdown"] == "資料不足"


def test_normalize_structured_output_analysis_markdown_ignores_non_string_literals():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    cases = [
        (
            3,
            {
                "reasoning_steps": ["品牌證據可量化", "技術優勢仍需折價", "整體分數需保留"],
                "moat_scores": {
                    "品牌影響力": 8,
                    "網路效應": 7,
                    "轉換成本": 6,
                    "成本優勢": 5,
                    "專利技術": 4,
                    "整體護城河": 6,
                },
            },
        ),
        (
            4,
            {
                "price_targets": {
                    "基本情境": 120,
                },
                "valuation_summary": {
                    "primary_method": "blended",
                    "uses_market_value_wacc": True,
                    "uses_normalized_fcf": True,
                    "double_counting_check": "未重複計算成長與多重評價。",
                },
            },
        ),
        (7, {"recommendation": {"建議": "持有"}}),
        (
            20,
            {
                "guidance_tone": "中立",
                "highlights": [{"keyword": "訂單", "quote": "AI 訂單恢復成長"}],
            },
        ),
        (
            21,
            {
                "thesis_summary": "空方風險仍需驗證",
                "downside_risks": [{"title": "需求風險", "evidence": "庫存去化慢於預期"}],
            },
        ),
        (
            24,
            {
                "trade_direction": "Long",
                "entry_zone": "NT$100-105",
                "target_price": "NT$112",
                "stop_loss": "NT$96",
                "core_catalyst": "法說會調升指引",
                "risk_level": "Medium",
            },
        ),
    ]

    for agent_num, payload in cases:
        normalized = normalize_structured_output(agent_num, {
            **payload,
            "analysis_markdown": StringifyingStructuredText(),
        })

        assert normalized is not None
        assert normalized["analysis_markdown"] == "資料不足"


def test_normalize_structured_output_display_fields_ignore_non_string_literals():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    downside = normalize_structured_output(21, {
        "thesis_summary": StringifyingStructuredText(),
        "downside_risks": [{"title": "需求風險", "evidence": "庫存去化慢於預期"}],
        "analysis_markdown": "空方正文",
    })
    recommendation = normalize_structured_output(7, {
        "recommendation": {
            "建議": "持有",
            "短期目標（3個月）": StringifyingStructuredText(),
            "中期目標（6個月）": "NT$330",
        },
        "analysis_markdown": "正式報告正文",
    })
    trade = normalize_structured_output(24, {
        "trade_direction": "Long",
        "entry_zone": StringifyingStructuredText(),
        "target_price": "NT$112",
        "stop_loss": "NT$96",
        "core_catalyst": StringifyingStructuredText(),
        "risk_level": "Medium",
        "analysis_markdown": "短線交易正文",
    })

    assert downside is not None
    assert recommendation is not None
    assert trade is not None
    assert downside["thesis_summary"] == "資料不足"
    assert recommendation["recommendation"]["短期目標（3個月）"] == "N/A"
    assert recommendation["recommendation"]["中期目標（6個月）"] == "NT$330"
    assert trade["entry_zone"] == "N/A"
    assert trade["core_catalyst"] == "N/A"
    combined = (
        structured_output_to_report_text(21, downside)
        + structured_output_to_report_text(7, recommendation)
        + structured_output_to_report_text(24, trade)
    )
    assert "bad-body-literal" not in combined


def test_normalize_structured_output_nested_display_rows_ignore_non_string_literals():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    management = normalize_structured_output(20, {
        "guidance_tone": "中立",
        "confidence": 0.4,
        "highlights": [
            {"keyword": StringifyingStructuredText(), "quote": "有效引述"},
            {"keyword": "有效亮點", "quote": StringifyingStructuredText()},
        ],
        "analysis_markdown": "管理層正文",
    })
    downside = normalize_structured_output(21, {
        "thesis_summary": "空方風險仍需驗證",
        "downside_risks": [
            {
                "title": StringifyingStructuredText(),
                "evidence": "有效證據",
                "impact": StringifyingStructuredText(),
                "severity": StringifyingStructuredText(),
                "confidence": 0.8,
            },
            {
                "title": "有效風險",
                "evidence": StringifyingStructuredText(),
                "impact": "有效影響",
                "severity": "high",
                "confidence": 0.6,
            },
            {
                "title": "保留風險",
                "evidence": "保留證據",
                "impact": "保留影響",
                "severity": "critical",
                "confidence": 0.4,
            },
        ],
        "analysis_markdown": "空方正文",
    })

    assert management is not None
    assert downside is not None
    assert management["highlights"][0]["keyword"] == "亮點"
    assert management["highlights"][1]["quote"] == "資料不足"
    assert downside["downside_risks"][0]["title"] == "保留風險"
    assert downside["downside_risks"][0]["evidence"] == "保留證據"
    assert downside["downside_risks"][1]["title"] == "下行風險"
    assert downside["downside_risks"][1]["evidence"] == "有效證據"
    assert downside["downside_risks"][1]["impact"] == ""
    assert downside["downside_risks"][1]["severity"] == "warning"
    assert downside["downside_risks"][2]["title"] == "有效風險"
    assert downside["downside_risks"][2]["evidence"] == "資料不足"
    combined = (
        repr(management)
        + repr(downside)
        + structured_output_to_report_text(20, management)
        + structured_output_to_report_text(21, downside)
    )
    assert "bad-body-literal" not in combined


def test_normalize_structured_output_skips_boolean_management_confidence():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    payload = {
        "guidance_tone": "樂觀",
        "confidence": True,
        "highlights": [
            {"keyword": "需求回溫", "quote": "AI 訂單恢復成長"},
            {"keyword": "毛利率", "quote": "管理層維持全年展望"},
            {"keyword": "資本支出", "quote": "供應鏈投資保持紀律"},
        ],
        "analysis_markdown": "管理層正文",
    }

    normalized = normalize_structured_output(20, payload)

    assert normalized is not None
    assert normalized["confidence"] == 0.0
    report_text = structured_output_to_report_text(20, normalized)
    assert "## 管理層語氣：樂觀" in report_text


def test_normalize_structured_output_skips_malformed_management_confidence_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "guidance_tone": "中立",
        "confidence": MalformedStructuredNumber(),
        "highlights": [
            {"keyword": "需求回溫", "quote": "AI 訂單恢復成長"},
            {"keyword": "毛利率", "quote": "管理層維持全年展望"},
            {"keyword": "資本支出", "quote": "供應鏈投資保持紀律"},
        ],
        "analysis_markdown": "管理層正文",
    }

    normalized = normalize_structured_output(20, payload)

    assert normalized is not None
    assert normalized["guidance_tone"] == "中立"
    assert normalized["confidence"] == 0.0
    assert normalized["highlights"][0]["keyword"] == "需求回溫"


def test_normalize_structured_output_agent20_uses_safe_text_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "guidance_tone": MalformedStructuredText(),
        "confidence": 0.4,
        "highlights": [
            {"keyword": "需求回溫", "quote": "AI 訂單恢復成長"},
            {"keyword": MalformedStructuredText(), "quote": "管理層維持全年展望"},
            {"keyword": "資本支出", "quote": MalformedStructuredText()},
        ],
        "analysis_markdown": "管理層正文",
    }

    normalized = normalize_structured_output(20, payload)

    assert normalized is not None
    assert normalized["guidance_tone"] == "資料不足"
    assert normalized["highlights"][1]["keyword"] == "亮點"
    assert normalized["highlights"][2]["quote"] == "資料不足"


def test_normalize_structured_output_agent20_malformed_highlight_rows_use_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "guidance_tone": "樂觀",
        "confidence": 0.4,
        "highlights": [
            {"keyword": "需求回溫", "quote": "AI 訂單恢復成長"},
            MalformedStructuredText(),
            {"keyword": "資本支出", "quote": "供應鏈投資保持紀律"},
        ],
        "analysis_markdown": "管理層正文",
    }

    normalized = normalize_structured_output(20, payload)

    assert normalized is not None
    assert normalized["highlights"][0]["keyword"] == "需求回溫"
    assert normalized["highlights"][1]["quote"] == "供應鏈投資保持紀律"
    assert normalized["highlights"][2] == {"keyword": "亮點", "quote": "資料不足"}


def test_normalize_structured_output_agent20_missing_highlights_use_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "guidance_tone": "樂觀",
        "confidence": 0.4,
        "analysis_markdown": "管理層正文",
    }

    normalized = normalize_structured_output(20, payload)

    assert normalized is not None
    assert normalized["guidance_tone"] == "樂觀"
    assert normalized["confidence"] == 0.4
    assert normalized["highlights"] == [
        {"keyword": "亮點", "quote": "資料不足"},
        {"keyword": "亮點", "quote": "資料不足"},
        {"keyword": "亮點", "quote": "資料不足"},
    ]
    assert normalized["analysis_markdown"] == "管理層正文"


def test_normalize_structured_output_agent20_empty_highlights_use_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "guidance_tone": "樂觀",
        "confidence": 0.4,
        "highlights": [],
        "analysis_markdown": "管理層正文",
    }

    normalized = normalize_structured_output(20, payload)

    assert normalized is not None
    assert normalized["guidance_tone"] == "樂觀"
    assert normalized["confidence"] == 0.4
    assert normalized["highlights"] == [
        {"keyword": "亮點", "quote": "資料不足"},
        {"keyword": "亮點", "quote": "資料不足"},
        {"keyword": "亮點", "quote": "資料不足"},
    ]
    assert normalized["analysis_markdown"] == "管理層正文"


def test_normalize_structured_output_agent20_prefers_valid_highlights_over_fallback_rows():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "guidance_tone": "樂觀",
        "confidence": 0.4,
        "highlights": [
            MalformedStructuredText(),
            {"keyword": "需求回溫", "quote": "AI 訂單恢復成長"},
            {"keyword": "毛利率", "quote": "管理層維持全年展望"},
            {"keyword": "資本支出", "quote": "供應鏈投資保持紀律"},
        ],
        "analysis_markdown": "管理層正文",
    }

    normalized = normalize_structured_output(20, payload)

    assert normalized is not None
    assert normalized["highlights"] == [
        {"keyword": "需求回溫", "quote": "AI 訂單恢復成長"},
        {"keyword": "毛利率", "quote": "管理層維持全年展望"},
        {"keyword": "資本支出", "quote": "供應鏈投資保持紀律"},
    ]


def test_normalize_structured_output_skips_boolean_downside_risk_confidence():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    payload = {
        "thesis_summary": "下行風險仍需折價。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值倍數下修",
                "severity": "high",
                "confidence": True,
            },
            {
                "title": "現金流轉弱",
                "evidence": "營運資金需求上升使 FCF 轉換率下滑。",
                "impact": "DCF 折價",
                "severity": "warning",
                "confidence": 0.6,
            },
            {
                "title": "客戶集中",
                "evidence": "主要客戶拉貨節奏可能放大營收波動。",
                "impact": "營收能見度下降",
                "severity": "warning",
                "confidence": 0.5,
            },
        ],
        "analysis_markdown": "空方正文",
    }

    normalized = normalize_structured_output(21, payload)

    assert normalized is not None
    assert normalized["downside_risks"][0]["confidence"] == 0.7
    assert normalized["downside_risks"][1]["confidence"] == 0.6
    report_text = structured_output_to_report_text(21, normalized)
    assert "毛利率壓力" in report_text


def test_normalize_structured_output_skips_malformed_downside_risk_confidence_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "thesis_summary": "下行風險仍需折價。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值倍數下修",
                "severity": "high",
                "confidence": MalformedStructuredNumber(),
            },
            {
                "title": "現金流轉弱",
                "evidence": "營運資金需求上升使 FCF 轉換率下滑。",
                "impact": "DCF 折價",
                "severity": "warning",
                "confidence": 0.6,
            },
            {
                "title": "客戶集中",
                "evidence": "主要客戶拉貨節奏可能放大營收波動。",
                "impact": "營收能見度下降",
                "severity": "warning",
                "confidence": 0.5,
            },
        ],
        "analysis_markdown": "空方正文",
    }

    normalized = normalize_structured_output(21, payload)

    assert normalized is not None
    assert normalized["downside_risks"][0]["confidence"] == 0.7
    assert normalized["downside_risks"][1]["confidence"] == 0.6
    assert normalized["downside_risks"][0]["title"] == "毛利率壓力"


def test_normalize_structured_output_preserves_zero_downside_risk_confidence():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "thesis_summary": "低信心風險不應被升級。",
        "downside_risks": [
            {
                "title": "早期風險訊號",
                "evidence": "只有單一領先指標轉弱，尚無交叉驗證。",
                "impact": "僅列為觀察",
                "severity": "warning",
                "confidence": 0.0,
            },
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值倍數下修",
                "severity": "high",
                "confidence": 0.6,
            },
            {
                "title": "客戶集中",
                "evidence": "主要客戶拉貨節奏可能放大營收波動。",
                "impact": "營收能見度下降",
                "severity": "warning",
                "confidence": 0.5,
            },
        ],
        "analysis_markdown": "空方正文",
    }

    normalized = normalize_structured_output(21, payload)

    assert normalized is not None
    assert normalized["downside_risks"][0]["confidence"] == 0.0


def test_normalize_structured_output_agent21_uses_safe_text_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "thesis_summary": "下行風險仍需保留有效列。",
        "downside_risks": [
            {
                "title": MalformedStructuredText(),
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": MalformedStructuredText(),
                "severity": MalformedStructuredText(),
                "confidence": 0.8,
            },
            {
                "title": "現金流轉弱",
                "evidence": MalformedStructuredText(),
                "impact": "DCF 折價",
                "severity": "high",
                "confidence": 0.6,
            },
            {
                "title": "客戶集中",
                "evidence": "主要客戶拉貨節奏可能放大營收波動。",
                "impact": "營收能見度下降",
                "severity": "warning",
                "confidence": 0.5,
            },
        ],
        "analysis_markdown": "空方正文",
    }

    normalized = normalize_structured_output(21, payload)

    assert normalized is not None
    assert normalized["downside_risks"][0]["title"] == "客戶集中"
    assert normalized["downside_risks"][0]["confidence"] == 0.5
    assert normalized["downside_risks"][1]["title"] == "下行風險"
    assert normalized["downside_risks"][1]["severity"] == "warning"
    assert normalized["downside_risks"][1]["confidence"] == 0.8
    assert normalized["downside_risks"][2]["evidence"] == "資料不足"
    assert normalized["downside_risks"][2]["confidence"] == 0.6


def test_normalize_structured_output_agent21_malformed_downside_risk_rows_use_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "thesis_summary": "壞列不應讓下行風險整包失效。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值倍數下修",
                "severity": "high",
                "confidence": 0.8,
            },
            MalformedStructuredText(),
            {
                "title": "現金流轉弱",
                "evidence": "營運資金需求上升使 FCF 轉換率下滑。",
                "impact": "DCF 折價",
                "severity": "warning",
                "confidence": 0.4,
            },
        ],
        "analysis_markdown": "空方正文",
    }

    normalized = normalize_structured_output(21, payload)

    assert normalized is not None
    assert normalized["downside_risks"][0]["title"] == "毛利率壓力"
    assert normalized["downside_risks"][1]["title"] == "現金流轉弱"
    assert normalized["downside_risks"][1]["confidence"] == 0.4
    assert normalized["downside_risks"][2]["title"] == "下行風險"
    assert normalized["downside_risks"][2]["evidence"] == "資料不足"
    assert normalized["downside_risks"][2]["severity"] == "warning"
    assert normalized["downside_risks"][2]["confidence"] == 0.7


def test_normalize_structured_output_agent21_missing_downside_risks_use_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "thesis_summary": "下行風險仍需折價。",
        "analysis_markdown": "空方正文",
    }

    normalized = normalize_structured_output(21, payload)

    assert normalized is not None
    assert normalized["thesis_summary"] == "下行風險仍需折價。"
    assert [
        (risk["title"], risk["evidence"], risk["impact"], risk["severity"], risk["confidence"])
        for risk in normalized["downside_risks"]
    ] == [
        ("下行風險", "資料不足", "", "warning", 0.7),
        ("下行風險", "資料不足", "", "warning", 0.7),
        ("下行風險", "資料不足", "", "warning", 0.7),
    ]
    assert normalized["analysis_markdown"] == "空方正文"


def test_normalize_structured_output_agent21_empty_downside_risks_use_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "thesis_summary": "下行風險仍需折價。",
        "downside_risks": [],
        "analysis_markdown": "空方正文",
    }

    normalized = normalize_structured_output(21, payload)

    assert normalized is not None
    assert normalized["thesis_summary"] == "下行風險仍需折價。"
    assert [
        (risk["title"], risk["evidence"], risk["impact"], risk["severity"], risk["confidence"])
        for risk in normalized["downside_risks"]
    ] == [
        ("下行風險", "資料不足", "", "warning", 0.7),
        ("下行風險", "資料不足", "", "warning", 0.7),
        ("下行風險", "資料不足", "", "warning", 0.7),
    ]
    assert normalized["analysis_markdown"] == "空方正文"


def test_normalize_structured_output_agent21_prefers_valid_downside_risks_over_fallback_rows():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "thesis_summary": "有效下行風險不應被 placeholder 擠掉。",
        "downside_risks": [MalformedStructuredText()] + [
            {
                "title": f"有效風險 {idx}",
                "evidence": f"第 {idx} 個有效風險證據足以支持下行情境。",
                "impact": f"第 {idx} 個估值或現金流影響",
                "severity": "warning",
                "confidence": idx / 10,
            }
            for idx in range(1, 6)
        ],
        "analysis_markdown": "空方正文",
    }

    normalized = normalize_structured_output(21, payload)

    assert normalized is not None
    assert [row["title"] for row in normalized["downside_risks"]] == [
        f"有效風險 {idx}" for idx in range(1, 6)
    ]
    assert [row["confidence"] for row in normalized["downside_risks"]] == [0.1, 0.2, 0.3, 0.4, 0.5]


def test_agent21_report_text_uses_downside_risk_fallback_row_when_empty():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(21, {
        "thesis_summary": "下行風險摘要仍需揭露。",
        "downside_risks": [],
        "analysis_markdown": "空方正文",
    })
    lines = report_text.splitlines()

    fallback_line = "- **下行風險**（嚴重度：warning；信心：0.7）：資料不足"
    assert fallback_line in lines
    assert (
        lines.index("## 最大下行風險 (Key Downside Risks) / 空頭觀點")
        < lines.index(fallback_line)
        < lines.index("空方正文")
    )


def test_agent21_report_text_surfaces_thesis_summary_before_downside_risks():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(21, {
        "thesis_summary": "需求下修與\n現金流轉弱是主要空方論點。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值倍數下修",
                "severity": "high",
                "confidence": 0.8,
            },
            {
                "title": "現金流轉弱",
                "evidence": "營運資金需求上升使 FCF 轉換率下滑。",
                "impact": "DCF 折價",
                "severity": "warning",
                "confidence": 0.6,
            },
            {
                "title": "客戶集中",
                "evidence": "主要客戶拉貨節奏可能放大營收波動。",
                "impact": "營收能見度下降",
                "severity": "warning",
                "confidence": 0.5,
            },
        ],
        "analysis_markdown": "空方正文",
    })
    lines = report_text.splitlines()

    assert "## 空方論點摘要" in lines
    assert "需求下修與 現金流轉弱是主要空方論點。" in lines
    assert lines.index("## 空方論點摘要") < lines.index("## 最大下行風險 (Key Downside Risks) / 空頭觀點")
    assert all(not line.startswith("現金流轉弱是主要空方論點") for line in lines)


def test_agent21_report_text_uses_thesis_summary_fallback_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(21, {
        "thesis_summary": "空",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值折價擴大",
                "severity": "warning",
                "confidence": 0.6,
            },
        ],
        "analysis_markdown": "空方正文",
    })
    lines = report_text.splitlines()

    assert "## 空方論點摘要" in lines
    assert "資料不足" in lines
    assert "空" not in lines
    assert lines.index("## 空方論點摘要") < lines.index("## 最大下行風險 (Key Downside Risks) / 空頭觀點")


def test_agent21_report_text_uses_analysis_body_fallback_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(21, {
        "thesis_summary": "需求下修是主要空方論點。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值折價擴大",
                "severity": "warning",
                "confidence": 0.6,
            },
        ],
        "analysis_markdown": "空",
    })
    lines = report_text.splitlines()

    assert "資料不足" in lines
    assert "空" not in lines
    assert lines.index("資料不足") > lines.index("## 最大下行風險 (Key Downside Risks) / 空頭觀點")


def test_agent21_report_text_surfaces_downside_risk_priority_metadata():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(21, {
        "thesis_summary": "需求下修與現金流轉弱是主要空方論點。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價\n下修且庫存去化慢於預期。",
                "impact": "估值倍數\n下修",
                "severity": "high",
                "confidence": 0.8,
            },
            {
                "title": "現金流轉弱",
                "evidence": "營運資金需求上升使 FCF 轉換率下滑。",
                "impact": "DCF 折價",
                "severity": "warning",
                "confidence": 0.6,
            },
            {
                "title": "客戶集中",
                "evidence": "主要客戶拉貨節奏可能放大營收波動。",
                "impact": "營收能見度下降",
                "severity": "critical",
                "confidence": 0.5,
            },
        ],
        "analysis_markdown": "空方正文",
    })
    lines = report_text.splitlines()

    assert "- **毛利率壓力**（嚴重度：high；信心：0.8）：同業報價 下修且庫存去化慢於預期。影響：估值倍數 下修" in lines
    assert "- **現金流轉弱**（嚴重度：warning；信心：0.6）：營運資金需求上升使 FCF 轉換率下滑。影響：DCF 折價" in lines
    assert "- **客戶集中**（嚴重度：critical；信心：0.5）：主要客戶拉貨節奏可能放大營收波動。影響：營收能見度下降" in lines
    assert all(not line.startswith(("下修且庫存", "下修")) for line in lines)


def test_agent21_report_text_separates_downside_risk_impact_from_evidence():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(21, {
        "thesis_summary": "需求下修與現金流轉弱是主要空方論點。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢",
                "impact": "估值倍數下修",
                "severity": "high",
                "confidence": 0.8,
            },
            {
                "title": "現金流轉弱",
                "evidence": "營運資金需求上升使 FCF 轉換率下滑。",
                "impact": "DCF 折價",
                "severity": "warning",
                "confidence": 0.6,
            },
            {
                "title": "客戶集中",
                "evidence": "主要客戶拉貨節奏可能放大營收波動。",
                "impact": "營收能見度下降",
                "severity": "warning",
                "confidence": 0.5,
            },
        ],
        "analysis_markdown": "空方正文",
    })
    lines = report_text.splitlines()

    assert "- **毛利率壓力**（嚴重度：high；信心：0.8）：同業報價下修且庫存去化慢；影響：估值倍數下修" in lines
    assert "去化慢影響：" not in report_text


def test_agent21_report_text_uses_evidence_fallback_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(21, {
        "thesis_summary": "需求下修與現金流轉弱是主要空方論點。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "短",
                "impact": "估值折價擴大",
                "severity": "warning",
                "confidence": 0.6,
            },
        ],
        "analysis_markdown": "空方正文",
    })
    lines = report_text.splitlines()

    assert "- **毛利率壓力**（嚴重度：warning；信心：0.6）：資料不足；影響：估值折價擴大" in lines
    assert "- **毛利率壓力**（嚴重度：warning；信心：0.6）：短；影響：估值折價擴大" not in lines


def test_agent21_report_text_uses_title_fallback_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(21, {
        "thesis_summary": "需求下修與現金流轉弱是主要空方論點。",
        "downside_risks": [
            {
                "title": "風",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值折價擴大",
                "severity": "warning",
                "confidence": 0.6,
            },
        ],
        "analysis_markdown": "空方正文",
    })
    lines = report_text.splitlines()

    assert "- **下行風險**（嚴重度：warning；信心：0.6）：同業報價下修且庫存去化慢於預期。影響：估值折價擴大" in lines
    assert "- **風**（嚴重度：warning；信心：0.6）：同業報價下修且庫存去化慢於預期。影響：估值折價擴大" not in lines


def test_agent21_report_text_omits_impact_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(21, {
        "thesis_summary": "需求下修與現金流轉弱是主要空方論點。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "縮",
                "severity": "warning",
                "confidence": 0.6,
            },
        ],
        "analysis_markdown": "空方正文",
    })
    lines = report_text.splitlines()

    assert "- **毛利率壓力**（嚴重度：warning；信心：0.6）：同業報價下修且庫存去化慢於預期。" in lines
    assert "影響：縮" not in report_text


def test_agent21_report_text_uses_severity_fallback_for_invalid_metadata():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(21, {
        "thesis_summary": "需求下修與現金流轉弱是主要空方論點。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值折價擴大",
                "severity": "高",
                "confidence": 0.6,
            },
        ],
        "analysis_markdown": "空方正文",
    })
    lines = report_text.splitlines()

    assert "- **毛利率壓力**（嚴重度：warning；信心：0.6）：同業報價下修且庫存去化慢於預期。影響：估值折價擴大" in lines
    assert "嚴重度：高" not in report_text


def test_agent21_report_text_uses_confidence_fallback_for_invalid_metadata():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(21, {
        "thesis_summary": "需求下修與現金流轉弱是主要空方論點。",
        "downside_risks": [
            {
                "title": "毛利率壓力",
                "evidence": "同業報價下修且庫存去化慢於預期。",
                "impact": "估值折價擴大",
                "severity": "warning",
                "confidence": "很高",
            },
        ],
        "analysis_markdown": "空方正文",
    })
    lines = report_text.splitlines()

    assert "- **毛利率壓力**（嚴重度：warning；信心：0.7）：同業報價下修且庫存去化慢於預期。影響：估值折價擴大" in lines
    assert "信心：很高" not in report_text


def test_normalize_structured_output_price_target_reasoning_uses_safe_text_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "price_targets": {
            "dcf_reasoning": MalformedStructuredText(),
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": "估值正文",
    }

    normalized = normalize_structured_output(4, payload)

    assert normalized is not None
    assert normalized["price_targets"] == {"熊市情境": 90.0, "基本情境": 120.0, "牛市情境": 150.0}
    assert normalized["valuation_reasoning"]["dcf_reasoning"] == "資料不足"
    assert normalized["valuation_reasoning"]["peer_reasoning"] == "同業比較完整"


def test_normalize_structured_output_price_target_drops_string_empty_tokens_before_validation():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    payload = {
        "price_targets": {
            "dcf_reasoning": "NaN",
            "peer_reasoning": "Infinity",
            "scenario_reasoning": "-Infinity",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "N/A",
        },
        "analysis_markdown": "NaN",
    }

    normalized = normalize_structured_output(4, payload)
    report_text = structured_output_to_report_text(4, normalized)

    assert normalized["analysis_markdown"] == "資料不足"
    assert normalized["valuation_reasoning"] == {
        "dcf_reasoning": "資料不足",
        "peer_reasoning": "資料不足",
        "scenario_reasoning": "資料不足",
    }
    assert normalized["valuation_summary"]["double_counting_check"] == "資料不足"
    assert "nan" not in str(normalized).lower()
    assert "infinity" not in str(normalized).lower()
    assert "nan" not in report_text.lower()
    assert "infinity" not in report_text.lower()


def test_normalize_structured_output_agent24_uses_safe_text_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "trade_direction": "Long",
        "entry_zone": MalformedStructuredText(),
        "target_price": "NT$112",
        "stop_loss": "NT$96",
        "core_catalyst": "法說會調升指引",
        "risk_level": "Medium",
    }

    normalized = normalize_structured_output(24, payload)

    assert normalized is not None
    assert normalized["trade_direction"] == "Long"
    assert normalized["entry_zone"] == "N/A"
    assert normalized["target_price"] == "NT$112"


def test_normalize_structured_output_agent24_invalid_enums_use_fallback_before_validation():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "trade_direction": "Buy",
        "entry_zone": "NT$100-105",
        "target_price": "NT$112",
        "stop_loss": "NT$96",
        "core_catalyst": "法說會調升指引",
        "risk_level": "Elevated",
    }

    normalized = normalize_structured_output(24, payload)

    assert normalized is not None
    assert normalized["trade_direction"] == "Neutral"
    assert normalized["risk_level"] == "High"
    assert normalized["entry_zone"] == "NT$100-105"


def test_normalize_structured_output_agent24_preserves_analysis_markdown_for_legacy_text():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    payload = {
        "trade_direction": "Long",
        "entry_zone": "NT$100-105",
        "target_price": "NT$112",
        "stop_loss": "NT$96",
        "core_catalyst": "法說會調升指引",
        "risk_level": "Medium",
        "analysis_markdown": "## 交易脈絡\n等待法說會確認量價突破。",
    }

    normalized = normalize_structured_output(24, payload)

    assert normalized is not None
    assert normalized["analysis_markdown"] == "## 交易脈絡\n等待法說會確認量價突破。"
    report_text = structured_output_to_report_text(24, normalized)
    assert "## 交易脈絡" in report_text
    assert "等待法說會確認量價突破。" in report_text


def test_normalize_structured_output_skips_malformed_price_target_keys():
    from structured_output_normalizer import normalize_structured_output  # noqa: E402

    payload = {
        "price_targets": {
            "dcf_reasoning": "DCF 假設完整",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "三情境差異完整",
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
            MalformedStructuredText(): 999,
        },
        "valuation_summary": {
            "primary_method": "blended",
            "uses_market_value_wacc": True,
            "uses_normalized_fcf": True,
            "double_counting_check": "未重複計算成長與多重評價。",
        },
        "analysis_markdown": "估值正文",
    }

    normalized = normalize_structured_output(4, payload)

    assert normalized is not None
    assert normalized["price_targets"] == {"熊市情境": 90.0, "基本情境": 120.0, "牛市情境": 150.0}


def test_agent19_required_sections_markdown_collapses_embedded_newlines_in_trigger_rows():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(19, {
        "recommendation": {
            "建議": "放空",
        },
        "scenario_triggers": [
            {
                "trigger_condition": "財測\n下修幅度超過預期",
                "action": "提高\n空方權重",
                "direction": "bearish_downgrade",
            },
            {
                "trigger_condition": "股價放量\n突破前高",
                "action": "回補並\n重新評估",
                "direction": "neutral_review",
            },
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- 財測 下修幅度超過預期：提高 空方權重" in lines
    assert "- 股價放量 突破前高：回補並 重新評估" in lines
    assert all(
        not line.startswith(("下修幅度超過預期", "空方權重", "突破前高", "重新評估"))
        for line in lines
    )


def test_agent19_required_sections_use_action_fallback_when_trigger_action_blank():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(19, {
        "recommendation": {
            "建議": "放空",
        },
        "scenario_triggers": [
            {
                "trigger_condition": "財測下修幅度超過預期",
                "action": memoryview(b"bad-crash-action"),
                "direction": "bearish_downgrade",
            },
            {
                "trigger_condition": "股價放量突破前高",
                "direction": "neutral_review",
            },
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- 財測下修幅度超過預期：重新檢查空方假設" in lines
    assert "- 股價放量突破前高：回補或暫停空方假設" in lines
    assert "- 財測下修幅度超過預期" not in lines
    assert "- 股價放量突破前高" not in lines
    assert "bad-crash-action" not in report_text
    assert "memory" not in report_text


def test_agent19_required_sections_guard_single_character_trigger_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(19, {
        "recommendation": {
            "建議": "放空",
        },
        "scenario_triggers": [
            {
                "trigger_condition": "跌",
                "action": "砍",
                "direction": "bearish_downgrade",
            },
            {
                "trigger_condition": "股價放量突破前高",
                "action": "補",
                "direction": "neutral_review",
            },
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- 跌：砍" not in lines
    assert "- 股價放量突破前高：回補或暫停空方假設" in lines
    assert "模型未提供足夠可量化崩盤催化" in report_text


def test_agent19_required_sections_ignore_non_string_trigger_directions():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(19, {
        "recommendation": {
            "建議": "放空",
        },
        "scenario_triggers": [
            {
                "trigger_condition": "財測下修幅度超過預期",
                "action": "提高空方權重",
                "direction": StringifyingBearishDirection(),
            },
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- 財測下修幅度超過預期：提高空方權重" not in lines
    assert "bearish_downgrade" not in report_text
    assert "模型未提供足夠可量化崩盤催化" in report_text


def test_recommendation_report_text_skips_readonly_confidence_basis_maps():
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text  # noqa: E402

    normalized = normalize_structured_output(7, _readonly(_recommendation_payload()))

    report_text = structured_output_to_report_text(7, _readonly(normalized))

    assert "[投資建議]" in report_text
    assert "建議: 持有" in report_text
    assert "估值接近基本情境" in report_text
    assert "confidence_basis" not in report_text
    assert "mappingproxy" not in report_text


def test_recommendation_report_text_skips_malformed_display_keys():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {
            "建議": "持有",
            memoryview(b"bad-recommendation-key"): "不應輸出",
            "短期目標（3個月）": "NT$300",
        },
        "analysis_markdown": "正式報告正文",
    })

    assert "建議: 持有" in report_text
    assert "短期目標（3個月）: NT$300" in report_text
    assert "不應輸出" not in report_text
    assert "memory" not in report_text
    assert "bad-recommendation-key" not in report_text


def test_recommendation_report_text_skips_single_character_display_keys():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {
            "建議": "持有",
            "短": "不應輸出",
            "信心指數": "8",
        },
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "建議: 持有" in lines
    assert "信心指數: 8" in lines
    assert "短: 不應輸出" not in lines
    assert "不應輸出" not in report_text


def test_recommendation_report_text_ignores_non_string_display_literals():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    standard_text = structured_output_to_report_text(7, {
        "recommendation": {
            "建議": "持有",
            StringifyingStructuredText(): "不應輸出",
            "短期目標（3個月）": StringifyingStructuredText(),
            "信心指數": 8,
        },
        "analysis_markdown": "正式報告正文",
    })
    agent19_text = structured_output_to_report_text(19, {
        "recommendation": {
            "建議": "放空",
            "短期目標（3個月）": StringifyingStructuredText(),
            "中期目標（6個月）": "NT$330",
            "長期目標（12個月）": StringifyingStructuredText(),
            "長期潛力（5年）": "NT$420",
            "信心指數": 8,
        },
        "analysis_markdown": "## 做空觸發條件（Catalyst for crash）\n財測下修。",
    })

    assert "建議: 持有" in standard_text
    assert "短期目標（3個月）: N/A" in standard_text
    assert "信心指數: 8" in standard_text
    assert "不應輸出" not in standard_text
    assert "短期目標（3個月）：N/A" in agent19_text
    assert "中期目標（6個月）：NT$330" in agent19_text
    assert "長期目標（12個月）：N/A" in agent19_text
    assert "信心指數：8" in agent19_text
    assert "bad-body-literal" not in (standard_text + agent19_text)


def test_recommendation_report_text_uses_fallback_row_when_standard_recommendation_empty():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {},
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "建議: N/A" in lines
    assert lines.index("[投資建議]") < lines.index("建議: N/A") < lines.index("[/投資建議]")


def test_agent19_recommendation_report_text_uses_text_safe_ordered_values():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(19, {
        "recommendation": {
            "建議": memoryview(b"bad-recommendation"),
            "短期目標（3個月）": memoryview(b"bad-short-target"),
            "中期目標（6個月）": "NT$330",
            "長期目標（12個月）": b"bad-long-target",
            "長期潛力（5年）": "NT$420",
            "信心指數": memoryview(b"bad-confidence"),
        },
        "analysis_markdown": "## 做空觸發條件（Catalyst for crash）\n財測下修。",
    })

    assert "建議：N/A" in report_text
    assert "短期目標（3個月）：N/A" in report_text
    assert "中期目標（6個月）：NT$330" in report_text
    assert "長期目標（12個月）：N/A" in report_text
    assert "長期潛力（5年）：NT$420" in report_text
    assert "信心指數：N/A" in report_text
    assert "memory" not in report_text
    assert "bad-long-target" not in report_text


def test_agent19_recommendation_report_text_uses_fallback_for_single_character_ordered_values():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(19, {
        "recommendation": {
            "建議": "空",
            "短期目標（3個月）": "高",
            "中期目標（6個月）": "NT$330",
            "長期目標（12個月）": "低",
            "長期潛力（5年）": "NT$420",
            "信心指數": "8",
        },
        "analysis_markdown": "## 做空觸發條件（Catalyst for crash）\n財測下修。",
    })
    lines = report_text.splitlines()

    assert "建議：N/A" in lines
    assert "短期目標（3個月）：N/A" in lines
    assert "中期目標（6個月）：NT$330" in lines
    assert "長期目標（12個月）：N/A" in lines
    assert "長期潛力（5年）：NT$420" in lines
    assert "信心指數：8" in lines
    assert "建議：空" not in lines
    assert "短期目標（3個月）：高" not in lines
    assert "長期目標（12個月）：低" not in lines


def test_recommendation_block_markdown_collapses_embedded_newlines_in_display_rows():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    standard_text = structured_output_to_report_text(7, {
        "recommendation": {
            "建議": "持有",
            "投資\n理由": "估值接近\n基本情境",
        },
        "analysis_markdown": "正式報告正文",
    })
    agent19_text = structured_output_to_report_text(19, {
        "recommendation": {
            "建議": "持有",
            "短期目標（3個月）": "NT$300\n偏保守",
            "中期目標（6個月）": "NT$330",
            "長期目標（12個月）": "NT$350",
            "長期潛力（5年）": "NT$420",
            "信心指數": "7/10\n中等",
        },
        "analysis_markdown": "## 做空觸發條件（Catalyst for crash）\n財測下修。",
    })
    lines = (standard_text + "\n" + agent19_text).splitlines()

    assert "投資 理由: 估值接近 基本情境" in lines
    assert "短期目標（3個月）：NT$300 偏保守" in lines
    assert "信心指數：7/10 中等" in lines
    assert all(
        not line.startswith(("理由", "基本情境", "偏保守", "中等"))
        for line in lines
    )


def test_legacy_structured_report_text_uses_safe_text_for_display_values():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    management_text = structured_output_to_report_text(20, {
        "guidance_tone": memoryview(b"bad-management-tone"),
        "highlights": [
            {"keyword": memoryview(b"bad-keyword"), "quote": b"bad-quote"},
            {"keyword": "有效亮點", "quote": "有效引述"},
        ],
        "analysis_markdown": "管理層正文",
    })
    downside_text = structured_output_to_report_text(21, {
        "downside_risks": [
            {"title": memoryview(b"bad-risk-title"), "evidence": b"bad-risk-evidence"},
            {"title": "有效風險", "evidence": "有效證據"},
        ],
        "analysis_markdown": "空方正文",
    })
    trade_text = structured_output_to_report_text(24, {
        "trade_direction": memoryview(b"bad-trade-direction"),
        "entry_zone": b"bad-entry-zone",
        "target_price": "NT$50",
        "stop_loss": memoryview(b"bad-stop-loss"),
        "core_catalyst": b"bad-catalyst",
        "risk_level": memoryview(b"bad-risk-level"),
    })

    assert "管理層語氣：資料不足" in management_text
    assert "有效亮點" in management_text
    assert "有效引述" in management_text
    assert "有效風險" in downside_text
    assert "有效證據" in downside_text
    assert "交易方向：Neutral" in trade_text
    assert "進場區間：N/A" in trade_text
    assert "1-2週目標價：NT$50" in trade_text
    assert "停損點：N/A" in trade_text
    assert "核心催化劑：N/A" in trade_text
    assert "短期波動風險：High" in trade_text
    combined = management_text + downside_text + trade_text
    assert "memory" not in combined
    assert "bad-" not in combined


def test_legacy_management_sentiment_report_text_surfaces_confidence():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(20, {
        "guidance_tone": "樂觀",
        "confidence": 0.86,
        "highlights": [
            {"keyword": "訂單", "quote": "AI 訂單增長"},
            {"keyword": "毛利率", "quote": "管理層維持全年展望"},
            {"keyword": "資本支出", "quote": "供應鏈投資保持紀律"},
        ],
        "analysis_markdown": "管理層正文",
    })
    lines = report_text.splitlines()

    assert "## 管理層語氣：樂觀" in lines
    assert "信心分數：0.86" in lines
    assert lines.index("信心分數：0.86") < lines.index("- **訂單**：AI 訂單增長")


def test_legacy_management_sentiment_report_text_uses_quote_fallback():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(20, {
        "guidance_tone": "中立",
        "highlights": [
            {"keyword": "訂單", "quote": memoryview(b"bad-quote")},
        ],
        "analysis_markdown": "管理層正文",
    })
    lines = report_text.splitlines()

    assert "- **訂單**：資料不足" in lines
    assert "- **訂單**：" not in lines
    assert "memory" not in report_text
    assert "bad-quote" not in report_text


def test_agent20_report_text_uses_highlight_fallbacks_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(20, {
        "guidance_tone": "中立",
        "confidence": 0.55,
        "highlights": [
            {"keyword": "營", "quote": "好"},
            {"keyword": "訂單", "quote": "AI 訂單恢復成長"},
        ],
        "analysis_markdown": "管理層正文",
    })
    lines = report_text.splitlines()

    assert "- **亮點**：資料不足" in lines
    assert "- **訂單**：AI 訂單恢復成長" in lines
    assert "- **營**：好" not in lines
    assert "信心分數：0.55" in lines


def test_legacy_management_sentiment_report_text_uses_highlight_fallback_row_when_empty():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(20, {
        "guidance_tone": "中立",
        "confidence": 0.4,
        "highlights": [],
        "analysis_markdown": "管理層正文",
    })
    lines = report_text.splitlines()

    assert "- **亮點**：資料不足" in lines
    assert lines.index("信心分數：0.4") < lines.index("- **亮點**：資料不足") < lines.index("管理層正文")


def test_agent20_report_text_uses_guidance_tone_fallback_for_invalid_metadata():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(20, {
        "guidance_tone": "樂",
        "confidence": 0.6,
        "highlights": [{"keyword": "需求回溫", "quote": "AI 訂單恢復成長"}],
        "analysis_markdown": "管理層正文",
    })
    lines = report_text.splitlines()

    assert "## 管理層語氣：資料不足" in lines
    assert "## 管理層語氣：樂" not in lines
    assert "信心分數：0.6" in lines
    assert "- **需求回溫**：AI 訂單恢復成長" in lines


def test_agent20_report_text_uses_analysis_body_fallback_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(20, {
        "guidance_tone": "中立",
        "confidence": 0.62,
        "highlights": [{"keyword": "需求回溫", "quote": "AI 訂單恢復成長"}],
        "analysis_markdown": "X",
    })
    lines = report_text.splitlines()

    assert lines[-1] == "資料不足"
    assert "X" not in report_text
    assert "- **需求回溫**：AI 訂單恢復成長" in lines


def test_legacy_trade_plan_report_text_preserves_body_context():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(
        24,
        {
            "trade_direction": "Long",
            "entry_zone": "NT$100-105",
            "target_price": "NT$112",
            "stop_loss": "NT$96",
            "core_catalyst": "法說調升指引",
            "risk_level": "Medium",
            "analysis_markdown": memoryview(b"bad-trade-body"),
        },
        fallback_text="## 交易脈絡\n等待法說會確認量價突破。",
    )
    lines = report_text.splitlines()

    assert "## 極短線交易計畫" in lines
    assert "## 交易脈絡" in lines
    assert "等待法說會確認量價突破。" in lines
    assert lines.index("## 極短線交易計畫") < lines.index("## 交易脈絡")
    assert "memory" not in report_text
    assert "bad-trade-body" not in report_text


def test_agent24_report_text_uses_trade_enum_fallback_for_invalid_metadata():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(24, {
        "trade_direction": "偏多",
        "entry_zone": "NT$100-105",
        "target_price": "NT$112",
        "stop_loss": "NT$96",
        "core_catalyst": "法說調升指引",
        "risk_level": "中高",
        "analysis_markdown": "短線交易正文",
    })
    lines = report_text.splitlines()

    assert "- **交易方向：Neutral**" in lines
    assert "- **短期波動風險：High**" in lines
    assert "- **交易方向：偏多**" not in lines
    assert "- **短期波動風險：中高**" not in lines
    assert "- **進場區間：NT$100-105**" in lines
    assert "- **核心催化劑：法說調升指引**" in lines


def test_agent24_report_text_uses_field_fallbacks_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(24, {
        "trade_direction": "Long",
        "entry_zone": "買",
        "target_price": "高",
        "stop_loss": "停",
        "core_catalyst": "量",
        "risk_level": "Medium",
        "analysis_markdown": "短線交易正文",
    })
    lines = report_text.splitlines()

    assert "- **交易方向：Long**" in lines
    assert "- **進場區間：N/A**" in lines
    assert "- **1-2週目標價：N/A**" in lines
    assert "- **🛑 停損點：N/A**" in lines
    assert "- **核心催化劑：N/A**" in lines
    assert "- **短期波動風險：Medium**" in lines
    assert "- **進場區間：買**" not in lines
    assert "- **1-2週目標價：高**" not in lines
    assert "- **🛑 停損點：停**" not in lines
    assert "- **核心催化劑：量**" not in lines


def test_agent24_report_text_uses_analysis_body_fallback_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(24, {
        "trade_direction": "Long",
        "entry_zone": "NT$100-105",
        "target_price": "NT$112",
        "stop_loss": "NT$96",
        "core_catalyst": "法說調升指引",
        "risk_level": "Medium",
        "analysis_markdown": "X",
    })
    lines = report_text.splitlines()

    assert lines[-1] == "資料不足"
    assert "X" not in report_text
    assert "- **交易方向：Long**" in lines
    assert "- **進場區間：NT$100-105**" in lines


def test_legacy_structured_markdown_collapses_embedded_newlines_in_display_fields():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    management_text = structured_output_to_report_text(20, {
        "guidance_tone": "謹慎\n樂觀",
        "highlights": [{"keyword": "需求\n回溫", "quote": "AI 訂單\n恢復成長"}],
        "analysis_markdown": "管理層正文",
    })
    downside_text = structured_output_to_report_text(21, {
        "downside_risks": [{"title": "毛利率\n下滑", "evidence": "報價壓力\n仍高"}],
        "analysis_markdown": "空方正文",
    })
    trade_text = structured_output_to_report_text(24, {
        "trade_direction": "偏多\n觀察",
        "entry_zone": "NT$100\n至 NT$105",
        "target_price": "NT$112\n短線",
        "stop_loss": "NT$96\n跌破退出",
        "core_catalyst": "法說會\n調升指引",
        "risk_level": "中高\n波動",
    })

    combined_lines = (management_text + "\n" + downside_text + "\n" + trade_text).splitlines()

    assert "## 管理層語氣：資料不足" in combined_lines
    assert "- **需求 回溫**：AI 訂單 恢復成長" in combined_lines
    assert "- **毛利率 下滑**：報價壓力 仍高" in combined_lines
    assert "- **交易方向：Neutral**" in combined_lines
    assert "- **進場區間：NT$100 至 NT$105**" in combined_lines
    assert "- **1-2週目標價：NT$112 短線**" in combined_lines
    assert "- **🛑 停損點：NT$96 跌破退出**" in combined_lines
    assert "- **核心催化劑：法說會 調升指引**" in combined_lines
    assert "- **短期波動風險：High**" in combined_lines
    assert all(
        not line.startswith(("樂觀", "回溫", "恢復成長", "下滑", "仍高", "至", "短線", "跌破退出", "調升指引", "波動"))
        for line in combined_lines
    )


def test_recommendation_tail_text_uses_safe_text_for_basis_and_triggers():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {
            "建議": "持有",
            "confidence_basis": {
                "evidence_items": [memoryview(b"bad-evidence"), "有效佐證"],
                "key_risks_acknowledged": [b"bad-risk", "有效風險"],
                "data_gaps": [memoryview(b"bad-gap"), "有效缺口"],
            },
        },
        "scenario_triggers": [
            {"trigger_condition": memoryview(b"bad-condition"), "action": "不應輸出"},
            {"trigger_condition": "有效條件", "action": memoryview(b"bad-action")},
            {"trigger_condition": "有效升級條件", "action": "重新評估上行情境"},
        ],
        "analysis_markdown": "正式報告正文",
    })

    assert "有效佐證" in report_text
    assert "有效風險" in report_text
    assert "有效缺口" in report_text
    assert "有效條件" in report_text
    assert "有效升級條件" in report_text
    assert "重新評估上行情境" in report_text
    assert "不應輸出" not in report_text
    assert "memory" not in report_text
    assert "bad-" not in report_text


def test_recommendation_tail_trigger_actions_use_fallback_when_blank():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {"建議": "持有"},
        "scenario_triggers": [
            {"trigger_condition": "毛利率連續兩季低於 43%", "action": memoryview(b"bad-action")},
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- 若「毛利率連續兩季低於 43%」：建議 重新檢查投資結論" in lines
    assert "- 若「毛利率連續兩季低於 43%」：建議 " not in lines
    assert "memory" not in report_text
    assert "bad-action" not in report_text


def test_recommendation_tail_trigger_conditions_skip_too_short_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {"建議": "持有"},
        "scenario_triggers": [
            {"trigger_condition": "短", "action": "重新評估風險情境"},
            {"trigger_condition": "毛利率連續兩季低於 43%", "action": "重新檢查投資結論"},
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- 若「毛利率連續兩季低於 43%」：建議 重新檢查投資結論" in lines
    assert "- 若「短」：建議 重新評估風險情境" not in lines


def test_recommendation_tail_trigger_actions_use_fallback_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {"建議": "持有"},
        "scenario_triggers": [
            {"trigger_condition": "毛利率連續兩季低於 43%", "action": "改"},
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- 若「毛利率連續兩季低於 43%」：建議 重新檢查投資結論" in lines
    assert "- 若「毛利率連續兩季低於 43%」：建議 改" not in lines


def test_recommendation_report_text_uses_body_fallback_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    standard_text = structured_output_to_report_text(7, {
        "recommendation": {"建議": "持有"},
        "analysis_markdown": "X",
    })
    agent19_text = structured_output_to_report_text(19, {
        "recommendation": {"建議": "放空"},
        "analysis_markdown": "弱",
    })
    lines = (standard_text + "\n" + agent19_text).splitlines()

    assert "資料不足" in lines
    assert "X" not in lines
    assert "弱" not in lines
    assert "[投資建議]" in lines
    assert "## 做空觸發條件（Catalyst for crash）" in lines


def test_recommendation_tail_markdown_collapses_embedded_newlines_in_basis_and_triggers():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {
            "建議": "持有",
            "confidence_basis": {
                "evidence_items": ["估值接近\n基本情境"],
                "key_risks_acknowledged": ["毛利率\n下滑"],
                "data_gaps": ["缺少\n最新法說"],
            },
        },
        "scenario_triggers": [
            {"trigger_condition": "若毛利率\n低於 43%", "action": "重新評估\n風險情境"},
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- **具體佐證**: 估值接近 基本情境" in lines
    assert "- **已納入考量的風險**: 毛利率 下滑" in lines
    assert "- **已知缺口**: 缺少 最新法說" in lines
    assert "- 若「若毛利率 低於 43%」：建議 重新評估 風險情境" in lines
    assert all(
        not line.startswith(("基本情境", "下滑", "最新法說", "低於 43%", "風險情境"))
        for line in lines
    )


def test_recommendation_tail_omits_empty_basis_and_trigger_sections():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {
            "建議": "持有",
            "confidence_basis": {
                "evidence_items": [memoryview(b"bad-evidence")],
                "key_risks_acknowledged": [memoryview(b"bad-risk")],
                "data_gaps": [memoryview(b"bad-gap")],
            },
        },
        "scenario_triggers": [
            {"trigger_condition": memoryview(b"bad-condition"), "action": "不應輸出"},
        ],
        "analysis_markdown": "正式報告正文",
    })

    assert "正式報告正文" in report_text
    assert "### 信心依據" not in report_text
    assert "### 情境觸發器" not in report_text
    assert "不應輸出" not in report_text
    assert "memory" not in report_text
    assert "bad-" not in report_text


def test_recommendation_tail_confidence_basis_ignores_non_string_display_literals():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {
            "建議": "持有",
            "confidence_basis": {
                "evidence_items": ["估值接近基本情境", StringifyingStructuredText()],
                "key_risks_acknowledged": [StringifyingStructuredText(), "毛利率下滑"],
                "data_gaps": [StringifyingStructuredText(), "月營收細項待補"],
            },
        },
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- **具體佐證**: 估值接近基本情境" in lines
    assert "- **已納入考量的風險**: 毛利率下滑" in lines
    assert "- **已知缺口**: 月營收細項待補" in lines
    assert "bad-body-literal" not in report_text


def test_recommendation_tail_confidence_basis_skips_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {
            "建議": "持有",
            "confidence_basis": {
                "evidence_items": ["短"],
                "key_risks_acknowledged": ["險"],
                "data_gaps": ["缺"],
            },
        },
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "### 信心依據" not in lines
    assert "- **具體佐證**: 短" not in lines
    assert "- **已納入考量的風險**: 險" not in lines
    assert "- **已知缺口**: 缺" not in lines


def test_recommendation_tail_report_text_surfaces_next_catalysts():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {"建議": "持有"},
        "next_catalysts": [
            {
                "event_name": "Q3 法說會",
                "expected_timeframe": "Q3 2026",
                "impact_direction": "bullish",
                "trigger_condition": "若管理層調升毛利率指引，重新評估上行情境。",
            },
            {
                "event_name": "庫存\n週轉",
                "expected_timeframe": "H2\n2026",
                "impact_direction": "bearish",
                "trigger_condition": "庫存天數連續兩季高於同業。",
            },
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "### 下一步催化觀察" in lines
    assert "- **Q3 法說會**（Q3 2026，bullish）：若管理層調升毛利率指引，重新評估上行情境。" in lines
    assert "- **庫存 週轉**（H2 2026，bearish）：庫存天數連續兩季高於同業。" in lines
    assert all(not line.startswith(("週轉", "2026")) for line in lines)


def test_recommendation_tail_next_catalysts_use_trigger_fallback_when_blank():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {"建議": "持有"},
        "next_catalysts": [
            {
                "event_name": "法說會",
                "expected_timeframe": "Q3 2026",
                "impact_direction": "bullish",
                "trigger_condition": memoryview(b"bad-catalyst-trigger"),
            },
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- **法說會**（Q3 2026，bullish）：待後續資料確認" in lines
    assert "bad-catalyst-trigger" not in report_text
    assert "memory" not in report_text


def test_recommendation_tail_next_catalysts_use_trigger_fallback_when_too_short():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {"建議": "持有"},
        "next_catalysts": [
            {
                "event_name": "法說會",
                "expected_timeframe": "Q3 2026",
                "impact_direction": "bullish",
                "trigger_condition": "短",
            },
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- **法說會**（Q3 2026，bullish）：待後續資料確認" in lines
    assert "- **法說會**（Q3 2026，bullish）：短" not in lines


def test_recommendation_tail_next_catalysts_use_impact_direction_fallback_when_invalid():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {"建議": "持有"},
        "next_catalysts": [
            {
                "event_name": "法說會",
                "expected_timeframe": "Q3 2026",
                "impact_direction": "moonshot\nunknown",
                "trigger_condition": "若管理層調升毛利率指引，重新評估上行情境。",
            },
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- **法說會**（Q3 2026，volatile）：若管理層調升毛利率指引，重新評估上行情境。" in lines
    assert "moonshot" not in report_text
    assert "unknown" not in report_text


def test_recommendation_tail_next_catalysts_use_event_metadata_fallback_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {"建議": "持有"},
        "next_catalysts": [
            {
                "event_name": "法",
                "expected_timeframe": "Q",
                "impact_direction": "bullish",
                "trigger_condition": "若管理層調升毛利率指引，重新評估上行情境。",
            },
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- **待確認催化事件**（待後續資料確認，bullish）：若管理層調升毛利率指引，重新評估上行情境。" in lines
    assert "- **法**（Q，bullish）：若管理層調升毛利率指引，重新評估上行情境。" not in lines


def test_recommendation_tail_next_catalysts_ignore_non_string_display_literals():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {"建議": "持有"},
        "next_catalysts": [
            {
                "event_name": StringifyingStructuredText(),
                "expected_timeframe": StringifyingStructuredText(),
                "impact_direction": StringifyingStructuredText(),
                "trigger_condition": StringifyingStructuredText(),
            },
            {
                "event_name": "月營收公布",
                "expected_timeframe": "下個月",
                "impact_direction": "bullish",
                "trigger_condition": "若營收連續兩個月回升，重新評估上行情境。",
            },
        ],
        "analysis_markdown": "正式報告正文",
    })
    lines = report_text.splitlines()

    assert "- **待確認催化事件**（待後續資料確認，volatile）：待後續資料確認" in lines
    assert "- **月營收公布**（下個月，bullish）：若營收連續兩個月回升，重新評估上行情境。" in lines
    assert "bad-body-literal" not in report_text


def test_agent19_recommendation_tail_keeps_next_catalysts_before_final_block():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(19, {
        "recommendation": {"建議": "放空"},
        "next_catalysts": [
            {
                "event_name": "財測下修",
                "expected_timeframe": "下一季財報",
                "impact_direction": "bearish",
                "trigger_condition": "若營收或毛利率指引下修，空方論點升級。",
            }
        ],
        "analysis_markdown": "## 做空觸發條件（Catalyst for crash）\n等待可驗證事件。",
    })

    assert "### 下一步催化觀察" in report_text
    assert "- **財測下修**（下一季財報，bearish）：若營收或毛利率指引下修，空方論點升級。" in report_text
    assert report_text.rstrip().endswith("[/投資建議]")
    assert report_text.index("### 下一步催化觀察") < report_text.index("[投資建議]")


def test_recommendation_tail_report_text_surfaces_reasoning_steps():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {"建議": "買進"},
        "reasoning_steps": [
            "確認營收成長\n仍在",
            "估值接近基本情境",
            "風險已反映於信心折讓",
        ],
        "analysis_markdown": "建議正文",
    })
    lines = report_text.splitlines()

    assert "### 投資推論步驟" in lines
    assert "- 確認營收成長 仍在" in lines
    assert "- 估值接近基本情境" in lines
    assert "- 風險已反映於信心折讓" in lines
    assert lines.index("### 投資推論步驟") < lines.index("建議正文")
    assert all(not line.startswith("仍在") for line in lines)


def test_recommendation_tail_reasoning_steps_skip_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {"建議": "買進"},
        "reasoning_steps": [
            "短",
            "估值接近基本情境",
            "風險已反映於信心折讓",
        ],
        "analysis_markdown": "建議正文",
    })
    lines = report_text.splitlines()

    assert "- 估值接近基本情境" in lines
    assert "- 風險已反映於信心折讓" in lines
    assert "- 短" not in lines


def test_recommendation_tail_reasoning_steps_ignore_non_string_display_literals():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(7, {
        "recommendation": {"建議": "買進"},
        "reasoning_steps": [
            "確認營收成長仍在",
            StringifyingStructuredText(),
            "風險已反映於信心折讓",
        ],
        "analysis_markdown": "建議正文",
    })
    lines = report_text.splitlines()

    assert "- 確認營收成長仍在" in lines
    assert "- 風險已反映於信心折讓" in lines
    assert "bad-body-literal" not in report_text


def test_agent19_recommendation_tail_keeps_reasoning_steps_before_final_block():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(19, {
        "recommendation": {"建議": "放空"},
        "reasoning_steps": [
            "估值泡沫\n擴大",
            "需求轉弱",
            "財測下修風險升高",
        ],
        "analysis_markdown": "## 做空觸發條件（Catalyst for crash）\n等待可驗證事件。",
    })

    assert "### 投資推論步驟" in report_text
    assert "- 估值泡沫 擴大" in report_text
    assert report_text.rstrip().endswith("[/投資建議]")
    assert report_text.index("### 投資推論步驟") < report_text.index("[投資建議]")


def test_legacy_score_and_valuation_report_text_uses_safe_display_values():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    moat_text = structured_output_to_report_text(3, {
        "moat_scores": {
            "品牌": memoryview(b"bad-moat-score"),
            "技術": 8,
        },
        "analysis_markdown": "護城河正文",
    })
    valuation_text = structured_output_to_report_text(4, {
        "price_targets": {
            "熊市情境": memoryview(b"bad-bear-target"),
            "基本情境": "NT$320",
            "牛市情境": 420,
        },
        "valuation_summary": {
            "資料品質": memoryview(b"bad-summary"),
            "估值結論": "基本情境仍可用",
        },
        "analysis_markdown": "估值正文",
    })

    assert "品牌: N/A" in moat_text
    assert "技術: 8" in moat_text
    assert "熊市情境: N/A" in valuation_text
    assert "基本情境: NT$320" in valuation_text
    assert "牛市情境: NT$420" in valuation_text
    assert "- 資料品質: N/A" in valuation_text
    assert "- 估值結論: 基本情境仍可用" in valuation_text
    combined = moat_text + valuation_text
    assert "memory" not in combined
    assert "bad-" not in combined


def test_legacy_moat_score_uses_metric_key_fallback_for_empty_display_keys():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(3, {
        "moat_scores": {
            memoryview(b"bad-moat-key"): 8,
        },
        "analysis_markdown": "護城河正文",
    })
    lines = report_text.splitlines()

    assert "護城河指標: 8" in lines
    assert "N/A: 8" not in lines
    assert "memory" not in report_text
    assert "bad-moat-key" not in report_text


def test_legacy_moat_score_uses_metric_key_fallback_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(3, {
        "moat_scores": {
            "品": 5,
            "網路效應": 8,
        },
        "analysis_markdown": "護城河正文",
    })
    lines = report_text.splitlines()

    assert "護城河指標: 5" in lines
    assert "網路效應: 8" in lines
    assert "品: 5" not in lines


def test_legacy_moat_score_uses_value_fallback_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(3, {
        "moat_scores": {
            "品牌": "高",
            "技術": 8,
            "規模": "7",
        },
        "analysis_markdown": "護城河正文",
    })
    lines = report_text.splitlines()

    assert "品牌: N/A" in lines
    assert "技術: 8" in lines
    assert "規模: 7" in lines
    assert "品牌: 高" not in lines


def test_legacy_moat_score_report_text_uses_score_fallback_row_when_empty():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(3, {
        "moat_scores": {},
        "analysis_markdown": "護城河正文",
    })
    lines = report_text.splitlines()

    assert "護城河指標: N/A" in lines
    assert lines.index("[護城河評分]") < lines.index("護城河指標: N/A") < lines.index("[/護城河評分]")


def test_legacy_valuation_summary_uses_key_fallback_for_empty_display_keys():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(4, {
        "price_targets": {
            "基本情境": 120,
        },
        "valuation_summary": {
            memoryview(b"bad-summary-key"): "基本情境仍可用",
        },
        "analysis_markdown": "估值正文",
    })
    lines = report_text.splitlines()

    assert "- 估值檢查項目: 基本情境仍可用" in lines
    assert "- N/A: 基本情境仍可用" not in lines
    assert "memory" not in report_text
    assert "bad-summary-key" not in report_text


def test_legacy_valuation_summary_uses_fallbacks_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(4, {
        "price_targets": {
            "基本情境": 120,
        },
        "valuation_summary": {
            "估": "好",
            "主要方法": "混合估值",
        },
        "analysis_markdown": "估值正文",
    })
    lines = report_text.splitlines()

    assert "- 估值檢查項目: N/A" in lines
    assert "- 主要方法: 混合估值" in lines
    assert "- 估: 好" not in lines


def test_legacy_valuation_report_text_uses_price_target_fallback_row_when_empty():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(4, {
        "price_targets": {},
        "analysis_markdown": "估值正文",
    })
    lines = report_text.splitlines()

    assert "目標價: N/A" in lines
    assert lines.index("[目標股價]") < lines.index("目標價: N/A") < lines.index("[/目標股價]")


def test_legacy_score_and_valuation_report_text_use_body_fallback_for_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    moat_text = structured_output_to_report_text(3, {
        "moat_scores": {"品牌": 8},
        "analysis_markdown": "X",
    })
    valuation_text = structured_output_to_report_text(4, {
        "price_targets": {"基本情境": 120},
        "analysis_markdown": "弱",
    })

    moat_lines = moat_text.splitlines()
    valuation_lines = valuation_text.splitlines()

    assert moat_lines[-1] == "資料不足"
    assert valuation_lines[-1] == "資料不足"
    assert "X" not in moat_text
    assert "弱" not in valuation_text


def test_legacy_moat_report_text_surfaces_reasoning_steps():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(3, {
        "reasoning_steps": [
            "品牌黏著度\n高",
            "轉換成本明確",
            "整體分數反映反證",
        ],
        "moat_scores": {
            "品牌影響力": 8,
            "轉換成本": 7,
            "整體護城河": 8,
        },
        "analysis_markdown": "護城河正文",
    })
    lines = report_text.splitlines()

    assert "## 護城河推論步驟" in lines
    assert "- 品牌黏著度 高" in lines
    assert "- 轉換成本明確" in lines
    assert "- 整體分數反映反證" in lines
    assert lines.index("## 護城河推論步驟") < lines.index("護城河正文")
    assert all(not line.startswith("高") for line in lines)


def test_legacy_valuation_report_text_surfaces_valuation_reasoning():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(4, {
        "price_targets": {
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "valuation_reasoning": {
            "dcf_reasoning": "DCF 假設\n保守且使用正常化現金流。",
            "peer_reasoning": "同業倍數偏高，需折價比較。",
            "scenario_reasoning": "牛熊情境差距大，基本情境採中位數。",
        },
        "analysis_markdown": "估值正文",
    })
    lines = report_text.splitlines()

    assert "## 估值推論" in lines
    assert "- DCF 推論: DCF 假設 保守且使用正常化現金流。" in lines
    assert "- 同業推論: 同業倍數偏高，需折價比較。" in lines
    assert "- 情境推論: 牛熊情境差距大，基本情境採中位數。" in lines
    assert lines.index("## 估值推論") < lines.index("估值正文")
    assert all(not line.startswith("保守且使用正常化現金流") for line in lines)


def test_legacy_valuation_reasoning_skips_single_character_fragments():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(4, {
        "price_targets": {
            "基本情境": 120,
        },
        "valuation_reasoning": {
            "dcf_reasoning": "好",
            "peer_reasoning": "同業比較完整",
            "scenario_reasoning": "弱",
        },
        "analysis_markdown": "估值正文",
    })
    lines = report_text.splitlines()

    assert "## 估值推論" in lines
    assert "- 同業推論: 同業比較完整" in lines
    assert "- DCF 推論: 好" not in lines
    assert "- 情境推論: 弱" not in lines


def test_legacy_valuation_report_text_surfaces_dcf_scenarios():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(4, {
        "price_targets": {
            "熊市情境": 90,
            "基本情境": 120,
            "牛市情境": 150,
        },
        "dcf_scenarios": [
            {
                "scenario": "bear",
                "revenue_growth_bias_pct": -5,
                "margin_bias_pct": -2,
                "wacc_pct": 9.5,
                "intrinsic_value": 90,
            },
            {
                "scenario": "base",
                "revenue_growth_bias_pct": 0,
                "margin_bias_pct": 0,
                "wacc_pct": 8.8,
                "intrinsic_value": 120,
            },
            {
                "scenario": "bull",
                "revenue_growth_bias_pct": 4,
                "margin_bias_pct": 1.5,
                "wacc_pct": 8.2,
                "intrinsic_value": 150,
            },
        ],
        "analysis_markdown": "估值正文",
    })
    lines = report_text.splitlines()

    assert "## DCF 情境假設" in lines
    assert "- 熊市：營收成長偏差 -5%；利潤率偏差 -2%；WACC 9.5%；內在價值 NT$90" in lines
    assert "- 基本：營收成長偏差 0%；利潤率偏差 0%；WACC 8.8%；內在價值 NT$120" in lines
    assert "- 牛市：營收成長偏差 4%；利潤率偏差 1.5%；WACC 8.2%；內在價值 NT$150" in lines
    assert lines.index("## DCF 情境假設") < lines.index("估值正文")


def test_legacy_valuation_report_text_uses_exception_safe_price_targets():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(4, {
        "price_targets": {
            "熊市情境": MalformedStructuredNumber(),
            "基本情境": "NT$320",
        },
        "analysis_markdown": "估值正文",
    })

    assert "熊市情境: N/A" in report_text
    assert "基本情境: NT$320" in report_text
    assert "structured number unavailable" not in report_text


def test_legacy_valuation_report_text_excludes_non_finite_price_targets():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(4, {
        "price_targets": {
            "熊市情境": float("nan"),
            "基本情境": "NT$320",
            "牛市情境": float("inf"),
        },
        "analysis_markdown": "估值正文",
    })

    assert "熊市情境: N/A" in report_text
    assert "基本情境: NT$320" in report_text
    assert "牛市情境: N/A" in report_text
    assert "NT$nan" not in report_text
    assert "NT$inf" not in report_text


def test_legacy_valuation_report_text_preserves_scientific_notation_price_targets():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(4, {
        "price_targets": {
            "熊市情境": "1e3",
            "基本情境": "NT$320",
        },
        "analysis_markdown": "估值正文",
    })

    assert "熊市情境: NT$1,000" in report_text
    assert "基本情境: NT$320" in report_text
    assert "熊市情境: NT$13" not in report_text


def test_legacy_score_and_valuation_markdown_collapses_embedded_newlines_in_key_value_lines():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    moat_text = structured_output_to_report_text(3, {
        "moat_scores": {
            "品牌\n分數": "8\n/10",
        },
        "analysis_markdown": "護城河正文",
    })
    valuation_text = structured_output_to_report_text(4, {
        "price_targets": {"基本情境": 120},
        "valuation_summary": {
            "估值\n假設": "折現率\n偏保守",
        },
        "analysis_markdown": "估值正文",
    })
    lines = (moat_text + "\n" + valuation_text).splitlines()

    assert "品牌 分數: 8 /10" in lines
    assert "- 估值 假設: 折現率 偏保守" in lines
    assert all(
        not line.startswith(("分數", "/10", "假設", "偏保守"))
        for line in lines
    )


def test_legacy_report_text_uses_safe_analysis_markdown_fallback():
    from structured_output_normalizer import structured_output_to_report_text  # noqa: E402

    report_text = structured_output_to_report_text(
        3,
        {
            "moat_scores": {"技術": 8},
            "analysis_markdown": memoryview(b"bad-analysis-markdown"),
        },
        fallback_text="## 備援正文\\n有效 fallback",
    )

    assert "技術: 8" in report_text
    assert "## 備援正文\n有效 fallback" in report_text
    assert "memory" not in report_text
    assert "bad-analysis-markdown" not in report_text
