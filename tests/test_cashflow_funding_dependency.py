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
