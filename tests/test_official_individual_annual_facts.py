"""Annual originals stay distinct from TTM and vendor history."""
from copy import deepcopy
from decimal import Decimal
import json
import pytest
from evidence_exit_gate import evaluate_report_evidence
from official_income_prompt import official_income_prompt_facts
from test_official_income_claims import selected

def annual(data):
 return official_income_prompt_facts(data)['annual_facts']

def checked(text,data):
 return [c for c in evaluate_report_evidence(text,{'data':data})['sampled_claims']if c.get('financial_amount')]

def test_annual_prompt_uses_replayed_rows_and_preserves_vendor_scalars():
 data=selected();data['revenue_history']=[3.9,4.22,5.48,6.61];before=deepcopy(data);facts=annual(data)
 assert facts['report_scope']=='individual'and facts['currency']=='TWD'
 assert set(facts['periods'])=={'2024','2025'}
 assert facts['five_year_history_verified']is False and facts['historical_pit_verified']is False
 assert facts['native_acquisition']is False and data==before
 assert 'raw_response_path'not in json.dumps(facts)
 for year,row in facts['periods'].items():
  assert row['period_start']==year+'-01-01'and row['period_end']==year+'-12-31'
  assert row['source_filing_year']==2025
  assert row['comparative_period']is(year=='2024')

@pytest.mark.parametrize('year',['2024','2025'])
@pytest.mark.parametrize('metric',['營收','淨利','自由現金流'])
def test_complete_annual_statement_replays_exact_official_fact(year,metric):
 data=selected();facts=annual(data);text=facts['periods'][year]['statements'][metric]
 rows=checked(text,data);assert len(rows)==1 and rows[0]['status']=='verified',rows
 assert rows[0]['verification_scope']=='replayed_official_individual_annual_fact'
 assert rows[0]['financial_period']==year+'-01-01/'+year+'-12-31'
 assert rows[0]['historical_pit_verified']is False and rows[0]['native_acquisition']is False

@pytest.mark.parametrize('change',[lambda s:s.replace('TWD ',''),lambda s:s.replace('個別','合併'),lambda s:s.replace('大東電業廠股份有限公司','台積電'),lambda s:s.replace('2025-01-01','2024-01-01'),lambda s:s.replace('2025-12-31','2026-06-30'),lambda s:'# 台積電\n'+s,lambda s:s.replace('淨利','預估淨利'),lambda s:s.replace('TWD','USD'),lambda s:s+'此為合併口徑。'])
def test_annual_scope_or_prediction_cannot_borrow_original(change):
 data=selected();text=annual(data)['periods']['2025']['statements']['淨利'];rows=checked(change(text),data)
 assert rows and all(c['status']=='unverifiable'for c in rows),rows

def test_wrong_annual_amount_mismatches_instead_of_using_vendor_fallback():
 data=selected();row=annual(data)['periods']['2025'];text=row['statements']['淨利']
 amount=format(Decimal(row['values_twd']['淨利'])/Decimal(100000000),'f');text=text.replace(amount,str(Decimal(amount)+100))
 rows=checked(text,data);assert len(rows)==1 and rows[0]['status']=='mismatch',rows

def test_missing_original_does_not_supply_annual_facts():
 data=selected();data['official_financial_projection']['reference']['annual_document']['sha256']='0'*64
 assert official_income_prompt_facts(data)is None

@pytest.mark.parametrize('compact,dense,role_scoped',[(False,False,False),(True,True,False),(True,True,True)])
def test_prompt_keeps_annual_and_ttm_in_separate_envelopes(compact,dense,role_scoped):
 from prompt_builder import format_data_for_prompt
 data=selected();data['_prompt_agent_num']=2;before=deepcopy(data)
 text=format_data_for_prompt(data,compact=compact,dense=dense,role_scoped=role_scoped)
 assert 'official_individual_annual_facts'in text and 'official_income_reference_text'in text
 assert 'source_filing_year'in text and 'comparative_period'in text
 assert 'raw_response_path'not in text and data==before


