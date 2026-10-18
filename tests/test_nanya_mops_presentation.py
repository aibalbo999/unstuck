"""Complete native originals, exact replay, and acquisition/projection boundaries."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import asyncio,gzip,json,time
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from data_fetch.market_sources import nanya_mops_presentation as nanya
from official_response_evidence import archive_response
from search_provider_runtime import SourceResponseError

F=Path(__file__).parent/'fixtures/source_acquisition'
NOW=1791764000.
def raw(name):return gzip.decompress((F/name).read_bytes())

@pytest.fixture
def harness(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    import official_financials_mops_conference as mops
    cache_store.set_cache_backend(InMemoryCache())
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return cls(2026,10,12,8,0,tzinfo=tz)
    monkeypatch.setattr(mops,'datetime',Clock)
    monkeypatch.setattr(nanya.time,'time',lambda:NOW)
    index=archive_response(raw('mops2408_same_day_conference_20261012.html.gz'),source_url=nanya.INDEX_URL,retrieved_at=NOW-1000)
    events=mops.parse_conference_response(raw('mops2408_same_day_conference_20261012.html.gz').decode(),'2408',http_status=200)
    metadata=nanya._metadata(events[0]);calls=[];observations=[];cache_rows=[]
    monkeypatch.setattr(nanya,'read_cached_listed_roster_bytes',lambda:(raw('nanya2408_complete_roster_20261011.json.gz'),{'fetched_at_epoch':NOW-2000}))
    def wire(url,**kwargs):
        calls.append(url);kwargs['diagnostics'].update(http_request_sent=True,http_status=200,response_complete=True)
        return raw('nanya2408_presentation_20260819.pdf.gz')
    monkeypatch.setattr(nanya,'download',wire);monkeypatch.setattr(nanya,'cooldown_state',lambda key:None)
    monkeypatch.setattr(nanya,'record_observation',lambda *a,**k:observations.append(deepcopy(k)))
    import search_provider_runtime
    monkeypatch.setattr(search_provider_runtime,'record_source_audit_entries',lambda rows:cache_rows.extend(deepcopy(rows)))
    @contextmanager
    def lease(*a,**k):yield lambda:True
    monkeypatch.setattr(nanya,'endpoint_admission',lease)
    def diagnostic():return {'mops_year_observations':[{'raw_http_receipt':index,'cache_hit':True}], 'http_request_count':0,'http_request_sent':False}
    yield SimpleNamespace(metadata=metadata,diagnostic=diagnostic,calls=calls,observations=observations,cache_rows=cache_rows)
    cache_store.reset_cache_store_for_tests()


def get(h,diagnostic=None):return nanya.enrich_nanya_context('2408.TW',h.metadata,diagnostics=diagnostic if diagnostic is not None else h.diagnostic(),deadline=time.monotonic()+20)


def test_full14_pages_have_distinct_event_file_quarter_dates_and_no_transcript(harness):
    h=harness;d=h.diagnostic();value=get(h,d);doc=value['documents'][0]
    assert len(h.calls)==1 and h.observations[0]['outcome']=='results'
    assert doc['page_count']==len(doc['pages'])==14
    assert doc['native_text_coverage']=='complete' and doc['missing_text_pages']==doc['garbled_pages']==[]
    assert value['date']==doc['event_date']=='2026-09-21' and doc['material_file_date']=='2026-08-19' and doc['content_period']=='Q2 2026'
    assert doc['published_at'] is None and value['transcript_available'] is False and not value['transcript_excerpt']
    assert value['coverage_status']=='partial' and doc['full_content_coverage_verified'] is False
    assert value['fetched_at_epoch']==d['fetched_at_epoch']==NOW-1000 and doc['retrieved_at_epoch']==NOW
    assert d['http_request_count']==1 and d['http_request_sent'] is True
    assert nanya.verify_context(value,'2408.TW')
    assert 'documents'not in h.metadata


@pytest.mark.parametrize('field',['text','event_date','file_date','period','issuer','identity','index','pdf','receipt','url','projection'])
def test_modified_context_cannot_pass_original_replay(harness,field):
    value=get(harness);doc=value['documents'][0]
    if field=='text':doc['pages'][0]['text']+=' invented value'
    elif field=='event_date':value['date']='2026-10-12'
    elif field=='file_date':doc['material_file_date']='2026-09-21'
    elif field=='period':doc['content_period']='Q3 2026'
    elif field=='issuer':value['ticker']='9103.TW'
    elif field=='receipt':value.pop('nanya_mops_receipt')
    elif field=='url':doc['url']=doc['url'].replace('2408','1325')
    elif field=='projection':doc.pop('projection_policy')
    else:value['nanya_mops_receipt'][field]['raw_response_bytes']+=1
    assert not nanya.verify_context(value,'2408.TW')


def test_warm_original_has_no_second_HTTP_and_retains_all_source_times(harness):
    h=harness;first=get(h);d=h.diagnostic();second=get(h,d)
    assert first==second and len(h.calls)==1
    assert d['http_request_sent'] is False and d['http_request_count']==0
    assert d['fetched_at_epoch']==NOW-1000
    assert len(h.cache_rows)==1 and h.cache_rows[0]['http_request_sent'] is False
    assert h.cache_rows[0]['fetched_at_epoch']==NOW


def test_missing_or_corrupt_cached_original_never_starts_another_download(harness,monkeypatch):
    h=harness;first=get(h);h.calls.clear()
    monkeypatch.setattr(nanya,'shared_fetch',lambda *a,**k:({'pdf':{},'diagnostic':{}},{'cache_hit':True}))
    d=h.diagnostic();value=get(h,d)
    assert value==h.metadata and not h.calls and not value.get('documents')
    assert d['component_statuses']['prepared_pdf']['error_kind']=='original_unverified'
    assert nanya.verify_context(first,'2408.TW')


@pytest.mark.parametrize('kind',['lease_lost','timeout','single_flight_busy','guard_storage_unavailable'])
def test_typed_abort_does_not_continue_with_a_second_source(harness,monkeypatch,kind):
    def fail(*a,**k):raise SourceResponseError(kind)
    monkeypatch.setattr(nanya,'download',fail)
    with pytest.raises(SourceResponseError)as exc:get(harness)
    assert exc.value.error_kind==kind


def test_expired_parent_deadline_does_not_start_the_pdf(harness):
    with pytest.raises(SourceResponseError)as exc:
        nanya.enrich_nanya_context('2408.TW',harness.metadata,diagnostics=harness.diagnostic(),deadline=time.monotonic()-1)
    assert exc.value.error_kind=='timeout' and not harness.calls


def test_source_guard_prevents_new_download_and_keeps_metadata(harness,monkeypatch):
    monkeypatch.setattr(nanya,'cooldown_state',lambda key:{'error_kind':'rate_limited','retry_at':NOW+60})
    d=harness.diagnostic();assert get(harness,d)==harness.metadata
    assert not harness.calls and not harness.observations[0]['sent']


def test_roles_receive_bounded_english_period_view_without_RGB_and_no_receipts(harness):
    from prompt_evidence import prompt_evidence_copy
    from conference_presentation_prompt import presentation_prompt_context
    value=get(harness);before=deepcopy(value)
    projected=prompt_evidence_copy(value);assert 'nanya_mops_receipt'not in projected
    for role in (3,5,12):
        view=presentation_prompt_context(value,role);doc=view['documents'][0]
        assert doc['content_period']=='Q2 2026' and doc['material_file_date']=='2026-08-19' and doc['event_date']=='2026-09-21'
        assert doc['layout_color_fields_omitted'] is True
        assert sum(len(p['text'].split())for p in doc['pages'])<=200
        assert not any('R 0\nG 182'in p['text']for p in doc['pages'])
        assert any(term in json.dumps(doc['pages']).casefold()for term in ('revenue','technology','outlook','capital','cash','market'))
    for role in (1,20,21,24):assert not presentation_prompt_context(value,role)
    assert value==before and value['documents'][0]['pages'][0]['text'].startswith(nanya.PALETTE)


def test_native_parent_and_warm_http_truth_are_not_double_counted(harness):
    from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
    from provider_acquisition import observation_kind
    d=harness.diagnostic();value=get(harness,d)
    result={'audit':{'status':'success','http_request_sent':True},'value':value}
    apply_earnings_call_audit(result,d);audit=result['audit']
    assert audit['http_request_sent'] is False and audit['source_http_request_sent'] is True
    assert observation_kind({'provider':audit['provider'],'status':audit['status'],'record_count':1,'message':audit['message'],'details':audit})=='aggregate_count'


@pytest.mark.parametrize('remove_markers',[False,True])
def test_source_refresh_cannot_accept_unverified_pages_after_marker_removal(harness,remove_markers):
    from report_source_refresh import fetch_report_source_data
    value=get(harness);value['documents'][0]['pages'][0]['text']+=' invented value'
    if remove_markers:
        value.pop('nanya_mops_receipt');value['source']='MOPS index';value['documents'][0]['source']='MOPS index'
    old={'ticker':'2408.TW','data':{'ticker':'2408.TW','current_price':100},'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-100,'ticker':'2408.TW'}]};before=deepcopy(old)
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):return SimpleNamespace(data={'ticker':'2408.TW','earnings_call':value},source_audit=[{'source':'earnings_call','status':'success','fetch_id':'fixture','fetched_at_epoch':NOW}])
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(old,'earnings_call',Service()))
    assert exc.value.status_code==502 and old==before


def test_unknown_RGB_template_is_not_generically_stripped_or_qualified(harness,monkeypatch):
    real=nanya.extract_pdf_pages
    def changed(*a,**k):
        result=real(*a,**k);result['pages'][2]['text']='R 9'+result['pages'][2]['text'][3:];return result
    monkeypatch.setattr(nanya,'extract_pdf_pages',changed)
    d=harness.diagnostic();value=get(harness,d)
    assert value==harness.metadata and not value.get('documents')
    assert len(harness.calls)==1 and harness.observations[0]['outcome']=='failure'


def test_PDF_child_timeout_stays_typed_abort(harness,monkeypatch):
    from source_pdf_reader import SourcePdfError
    def timed_out(*a,**k):raise SourcePdfError('timeout')
    monkeypatch.setattr(nanya,'extract_pdf_pages',timed_out)
    with pytest.raises(SourceResponseError)as exc:get(harness)
    assert exc.value.error_kind=='timeout' and len(harness.calls)==1


def test_unavailable_guard_storage_is_not_hidden_as_optional_metadata(harness,monkeypatch):
    monkeypatch.setattr(nanya,'cooldown_state',lambda key:{'error_kind':'guard_storage_unavailable'})
    with pytest.raises(SourceResponseError)as exc:get(harness)
    assert exc.value.error_kind=='guard_storage_unavailable' and not harness.calls


def test_newly_started_event_without_material_does_not_inherit_prior_quarter_PDF(harness,monkeypatch):
    import official_financials_mops_conference as mops
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return cls(2026,10,12,16,0,tzinfo=tz)
    monkeypatch.setattr(mops,'datetime',Clock)
    events=mops.parse_conference_response(raw('mops2408_same_day_conference_20261012.html.gz').decode(),'2408',http_status=200)
    metadata=nanya._metadata(events[0]);assert metadata['date']=='2026-10-12' and metadata['materials']==[]
    value=nanya.enrich_nanya_context('2408.TW',metadata,diagnostics=harness.diagnostic(),deadline=time.monotonic()+20)
    assert value==metadata and not value.get('documents') and not harness.calls


def test_actual_public_workflow_integrates_all14_original_pages(harness,monkeypatch):
    from data_fetch import earnings_call_fetcher as flow
    def metadata(*a,**kwargs):kwargs['diagnostics'].update(harness.diagnostic());return deepcopy(harness.metadata)
    monkeypatch.setattr(flow,'_fetch_official_index_context',metadata)
    value=flow.fetch_free_earnings_call_context('2408.TW')
    assert value['documents'][0]['page_count']==14 and nanya.verify_context(value,'2408.TW')
    assert len(harness.calls)==1


def test_other_stock_cannot_accept_a_renamed_nanya_prepared_original(harness):
    from report_source_refresh import fetch_report_source_data
    value=get(harness);value['ticker']='9103.TW'
    old={'ticker':'9103.TW','data':{'ticker':'9103.TW','current_price':100},'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-100,'ticker':'9103.TW'}]};before=deepcopy(old)
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):return SimpleNamespace(data={'ticker':'9103.TW','earnings_call':value},source_audit=[{'source':'earnings_call','status':'success','fetch_id':'fixture','fetched_at_epoch':NOW}])
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(old,'earnings_call',Service()))
    assert exc.value.status_code==502 and old==before


@pytest.mark.parametrize('index_http',[0,1])
def test_failed_PDF_HTTP_is_counted_once_in_this_workflow(harness,monkeypatch,index_http):
    def fail(url,**kwargs):
        harness.calls.append(url);kwargs['diagnostics'].update(http_request_sent=True,http_status=503)
        raise SourceResponseError('server_error',status_code=503)
    monkeypatch.setattr(nanya,'download',fail)
    d=harness.diagnostic();d.update(http_request_count=index_http,http_request_sent=bool(index_http))
    assert get(harness,d)==harness.metadata
    assert d['http_request_count']==index_http+1 and d['http_request_sent'] is True
    second=harness.diagnostic();assert get(harness,second)==harness.metadata
    assert len(harness.calls)==1 and second['http_request_count']==0 and second['http_request_sent'] is False


def test_HTTP200_local_parser_warning_has_document_error_cache_not_shared_MOPS_outage(harness,monkeypatch):
    from cache_store import get_cache_json
    from source_pdf_reader import SourcePdfError
    def warn(*a,**k):raise SourcePdfError('parser_warning')
    monkeypatch.setattr(nanya,'extract_pdf_pages',warn)
    d=harness.diagnostic();assert get(harness,d)==harness.metadata
    assert harness.observations[0]['details']['http_status']==200
    assert get_cache_json(nanya.GUARD) is None
    assert get(harness)==harness.metadata and len(harness.calls)==1


def test_valid_warm_original_survives_best_effort_telemetry_failure(harness,monkeypatch):
    import search_provider_runtime,sqlite3
    first=get(harness);harness.calls.clear()
    def fail(*a,**k):raise sqlite3.OperationalError('isolated lock')
    monkeypatch.setattr(search_provider_runtime,'record_source_audit_entries',fail)
    d=harness.diagnostic();assert get(harness,d)==first and not harness.calls
    assert d['http_request_count']==0 and d['http_request_sent'] is False
    assert d['component_statuses']['prepared_pdf']['cache_observation_error_kind']=='OperationalError'


def test_cache_observation_cannot_publish_after_endpoint_lease_is_lost(harness,monkeypatch):
    import search_provider_runtime
    get(harness);harness.calls.clear();owned=[True]
    @contextmanager
    def lease(*a,**k):yield lambda:owned[0]
    monkeypatch.setattr(nanya,'endpoint_admission',lease)
    monkeypatch.setattr(search_provider_runtime,'record_source_audit_entries',lambda *a,**k:owned.__setitem__(0,False))
    with pytest.raises(SourceResponseError)as exc:get(harness)
    assert exc.value.error_kind=='lease_lost' and not harness.calls


def test_cache_observation_cannot_publish_past_parent_deadline(harness,monkeypatch):
    import search_provider_runtime
    get(harness);harness.calls.clear();clock=[0.]
    monkeypatch.setattr(nanya,'time',SimpleNamespace(time=lambda:NOW,monotonic=lambda:clock[0]))
    monkeypatch.setattr(search_provider_runtime,'record_source_audit_entries',lambda *a,**k:clock.__setitem__(0,21.))
    with pytest.raises(SourceResponseError)as exc:
        nanya.enrich_nanya_context('2408.TW',harness.metadata,diagnostics=harness.diagnostic(),deadline=20.)
    assert exc.value.error_kind=='timeout' and not harness.calls and clock[0]==21.


def test_complete_original_survives_HTTP_error_cache_without_download_or_age_renewal(harness,monkeypatch):
    from hashlib import sha256
    from cache_store import get_cache_json,set_cache_json
    h=harness;first=get(h);receipt=first['nanya_mops_receipt']['pdf'];h.calls.clear()
    key='shared_provider:v1:'+sha256((nanya.POLICY+':'+receipt['source_url']).encode()).hexdigest()
    failed={'error_kind':'SourceResponseError','retry_after_epoch':NOW+3600,'fresh_until_epoch':NOW}
    set_cache_json(key,failed,ttl_seconds=3600)
    monkeypatch.setattr(nanya.time,'time',lambda:NOW+1200)
    def unexpected(*a,**k):
        h.calls.append('unexpected');raise SourceResponseError('server_error',status_code=503)
    monkeypatch.setattr(nanya,'download',unexpected)
    d=h.diagnostic();second=get(h,d)
    assert second.get('documents')==first['documents'] and nanya.verify_context(second,'2408.TW')
    assert second['fetched_at_epoch']==NOW-1000 and second['documents'][0]['retrieved_at_epoch']==NOW
    assert get_cache_json(key)==failed and not h.calls and len(h.observations)==1
    assert d['http_request_count']==0 and d['http_request_sent'] is False
    assert h.cache_rows[-1]['status']=='skipped_fresh_cache' and h.cache_rows[-1]['http_request_sent'] is False
    assert h.cache_rows[-1]['fetched_at_epoch']==NOW


def test_explicit_qualified_reuse_keeps_original_expiry_guards_and_HTTP_failure(harness,monkeypatch):
    from hashlib import sha256
    from cache_store import get_cache_backend,get_cache_json,set_cache_json
    h=harness;first=get(h);receipt=first['nanya_mops_receipt']['pdf'];h.calls.clear()
    original_key='nanya_mops_original:v1:'+sha256(receipt['source_url'].encode()).hexdigest()
    get_cache_backend().delete(original_key)
    key='shared_provider:v1:'+sha256((nanya.POLICY+':'+receipt['source_url']).encode()).hexdigest()
    failed={'error_kind':'SourceResponseError','retry_after_epoch':NOW+7200}
    guard={'error_kind':'rate_limited','retry_at':NOW+7200,'http_status':429}
    set_cache_json(key,failed,ttl_seconds=7200);set_cache_json(nanya.GUARD,guard,ttl_seconds=7200)
    monkeypatch.setattr(nanya.time,'time',lambda:NOW+1200)
    written=[];original_set=set_cache_json
    def save(cache_key,value,ttl_seconds):
        written.append((cache_key,deepcopy(value),ttl_seconds));original_set(cache_key,value,ttl_seconds)
    import cache_store
    monkeypatch.setattr(cache_store,'set_cache_json',save)
    outcome=nanya.retain_qualified_original(first)
    assert outcome['new_HTTP_or_acquisition_successes']==0 and outcome['original_receipt']==receipt
    assert written==[(original_key,{'policy':nanya.POLICY,'pdf':receipt},nanya._freshness()-1200)]
    assert get_cache_json(key)==failed and get_cache_json(nanya.GUARD)==guard
    d=h.diagnostic();second=get(h,d)
    assert second==first and not h.calls and len(h.observations)==1
    assert d['http_request_sent'] is False and d['http_request_count']==0
    assert get_cache_json(key)==failed and get_cache_json(nanya.GUARD)==guard


@pytest.mark.parametrize('corruption',['future','expired','bool_epoch','page','URL','missing_receipt'])
def test_adoption_rejects_unqualified_original_and_does_not_write_or_call_HTTP(harness,monkeypatch,corruption):
    import cache_store
    value=get(harness);before=deepcopy(value);harness.calls.clear();receipt=value['nanya_mops_receipt']['pdf']
    if corruption=='future':receipt['retrieved_at']=NOW+1
    elif corruption=='expired':receipt['retrieved_at']=NOW-nanya._freshness()
    elif corruption=='bool_epoch':receipt['retrieved_at']=True
    elif corruption=='page':value['documents'][0]['pages'][0]['text']+=' invention'
    elif corruption=='URL':receipt['source_url']=receipt['source_url'].replace('2408','1325')
    else:value.pop('nanya_mops_receipt')
    def forbidden(*a,**k):raise AssertionError('invalid original must not be retained')
    monkeypatch.setattr(cache_store,'set_cache_json',forbidden)
    with pytest.raises(ValueError,match='not qualified'):nanya.retain_qualified_original(value)
    assert not harness.calls and len(harness.observations)==1 and nanya.verify_context(before,'2408.TW')


def test_retained_original_never_attaches_to_a_new_event_without_material(harness,monkeypatch):
    import official_financials_mops_conference as mops
    get(harness);harness.calls.clear()
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return cls(2026,10,12,16,0,tzinfo=tz)
    monkeypatch.setattr(mops,'datetime',Clock)
    events=mops.parse_conference_response(raw('mops2408_same_day_conference_20261012.html.gz').decode(),'2408',http_status=200)
    metadata=nanya._metadata(events[0]);assert not metadata['materials']
    value=nanya.enrich_nanya_context('2408.TW',metadata,diagnostics=harness.diagnostic(),deadline=time.monotonic()+20)
    assert value==metadata and not value.get('documents') and not harness.calls


def test_optional_retention_write_error_cannot_discard_completed_native_result(harness,monkeypatch):
    import cache_store
    original_set=cache_store.set_cache_json
    def fail(key,*a,**k):
        if key.startswith('nanya_mops_original:'):raise OSError('isolated unavailable cache')
        return original_set(key,*a,**k)
    monkeypatch.setattr(cache_store,'set_cache_json',fail)
    d=harness.diagnostic();value=get(harness,d)
    assert len(harness.calls)==1 and value['documents'][0]['page_count']==14 and nanya.verify_context(value,'2408.TW')
    assert d['component_statuses']['prepared_pdf']['original_retention_error_kind']=='OSError'
