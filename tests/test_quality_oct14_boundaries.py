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

CASES=json.loads(gzip.decompress((Path(__file__).parent/'fixtures/quality_oct14_saved.json.gz').read_bytes()))
CASE=next(c for c in CASES if c['ticker']=='2354.TW')

@pytest.mark.parametrize('before,after,relation',[(-.57,-.44,'negative_contraction'),(-.44,-.57,'negative_expansion'),(.57,.44,'positive_contraction'),(.44,.57,'positive_expansion'),(-.1,.1,'crossed_zero'),(.1,-.1,'crossed_zero'),(-.1,-.1,'negative_unchanged'),(0,0,'unchanged'),(-.1,0,'touches_zero')])
def test_histogram_sign_and_magnitude_are_separate(before,after,relation):
    result=histogram_comparison([before,after],[0,0],[{'date':'2026-10-13'},{'date':'2026-10-14'}],{'as_of':'2026-10-14','price_adjustment_basis':'same'},'receipt')
    assert result['relation']==relation
    assert result['signed_delta']==pytest.approx(after-before)
    assert result['magnitude_delta']==pytest.approx(abs(after)-abs(before))


def test_saved_2354_full_window_recomputes_correct_contraction_and_prompt():
    data=CASE['snapshot']['data'];before=copy.deepcopy(data)
    comparison=calculate_technical_indicators(data['daily_market_data'])['macd_histogram_comparison']
    assert comparison['relation']=='negative_contraction'
    assert comparison['previous']==pytest.approx(-.5697127,abs=1e-7)
    assert comparison['current']==pytest.approx(-.4423201,abs=1e-7)
    assert comparison['previous_date']=='2026-10-13' and comparison['observed_date']=='2026-10-14'
    assert comparison['input_bars_sha256']==data['technical_indicators']['input_window']['bars_sha256']
    text=technical_comparison_prompt(source_catalog(data))
    assert 'negative_contraction' in text and '絕對值' in text and '兩日計算收據' in text
    assert data==before


def test_saved_wrong_prose_is_rejected_but_corrected_relation_is_not_a_buy_signal():
    before=copy.deepcopy(CASE['snapshot'])
    checks=histogram_reasoning_checks(CASE['markdown'],CASE['snapshot']['data'])
    assert any(c['status']=='mismatch' for c in checks)
    gate=evaluate_report_evidence('MACD負柱目前擴張。',CASE['snapshot'])
    assert gate['verdict']=='rejected' and gate['technical_reasoning_checks'][0]['status']=='mismatch'
    correct=evaluate_report_evidence('MACD負柱目前收斂。',CASE['snapshot'])
    assert correct['technical_reasoning_checks'][0]['status']=='verified'
    assert CASE['snapshot']==before

@pytest.mark.parametrize('change',['missing_previous','basis','input_hash','as_of'])
def test_missing_or_incomparable_evidence_stays_unfinished(change):
    d=copy.deepcopy(CASE['snapshot']['data'])
    if change=='missing_previous':d['daily_market_data']['bars']=d['daily_market_data']['bars'][-1:]
    elif change=='basis':d['technical_indicators']['price_adjustment_basis']='different'
    elif change=='input_hash':d['technical_indicators']['input_window']['bars_sha256']='wrong'
    else:d['technical_indicators']['as_of']='2026-10-13'
    assert histogram_reasoning_checks('MACD負柱目前收斂。',d)[0]['status']=='unverifiable'

@pytest.mark.parametrize('text',['如果MACD負柱擴張，重新評估。','MACD負柱不是擴張。','過去MACD負柱擴張。','RSI擴張。','MACD柱狀體數值偏小，上攻動能尚未全面擴張。'])
def test_future_negated_and_unrelated_claims_not_misclassified(text):
    assert histogram_reasoning_checks(text,CASE['snapshot']['data'])==[]


