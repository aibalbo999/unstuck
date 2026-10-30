"""Offline public checks; original-data replay remains in the local private corpus."""
"""Saved report/source boundaries; no model calls, refresh or historical rewrites."""

import copy,gzip,json

from pathlib import Path

from datetime import datetime

from zoneinfo import ZoneInfo

import pytest

from short_term_technical_indicators import calculate_technical_indicators,histogram_comparison

from technical_reasoning import histogram_reasoning_checks

from candidate_decision_explanation import explain_report_decision,compare_institutional_versions,summarize_report_decisions

from report_publication_gate import assert_report_publishable,ReportPublicationBlockedError

from evidence_exit_gate import evaluate_report_evidence

from trade_source_contract import source_catalog

from trade_source_guidance import technical_comparison_prompt

@pytest.mark.parametrize('before,after,relation',[(-.57,-.44,'negative_contraction'),(-.44,-.57,'negative_expansion'),(.57,.44,'positive_contraction'),(.44,.57,'positive_expansion'),(-.1,.1,'crossed_zero'),(.1,-.1,'crossed_zero'),(-.1,-.1,'negative_unchanged'),(0,0,'unchanged'),(-.1,0,'touches_zero')])
def test_histogram_sign_and_magnitude_are_separate(before,after,relation):
    result=histogram_comparison([before,after],[0,0],[{'date':'2026-10-13'},{'date':'2026-10-14'}],{'as_of':'2026-10-14','price_adjustment_basis':'same'},'receipt')
    assert result['relation']==relation
    assert result['signed_delta']==pytest.approx(after-before)
    assert result['magnitude_delta']==pytest.approx(abs(after)-abs(before))

@pytest.mark.parametrize('status',['warning','caution'])
def test_general_warning_does_not_kill_publication_or_research_observation(status):
    snapshot={'pipeline':'v4','content_credibility':{'status':status},'evidence_exit_gate':{'verdict':'caution'},'rerun_context':{'structured_outputs':{'24':{'trade_direction':'Neutral'}}}}
    assert_report_publishable(snapshot)
    x=explain_report_decision(snapshot)
    assert x['observation_allowed'] is True and x['actionable'] is False
    assert x['direction']=='Neutral' and not x['withdrawn']
    assert x['qualification_evaluation_status']=='not_independently_evaluated'

def test_hard_block_and_quality_withdrawal_not_mistaken_for_warning():
    x={'pipeline':'v4','content_credibility':{'status':'blocked'},'evidence_exit_gate':{'verdict':'rejected','source_admission':{'blockers':['executable_price_grid_not_verified']}},'rerun_context':{'structured_outputs':{'24':{'trade_direction':'Long'}}}}
    with pytest.raises(ReportPublicationBlockedError):assert_report_publishable(x)
    result=explain_report_decision(x)
    assert result['withdrawn'] and not result['observation_allowed'] and not result['actionable']
    assert any(r['kind']=='hard_evidence_gap' for r in result['reasons'])

def test_raw_negative_fcf_is_period_limitation_not_cause_or_catalyst():
    from trade_financial_risk import enforce_trade_financial_risk,NEGATIVE_FCF_WARNING
    from reporting.content_credibility_trade_basis import evaluate_trade_basis
    p={"trade_direction":"Neutral","core_catalyst":"等待來源核對","financial_risk_flags":[]}
    out=enforce_trade_financial_risk(p,{"free_cash_flow_raw":-25623500})
    assert NEGATIVE_FCF_WARNING in out["financial_risk_flags"]
    asserted={**out,"core_catalyst":"自由現金流為負，因此股價會上漲"}
    gate=evaluate_trade_basis({"parsed":{"trade_setup":asserted}},{"free_cash_flow_raw":-25623500},"v4")
    assert any(x["id"]=="v4_unverified_fcf_as_catalyst" for x in gate["blocking_issues"])

def test_unread_reports_and_unknown_direction_are_not_counted_as_qualified_zero():
    summary=summarize_report_decisions({"X":{"status":"unavailable"}},requested_count=30)
    assert summary["loaded_report_count"]==0 and summary["not_read_count"]==30
    assert summary["actionable_candidate_count"] is None

def test_escaped_decision_reasons_are_visible_without_inventing_trade_count():
    import subprocess
    script=Path(__file__).parents[1]/'backend/static/daily_candidate_review.js'
    data={'candidate_review':{'schema_version':'daily_candidate_review.v1','returned_count':1,'partition':{},'interpretation':'研究'},
          'top_candidates':[{'ticker':'TEST','report_evidence':{'status':'available','decision_explanation':{'direction_label':'Neutral','quality_label':'一般警示','reasons':[{'message':'<script>unsafe</script>'}]}}}]}
    code="const window={};"+script.read_text()+";console.log(window.StockAgentDailyCandidateReview.render("+json.dumps(data)+",s=>String(s).replaceAll('<','&lt;').replaceAll('>','&gt;')));"
    html=subprocess.run(['node','-e',code],capture_output=True,text=True,check=True).stdout
    assert '<script>unsafe' not in html and '&lt;script&gt;unsafe' in html
    assert '尚未逐檔獨立判定' in html and 'Neutral' in html

@pytest.mark.parametrize('section,field,value',[('report_conformance','status','blocked'),('report_lint','status','failed'),('evidence_exit_gate','verdict','rejected')])
def test_all_existing_publication_hard_gates_remain_observation_blockers(section,field,value):
    snapshot={'pipeline':'v4','content_credibility':{'status':'warning'},section:{field:value},'rerun_context':{'structured_outputs':{'24':{'trade_direction':'Neutral'}}}}
    result=explain_report_decision(snapshot)
    assert result['withdrawn'] and not result['observation_allowed'] and not result['actionable']
