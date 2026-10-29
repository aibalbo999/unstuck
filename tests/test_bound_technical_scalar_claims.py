"""Original-window arithmetic must bind to its own dated field, never plans."""
from copy import deepcopy
from datetime import date,timedelta
import math
import pytest
from report_analysis_evidence import _digest,_seal,freeze_input_evidence,capture_analysis_evidence
from workflow_trade_evidence import trade_input_fingerprint
from short_term_technical_indicators import calculate_technical_indicators
from market_calendar_store import load_market_calendar,session_day_status
from evidence_exit_gate import evaluate_report_evidence


def fixture():
 calendar=load_market_calendar('tw',2026);dates=[];day=date(2026,10,29)
 while len(dates)<120:
  if session_day_status(day,market='tw',calendar=calendar,exchange='TWSE')['state']=='open':dates.append(day.isoformat())
  day-=timedelta(days=1)
 dates.reverse();bars=[]
 for i,d in enumerate(dates):
  close=50+i*.05+math.sin(i*.4);bars.append({'date':d,'open':close-.1,'high':close+.5,'low':close-.5,'close':close,'volume':100000+i*100})
 daily={'ticker':'2356.TW','bars':bars,'as_of':dates[-1],'source':'unit fixture saved bars','availability':'available','volume_unit':'shares','volume_basis':'provider shares','price_adjustment_basis':'fixture adjusted OHLC;not exchange raw'}
 technical=calculate_technical_indicators(daily);data={'ticker':'2356.TW','currency':'TWD','financial_currency':'TWD','quote_type':'EQUITY','daily_market_data':daily,'technical_indicators':technical}
 data['analysis_input_hash']=_digest(data);data['analysis_input_cutoff']='2026-10-29T14:00:00+00:00'
 data['_analysis_input_evidence']=freeze_input_evidence(data)
 catalog={'short_term_market_context':{'ticker':'2356.TW','as_of':dates[-1],'technical_indicators':deepcopy(technical)}}
 manifest={'visible':True,'version':'trade-sources:v4','catalog':catalog,'fingerprint':_digest(catalog),'input_fingerprint':trade_input_fingerprint(data)}
 section=lambda v:{'status':'preserved','data':v,'fingerprint':_digest(v)}
 packet=capture_analysis_evidence({'data':data,'_trade_source_manifest':manifest})
 snapshot={'analysis_evidence':packet,'data':deepcopy(data),'pipeline_id':'v4','rerun_context':{'structured_outputs':{'24':{'source_assessment':{'source_fingerprint':manifest['fingerprint']},'support_level':technical['rsi_14']}}}}
 return snapshot,technical


def text(t):
 c=t['macd_histogram_comparison'];root='short_term_market_context.technical_indicators'
 return (f"2026-10-29 rsi_14:{t['rsi_14']}（source ref={root}.rsi_14），落於中力線附近。"
  f"以相同120根K線及EMA種子計算之收據觀測：macd:{t['macd']}元、macd_signal:{t['macd_signal']}元、macd_histogram:{t['macd_histogram']}元（source ref={root}）。"
  f"與前日(2026-10-28) macd_histogram:{c['previous']}元相比，signed_delta:{c['signed_delta']}元，magnitude_delta:{c['magnitude_delta']}元（source ref={root}.macd_histogram_comparison）。\n"
  f"2026-10-29 量比 volume_ratio_20:{t['volume_ratio_20']}（source ref={root}.volume_ratio_20）。10-27為另一歷史觀測。")


@pytest.mark.parametrize('key',['rsi_14','volume_ratio_20','macd','macd_signal','macd_histogram','signed_delta','magnitude_delta'])
def test_exact_original_window_scalar_survives_separate_prior_day_comparison(key):
 s,t=fixture();value=t.get(key,t['macd_histogram_comparison'].get(key));gate=evaluate_report_evidence(text(t),s,min_sample=1)
 rows=[c for c in gate['sampled_claims']if c['reported_value']==value]
 assert rows, f'missing extracted claim for {key}'
 claim=rows[0];assert claim['status']=='verified'
 assert claim['verification_scope']=='saved_window_arithmetic'
 assert claim.get('independent_primary_source_verified')is False
 assert claim.get('historical_point_in_time_verified')is False


@pytest.mark.parametrize('mode',['wrong_output','tampered_original','foreign_ticker','missing_input'])
def test_missing_or_wrong_original_binding_never_verifies_rsi(mode):
 s,t=fixture()
 if mode=='wrong_output':s['rerun_context']['structured_outputs']['24']['source_assessment']['source_fingerprint']='0'*64
 if mode=='tampered_original':s['analysis_evidence']['sections']['analysis_input']['data']['daily_market_data']['bars'][-1]['close']+=1
 if mode=='foreign_ticker':s['data']['ticker']='3231.TW'
 if mode=='missing_input':s['analysis_evidence']['sections'].pop('analysis_input')
 gate=evaluate_report_evidence(text(t),s,min_sample=1);assert all(c['status']!='verified'for c in gate['sampled_claims']if c['reported_value']==t['rsi_14'])


