from evidence_exit_gate import _check_claim


def test_generated_target_does_not_verify_itself():
    claim = {"label": "1–2 週目標", "raw_text": "1–2 週目標：95.70 元", "reported_value": 95.7, "unit": "元"}
    values = [{"path": "rerun_context.structured_outputs.24.target_price", "value": 95.7}]
    result = _check_claim(claim, values, tolerance_pct=1)
    assert result["status"] == "unverifiable"
    assert result["verification_reason_code"] == "generated_analysis_not_independent_evidence"
    assert result["verification_scope"] == "saved_analysis_consistency"


def test_generated_level_cannot_mask_missing_market_evidence():
    claim = {"label": "壓力", "raw_text": "壓力：95.70 元", "reported_value": 95.7, "unit": "元"}
    result = _check_claim(claim, [{"path": "rerun_context.structured_outputs.24.resistance_level", "value": 95.7}], tolerance_pct=1)
    assert result["status"] == "unverifiable"


def test_independent_raw_fact_still_verifies():
    claim = {"label": "Beta", "raw_text": "Beta：0.82", "reported_value": .82, "unit": ""}
    result = _check_claim(claim, [{"path": "data.beta", "value": .82}], tolerance_pct=1)
    assert result["status"] == "verified"


def test_one_bad_fact_is_not_diluted_by_correct_facts():
    from evidence_exit_gate import evaluate_report_evidence
    from report_publication_gate import assert_report_publishable, ReportPublicationBlockedError
    import pytest
    result = evaluate_report_evidence("- Beta: 9.99\n- 最新價格: 100 元\n- 52週最高價: 110 元", {"data": {"beta": .82, "current_price": 100, "week_52_high": 110}}, sample_ratio=1, min_sample=1)
    assert result["failed_count"] >= 1
    assert result["verdict"] == "rejected"
    with pytest.raises(ReportPublicationBlockedError):
        assert_report_publishable({"evidence_exit_gate": result})
