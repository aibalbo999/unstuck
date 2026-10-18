"""Only a provably unentered callback is a local provider admission block."""
import asyncio
from copy import deepcopy
from datetime import datetime
import json

import pytest

import provider_resilience as resilience
from provider_acquisition import observation_kind,project_acquisition_events
from source_audit import audited_fetch,audited_fetch_async


@pytest.fixture(autouse=True)
def isolation(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setenv('PROVIDER_RETRY_ATTEMPTS','1')
    monkeypatch.setattr(resilience,'_check_provider_state',lambda *a:None)
    monkeypatch.setattr(resilience,'enforce_provider_throttle',lambda *a:None)
    async def no_throttle(*a):return None
    monkeypatch.setattr(resilience,'enforce_provider_throttle_async',no_throttle)
    monkeypatch.setattr(resilience,'_record_provider_success',lambda *a:None)
    monkeypatch.setattr(resilience,'_record_provider_failure',lambda *a:None)
    monkeypatch.setattr(resilience,'mark_rate_limit_cooldown',lambda *a:None)
    yield
    cache_store.reset_cache_store_for_tests()


def row(a):
    return {**a,'created_at':datetime.fromisoformat(a['fetched_at']).timestamp(),'details':a,'details_json':json.dumps(a)}


@pytest.mark.parametrize('async_mode',[False,True])
@pytest.mark.parametrize('gate',['circuit','throttle'])
def test_unentered_guard_is_local_block_without_success_or_fetch_attempt(monkeypatch,async_mode,gate):
    calls=[]
    error=resilience.ProviderCircuitOpenError if gate=='circuit'else resilience.ProviderRateLimitOpenError
    def blocked(*a):raise error('provider admission unavailable')
    async def async_blocked(*a):raise error('provider admission unavailable')
    if gate=='circuit':monkeypatch.setattr(resilience,'_check_provider_state',blocked)
    else:
        monkeypatch.setattr(resilience,'enforce_provider_throttle',blocked)
        monkeypatch.setattr(resilience,'enforce_provider_throttle_async',async_blocked)
    def callback():calls.append(1);return ['never delivered']
    async def async_callback():calls.append(1);return ['never delivered']
    result=asyncio.run(audited_fetch_async('monthly_revenue','isolated admission',async_callback,default=[]))if async_mode else audited_fetch('monthly_revenue','isolated admission',callback,default=[])
    a=result['audit'];assert calls==[] and result['value']==[] and a['status']=='unavailable'
    assert a['provider_attempts']==[]
    assert a['event_kind']=='local_block' and a['http_request_sent']is False and a['http_request_count']==0
    assert a['provider_admission_blocked']is True and a['error_kind']==error.__name__
    counts=project_acquisition_events([row(a)],window='last_24h',now=row(a)['created_at'])['sources'][0]
    assert counts['local_block_count']==1 and counts['fetch_attempts']==counts['fetched_count']==counts['http_attempt_count']==0


@pytest.mark.parametrize('async_mode',[False,True])
@pytest.mark.parametrize('error',[resilience.ProviderCircuitOpenError,resilience.ProviderRateLimitOpenError])
def test_same_error_raised_inside_callback_is_not_proof_of_no_request(async_mode,error):
    calls=[]
    def callback():calls.append(1);raise error('inner SDK admission unknown')
    async def async_callback():calls.append(1);raise error('inner SDK admission unknown')
    result=asyncio.run(audited_fetch_async('monthly_revenue','isolated admission',async_callback,default=[]))if async_mode else audited_fetch('monthly_revenue','isolated admission',callback,default=[])
    a=result['audit'];assert calls==[1] and len(a['provider_attempts'])==1
    assert observation_kind(row(a))=='failed_count' and a.get('provider_admission_blocked')is not True
    assert 'http_request_sent'not in a and a['status']=='unavailable'


def test_new_blocks_do_not_reclassify_or_modify_saved_failure_rows(monkeypatch):
    old={'source':'monthly_revenue','provider':'isolated admission','status':'unavailable','record_count':0,
         'message':'historical circuit','event_kind':'aggregate','provider_attempts':[],'provider_attempt_count':0,
         'error_kind':'ProviderCircuitOpenError','created_at':1.,'details_json':'{}'}
    held=deepcopy(old)
    def blocked(*a):raise resilience.ProviderCircuitOpenError('new blocked operation')
    monkeypatch.setattr(resilience,'_check_provider_state',blocked)
    a=audited_fetch('monthly_revenue','isolated admission',lambda:pytest.fail('blocked callback'),default=[])['audit']
    assert observation_kind({**old,'details':{}})=='failed_count' and old==held
    assert observation_kind(row(a))=='local_block_count'


def test_monthly_reuses_current_core_local_block_and_recovers_official_data(monkeypatch):
    from test_official_monthly_revenue import native_csv
    from data_fetch.types import FetchRequest
    from provider_correlation import correlation_scope
    import data_fetch.taiwan_providers as providers
    calls=native_csv(monkeypatch)
    def blocked(*a):raise resilience.ProviderCircuitOpenError('same fetch current circuit')
    monkeypatch.setattr(resilience,'_check_provider_state',blocked)
    with correlation_scope(replace=True,fetch_id='current-real-fetch',ticker='2330.TW'):
        original=audited_fetch('monthly_revenue',providers.MonthlyRevenueProvider.name,lambda:pytest.fail('primary callback blocked'),default=[])
        data={'ticker':'2330.TW','source_audit':[original['audit']]};held=deepcopy(data)
        monkeypatch.setattr(providers,'audited_fetch',lambda *a,**k:pytest.fail('same core admission must not be repeated'))
        result=providers.MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'),{'data':data})
    assert len(calls)==1 and result.status=='success'and result.value==['2026年8月: NT$5148.05億','2026年9月: NT$5118.57億']
    assert result.audit['related_entries']==[] and result.audit['primary_failure_operation_id']==original['audit']['operation_id']
    assert data==held and original['audit']['provider_admission_blocked']is True


@pytest.mark.parametrize('field,value',[('cache_hit',True),('stale',True),('ticker','3023.TW'),
                                      ('provider_admission_blocked',False),('provider_attempt_count',False),
                                      ('http_request_count',False),('provider_attempts',[{'status':'error'}])])
def test_monthly_does_not_reuse_inconsistent_or_old_local_block(monkeypatch,field,value):
    from test_official_monthly_revenue import native_csv
    from data_fetch.types import FetchRequest
    from provider_correlation import correlation_scope
    import data_fetch.taiwan_providers as providers
    native_csv(monkeypatch);calls=[]
    class Loader:
        def taiwan_stock_month_revenue(self,**kwargs):
            import pandas as pd
            calls.append(kwargs);return pd.DataFrame()
    monkeypatch.setattr('data_fetch.market_sources.taiwan.DataLoader',Loader)
    prior={'source':'monthly_revenue','provider':providers.MonthlyRevenueProvider.name,'status':'unavailable',
           'record_count':0,'operation_id':'old','fetch_id':'same-current','ticker':'2330.TW','cache_hit':False,'stale':False,
           'event_kind':'local_block','provider_admission_blocked':True,'http_request_sent':False,'http_request_count':0,
           'provider_attempt_count':0,'provider_attempts':[]}
    prior[field]=value
    with correlation_scope(replace=True,fetch_id='same-current',ticker='2330.TW'):
        result=providers.MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'),{'data':{'ticker':'2330.TW','source_audit':[prior]}})
    assert len(calls)==1 and result.audit.get('primary_failure_operation_id')is None


def test_persisted_block_keeps_unavailability_and_zero_usage_without_changing_old_row(monkeypatch,tmp_path):
    import sqlite3
    import provider_sla
    path=tmp_path/'source-admission.sqlite3';monkeypatch.setattr(provider_sla,'TASK_DB_PATH',str(path))
    old={'source':'monthly_revenue','provider':'isolated admission','status':'unavailable','record_count':0,
         'message':'original failed operation','error_kind':'ProviderCircuitOpenError','event_kind':'aggregate',
         'provider_attempts':[]}
    provider_sla.record_source_audit_entries([old])
    with sqlite3.connect(path)as db:
        held=db.execute('select *from provider_sla_events order by id').fetchall()
    def blocked(*a):raise resilience.ProviderCircuitOpenError('new actual admission block')
    monkeypatch.setattr(resilience,'_check_provider_state',blocked)
    a=audited_fetch('monthly_revenue','isolated admission',lambda:pytest.fail('no callback'),default=[])['audit']
    provider_sla.record_source_audit_entries([a])
    with sqlite3.connect(path)as db:
        db.row_factory=sqlite3.Row
        current=[dict(r)for r in db.execute('select *from provider_sla_events order by id')]
        assert [tuple(r.values())for r in current[:1]]==held
        usage=[dict(r)for r in db.execute('select units,metadata_json from api_usage_events order by id')]
    assert current[1]['status']=='unavailable'and current[1]['record_count']==0
    current[1]['details']=json.loads(current[1]['details_json'])
    assert observation_kind(current[1])=='local_block_count'and current[1]['details']['provider_attempt_count']==0
    assert usage[0]['units']==1 and usage[1]['units']==0
    details=json.loads(usage[1]['metadata_json']);assert details['http_request_sent']is False and details['event_kind']=='local_block'


def test_prebuilt_task_transport_state_cannot_be_inferred_from_empty_wrapper_trace(monkeypatch):
    calls=[]
    def blocked(*a):raise resilience.ProviderCircuitOpenError('blocked after eager task creation')
    monkeypatch.setattr(resilience,'_check_provider_state',blocked)
    async def run():
        async def already_started():calls.append(1);return ['existing operation']
        task=asyncio.create_task(already_started());await task
        result=await audited_fetch_async('monthly_revenue','isolated admission',task,default=[])
        assert task.result()==['existing operation']
        return result
    a=asyncio.run(run())['audit'];assert calls==[1] and a['provider_attempts']==[]
    assert a['status']=='unavailable'and 'http_request_sent'not in a and a.get('provider_admission_blocked')is not True