def test_support_plan_equal_to_rsi_remains_generated_not_independent():
 s,t=fixture();gate=evaluate_report_evidence(f"支撐位:{t['rsi_14']}元",s,min_sample=1)
 assert gate['verified_count']==0
 assert gate['sampled_claims'][0]['verification_reason_code']=='generated_analysis_not_independent_evidence'


def reseal(s):
 packet=s['analysis_evidence'];data=packet['sections']['analysis_input']['data']
 data['analysis_input_hash']=_digest({k:v for k,v in data.items()if k not in {'analysis_input_hash','analysis_input_cutoff','_analysis_input_evidence'}})
 data['_analysis_input_evidence']=freeze_input_evidence(data);manifest=packet['sections']['trade_source_manifest']['data']
 manifest['catalog']['short_term_market_context']['technical_indicators']=deepcopy(data['technical_indicators'])
 manifest['input_fingerprint']=trade_input_fingerprint(data);manifest['fingerprint']=_digest(manifest['catalog'])
 s['analysis_evidence']=capture_analysis_evidence({'data':data,'_trade_source_manifest':manifest});s['data']=deepcopy(data)
 s['rerun_context']['structured_outputs']['24']['source_assessment']['source_fingerprint']=manifest['fingerprint']


@pytest.mark.parametrize('mode',['currency','bars_hash','seed','comparison','missing_session','basis','source','prices'])
def test_sealed_but_invalid_source_calculation_or_session_cannot_verify(mode):
 s,t=fixture();data=s['analysis_evidence']['sections']['analysis_input']['data']
 if mode=='currency':data['currency']=data['financial_currency']='USD'
 if mode=='bars_hash':data['technical_indicators']['input_window']['bars_sha256']='0'*64
 if mode=='seed':data['technical_indicators']['calculation_policy']['macd']='unverified seed'
 if mode=='comparison':data['technical_indicators']['macd_histogram_comparison']['signed_delta']+=1
 if mode=='missing_session':
  data['daily_market_data']['bars'].pop(-2);data['technical_indicators']=calculate_technical_indicators(data['daily_market_data'])
 if mode=='basis':data['technical_indicators']['price_adjustment_basis']='another basis'
 if mode=='source':data['technical_indicators']['source']=data['daily_market_data']['source']='unknown'
 if mode=='prices':data['daily_market_data']['bars'][-1]['low']=data['daily_market_data']['bars'][-1]['high']+1
 reseal(s);gate=evaluate_report_evidence(text(t),s,min_sample=1)
 assert all(c['status']!='verified'for c in gate['sampled_claims']if c['reported_value']==t['rsi_14'])


@pytest.mark.parametrize('mode',['foreign_ticker','wrong_reference','wrong_date','duplicate','percent','currency_unit','forecast','english_research','lowercase_foreign','foreign_code','partial_date','ambiguous_prior'])
def test_literal_ownership_currency_and_date_are_not_inferred_by_value(mode):
 s,t=fixture();raw=text(t);literal=f"rsi_14:{t['rsi_14']}"
 if mode=='foreign_ticker':raw=raw.replace('2026-10-29 ','2026-10-29 3231.TW ',1)
 if mode=='wrong_reference':raw=raw.replace('technical_indicators.rsi_14','technical_indicators.macd',1)
 if mode=='wrong_date':raw=raw.replace('2026-10-29','2026-10-28',1)
 if mode=='duplicate':raw=f"2026-10-29 {literal}（source ref=short_term_market_context.technical_indicators.rsi_14）。"+raw
 if mode=='percent':raw=raw.replace(literal,literal+'%',1)
 if mode=='currency_unit':raw=raw.replace(literal,literal+'元',1)
 if mode=='forecast':raw='假設 '+raw
 if mode=='english_research':raw='broker research '+raw
 if mode=='lowercase_foreign':raw=raw.replace('2026-10-29 ','2026-10-29 3231.tw ',1)
 if mode=='foreign_code':raw=raw.replace('2026-10-29 ','2026-10-29 公司代號3231 ',1)
 if mode=='partial_date':raw=raw.replace('2026-10-29 ','2026-10-29 10-28 ',1)
 if mode=='ambiguous_prior':raw=raw.replace('與前日','另有觀測')
 gate=evaluate_report_evidence(raw,s,min_sample=1)
 assert all(c['status']!='verified'for c in gate['sampled_claims']if c['reported_value']==t['rsi_14'])


