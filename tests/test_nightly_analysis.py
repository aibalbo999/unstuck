"""Bounded overnight work uses isolated SQLite and installed RQ without network."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace
import pytest
import job_store
import nightly_analysis as nightly
import nightly_analysis_policy as policy
import nightly_analysis_store as store
import nightly_analysis_status as status
import watchlist_service
from data_fetch import FetchResult
from test_watchlist_dispatch_recovery import MemoryRedis, queue, noop

NOW = datetime(2026,10,30,22,35,tzinfo=policy.TZ) # Friday
ITEM = {'ticker':'2308.TW','pipeline':'v4','enabled':True,'schedule_slots':['post_market']}
GOOD = {'eligible':True,'reason_codes':[]}

@pytest.fixture
def env(monkeypatch,tmp_path):
    monkeypatch.setenv('NIGHTLY_TAIWAN_ANALYSIS_ENABLED','1')
    monkeypatch.setattr(store,'path',lambda:tmp_path/'nightly.sqlite3')
    monkeypatch.setattr(policy,'session_state',lambda session,ticker:'open')
    monkeypatch.setattr(nightly,'source_readiness',lambda *a:deepcopy(GOOD))
    monkeypatch.setattr(watchlist_service,'list_watchlist',lambda:{'items':[deepcopy(ITEM)]})
    calls=[]
    async def fetch(request):
        calls.append(request)
        assert request.options.force_refresh
        return FetchResult(request=request,data={'ticker':request.ticker,'current_price':100})
    redis=MemoryRedis()
    return SimpleNamespace(calls=calls,redis=redis,queue=queue(redis),service=SimpleNamespace(fetch_async=fetch))

def tick(env,now=NOW):
    return asyncio.run(nightly.process_one(service=env.service,queue=env.queue,runner=noop,now=now))

def test_session_boundaries_and_friday_delivery():
    assert policy.session_for_acquisition(NOW-timedelta(minutes=1)) is None
    assert policy.session_for_acquisition(NOW)=='2026-10-30'
    assert policy.session_for_acquisition(NOW+timedelta(hours=5))=='2026-10-30'
    assert policy.session_for_acquisition(NOW+timedelta(hours=8,minutes=25)) is None
    assert policy.delivery_session(NOW+timedelta(hours=9))=='2026-10-30'
    with pytest.raises(ValueError): policy.session_for_acquisition(NOW.replace(tzinfo=None))

@pytest.mark.parametrize('failure',['offline','before','after'])
def test_queue_failures_resume_same_frozen_input_and_single_task(env,failure):
    setattr(env.redis,failure,True)
    assert tick(env)['status']=='waiting_error'
    first=store.read_rows()[0]
    assert first['state']=='prepared'
    setattr(env.redis,failure,False)
    assert tick(env,NOW+timedelta(minutes=16))['status']=='dispatched'
    assert tick(env,NOW+timedelta(hours=4))['status']=='idle'
    assert store.read_rows()[0]['job_id']==first['job_id']
    assert len(env.calls)==1
    assert env.redis.lists['rq:queue:watchlist']==[('analysis:'+first['job_id']).encode()]


def test_closed_unknown_session_never_creates_work(env,monkeypatch):
    monkeypatch.setattr(policy,'session_state',lambda *a:'closed')
    assert tick(env)['status']=='no_open_scope'
    assert store.read_rows()==[] and not env.calls


def test_old_completed_slot_does_not_skip_nightly_and_scope_frozen(env,monkeypatch):
    item={**ITEM,'last_run_dates':{'post_market':'2026-10-30'}}
    monkeypatch.setattr(watchlist_service,'list_watchlist',lambda:{'items':[item]})
    assert tick(env)['status']=='dispatched'
    monkeypatch.setattr(watchlist_service,'list_watchlist',lambda:{'items':[item,{**ITEM,'ticker':'2330.TW'}]})
    assert tick(env,NOW+timedelta(hours=1))['status']=='idle'
    assert len(store.read_rows())==1


@pytest.mark.parametrize('change', ['removed', 'disabled', 'unknown_added'])
def test_frozen_scope_resumes_after_watchlist_or_calendar_changes(env, monkeypatch, change):
    store.seed('2026-10-30', [ITEM], NOW)
    current = [] if change == 'removed' else [{**ITEM, 'enabled': False}] if change == 'disabled' else [ITEM, {**ITEM, 'ticker': '2330.TW'}]
    monkeypatch.setattr(watchlist_service, 'list_watchlist', lambda: {'items': current})
    if change == 'unknown_added':
        monkeypatch.setattr(policy, 'session_state', lambda session, ticker: 'unknown' if ticker == '2330.TW' else 'open')
    assert tick(env)['status'] == 'dispatched'
    assert [row['ticker'] for row in store.read_rows()] == ['2308.TW']


def test_old_active_waits_without_attaching(env):
    old=job_store.create_job('2308.TW','v4')
    assert tick(env)['status']=='waiting_active'
    assert store.read_rows()[0]['job_id']!=old and not env.calls
    job_store.update_job(old,'done',filename='old.html')
    assert tick(env,NOW+timedelta(minutes=6))['status']=='dispatched'


def test_source_failure_bounded_no_jobs_or_queue(env,monkeypatch):
    monkeypatch.setattr(nightly,'source_readiness',lambda *a:{'eligible':False,'reason_codes':['provisional']})
    for i in range(6): assert tick(env,NOW+timedelta(minutes=16*i))['status']=='waiting_source'
    assert tick(env,NOW+timedelta(minutes=96))['status']=='idle'
    row=store.read_rows()[0]
    assert row['attempts']==6 and not job_store.get_job(row['job_id']) and env.redis.lists=={}

@pytest.mark.parametrize('state',['running','waiting_retry','done','error','cancelled'])
def test_execution_receipt_never_requeues(env,state):
    store.seed('2026-10-30',[ITEM],NOW)
    row=store.read_rows()[0]
    job_store.create_job(row['ticker'],row['pipeline'],job_id=row['job_id'])
    job_store.update_job(row['job_id'],state)
    assert tick(env)['status']=='existing_execution'
    assert not env.calls and env.redis.lists=={}


def test_expired_owner_cannot_modify_or_acknowledge(env):
    store.seed('2026-10-30',[ITEM],NOW)
    old=store.claim('2026-10-30',NOW)
    later=NOW+timedelta(minutes=11)
    new=store.claim('2026-10-30',later)
    assert not store.update_owned(old,later,state='dispatched')
    assert store.get_work(old['job_id'])['lease_token']==new['lease_token']


def test_feature_off_does_nothing(env,monkeypatch):
    monkeypatch.setenv('NIGHTLY_TAIWAN_ANALYSIS_ENABLED','0')
    assert tick(env)['status']=='outside_window'
    assert store.read_rows()==[]


def test_prepared_input_rejects_changed_integrity_session_or_sources(env,monkeypatch):
    tick(env);row=store.read_rows()[0]
    data=nightly.prepared_input(row['job_id'],row['ticker'],row['pipeline'])
    data['nightly_analysis']['session_date']='2026-10-29'
    with pytest.raises(ValueError,match='binding'):nightly.validate_input(row,data)
    monkeypatch.setattr(nightly,'source_readiness',lambda *a:{'eligible':False,'reason_codes':['stale']})
    with pytest.raises(ValueError,match='not ready'):nightly.prepared_input(row['job_id'],row['ticker'],row['pipeline'])


def test_policy_requires_both_official_source_gates_and_exact_price_date(env,monkeypatch):
    import report_source_admission as admission
    import market_session_admission as sessions
    monkeypatch.setattr(sessions,'assess_daily_session_integrity',lambda *a,**k:GOOD)
    calls=[]
    monkeypatch.setattr(admission,'institutional_admission',lambda *a:(calls.append('institutional') or {'eligible':False,'reason':'precutoff'}))
    monkeypatch.setattr(admission,'price_admission',lambda *a:(calls.append('price') or {'eligible':False,'reason':'unarchived'}))
    r=policy.source_readiness({'ticker':'2308.TW','daily_market_data':{'as_of':'2026-10-29'}},'2026-10-30','2308.TW')
    assert not r['eligible'] and set(r['reason_codes'])=={'price_session_mismatch','precutoff','unarchived','institutional_security_or_market_mismatch','official_provider_price_mismatch_or_unverified'}
    assert calls==['institutional','price']


def test_readiness_requires_new_report_and_current_nonblocking_quality(env,monkeypatch):
    monkeypatch.setattr(status,'source_readiness',lambda *a:GOOD)
    work={'job_id':'new','session_date':'2026-10-30','ticker':'2308.TW'}
    data={'nightly_analysis':{'job_id':'new','session_date':'2026-10-30'}}
    snapshot={'data':data}
    projected={'snapshot_integrity':{'valid':True},'analysis_completeness':{'status':'observation','quality_recorded':True,'basis':'source_assessment','source_status':'observation'},'report_conformance':{'status':'warning'},'content_credibility':{'status':'warning'},'evidence_exit_gate':{'verdict':'caution'}}
    job={'status':'done','filename':'new.html'}
    assert status.assess_report(work,job,snapshot,projected)['ready']
    for key,value in [('analysis_completeness',{'status':'degraded'}),('evidence_exit_gate',{'verdict':'rejected'}),('content_credibility',{'status':'blocked'}),('decision_freshness',{'requires_rerun':True}),('snapshot_integrity',{'valid':False}),('analysis_text_stale',True)]:
        assert not status.assess_report(work,job,snapshot,{**projected,key:value})['ready']
    assert not status.assess_report(work,job,{'data':{},'refreshed_without_analysis_rerun':True},projected)['ready']
    assert not status.assess_report(work,{'status':'running'},snapshot,projected)['ready']


def test_snapshot_size_governance_preserves_session_binding():
    from data_trust_snapshot_integrity import apply_snapshot_size_governance
    marker={'job_id':'new','session_date':'2026-10-30','policy':policy.POLICY}
    snapshot=apply_snapshot_size_governance({'data':{'nightly_analysis':marker,'noncore':'x'*10000}},max_bytes=200)
    assert snapshot['data']['nightly_analysis']==marker and 'noncore' not in snapshot['data']

@pytest.mark.parametrize('slots,selected,expected',[(['pre_market'],'v4',1),(['post_market'],'v3',1),(['post_market'],'v4',0)])
def test_trigger_deferred_only_when_nightly_covers_same_mode(env,monkeypatch,slots,selected,expected):
    item={**ITEM,'schedule_slots':slots,'triggers':[{'type':'test'}]}
    monkeypatch.setattr(watchlist_service,'_sync_store_config',lambda:None)
    monkeypatch.setattr(watchlist_service,'list_watchlist',lambda:{'items':[item]})
    async def radar(*a):return {}
    async def no_wait(*a):return None
    monkeypatch.setattr(watchlist_service,'fetch_radar_data',radar)
    monkeypatch.setattr(watchlist_service,'asyncio',SimpleNamespace(sleep=no_wait))
    monkeypatch.setattr(watchlist_service,'evaluate_watchlist_triggers',lambda *a,**k:[{'matched':True,'pipeline_selected':selected}])
    monkeypatch.setattr(watchlist_service.watchlist_trigger_store,'record_trigger_event',lambda *a:{'inserted':True})
    queued=[]
    monkeypatch.setattr(watchlist_service,'_enqueue_watchlist_analysis',lambda *a:queued.append(a))
    result=asyncio.run(watchlist_service.monitor_watchlist_triggers(data_service=None,create_job=lambda *a:'test',find_active_job=lambda *a:{},task_queue=None,run_stock_analysis_job=noop,now=NOW))
    assert len(queued)==expected and len(result['queued'])==expected


def test_unknown_calendar_does_not_freeze_empty_scope(env,monkeypatch):
    monkeypatch.setattr(policy,'session_state',lambda *a:'unknown')
    assert tick(env)['status']=='waiting_calendar' and store.read_rows()==[]
    monkeypatch.setattr(policy,'session_state',lambda *a:'open')
    assert tick(env,NOW+timedelta(minutes=1))['status']=='dispatched'


def test_reconciliation_preserves_nightly_pending_ack(env,monkeypatch):
    import worker_main
    env.redis.before=True
    tick(env)
    row=store.read_rows()[0]
    monkeypatch.setattr(worker_main,'_rq_job_states',lambda *a:{})
    assert worker_main.reconcile_abandoned_rq_jobs(SimpleNamespace(task_queue=SimpleNamespace(queues={'q':object()})))==0
    assert job_store.get_job(row['job_id'])['status']=='queued'


def test_status_uses_locator_and_latest_projection(env,monkeypatch):
    import json
    import report_history_storage, report_index
    from storage.report_storage import InMemoryStorage
    from report_paths import report_storage_key_for_filename, report_markdown_filename_for_report
    from data_trust import data_snapshot_filename_for_report
    tick(env)
    work=store.read_rows()[0]
    filename='2308_TW_v4_report_20261030_231000.html'
    job_store.update_job(work['job_id'],'done',filename=filename)
    snapshot={'data':json.loads(work['data_json'])}
    projected={'filename':filename,'snapshot_integrity':{'valid':True},
        'analysis_completeness':{'status':'quality_warning','basis':'source_assessment','source_status':'observation','quality_recorded':True},
        'report_conformance':{'status':'warning'},'content_credibility':{'status':'warning'},'evidence_exit_gate':{'verdict':'caution'}}
    storage=InMemoryStorage()
    html=report_storage_key_for_filename(filename); folder=html.rsplit('/',1)[0]
    storage.save_report(html,b'<html></html>',content_type='text/html')
    storage.save_report(folder+'/'+report_markdown_filename_for_report(filename),b'# report',content_type='text/markdown')
    storage.save_report(folder+'/'+data_snapshot_filename_for_report(filename),json.dumps(snapshot).encode(),content_type='application/json')
    monkeypatch.setattr(report_history_storage,'storage_for_existing_output_dir',lambda *a:storage)
    def query(**kwargs):
        assert kwargs['sync_metadata'] is False and kwargs['q']==filename
        return [projected],1
    monkeypatch.setattr(report_index,'query_report_metadata',query)
    monkeypatch.setattr(status,'source_readiness',lambda *a:GOOD)
    result=status.read_status('unused',now=NOW+timedelta(hours=9))
    assert result['ready'] and result['delivery_date']=='2026-10-31'
    projected['evidence_exit_gate']={'verdict':'rejected'}
    assert not status.read_status('unused',now=NOW+timedelta(hours=9))['ready']
