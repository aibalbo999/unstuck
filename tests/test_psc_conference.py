"""Public PSC acquisition uses original event, issuer and complete PDF evidence."""
from pathlib import Path
from datetime import datetime,timezone
from copy import deepcopy
from hashlib import sha256
from contextlib import contextmanager
import gzip,sys,time,asyncio
import pytest
from fastapi import HTTPException

F=Path(__file__).parent/'fixtures/source_acquisition'
NOW=datetime(2026,10,13,0,30,tzinfo=timezone.utc).timestamp()
PDF='https://www.pscnet.com.tw/upload/pscnet/file/20260826164426662249.pdf'
ANNOUNCEMENT='https://www.pscnet.com.tw/pscnetAbout/newsContent.do?sub_id=BIG_MESSAGE_SUB_ID&id=6ba2dc9d7a00000062fb548c63075544'
def raw(name):return gzip.decompress((F/name).read_bytes())

@pytest.fixture
def harness(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    from cache_backends import InMemoryCache
    import cache_store
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time,'time',lambda:NOW)
    monkeypatch.setattr(fetcher,'_fetch_official_index_context',lambda *a,**k:{})
    calls=[];observations=[];bodies={}
    if (Path(__file__).parents[1]/'backend/data_fetch/market_sources/psc_conference.py').exists():
        from data_fetch.market_sources import psc_conference as psc
        bodies.update({psc.ROSTER_URL:raw('nanya2408_complete_roster_20261011.json.gz'),
                       psc.HOME_URL:raw('psc2855_complete_about_20261013.gz'),psc.INDEX_URL:raw('psc2855_complete_index_20261013.gz'),
                       ANNOUNCEMENT:raw('psc2855_complete_announcement_20261013.gz'),PDF:raw('psc2855_complete_presentation_20261013.gz')})
        def master():
            body=bodies[psc.ROSTER_URL]
            return body,{'fetched_at_epoch':NOW-3600,'http_status_observed':False,'cache_source':'official-company-roster:v2:.TW',
                         'source_payload_sha256':sha256(body).hexdigest(),'source_payload_bytes':len(body)}
        def download(url,**kwargs):
            calls.append(url);kwargs['diagnostics'].update(http_request_sent=True,http_status=200,response_complete=True);return bodies[url]
        monkeypatch.setattr(psc,'read_cached_listed_roster_bytes',master);monkeypatch.setattr(psc,'download',download)
        monkeypatch.setattr(psc,'cooldown_state',lambda key:None);monkeypatch.setattr(psc,'record_observation',lambda *a,**k:observations.append(k))
        @contextmanager
        def lease(*a,**k):yield lambda:True
        monkeypatch.setattr(psc,'endpoint_admission',lease)
    yield bodies,calls,observations
    cache_store.reset_cache_store_for_tests()

def test_public_free_call_recovers_complete_PSC_original_with_real_announced_time(harness):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    details={};value=fetch_free_earnings_call_context('2855.TW',diagnostics=details)
    assert value.get('documents') and value['documents'][0]['page_count']==12
    assert value['date']=='2026-08-26'and value['time']=='14:00'
    assert value['transcript_available']is False and details['psc_originals_verified']is True

def test_source_only_conflicting_instrument_is_rejected_before_provider(harness):
    from report_source_refresh import fetch_report_source_data
    data={'ticker':'2855.TW','quote_type':'ETF','company_name':'統一證'}
    old={'ticker':'2855.TW','data':data,'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-100}]};calls=[]
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):calls.append(1);raise AssertionError('invalid stock context must stop before acquisition')
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(old,'earnings_call',Service()))
    assert exc.value.status_code==400 and not calls


def test_complete_packet_replays_event_and_originals_without_claiming_transcript(harness):
    from data_fetch.market_sources import psc_conference as psc
    _,calls,observations=harness;value=psc._fetch()['context'];doc=value['documents'][0]
    assert calls==[psc.HOME_URL,psc.INDEX_URL,ANNOUNCEMENT,PDF]
    assert len(observations)==4 and all(o['outcome']=='results'for o in observations)
    assert value['date']=='2026-08-26'and value['time']=='14:00'and value['period']=='2026Q2'
    assert doc['event_date_basis']=='issuer_announcement_date_time_and_PDF_cover_match'
    assert doc['page_count']==len(doc['pages'])==12 and doc['full_content_coverage_verified']is False
    assert value['transcript_available']is False and value['summary']==value['transcript_excerpt']==''
    assert psc.verify_context(value,'2855.TW')


