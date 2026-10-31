from decimal import Decimal
import pytest
from test_explicit_cashflow_components_proof import projected
from evidence_exit_gate import evaluate_report_evidence
from evidence_exit_gate_claims import extract_numeric_claims

PREFIX='## 估值偏離度客觀描述\n### 信心依據\n'
OWNER='大東電業廠股份有限公司官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）'
def case():
    d=projected();value=str(Decimal(d['official_financial_projection']['facts']['cashflows']['ttm']['free_cash_flow'])/Decimal(100000000))
    return d,PREFIX+'- **已納入考量的風險**: '+OWNER+'自由現金流為 '+value+' 億元。',value

def row(d,t):
    return next(r for r in evaluate_report_evidence(t,{'data':d})['sampled_claims']if r.get('financial_metric')=='自由現金流')

def test_complete_native_risk_label_replays_original_and_preserves_claim():
    d,t,v=case();r=row(d,t);original=next(c for c in extract_numeric_claims(t)if c.get('financial_metric')=='自由現金流')
    assert r['status']=='verified'
    assert r['independent_primary_source_verified'] is True
    for key in ['id','line_number','raw_text','label','reported_value','unit']:assert r[key]==original[key]

@pytest.mark.parametrize('old,new',[
 ('TWD','USD'),('TWD ',''),('2025-07-01','2024-07-01'),('官方個別','官方合併'),
 ('大東電業廠股份有限公司','台積電'),('已納入考量的風險','台積電已納入考量的風險'),
 ('信心依據','未來情境信心依據'),('估值偏離度客觀描述','2024年度估值偏離度客觀描述'),
 ('自由現金流為','預估自由現金流為')])
def test_scope_corruption_stays_unknown(old,new):
    d,t,v=case();assert row(d,t.replace(old,new))['status']=='unverifiable'

@pytest.mark.parametrize('factor',[10,-1])
def test_value_or_sign_error_stays_mismatch(factor):
    d,t,v=case();assert row(d,t.replace(v+' 億元',str(Decimal(v)*factor)+' 億元'))['status']=='mismatch'

def test_changed_original_remains_unknown():
    d,t,v=case();d['official_financial_projection']['reference']['quarterly_document']['sha256']='0'*64
    assert row(d,t)['status']=='unverifiable'

@pytest.mark.parametrize('tail',['此為合併口徑。','幣別為美元。','未知額外文字。','此數據已證明擴產成效。'])
def test_unbound_extra_prose_is_not_stripped(tail):
    d,t,v=case();assert row(d,t+tail)['status']=='unverifiable'
