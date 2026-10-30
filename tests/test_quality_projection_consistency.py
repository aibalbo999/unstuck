import json
from types import SimpleNamespace

def test_hydration_content_uses_same_current_evidence(monkeypatch):
 import report_quality_audit_rows as rows
 snapshot={'pipeline':'v4','data':{'ticker':'5880.TW'},'content_credibility':{'status':'warning'},'evidence_exit_gate':{'verdict':'approved'}}
 seen=[]
 monkeypatch.setattr(rows,'project_evidence_exit_gate',lambda *_:{'verdict':'rejected'})
 def project(value):
  seen.append(value['evidence_exit_gate']['verdict']);return {'status':'blocked' if seen[-1]=='rejected' else 'warning'}
 monkeypatch.setattr(rows,'project_content_credibility',project)
 row=rows.hydrate_report_from_index_row({'filename':'5880_TW_v4_report_test.html'},True,load_item=lambda *a,kind:SimpleNamespace(content=json.dumps(snapshot) if kind=='data' else '本文'),verify_snapshot_integrity=lambda _: {})
 assert seen==['rejected'] and row['content_credibility']['status']=='blocked'
 assert snapshot['evidence_exit_gate']['verdict']=='approved'

def test_nonblocked_current_projection_reaches_candidate(monkeypatch):
 from daily_decision_dashboard import build_daily_decision_dashboard
 import candidate_report_observations
 captured=[]
 monkeypatch.setattr(candidate_report_observations,'load_candidate_report_observations',lambda candidates,items,*a,**k:captured.extend(items) or {})
 filename='5880_TW_v4_report_test.html'
 projection={'ticker':'5880.TW','filename':filename,'pipeline_id':'v4','evidence_exit_gate':{'verdict':'caution','source_admission':{'source_eligible':False}}}
 build_daily_decision_dashboard(reports={},watchlist={},screener={'items':[{'ticker':'5880.TW','latest_report':{'filename':filename,'evidence_exit_gate':{'verdict':'approved'}}}]},performance={},free_mode={},quality_audit={'scope':'all_indexed_reports','selection_basis':'latest_per_ticker_pipeline','current_blocked_reports':[],'current_report_projections':[projection]},output_dir='/unused')
 assert captured[0]['latest_report']['evidence_exit_gate']==projection['evidence_exit_gate']
