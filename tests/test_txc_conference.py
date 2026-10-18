"""Exact complete originals, native symbols, and truthful linked-event metadata."""
from pathlib import Path
from datetime import datetime,timezone
from hashlib import sha256
from copy import deepcopy
from contextlib import contextmanager
import gzip,time,asyncio
import pytest
from fastapi import HTTPException
from data_fetch.market_sources import txc_conference as txc
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError

F=Path(__file__).parent/'fixtures/source_acquisition'
NOW=datetime(2026,10,12,4,tzinfo=timezone.utc).timestamp()
def raw(name):return gzip.decompress((F/name).read_bytes())

@pytest.fixture
def harness(monkeypatch):
    bodies={txc.ROSTER_URL:raw('nanya2408_complete_roster_20261011.json.gz'),txc.INDEX_URL:raw('txc3042_conference_index_20261012.html.gz'),'https://www.txccorp.com/download/219/':raw('txc3042_conference219_complete_20260910.pdf.gz')}
    calls=[];observations=[]
    monkeypatch.setattr(time,'time',lambda:NOW)
    def master():
        body=bodies[txc.ROSTER_URL]
        return body,{'fetched_at_epoch':NOW-3600,'http_status_observed':False,'cache_source':'official-company-roster:v2:.TW','source_payload_sha256':sha256(body).hexdigest(),'source_payload_bytes':len(body)}
    monkeypatch.setattr(txc,'read_cached_listed_roster_bytes',master)
    def download(url,**kwargs):
        calls.append(url);kwargs['diagnostics'].update(http_request_sent=True,http_status=200,response_complete=True);return bodies[url]
    monkeypatch.setattr(txc,'download',download)
    monkeypatch.setattr(txc,'cooldown_state',lambda key:None)
    monkeypatch.setattr(txc,'record_observation',lambda *a,**k:observations.append(k))
    @contextmanager
    def lease(*a,**k):yield lambda:True
    monkeypatch.setattr(txc,'endpoint_admission',lease)
    return bodies,calls,observations

