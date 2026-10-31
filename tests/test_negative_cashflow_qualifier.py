from decimal import Decimal
import pytest
from test_explicit_cashflow_components_proof import projected
from evidence_exit_gate import evaluate_report_evidence
from evidence_exit_gate_claims import extract_numeric_claims
NOTE='此現金流總額無法判定備料、存貨、應收款或擴產原因，任何用途解釋僅是待驗證假設。'
def case(label='現金流警示'):
    d=projected();value=str(Decimal(d['official_financial_projection']['facts']['cashflows']['ttm']['free_cash_flow'])/Decimal(100000000))
    text='## 已觀測財務與歷史反證\n- **'+label+'**：大東電業廠股份有限公司官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）自由現金流為 '+value+' 億元。'+NOTE
    return d,text,value

def row(d,t):return next(r for r in evaluate_report_evidence(t,{'data':d})['sampled_claims']if r.get('financial_metric')=='自由現金流')
@pytest.mark.parametrize('label',['現金流警示','現金流與營運資金波動'])
def test_exact_negative_motive_note_preserves_fact_and_unknown_motive(label):
    d,t,v=case(label);r=row(d,t);c=next(c for c in extract_numeric_claims(t)if c.get('financial_metric')=='自由現金流')
    assert r['status']=='verified'
    assert r['underlying_business_motive']=='unverified'
    assert r['independent_primary_source_verified'] is True
    for k in ['id','raw_text','line_number','reported_value','unit','label']:assert r[k]==c[k]
    assert not evaluate_report_evidence(t,{'data':d})['cashflow_causal_checks']

@pytest.mark.parametrize('old,new',[('TWD','USD'),('TWD ',''),('2025-07-01','2024-07-01'),('官方個別','官方合併'),('大東電業廠股份有限公司','台積電'),('已觀測財務與歷史反證','2024年度財務證據'),('自由現金流為','預估自由現金流為'),('無法判定','可以判定'),('待驗證假設','已驗證事實')])
def test_scope_or_qualifier_damage_not_verified(old,new):
    d,t,v=case();assert row(d,t.replace(old,new))['status']=='unverifiable'
@pytest.mark.parametrize('factor',[10,-1])
def test_bad_numeric_fact_stays_mismatch(factor):
    d,t,v=case();assert row(d,t.replace(v+' 億元',str(Decimal(v)*factor)+' 億元'))['status']=='mismatch'
@pytest.mark.parametrize('tail',['此為合併口徑。','台積電營收為1億元。','未知文字。','此已證明擴產。'])
def test_extra_prose_or_amount_is_not_consumed(tail):
    d,t,v=case();assert row(d,t+tail)['status']=='unverifiable'
def test_changed_source_still_unknown():
    d,t,v=case();d['official_financial_projection']['reference']['quarterly_document']['sha256']='0'*64
    assert row(d,t)['status']=='unverifiable'
