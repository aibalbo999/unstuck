from datetime import datetime
from zoneinfo import ZoneInfo
from candidate_decision_explanation import explain_report_decision

def test_neutral_warning_does_not_imply_sources_admitted():
 snapshot={'pipeline':'v4','data':{'ticker':'2330.TW','daily_market_data':{'as_of':'2026-10-15'},'institutional_trading':{'latest_date':'2026-10-14'}},'rerun_context':{'structured_outputs':{'24':{'trade_direction':'Neutral'}}},'content_credibility':{'status':'warning'},'evidence_exit_gate':{'verdict':'caution','source_admission':{'source_eligible':False,'blockers':[],'source_warnings':['latest_institutional_session_missing']}}}
 e=explain_report_decision(snapshot,moment=datetime(2026,10,15,22,47,tzinfo=ZoneInfo('Asia/Taipei')))
 assert e['observation_allowed'] is True and e['actionable'] is False
 assert e['source_evidence_state']['source_eligible'] is False
 assert e['source_evidence_state']['institutional_snapshot_state']=='latest_session_missing_from_snapshot'
 assert e['source_evidence_state']['external_newer_evidence_checked'] is False
 assert '來源未准入' in e['quality_label']

def test_current_projection_and_saved_gate_remain_distinct():
 snapshot={'pipeline':'v4','data':{},'evidence_exit_gate':{'verdict':'caution','source_admission':{'source_eligible':False}}}
 latest={'_quality_projection_basis':'current_rules_readonly','evidence_exit_gate':{'verdict':'approved','source_admission':{'source_eligible':True}}}
 e=explain_report_decision(snapshot,latest)
 assert e['source_evidence_state']['source_eligible'] is True
 assert e['source_evidence_state']['saved_gate_source_eligible'] is False
 assert e['source_evidence_state']['basis']=='current_readonly_projection'
 assert e['source_evidence_state']['historical_available_at_verified'] is False
