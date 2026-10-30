from datetime import datetime
from copy import deepcopy
from zoneinfo import ZoneInfo
import json
import subprocess
from pathlib import Path
from daily_candidate_review import evidence_context, quality_context, build_candidate_review
from daily_decision_dashboard import build_daily_decision_dashboard

MOMENT = datetime(2026,10,2,10,tzinfo=ZoneInfo('Asia/Taipei'))


def dashboard(items, blocked=None):
    return build_daily_decision_dashboard(reports={'reports':[]},watchlist={'items':[]},
        screener={'items':items,'pagination':{'total':100}},performance={},free_mode={},
        quality_audit={'scope':'all_indexed_reports','selection_basis':'latest_per_ticker_pipeline',
                       'current_blocked_reports':blocked or []})


def test_scan_and_report_times_cannot_fill_missing_observation_dates():
    item={'screen_date':'2026-10-01','latest_report':{'date':'2026-10-01 18:00'},
          'metrics':{'screen_date':'2026-10-01'},'updated_at':'2026-10-01T18:00:00+08:00'}
    e=evidence_context(item,moment=MOMENT)
    assert e['screen_date']=='2026-10-01' and e['report_generated_at']=='2026-10-01 18:00'
    assert e['price_observation_date'] is None and e['institutional_observation_date'] is None
    assert e['latest_source_dates_aligned'] is False and e['actionable'] is False


def test_aligned_dates_are_observations_only_not_an_execution_approval():
    e=evidence_context({'ticker':'2330.TW','metrics':{'price_observation_date':'2026-10-01','flow_observation_date':'2026-10-01'}},moment=MOMENT)
    assert e['latest_source_dates_aligned'] is True and e['actionable'] is False
    assert 'available_at' not in e


def test_nested_gray_is_retained_and_unknown_score_is_not_zero():
    original={'ticker':'2330.TW','score':None,'ranking_status':'separate_dimensions_not_calibrated',
              'triggers':[{'quality_funnel':{'outcome':'gray','missing_rules':[{'label':'ROE'}]}}]}
    before=deepcopy(original);d=dashboard([original]);c=d['top_candidates'][0]
    assert c['score'] is None and c['quality_outcome']=='gray'
    assert c['evidence']['missing_quality_indicators']==['ROE'] and original==before


def test_any_saved_reject_is_not_hidden_by_another_pass():
    item={'ticker':'2330.TW','quality_funnel':{'outcome':'pass'},'triggers':[{'quality_funnel':{'outcome':'reject'}}]}
    assert quality_context(item)['outcome']=='reject'
    d=dashboard([item]);assert d['top_candidates']==[]
    assert d['candidate_review']['partition']['saved_funnel_rejected']==1


def test_quality_withdrawal_wins_over_numeric_score_and_saved_green():
    blocked={'ticker':'1301.TW','filename':'1301_TW_v4_report_x.html','pipeline_id':'v4',
             'content_credibility':{'blocking_issues':[{'message':'均線方向與保存行情矛盾'}]}}
    d=dashboard([{'ticker':'1301.TW','score':999,'quality_funnel':{'outcome':'pass'}}],[blocked])
    assert not d['top_candidates']
    review=d['candidate_review'];assert review['partition']['quality_blocked']==1
    assert review['excluded_items'][0]['reasons']==['均線方向與保存行情矛盾']


def test_display_limit_is_not_a_quality_rejection_or_whole_market_claim():
    items=[{'ticker':f'{x}.TW','ranking_status':'separate_dimensions_not_calibrated','score':999-x} for x in range(8,0,-1)]
    d=dashboard(items);r=d['candidate_review']
    assert [c['ticker'] for c in d['top_candidates']]==[f'{x}.TW' for x in range(1,6)]
    assert all(c['score'] is None for c in d['top_candidates'])
    assert r['scope']=='returned_screener_page' and r['returned_count']==8 and r['screener_total_if_reported']==100
    assert sum(r['partition'].values())==8 and r['partition']['outside_display_limit']==3
    assert r['performance_maturity_context']['status']=='unavailable'


def test_maturity_is_separate_global_context_not_inferred_for_displayed_stock():
    candidates=[{'ticker':'2330.TW'}]
    review=build_candidate_review([{'ticker':'2330.TW'}],candidates,[],{},
        {'population':{'as_of':'2026-10-01','net_result_diagnostics':{'primary_nonoverlapping_slots':{'partition':{'awaiting_maturity':76}}}}},moment=MOMENT)
    assert review['performance_maturity_context']['partition']['awaiting_maturity']==76
    assert 'maturity_date' not in candidates[0]['evidence']


def test_real_js_renders_reasons_dates_and_escapes_source_text():
    d=dashboard([{'ticker':'2330.TW','reason':'<script>unsafe</script>','score':None}])
    root=Path(__file__).resolve().parents[1]/'backend/static'
    script="const window={};"+(root/'daily_candidate_review.js').read_text()+";const payload="+json.dumps(d)+";console.log(window.StockAgentDailyCandidateReview.render(payload,s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')));"
    html=subprocess.run(['node','-e',script],check=True,capture_output=True,text=True).stdout
    assert '<script>unsafe' not in html and '&lt;script&gt;unsafe' in html
    assert '行情 未確認' in html and '可執行候選尚未逐檔獨立判定' in html and '不代表全市場' in html


def test_operator_panel_load_mounts_readonly_candidate_review():
    d=dashboard([{'ticker':'2330.TW','score':None}])
    root=Path(__file__).resolve().parents[1]/'backend/static'
    script="""const window={};const actionList={innerHTML:'',addEventListener(){}};
    const document={getElementById:id=>id==='operator-action-list'?actionList:null,querySelectorAll:()=>[]};
    const text=()=>({tone:'ok',value:'ok',detail:''});
    window.StockAgentOperatorSummaryHelpers={activeJobText:text,quotaText:text,trustText:text,rerunText:text,operatorActionItems:()=>[]};
    window.StockAgentOperatorDashboardActions={actionableActionCount:()=>0,dashboardText:text,dashboardActionItems:()=>[]};
    """+(root/'daily_candidate_review.js').read_text()+(root/'operator_summary_panel.js').read_text()+";const payload="+json.dumps(d)+""";
    const empty=async()=>({});const panel=window.StockAgentOperatorSummaryPanel.create({apiClient:{
      fetchActiveJobs:empty,fetchApiQuotas:empty,fetchReports:empty,fetchWatchlist:empty,
      fetchDailyDecisionDashboard:async()=>payload,requestJson:()=>{throw Error('no mutation permitted')}}});
    panel.load().then(()=>console.log(actionList.innerHTML));"""
    html=subprocess.run(['node','-e',script],check=True,capture_output=True,text=True).stdout
    assert '兩週研究名單' in html and '2330.TW' in html and '行情 未確認' in html
