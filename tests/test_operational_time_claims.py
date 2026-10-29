from copy import deepcopy
import pytest
from datetime import datetime,timezone,timedelta
from evidence_exit_gate import evaluate_report_evidence

LABELS={'原始擷取時間（台北）','報告保存與刷新（台北）','法人採用政策'}
def context():
 day='2026-06-16';url='https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date=20260616&selectType=ALLBUT0999'
 return {'ticker':'2855.TW','generated_at':day+'T17:45:32+08:00','data':{
  'ticker':'2855.TW','analysis_input_cutoff':day+'T16:00:00+08:00','market_data_fetched_at':day+'T15:57:44+08:00',
  'daily_market_data':{'as_of':day},'institutional_trading':{
   'latest_date':day,'source':'FinMind','source_provenance':{'status':'archived','source_url':'https://api.finmindtrade.com/api/v4/data',
   'retrieved_at':day+'T15:57:41+08:00','query':{'dataset':'TaiwanStockInstitutionalInvestorsBuySell','data_id':'2855','start_date':'2026-05-01','end_date':day}},
   'latest_session_admission':{'eligible':False,'reason':'official_observation_is_provisional'},
   'official_recovery':{'reports':[{'date':day,'status':'available','source_url':url,'raw_evidence':{'status':'archived','http_status':200,'source_url':url,'retrieved_at':day+'T15:44:40+08:00'}}]}}}}

def sample():
 c=context();c.pop('generated_at');return c

def markdown(c):
 def clock(value):
  if value is None:return '未記錄／時區未確認'
  d=datetime.fromisoformat(value);return d.astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')+' +08:00'
 d=c['data'];i=d['institutional_trading'];official=i['official_recovery']['reports'][0]['raw_evidence']
 return ('## 報告使用範圍與判讀限制\n'
  '- **原始擷取時間（台北）:** 行情 '+clock(d['market_data_fetched_at'])+'；法人主來源 '+clock(i['source_provenance']['retrieved_at'])+'；法人官方回應 '+clock(official['retrieved_at'])+'（快取命中不代表重新擷取）\n'
  '- **報告保存與刷新（台北）:** 保存 '+clock(c.get('generated_at'))+'；資料截止 '+clock(d['analysis_input_cutoff'])+'；來源刷新 未記錄／時區未確認；保存或刷新時間未確認\n'
  '- **法人採用政策:** 22:30（Asia/Taipei）為內部保守重查界線，非官方發布 SLA；時間經過不會自動升級保存資料。')

def test_five_clock_items_are_retained_separate_from_financial_evidence():
 c=sample();before=deepcopy(c);g=evaluate_report_evidence(markdown(c),c)
 assert g['claim_count']==0 and g['verified_count']==0
 assert g['timestamp_claim_count']==g['timestamp_checked_count']==5
 assert g['timestamp_invalid_count']==g['timestamp_unverifiable_count']==0
 assert g['all_numeric_claim_count']==g['all_numeric_checked_count']==5
 assert len(g['timestamp_claims'])==5 and all(x['status']=='valid'for x in g['timestamp_claims'])
 assert all(x['native_acquisition']is False and x['independent_primary_source_verified']is False for x in g['timestamp_claims'])
 assert g['verdict']!='approved'and c==before

@pytest.mark.parametrize('change',['hour','day','zone','policy'])
def test_false_clock_never_passes_even_with_same_minute(change):
 c=sample();md=markdown(c)
 if change=='hour':md=md.replace('15:57:44','16:57:44')
 elif change=='day':md=md.replace('2026-06-16 15:57:44','2026-06-17 15:57:44')
 elif change=='zone':md=md.replace('15:57:44 +08:00','15:57:44 +00:00')
 else:md=md.replace('22:30（Asia/Taipei）','22:31（Asia/Taipei）')
 g=evaluate_report_evidence(md,c)
 assert g['timestamp_invalid_count']>=1 and g['verdict']=='rejected'
 assert g['timestamp_claim_count']==g['timestamp_checked_count']==5
 from report_publication_gate import assert_report_publishable,ReportPublicationBlockedError
 with pytest.raises(ReportPublicationBlockedError):assert_report_publishable({'evidence_exit_gate':g})

@pytest.mark.parametrize('change',['naive_source','missing_cutoff','render_time_not_cutoff'])
def test_missing_time_is_unknown_not_filled_from_render_or_financial_values(change):
 c=sample();md=markdown(c)
 if change=='naive_source':c['data']['market_data_fetched_at']='2026-06-16T15:57:44'
 else:
  c['data'].pop('analysis_input_cutoff')
  if change=='render_time_not_cutoff':c['generated_at']='2026-06-16T16:00:00+08:00'
 c['data']['net_income']=57
 g=evaluate_report_evidence(md,c)
 assert g['timestamp_unverifiable_count']>=1 and g['verdict']!='approved'
 assert not any(x.get('verification_scope')=='snapshot_fact_consistency'for x in g['timestamp_claims'])


def test_time_consistency_does_not_upgrade_source_admission_or_failure():
 c=sample();c['data']['institutional_trading']['official_recovery']['reports'][0]['status']='unavailable';before=deepcopy(c)
 g=evaluate_report_evidence(markdown(c),c)
 assert g['timestamp_claim_count']==5 and g['timestamp_invalid_count']==0
 assert c==before and c['data']['institutional_trading']['official_recovery']['reports'][0]['status']=='unavailable'
 assert c['data']['institutional_trading']['latest_session_admission']['eligible']is False


def test_financial_amount_inside_notice_is_not_hidden_as_clock_metadata():
 c=sample();text=markdown(c)+'\n- **淨利:** 57 億元\n'
 g=evaluate_report_evidence(text,c)
 assert g['timestamp_claim_count']==5 and g['claim_count']>=1
 assert any(x['reported_value']==57 for x in g['sampled_claims'])


