"""Allis exact originals, no-store acquisition and fail-closed saved replay."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import base64
import json
import time
import pytest

from data_fetch.market_sources.allis_conference_transport import MASTER_URL, INDEX_URL, PDF_URL

ROOT = Path(__file__).parents[1]
D = ROOT/'docs/evidence/source-acquisition/20261014/remaining-source-candidates/conference-entry'
MASTER = ROOT/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
NOW = 1791948208.0


@pytest.fixture
def harness(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources.allis_conference_transport import ConferenceHttp
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    bodies = {MASTER_URL:MASTER.read_bytes(), INDEX_URL:(D/'native-allis-index.body').read_bytes(),
              PDF_URL:(D/'native-allis-pdf.body').read_bytes()}
    calls = []
    def download(self, url, diagnostic):
        raw=bodies[url]; calls.append(url); self.http_request_count+=1
        metadata={'http_status':200,'effective_url':url,'num_redirects':0,'size_download':len(raw),
                  'content_type':'text/csv' if url==MASTER_URL else 'text/html' if url==INDEX_URL else 'application/pdf',
                  'content_length':len(raw),'method':'GET','proxy_used':0,'cache_control':'no-store, no-cache'}
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
    saved=json.loads((D/'current-1514-gap-identity.json').read_text())['report']['identity']
    return {**deepcopy(saved),'instrument_type':'EQUITY'}


def test_public_original_is_complete_native_and_partial_visual(harness):
    from data_fetch.market_sources import allis_conference as source
    assert source.validate_context(valid_data(),'1514.TW')
    d={};value=source.fetch_allis_context('1514.TW',diagnostics=d)
    doc=value['documents'][0]
    assert doc['page_count']==len(doc['pages'])==29
    assert doc['native_text_coverage']=='complete' and doc['coverage_status']=='partial'
    assert doc['full_content_coverage_verified']is False and doc['q_and_a_transcript_available']is False
    assert doc['content_periods'][0]=='2026H1' and doc['content_period']==''
    assert doc['event_date']=='2026-08-27' and doc['published_at']is None and doc['event_time']is None
    assert d['http_request_count']==3
    assert d['allis_originals_verified']is True and d['cache_hit']is False
    assert source.verify_context(value,'1514.TW',max_age=1800)
    assert harness[1]==[MASTER_URL,INDEX_URL,PDF_URL]


@pytest.mark.parametrize('options',[{}, {'force_refresh':True}, {'use_cache':False}])
def test_no_store_does_not_reuse_old_raw_or_context(harness,monkeypatch,options):
    from data_fetch.market_sources import allis_conference as source
    import cache_store
    first=source.fetch_allis_context('1514.TW')
    monkeypatch.setattr(time,'time',lambda:NOW+10)
    second=source.fetch_allis_context('1514.TW',**options)
    assert len(harness[1])==6 and second['fetched_at_epoch']==NOW+10
    assert first['fetched_at_epoch']==NOW
    entries=cache_store.get_cache_backend()._entries
    assert all('body_b64'not in str(row) and 'documents'not in str(row) for row in entries.values())
    assert source.verify_context(first,'1514.TW',max_age=1800)


@pytest.mark.parametrize('change',['newer_without_link','newer_unknown','duplicate','future','count','master'])
def test_latest_or_identity_uncertainty_cannot_fall_back_to_old_pdf(harness,change):
    from data_fetch.market_sources import allis_conference as source
    from search_provider_runtime import SourceResponseError
    from bs4 import BeautifulSoup
    if change=='master':harness[0][MASTER_URL]=harness[0][MASTER_URL].replace(b'03213392',b'03213393')
    else:
        soup=BeautifulSoup(harness[0][INDEX_URL],'html.parser')
        first=soup.select('#wb-list > .card')[0]
        if change in {'newer_without_link','newer_unknown','future'}:
            first.select_one('.download-title').string='115年'+('12'if change=='future'else'09')+'月法說會簡報'
            if change=='newer_without_link':first.select_one('a').decompose()
        elif change=='duplicate':soup.select('#wb-list > .card')[1].select_one('.download-title').string='115年08月法說會簡報'
        else:soup.select_one('#wb-toolbar .toolbar-amount').string='第 1 到 3 筆。共 4 筆。'
        harness[0][INDEX_URL]=str(soup).encode()
    with pytest.raises(SourceResponseError):source.fetch_allis_context('1514.TW')
    assert PDF_URL not in harness[1]


@pytest.mark.parametrize('change',['root_name','alias','ubn','quote','forbidden','foreign_suffix'])
def test_identity_does_not_borrow_good_name_to_hide_contradiction(change):
    from data_fetch.market_sources.allis_conference import validate_context
    v=valid_data()
    if change=='root_name':v['company_name']='ARES'
    elif change=='alias':v['company_identity']['english_names']={}
    elif change=='ubn':v['company_identity']['official_ubn']='00000000'
    elif change=='quote':v['quote_type']='ETF'
    elif change=='forbidden':v['company_identity']['forbidden_aliases']=['亞力']
    else:v['raw_company_name']='Allis Electric Co.,Ltd. unrelated'
    assert not validate_context(v,'1514.TW')


@pytest.mark.parametrize('change',['expiry','epoch','cache','metadata','manifest','proof_bool','digit','semantics'])
def test_saved_original_replay_rejects_retiming_and_semantic_tamper(harness,change):
    from data_fetch.market_sources import allis_conference as source
    v=source.fetch_allis_context('1514.TW'); r=v['allis_conference_receipt']['pdf']
    if change=='expiry':r['fresh_until_epoch']-=1
    elif change=='epoch':r['retrieved_at']+=1
    elif change=='cache':r['cache_hit']=True
    elif change=='metadata':r['response_metadata']['cache_control']='public'
    elif change=='manifest':r['acquisition_manifest']['raw_response_sha256']='0'*64
    elif change=='proof_bool':v['documents'][0]['allis_glyph_evidence']['raw_bytes_rewritten']=0
    elif change=='digit':v['documents'][0]['pages'][17]['text']+=' 99999'
    else:v['documents'][0]['coverage_status']='complete'
    assert source.verify_context(v,'1514.TW',max_age=1800)is False


def test_failed_http_admission_keeps_120_seconds_even_force(harness,monkeypatch):
    from data_fetch.market_sources import allis_conference as source
    from data_fetch.market_sources.allis_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    calls=[]
    def fail(self,url,diagnostic):
        self.http_request_count+=1; calls.append(url); diagnostic['http_request_sent']=True
        raise SourceResponseError('rate_limited',status_code=429)
    monkeypatch.setattr(ConferenceHttp,'download_original',fail)
    for options in ({},{'force_refresh':True},{'use_cache':False}):
        with pytest.raises(SourceResponseError):source.fetch_allis_context('1514.TW',**options)
    assert calls==[MASTER_URL]


@pytest.mark.parametrize('stage',['reader','handoff','components'])
def test_total_deadline_includes_projection_and_copy(harness,monkeypatch,stage):
    from data_fetch.market_sources import allis_conference as source
    from search_provider_runtime import SourceResponseError
    from types import SimpleNamespace
    clock=[time.monotonic()];expired=clock[0]+26
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=lambda:NOW))
    if stage=='reader':
        real=source.extract_allis_presentation_pages
        def delayed(*a,**k):v=real(*a,**k);clock[0]=expired;return v
        monkeypatch.setattr(source,'extract_allis_presentation_pages',delayed)
    else:
        real=source.deepcopy
        def delayed(v):
            out=real(v)
            if stage=='handoff'and isinstance(v,dict)and'documents'in v or stage=='components'and isinstance(v,list):clock[0]=expired
            return out
        monkeypatch.setattr(source,'deepcopy',delayed)
    with pytest.raises(SourceResponseError)as e:source.fetch_allis_context('1514.TW')
    assert e.value.error_kind=='timeout'


def test_historical_saved_replay_does_not_claim_current_acquisition(harness,monkeypatch):
    from data_fetch.market_sources import allis_conference as source
    value=source.fetch_allis_context('1514.TW')
    original=deepcopy(value)
    monkeypatch.setattr(time,'time',lambda:NOW+1801)
    assert source.verify_context(value,'1514.TW',max_age=1800)is False
    assert source.verify_context(value,'1514.TW',max_age=86400)is True
    assert value==original and len(harness[1])==3
    monkeypatch.setattr(time,'time',lambda:NOW+86400)
    assert source.verify_context(value,'1514.TW',max_age=86400)is False


def test_preplanted_success_cache_cannot_supply_allis_body(harness):
    import cache_store
    from data_fetch.market_sources import allis_conference as source
    from data_fetch.market_sources.allis_conference_transport import ConferenceHttp
    key=ConferenceHttp.raw_cache_prefix+PDF_URL
    fake={'value':{'body_b64':'YmFk','fetched_at_epoch':NOW},'fetched_at_epoch':NOW,'fresh_until_epoch':NOW+1800}
    cache_store.set_cache_json(key,fake,ttl_seconds=1800)
    value=source.fetch_allis_context('1514.TW')
    assert value['documents'][0]['page_count']==29 and len(harness[1])==3
    assert cache_store.get_cache_json(key)==fake


@pytest.mark.parametrize('advance',['budget','validation_age'])
def test_final_diagnostic_handoff_cannot_return_expired_success(harness,monkeypatch,advance):
    from types import SimpleNamespace
    from data_fetch.market_sources import allis_conference as source
    from search_provider_runtime import SourceResponseError
    mono=[time.monotonic()];epoch=[NOW]
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:mono[0],time=lambda:epoch[0]))
    class Diagnostic(dict):
        def update(self,*a,**kw):
            super().update(*a,**kw)
            if self.get('allis_originals_verified'):
                if advance=='budget':mono[0]+=26
                else:epoch[0]+=1800
    diagnostic=Diagnostic()
    with pytest.raises(SourceResponseError)as caught:source.fetch_allis_context('1514.TW',diagnostics=diagnostic)
    assert caught.value.error_kind==('timeout'if advance=='budget'else'original_expired')
    assert diagnostic['allis_originals_verified']is False
    assert all(k not in diagnostic for k in ('coverage_status','cache_hit','stale','fetched_at_epoch'))
    assert diagnostic['http_request_count']==3 and diagnostic['http_request_sent']is True
