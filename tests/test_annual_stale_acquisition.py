"""Retained data is distinct from a current failed source attempt."""
import asyncio,copy,json
from contextlib import contextmanager
from datetime import date,datetime
from zoneinfo import ZoneInfo
import httpx
import pytest
from data_fetch import annual_workforce_provider as workforce
from data_fetch import annual_occupational_safety as safety
from data_fetch.types import FetchRequest
from data_fetch.provider_execution import fetch_correlated_provider
from provider_correlation import correlation_scope
from provider_observation_details import observation_details
from provider_acquisition import project_acquisition_events
import provider_sla,shared_provider_cache,cache_store


@pytest.fixture
def annual(monkeypatch):
    now=[datetime(2026,10,17,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()]
    store={};calls=[];transport=[];fail=[False]
    monkeypatch.setattr(shared_provider_cache.time,'time',lambda:now[0])
    monkeypatch.setattr(cache_store,'get_cache_json',lambda key:copy.deepcopy(store.get(key)))
    monkeypatch.setattr(cache_store,'set_cache_json',lambda key,value,**kw:store.__setitem__(key,copy.deepcopy(value)))
    @contextmanager
    def owned(*a,**kw):yield True
    monkeypatch.setattr(shared_provider_cache,'_process_lock',owned)
    monkeypatch.setattr(workforce,'_today',lambda:date(2026,10,17))
    monkeypatch.setattr(safety,'_today',lambda:date(2026,10,17))
    common={'出表日期':'1151016','報告年度':'114','公司代號':'2330','公司名稱':'台積電'}
    w={**common,'員工薪資平均數(仟元/人)':'4093','非擔任主管之全時員工薪資中位數(仟元/人)':'3162','管理職女性主管佔比':'15%'}
    s={**common,'職業災害人數及比率-人數':'0','職業災害人數及比率-比率':'0.00%',
        '火災件數(件)':'2','火災死傷人數(人)':'1','火災死傷人數占員工總人數比率':'0.01%'}
    def get(url,**kw):
        calls.append(url)
        if fail[0]=='timeout':raise httpx.ReadTimeout('no observed response',request=httpx.Request('GET',url))
        failed=fail[0] is True or isinstance(fail[0],set)and url in fail[0]
        response=httpx.Response(503 if failed else 200,content=b'unavailable'if failed else json.dumps([w if url==workforce.URLS['.TW']else s]).encode(),request=httpx.Request('GET',url))
        response.raise_for_status();return response
    monkeypatch.setattr(workforce,'sync_get',get)
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:transport.extend(rows))
    async def fetch():
        return await fetch_correlated_provider(workforce.AnnualWorkforceProvider(),FetchRequest.from_ticker('2330.TW'),{})
    def run(fetch_id):
        with correlation_scope(replace=True,ticker='2330.TW',fetch_id=fetch_id):return asyncio.run(fetch())
    initial=run('seed');assert initial.audit['status']=='success'
    retained=copy.deepcopy(store);calls.clear();transport.clear()
    return now,store,calls,fail,run,retained


def projected(result,now,fetch_id):
    entries=[result.audit,*result.audit['related_entries']]
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id=fetch_id):
        rows=[{'source':e['source'],'provider':e['provider'],'status':e['status'],'record_count':e['record_count'],
               'message':e.get('message',''),'created_at':now,'details_json':json.dumps(observation_details(e))}for e in entries]
    return {g['source']:g for g in project_acquisition_events(rows,window='last_1h',now=now)['sources']},rows


def test_actual_failed_refresh_with_stale_fallback_stays_in_attempt_denominator(annual):
    now,store,calls,fail,run,before=annual
    now[0]+=86401;fail[0]=True;result=run('fresh-failed')
    assert len(calls)==2
    assert result.audit['cache_hit'] is True and result.audit['stale'] is True
    assert result.audit['http_request_sent'] is True
    assert result.audit['fetched_at_epoch']==next(iter(before.values()))['fetched_at_epoch']
    groups,_=projected(result,now[0],'fresh-failed')
    for source in ('annual_workforce','esg_occupational_safety'):
        assert groups[source]['fetch_attempts']==1
        assert groups[source]['fetched_count']==0 and groups[source]['failed_count']==1
    for key,old in before.items():
        assert store[key]['value']==old['value']
        assert store[key]['fetched_at_epoch']==old['fetched_at_epoch']
        assert store[key]['retained_until_epoch']==old['retained_until_epoch']


def test_warm_cache_and_failure_cooldown_remain_nonfetch_observations(annual):
    now,store,calls,fail,run,before=annual
    warm=run('warm');groups,_=projected(warm,now[0],'warm')
    assert calls==[] and all(g['fetch_attempts']==0 for g in groups.values())
    now[0]+=86401;fail[0]=True;run('actual-failed');calls.clear()
    cooldown=run('cooldown');groups,_=projected(cooldown,now[0],'cooldown')
    assert calls==[] and all(g['fetch_attempts']==0 for g in groups.values())


def test_retained_failed_audit_cannot_be_rebound_as_new_attempt(annual):
    now,store,calls,fail,run,before=annual
    now[0]+=86401;fail[0]=True;result=run('original-failed')
    original=copy.deepcopy(result.audit)
    groups,_=projected(result,now[0],'new-cache-delivery')
    assert all(g['fetch_attempts']==0 for g in groups.values())
    assert result.audit==original


