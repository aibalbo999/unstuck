from copy import deepcopy
import pytest
from test_official_financial_claim_binding import projected
from evidence_exit_gate import evaluate_report_evidence


def claims(text,data=None):
    result=evaluate_report_evidence(text,{'data':projected() if data is None else data})
    return [c for c in result['sampled_claims'] if c.get('official_debt_component')]


@pytest.mark.parametrize('amount,status',[('0.005','verified'),('0.0005','mismatch'),('-0.005','mismatch')])
def test_exact_component_is_checked_not_hidden_by_total(amount,status):
    rows=claims('大東電個別2026-06-30長期借款流動部分為'+amount+'億元。')
    assert len(rows)==1 and rows[0]['status']==status
    assert rows[0]['matched_value']==0.005
    assert rows[0]['financial_period']=='2026-06-30'


@pytest.mark.parametrize('text',[
 '同業華通個別2026-06-30長期借款流動部分為0.005億元。',
 '華通個別2026-06-30長期借款流動部分為0.005億元。',
 '大東電合併2026-06-30長期借款流動部分為0.005億元。',
 '大東電個別2025-06-30長期借款流動部分為0.005億元。',
 '大東電個別長期借款流動部分為0.005億元。',
 '大東電個別2026-06-30長期借款流動部分為0.005億港元。',
 '大東電個別2026-06-30長期借款流動部分為0.005億歐元。',
 '大東電個別2026-06-30長期借款流動部分預期為0.005億元。',
 '大東電個別2026-06-30長期借款流動部分為0.005億元（同業華通）。',
 '大東電個別2026-06-30長期借款流動部分為0.005億元（華通）。',
 '大東電個別2026-06-30長期借款流動部分為0.005億元，華通資料。',
 '大東電個別2026-06-30長期借款流動部分為0.005億元，此為華通資料。',
])
def test_unknown_scope_never_borrows_official_component(text):
    rows=claims(text)
    assert rows and all(c['status']=='unverifiable' for c in rows)


def test_missing_receipt_never_verifies_or_mutates_data():
    data=projected();data['official_financial_projection']['reference']['quarterly_document']['sha256']='0'*64
    before=deepcopy(data)
    rows=claims('大東電個別2026-06-30長期借款流動部分為0.005億元。',data)
    assert rows and rows[0]['status']=='unverifiable' and data==before