def test_vendor_disclaimer_is_not_misread_as_an_official_annual_assertion():
 from official_individual_annual_facts import check_individual_annual_claim
 claim={'financial_metric':'淨利','raw_text':'vendor年度淨利為8.2億元，年度口徑未經官方核實。'}
 assert check_individual_annual_claim(claim,selected(),1)is None

def test_annual_statement_cannot_borrow_the_adjacent_ttm_interval():
 data=selected();text=annual(data)['periods']['2025']['statements']['淨利']
 text=text.replace('2025-01-01 至 2025-12-31','2025-07-01 至 2026-06-30')
 result=checked(text,data);assert result and all(c['status']=='unverifiable'for c in result),result


def test_caller_supplied_annual_envelope_cannot_replace_originals():
 data=selected();text=annual(data)['periods']['2025']['statements']['淨利']
 fake=deepcopy(annual(data));fake['periods']['2025']['values_twd']['淨利']=99900000000
 data['official_individual_annual_facts']=fake
 data.pop('official_financial_projection')
 result=checked(text,data);assert result and all(c['status']=='unverifiable'for c in result),result

def test_annual_fact_does_not_grant_a_ttm_fact_with_the_same_amount():
 data=selected();text=annual(data)['periods']['2025']['statements']['淨利']
 amount=Decimal(annual(data)['periods']['2025']['values_twd']['淨利'])/Decimal(100000000)
 text=text.replace(format(amount,'f'),format(amount,'.8f'))
 text=text.replace('年度（2025-01-01 至 2025-12-31）','TTM（2025-07-01 至 2026-06-30）')
 result=checked(text,data);assert result and all(c['status']!='verified'for c in result),result


def test_nearby_amount_with_false_precision_is_not_accepted_by_one_percent_tolerance():
 data=selected();row=annual(data)['periods']['2025'];text=row['statements']['淨利']
 amount=Decimal(row['values_twd']['淨利'])/Decimal(100000000);assert amount!=0
 text=text.replace(format(amount,'f'),format(amount+abs(amount)*Decimal('0.001'),'f'))
 result=checked(text,data);assert len(result)==1 and result[0]['status']=='mismatch',result

def test_legitimate_display_rounding_remains_verified():
 data=selected();row=annual(data)['periods']['2025'];text=row['statements']['淨利']
 amount=Decimal(row['values_twd']['淨利'])/Decimal(100000000)
 text=text.replace(format(amount,'f'),format(amount.quantize(Decimal('0.01')),'f'))
 result=checked(text,data);assert len(result)==1 and result[0]['status']=='verified',result


@pytest.mark.parametrize('heading',['## 一、營收成長分析','## 已核實年度財務','## 官方財務事實清單'])
def test_native_observed_annual_heading_keeps_complete_fact(heading):
 data=selected();text=heading+'\n\n'+annual(data)['periods']['2025']['statements']['營收']
 result=checked(text,data);assert len(result)==1 and result[0]['status']=='verified',result
 for qualifier in ('2024年度','台積電','預估','USD'):
  result=checked(text.replace(heading,heading+' '+qualifier),data)
  assert result and all(c['status']=='unverifiable'for c in result),result


@pytest.mark.parametrize('model',['gemini-3.8-flash','gemma-4-31b-it'])
def test_full_model_prompt_replays_private_originals_before_public_projection(monkeypatch,model):
 from agent_runtime import prompting
 monkeypatch.setattr(prompting,'get_agent_prompt_token_budget',lambda *args,**kwargs:1000000)
 data=selected();before=deepcopy(data);context={'data':data,'analyses':{},'structured_outputs':{},'_prompt_model_id':model,'_audit_retry_instruction':'保留官方年度與TTM完整範圍。'}
 prompt=prompting.build_prompt(2,data,context)
 assert 'official_individual_annual_facts'in prompt and 'official_income_reference_text'in prompt
 assert '3200000'in prompt and 'source_filing_year'in prompt
 assert 'raw_response_path'not in prompt and 'official-response-evidence/'not in prompt
 assert data==before