def test_wrong_value_is_mismatch_not_missing_and_cannot_borrow_another_metric():
 s,t=fixture();wrong=t['rsi_14']+10;raw=text(t).replace(f"rsi_14:{t['rsi_14']}",f'rsi_14:{wrong}',1)
 s['data']['unrelated_equal_value']=wrong
 gate=evaluate_report_evidence(raw,s,min_sample=1);claim=next(c for c in gate['sampled_claims']if c['reported_value']==wrong)
 assert claim['status']=='mismatch' and claim['matched_value']==t['rsi_14']
 assert claim['matched_path'].endswith('.rsi_14') and claim['candidate_count']==1


def test_swapped_signed_and_magnitude_deltas_are_mismatches():
 s,t=fixture();comp=t['macd_histogram_comparison'];signed,mag=comp['signed_delta'],comp['magnitude_delta'];assert signed!=mag
 raw=text(t).replace(f'signed_delta:{signed}',f'signed_delta:{mag}').replace(f'magnitude_delta:{mag}',f'magnitude_delta:{signed}')
 gate=evaluate_report_evidence(raw,s,min_sample=1)
 for label,key in [('signeddelta','signed_delta'),('magnitudedelta','magnitude_delta')]:
  claim=next(c for c in gate['sampled_claims']if c['label'].lower().replace('_','').endswith(label))
  assert claim['status']=='mismatch' and claim['matched_path'].endswith('.'+key)
  assert claim['matched_value']==comp[key]


def test_later_refreshed_values_cannot_replace_original_frozen_arithmetic():
 s,t=fixture();s['data']['technical_indicators']['rsi_14']=1.0
 gate=evaluate_report_evidence(text(t),s,min_sample=1);claim=next(c for c in gate['sampled_claims']if c['reported_value']==t['rsi_14'])
 assert claim['status']=='verified' and claim['matched_value']==t['rsi_14']
 assert claim['matched_path'].startswith('analysis_evidence.sections.analysis_input.')


def test_future_bar_window_cannot_be_backdated_to_original_cutoff():
 from evidence_bound_technical_claims import prepare_bound_technical
 s,t=fixture();data=s['analysis_evidence']['sections']['analysis_input']['data'];daily=data['daily_market_data']
 following=deepcopy(daily['bars'][-1]);following['date']='2026-10-30'
 daily['bars']=daily['bars'][1:]+[following];daily['as_of']='2026-10-30';data['technical_indicators']=calculate_technical_indicators(daily);reseal(s)
 assert prepare_bound_technical(s)is None


def test_render_hash_without_preserved_start_receipt_does_not_admit_new_paths():
 from evidence_bound_technical_claims import prepare_bound_technical
 s,t=fixture();packet=s['analysis_evidence'];data=packet['sections']['analysis_input']['data'];manifest=packet['sections']['trade_source_manifest']['data']
 s['analysis_evidence']=capture_analysis_evidence({'data':data,'_trade_source_manifest':manifest})
 assert s['analysis_evidence']['capture_boundary']=='report_render'
 assert s['analysis_evidence']['input_verification']=='hash_verified'
 assert 'frozen_market_input_fingerprint'not in s['analysis_evidence']
 assert prepare_bound_technical(s)is None


def test_frozen_fingerprint_and_original_hash_are_both_required():
 from evidence_bound_technical_claims import prepare_bound_technical
 s,t=fixture();packet=s['analysis_evidence'];packet['frozen_market_input_fingerprint']='0'*64;packet.pop('packet_fingerprint');_seal(packet)
 assert prepare_bound_technical(s)is None
 s,t=fixture();packet=s['analysis_evidence'];data=packet['sections']['analysis_input']['data'];data['added_after_capture']='not original'
 manifest=packet['sections']['trade_source_manifest']['data'];manifest['input_fingerprint']=trade_input_fingerprint(data)
 for name in ['analysis_input','trade_source_manifest']:packet['sections'][name]['fingerprint']=_digest(packet['sections'][name]['data'])
 packet['frozen_market_input_fingerprint']=packet['sections']['analysis_input']['fingerprint'];packet.pop('packet_fingerprint');_seal(packet)
 assert prepare_bound_technical(s)is None


def test_future_capture_cutoff_and_legacy_bootstrap_cannot_add_verified_paths():
 from evidence_bound_technical_claims import prepare_bound_technical
 s,t=fixture();s['analysis_evidence']['sections']['analysis_input']['data']['analysis_input_cutoff']='2099-10-29T14:00:00+00:00';reseal(s)
 assert prepare_bound_technical(s)is None
 s,t=fixture();packet=s['analysis_evidence'];packet['capture_boundary']='legacy_hash_verified';packet.pop('packet_fingerprint');_seal(packet)
 assert prepare_bound_technical(s)is None
