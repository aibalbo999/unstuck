import pytest
from decimal import Decimal
from test_explicit_cashflow_components_proof import projected
from evidence_exit_gate import evaluate_report_evidence
from evidence_financial_amounts import _native_mode_a_structural_headings

def case():
 data=projected();f=data['official_financial_projection']['facts'];v=Decimal(str(f['cashflows']['ttm']['free_cash_flow']))/Decimal(100000000)
 title=next(x for x in _native_mode_a_structural_headings(data) if x.startswith('# '))
 text=title+'\n## 三、自由現金流分析\n- **官方 TTM 現金流表現**：大東電業廠股份有限公司官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）自由現金流為 '+str(v)+' 億元。'
 return data,text,str(v)
def row(data,text):
 return next(x for x in evaluate_report_evidence(text,{'data':data})['sampled_claims'] if x.get('financial_metric')=='自由現金流')
def test_native_complete_fcf_label():
 d,t,v=case();assert row(d,t)['status']=='verified'
@pytest.mark.parametrize('old,new',[('TWD','USD'),('2025-07-01','2024-07-01'),('官方個別','官方合併'),('大東電業廠股份有限公司','台積電'),('官方 TTM 現金流表現','台積電現金流表現')])
def test_scope_damage_unknown(old,new):
 d,t,v=case();assert row(d,t.replace(old,new))['status']=='unverifiable'
def test_bad_amount_mismatch():
 d,t,v=case();assert row(d,t.replace(v+' 億元',str(Decimal(v)*10)+' 億元'))['status']=='mismatch'
