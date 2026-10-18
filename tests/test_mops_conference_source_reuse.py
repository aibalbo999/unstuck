"""Repeated normal metadata requests preserve source age without repeated HTTP."""
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest
import cache_store
from cache_backends import InMemoryCache
from data_fetch.enrichment_providers import EarningsCallProvider
from data_fetch.types import FetchRequest
import official_financials_mops_conference as mops
from provider_correlation import correlation_scope


@pytest.fixture
def upstream(monkeypatch):
    import shared_provider_cache
    import search_provider_runtime
    import official_financials_webpro_conference
    class Today(date):
        @classmethod
        def today(cls):return cls(2026,10,10)
    import data_fetch.earnings_call_fetcher as flow
    monkeypatch.setattr(flow,'date',Today)
    monkeypatch.setattr(mops,'date',Today)
    now=[1791631000.0];calls=[];observations=[];description=['原始營運說明']
    monkeypatch.setattr(shared_provider_cache.time,'time',lambda:now[0])
    monkeypatch.setattr(search_provider_runtime,'record_source_audit_entries',lambda rows:observations.extend(deepcopy(rows)))
    monkeypatch.setattr(official_financials_webpro_conference,'fetch_webpro_conference_context',lambda *a,**k:{})
    cache_store.set_cache_backend(InMemoryCache())
    def post(url,**kwargs):
        calls.append(deepcopy(kwargs['data']))
        text=('<html><body>查無資料</body></html>' if kwargs['data']['year']=='115' else
          '<table><tr><th>公司代號</th><th>公司名稱</th><th>召開法人說明會日期</th><th>相關資訊</th></tr>'
          '<tr><td>1325</td><td>恒大</td><td>2025/12/19</td><td>'+description[0]+'</td></tr></table>')
        return SimpleNamespace(text=text,content=text.encode(),encoding='utf-8',status_code=200)
    monkeypatch.setattr(mops,'_http_post',post)
    yield now,calls,observations,description
    cache_store.reset_cache_store_for_tests()


def get_context(fetch_id,*,force=False):
    with correlation_scope(replace=True,fetch_id=fetch_id):
        return EarningsCallProvider().fetch(FetchRequest.from_ticker('1325.TW',force_refresh=force))


def test_normal_earnings_context_reuses_both_years_without_new_http_or_new_source_age(upstream):
    now,calls,observations,_=upstream
    first=get_context('first-normal');assert first.value['date']=='2025-12-19'
    assert [r['year'] for r in calls]==['115','114']
    stamp=first.audit.get('fetched_at_epoch')
    now[0]+=120;second=get_context('second-normal')
    assert len(calls)==2
    assert second.value==first.value and second.value['transcript_available'] is False
    assert stamp==1791631000.0 and second.audit['fetched_at_epoch']==stamp
    assert second.audit['cache_hit'] is True and second.audit['http_request_count']==0
    assert second.audit['http_request_sent'] is False
    native=[r for r in observations if r.get('http_request_sent') is True]
    assert len(native)==2 and [r['record_count'] for r in native]==[0,1]
    warm=[r for r in observations if r.get('event_kind')=='cache_hit']
    assert len(warm)==2 and all(r['fetch_id']=='second-normal' for r in warm)
    assert all(r['cache_hit'] is True and r['http_request_sent'] is False for r in warm)


def test_cached_query_diagnostics_expose_the_actual_result_status(upstream):
    now, calls, observations, _ = upstream
    native = {}
    assert mops.fetch_mops_investor_conference_events(
        '1325.TW', year=2025, use_cache=True, diagnostics=native)
    assert native['status'] == 'success' and native['record_count'] == 1
    assert native['outcome'] == 'results' and native['http_request_count'] == 1
    now[0] += 1
    warm = {}
    assert mops.fetch_mops_investor_conference_events(
        '1325.TW', year=2025, use_cache=True, diagnostics=warm)
    assert warm['status'] == 'skipped_fresh_cache' and warm['record_count'] == 1
    assert warm['http_request_count'] == 0
    assert warm['fetched_at_epoch'] == native['fetched_at_epoch']
    empty = {}
    assert not mops.fetch_mops_investor_conference_events(
        '1325.TW', year=2026, use_cache=True, diagnostics=empty)
    assert empty['status'] == 'degraded_enrichment' and empty['record_count'] == 0
    assert empty['outcome'] == 'valid_empty'
    assert len(calls) == 2