def test_refreshed_snapshot_cannot_invalidate_old_analysis_using_new_prices():
    snapshot=copy.deepcopy(CASE['snapshot']);original=copy.deepcopy(snapshot['analysis_evidence']['sections']['analysis_input']['data'])
    snapshot['data']['daily_market_data']['bars'][-1]['close']=999
    snapshot['refreshed_without_analysis_rerun']=True
    gate=evaluate_report_evidence('MACD負柱目前收斂。',snapshot)
    assert gate['technical_reasoning_checks'][0]['status']=='verified'
    assert snapshot['analysis_evidence']['sections']['analysis_input']['data']==original

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


def test_today_saved_axes_and_counts_do_not_make_warning_or_validated_zero_a_veto():
    explanations=[explain_report_decision(c['snapshot']) for c in CASES]
    assert sum(x['direction']=='Neutral' for x in explanations)==15
    assert sum(x['direction']=='Long' for x in explanations)==0
    assert sum(x['withdrawn'] for x in explanations)==1  # 2354's explicit contradiction; ambiguous momentum is unfinished
    assert all(not x['actionable'] for x in explanations)
    observations={c['ticker']:{'status':'available','decision_explanation':x} for c,x in zip(CASES,explanations)}
    summary=summarize_report_decisions(observations,requested_count=16)
    assert summary['loaded_report_count']==16 and summary['research_observation_count']==15
    assert summary['actionable_candidate_count'] is None and summary['direction_counts']['Long']==0


def test_saved_1216_revision_is_delta_without_materiality_or_staleness_guess():
    snapshot=next(c['snapshot'] for c in CASES if c['ticker']=='1216.TW')
    old=copy.deepcopy(snapshot['data']['institutional_trading']);after=copy.deepcopy(old)
    observation=after['latest_official_observation'];before=old['latest_official_observation']['categories']['investment_trust']
    assert before==1224103
    observation['categories']['investment_trust']=1227103
    observation['raw_evidence']['raw_response_sha256']='f95e406e80b9729255d7c7d32c336defea66404bac82dc3edd4361dcd79537ee'
    result=compare_institutional_versions(old,after)
    assert result['status']=='revised_same_session' and result['changed_components'][0]['delta_shares']==3000
    assert result['changed_components'][0]['sign_changed'] is False
    assert 'materiality_not_established' in result['impact'] and not result['raw_bodies_independently_verified']
    after['latest_official_observation']['date']='2026-10-13'
    assert compare_institutional_versions(old,after)['status']=='older_session'
    after['latest_official_observation']['date']='2026-10-15'
    assert compare_institutional_versions(old,after)['status']=='newer_session'
    after['latest_official_observation']['unit']='lots'
    assert compare_institutional_versions(old,after)['status']=='scope_mismatch'


def test_ambiguous_momentum_is_not_false_histogram_mismatch():
    checks=histogram_reasoning_checks("MACD柱狀體為0.188，動能持續擴張。",CASE["snapshot"]["data"])
    assert checks[0]["status"]=="unverifiable" and checks[0]["reason"]=="histogram_assertion_scope_ambiguous"


def test_legacy_fcf_test_payload_is_incomplete_under_current_v4_contract():
    from test_financial_policy_admission_order import context
    from test_trade_source_completion import setup_payload
    from structured_output_runtime import process_agent_response
    c=context(100)
    process_agent_response(24,json.dumps(setup_payload()),c)
    assert "price_level_evidence" in c["_trade_incomplete_fields"]
    assert not c["structured_outputs"].get(24)


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