@pytest.mark.parametrize('change',['text','date','time','source','URL','receipt','hash','bool_epoch','future_epoch','expired_master','fake_native_master','transcript','extra'])
def test_saved_packet_cannot_override_native_originals(harness,change):
    from data_fetch.market_sources import psc_conference as psc
    value=psc._fetch()['context'];proof=value['psc_conference_receipt']
    if change=='text':value['documents'][0]['pages'][0]['text']+='invented'
    elif change=='date':value['date']='2026-08-27'
    elif change=='time':value['time']='14:01'
    elif change=='source':value['documents'][0]['source']='other'
    elif change=='URL':value['documents'][0]['url']='https://evil.example/fake.pdf'
    elif change=='receipt':value.pop('psc_conference_receipt')
    elif change=='hash':proof['pdf']['raw_response_sha256']='0'*64
    elif change=='bool_epoch':proof['pdf']['retrieved_at']=True
    elif change=='future_epoch':proof['pdf']['retrieved_at']=NOW+1
    elif change=='expired_master':proof['identity']['retrieved_at']=NOW-86401
    elif change=='fake_native_master':proof['identity']['http_status']=200
    elif change=='transcript':value['transcript_available']=True
    else:value['invented_transcript']='not real'
    assert not psc.verify_context(value,'2855.TW')
    assert psc.is_marked(value)


def test_warm_cache_uses_same_original_epoch_without_HTTP_observations(harness):
    from data_fetch.market_sources import psc_conference as psc
    _,calls,observations=harness;details={};value=psc.fetch_psc_context('2855.TW',diagnostics=details)
    calls.clear();observations.clear();warm={};assert psc.fetch_psc_context('2855.TW',diagnostics=warm)==value
    assert not calls and not observations and warm['http_request_count']==0 and warm['http_request_sent']is False
    assert warm['fetched_at_epoch']==details['fetched_at_epoch']==NOW


def test_guard_storage_unavailable_stops_before_HTTP(harness,monkeypatch):
    from data_fetch.market_sources import psc_conference as psc
    from search_provider_runtime import SourceResponseError
    import cache_store
    def fail(*a,**k):raise RuntimeError('guard store unavailable')
    monkeypatch.setattr(cache_store,'get_cache_json',fail)
    with pytest.raises(SourceResponseError)as exc:psc._fetch()
    assert exc.value.error_kind=='guard_storage_unavailable'and not harness[1]


@pytest.mark.parametrize('case_ticker,data',[('2855.TW',{'ticker':'3042.TW','quote_type':'EQUITY'}),
                                       ('3042.TW',{'ticker':'2855.TW','quote_type':'EQUITY'}),
                                       ('2855.TW',{'ticker':'2855.TW','quote_type':'ETF'}),
                                       ('2855.TW',{'ticker':'2855.TW','quote_type':'EQUITY','company_name':'台積電'})])
def test_public_provider_cannot_rewrite_stock_subject_before_native_HTTP(harness,case_ticker,data):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker(case_ticker),{'data':data})
    assert result.status=='unavailable'and result.audit['event_kind']=='local_block'and not harness[1]


def test_private_receipts_are_not_prompt_context(harness):
    from data_fetch.market_sources import psc_conference as psc
    from prompt_evidence import prompt_evidence_copy
    value=psc._fetch()['context'];before=deepcopy(value)
    projected=prompt_evidence_copy(value)
    assert 'psc_conference_receipt'not in projected and value==before


@pytest.mark.parametrize('kind',['lease_lost','timeout','single_flight_busy','guard_storage_unavailable'])
def test_terminal_guard_error_does_not_start_more_index_fallback(harness,monkeypatch,kind):
    from data_fetch.market_sources import psc_conference as psc
    from data_fetch import earnings_call_fetcher as fetcher
    from search_provider_runtime import SourceResponseError
    def fail(*a,**k):raise SourceResponseError(kind)
    monkeypatch.setattr(psc,'fetch_psc_context',fail)
    monkeypatch.setattr(fetcher,'_fetch_official_index_context',lambda *a,**k:pytest.fail('second fallback after terminal guard'))
    with pytest.raises(SourceResponseError)as exc:fetcher.fetch_free_earnings_call_context('2855.TW')
    assert exc.value.error_kind==kind


def test_reported_financial_year_is_independent_of_event_year(harness):
    from data_fetch.market_sources import psc_conference as psc
    body=raw('psc2855_complete_announcement_20261013.gz')
    selection=psc.select_index(raw('psc2855_complete_index_20261013.gz'))
    previous=body.replace('115年度Q2'.encode(),'114年度Q2'.encode())
    assert psc.parse_announcement(previous,selection)['content_period']=='2025Q2'
    with pytest.raises(ValueError):psc.parse_announcement(body.replace('115年度Q2'.encode(),'116年度Q2'.encode()),selection)


def test_role_prompt_preserves_date_basis_and_read_limit(harness):
    from data_fetch.market_sources import psc_conference as psc
    from conference_presentation_prompt import presentation_prompt_context
    value=psc._fetch()['context'];before=deepcopy(value);projected=presentation_prompt_context(value,3)
    doc=projected['documents'][0]
    assert doc['event_date_basis']=='issuer_announcement_date_time_and_PDF_cover_match'
    assert doc['event_time']=='14:00'and doc['content_period']=='2026Q2'
    assert doc['event_status']=='announced_past_start_not_independently_occurrence_verified'
    assert projected['transcript_available']is False and value==before


