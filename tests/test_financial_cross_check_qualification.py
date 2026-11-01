from copy import deepcopy
from financial_cross_checks import build_financial_cross_checks

def test_arithmetic_note_preserves_original_without_authenticating_its_source():
 note='同期間年度杜邦恒等式：淨利率12.4% × 資產周轉率0.928x × 權益乘數2.422x = ROE27.9%'
 data={'dupont_identity_note':note,'shares_raw':1000000,'forward_eps':2,'profit_margin_raw':.2,'revenue_ttm_raw':100000000};before=deepcopy(data)
 result=build_financial_cross_checks(data)
 assert result['dupont_identity_note']==note
 assert '原件期間與申報範圍未核實'in result['dupont_identity_note_qualified']
 assert result['dupont_source_qualification']['independent_primary_source_verified']is False
 assert result['dupont_source_qualification']['verification_scope']=='snapshot_arithmetic_consistency_only'
 assert result['forward_eps_implied_net_income_billion_twd']==.002
 assert result['forward_eps_implied_revenue_growth_pct']==-90.0
 assert data==before

def test_a_source_claim_inside_the_note_cannot_grant_itself_authentication():
 result=build_financial_cross_checks({'dupont_identity_note':'官方已核實的年度杜邦分析：ROE27.9%'})
 assert result['dupont_source_qualification']['independent_primary_source_verified']is False
 assert result['dupont_source_qualification']['may_support_official_source_claim']is False

def test_model_view_qualifies_note_but_keeps_the_raw_value_and_source_input():
 import json
 from prompt_builder import format_data_for_prompt
 data={'_prompt_agent_num':2,'ticker':'1623.TW','dupont_identity_note':'同期間年度杜邦恒等式：ROE27.9%'};before=deepcopy(data)
 body=format_data_for_prompt(data).split('【財務資料 JSON】\n',1)[1];payload,_=json.JSONDecoder().raw_decode(body);checks=payload['cross_checks']
 assert checks['dupont_identity_note_raw']==before['dupont_identity_note']
 assert '原件期間與申報範圍未核實'in checks['dupont_identity_note']
 assert checks['dupont_source_qualification']['independent_primary_source_verified']is False
 assert data==before
