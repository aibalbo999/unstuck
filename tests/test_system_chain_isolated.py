"""Joined control-flow integration; providers/renderer/Redis are fake boundaries.
No claim of live model quality or production dispatch is made by this test.
"""
import asyncio
from datetime import datetime
from types import SimpleNamespace
import pytest
import analysis_jobs,watchlist_service,watchlist_scheduler
from agent_runtime import AnalysisResult
from data_fetch import FetchResult
from reporting import ReportBundle
from report_artifacts import ReportArtifactLocator
from report_repository import DEFAULT_REPORT_REPOSITORY
from storage.report_storage import LocalFileStorage

@pytest.mark.parametrize('mode',['v1','v2','v3','v4'])
@pytest.mark.parametrize('blocked',[False,True])
def test_schedule_to_publication_and_replay_dedup(monkeypatch,tmp_path,mode,blocked):
    monkeypatch.setattr(watchlist_service,'WATCHLIST_PATH',tmp_path/'watchlist.json')
    watchlist_service.reset_watchlist_store_for_tests()
    watchlist_service.upsert_watchlist_item({'ticker':'2308.TW','pipeline':mode,'enabled':True,'schedule_slots':['post_market']})
    now=datetime(2026,10,7,19,0,tzinfo=watchlist_service.TAIPEI)
    claim=watchlist_service.claim_due_watchlist_items
    monkeypatch.setattr(watchlist_service,'claim_due_watchlist_items',lambda:claim(now))
    monkeypatch.setattr(watchlist_service.time,'sleep',lambda _:None)
    queued=[];events=[];updates=[];calls=[]
    def enqueue(key,fn,*args,queue_name=None):
        queued.append((key,fn,args,queue_name))
        return {'task_id':key,'created':True}
    def dispatch():return watchlist_scheduler._run_due_watchlist_batch(create_job=__import__('job_store').create_job,find_active_job=lambda t,p:{},task_queue=SimpleNamespace(enqueue_once=enqueue),run_stock_analysis_job=analysis_jobs.run_stock_analysis_job_async,emit_log=lambda _:None)
    assert len(dispatch()['queued'])==1
    assert dispatch()['queued']==[] and len(queued)==1
    assert queued[0][3]=='watchlist'
    async def fetch(request):return FetchResult(request=request,data={'ticker':request.ticker,'current_price':100},data_trust={'status':'fresh'})
    async def pipeline(request):
        calls.append(request.pipeline_id)
        return AnalysisResult(context={'ticker':'2308.TW','pipeline_id':mode,'final_audit':{'status':'passed','critical':[]}},pipeline_id=mode)
    async def render(request):
        quality={'content_credibility':{'status':'blocked'}} if blocked else {}
        return ReportBundle(html='<html>isolated integration fixture</html>',markdown='# isolated integration fixture',data_snapshot={'ticker':'2308.TW','pipeline':mode,'generated_at':'2026-10-07T11:00:00+00:00',**quality})
    output=tmp_path/'output'
    monkeypatch.setattr(analysis_jobs,'OUTPUT_DIR',str(output))
    monkeypatch.setattr(analysis_jobs,'has_api_keys',lambda:True)
    monkeypatch.setattr(analysis_jobs,'terminal_job_result',lambda _:None)
    monkeypatch.setattr(analysis_jobs,'is_job_cancel_requested',lambda _:False)
    monkeypatch.setattr(analysis_jobs,'STOCK_DATA_SERVICE',SimpleNamespace(fetch_async=fetch))
    monkeypatch.setattr(analysis_jobs,'PIPELINE_RUNNER',SimpleNamespace(run_async=pipeline))
    monkeypatch.setattr(analysis_jobs,'REPORT_RENDERER',SimpleNamespace(render_async=render))
    monkeypatch.setattr(analysis_jobs,'build_temporal_memory',lambda *a,**kw:{})
    monkeypatch.setattr(analysis_jobs,'append_event',lambda _,p:events.append(p))
    monkeypatch.setattr(analysis_jobs,'update_job',lambda _,status,**kw:updates.append(status))
    _,fn,args,_=queued[0]
    filename=asyncio.run(fn(*args))
    assert calls==[mode]
    if blocked:
        assert filename=='' and updates[-1]=='error' and 'done' not in updates
        assert events[-1]['phase']=='report_quality_blocked'
        assert list(output.rglob('*.html'))==[]
        return
    assert updates[-1]=='done'
    assert DEFAULT_REPORT_REPOSITORY.exists(filename,str(output))
    bundle=ReportArtifactLocator(LocalFileStorage(output)).require_bundle(filename)
    assert bundle.read_data_snapshot()['pipeline']==mode
    assert [e['filename'] for e in events if e['type']=='report_done']==[filename]