def test_metadata_rows_are_visible_in_both_report_formats():
 from reporting.evidence_ledger_view import evidence_ledger_markdown,evidence_ledger_html
 c=sample();g=evaluate_report_evidence(markdown(c),c)
 for rendered in (evidence_ledger_markdown({'evidence_exit_gate':g}),evidence_ledger_html({'evidence_exit_gate':g})):
  assert '時間中繼資料' in rendered and '非財務證據' in rendered
  assert '2026-06-16 15:57:44 +08:00' in rendered


def test_financial_value_in_clock_notice_remains_in_financial_coverage():
 c=sample();md=markdown(c).replace('（快取命中不代表重新擷取）','（快取命中不代表重新擷取）；淨利: 57 億元')
 g=evaluate_report_evidence(md,c)
 assert g['timestamp_claim_count']==5 and any(x['reported_value']==57 for x in g['sampled_claims'])
 assert g['all_numeric_claim_count']==g['all_numeric_checked_count']==6


def test_every_extracted_clock_and_financial_item_remains_accounted_for():
 from collections import Counter
 from evidence_exit_gate_claims import extract_numeric_claims
 c=sample();md=markdown(c)+'\n- **淨利:** 57 億元\n';g=evaluate_report_evidence(md,c)
 key=lambda x:tuple(str(x.get(k))for k in ['id','label','reported_value','unit','line_number','raw_text'])
 original=Counter(map(key,extract_numeric_claims(md)))
 checked=Counter(map(key,g['sampled_claims']+g['timestamp_claims']+g['metadata_claims']+g['policy_claims']))
 assert original==checked


def test_internal_policy_cannot_be_reworded_as_official_publication_promise():
 c=sample();md=markdown(c).replace('非官方發布 SLA','官方發布 SLA')
 g=evaluate_report_evidence(md,c)
 assert g['timestamp_invalid_count']>=1 and g['verdict']=='rejected'


def test_render_generated_time_is_not_actual_save_evidence():
 c=context();md=markdown(c)
 g=evaluate_report_evidence(md,c)
 rows=[x for x in g['timestamp_claims']if x.get('metadata_field')=='保存']
 assert len(rows)==1 and rows[0]['status']=='unverifiable'
 assert rows[0]['basis_path']=='report_saved_at'and rows[0]['expected_time']is None


def test_native_whole_second_display_keeps_fractional_source_and_rejects_next_second():
 c=sample();c['data']['market_data_fetched_at']='2026-06-16T15:57:44.999999+08:00';before=deepcopy(c)
 md=markdown(c);g=evaluate_report_evidence(md,c)
 assert g['timestamp_invalid_count']==0 and c==before
 row=next(x for x in g['timestamp_claims']if x['metadata_field']=='行情')
 assert '.999999'in row['expected_time']and row['display_precision']=='whole_seconds_truncated_by_native_formatter'
 changed=evaluate_report_evidence(md.replace('15:57:44','15:57:45'),c)
 assert changed['timestamp_invalid_count']>=1 and changed['verdict']=='rejected'


def test_other_issuer_receipt_is_not_reused_as_target_time_evidence():
 c=sample();md=markdown(c)
 c['data']['institutional_trading']['source_provenance']['query']['data_id']='2330'
 g=evaluate_report_evidence(md,c)
 assert g['timestamp_unverifiable_count']>=1
 assert any(x['metadata_field']=='法人主來源'and x['status']=='unverifiable'for x in g['timestamp_claims'])


def test_time_table_escapes_untrusted_text_and_never_counts_it_as_finance():
 from reporting.evidence_ledger_view import evidence_ledger_html
 c=sample();g=evaluate_report_evidence(markdown(c),c)
 g['timestamp_claims'][0]['reported_time']='<script>bad()</script>'
 html=evidence_ledger_html({'evidence_exit_gate':g})
 assert '<script>'not in html and '&lt;script&gt;'in html


def test_invalid_primary_record_does_not_borrow_valid_archive_clock():
 c=sample();md=markdown(c);i=c['data']['institutional_trading'];old=deepcopy(i['source_provenance'])
 i['_source_record_archive']={'primary_sdk':old};i['source_provenance']={'status':'error'}
 g=evaluate_report_evidence(md,c)
 assert next(x for x in g['timestamp_claims']if x['metadata_field']=='法人主來源')['status']=='unverifiable'


def test_failed_current_official_record_does_not_borrow_latest_success_clock():
 c=sample();md=markdown(c);i=c['data']['institutional_trading'];old=deepcopy(i['official_recovery']['reports'][0])
 i['latest_official_observation']=old;i['official_recovery']['reports'][0].update(status='error',error_kind='timeout',raw_evidence=None)
 g=evaluate_report_evidence(md,c)
 assert next(x for x in g['timestamp_claims']if x['metadata_field']=='法人官方回應')['status']=='unverifiable'


def test_ambiguous_current_receipts_stay_unknown_without_cherry_picking():
 c=sample();md=markdown(c);rows=c['data']['institutional_trading']['official_recovery']['reports'];rows.append(deepcopy(rows[0]))
 g=evaluate_report_evidence(md,c)
 assert next(x for x in g['timestamp_claims']if x['metadata_field']=='法人官方回應')['status']=='unverifiable'


def test_invalid_offset_minutes_are_not_silently_normalized():
 c=sample();md=markdown(c)
 c['data']['market_data_fetched_at']='2026-06-16T15:57:44+08:99'
 g=evaluate_report_evidence(md,c)
 assert next(x for x in g['timestamp_claims']if x['metadata_field']=='行情')['status']=='unverifiable'
