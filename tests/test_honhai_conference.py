"""Recover only a matching declared call from complete first-party originals."""
from copy import deepcopy
from data_fetch import earnings_call_fetcher as earnings
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
from contextlib import contextmanager
from types import SimpleNamespace
import gzip,time,asyncio
import pytest
from fastapi import HTTPException
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError
from data_fetch.market_sources import honhai_conference as hh

F=Path(__file__).parent/'fixtures/source_acquisition'
NOW=datetime(2026,10,12,5,tzinfo=timezone.utc).timestamp()

@pytest.fixture
def harness(monkeypatch):
    bodies={hh.ROSTER_URL:gzip.decompress((F/'nanya2408_complete_roster_20261011.json.gz').read_bytes()),hh.PAGE_URL:gzip.decompress((F/'honhai2317_event106_complete_20261012.html.gz').read_bytes()),hh.TRANSCRIPT_URL:gzip.decompress((F/'honhai2317_transcript_2q26_complete_20260812.pdf.gz').read_bytes())}
    calls=[];observations=[];monkeypatch.setattr(time,'time',lambda:NOW)
    def master():
        raw=bodies[hh.ROSTER_URL]
        return raw,{'fetched_at_epoch':NOW-3600,'http_status_observed':False,'cache_source':'official-company-roster:v2:.TW','source_payload_sha256':sha256(raw).hexdigest(),'source_payload_bytes':len(raw)}
    monkeypatch.setattr(hh,'read_cached_listed_roster_bytes',master)
    def download(url,**kw):calls.append(url);kw['diagnostics'].update(http_request_sent=True,http_status=200,response_complete=True);return bodies[url]
    monkeypatch.setattr(hh,'download',download);monkeypatch.setattr(hh,'cooldown_state',lambda k:{})
    monkeypatch.setattr(hh,'record_observation',lambda *a,**k:observations.append(k))
    @contextmanager
    def lease(*a,**k):yield lambda:True
    monkeypatch.setattr(hh,'endpoint_admission',lease)
    return bodies,calls,observations

def test_public_path_recovers_matching_official_transcript_body(harness,monkeypatch):
    old={'ticker':'2317.TW','date':'2026-08-12','title':'2026年第二季法人說明會','source':'TWSE WebPro conference metadata','documents':[]}
    monkeypatch.setattr(earnings,'_fetch_official_index_context',lambda *a,**k:deepcopy(old))
    value=earnings.fetch_free_earnings_call_context('2317.TW')
    assert value.get('documents') and value['documents'][0]['page_count']==23
    assert value['transcript_available']is True

def test_complete_native_original_and_declared_dates_are_separate(harness):
    _,calls,observations=harness;value=hh._fetch()['context'];doc=value['documents'][0]
    assert calls==[hh.PAGE_URL,hh.TRANSCRIPT_URL] and len(observations)==2
    assert doc['page_count']==len(doc['pages'])==23 and doc['garbled_pages']==[]
    assert doc['document_kind']=='transcript' and doc['event_date']=='2026-08-12' and doc['event_time_Taipei']=='15:00'
    assert doc['event_date_basis']=='official_transcript_cover_declared_date_time' and doc['source_page_displayed_date']=='2026-07-29'
    assert doc['content_period']=='2026 Q2' and doc['published_at']is doc['material_file_date']is None
    assert doc['transcript_accuracy_independently_verified']is False and doc['full_content_coverage_verified']is False and doc['coverage_status']=='partial'
    assert value['summary']==value['transcript_excerpt']=='' and hh.verify_context(value,'2317.TW')
    assert value['honhai_conference_receipt']['identity']['http_status']is None

