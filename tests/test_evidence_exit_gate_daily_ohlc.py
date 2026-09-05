"""Dated daily extremes must not borrow close prices or another day's bar."""

import pytest

from evidence_exit_gate import evaluate_report_evidence


def _snapshot(bars):
    return {"data": {
        "price_history": {"dates": ["2026-09-03", "2026-09-04"], "prices": [210.0, 210.0]},
        "daily_market_data": {"interval": "1d", "bars": bars},
    }}


def _claim(text, bars):
    result = evaluate_report_evidence(text, _snapshot(bars), sample_ratio=1.0, min_sample=1)
    assert len(result["sampled_claims"]) == 1
    return result["sampled_claims"][0]


@pytest.mark.parametrize(("kind", "word"), [("high", "高點"), ("low", "低點")])
def test_dated_daily_extreme_uses_exact_bar_field(kind, word):
    claim = _claim(
        f"- 第一壓力區：210.0 元（2026-09-04 當日{word}）。",
        [{"date": "2026-09-04", kind: 210.0, "close": 208.0}],
    )
    assert claim["status"] == "verified"
    assert claim["matched_path"] == f"data.daily_market_data.bars[2026-09-04].{kind}"
    assert claim["candidate_count"] == 1


def test_live_daily_high_phrase_does_not_match_nearby_close():
    claim = _claim(
        "* **第一壓力區：** 210.0 元（2026-09-04 當日高點與 08-10 近期高點附近）。",
        [{"date": "2026-09-04", "high": 210.0, "low": 203.5, "close": 208.0}],
    )
    assert claim["matched_path"] == "data.daily_market_data.bars[2026-09-04].high"
    assert claim["matched_value"] == 210.0
    assert claim["diff_pct"] == 0.0


@pytest.mark.parametrize(("kind", "word"), [("high", "高點"), ("low", "低點")])
def test_dated_daily_extreme_mismatch_cannot_borrow_equal_close(kind, word):
    claim = _claim(
        f"- 關鍵支撐：210 元（2026-09-04 當日{word}）。",
        [{"date": "2026-09-04", kind: 190.0, "close": 210.0}],
    )
    assert claim["status"] == "mismatch"
    assert claim["verification_reason_code"] == "snapshot_value_mismatch"
    assert claim["matched_value"] == 190.0


@pytest.mark.parametrize("bars", [
    [],
    [{"date": "2026-09-03", "high": 210.0}],
    [{"date": "2026-09-04", "high": None, "low": 210.0, "close": 210.0}],
    [{"date": "2026-09-04", "low": 210.0, "close": 210.0}],
])
def test_missing_daily_date_or_field_does_not_borrow_equal_values(bars):
    claim = _claim("- 近期壓力：210 元（2026-09-04 當日高點）。", bars)
    assert claim["status"] == "unverifiable"
    assert claim["candidate_count"] == 0
    assert claim["matched_path"] == ""


@pytest.mark.parametrize("text", [
    "- 近期壓力：210 元（2026-09-03 與 2026-09-04 當日高點）。",
    "- 近期壓力：210 元（2026-09-03 高點與 2026-09-04 高點）。",
])
def test_multiple_daily_dates_do_not_pick_the_nearest_equal_price(text):
    claim = _claim(text, [
        {"date": "2026-09-03", "high": 190.0},
        {"date": "2026-09-04", "high": 210.0},
    ])
    assert claim["status"] == "unverifiable"
    assert claim["candidate_count"] == 0


def test_duplicate_daily_dates_do_not_pick_the_equal_high():
    claim = _claim("- 壓力：210 元（2026-09-04 當日高點）。", [
        {"date": "2026-09-04", "high": 190.0},
        {"date": "2026-09-04", "high": 210.0},
    ])
    assert claim["status"] == "unverifiable"
    assert claim["candidate_count"] == 0


def test_dated_low_with_high_word_in_source_does_not_borrow_high():
    claim = _claim(
        "- 支撐：210 元（2026-09-04 當日低點；high 不是本欄位）。",
        [{"date": "2026-09-04", "high": 210.0, "low": 190.0}],
    )
    assert claim["status"] == "mismatch"
    assert claim["matched_path"] == "data.daily_market_data.bars[2026-09-04].low"


def test_dated_extreme_wording_does_not_reroute_non_price_claims():
    snapshot = _snapshot([{"date": "2026-09-04", "high": 230.0}])
    snapshot["data"]["revenue"] = 210.0
    result = evaluate_report_evidence(
        "- 營收：210 億（2026-09-04 當日高點）。", snapshot, sample_ratio=1.0, min_sample=1,
    )
    assert result["sampled_claims"][0]["matched_path"] == "data.revenue"


def test_dated_volume_high_does_not_borrow_same_value_from_price_high():
    claim = _claim(
        "- 成交量：210 張（2026-09-04 當日高點）。",
        [{"date": "2026-09-04", "high": 210.0, "volume": 400.0}],
    )
    assert claim["status"] != "verified"
    assert claim["matched_path"] != "data.daily_market_data.bars[2026-09-04].high"


def test_cash_flow_word_suffix_is_not_a_daily_low_price_label():
    snapshot = _snapshot([{"date": "2026-09-04", "low": 210.0, "close": 230.0}])
    snapshot["data"]["free_cash_flow"] = 400.0
    result = evaluate_report_evidence(
        "- Free Cash Flow：210（2026-09-04）。", snapshot, sample_ratio=1.0, min_sample=1,
    )
    claim = result["sampled_claims"][0]
    assert claim["status"] == "mismatch"
    assert claim["matched_path"] == "data.free_cash_flow"


def test_dated_high_label_with_explicit_price_history_close_keeps_legacy_basis():
    claim = _claim(
        "- 近期壓力：210 元（2026-09-04 高點，引用 price_history 收盤價）。",
        [{"date": "2026-09-04", "high": 230.0, "close": 210.0}],
    )
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.price_history[2026-09-04].prices[1]"


@pytest.mark.parametrize("description", ["2026-09-04 的當日高點", "當日高點，2026-09-04"])
def test_daily_high_date_word_order_cannot_fall_back_to_close(description):
    claim = _claim(f"- 壓力：210 元（{description}）。", [
        {"date": "2026-09-04", "high": 230.0, "close": 210.0},
    ])
    assert claim["status"] == "mismatch"
    assert claim["matched_path"] == "data.daily_market_data.bars[2026-09-04].high"


@pytest.mark.parametrize("description", ["收盤價", "價格基準"])
def test_explicit_legacy_close_and_price_basis_keep_price_history(description):
    claim = _claim(
        f"- 關鍵壓力：210 元（2026-09-04 {description}）。",
        [{"date": "2026-09-04", "high": 230.0, "close": 210.0}],
    )
    assert claim["status"] == "verified"
    assert claim["matched_path"] == "data.price_history[2026-09-04].prices[1]"