def test_failed_callback_without_response_keeps_unknown_http_but_counts_call(annual):
    now,store,calls,fail,run,before=annual
    now[0]+=86401;fail[0]='timeout';result=run('unknown-transport')
    groups,_=projected(result,now[0],'unknown-transport')
    assert len(calls)==2 and result.audit['http_request_sent']is None
    assert result.audit['http_request_count']==0 and result.audit['http_status']is None
    assert all(g['failed_count']==g['fetch_attempts']==1 for g in groups.values())


def test_duplicate_projection_does_not_create_another_source_attempt(annual):
    now,store,calls,fail,run,before=annual
    now[0]+=86401;fail[0]=True;result=run('one-failure')
    _,rows=projected(result,now[0],'one-failure')
    groups={g['source']:g for g in project_acquisition_events([*rows,*copy.deepcopy(rows)],window='last_1h',now=now[0])['sources']}
    assert all(g['failed_count']==g['fetch_attempts']==1 for g in groups.values())
    assert all(g['aggregate_count']==1 for g in groups.values())


def test_copied_current_flag_cannot_override_new_delivery_context(annual):
    now,store,calls,fail,run,before=annual
    now[0]+=86401;fail[0]=True;result=run('real-failure')
    result.audit['acquisition_context_current']=True
    for entry in result.audit['related_entries']:entry['acquisition_context_current']=True
    groups,rows=projected(result,now[0],'different-fetch')
    assert all(g['fetch_attempts']==0 for g in groups.values())
    assert all(json.loads(row['details_json'])['acquisition_context_current']is False for row in rows)


def test_legacy_stale_http_booleans_are_not_reinterpreted():
    from provider_acquisition import observation_kind
    old={'source':'annual_workforce','provider':workforce.PROVIDER,'status':'degraded_enrichment','record_count':1,'message':'original',
        'details':{'cache_hit':True,'stale':True,'http_request_sent':True,'http_request_count':1}}
    assert observation_kind(old)=='stale_cache_count'


def test_service_serializes_current_context_without_mutating_frozen_audit(annual):
    import data_fetch.service as service
    from provider_acquisition import get_provider_acquisition_summary
    now,store,calls,fail,run,before=annual
    now[0]+=86401;fail[0]=True
    result=asyncio.run(service.StockDataService().fetch_source_async(FetchRequest.from_ticker('2330.TW'),'annual_workforce'))
    assert len(calls)==2
    assert all('acquisition_context_current'not in entry for entry in result.source_audit)
    groups={g['source']:g for g in get_provider_acquisition_summary('last_1h')['sources']}
    assert all(groups[s]['failed_count']==groups[s]['fetch_attempts']==1 for s in('annual_workforce','esg_occupational_safety'))


def test_distinct_actual_failures_in_same_fetch_are_not_deduplicated(annual):
    now,store,calls,fail,run,before=annual
    now[0]+=86401;fail[0]=True;first=run('same-fetch')
    _,rows1=projected(first,now[0],'same-fetch')
    now[0]+=61;second=run('same-fetch')
    _,rows2=projected(second,now[0],'same-fetch')
    assert len(calls)==4 and first.audit['operation_id']!=second.audit['operation_id']
    groups=project_acquisition_events([*rows1,*rows2],window='last_1h',now=now[0])['sources']
    assert all(g['fetch_attempts']==g['failed_count']==2 for g in groups)


def test_one_failed_component_does_not_reclassify_other_fresh_success(annual):
    now,store,calls,fail,run,before=annual
    now[0]+=86401;fail[0]={workforce.URLS['.TW']};result=run('mixed')
    groups,_=projected(result,now[0],'mixed')
    assert groups['annual_workforce']['failed_count']==1
    assert groups['annual_workforce']['fetched_count']==0
    assert groups['esg_occupational_safety']['fetched_count']==1
    assert groups['esg_occupational_safety']['failed_count']==0


@pytest.mark.parametrize('signal',[False,0,1,'false'])
def test_no_send_or_invalid_flag_cannot_become_an_attempt_via_copied_policy(annual,signal):
    now,store,calls,fail,run,before=annual
    now[0]+=86401;fail[0]=True;result=run('actual-origin')
    result.audit['http_request_sent']=signal
    for entry in result.audit['related_entries']:entry['http_request_sent']=signal
    groups,_=projected(result,now[0],'actual-origin')
    assert all(g['fetch_attempts']==0 for g in groups.values())


def test_policy_cannot_reclassify_an_unrelated_cached_provider():
    from annual_disclosure_acquisition import POLICY,ATTEMPT_KIND
    from provider_acquisition import observation_kind
    row={'source':'market_data','provider':'unrelated','status':'degraded_enrichment','record_count':1,'message':'cached',
         'details':{'acquisition_count_policy':POLICY,'acquisition_attempt_kind':ATTEMPT_KIND,'acquisition_record_count':0,
             'acquisition_context_current':True,'ticker':'2330.TW','fetch_id':'x','operation_id':'y','event_kind':'fetch',
             'error_kind':'ReadError','cache_hit':True,'stale':True,'http_request_sent':True}}
    assert observation_kind(row)=='stale_cache_count'