def test_public_free_call_path_recovers_full_issuer_original_without_unread_index_fallback(harness,monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    monkeypatch.setattr(fetcher,'_fetch_official_index_context',lambda *a,**k:{'ticker':'3042.TW','source':'MOPS investor conference','date':'2026-09-10'})
    details={};value=fetcher.fetch_free_earnings_call_context('3042.TW',diagnostics=details)
    assert value.get('documents') and value['documents'][0]['page_count']==15
    assert value['source']=='TXC official conference presentation' and details['txc_originals_verified']is True

def test_full_originals_have_complete_native_text_but_unverified_cover_date_and_no_transcript(harness):
    bodies,calls,observations=harness;result=txc._fetch();value=result['context'];doc=value['documents'][0]
    assert calls==[txc.INDEX_URL,'https://www.txccorp.com/download/219/']
    assert [o['outcome']for o in observations]==['results','results']
    assert doc['page_count']==len(doc['pages'])==15 and doc['garbled_pages']==[] and doc['native_text_coverage']=='complete'
    assert doc['event_date']=='2026-09-10' and doc['event_date_basis']=='issuer_index_linked_date_not_PDF_cover_confirmation'
    assert doc['published_at']is doc['material_file_date']is doc['content_period']is None
    assert doc['coverage_status']=='partial' and doc['full_content_coverage_verified']is False and value['transcript_available']is False
    assert value['summary']==value['transcript_excerpt']=='' and txc.verify_context(value,'3042.TW')
    assert value['txc_conference_receipt']['identity']['http_status']is None

@pytest.mark.parametrize('change',['text','event','source','URL','receipt','hash','bool_epoch','future_epoch','expired_master','fake_native_master','fake_transcript','extra'])
def test_saved_context_cannot_override_full_originals_or_assertions(harness,change):
    value=txc._fetch()['context'];proof=value['txc_conference_receipt']
    if change=='text':value['documents'][0]['pages'][0]['text']+='invented'
    elif change=='event':value['documents'][0]['event_date']='2026-09-11'
    elif change=='source':value['documents'][0]['source']='other'
    elif change=='URL':value['documents'][0]['url']='https://www.txccorp.com/download/214/'
    elif change=='receipt':value.pop('txc_conference_receipt')
    elif change=='hash':proof['pdf']['raw_response_sha256']='0'*64
    elif change=='bool_epoch':proof['pdf']['retrieved_at']=True
    elif change=='future_epoch':proof['pdf']['retrieved_at']=NOW+1
    elif change=='expired_master':proof['identity']['retrieved_at']=NOW-86401
    elif change=='fake_native_master':proof['identity']['http_status']=200
    elif change=='fake_transcript':value['transcript_available']=True
    else:value['invented_transcript']='unverified'
    assert not txc.verify_context(value,'3042.TW')
    assert txc.is_marked(value)

def test_wrong_master_fails_before_network(harness):
    bodies,calls,observations=harness;bodies[txc.ROSTER_URL]=bodies[txc.ROSTER_URL].replace('台灣晶技股份有限公司'.encode(),'其他晶技股份有限公司'.encode())
    with pytest.raises(SourceResponseError):txc._fetch()
    assert not calls and not observations

def test_current_index_filters_same_day_unknown_start_and_future_events(harness):
    bodies,_,_=harness;original=bodies[txc.INDEX_URL]
    current=original.replace(b'10/09/2026',b'12/10/2026')
    assert txc.select_index(current)['event_date']=='2026-08-19'
    future=original.replace(b'10/09/2026',b'20/12/2026')
    assert txc.select_index(future)['event_date']=='2026-08-19'

def test_warm_cache_replays_original_times_without_HTTP_or_native_observations(harness):
    _,calls,observations=harness;details={};value=txc.fetch_txc_context('3042.TW',diagnostics=details);calls.clear();observations.clear();warm={}
    assert txc.fetch_txc_context('3042.TW',diagnostics=warm)==value
    assert not calls and not observations and warm['cache_hit']is True and warm['http_request_count']==0 and warm['http_request_sent']is False
    assert warm['fetched_at_epoch']==details['fetched_at_epoch']==NOW

@pytest.mark.parametrize('field',['instrument_type','quote_type','quoteType'])
def test_source_only_conflicting_instrument_stops_before_any_acquisition(harness,field):
    from report_source_refresh import fetch_report_source_data
    data={'ticker':'3042.TW','instrument_type':'EQUITY',field:'ETF'};old={'ticker':'3042.TW','data':data,'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-100}]};calls=[]
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):calls.append(1);raise AssertionError('invalid context must stop before acquisition')
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(old,'earnings_call',Service()))
    assert exc.value.status_code==400 and not calls

@pytest.mark.parametrize('kind',['lease_lost','timeout','single_flight_busy','guard_storage_unavailable'])
def test_terminal_source_guard_failure_cannot_start_a_second_fallback(harness,monkeypatch,kind):
    from data_fetch import earnings_call_fetcher as fetcher
    def fail(*a,**k):raise SourceResponseError(kind)
    monkeypatch.setattr(txc,'fetch_txc_context',fail)
    monkeypatch.setattr(fetcher,'_fetch_official_index_context',lambda *a,**k:pytest.fail('no second workflow'))
    with pytest.raises(SourceResponseError)as exc:fetcher.fetch_free_earnings_call_context('3042.TW')
    assert exc.value.error_kind==kind

@pytest.mark.parametrize('warm',[False,True])
def test_child_reader_timeout_cannot_start_another_workflow(harness,monkeypatch,warm):
    from data_fetch import earnings_call_fetcher as fetcher
    _,calls,observations=harness
    if warm:
        assert txc.fetch_txc_context('3042.TW')['documents']
        calls.clear();observations.clear()
    def timed_out(*a,**k):raise SourcePdfError('timeout')
    monkeypatch.setattr(txc,'extract_pdf_pages',timed_out)
    monkeypatch.setattr(fetcher,'_fetch_official_index_context',lambda *a,**k:pytest.fail('no workflow after reader timeout'))
    with pytest.raises(SourceResponseError)as exc:fetcher.fetch_free_earnings_call_context('3042.TW')
    assert exc.value.error_kind=='timeout'
    assert len(calls)==(0 if warm else 2)
    if warm:assert not observations
    else:assert observations[-1]['details']['error_kind']=='timeout'

