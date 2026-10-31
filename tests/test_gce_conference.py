"""GCE exact originals, no-store acquisition and fail-closed saved replay."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import base64
import json
import time
import pytest

from data_fetch.market_sources.gce_conference_transport import MASTER_URL, INDEX_URL, PDF_URL

ROOT = Path(__file__).parents[1]
D = ROOT/'docs/evidence/source-acquisition/20261014/freshness-and-free-source-next/research'
MASTER = ROOT/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
NOW = 1791948208.0


@pytest.fixture
def harness(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources.gce_conference_transport import ConferenceHttp
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    bodies = {MASTER_URL:MASTER.read_bytes(), INDEX_URL:(D/'gce-index.body').read_bytes(),
              PDF_URL:(D/'gce-20260828-en.body').read_bytes()}
    calls = []
    def download(self, url, diagnostic):
        raw=bodies[url]; calls.append(url); self.http_request_count+=1
        metadata={'http_status':200,'effective_url':url,'num_redirects':0,'size_download':len(raw),
                  'content_type':'text/csv' if url==MASTER_URL else 'text/html' if url==INDEX_URL else 'application/pdf',
                  'content_length':len(raw),'method':'GET','proxy_used':0,'cache_control':'no-cache'}
        if url == MASTER_URL:
            from data_fetch.market_sources import official_issuer_master
            metadata = official_issuer_master.master_metadata(metadata,raw,{})
        diagnostic.update(http_request_sent=True,http_status=200,response_metadata=metadata)
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),
                'request_method':'GET','request_body':None,'response_metadata':metadata}
    monkeypatch.setattr(ConferenceHttp,'download_original',download)
    yield bodies,calls
    cache_store.reset_cache_store_for_tests()


def valid_data():
    return {'ticker':'2368.TW','company_name':'金像電 / Gold Circuit Electronics Ltd.',
        'raw_company_name':'Gold Circuit Electronics Ltd.','quote_type':'EQUITY','instrument_type':'EQUITY',
        'company_identity':{'ticker':'2368.TW','stock_id':'2368','official_name':'金像電','instrument_type':'EQUITY',
            'allowed_aliases':['金像電','Gold Circuit Electronics Ltd.','GOLD CIRCUIT ELECTRONICS CO','2368.TW','2368'],
            'english_names':['Gold Circuit Electronics Ltd.','GOLD CIRCUIT ELECTRONICS CO'],'forbidden_aliases':[]}}


def test_public_original_is_complete_native_and_partial_visual(harness):
    from data_fetch.market_sources import gce_conference as source
    assert source.validate_context(valid_data(),'2368.TW')
    d={};value=source.fetch_gce_context('2368.TW',diagnostics=d)
    doc=value['documents'][0]
    assert doc['page_count']==len(doc['pages'])==11
    assert doc['native_text_coverage']=='complete' and doc['coverage_status']=='partial'
    assert doc['full_content_coverage_verified']is False and doc['q_and_a_transcript_available']is False
    assert doc['content_periods'][0]=='2026H1' and doc['content_period']==''
    assert doc['event_date']=='2026-08-28' and doc['published_at']is None and doc['event_time']is None
    assert d['http_request_count']==3
    assert d['gce_originals_verified']is True and d['cache_hit']is False
    assert source.verify_context(value,'2368.TW',max_age=1800)
    assert harness[1]==[MASTER_URL,INDEX_URL,PDF_URL]


def test_shared_private_master_keeps_new_pdf_as_one_fresh_body_acquisition(harness,monkeypatch):
    from data_fetch.market_sources import gce_conference as source
    from data_fetch.market_sources.gce_conference_transport import ConferenceHttp
    original=ConferenceHttp.download_original
    def private_master(self,url,diagnostic):
        value=original(self,url,diagnostic)
        if url==MASTER_URL:value['response_metadata']['cache_control']='private'
        return value
    monkeypatch.setattr(ConferenceHttp,'download_original',private_master)
    first=source.fetch_gce_context('2368.TW')
    monkeypatch.setattr(time,'time',lambda:NOW+10)
    diagnostics={};second=source.fetch_gce_context('2368.TW',force_refresh=True,diagnostics=diagnostics)
    assert harness[1]==[MASTER_URL,INDEX_URL,PDF_URL,INDEX_URL,PDF_URL]
    proof=second['gce_conference_receipt']
    assert proof['identity']['cache_hit'] is True and proof['identity']['retrieved_at']==NOW
    assert proof['pdf']['cache_hit'] is False and proof['pdf']['retrieved_at']==NOW+10
    assert diagnostics['http_request_count']==2 and diagnostics['cache_hit'] is False
    assert diagnostics['fetched_at_epoch']==NOW+10 and diagnostics['gce_originals_verified'] is True
    assert source.verify_context(first,'2368.TW',max_age=1800)
    assert source.verify_context(second,'2368.TW',max_age=1800)


def test_verify_final_expiry_does_not_add_unbudgeted_storage_after_last_deadline_check(harness,monkeypatch):
    import inspect
    from types import SimpleNamespace
    from data_fetch.market_sources import gce_conference as source, official_issuer_master as master
    from data_fetch.market_sources.gce_conference_transport import ConferenceHttp
    original=ConferenceHttp.download_original
    def private(self,url,diagnostic):
        value=original(self,url,diagnostic)
        if url==MASTER_URL:value['response_metadata']['cache_control']='private'
        return value
    monkeypatch.setattr(ConferenceHttp,'download_original',private)
    source.fetch_gce_context('2368.TW')
    value=source.fetch_gce_context('2368.TW')
    clock=[time.monotonic()];deadline=clock[0]+2
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=lambda:NOW))
    real=master._stored
    def slow_final_read():
        if any(frame.function=='_originals_fresh' for frame in inspect.stack()):clock[0]+=3
        return real()
    monkeypatch.setattr(master,'_stored',slow_final_read)
    assert source.verify_context(value,'2368.TW',deadline=deadline,max_age=1800)
    assert clock[0]<deadline, 'storage was added after the final caller deadline check'


@pytest.mark.parametrize('options',[{}, {'force_refresh':True}, {'use_cache':False}])
def test_no_store_does_not_reuse_old_raw_or_context(harness,monkeypatch,options):
    from data_fetch.market_sources import gce_conference as source
    import cache_store
    first=source.fetch_gce_context('2368.TW')
    monkeypatch.setattr(time,'time',lambda:NOW+10)
    second=source.fetch_gce_context('2368.TW',**options)
    assert len(harness[1])==6 and second['fetched_at_epoch']==NOW+10
    assert first['fetched_at_epoch']==NOW
    entries=cache_store.get_cache_backend()._entries
    assert all('body_b64'not in str(row) and 'documents'not in str(row) for row in entries.values())
    assert source.verify_context(first,'2368.TW',max_age=1800)


@pytest.mark.parametrize('change',['newer_without_link','newer_unknown','duplicate','future','count','master','attachment','publisher'])
def test_latest_or_identity_uncertainty_cannot_fall_back_to_old_pdf(harness,change):
    from data_fetch.market_sources import gce_conference as source
    from search_provider_runtime import SourceResponseError
    from bs4 import BeautifulSoup
    if change=='master':harness[0][MASTER_URL]=harness[0][MASTER_URL].replace(b'30955404',b'30955405')
    else:
        soup=BeautifulSoup(harness[0][INDEX_URL],'html.parser')
        rows=soup.select('table tbody tr'); first=rows[0]
        if change in {'newer_without_link','newer_unknown','future'}:
            first.select_one('td').string='115年度本公司法人說明會資料 (115.'+('12.28' if change=='future' else '09.28')+' 中文版,英文版)'
            if change=='newer_without_link':first.select_one('a').decompose()
        elif change=='duplicate':rows[1].select_one('td').string=first.select_one('td').get_text()
        elif change=='count':rows[-1].decompose()
        elif change=='attachment':first.select('a')[1]['href']='file/unknown.pdf'
        else:soup.title.string='Other issuer'
        harness[0][INDEX_URL]=str(soup).encode()
    with pytest.raises(SourceResponseError):source.fetch_gce_context('2368.TW')
    assert PDF_URL not in harness[1]


@pytest.mark.parametrize('change',['root_name','alias','ubn','quote','forbidden','foreign_suffix'])
def test_identity_does_not_borrow_good_name_to_hide_contradiction(change):
    from data_fetch.market_sources.gce_conference import validate_context
    v=valid_data()
    if change=='root_name':v['company_name']='ARES'
    elif change=='alias':v['company_identity']['english_names']={}
    elif change=='ubn':v['company_identity']['official_ubn']='00000000'
    elif change=='quote':v['quote_type']='ETF'
    elif change=='forbidden':v['company_identity']['forbidden_aliases']=['金像電']
    else:v['raw_company_name']='GCE Electric Co.,Ltd. unrelated'
    assert not validate_context(v,'2368.TW')


@pytest.mark.parametrize('change',['expiry','epoch','cache','metadata','manifest','proof_bool','digit','semantics'])
def test_saved_original_replay_rejects_retiming_and_semantic_tamper(harness,change):
    from data_fetch.market_sources import gce_conference as source
    v=source.fetch_gce_context('2368.TW'); r=v['gce_conference_receipt']['pdf']
    if change=='expiry':r['fresh_until_epoch']-=1
    elif change=='epoch':r['retrieved_at']+=1
    elif change=='cache':r['cache_hit']=True
    elif change=='metadata':r['response_metadata']['cache_control']='public'
    elif change=='manifest':r['acquisition_manifest']['raw_response_sha256']='0'*64
    elif change=='proof_bool':v['documents'][0]['gce_glyph_evidence']['raw_bytes_rewritten']=0
    elif change=='digit':v['documents'][0]['pages'][6]['text']+=' 99999'
    else:v['documents'][0]['coverage_status']='complete'
    assert source.verify_context(v,'2368.TW',max_age=1800)is False


def test_failed_http_admission_keeps_120_seconds_even_force(harness,monkeypatch):
    from data_fetch.market_sources import gce_conference as source
    from data_fetch.market_sources.gce_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    calls=[]
    def fail(self,url,diagnostic):
        self.http_request_count+=1; calls.append(url); diagnostic['http_request_sent']=True
        raise SourceResponseError('rate_limited',status_code=429)
    monkeypatch.setattr(ConferenceHttp,'download_original',fail)
    for options in ({},{'force_refresh':True},{'use_cache':False}):
        with pytest.raises(SourceResponseError):source.fetch_gce_context('2368.TW',**options)
    assert calls==[MASTER_URL]


@pytest.mark.parametrize('stage',['reader','handoff','components'])
def test_total_deadline_includes_projection_and_copy(harness,monkeypatch,stage):
    from data_fetch.market_sources import gce_conference as source
    from search_provider_runtime import SourceResponseError
    from types import SimpleNamespace
    clock=[time.monotonic()];expired=clock[0]+26
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=lambda:NOW))
    if stage=='reader':
        real=source.extract_gce_presentation_pages
        def delayed(*a,**k):v=real(*a,**k);clock[0]=expired;return v
        monkeypatch.setattr(source,'extract_gce_presentation_pages',delayed)
    else:
        real=source.deepcopy
        def delayed(v):
            out=real(v)
            if stage=='handoff'and isinstance(v,dict)and'documents'in v or stage=='components'and isinstance(v,list):clock[0]=expired
            return out
        monkeypatch.setattr(source,'deepcopy',delayed)
    with pytest.raises(SourceResponseError)as e:source.fetch_gce_context('2368.TW')
    assert e.value.error_kind=='timeout'


def test_historical_saved_replay_does_not_claim_current_acquisition(harness,monkeypatch):
    from data_fetch.market_sources import gce_conference as source
    value=source.fetch_gce_context('2368.TW')
    original=deepcopy(value)
    monkeypatch.setattr(time,'time',lambda:NOW+1801)
    assert source.verify_context(value,'2368.TW',max_age=1800)is False
    assert source.verify_context(value,'2368.TW',max_age=86400)is True
    assert value==original and len(harness[1])==3
    monkeypatch.setattr(time,'time',lambda:NOW+86400)
    assert source.verify_context(value,'2368.TW',max_age=86400)is False


def test_preplanted_success_cache_cannot_supply_gce_body(harness):
    import cache_store
    from data_fetch.market_sources import gce_conference as source
    from data_fetch.market_sources.gce_conference_transport import ConferenceHttp
    key=ConferenceHttp.raw_cache_prefix+PDF_URL
    fake={'value':{'body_b64':'YmFk','fetched_at_epoch':NOW},'fetched_at_epoch':NOW,'fresh_until_epoch':NOW+1800}
    cache_store.set_cache_json(key,fake,ttl_seconds=1800)
    value=source.fetch_gce_context('2368.TW')
    assert value['documents'][0]['page_count']==11 and len(harness[1])==3
    assert cache_store.get_cache_json(key)==fake


@pytest.mark.parametrize('advance',['budget','validation_age'])
def test_final_diagnostic_handoff_cannot_return_expired_success(harness,monkeypatch,advance):
    from types import SimpleNamespace
    from data_fetch.market_sources import gce_conference as source
    from search_provider_runtime import SourceResponseError
    mono=[time.monotonic()];epoch=[NOW]
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:mono[0],time=lambda:epoch[0]))
    class Diagnostic(dict):
        def update(self,*a,**kw):
            super().update(*a,**kw)
            if self.get('gce_originals_verified'):
                if advance=='budget':mono[0]+=26
                else:epoch[0]+=1800
    diagnostic=Diagnostic()
    with pytest.raises(SourceResponseError)as caught:source.fetch_gce_context('2368.TW',diagnostics=diagnostic)
    assert caught.value.error_kind==('timeout'if advance=='budget'else'original_expired')
    assert diagnostic['gce_originals_verified']is False
    assert all(k not in diagnostic for k in ('coverage_status','cache_hit','stale','fetched_at_epoch'))
    assert diagnostic['http_request_count']==3 and diagnostic['http_request_sent']is True
