"""No production API, queue, provider or model calls in these regressions."""
import asyncio
import json
from pathlib import Path
import subprocess

import pytest

STATIC = Path(__file__).resolve().parents[1] / 'backend/static'


def node(script):
    result = subprocess.run(['node', '-e', script.replace('__STATIC__', json.dumps(str(STATIC)))],
                            text=True, capture_output=True, check=True, timeout=15)
    return json.loads(result.stdout)


def test_preview_duplicate_events_share_one_request_and_stream_then_allow_explicit_retry():
    result = node("""
global.window={};require(__STATIC__+'/report_rerun_controls.js');require(__STATIC__+'/report_rerun.js');
let release;const pending=new Promise(r=>release=r), calls=[], streams=[], errors=[];
window.StockAgentReportRerunStream={open:async value=>{streams.push(value);await pending;throw Error('fixture rejection')}};
const options={previewReport:{filename:'1623_TW_v1_report_20260927_124912.html'},scope:'full_report',
apiClient:{requestJson:async (url,opt)=>{calls.push({url,...opt});return {queued:true,job_id:'fixture',stream_url:'/fixture-stream'}}},
notify:{error:message=>errors.push(message)},loadHistory:async()=>{}};
(async()=>{const a=window.StockAgentReportRerun.rerunPreviewReport(options);
const b=window.StockAgentReportRerun.rerunPreviewReport(options);await new Promise(setImmediate);
const during={calls:calls.length,streams:streams.length};release();await Promise.all([a,b]);
await window.StockAgentReportRerun.rerunPreviewReport(options);
console.log(JSON.stringify({during,calls,streams:streams.length,errors:errors.length}));})();
""")
    assert result['during'] == {'calls': 1, 'streams': 1}
    assert len(result['calls']) == 2 and result['streams'] == 2 and result['errors'] == 2
    assert result['calls'][0]['headers']['X-Stock-Agent-Action-Source'] == 'report_preview'


def test_tracking_load_and_repeated_refresh_do_not_submit_reruns_and_bulk_is_not_reentrant():
    result = node("""
global.window={StockAgentDecisionTrackingHelpers:{trackedGroups:()=>[],trackedSet:()=>new Set(),
uniqueRecommendedActions:p=>p.items}};require(__STATIC__+'/decision_tracking_panel.js');
let release;const pending=new Promise(r=>release=r),calls=[];
const payload={items:[{type:'rerun_full_report',filename:'fixture.html'}]};
const panel=window.StockAgentDecisionTrackingPanel.create({apiClient:{fetchDecisionTracking:async()=>payload,
refreshDecisionTracking:async()=>payload,requestJson:async(url,opt)=>{calls.push({url,...opt});await pending;return {queued:true}}},
historyPanel:{renderTrackingGroups(){}},elements:{}});
(async()=>{await panel.load();await panel.load();await panel.refresh();const before=calls.length;
const a=panel.runAllRecommendedActions(),b=panel.runAllRecommendedActions();await new Promise(setImmediate);
const during=calls.length;release();await Promise.all([a,b]);console.log(JSON.stringify({before,during,calls}));})();
""")
    assert result['before'] == 0 and result['during'] == 1
    assert result['calls'][0]['headers']['X-Stock-Agent-Action-Source'] == 'decision_tracking'


def test_quality_has_a_bounded_budget_for_observed_41_second_complete_audits(monkeypatch):
    import tracking_read_executor as module
    # Simulate elapsed work without sleeping for a minute. The actual reader
    # deadline is inspected by the executor tests; this checks both nested budgets.
    deadlines = []
    original_timeout = asyncio.timeout
    def timeout(seconds):
        deadlines.append(seconds)
        return original_timeout(seconds)
    class Preparation:
        async def read(self, request):return ('reports', 'current')
    class Quality:
        async def read(self, request):return {'status': 'complete', 'audited_reports': 0}
    monkeypatch.setattr(module.asyncio, 'timeout', timeout)
    monkeypatch.setattr(module, 'tracking_preparations', Preparation())
    child_budget = module.quality_reads._timeout_seconds
    monkeypatch.setattr(module, 'quality_reads', Quality())
    assert asyncio.run(module.read_quality_audit('reports'))['audited_reports'] == 0
    assert 41 < child_budget <= 60
    assert child_budget < deadlines[0] <= 85


@pytest.mark.parametrize('reason', ['quality_read_timeout','quality_sources_changed','quality_rules_require_reload'])
def test_quality_failures_still_return_unavailable_without_saved_success(monkeypatch, reason):
    import tracking_read_executor as module
    from performance_read_executor import PerformanceReadUnavailable
    class Preparation:
        async def read(self, request):return ('reports','current')
    class Quality:
        async def read(self, request):raise PerformanceReadUnavailable(reason)
    monkeypatch.setattr(module,'tracking_preparations',Preparation())
    monkeypatch.setattr(module,'quality_reads',Quality())
    value=asyncio.run(module.read_quality_audit('reports'))
    assert value['read_unavailable'] is True and value['reason']==reason
    assert 'current_report_projections' not in value