def test_real_locator_dashboard_attaches_direction_and_gaps_beyond_display_limit(tmp_path):
    from daily_decision_dashboard import build_daily_decision_dashboard
    items=[]
    for i,case in enumerate(CASES[:8]):
        name=case['filename'];(tmp_path/(name[:-5]+'.data.json')).write_text(json.dumps(case['snapshot']))
        items.append({'ticker':case['ticker'],'quality_funnel':{'outcome':'gray'},'ranking_status':'separate_dimensions_not_calibrated',
                      'latest_report':{'filename':name},'metrics':{}})
    before=copy.deepcopy(items)
    dashboard=build_daily_decision_dashboard(reports={'reports':[]},watchlist={'items':[]},screener={'items':items},performance={'population':{'validated_strategy_results':0}},free_mode={},output_dir=str(tmp_path),quality_audit={'scope':'all_indexed_reports','selection_basis':'latest_per_ticker_pipeline','current_blocked_reports':[]})
    summary=dashboard['candidate_review']['report_decision_summary']
    assert summary['loaded_report_count']==8 and summary['not_read_count']==0
    assert summary['direction_counts']['Neutral']==8 and summary['direction_counts']['Long']==0
    assert summary['actionable_candidate_count'] is None
    assert len(dashboard['top_candidates'])==5 and len(dashboard['candidate_review']['excluded_items'])==3
    assert all(c.get('report_evidence',{}).get('decision_explanation') for c in dashboard['candidate_review']['excluded_items'])
    assert items==before


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


def test_duplicate_input_session_cannot_prove_histogram_relation():
    data=copy.deepcopy(CASE['snapshot']['data'])
    data['daily_market_data']['bars'][-3]['date']=data['daily_market_data']['bars'][-4]['date']
    assert histogram_reasoning_checks('MACD負柱收斂。',data)[0]['status']=='unverifiable'


def test_specific_fcf_and_volume_warnings_explain_missing_evidence_without_research_veto():
    case=next(c for c in CASES if c['ticker']=='1402.TW')
    decision=explain_report_decision(case['snapshot'])
    assert decision['observation_allowed'] and not decision['actionable']
    details={r['code']:r for r in decision['reasons']}
    assert 'FCF所屬財期' in details['v4_raw_fcf_period_unverified']['next_evidence']
    assert details['v4_raw_fcf_period_unverified']['alone_blocks_observation'] is False


def test_null_legacy_original_input_is_unfinished_without_crashing():
    snapshot={'analysis_evidence':None,'refreshed_without_analysis_rerun':True,'data':CASE['snapshot']['data']}
    gate=evaluate_report_evidence('MACD負柱收斂。',snapshot)
    assert gate['technical_reasoning_checks'][0]['status']=='unverifiable' and gate['verdict']!='approved'


def test_current_exact_report_quality_overrides_saved_warning_in_counts(tmp_path):
    from daily_decision_dashboard import build_daily_decision_dashboard
    case=next(c for c in CASES if c['ticker']=='1402.TW');name=case['filename']
    (tmp_path/(name[:-5]+'.data.json')).write_text(json.dumps(case['snapshot']))
    items=[{'ticker':case['ticker'],'quality_funnel':{'outcome':'gray'},'latest_report':{'filename':name,'content_credibility':{'status':'warning'}}}]
    before=copy.deepcopy(items)
    blocked={'ticker':case['ticker'],'filename':name,'pipeline_id':'v4','content_credibility':{'status':'blocked','blocking_issues':[{'message':'synthetic current-rule rejection'}]}}
    args=dict(reports={'reports':[]},watchlist={},screener={'items':items},performance={},free_mode={},output_dir=str(tmp_path))
    dashboard=build_daily_decision_dashboard(**args,quality_audit={'scope':'all_indexed_reports','selection_basis':'latest_per_ticker_pipeline','current_blocked_reports':[blocked]})
    review=dashboard['candidate_review']
    assert review['partition']['quality_blocked']==1
    assert review['report_decision_summary']['research_observation_count']==0
    assert review['report_decision_summary']['quality_withdrawal_count']==1
    assert review['excluded_items'][0]['report_evidence']['decision_explanation']['withdrawn'] is True
    wrong={**blocked,'filename':'different_v4_report.html'}
    unrelated=build_daily_decision_dashboard(**args,quality_audit={'scope':'all_indexed_reports','selection_basis':'latest_per_ticker_pipeline','current_blocked_reports':[wrong]})
    assert unrelated['candidate_review']['report_decision_summary']['quality_withdrawal_count']==0
    assert items==before