@pytest.mark.parametrize('change',['text','event','date_basis','period','source','URL','receipt','hash','bool_epoch','future_epoch','expired_master','fake_HTTP_master','claimed_accuracy','extra'])
def test_saved_context_cannot_override_complete_original_or_date_claims(harness,change):
    v=hh._fetch()['context'];proof=v['honhai_conference_receipt'];d=v['documents'][0]
    if change=='text':d['pages'][0]['text']+='invented'
    elif change=='event':d['event_date']='2026-08-18'
    elif change=='date_basis':d['published_at']='2026-07-29'
    elif change=='period':d['content_period']='2026 Q3'
    elif change=='source':d['source']='other'
    elif change=='URL':d['url']=hh.PAGE_URL
    elif change=='receipt':v.pop('honhai_conference_receipt')
    elif change=='hash':proof['pdf']['raw_response_sha256']='0'*64
    elif change=='bool_epoch':proof['pdf']['retrieved_at']=True
    elif change=='future_epoch':proof['pdf']['retrieved_at']=NOW+1
    elif change=='expired_master':proof['identity']['retrieved_at']=NOW-86401
    elif change=='fake_HTTP_master':proof['identity']['http_status']=200
    elif change=='claimed_accuracy':d['transcript_accuracy_independently_verified']=True
    else:v['unverified']='extra'
    assert not hh.verify_context(v,'2317.TW')

def test_wrong_master_and_different_call_cannot_start_native_acquisition(harness,monkeypatch):
    bodies,calls,_=harness;bodies[hh.ROSTER_URL]=bodies[hh.ROSTER_URL].replace('鴻海精密工業股份有限公司'.encode(),'其他股份有限公司'.encode())
    with pytest.raises(SourceResponseError):hh._fetch()
    assert not calls
    original={'ticker':'2317.TW','date':'2026-11-12','source':'MOPS investor conference'}
    assert hh.enrich_honhai_context('2317.TW',original)==original and not calls

def test_warm_cache_replays_original_epoch_without_HTTP_observations(harness):
    _,calls,observations=harness;d={};v=hh.fetch_honhai_context('2317.TW',expected_event_date=hh.EVENT_DATE,diagnostics=d);calls.clear();observations.clear();warm={}
    assert hh.fetch_honhai_context('2317.TW',expected_event_date=hh.EVENT_DATE,diagnostics=warm)==v
    assert not calls and not observations and warm['http_request_sent']is False and warm['http_request_count']==0
    assert warm['fetched_at_epoch']==d['fetched_at_epoch']==NOW

def test_cold_final_replay_timeout_keeps_actual_native_http_audit(harness,monkeypatch):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    real=hh.extract_pdf_pages;reads=[]
    def last_timeout(*a,**k):
        reads.append(1)
        if len(reads)==3:raise SourcePdfError('timeout')
        return real(*a,**k)
    monkeypatch.setattr(hh,'extract_pdf_pages',last_timeout)
    monkeypatch.setattr(earnings,'_fetch_official_index_context',lambda *a,**k:pytest.fail('no second metadata workflow'))
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('2317.TW'),{'source_only_recovery':True,'data':{'ticker':'2317.TW','instrument_type':'EQUITY','earnings_call':{'ticker':'2317','date':hh.EVENT_DATE}}})
    assert len(reads)==3 and harness[1]==[hh.PAGE_URL,hh.TRANSCRIPT_URL] and len(harness[2])==2
    assert result.audit['error_kind']=='timeout' and result.audit['http_request_sent']is False
    assert result.audit['http_request_count']==2 and result.audit['source_http_request_sent']is True
    assert len(result.audit['component_statuses'])==2

@pytest.mark.parametrize('warm',[False,True])
def test_failed_consumer_replay_stays_error_without_successful_cache_flags(harness,monkeypatch,warm):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    if warm:
        hh.fetch_honhai_context('2317.TW',expected_event_date=hh.EVENT_DATE)
        harness[1].clear();harness[2].clear()
    real=hh.extract_pdf_pages;reads=[]
    def timeout(*a,**k):
        reads.append(1)
        if warm or len(reads)==3:raise SourcePdfError('timeout')
        return real(*a,**k)
    monkeypatch.setattr(hh,'extract_pdf_pages',timeout)
    monkeypatch.setattr(earnings,'_fetch_official_index_context',lambda *a,**k:pytest.fail('no second metadata workflow'))
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('2317.TW'),{'source_only_recovery':True,'data':{'ticker':'2317.TW','instrument_type':'EQUITY','earnings_call':{'ticker':'2317','date':hh.EVENT_DATE}}})
    assert result.value=={} and result.status==result.audit['status']=='error'
    assert result.audit['error_kind']=='timeout' and result.audit['honhai_originals_verified']is False
    assert result.audit['http_request_sent']is False and result.audit['http_request_count']==(0 if warm else 2)
    assert result.audit['source_http_request_sent']is(not warm) and len(harness[1])==(0 if warm else 2)
    assert 'coverage_status'not in result.audit and result.audit.get('record_count',0)==0