def test_monthly_mops_index_is_cached_by_exact_month(upstream,monkeypatch):
    from types import SimpleNamespace
    now,calls,_,_=upstream
    def post(url,**kwargs):
        data=deepcopy(kwargs['data']);calls.append(data)
        month=int(data['month'])
        html=(
            '<table><tr><th>公司代號</th><th>公司名稱</th><th>召開法人說明會日期</th>'
            '<th>召開法人說明會時間</th><th>召開法人說明會地點</th><th>相關資訊</th>'
            '<th>簡報檔案</th><th>影音連結</th></tr>'
            f'<tr><td>1325</td><td>恒大</td><td>2025/{month:02d}/23</td>'
            '<td>14:00</td><td>線上</td><td>季營運說明</td><td></td><td></td></tr></table>'
        )
        return SimpleNamespace(text=html,content=html.encode(),encoding='utf-8',status_code=200)
    monkeypatch.setattr(mops,'_http_post',post)
    results=[]
    for month in (9,10,9):
        diagnostics={}
        rows=mops.fetch_mops_investor_conference_events(
            '1325.TW',year=2025,month=month,use_cache=True,diagnostics=diagnostics,
        )
        results.append((rows[0]['date'],diagnostics.get('cache_hit')))
    assert results==[('2025-09-23',False),('2025-10-23',False),('2025-09-23',True)]
    assert [row['month'] for row in calls]==['09','10']


def test_manual_force_replaces_saved_context_for_the_next_normal_request(upstream):
    now,calls,_,description=upstream
    first=get_context('first-normal');description[0]='新的營運說明';now[0]+=120
    forced=get_context('forced',force=True)
    assert len(calls)==4 and forced.value['summary']=='新的營運說明'
    assert forced.audit.get('cache_hit') is False
    now[0]+=120;normal=get_context('next-normal')
    assert len(calls)==4 and normal.value==forced.value
    assert normal.audit['fetched_at_epoch']==forced.audit['fetched_at_epoch']==1791631120.0


def test_empty_current_year_expires_earlier_than_successful_previous_year(upstream):
    now,calls,_,_=upstream
    first=get_context('first-normal');now[0]+=601
    later=get_context('after-empty-ttl')
    assert [r['year'] for r in calls]==['115','114','115']
    assert later.value==first.value and later.audit['fetched_at_epoch']==first.audit['fetched_at_epoch']
    assert later.audit['cache_hit'] is False and later.audit['http_request_count']==1


def test_force_failure_and_cooldown_never_publish_the_old_source_as_fresh(upstream,monkeypatch):
    from search_provider_runtime import SourceResponseError
    now,calls,observations,_=upstream
    first=get_context('first-normal');original=mops._http_post;now[0]+=120
    def fail_previous(url,**kwargs):
        if kwargs['data']['year']=='114':
            calls.append(deepcopy(kwargs['data']))
            raise SourceResponseError('server_error',status_code=503)
        return original(url,**kwargs)
    monkeypatch.setattr(mops,'_http_post',fail_previous)
    forced=get_context('failed-force',force=True)
    assert not forced.value and forced.status!='success' and len(calls)==4
    assert forced.audit['component_statuses']['MOPS']['error_kind']=='server_error'
    now[0]+=1;normal=get_context('after-force-failure')
    assert not normal.value and normal.status!='success' and len(calls)==4
    assert normal.audit['component_statuses']['MOPS']['error_kind']=='server_error'
    assert any(o.get('event_kind')=='local_block' for o in observations)
    assert first.value['summary']=='原始營運說明'


@pytest.mark.parametrize('field',['source_url','timestamp','missing_archive','bad_native_bytes','huge_timestamp'])
def test_corrupt_warm_original_is_rejected_without_another_mops_request(upstream,field):
    import hashlib
    from pathlib import Path
    now,calls,_,_=upstream
    first=get_context('first-normal')
    key='shared_provider:v1:'+hashlib.sha256(b'mops-conference-original:v1:mops-conference-v3:1325:sii:2025').hexdigest()
    cached=cache_store.get_cache_json(key);payload=cached['value'];receipt=payload['receipt']
    if field=='source_url':receipt['source_url']='https://evil.example/fake'
    elif field=='timestamp':payload['fetched_at_epoch']=True
    elif field=='huge_timestamp':payload['fetched_at_epoch']=10**400
    elif field=='missing_archive':Path(receipt['raw_response_path']).unlink()
    else:receipt['raw_response_bytes']+=1
    cache_store.set_cache_json(key,cached,86400)
    now[0]+=120;normal=get_context('bad-cache')
    assert not normal.value and normal.status!='success' and len(calls)==2
    assert normal.audit['component_statuses']['MOPS']['error_kind']=='original_unverified'
    assert first.value['date']=='2025-12-19'


def test_archive_failure_keeps_native_result_and_its_actual_requests(upstream,monkeypatch):
    import mops_conference_cache
    now,calls,_,_=upstream
    monkeypatch.setattr(mops_conference_cache,'archive_response',lambda *a,**k:{'status':'unavailable'})
    first=get_context('unarchivable-native');assert first.value['date']=='2025-12-19'
    now[0]+=.2;second=get_context('unarchivable-next')
    assert second.value==first.value and len(calls)==4
    assert second.audit['cache_hit'] is False and second.audit['http_request_count']==2


def acquisition(rows,now):
    import json
    from provider_acquisition import project_acquisition_events
    from provider_observation_details import observation_details
    events=[{**r,'created_at':now,'details_json':json.dumps(observation_details(r))} for r in rows]
    return project_acquisition_events(events,window='last_24h',now=now)['sources'][0]


