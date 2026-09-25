"""Unassessed target explanations are not prices or directional evidence."""

from copy import deepcopy

import pytest


UNASSESSED_TARGETS = [
    "N/A／未評估（需觀察 2026 Q3/Q4 毛利率是否能從 24.1% 回升）",
    "N/A／未評估（股價於 GDS 發行價 908.32 元附近震盪，缺乏明確方向性催化）",
    "N/A／未評估（5年營收 CAGR 為 -4.8%，長期成長路徑不明）",
    "Ｎ／Ａ／未評估（需觀察２０２６年毛利率２４．１％與發行價９０８．３２元）",
    "NA (await 2026 Q3/Q4 financial results; historical issue price NT$908.32)",
    "not assessed (2026 margin 24.1%, historical price NT$908.32)",
    "未評估（需確認 2026 年財報，發行價 908.32 元僅為歷史參考）",
    "資料不足（2026 Q3 毛利率 24.1% 仍待確認）",
    "不適用（歷史發行價 908.32 元不能作為估值）",
    "12個月目標價：N/A（需觀察 2026 Q3）",
    "基本情境：N/A（發行價 908.32 元僅為歷史參考）",
    "N/A（參考舊目標價 NT$1200，尚未評估本次目標）",
    "N/A（前次 target price NT$1200 並未採用；待財報重新評估）",
    "N/A（資料待更新（歷史目標價 NT$1200 僅供參考））",
    "N/A（目前目標價 NT$1200 僅是外部共識參考，尚未採用）",
]


@pytest.mark.parametrize("value", UNASSESSED_TARGETS)
def test_target_parser_rejects_numbers_in_unassessed_explanations(value):
    from price_parser import extract_target_price_numbers

    assert extract_target_price_numbers(value) == []


@pytest.mark.parametrize(("value", "expected"), [
    ("目標價 NT$110（EPS N/A）", [110.0]),
    ("目標價 NT$100-160（EPS 未評估）", [100.0, 160.0]),
    ("目標價由 NT$100 上調至 NT$110", [110.0]),
    ("先前 N/A，現改為目標價 NT$110", [110.0]),
    ("N/A（等待 2026 年財报）；目前目標價 NT$110", [110.0]),
    ("N/A，但目前目標價 NT$110", [110.0]),
    ("NA; current target price USD 110", [110.0]),
    ("N/A（本次目標價 NT$110）", [110.0]),
    ("N/A（舊目標價 NT$1200；本次目標價 NT$110）", [110.0]),
    ("N/A（參考舊目標價 NT$1200）；目前目標價 NT$110", [110.0]),
    ("N/A；目前目標價 NT$110（前次目標價 NT$1200 並未採用）", [110.0]),
    ("N/A（等待財報）；目前目標價 NT$100–160", [100.0, 160.0]),
    ("N/A；目標價由 NT$100 上調至 NT$110", [110.0]),
    ("N/A；目標價由 NT$1,100 上調至 NT$1,500", [1500.0]),
    ("N/A（等待財報）；目前目標價 NT$1,100–1,500", [1100.0, 1500.0]),
])
def test_missing_annotation_does_not_hide_an_explicit_numeric_target(value, expected):
    from price_parser import extract_target_price_numbers

    assert extract_target_price_numbers(value) == expected


@pytest.mark.parametrize("label", ["避免", "持有", "買入", "放空"])
def test_live_unassessed_horizons_keep_missing_alignment_warning(label):
    from reporting.content_credibility import evaluate_content_credibility
    from reporting.content_credibility_target_prices import target_price_candidates

    context = {
        "pipeline_id": "v3", "data": {"current_price": 948.0},
        "parsed": {
            "recommendation": {
                "建議": label,
                "短期目標（3個月）": UNASSESSED_TARGETS[1],
                "中期目標（6個月）": UNASSESSED_TARGETS[0],
                "長期目標（12個月）": "N/A／未評估（前瞻預期未驗證，資料不足）",
            },
            "short_setup": {
                "entry_trigger": "目前不建立空方部位；等待可驗證條件後重新評估。",
                "downside_target": "N/A", "cover_stop": "N/A",
                "squeeze_risk": "借券不足，需確認軋空風險。",
                "thesis_invalidation": "後續財報改善時重新評估。",
            },
        },
    }
    original = deepcopy(context)
    assert target_price_candidates(context["parsed"]) == []
    result = evaluate_content_credibility(context)
    alignment = next(c for c in result["checks"] if c["id"] == "recommendation_target_alignment")
    assert alignment["status"] == "warning"
    assert alignment["details"]["target_price"] is None
    assert "missing_price_alignment_inputs" in {i["id"] for i in result["warnings"]}
    assert context == original


def test_horizon_selection_cannot_discard_the_unassessed_declaration():
    from reporting.content_credibility_target_prices import target_price_candidates

    parsed = {"recommendation": {"12個月": "N/A／未評估；12個月等待 2026 年財報"}}
    assert target_price_candidates(parsed) == []


def test_unassessed_horizon_explanation_cannot_hide_a_later_current_target():
    from reporting.content_credibility_target_prices import target_price_candidates

    value = "N/A（12個月資料尚未齊備）；目前目標價 NT$1100"
    candidates = target_price_candidates({"recommendation": {"12個月": value}})
    assert len(candidates) == 1
    assert candidates[0]["price"] == 1100.0


def test_mixed_unassessed_text_preserves_multiple_current_horizons():
    from reporting.content_credibility_target_prices import target_price_candidates

    value = "N/A（先前未評估）；12個月目標價 NT$160；6個月目標價 NT$140"
    candidates = target_price_candidates({"recommendation": {"12個月": value, "6個月": value}})
    assert [(row["label"], row["price"]) for row in candidates] == [("12個月", 160.0), ("6個月", 140.0)]


def test_legacy_scenario_parser_does_not_restore_unassessed_prices_from_full_lines():
    from structured_output_parser import parse_price_targets_from_text

    text = "[目標股價]\n基本情境：" + UNASSESSED_TARGETS[1] + "\n[/目標股價]"
    assert parse_price_targets_from_text(text) == {}


def test_calibration_does_not_upgrade_hold_from_unassessed_explanation():
    from recommendation_calibration import calibrate_recommendation_summary

    recommendation = {
        "recommendation": "持有", "current_price": 948.0,
        "target_12m": UNASSESSED_TARGETS[0], "confidence": "7/10",
    }
    assert calibrate_recommendation_summary(recommendation, data_trust={"status": "fresh"}) == recommendation
