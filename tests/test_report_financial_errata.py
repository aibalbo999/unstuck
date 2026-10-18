"""Source-bound unit errata retain the original analysis and all quality gates."""

import hashlib
import json
from copy import deepcopy

import pytest

from financial_money_claims import financial_money_claim_issues
from report_analysis_evidence import capture_analysis_evidence


def snapshot(text):
    original = {"ticker": "TEST.TW", "financial_currency": "TWD", "years": ["2024", "2025"],
                "revenue_history": [4.0, 6.61], "net_income_history": [0.1, 0.15],
                "fcf_history": [0.77, 1.28], "revenue_ttm_raw": 35364397056,
                "unit_contract": {"money": "billion_twd"}}
    original["analysis_input_hash"] = hashlib.sha256(json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    original["analysis_input_cutoff"] = "2026-09-24T02:00:00+08:00"
    return {"data": {**original, "fcf_history": [100, 200]},
            "analysis_evidence": capture_analysis_evidence({"data": original}),
            "refreshed_without_analysis_rerun": True,
            "rerun_context": {"analyses": {"9": text}},
            "final_audit": {"status": "blocked", "critical": ["原警示"]}}


@pytest.mark.parametrize(("text", "correct"), [
    ("2025年營收為6.61億元。", 66.1),
    ("2024年FCF為0.77億元。", 7.7),
    ("2025年自由現金流為1.28億元。", 12.8),
    ("TTM營收為35.36億元。", 353.64397056),
])
def test_errata_uses_preserved_input_not_refreshed_values(text, correct):
    from report_financial_errata import financial_errata
    saved = snapshot(text); before = deepcopy(saved)
    rows = financial_errata(saved)
    assert len(rows) == 1
    assert rows[0]["corrected_value"] == pytest.approx(correct)
    assert rows[0]["source_path"].startswith("analysis_evidence.sections.analysis_input.data.")
    assert rows[0]["analysis_input_cutoff"] == "2026-09-24T02:00:00+08:00"
    assert saved == before


@pytest.mark.parametrize("text", [
    "預估2025年營收6.61億元。", "2025年營收6.61億美元。", "2023年FCF為0.77億元。",
    "2025年Q2自由現金流1.28億元。", "2025年每股淨利0.15元。", "2025年營收為66.1億元。",
    "同業甲公司2025年營收6.61億元。",
    "同業甲公司，2025年營收為6.61億元。", "甲公司：2025年營收為6.61億元。",
    "蘋果，2025年營收為6.61億元。", "蘋果，根據財務數據，2025年營收為6.61億元。",
    "同業甲公司（2025年營收為6.61億元）。", "蘋果(2025年營收為6.61億元)。",
    "甲公司(根據財務資料，2025年營收為6.61億元)。",
])
def test_unknown_period_forecasts_other_currencies_and_correct_values_are_not_rewritten(text):
    from report_financial_errata import financial_errata
    assert financial_errata(snapshot(text)) == []


def test_corrupt_original_input_never_borrows_new_data_to_correct_old_prose():
    from report_financial_errata import financial_errata
    saved = snapshot("2025年FCF為1.28億元。")
    saved["analysis_evidence"]["sections"]["analysis_input"]["data"]["fcf_history"] = [3, 4]
    assert financial_errata(saved) == []


def test_repeated_amounts_in_one_bound_line_keep_independent_metric_and_token_positions():
    from report_financial_errata import financial_errata, correct_financial_summary
    text = '2025年自由現金流1.28億元（基於2025年淨利0.15億元與自由現金流1.28億元）。'
    saved = snapshot(text)
    rows = financial_errata(saved)
    assert len(rows) == 3
    corrected = correct_financial_summary(text, saved)
    assert corrected == '2025年自由現金流12.8億元（基於2025年淨利1.5億元與自由現金流12.8億元）。'


@pytest.mark.parametrize("text", ["2024年FCF為0.77億元。", "TTM營收為35.36億元。"])
def test_future_output_rejects_annual_fcf_and_ttm_unit_errors(text):
    saved = snapshot(text)
    original = saved["analysis_evidence"]["sections"]["analysis_input"]["data"]
    assert any("財務金額單位紅線" in issue for issue in financial_money_claim_issues(text, original))
