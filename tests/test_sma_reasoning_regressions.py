import json,gzip
from pathlib import Path
import pytest
from evidence_exit_gate import evaluate_report_evidence
from technical_reasoning import histogram_data_from_snapshot
CASES=json.loads(gzip.decompress((Path(__file__).parent/'fixtures/sma_reasoning_oct15.json.gz').read_bytes()))
@pytest.mark.parametrize('name,code', [('2855_TW_v4_report_job_b596a5c41cb6','close_above_sma'),('1476_TW_v4_report_job_e5ffdeed7fab','bullish_sma_order')])
def test_saved_contradiction_rejected_without_rewriting(name,code):
 snapshot=CASES[name]['snapshot'];text=CASES[name]['markdown']
 result=evaluate_report_evidence(text,snapshot)
 assert any(c.get('claim_type')==code and c['status']=='mismatch' for c in result['technical_reasoning_checks'])
 assert result['verdict']=='rejected'
def test_hypothetical_is_not_current_assertion():
 from technical_reasoning import sma_reasoning_checks
 assert sma_reasoning_checks('若股價站上5日線，才重新評估。',{})==[]
def test_missing_original_evidence_does_not_use_new_snapshot():
 from technical_reasoning import sma_reasoning_checks
 snapshot={'refreshed_without_analysis_rerun':True,'data':{'technical_indicators':{'sma_5':1}}}
 checks=sma_reasoning_checks('收盤價站上5日線。',histogram_data_from_snapshot(snapshot))
 assert checks and all(c['status']=='unverifiable' for c in checks)

def test_short_period_order_does_not_borrow_long_period_mention():
 from technical_reasoning import sma_reasoning_checks
 data=histogram_data_from_snapshot(CASES['1476_TW_v4_report_job_e5ffdeed7fab']['snapshot'])
 checks=sma_reasoning_checks('收盤價324元高於5日線、10日線、20日線及60日線，5/10/20日均線呈現標準多頭排列。',data)
 order=[c for c in checks if c.get('claim_type')=='bullish_sma_order']
 assert order and order[0]['status']=='verified'
 assert order[0]['comparison']['periods']==[5,10,20]

def test_negated_above_is_not_a_positive_assertion():
 from technical_reasoning import sma_reasoning_checks
 assert sma_reasoning_checks('股價未高於5日線。',{})==[]

@pytest.mark.parametrize('text',[
 '股價未形成5/10/20日均線多頭排列。',
 '收盤價高於5日線、10日線、20日線，但持續低於60日線。',
 '收盤價高於5日線、10日線、20日線及60日線，且5、10、20日均線呈現多頭排列。',
 '收盤價高於5日線、10日線、20日線及60日線，SMA5 > SMA10 > SMA20 的短中期多頭排列。',
])
def test_scope_and_negation_do_not_infer_false_long_term_order(text):
 from technical_reasoning import sma_reasoning_checks
 data=histogram_data_from_snapshot(CASES['1476_TW_v4_report_job_e5ffdeed7fab']['snapshot'])
 assert not any(c['status']=='mismatch' for c in sma_reasoning_checks(text,data))

@pytest.mark.parametrize('text',[
 '目前均線值順序為 SMA5 > SMA20 > SMA10，未達 SMA5 > SMA10 > SMA20 之標準多頭排列結構。',
 '當前均線順序為 SMA20 > SMA5 > SMA10，不符合典型5/10/20日多頭排列。',
 '動能延續情境：收盤價需帶量站穩20日均線之上。',
])
def test_negated_or_required_future_order_is_not_positive(text):
 from technical_reasoning import sma_reasoning_checks
 assert sma_reasoning_checks(text,{})==[]

def test_separate_deviation_comparison_does_not_widen_price_scope():
 from technical_reasoning import sma_reasoning_checks
 data=histogram_data_from_snapshot(CASES['1476_TW_v4_report_job_e5ffdeed7fab']['snapshot'])
 checks=sma_reasoning_checks('收盤價324元高於5日線，相較於20日線乖離率及60日線乖離率較大。',data)
 assert checks and checks[0]['comparison']['periods']==[5]
