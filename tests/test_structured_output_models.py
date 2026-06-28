import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from structured_output_models import (  # noqa: E402
    Catalyst,
    ExecutiveThesisOutput,
    RecommendationStructuredOutput,
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


def test_recommendation_output_requires_next_catalysts():
    payload = _recommendation_payload()

    output = RecommendationStructuredOutput.model_validate(payload)

    assert isinstance(output.next_catalysts[0], Catalyst)
    assert output.next_catalysts[0].impact_direction == "bullish"

    with pytest.raises(ValidationError):
        RecommendationStructuredOutput.model_validate(_recommendation_payload(next_catalysts=[]))
