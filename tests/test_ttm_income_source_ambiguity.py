import pytest
from evidence_exit_gate import evaluate_report_evidence


@pytest.fixture
def qualified_official_source(monkeypatch):
    import official_income_prompt
    import evidence_official_income_claims
    monkeypatch.setattr(official_income_prompt,"official_income_prompt_facts",lambda data:{
        "currency":"TWD","report_scope":"individual","net_income_ttm_raw":819804000})
    monkeypatch.setattr(evidence_official_income_claims,"official_income_claim",lambda *a,**k:None)
    return {"ticker":"1623.TW","company_name":"大東電","financial_currency":"TWD","net_income_ttm_raw":860640000}


@pytest.mark.parametrize("amount",["8.19804","99"])
def test_bare_ttm_does_not_borrow_a_different_vendor_basis(qualified_official_source,amount):
    text=f"供應商歷史數列未核實，官方年度明細不足。此外，TTM淨利為{amount}億元。"
    rows=evaluate_report_evidence(text,{"data":qualified_official_source})["sampled_claims"]
    row=next(x for x in rows if x.get("financial_metric")=="淨利")
    assert row["status"]=="unverifiable" and row["raw_text"]==text
    assert row["verification_reason_code"]=="official_income_scope_unbound_no_vendor_fallback"
    assert row["independent_primary_source_verified"] is False


def test_explicit_vendor_record_retains_snapshot_comparator(qualified_official_source):
    rows=evaluate_report_evidence("大東電供應商TTM淨利記錄為8.6064億元。",{"data":qualified_official_source})["sampled_claims"]
    row=next(x for x in rows if x.get("financial_metric")=="淨利")
    assert row["status"]=="verified" and row["independent_primary_source_verified"] is False