@pytest.mark.parametrize('delay_stage',['reader','cover','equality','handoff'])
def test_warm_replay_rechecks_same_deadline_after_completed_work(harness,monkeypatch,delay_stage):
    hh.fetch_honhai_context('2317.TW',expected_event_date=hh.EVENT_DATE)
    harness[1].clear();harness[2].clear();clock=[1000.]
    monkeypatch.setattr(hh,'time',SimpleNamespace(time=lambda:NOW,monotonic=lambda:clock[0]))
    if delay_stage=='reader':
        real=hh.extract_pdf_pages
        def delayed(*a,**k):
            result=real(*a,**k);clock[0]=1021.;return result
        monkeypatch.setattr(hh,'extract_pdf_pages',delayed)
    elif delay_stage=='cover':
        real=hh.re
        def delayed(*a,**k):
            result=real.sub(*a,**k);clock[0]=1021.;return result
        monkeypatch.setattr(hh,'re',SimpleNamespace(sub=delayed))
    elif delay_stage=='equality':
        real=hh._context
        class DelayedEqualDict(dict):
            def __eq__(self,other):
                result=super().__eq__(other);clock[0]=1021.;return result
        def delayed(*a,**k):
            result=real(*a,**k);result['honhai_conference_receipt']=DelayedEqualDict(result['honhai_conference_receipt']);return result
        monkeypatch.setattr(hh,'_context',delayed)
    else:
        real=hh.deepcopy
        def delayed(*a,**k):
            result=real(*a,**k);clock[0]=1021.;return result
        monkeypatch.setattr(hh,'deepcopy',delayed)
    with pytest.raises(SourceResponseError)as exc:
        hh.fetch_honhai_context('2317.TW',expected_event_date=hh.EVENT_DATE,deadline=1020.)
    assert exc.value.error_kind=='timeout' and harness[1]==harness[2]==[]
    assert exc.value.diagnostic['http_request_sent']is False and exc.value.diagnostic['http_request_count']==0

@pytest.mark.parametrize('warm',[False,True])
def test_actual_reader_timeout_is_terminal_without_metadata_relaunch(harness,monkeypatch,warm):
    _,calls,observations=harness
    if warm:assert hh.fetch_honhai_context('2317.TW',expected_event_date=hh.EVENT_DATE);calls.clear();observations.clear()
    def timeout(*a,**k):raise SourcePdfError('timeout')
    monkeypatch.setattr(hh,'extract_pdf_pages',timeout)
    monkeypatch.setattr(earnings,'_fetch_official_index_context',lambda *a,**k:pytest.fail('source-only already has declared call'))
    context={'ticker':'2317.TW','instrument_type':'EQUITY','earnings_call':{'ticker':'2317.TW','date':hh.EVENT_DATE}}
    with pytest.raises(SourceResponseError)as exc:earnings.fetch_free_earnings_call_context('2317.TW',source_context=context)
    assert exc.value.error_kind=='timeout' and len(calls)==(0 if warm else 2)

@pytest.mark.parametrize('field',['instrument_type','quote_type','quoteType','company_name'])
def test_source_only_wrong_instrument_or_unqualified_event_stops_before_provider(harness,field):
    from report_source_refresh import fetch_report_source_data
    data={'ticker':'2317.TW','instrument_type':'EQUITY','earnings_call':{'date':hh.EVENT_DATE}}
    if field=='company_name':data[field]='其他公司'
    else:data[field]='ETF'
    old={'ticker':'2317.TW','data':data,'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-100}]};called=[]
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):called.append(1);pytest.fail('context must stop before provider')
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(old,'earnings_call',Service()))
    assert exc.value.status_code==400 and not called

