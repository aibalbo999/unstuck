"""Offline public MOPS acquisition with the complete shared identity fallback."""
from copy import deepcopy
from hashlib import sha256
import time
import pytest
from search_provider_runtime import SourceResponseError
from test_mops_presentation import harness, NOW, valid_data
from test_official_issuer_master_json import json_value, RAW, JSON_URL


@pytest.fixture
def fallback(harness, monkeypatch):
    from data_fetch.market_sources import mops_presentation as source
    calls=[]; control={'failure':'timeout','value':json_value()}
    def download(self,url,diagnostic):
        calls.append(url);self.http_request_count+=1
        diagnostic.update(http_request_sent=True,http_status=200)
        if url==source.MASTER_URL:
            raise SourceResponseError(control['failure'],status_code=200)
        assert url==JSON_URL
        return deepcopy(control['value'])
    monkeypatch.setattr(source.MasterHttp,'download_original',download)
    return source,calls,control,harness


@pytest.mark.parametrize('ticker',['1229.TW','2330.TW'])
def test_public_csv_timeout_recovers_complete_json_without_losing_first_attempt(fallback,ticker):
    source,calls,control,base=fallback;diagnostic={}
    value=source.fetch_presentation_context(ticker,diagnostics=diagnostic)
    assert len(value['documents'][0]['pages'])==(30 if ticker=='1229.TW' else 12)
    assert calls==[source.MASTER_URL,JSON_URL]
    assert base[1]==[ticker+':index',ticker+':material']
    receipt=value['mops_material_receipt']['master']
    assert receipt['source_url']==JSON_URL and receipt['raw_response_sha256']==sha256(RAW).hexdigest()
    assert diagnostic['http_request_count']==4 and diagnostic['mops_material_originals_verified']
    assert diagnostic['component_statuses'][0]['error_kind']=='timeout'
    assert diagnostic['component_statuses'][0]['http_request_sent'] is True
    assert source.verify_context(value,ticker)


def test_legacy_denial_still_blocks_json_when_shared_csv_already_cooling(fallback):
    from cache_store import set_cache_json
    from data_fetch.market_sources import official_issuer_master as shared
    from data_fetch.market_sources import official_issuer_master_transport as transport
    source,calls,control,base=fallback
    set_cache_json(shared.ADMISSION_KEY,{'retry_at':NOW+60,'error_kind':'timeout','fallback_eligible':True},ttl_seconds=60)
    set_cache_json(transport.LEGACY_RAW_KEY,{'retry_after_epoch':NOW+60,'error_kind':'access_denied','http_status':403},ttl_seconds=60)
    with pytest.raises(SourceResponseError) as exc:source.fetch_presentation_context('1229.TW')
    assert exc.value.error_kind=='access_denied'
    assert calls==[] and base[1]==[]


@pytest.mark.parametrize('failure',['authentication','access_denied','rate_limited','guard_storage_unavailable',
    'lease_lost','single_flight_busy','request_pacing','original_unverified','cache_receipt_invalid','parse_error'])
def test_terminal_csv_failure_never_falls_back_or_reaches_mops(fallback,failure):
    source,calls,control,base=fallback;control['failure']=failure;d={}
    with pytest.raises(SourceResponseError) as exc:source.fetch_presentation_context('1229.TW',diagnostics=d)
    assert exc.value.error_kind==failure
    assert calls==[source.MASTER_URL] and not base[1] and d['http_request_count']==1