@pytest.mark.parametrize('warm',[False,True])
def test_real_pdf_timeout_stops_public_fallback(harness,monkeypatch,warm):
    from data_fetch.market_sources import psc_conference as psc
    from data_fetch import earnings_call_fetcher as fetcher
    from source_pdf_reader import SourcePdfError
    from search_provider_runtime import SourceResponseError
    if warm:
        assert psc.fetch_psc_context('2855.TW')['documents']
    harness[1].clear()
    fallbacks=[]
    def fallback(*a,**k):
        fallbacks.append(1)
        return {'ticker':'2855.TW','source':'MOPS investor conference','date':'2026-08-26'}
    def timeout(*a,**k):raise SourcePdfError('timeout')
    monkeypatch.setattr(psc,'extract_pdf_pages',timeout)
    monkeypatch.setattr(fetcher,'_fetch_official_index_context',fallback)
    with pytest.raises(SourceResponseError)as exc:fetcher.fetch_free_earnings_call_context('2855.TW')
    assert exc.value.error_kind=='timeout' and not fallbacks


@pytest.mark.parametrize('late_stage',['reader','comparison','handoff'])
def test_warm_consumer_cannot_deliver_after_common_deadline(harness,monkeypatch,late_stage):
    from types import SimpleNamespace
    from data_fetch.market_sources import psc_conference as psc
    from search_provider_runtime import SourceResponseError
    assert psc.fetch_psc_context('2855.TW')['documents']
    native=psc.extract_pdf_pages(harness[0][PDF]);clock=[100.]
    monkeypatch.setattr(psc,'time',SimpleNamespace(time=lambda:NOW,monotonic=lambda:clock[0]))
    if late_stage=='reader':
        def late(*a,**k):clock[0]+=21.;return deepcopy(native)
        monkeypatch.setattr(psc,'extract_pdf_pages',late)
    elif late_stage=='comparison':
        original=psc._context
        def late(*a,**k):value=original(*a,**k);clock[0]+=21.;return value
        monkeypatch.setattr(psc,'_context',late)
    else:
        def late(value):clock[0]+=21.;return deepcopy(value)
        monkeypatch.setattr(psc,'deepcopy',late)
    harness[1].clear()
    with pytest.raises(SourceResponseError)as exc:psc.fetch_psc_context('2855.TW')
    assert exc.value.error_kind=='timeout' and not harness[1]


def test_source_only_reader_timeout_returns_502_and_preserves_original(harness,monkeypatch):
    from types import SimpleNamespace
    from data_fetch.market_sources import psc_conference as psc
    from report_source_refresh import fetch_report_source_data
    from source_pdf_reader import SourcePdfError
    packet=psc.fetch_psc_context('2855.TW')
    before={'ticker':'2855.TW','data':{'ticker':'2855.TW','quote_type':'EQUITY','company_name':'統一證',
            'current_price':29.,'earnings_call':{'ticker':'2855','date':'2026-08-26','source':'MOPS investor conference'}},
            'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-3600,'fetch_id':'old'}],
            'analysis_evidence':{'status':'unknown'},'final_audit':{'status':'warning'}}
    held=deepcopy(before)
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):
            return SimpleNamespace(data={'ticker':'2855.TW','earnings_call':packet},source_audit=[
                {'source':'earnings_call','provider':psc.PROVIDER,'status':'success','fetch_id':'isolated-current'}])
    def timeout(*a,**k):raise SourcePdfError('timeout')
    monkeypatch.setattr(psc,'extract_pdf_pages',timeout)
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(before,'earnings_call',Service()))
    assert exc.value.status_code==502 and before==held


def test_failed_public_PSC_parent_is_not_another_acquisition(harness,monkeypatch):
    from data_fetch.market_sources import psc_conference as psc
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from source_pdf_reader import SourcePdfError
    from provider_acquisition import observation_kind,project_acquisition_events
    import search_provider_runtime
    import json
    native=[]
    monkeypatch.setattr(search_provider_runtime,'record_source_audit_entries',lambda entries:native.extend(deepcopy(entries)))
    monkeypatch.setattr(psc,'record_observation',search_provider_runtime.record_observation)
    def timeout(*a,**k):raise SourcePdfError('timeout')
    monkeypatch.setattr(psc,'extract_pdf_pages',timeout)
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('2855.TW'),{'data':{'ticker':'2855.TW','quote_type':'EQUITY','company_name':'統一證'}})
    assert not result.value and len(native)==len(harness[1])==4
    def row(a):return {'source':a['source'],'provider':a['provider'],'status':a['status'],'record_count':a.get('record_count',0),
                       'message':a.get('message',''),'details':a,'details_json':json.dumps(a),'created_at':NOW}
    events=[row(a)for a in native]+[row(result.audit)]
    projected=project_acquisition_events(events,window='last_24h',now=NOW)['sources'][0]
    assert observation_kind(events[-1])=='aggregate_count' and result.audit['http_request_sent']is False
    assert projected['http_attempt_count']==projected['fetch_attempts']==4
    assert projected['fetched_count']==3 and projected['failed_count']==1