@pytest.mark.parametrize('state', ['failed', 'empty', 'success'])
def test_operator_refresh_is_read_only_and_failure_stays_visible(state):
    script = """
const state=__STATE__, callbacks={}, nodes={};
const makeNode=()=>({dataset:{},querySelector:selector=>selector==='strong'?{textContent:''}:{textContent:''}});
const strong={textContent:''},em={textContent:''},shift={dataset:{},querySelector:s=>s==='strong'?strong:em};
nodes['operator-action-list']={innerHTML:'',addEventListener:(type,fn)=>callbacks[type]=fn};
global.document={getElementById:id=>nodes[id]||null,querySelectorAll:()=>[shift]};
const ok=()=>({tone:'ok',value:'正常'}), calls=[];
global.window={StockAgentOperatorSummaryHelpers:{activeJobText:ok,quotaText:ok,trustText:ok,rerunText:ok,operatorActionItems:()=>[]},
StockAgentOperatorDashboardActions:{actionableActionCount:()=>0,dashboardText:ok,dashboardActionItems:()=>[]}};
require(__STATIC__+'/operator_summary_panel.js');
const read=async()=>({}),panel=window.StockAgentOperatorSummaryPanel.create({apiClient:{fetchActiveJobs:read,fetchApiQuotas:read,
fetchReports:read,fetchWatchlist:read,fetchDailyDecisionDashboard:async()=>{if(state==='failed')throw Error('HTTP 503');return {top_candidates:state==='empty'?[]:[{ticker:'fixture'}]}},
requestJson:async()=>calls.push('POST')}});
(async()=>{await Promise.all([panel.load(),panel.load()]);await panel.load();
console.log(JSON.stringify({calls,value:strong.textContent,detail:em.textContent,html:nodes['operator-action-list'].innerHTML}));})();
""".replace('__STATE__', json.dumps(state))
    value = node(script)
    assert value['calls'] == []
    if state == 'failed':
        assert value['value'] == '工作台查核未就緒' and '讀取失敗' in value['detail']
    else:
        assert value['value'] == '可正常操作'


def test_rerun_request_audit_records_only_allowlisted_surface_and_unique_server_id(tmp_path, caplog):
    import logging
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_routes.reports import ReportRouteDeps, create_reports_router
    from report_persistence import report_bundle_keys_for_filename
    from storage.report_storage import InMemoryStorage
    filename='1623_TW_v1_report_20260927_124912.html'
    keys=report_bundle_keys_for_filename(filename)
    storage=InMemoryStorage()
    storage.save_report(keys.html_key,b'fixture',content_type='text/html')
    storage.save_report(keys.data_key,b'{}',content_type='application/json')
    enqueued=[]
    class Queue:
        def enqueue(self,*args):enqueued.append(args)
    app=FastAPI()
    app.include_router(create_reports_router(ReportRouteDeps(
        get_output_dir=lambda:str(tmp_path),get_report_storage=lambda:storage,
        get_refresh_service=lambda:None,get_pipeline_runner=lambda:None,get_report_renderer=lambda:None,
        get_task_queue=Queue,run_report_rerun_job=lambda *a:pytest.fail('worker must never run'),
        create_job=lambda *a:'fixture-job',get_job=lambda *a:{},get_events_since=lambda *a:[],
        update_job=lambda *a,**kw:None,append_event=lambda *a:None,request_job_cancel=lambda *a:False,
        print_streamed_event=lambda *a:None,require_mutation_authorized=lambda _:None)))
    caplog.set_level(logging.INFO,logger='uvicorn.error')
    client=TestClient(app)
    ids=[]
    for source in ['report_preview', 'decision_tracking', 'operator_summary', 'secret-token-do-not-log']:
        response=client.post(f'/api/report/{filename}/rerun?scope=full_report',headers={
            'X-Stock-Agent-Action-Source':source,'X-Mutation-Token':'private-token-do-not-log'})
        assert response.status_code==200 and response.json()['queued'] is True
        ids.append(response.json()['request_id'])
    assert len(set(ids))==4 and len(enqueued)==4  # fake queue only, no worker
    records=[r.message for r in caplog.records if 'report_rerun_request ' in r.message]
    assert len(records)==4 and 'action_source=unspecified' in records[-1]
    assert all(secret not in '\n'.join(records) for secret in ['secret-token-do-not-log','private-token-do-not-log'])
    assert all(request_id in record for request_id,record in zip(ids,records))