@pytest.mark.parametrize('key,fields,expected',[
    ('raw',{'retry_after_epoch':NOW+60,'error_kind':'SourceResponseError'},'guard_storage_unavailable'),
    ('raw',{'retry_after_epoch':True,'error_kind':'timeout'},'guard_storage_unavailable'),
    ('raw',{'retry_after_epoch':NOW+60,'error_kind':'timeout','fallback_eligible':False},'guard_storage_unavailable'),
    ('raw',{'retry_after_epoch':NOW+60,'error_kind':'timeout','http_status':'403'},'guard_storage_unavailable'),
    ('raw',{'retry_after_epoch':NOW+60,'error_kind':'rate_limited','http_status':429},'rate_limited'),
    ('raw',{'retry_after_epoch':NOW+60,'error_kind':'authentication','http_status':401},'authentication'),
    ('raw',{'retry_after_epoch':NOW+60,'error_kind':'cache_receipt_invalid'},'cache_receipt_invalid'),
    ('admission',{'retry_at':NOW+60,'token':'unfinished-native'},'guard_storage_unavailable'),
    ('admission',{'retry_at':0,'next_request_at':NOW+60,'error_kind':'cooldown'},'request_pacing'),
    ('admission',[], 'guard_storage_unavailable'),
    ('admission',{}, 'guard_storage_unavailable'),
    ('raw',{'error_kind':'timeout'},'guard_storage_unavailable'),
    ('raw',{'retry_after_epoch':NOW+60,'error_kind':'timeout','fallback_eligible':0},'guard_storage_unavailable'),
])
def test_legacy_guards_fail_closed_without_new_calls(fallback,key,fields,expected):
    from cache_store import set_cache_json
    from data_fetch.market_sources import official_issuer_master_transport as transport
    source,calls,control,base=fallback
    set_cache_json(transport.LEGACY_RAW_KEY if key=='raw' else transport.LEGACY_ADMISSION_KEY,fields,ttl_seconds=60)
    with pytest.raises(SourceResponseError) as exc:source.fetch_presentation_context('1229.TW')
    assert exc.value.error_kind==expected
    assert not calls and not base[1]


def test_typed_legacy_timeout_permits_only_distinct_json_not_csv_repeat(fallback):
    from cache_store import set_cache_json
    from data_fetch.market_sources import official_issuer_master_transport as transport
    source,calls,control,base=fallback;d={}
    set_cache_json(transport.LEGACY_RAW_KEY,{'retry_after_epoch':NOW+60,'error_kind':'timeout'},ttl_seconds=60)
    result=source.fetch_presentation_context('1229.TW',diagnostics=d)
    assert calls==[JSON_URL] and d['http_request_count']==3
    assert d['component_statuses'][0]['error_kind']=='cooldown'
    assert d['component_statuses'][0]['http_request_sent'] is False
    assert source.verify_context(result,'1229.TW')


def test_legacy_guard_storage_error_does_not_become_fallback(fallback,monkeypatch):
    import cache_store
    from data_fetch.market_sources import official_issuer_master_transport as transport
    source,calls,control,base=fallback;read=cache_store.get_cache_json
    def broken(key):
        if key==transport.LEGACY_RAW_KEY:raise OSError('isolated read unavailable')
        return read(key)
    monkeypatch.setattr(cache_store,'get_cache_json',broken)
    with pytest.raises(SourceResponseError) as exc:source.fetch_presentation_context('1229.TW')
    assert exc.value.error_kind=='guard_storage_unavailable' and not calls and not base[1]


@pytest.mark.parametrize('change',['issuer','duplicate','truncated','stale','future','fields'])
def test_invalid_complete_master_never_promotes_identity_or_downloads_material(fallback,change):
    import json
    source,calls,control,base=fallback
    rows=json.loads(RAW);row=next(r for r in rows if r['公司代號']=='1229')
    if change=='issuer':row['營利事業統一編號']='22099131'
    elif change=='duplicate':rows.append(deepcopy(row))
    elif change=='truncated':rows=rows[:1]
    elif change in ('stale','future'):
        for r in rows:r['出表日期']='1150801' if change=='stale' else '1151015'
    else:del row['網址']
    raw=json.dumps(rows,ensure_ascii=False).encode()
    control['value']=json_value(raw,raw,encoding='identity')
    with pytest.raises(SourceResponseError):source.fetch_presentation_context('1229.TW')
    assert calls==[source.MASTER_URL,JSON_URL] and not base[1]


def test_shared_json_warm_preserves_epoch_ttl_and_success_semantics(fallback,monkeypatch):
    # This is a replay of the retained MOPS receipt, not the preferred 1229 route.
    # Fresh 1229 requests now use the issuer PDF (covered by its routing tests).
    from data_fetch import enrichment_providers
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from data_fetch.market_sources import official_issuer_master as shared
    from cache_store import get_cache_backend
    source,calls,control,base=fallback;request=FetchRequest.from_ticker('1229.TW')
    monkeypatch.setattr(enrichment_providers,'fetch_free_earnings_call_context',source.fetch_presentation_context)
    cold=EarningsCallProvider().fetch(request,{'data':valid_data()})
    assert cold.audit['status']=='success' and cold.audit['http_request_count']==4
    receipt=cold.value['mops_material_receipt']['master'];key=shared._parameters(JSON_URL)[2]
    before=deepcopy(get_cache_backend()._entries[key])
    calls.clear();base[1].clear();monkeypatch.setattr(time,'time',lambda:NOW+60)
    warm=EarningsCallProvider().fetch(request,{'data':valid_data()})
    assert warm.audit['status']=='skipped_fresh_cache' and warm.audit['record_count']==1
    assert warm.audit['http_request_count']==0 and not warm.audit['http_request_sent']
    assert not calls and not base[1] and warm.value['documents']==cold.value['documents']
    after=warm.value['mops_material_receipt']['master']
    assert after['cache_hit'] is True and after['retrieved_at']==receipt['retrieved_at']==NOW
    assert after['fresh_until_epoch']==receipt['fresh_until_epoch']
    assert get_cache_backend()._entries[key]==before


