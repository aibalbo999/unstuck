import json
from test_sma_reasoning_regressions import CASES
from technical_reasoning import sma_reasoning_checks,histogram_data_from_snapshot
from evidence_exit_gate import evaluate_report_evidence

def test_sma_comparison_is_json_stable_without_changing_period_numbers():
    data=histogram_data_from_snapshot(CASES['1476_TW_v4_report_job_e5ffdeed7fab']['snapshot'])
    checks=sma_reasoning_checks('收盤價324元高於5日線、10日線、20日線及60日線，5/10/20日均線呈現標準多頭排列。',data)
    assert checks and all(c['comparison']['sma_values']for c in checks)
    assert checks==json.loads(json.dumps(checks))
    assert all(type(k)is str for c in checks for k in c['comparison']['sma_values'])
    assert all(type(p)is int for c in checks for p in c['comparison']['periods'])
    assert all(c['independent_primary_source_verified']is False for c in checks)

def test_saved_false_sma_claim_stays_mismatch_after_json_roundtrip():
    c=CASES['2855_TW_v4_report_job_b596a5c41cb6']
    r=evaluate_report_evidence(c['markdown'],c['snapshot'])
    checks=r['technical_reasoning_checks']
    assert any(c['status']=='mismatch'for c in checks)
    assert checks==json.loads(json.dumps(checks))
    assert r['verdict']=='rejected'
