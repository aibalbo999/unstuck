import pytest
from cashflow_causal_claims import cashflow_driver_inference_issues


@pytest.mark.parametrize("text",[
 "自由現金流持續淨流出，營運資金依賴外部融資。",
 "自由現金流為負值，營運資金依賴 external 融資，尚待核實。",
 "負FCF不構成營運資金依賴外部融資的證明，但營運資金高度依賴外部融資。",
])
def test_negative_cashflow_does_not_prove_funding_dependence_without_a_cause_verb(text):
    assert cashflow_driver_inference_issues(text)


@pytest.mark.parametrize("text",[
 "自由現金流持續淨流出，無法證實營運資金依賴外部融資。",
 "自由現金流持續淨流出，若營運資金依賴外部融資且展期受阻，可能受壓。",
 "自由現金流持續淨流出，營運資金是否依賴外部融資尚待核實。",
 "自由現金流持續淨流出，不構成營運資金依賴外部融資的證明。",
])
def test_questions_hypotheses_and_denial_do_not_assert_dependency(text):
    assert cashflow_driver_inference_issues(text)==[]

def test_future_trigger_requests_reassessment_without_asserting_a_cashflow_driver():
    text='- 若「官方單季財報顯示營業現金流持續為負且自由現金流淨流出擴大」：建議重新評估營運資金與短債展期風險。'
    assert cashflow_driver_inference_issues(text)==[]


def test_later_reassessment_does_not_excuse_an_earlier_asserted_driver():
    assert cashflow_driver_inference_issues("負FCF顯示公司積極備料，需重新評估營運資金。")


def test_explicit_unverified_working_capital_effect_is_not_an_asserted_cause():
    assert cashflow_driver_inference_issues("cash_flow.official_income_facts 顯示 TTM 自由現金流為淨流出，具體成因與對營運資金之影響尚未核實。")==[]


def test_unverified_effect_does_not_excuse_earlier_asserted_inventory_cause():
    assert cashflow_driver_inference_issues("負FCF顯示公司積極備料，對營運資金之影響尚未核實。")
