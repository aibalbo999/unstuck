"""Tracking must not display explanation numbers as actionable targets."""

import pytest


def test_tracking_keeps_unassessed_targets_and_progress_unavailable():
    from decision_tracking import build_decision_tracking

    tracking = build_decision_tracking({
        "recommendation": "避免", "current_price": "NT$948.00",
        "target_3m": "N/A／未評估（歷史發行價 908.32 元，等待重評）",
        "target_6m": "N/A／未評估（需觀察 2026 Q3/Q4 毛利率 24.1%）",
        "target_12m": "Ｎ／Ａ（２０２６年財報尚未取得）",
    }, snapshot={"data": {"current_price": 950.0}})

    assert tracking["initial_price"] == 948.0
    assert tracking["latest_price"] == 950.0
    assert tracking["return_pct"] == pytest.approx(0.211, abs=0.0001)
    for field in ("target_3m", "target_6m", "target_12m"):
        assert tracking[field] is None
        assert tracking["target_comparisons"][field]["status"] == "unavailable"
    assert tracking["target_12m_gap_pct"] is None
    assert tracking["target_12m_progress_pct"] is None
    assert tracking["tracking_summary_status"] == "尚無法比較目標"


def test_target_parser_opt_in_preserves_generic_price_callers():
    from decision_tracking import parse_optional_price

    explanation = "N/A（歷史發行價 908.32 元，等待 2026 年財報）"
    assert parse_optional_price(explanation) == 908.32
    assert parse_optional_price(explanation, target_context=True) is None
    assert parse_optional_price("NT$948.00") == 948.0


def test_tracking_preserves_real_target_and_numeric_price_without_confusing_eps_missing():
    from decision_tracking import build_decision_tracking

    tracking = build_decision_tracking({
        "recommendation": "買入", "current_price": 100.0,
        "target_3m": "目標價 NT$110（EPS N/A）",
        "target_6m": "先前 N/A，目前目標價 NT$120",
        "target_12m": 130.0,
    }, snapshot={"data": {"current_price": 105.0}})
    assert tracking["target_3m"] == 110.0
    assert tracking["target_6m"] == 120.0
    assert tracking["target_12m"] == 130.0
    assert tracking["target_12m_gap_pct"] == pytest.approx(23.8095)
