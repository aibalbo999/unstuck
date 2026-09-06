"""Explicit technical and saved recommendation evidence cannot borrow equal values."""

import pytest

from evidence_exit_gate import evaluate_report_evidence


def _snapshot(**technical):
    return {"data": {"technical_indicators": {
        "availability": "available", "as_of": "2026-09-04", "source": "yfinance", "sma_20": 205.425,
        "volume_sma_20": 205.4, "sma_200": 205.4, **technical,
    }, "risk_price": 205.4, "current_price": 205.4}}


def _claims(text, snapshot):
    return evaluate_report_evidence(text, snapshot, sample_ratio=1.0, min_sample=1)["sampled_claims"]


@pytest.mark.parametrize("basis", ["20日均線", "SMA20", "SMA_20", "20 日 SMA", "2026-09-04 的 20 日均線"])
def test_sma_support_only_matches_its_exact_period(basis):
    claim = _claims(f"支撐位：205.4 元（{basis}）", _snapshot())[0]
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.technical_indicators.sma_20"
    assert claim["candidate_count"] == 1


def test_sma_mismatch_cannot_borrow_equal_volume_or_risk_price():
    claim = _claims("支撐位：205.4 元（20日均線）", _snapshot(sma_20=190))[0]
    assert claim["status"] == "mismatch"
    assert claim["matched_value"] == 190


@pytest.mark.parametrize("technical", [
    {"sma_20": None}, {"sma_20": "205.4"}, {"sma_20": True}, {"sma_20": float("nan")},
    {"sma_20": 0}, {"availability": "unavailable"}, {"as_of": None}, {"as_of": "bad-date"},
    {"source": None}, {"source": "N/A"}, {"missing_indicators": 1},
])
def test_unavailable_sma_never_uses_other_equal_fields(technical):
    claim = _claims("支撐位：205.4 元（20日均線）", _snapshot(**technical))[0]
    assert claim["status"] == "unverifiable"
    assert claim["candidate_count"] == 0


@pytest.mark.parametrize("basis", [
    "EMA20", "20日指數均線", "20日均線與200日均線", "20日均線與當日收盤",
    "20日均線與205.4元壓力", "新聞提及20日均線", "券商給予20日均線",
    "2026-09-03 的20日均線", "2026-09-03與2026-09-04的20日均線",
    "20日均線 unavailable", "成交量20日均線", "volume_sma_20",
    "20日均線與前期平台", "20日均線與另一指標共振",
])
def test_ambiguous_sma_basis_fails_closed(basis):
    claim = _claims(f"支撐位：205.4 元（{basis}）", _snapshot())[0]
    assert claim["status"] == "unverifiable"
    assert claim["candidate_count"] == 0


def test_missing_sma_exact_key_does_not_match_sma_200():
    snapshot = _snapshot()
    del snapshot["data"]["technical_indicators"]["sma_20"]
    assert _claims("支撐位：205.4 元（20日均線）", snapshot)[0]["candidate_count"] == 0


def test_late_ambiguity_is_not_hidden_by_claim_display_truncation():
    text = "支撐位：205.4 元（20日均線；" + "背景說明" * 50 + "；另有200日均線）"
    assert _claims(text, _snapshot())[0]["candidate_count"] == 0


@pytest.mark.parametrize("technical", [{"availability": "partial"}, {"missing_indicators": ["sma_20"]}])
def test_partial_snapshot_uses_only_present_available_indicator(technical):
    claim = _claims("支撐位：205.4 元（20日均線）", _snapshot(**technical))[0]
    assert claim["status"] == ("unverifiable" if "missing_indicators" in technical else "verified")


def test_same_named_nested_field_cannot_impersonate_canonical_sma():
    snapshot = _snapshot(sma_20=190)
    snapshot["data"]["other"] = {"technical_indicators": {"sma_20": 205.4}}
    claim = _claims("支撐位：205.4 元（20日均線）", snapshot)[0]
    assert claim["status"] == "mismatch" and claim["candidate_count"] == 1


@pytest.mark.parametrize("snapshot", [{"data": "unavailable"}, {"data": {"technical_indicators": ["invalid"]}}])
def test_malformed_technical_container_is_unverifiable_not_a_gate_crash(snapshot):
    claim = _claims("支撐位：205.4 元（20日均線）", snapshot)[0]
    assert claim["status"] == "unverifiable"


def _recommendation_snapshot():
    return {"data": {"current_price": 1380, "target_price": 1380}, "rerun_context": {
        "parsed": {"recommendation": {"短期目標（3個月）": "1280 元", "中期目標（6個月）": "1380 元", "長期目標（12個月）": "1480 元"}},
    }}


def test_compact_final_row_binds_each_horizon_not_neighboring_targets():
    claims = _claims("| 最終投資建議 | 買入；3個月：1280元；6個月：1380元；12個月：1480元 |", _recommendation_snapshot())
    assert len(claims) == 3
    assert [item["matched_path"] for item in claims] == [
        f"rerun_context.parsed.recommendation.{label}" for label in
        ("短期目標（3個月）", "中期目標（6個月）", "長期目標（12個月）")
    ]
    assert all(item["status"] == "verified" and item["candidate_count"] == 1 for item in claims)


def test_compact_horizon_outside_final_row_is_not_canonical_recommendation():
    claims = _claims("一般觀察：6個月：1380元", _recommendation_snapshot())
    assert claims and all(item["status"] == "unverifiable" for item in claims)


def test_final_recommendation_keyword_in_comment_does_not_create_a_final_row():
    claims = _claims("| 評論 | 並非最終投資建議；6個月：1380元 |", _recommendation_snapshot())
    assert claims and all(item["status"] == "unverifiable" for item in claims)


def test_compact_missing_horizon_cannot_borrow_equal_other_horizon():
    snapshot = _recommendation_snapshot()
    del snapshot["rerun_context"]["parsed"]["recommendation"]["中期目標（6個月）"]
    snapshot["rerun_context"]["parsed"]["recommendation"]["短期目標（3個月）"] = "1380 元"
    assert _claims("| 最終投資建議 | 6個月：1380元 |", snapshot)[0]["candidate_count"] == 0


def test_compact_horizon_mismatch_remains_visible():
    claim = _claims("| 最終投資建議 | 6個月：1480元 |", _recommendation_snapshot())[0]
    assert claim["status"] == "mismatch" and claim["matched_value"] == 1380


@pytest.mark.parametrize("text", [
    "| 最終投資建議 | 3個月：1280元 6個月：1380元 |",
    "| 最終投資建議 | 6個月：1380元；6個月：1480元 |",
])
def test_ambiguous_compact_horizons_are_not_verified(text):
    assert all(item["status"] == "unverifiable" for item in _claims(text, _recommendation_snapshot()))


@pytest.mark.parametrize("label", ["情緒過熱評分", "過熱評分"])
def test_overheat_scores_remain_analysis_metadata(label):
    claim = _claims(f"{label}：7.5（模型評估）", {"data": {"score": 7.5, "current_price": 7.5}})[0]
    assert claim["status"] == "unverifiable"
    assert claim["verification_reason_code"] == "analysis_metadata_not_evidence"