def test_template_data_and_context_stay_public_when_financial_server_replay_needs_paths(monkeypatch):
 from agent_runtime import prompting
 monkeypatch.setattr(prompting,'get_agent_prompt_token_budget',lambda *args,**kwargs:1000000)
 monkeypatch.setitem(prompting.ANALYSIS_PROMPTS,2,'{{ data }}\n{{ context }}\n{{ fin_data }}')
 data=selected();before=deepcopy(data);context={'data':data,'analyses':{},'structured_outputs':{},'_prompt_model_id':'gemini-3.8-flash'}
 prompt=prompting.build_prompt(2,data,context)
 assert 'official_individual_annual_facts'in prompt and 'official_income_reference_text'in prompt
 assert 'raw_response_path'not in prompt and 'official-response-evidence/'not in prompt
 assert data==before

@pytest.mark.parametrize('caption,metric',[('官方個別年度營收事實','營收'),('官方個別年度與 TTM 淨利事實','淨利'),('官方個別年度與 TTM 自由現金流事實','自由現金流')])
def test_exact_neutral_fact_caption_does_not_hide_complete_annual_scope(caption,metric):
 data=selected();statement=annual(data)['periods']['2025']['statements'][metric]
 rows=checked('## 一、營收成長分析\n\n- '+caption+'：\n'+statement,data)
 assert len(rows)==1 and rows[0]['status']=='verified',rows
 for bad in (' 台積電',' USD',' 2024年度',' 合併',' 預估'):
  rows=checked('## 一、營收成長分析\n\n- '+caption+bad+'：\n'+statement,data)
  assert rows and all(x['status']=='unverifiable'for x in rows),rows


def test_qualified_annual_siblings_do_not_supply_or_override_local_ttm_scope():
 from official_income_prompt import official_income_reference_text
 data=selected();facts=annual(data);siblings='\n'.join(facts['periods'][y]['statements']['淨利']for y in ('2024','2025'))
 ttm=official_income_reference_text(official_income_prompt_facts(data))['statement']
 text='## 二、獲利趨勢深析\n\n- 官方個別年度與 TTM 淨利事實：\n'+siblings+'\n'+ttm
 rows=checked(text,data);assert len(rows)==3 and all(x['status']=='verified'for x in rows),rows
 for bad in (siblings.replace('TWD','USD'),siblings+'\n台積電財報。',siblings.replace('為 ','為 9',1)):
  rows=checked('## 二、獲利趨勢深析\n\n- 官方個別年度與 TTM 淨利事實：\n'+bad+'\n'+ttm,data)
  assert rows[-1]['status']=='unverifiable',rows
 rows=checked(text.replace(ttm,ttm.replace('TWD ','')),data)
 assert rows[-1]['status']=='unverifiable',rows

def test_native_official_fact_list_keeps_ttm_scope_without_granting_it():
 from official_income_prompt import official_income_reference_text
 data=selected();s=official_income_reference_text(official_income_prompt_facts(data))['statement']
 heading='## 官方財務事實清單';rows=checked(heading+'\n\n'+s,data)
 assert len(rows)==1 and rows[0]['status']=='verified',rows
 for suffix in (' USD',' 台積電',' 2024年度',' 合併',' 預估'):
  rows=checked(heading+suffix+'\n\n'+s,data)
  assert rows and all(x['status']=='unverifiable'for x in rows),rows
 rows=checked(heading+'\n\n'+s.replace('TWD ',''),data)
 assert rows and all(x['status']=='unverifiable'for x in rows),rows

@pytest.mark.parametrize('ancestor',['# 台積電','# 2024年度','# 合併財報','# USD','# 預估財務'])
def test_official_fact_list_cannot_hide_a_conflicting_ancestor(ancestor):
 from official_income_prompt import official_income_reference_text
 data=selected();a=annual(data)['periods']['2025']['statements']['淨利'];t=official_income_reference_text(official_income_prompt_facts(data))['statement']
 for statement in (a,t):
  rows=checked(ancestor+'\n\n## 官方財務事實清單\n\n'+statement,data)
  assert rows and all(x['status']=='unverifiable'for x in rows),rows
