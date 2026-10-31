import pytest
from test_cashflow_component_issuer_alias import component_data
from evidence_exit_gate import evaluate_report_evidence
from evidence_financial_amounts import _native_mode_a_structural_headings

def case():
 d=component_data();title=next(x for x in _native_mode_a_structural_headings(d) if x.startswith('# '))
 return d,title+'\n## 三、自由現金流分析\n- **存貨變動影響**：大東電業廠股份有限公司官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）存貨變動現金影響為 -0.08000 億元。'
def row(d,t):
 return next(x for x in evaluate_report_evidence(t,{'data':d})['sampled_claims'] if x.get('financial_metric')=='存貨變動現金影響')
def test_exact_inventory_label_replays_originals():
 d,t=case();r=row(d,t);assert r['status']=='verified';assert r['underlying_business_motive']=='unverified'
@pytest.mark.parametrize('old,new',[('TWD','USD'),('2025-07-01','2024-07-01'),('官方個別','官方合併'),('大東電業廠股份有限公司','台積電'),('**存貨變動影響**','**應收帳款變動影響**')])
def test_inventory_scope_damage_unknown(old,new):
 d,t=case();assert row(d,t.replace(old,new))['status']=='unverifiable'
@pytest.mark.parametrize('number',['0.08000','-0.80000'])
def test_inventory_wrong_sign_amount_mismatch(number):
 d,t=case();assert row(d,t.replace('-0.08000',number))['status']=='mismatch'
