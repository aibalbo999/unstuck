import pytest
from cashflow_causal_claims import cashflow_driver_inference_issues


def test_negative_fcf_explicitly_does_not_constitute_driver_proof():
    text="反證：負自由現金流不構成擴產或備料之經營動機證明，具體資金占用成因仍缺乏管理層原件驗證。"
    assert cashflow_driver_inference_issues(text)==[]


@pytest.mark.parametrize("text",[
    "負自由現金流顯示公司正在積極備料，但不構成訂單確立之證明。",
    "負自由現金流不構成擴產證明，但顯示公司正在積極備料。",
    "負自由現金流不構成擴產證明，然而反映公司存貨占用資金。",
    "負自由現金流顯示公司正在擴產，後續資料不足不構成否定理由。",
])
def test_positive_assertion_not_erased_by_negated_proof(text):
    rows=cashflow_driver_inference_issues(text)
    assert rows and rows[0]["reason_code"]=="cashflow_total_does_not_establish_operating_driver"


def test_negated_proof_then_explicit_hypothesis_stays_uncertain():
    assert cashflow_driver_inference_issues("負自由現金流不構成擴產證明，但可能反映公司備料，仍待核實。") == []
