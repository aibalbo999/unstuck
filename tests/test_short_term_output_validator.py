"""Regression evidence from the 2026-09-19 1623.TW live integration."""

import pytest

from validators import validate_analysis_output
from final_audit import run_final_report_audit


def source_data(unit="shares"):
    return {
        "ticker": "1623.TW", "company_name": "大東電", "current_price": 208.5,
        "daily_market_data": {"volume_unit": unit, "bars": [
            {"date": "2026-09-09", "volume": 331068},
            {"date": "2026-09-18", "volume": 88002}]},
        "technical_indicators": {"volume_unit": unit, "volume_sma_5": 46067,
                                 "volume_sma_20": 83656},
        "chip_data": {"twse_margin_short_sales": {"margin_sale": 5,
                        "short_sale": None, "margin_balance": 344, "source": "TWSE OpenAPI MI_MARGN"}},
    }


def test_live_volume_regression_is_rejected_and_enters_final_audit_repair():
    text = "9 月 9 日曾伴隨單日成交量擴大至 331,068 張，推升收盤價至 218.5 元。"
    issues = validate_analysis_output(22, text, source_data())
    assert any("成交量單位" in issue for issue in issues)
    result = run_final_report_audit({"pipeline_id": "v4", "agent_sequence": [22],
        "data": source_data(), "analyses": {22: text}}, append_section=False)
    assert any("成交量單位" in issue for issue in result["critical"])
    assert any("成交量單位" in issue for issue in result["repair_agent_issues"][22])


def test_live_margin_sale_regression_is_rejected():
    text = "當日借券賣出 2,000 股、還券 1,000 股；融券賣出 5 張。"
    issues = validate_analysis_output(23, text, source_data())
    assert any("short_sale" in issue and "null" in issue for issue in issues)


@pytest.mark.parametrize("text", ["成交量為 331,068 股。", "成交量約 331.068 張。",
                                  "成交量約 331 張。", "20 日均量 83,656 股。",
                                  "若成交量達到 500 張，才考慮進場。"])
def test_valid_volume_units_and_explicit_future_conditions_pass(text):
    assert not validate_analysis_output(22, text, source_data())


@pytest.mark.parametrize("text", ["成交量為 331,068 張。", "曾出現 331,068 張的大幅放量。",
                                  "5 日均量 46,067 張與 20 日均量 83,656 張。"])
def test_raw_share_values_cannot_be_relabelled_as_lots(text):
    assert any("成交量單位" in issue for issue in validate_analysis_output(22, text, source_data()))


def test_unknown_volume_unit_is_not_guessed_from_source_name():
    data = source_data(None)
    data["daily_market_data"]["source"] = "yfinance 5y history"
    assert any("單位未確認" in issue for issue in validate_analysis_output(22, "成交量為 331,068 股。", data))
    assert not validate_analysis_output(22, "成交量原始數值 331068，單位未確認。", data)


@pytest.mark.parametrize("text", ["融資賣出 5 張。", "融資餘額為 344 張。融券賣出資料不足。",
                                  "若融券賣出達 5 張，應重新檢查。", "不能稱為融券賣出 5 張。"])
def test_financing_and_missing_or_conditional_short_sales_do_not_raise(text):
    assert not validate_analysis_output(23, text, source_data())


def test_explicit_zero_and_nonzero_short_sales_are_distinct_from_null():
    data = source_data()
    assert validate_analysis_output(23, "融券賣出 0 張。", data)
    data["chip_data"]["twse_margin_short_sales"]["short_sale"] = 0
    assert not validate_analysis_output(23, "融券賣出 0 張。", data)
    assert validate_analysis_output(23, "融券賣出 5 張。", data)
    data["chip_data"]["twse_margin_short_sales"]["short_sale"] = 5
    assert not validate_analysis_output(23, "融券賣出 5 張。", data)


@pytest.mark.parametrize("text", ["成交量為 331,068 張。", "融券賣出 5 張。"])
def test_final_decision_cannot_repeat_upstream_unit_or_field_error(text):
    assert validate_analysis_output(24, text, source_data())


def test_missing_credit_counts_are_repairable_in_final_audit():
    result = run_final_report_audit({"pipeline_id": "v4", "agent_sequence": [23],
        "data": source_data(), "analyses": {23: "融券賣出 5 張。"}}, append_section=False)
    assert any("short_sale" in issue for issue in result["repair_agent_issues"][23])


def test_known_lot_volume_is_not_reinterpreted_as_shares():
    data = source_data("lots")
    assert not validate_analysis_output(22, "成交量為 331,068 張。", data)
    assert validate_analysis_output(22, "成交量為 331,068 股。", data)


def test_credit_table_and_markdown_labels_still_validate_null():
    assert validate_analysis_output(23, "| **融券賣出** | 5 張 |", source_data())


def test_credit_share_conversion_is_numeric_not_unit_relabelling():
    data = source_data()
    data["chip_data"]["twse_margin_short_sales"]["short_sale"] = 5
    assert not validate_analysis_output(23, "融券賣出 5,000 股。", data)
    assert validate_analysis_output(23, "融券賣出 5 股。", data)


@pytest.mark.parametrize("data", [None, {}, {"daily_market_data": []},
                                  {"daily_market_data": {"volume_unit": {}, "bars": None}},
                                  {"daily_market_data": "bad", "technical_indicators": 42},
                                  {"chip_data": []}, {"chip_data": {"twse_margin_short_sales": []}}])
def test_malformed_optional_source_metadata_does_not_abort_quality_gate(data):
    assert isinstance(validate_analysis_output(24, "成交量為 1000 股。融券賣出 5 張。", data), list)


def test_foreign_or_unknown_market_cannot_assume_taiwan_lot_conversion():
    for ticker in ("AAPL", "", None):
        data = source_data()
        data["ticker"] = ticker
        assert any("台股" in issue for issue in validate_analysis_output(22, "成交量約 331.068 張。", data))
        assert not validate_analysis_output(22, "成交量為 331,068 股。", data)


def test_unidentified_credit_provider_does_not_assume_twse_lots():
    data = source_data()
    data["chip_data"]["twse_margin_short_sales"].pop("source")
    assert any("單位未確認" in issue for issue in validate_analysis_output(23, "融資賣出5張。", data))


def test_previous_and_current_credit_balances_keep_their_own_source_fields():
    data = source_data()
    credit = data["chip_data"]["twse_margin_short_sales"]
    credit.update(margin_previous_balance=349, short_previous_balance=10, short_balance=7)
    assert not validate_analysis_output(23, "昨日融資餘額349張，今日融資餘額344張。", data)
    assert not validate_analysis_output(23, "前日融券餘額10張，今日融券餘額7張。", data)
    assert not validate_analysis_output(23, "融資前日餘額349張，融券前日餘額10張。", data)
    assert validate_analysis_output(23, "昨日融資餘額344張，今日融資餘額349張。", data)
    credit["margin_previous_balance"] = None
    assert any("margin_previous_balance" in issue for issue in validate_analysis_output(23, "前日融資餘額349張。", data))