@pytest.mark.parametrize('boundary',['archive_raises','cold_readback_io'])
def test_native_metadata_survives_local_original_storage_io_without_phantom_http(upstream,monkeypatch,boundary):
    import mops_conference_cache
    now,calls,observations,_=upstream
    def fail(*a,**k):raise OSError('isolated source archive unavailable')
    monkeypatch.setattr(mops_conference_cache,'archive_response' if boundary=='archive_raises' else 'read_response',fail)
    result=get_context('native-io')
    assert result.value['date']=='2025-12-19' and len(calls)==2
    assert result.audit['fetched_at_epoch']==now[0] and result.audit['http_request_count']==2
    assert result.audit['source_http_request_sent'] is True and result.audit['cache_hit'] is False
    assert all(r['http_request_sent'] is True for r in result.audit['mops_year_observations'])
    projected=acquisition([*observations,result.audit],now[0])
    assert projected['http_attempt_count']==2 and projected['fetched_count']==1
    assert projected['empty_count']==1 and projected['aggregate_count']==1


def test_stale_shared_observation_without_error_text_never_becomes_fresh(upstream):
    from hashlib import sha256
    now,calls,_,_=upstream
    get_context('first-normal')
    key='shared_provider:v1:'+sha256(b'mops-conference-original:v1:mops-conference-v3:1325:sii:2025').hexdigest()
    row=cache_store.get_cache_json(key)
    row.update(fresh_until_epoch=now[0]-1,retry_after_epoch=now[0]+60,error_kind=None)
    cache_store.set_cache_json(key,row,86400)
    result=get_context('retained-stale')
    assert not result.value and result.status!='success' and len(calls)==2
    assert result.audit['component_statuses']['MOPS']['error_kind']=='stale_source'


def test_empty_new_http_and_cached_past_event_are_not_a_new_success(upstream):
    now,calls,observations,_=upstream
    original=get_context('first-normal');observations.clear();now[0]+=601
    result=get_context('mixed')
    assert result.value==original.value and len(calls)==3
    assert result.status=='degraded_enrichment'
    assert result.audit['acquisition_status']=='partial_acquisition_with_cached_records'
    projected=acquisition([*observations,result.audit],now[0])
    assert projected['fetched_count']==0 and projected['fetch_attempts']==1
    assert projected['http_attempt_count']==1 and projected['empty_count']==1
    assert projected['fresh_cache_count']==1 and projected['aggregate_count']==1


def test_partial_http_200_timeout_cools_only_the_same_mops_issuer(upstream,monkeypatch):
    import search_provider_runtime as runtime
    from search_provider_runtime import SourceResponseError

    _now,_calls,_observations,_description=upstream
    original=mops._http_post
    attempted=[]
    def post(url,**kwargs):
        code=kwargs['data']['co_id']
        attempted.append(code)
        if code=='2330':
            error=SourceResponseError('timeout',status_code=200)
            error.diagnostic.update(response_bytes=393216,response_sha256='partial-body')
            raise error
        return original(url,**kwargs)
    monkeypatch.setattr(mops,'_http_post',post)

    with pytest.raises(SourceResponseError) as failed:
        mops.fetch_mops_investor_conference_events('2330.TW',year=2026)
    assert failed.value.error_kind=='timeout'
    global_key=runtime.scope_key('MOPS',endpoint='mopsov_investor_conference')
    issuer_key=runtime.scope_key('MOPS',endpoint='mopsov_investor_conference:2330')
    assert runtime.cooldown_state(global_key)=={}
    assert runtime.cooldown_state(issuer_key)['error_kind']=='timeout'

    # An HTTP 200 partial-body timeout for one issuer must not suppress a
    # different issuer's MOPS query, while the timed-out issuer stays guarded.
    other=mops.fetch_mops_investor_conference_events('2324.TW',year=2026)
    assert other==[]
    diagnostics={}
    with pytest.raises(SourceResponseError) as blocked:
        mops.fetch_mops_investor_conference_events('2330.TW',year=2026,diagnostics=diagnostics)
    assert blocked.value.error_kind=='timeout'
    assert diagnostics['http_request_sent'] is False
    assert attempted==['2330','2324']


def test_legacy_shared_http_200_timeout_does_not_block_other_mops_issuers(upstream):
    import time
    import search_provider_runtime as runtime

    _now,calls,_observations,_description=upstream
    global_key=runtime.scope_key('MOPS',endpoint='mopsov_investor_conference')
    cache_store.set_cache_json(global_key,{
        'error_kind':'timeout','http_status':200,'retry_at':time.time()+300,
        'response_bytes':393216,
    },86400)
    diagnostics={}

    assert mops.fetch_mops_investor_conference_events(
        '2324.TW',year=2026,diagnostics=diagnostics,
    )==[]
    assert len(calls)==1
    assert diagnostics['legacy_shared_http_200_timeout_ignored'] is True
    assert runtime.cooldown_state(global_key)['error_kind']=='timeout'