def test_existing_shared_master_cross_consumer_has_no_second_identity_request(harness,monkeypatch):
    from data_fetch.market_sources import mops_presentation as source
    from data_fetch.market_sources.gce_conference_transport import ConferenceHttp
    download=source.MasterHttp.download_original
    monkeypatch.setattr(ConferenceHttp,'download_original',download)
    _,original=ConferenceHttp(time.monotonic()+25).get_receipt(source.MASTER_URL)
    harness[1].clear()
    value=source.fetch_presentation_context('1229.TW')
    receipt=value['mops_material_receipt']['master']
    assert receipt['cache_hit'] is True and receipt['retrieved_at']==original['retrieved_at']
    assert harness[1]==['1229.TW:index','1229.TW:material']


def test_valid_shared_warm_precedes_legacy_guard_without_renewing(harness,monkeypatch):
    from cache_store import set_cache_json
    from data_fetch.market_sources import mops_presentation as source
    from data_fetch.market_sources import official_issuer_master_transport as transport
    cold=source.fetch_presentation_context('1229.TW');harness[1].clear()
    set_cache_json(transport.LEGACY_ADMISSION_KEY,{'retry_at':NOW+60},ttl_seconds=60)
    d={};warm=source.fetch_presentation_context('1229.TW',diagnostics=d)
    assert not harness[1] and d['http_request_count']==0 and d['cache_hit'] is True
    assert warm['mops_material_receipt']['master']['retrieved_at']==cold['mops_material_receipt']['master']['retrieved_at']


def test_old_winbond_receipt_remains_exact_and_replayable(harness,monkeypatch):
    import base64
    from data_fetch.market_sources import mops_presentation as source
    from data_fetch.market_sources.winbond_conference_transport import ConferenceHttp
    def old_download(self,url,diagnostic):
        raw=harness[0]['master'];harness[1].append('legacy-master')
        diagnostic.update(http_request_sent=True,http_status=200)
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest()}
    with monkeypatch.context() as patch:
        patch.setattr(ConferenceHttp,'download_original',old_download)
        patch.setattr(source,'MasterHttp',ConferenceHttp)
        old=source.fetch_presentation_context('1229.TW')
    original=deepcopy(old);harness[1].clear()
    assert 'retrieval_policy' not in old['mops_material_receipt']['master']
    assert source.verify_context(old,'1229.TW') and old==original and not harness[1]
    old['mops_material_receipt']['master']['source_url']=JSON_URL
    assert not source.verify_context(old,'1229.TW')


@pytest.mark.parametrize('opts',[{}, {'force_refresh':True},{'use_cache':False}])
def test_mops_cooldown_cannot_be_bypassed_by_shared_master(fallback,opts):
    from cache_store import set_cache_json
    from mops_material_originals import GUARD
    source,calls,control,base=fallback;d={}
    set_cache_json(GUARD,{'retry_at':NOW+7200,'error_kind':'timeout'},ttl_seconds=7200)
    with pytest.raises(SourceResponseError) as exc:source.fetch_presentation_context('1229.TW',diagnostics=d,**opts)
    assert exc.value.error_kind=='cooldown'
    assert calls==[source.MASTER_URL,JSON_URL] and not base[1]
    assert not d['mops_material_originals_verified'] and d['http_request_count']==2