@pytest.mark.parametrize('state', ['empty', 'success', 'unavailable'])
def test_actual_dashboard_route_repeated_reads_preserve_truthful_status(monkeypatch,tmp_path,state):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import api_routes.watchlist as routes
    calls=[]
    async def quality(_):
        calls.append('quality')
        if state=='unavailable':
            return {'status':'unavailable','read_unavailable':True,'reason':'quality_read_timeout'}
        return {'scope':'all_indexed_reports','selection_basis':'latest_per_ticker_pipeline',
                'audited_reports':0,'current_report_projections':[],'current_blocked_reports':[]}
    def reports(**kw):
        calls.append('reports')
        return {'reports':[] if state=='empty' else [{'filename':'fixture.html','ticker':'FIXTURE','pipeline_id':'v1'}]}
    monkeypatch.setattr(routes.report_history_service,'list_reports',reports)
    monkeypatch.setattr(routes.watchlist_service,'list_watchlist_with_report_alerts',lambda *a,**kw:{'items':[]})
    monkeypatch.setattr(routes.market_screener,'list_auto_screener_watchlist',lambda *a,**kw:{'items':[]})
    monkeypatch.setattr(routes.decision_tracking_service,'compute_tracking_performance_stats',lambda *a:{})
    monkeypatch.setattr(routes.job_observability,'build_ops_dashboard_snapshot',lambda **kw:{})
    monkeypatch.setattr(routes,'get_delivery_audit_summary',lambda:{})
    app=FastAPI()
    app.include_router(routes.create_watchlist_router(routes.WatchlistRouteDeps(
        get_output_dir=lambda:str(tmp_path),get_task_queue=lambda:pytest.fail('GET must not use queue'),
        run_stock_analysis_job=lambda *a:pytest.fail('GET must not run analysis'),create_job=lambda *a:pytest.fail('GET must not create job'),
        find_active_job=lambda *a:{},require_mutation_authorized=lambda _:None,read_quality_audit=quality)))
    with TestClient(app) as client:
        for _ in range(3):
            response=client.get('/api/watchlist/daily-dashboard')
            assert response.status_code==(503 if state=='unavailable' else 200)
            if state=='unavailable':assert response.json()['reason']=='quality_read_timeout'
            else:assert response.json()['top_candidates']==[]
    assert calls.count('quality')==3
    assert calls.count('reports')==(0 if state=='unavailable' else 3)


def test_overlapping_dashboard_gets_share_only_inflight_read_and_failure_is_retryable():
    result=node("""
global.window={};let fetches=0,failed=false;const releases=[],resolve=()=>releases.splice(0).forEach(r=>r());
global.fetch=async()=>{fetches++;await new Promise(r=>releases.push(r));return {ok:!failed,status:failed?503:200,text:async()=>JSON.stringify(failed?{message:'fixture unavailable'}:{revision:fetches})}};
require(__STATIC__+'/api_request.js');window.StockAgentApiClient={requestJson:window.StockAgentApiRequest.requestJson};
require(__STATIC__+'/api_client_extensions.js');const read=window.StockAgentApiClient.fetchDailyDecisionDashboard;
(async()=>{const a=read(),b=read();await new Promise(setImmediate);const overlap=fetches;resolve();const results=await Promise.all([a,b]);
failed=true;const c=read();await new Promise(setImmediate);resolve();let error;try{await c}catch(e){error=e.message}
failed=false;const d=read();await new Promise(setImmediate);resolve();const retried=await d;
console.log(JSON.stringify({overlap,fetches,results,error,retried}));})();
""")
    assert result['overlap']==1 and result['fetches']==3
    assert result['results']==[{'revision':1},{'revision':1}]
    assert result['error']=='fixture unavailable' and result['retried']=={'revision':3}


def test_operator_duplicate_actions_are_blocked_even_when_button_is_replaced():
    value=node("""
const handlers={},reads=async()=>({}),calls=[],releases=[];
const list={addEventListener:(type,fn)=>handlers[type]=fn};
global.document={getElementById:id=>id==='operator-action-list'?list:null,querySelectorAll:()=>[]};
const ok=()=>({tone:'ok'});
global.window={StockAgentOperatorSummaryHelpers:{activeJobText:ok,quotaText:ok,trustText:ok,rerunText:ok,operatorActionItems:()=>[]},
StockAgentOperatorDashboardActions:{actionableActionCount:()=>0,dashboardText:ok,dashboardActionItems:()=>[]}};
require(__STATIC__+'/operator_summary_panel.js');
window.StockAgentOperatorSummaryPanel.create({apiClient:{fetchActiveJobs:reads,fetchApiQuotas:reads,fetchReports:reads,
fetchWatchlist:reads,fetchDailyDecisionDashboard:reads,requestJson:async(url,opt)=>{calls.push({url,...opt});await new Promise(r=>releases.push(r));return {queued:true}}}});
const event=()=>{const button={dataset:{operatorAction:'rerun-report',filename:'fixture.html'},textContent:'完整重跑',disabled:false};
return {target:{closest:selector=>selector==='[data-operator-action]'?button:null}}};
(async()=>{const a=handlers.click(event()),b=handlers.click(event());await new Promise(setImmediate);const during=calls.length;
releases.splice(0).forEach(r=>r());await Promise.all([a,b]);const c=handlers.click(event());await new Promise(setImmediate);
releases.splice(0).forEach(r=>r());await c;console.log(JSON.stringify({during,calls}));})();
""")
    assert value['during']==1 and len(value['calls'])==2
    assert value['calls'][0]['headers']['X-Stock-Agent-Action-Source']=='operator_summary'