def test_other_call_dates_keep_existing_source_refresh_and_provider_context(harness):
    from types import SimpleNamespace
    from report_source_refresh import fetch_report_source_data
    old={'ticker':'2317.TW','data':{'ticker':'2317.TW','instrument_type':'EQUITY','earnings_call':{'date':'2026-03-16'}},'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-100}]};called=[]
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):
            called.append(k)
            return SimpleNamespace(data={'ticker':'2317.TW','earnings_call':{'ticker':'2317.TW','date':'2026-05-14','source':'MOPS investor conference'}},source_audit=[{'source':'earnings_call','provider':'MOPS investor conference','status':'success','fetched_at_epoch':NOW,'fetch_id':'legacy-nonmatching-test','record_count':1}])
    data=asyncio.run(fetch_report_source_data(old,'earnings_call',Service()))
    assert called==[{}] and data['earnings_call']['date']=='2026-05-14'

def test_current_saved_bare_call_ticker_matches_explicit_TW_equity_root(harness,monkeypatch):
    data={'ticker':'2317.TW','company_name':'鴻海 / Hon Hai Precision Industry Co., Ltd.','instrument_type':'EQUITY','earnings_call':{'ticker':'2317','date':hh.EVENT_DATE,'source':'TWSE WebPro conference metadata'}}
    assert hh.validate_context(data,'2317.TW')
    monkeypatch.setattr(earnings,'_fetch_official_index_context',lambda *a,**k:pytest.fail('matching source-only metadata must not be repeated'))
    value=earnings.fetch_free_earnings_call_context('2317.TW',source_context=data)
    assert value['ticker']=='2317.TW'and value['documents'][0]['page_count']==23

@pytest.mark.parametrize('strip_markers',[False,True])
def test_source_only_unverified_or_marker_removed_body_is_not_admitted(harness,strip_markers):
    from types import SimpleNamespace
    from report_source_refresh import fetch_report_source_data
    value=hh._fetch()['context'];value['documents'][0]['pages'][0]['text']='invented';value.pop('honhai_conference_receipt')
    if strip_markers:value['source']='generic';value['source_url']='https://example.com';value['materials']=[];value['documents'][0]['source']='generic';value['documents'][0]['url']='https://example.com'
    old={'ticker':'2317.TW','data':{'ticker':'2317.TW','instrument_type':'EQUITY','earnings_call':{'date':hh.EVENT_DATE}},'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-100}]};before=deepcopy(old)
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):return SimpleNamespace(data={'ticker':'2317.TW','earnings_call':value},source_audit=[{'source':'earnings_call','provider':hh.PROVIDER,'status':'success'}])
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(old,'earnings_call',Service()))
    assert exc.value.status_code==502 and old==before

def test_source_only_metadata_fallback_without_native_body_is_not_success(harness):
    from types import SimpleNamespace
    from report_source_refresh import fetch_report_source_data
    old={'ticker':'2317.TW','data':{'ticker':'2317.TW','instrument_type':'EQUITY','earnings_call':{'date':hh.EVENT_DATE}},'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-100}]}
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):return SimpleNamespace(data={'ticker':'2317.TW','earnings_call':{'ticker':'2317.TW','date':hh.EVENT_DATE}},source_audit=[])
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(old,'earnings_call',Service()))
    assert exc.value.status_code==502

def test_source_only_verification_reader_timeout_keeps_snapshot(harness,monkeypatch):
    from types import SimpleNamespace
    from report_source_refresh import fetch_report_source_data
    value=hh._fetch()['context'];old={'ticker':'2317.TW','data':{'ticker':'2317.TW','instrument_type':'EQUITY','earnings_call':{'date':hh.EVENT_DATE}},'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-100}]};before=deepcopy(old)
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):return SimpleNamespace(data={'ticker':'2317.TW','earnings_call':value},source_audit=[])
    def timeout(*a,**k):raise SourcePdfError('timeout')
    monkeypatch.setattr(hh,'extract_pdf_pages',timeout)
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(old,'earnings_call',Service()))
    assert exc.value.status_code==502 and old==before
