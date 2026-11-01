from decimal import Decimal
import pytest
from test_native_fcf_label import case as base_case,row
from evidence_exit_gate_claims import extract_numeric_claims
NOTE='此現金流總額無法判定備料、存貨、應收款或擴產原因，任何用途解釋僅是待驗證假設。'
def case():
 d,t,v=base_case();t=t.replace('自由現金流分析','風險提示與結論').replace('官方 TTM 現金流表現','現金流與營運資金波動')+NOTE
 return d,t,v

def test_neutral_risk_heading_keeps_complete_fact_and_negative_qualifier():
 d,t,v=case();r=row(d,t);original=next(x for x in extract_numeric_claims(t)if x.get('financial_metric')=='自由現金流')
 assert r['status']=='verified'and r['independent_primary_source_verified']is True
 assert r['underlying_business_motive']=='unverified'
 for k in ('id','line_number','raw_text','label','reported_value','unit'):assert r[k]==original[k]

@pytest.mark.parametrize('old,new',[
 ('TWD','USD'),('TWD ',''),('2025-07-01','2024-07-01'),('2026-06-30','2026-09-30'),
 ('官方個別','官方合併'),('大東電業廠股份有限公司','台積電'),
 ('風險提示與結論','台積電風險提示與結論'),('風險提示與結論','2025年度風險提示與結論'),
 ('風險提示與結論','風險提示與結論（美元）'),('自由現金流為','預估自由現金流為')])
def test_qualified_or_wrong_scope_remains_unknown(old,new):
 d,t,v=case();assert row(d,t.replace(old,new))['status']=='unverifiable'

@pytest.mark.parametrize('factor',[10,-1])
def test_wrong_value_and_sign_remain_mismatch(factor):
 d,t,v=case();assert row(d,t.replace(v+' 億元',str(Decimal(v)*factor)+' 億元'))['status']=='mismatch'

def test_original_digest_corruption_stays_unknown():
 d,t,v=case();d['official_financial_projection']['reference']['quarterly_document']['sha256']='0'*64
 assert row(d,t)['status']=='unverifiable'

@pytest.mark.parametrize('tail',['此數據已證明擴產成效。','此為合併口徑。','未知額外推論。'])
def test_extra_prose_is_not_consumed(tail):
 d,t,v=case();assert row(d,t+tail)['status']=='unverifiable'