def test_source_only_reader_verification_timeout_keeps_snapshot(harness,monkeypatch):
    from types import SimpleNamespace
    from report_source_refresh import fetch_report_source_data
    value=txc._fetch()['context']
    old={'ticker':'3042.TW','data':{'ticker':'3042.TW','instrument_type':'EQUITY'},'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-100}]};before=deepcopy(old)
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):return SimpleNamespace(data={'ticker':'3042.TW','earnings_call':value},source_audit=[{'source':'earnings_call','provider':txc.PROVIDER,'status':'success'}])
    def timed_out(*a,**k):raise SourcePdfError('timeout')
    monkeypatch.setattr(txc,'extract_pdf_pages',timed_out)
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(old,'earnings_call',Service()))
    assert exc.value.status_code==502 and old==before

@pytest.mark.parametrize('strip_all_markers',[False,True])
def test_original_damage_is_rejected_by_API_even_when_record_markers_are_removed(harness,strip_all_markers):
    from types import SimpleNamespace
    from report_source_refresh import fetch_report_source_data
    value=txc._fetch()['context'];value['documents'][0]['pages'][0]['text']='invented'
    value.pop('txc_conference_receipt')
    if strip_all_markers:
        value['source']='generic';value['source_url']='https://example.com';value['materials']=[]
        value['documents'][0]['source']='generic';value['documents'][0]['url']='https://example.com'
    old={'ticker':'3042.TW','data':{'ticker':'3042.TW','instrument_type':'EQUITY'},'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-100}]};before=deepcopy(old)
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):return SimpleNamespace(data={'ticker':'3042.TW','earnings_call':value},source_audit=[{'source':'earnings_call','provider':txc.PROVIDER,'status':'success','fetch_id':'test'}])
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(old,'earnings_call',Service()))
    assert exc.value.status_code==502 and old==before

def test_parser_exceeding_original_shared_deadline_cannot_publish_or_reset_source(harness,monkeypatch):
    _,calls,_=harness;clock=[0.];original=txc._native_pdf
    monkeypatch.setattr(txc.time,'monotonic',lambda:clock[0])
    def late(*a):
        value=original(*a);clock[0]=21.;return value
    monkeypatch.setattr(txc,'_native_pdf',late)
    # The native reader uses the real parent's timeout; this check advances
    # only the caller's completed-parse deadline boundary.
    monkeypatch.setattr(txc,'extract_pdf_pages',lambda *a,**k:{'pages':[{'page_number':1,'text':'台灣晶技股份有限公司 法人說明會 ©2026台灣晶技股份有限公司'}],'coverage_status':'complete'})
    with pytest.raises(SourceResponseError)as exc:txc._fetch(deadline=20.)
    assert exc.value.error_kind=='timeout' and len(calls)==2

def test_internal_original_receipts_are_not_sent_into_role_prompt(harness):
    from prompt_evidence import prompt_evidence_copy
    value=txc._fetch()['context'];view=prompt_evidence_copy({'earnings_call':value})
    assert 'raw_response_path'not in str(view) and 'txc_conference_receipt'not in str(view)

def test_role_projection_keeps_the_unknown_cover_date_and_index_date_basis(harness):
    from conference_presentation_prompt import presentation_prompt_context
    value=txc._fetch()['context'];view=presentation_prompt_context(value,3)
    doc=view['documents'][0]
    assert doc['event_date_basis']=='issuer_index_linked_date_not_PDF_cover_confirmation'
    assert doc['material_file_date']is doc['content_period']is None
    assert view['transcript_available']is False and doc['full_content_coverage_verified']is False
