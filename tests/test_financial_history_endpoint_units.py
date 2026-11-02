import pytest
from financial_unit_declarations import financial_unit_declaration_issues


DATA={"years":["2022","2023","2024","2025"],"revenue_history":[3.9,4.22,5.48,6.61],
      "quant_metrics":{"unit_contract":{"money":"billion_twd"}}}


@pytest.mark.parametrize("unit",["億元","億新臺幣","億新台幣"])
def test_copied_history_endpoints_cannot_change_billion_to_yi(unit):
    text=f"供應商歷史營收從2022年3.9{unit}成長至2025年6.61{unit}，3期CAGR為19.2282%。"
    rows=financial_unit_declaration_issues(text,DATA)
    assert rows and rows[0]["reason_code"]=="history_billion_twd_endpoints_mislabeled_yi"
    assert rows[0]["period_verified"] is False


@pytest.mark.parametrize("text",[
 "供應商歷史營收從2022年39億元成長至2025年66.1億元。",
 "供應商歷史營收從2022年3.9 billion_twd成長至2025年6.61 billion_twd。",
 "假設未來營收從2027年3.9億元成長至2030年6.61億元。",
 "不可寫供應商歷史營收從2022年3.9億元成長至2025年6.61億元。",
 "同業歷史營收從2022年3.9億元成長至2025年6.61億元。",
])
def test_correct_units_forecast_other_issuer_and_correction_do_not_borrow_history(text):
    assert financial_unit_declaration_issues(text,DATA)==[]


def test_untyped_history_does_not_establish_source_unit():
    assert financial_unit_declaration_issues("供應商歷史營收從2022年3.9億元成長至2025年6.61億元。",{"years":DATA["years"],"revenue_history":DATA["revenue_history"]})==[]