def test_whole_deadline_spent_on_csv_never_attempts_json_or_mops(fallback,monkeypatch):
    source,calls,control,base=fallback;clock=[10.]
    monkeypatch.setattr(time,'monotonic',lambda:clock[0])
    def timeout(self,url,d):
        calls.append(url);d.update(http_request_sent=True);clock[0]+=25
        raise SourceResponseError('timeout')
    monkeypatch.setattr(source.MasterHttp,'download_original',timeout)
    with pytest.raises(SourceResponseError) as exc:source.fetch_presentation_context('1229.TW')
    assert exc.value.error_kind=='timeout' and calls==[source.MASTER_URL] and not base[1]


@pytest.mark.parametrize('url',['https://www.gce.com.tw/','https://www.winbond.com.tw/',JSON_URL+'?x=1','http://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'])
def test_dedicated_native_surface_has_no_issuer_or_arbitrary_url_route(monkeypatch,url):
    from data_fetch.market_sources import official_issuer_master_transport as transport
    monkeypatch.setattr(transport.native.ConferenceHttp,'download_original',lambda *a:pytest.fail('unexpected delegated URL'))
    http=transport.IssuerMasterHttp(time.monotonic()+25)
    with pytest.raises(SourceResponseError):http.download_original(url,{})
    with pytest.raises(SourceResponseError):http.get_receipt(url)
    assert http.http_request_count==0


def _shorten_mops_original(receipt, spec):
    """Model a legitimate independently stored shorter deadline in isolation."""
    from cache_store import get_cache_json,set_cache_json
    from mops_material_originals import cache_key
    key='shared_provider:v1:'+sha256(cache_key(spec).encode()).hexdigest()
    row=get_cache_json(key);row['fresh_until_epoch']=NOW+5
    set_cache_json(key,row,ttl_seconds=1800)
    receipt['fresh_until_epoch']=NOW+5


@pytest.mark.parametrize('short_component',['master','index','material'])
def test_public_handoff_rechecks_all_original_deadlines_after_final_read(fallback,monkeypatch,short_component):
    source,calls,control,base=fallback
    if short_component=='master':control['value']['response_metadata']['cache_control']='max-age=5'
    clock=[NOW];monkeypatch.setattr(time,'time',lambda:clock[0])
    acquire=source.get_original
    def shorter(spec,*args,**kwargs):
        raw,receipt=acquire(spec,*args,**kwargs)
        kind='index' if spec['format']=='html' else 'material'
        if kind==short_component:_shorten_mops_original(receipt,spec)
        return raw,receipt
    monkeypatch.setattr(source,'get_original',shorter)
    read=source.original_bytes;material_reads=[]
    def finishing_read(receipt,spec):
        raw=read(receipt,spec)
        if spec['format']=='pptx':
            material_reads.append(receipt['raw_response_sha256'])
            if len(material_reads)==3:clock[0]=NOW+5.1
        return raw
    monkeypatch.setattr(source,'original_bytes',finishing_read)
    d={}
    with pytest.raises(SourceResponseError) as exc:source.fetch_presentation_context('1229.TW',diagnostics=d)
    assert exc.value.error_kind=='original_expired' and len(material_reads)==3
    assert d['mops_material_originals_verified'] is False and d['http_request_count']==4
    assert calls==[source.MASTER_URL,JSON_URL] and base[1]==['1229.TW:index','1229.TW:material']


@pytest.mark.parametrize('short_component',['master','index','material','max_age'])
def test_saved_context_verification_rechecks_final_clock_without_more_io(fallback,monkeypatch,short_component):
    source,calls,control,base=fallback
    if short_component=='master':control['value']['response_metadata']['cache_control']='max-age=5'
    value=source.fetch_presentation_context('1229.TW');proof=value['mops_material_receipt']
    if short_component in ('index','material'):
        spec=proof['index_request'] if short_component=='index' else proof['selected']
        _shorten_mops_original(proof[short_component],spec)
    age=5 if short_component=='max_age' else 1800
    assert source.verify_context(value,'1229.TW',max_age=age)
    calls.clear();base[1].clear();before=deepcopy(value)
    clock=[NOW];monkeypatch.setattr(time,'time',lambda:clock[0])
    read=source.master_bytes;master_reads=[]
    def finishing_read(*args,**kwargs):
        raw=read(*args,**kwargs);master_reads.append(1)
        if len(master_reads)==2:clock[0]=NOW+5.1
        return raw
    monkeypatch.setattr(source,'master_bytes',finishing_read)
    assert not source.verify_context(value,'1229.TW',max_age=age)
    assert len(master_reads)==2 and value==before and not calls and not base[1]
