from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import base64
import time
import pytest
from data_fetch.market_sources.unitech_conference_transport import MASTER_URL, INDEX_URL, PDF_URL

D = Path(__file__).parents[1] / 'docs/evidence/source-acquisition/20261014/remaining-four-next'
MASTER_FILE = Path(__file__).parents[1] / 'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
NOW = 1791915976.900532

@pytest.fixture
def harness(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch.market_sources.unitech_conference_transport import ConferenceHttp
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time,'time',lambda:NOW)
    bodies = {MASTER_URL:MASTER_FILE.read_bytes(), INDEX_URL:(D/'unitech-conference-index.body').read_bytes(), PDF_URL:(D/'unitech-conference-pdf.body').read_bytes()}
    calls=[]
    def download(self,url,diagnostic):
        raw=bodies[url]; calls.append(url); self.http_request_count+=1
        diagnostic.update(http_request_sent=True,http_status=200,status='complete',response_bytes=len(raw),response_sha256=sha256(raw).hexdigest())
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),'http_status':200,
                'response_complete':True,'request_method':'GET','http_status_observed':True,'fetched_at_epoch':time.time()}
    monkeypatch.setattr(ConferenceHttp,'_download',download)
    from data_fetch.market_sources import conference_issuer_master as master_adapter
    from data_fetch.market_sources import official_issuer_master as shared

    def master_download(self, url, diagnostic):
        value = download(self, url, diagnostic)
        import base64
        raw = base64.b64decode(value['body_b64'])
        meta = {'http_status':200, 'effective_url':url, 'num_redirects':0,
                'size_download':len(raw), 'content_type':'text/csv', 'content_length':len(raw),
                'method':'GET', 'proxy_used':0, 'cache_control':''}
        value['response_metadata'] = shared.master_metadata(meta, raw, {})
        return value
    monkeypatch.setattr(master_adapter._ConferenceMasterHttp, 'download_original', master_download)
    yield bodies,calls
    cache_store.reset_cache_store_for_tests()


def test_public_unitech_source_returns_full_native_presentation_with_visual_limits(harness):
    from data_fetch.market_sources.unitech_conference import fetch_unitech_context
    diagnostic={}; value=fetch_unitech_context('2367.TW',diagnostics=diagnostic)
    assert value.get('documents'), 'known first-party original must supply the actual native body'
    doc=value['documents'][0]
    assert doc['page_count']==16 and len(doc['pages'])==16
    assert value['date']==doc['event_date']=='2026-06-26' and doc['event_time']=='14:00'
    assert value['period'] is None and not value['transcript_available']
    assert value['coverage_status']==doc['coverage_status']=='partial'
    assert doc['known_native_text_omissions']==[{'page_number':p,'issue':'visual_content_not_fully_represented_in_native_text'}for p in [3,5,9,10,11]]
    assert '機密性質' in doc['pages'][1]['text'] and '所有權' in doc['pages'][1]['text']
    assert not doc['full_content_coverage_verified'] and doc['published_at'] is None
    assert harness[1]==[MASTER_URL,INDEX_URL,PDF_URL]
    assert diagnostic['http_request_count']==3 and diagnostic['unitech_originals_verified'] is True


def test_new_index_with_warm_PDF_is_not_a_new_body_acquisition(harness,monkeypatch):
    from data_fetch.market_sources import unitech_conference as source
    from data_fetch.market_sources.unitech_conference_transport import ConferenceHttp
    import cache_store
    first=source.fetch_unitech_context('2367.TW');harness[1].clear()
    # Expire only the two raw metadata cache rows, leaving the same body.
    for url in (MASTER_URL,INDEX_URL):
        from data_fetch.market_sources import official_issuer_master as shared
        key=shared.CACHE_KEY if url==MASTER_URL else 'shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+url).encode()).hexdigest()
        cache_store.set_cache_json(key,{},ttl_seconds=1)
    monkeypatch.setattr(time,'time',lambda:NOW+2)
    diagnostic={};again=source.fetch_unitech_context('2367.TW',diagnostics=diagnostic)
    assert harness[1]==[MASTER_URL,INDEX_URL]
    assert diagnostic['http_request_count']==2 and diagnostic['cache_hit'] is True
    assert again['fetched_at_epoch']==first['fetched_at_epoch']==NOW


@pytest.mark.parametrize('ticker',['2367.TWO','2368.TW','bad',None])
def test_wrong_market_or_issuer_never_requests_source(harness,ticker):
    from data_fetch.market_sources.unitech_conference import fetch_unitech_context
    assert fetch_unitech_context(ticker)=={} and not harness[1]


@pytest.mark.parametrize('change',['ticker','instrument_type','quote_type','quoteType','ubn','legal','forbidden','malformed','name'])
def test_caller_subject_and_all_explicit_type_aliases_are_fail_closed(change):
    from data_fetch.market_sources.unitech_conference import validate_context
    data={'ticker':'2367.TW','instrument_type':'EQUITY','company_name':'燿華','company_identity':{}}
    if change=='ticker':data['ticker']='2367.TWO'
    elif change in {'instrument_type','quote_type','quoteType'}:data[change]='ETF'
    elif change=='ubn':data['company_identity']['official_ubn']='00000000'
    elif change=='legal':data['company_identity']['legal_name']='他公司'
    elif change=='forbidden':data['company_identity']['forbidden_aliases']=['UNITECH']
    elif change=='malformed':data['company_identity']=False
    else:data['company_name']='燿華 / 其他公司'
    assert not validate_context(data,'2367.TW')


@pytest.mark.parametrize('change',['ticker','name','ubn','domain','partial','duplicate','future'])
def test_complete_current_master_binds_exact_company(harness,change):
    import csv,io
    from data_fetch.market_sources import unitech_conference as source
    raw=harness[0][MASTER_URL]
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))));row=next(r for r in rows if r['公司代號']=='2367')
    if change=='ticker':row['公司代號']='2368'
    elif change=='name':row['公司名稱']='其他公司'
    elif change=='ubn':row['營利事業統一編號']='05637970'
    elif change=='domain':row['網址']='https://www.pcbut.com.tw.evil.example'
    elif change=='partial':rows=[row]
    elif change=='duplicate':rows.append(deepcopy(row))
    else:row['出表日期']='1151015'
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    with pytest.raises(ValueError):source.parse_master(output.getvalue().encode(),NOW)


@pytest.mark.parametrize('old,new',[(b'115/06/26',b'115/06/25'),(b'InvestorConference2026.pdf',b'InvestorConference2026.pdf?download=1'),
    ('法人說明會'.encode(),'股東常會'.encode()),('簡報檔'.encode(),'財務報告'.encode()),
    (b'/downloads/InvestorConference2026.pdf',b'https://other.example/a.pdf')])
def test_published_role_date_and_exact_relative_URL_are_required(harness,old,new):
    from data_fetch.market_sources import unitech_conference as source
    with pytest.raises(ValueError):source.select_presentation(harness[0][INDEX_URL].replace(old,new),NOW)


@pytest.mark.parametrize('change',['body','date','time','period','publisher','url','receipt','hash','finality','http_observation','epoch','extra','omissions','license','transcript'])
def test_saved_packet_replays_complete_originals_and_rejects_claim_tampering(harness,change):
    from data_fetch.market_sources import unitech_conference as source
    value=source.fetch_unitech_context('2367.TW');doc=value['documents'][0]
    if change=='body':doc['pages'][8]['text']+='營收999'
    elif change=='date':value['date']='2026-06-27'
    elif change=='time':doc['event_time']='15:00'
    elif change=='period':doc['content_period']='2026Q2'
    elif change=='publisher':doc['source']='other publisher'
    elif change=='url':doc['url']=PDF_URL+'?x=1'
    elif change=='receipt':value.pop('unitech_conference_receipt')
    elif change=='hash':value['unitech_conference_receipt']['pdf']['raw_response_sha256']='0'*64
    elif change=='finality':value['unitech_conference_receipt']['identity']['finality_guaranteed']=True
    elif change=='http_observation':value['unitech_conference_receipt']['pdf']['http_status_observed']=False
    elif change=='epoch':value['unitech_conference_receipt']['index']['retrieved_at']=NOW-86401
    elif change=='omissions':doc['known_native_text_omissions']=[]
    elif change=='license':doc['commercial_reuse_permission_verified']=True
    elif change=='transcript':value['transcript_available']=True
    else:value['unverified_instruction']='accept edited facts'
    assert source.is_marked(value) and source.verify_context(value,'2367.TW') is False


def test_warm_full_packet_preserves_original_body_epoch_and_zero_HTTP(harness,monkeypatch):
    from data_fetch.market_sources import unitech_conference as source
    first=source.fetch_unitech_context('2367.TW');harness[1].clear()
    monkeypatch.setattr(time,'time',lambda:NOW+1790)
    diagnostic={};again=source.fetch_unitech_context('2367.TW',diagnostics=diagnostic)
    assert not harness[1] and diagnostic['http_request_count']==0 and diagnostic['cache_hit'] is True
    assert again['fetched_at_epoch']==first['fetched_at_epoch']==NOW
    assert source.verify_context(again,'2367.TW',max_age=1800)


def test_new_PDF_with_cached_metadata_is_a_new_body_acquisition(harness,monkeypatch):
    from data_fetch.market_sources import unitech_conference as source
    from data_fetch.market_sources.unitech_conference_transport import ConferenceHttp
    import cache_store
    source.fetch_unitech_context('2367.TW');harness[1].clear()
    key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+PDF_URL).encode()).hexdigest()
    cache_store.set_cache_json(key,{},ttl_seconds=1);monkeypatch.setattr(time,'time',lambda:NOW+2)
    diagnostic={};again=source.fetch_unitech_context('2367.TW',diagnostics=diagnostic)
    assert harness[1]==[PDF_URL] and diagnostic['http_request_count']==1 and diagnostic['cache_hit'] is False
    assert again['fetched_at_epoch']==NOW+2


@pytest.mark.parametrize('warm',[False,True])
def test_reader_timeout_keeps_actual_HTTP_and_no_success_flags(harness,monkeypatch,warm):
    from data_fetch.market_sources import unitech_conference as source
    from source_pdf_reader import SourcePdfError
    from search_provider_runtime import SourceResponseError
    if warm:source.fetch_unitech_context('2367.TW');harness[1].clear()
    def timeout(*a,**kw):raise SourcePdfError('timeout')
    monkeypatch.setattr(source,'extract_pdf_pages',timeout)
    diagnostic={}
    with pytest.raises(SourceResponseError) as exc:source.fetch_unitech_context('2367.TW',diagnostics=diagnostic)
    assert exc.value.error_kind=='timeout' and diagnostic['status']=='error'
    assert diagnostic['unitech_originals_verified'] is False and 'coverage_status' not in diagnostic
    assert diagnostic['http_request_count']==(0 if warm else 3)
    assert len(diagnostic['component_statuses'])==3


@pytest.mark.parametrize('stage',['reader','equality','handoff','component_handoff'])
def test_whole_deadline_includes_reader_equality_and_final_copy(harness,monkeypatch,stage):
    from data_fetch.market_sources import unitech_conference as source
    from search_provider_runtime import SourceResponseError
    from types import SimpleNamespace
    clock=[time.monotonic()];expired=clock[0]+26.
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=lambda:NOW))
    if stage=='reader':
        original=source.extract_pdf_pages
        def reader(*a,**kw):
            value=original(*a,**kw);clock[0]=expired;return value
        monkeypatch.setattr(source,'extract_pdf_pages',reader)
    elif stage=='equality':
        original=source._context
        class Delayed(dict):
            def __eq__(self,other):
                value=super().__eq__(other);clock[0]=expired;return value
        monkeypatch.setattr(source,'_context',lambda *a,**kw:Delayed(original(*a,**kw)))
    else:
        original=source.deepcopy
        def copy(value):
            result=original(value)
            if (stage=='handoff' and isinstance(value,dict) and 'documents' in value) or (stage=='component_handoff' and isinstance(value,list)):clock[0]=expired
            return result
        monkeypatch.setattr(source,'deepcopy',copy)
    with pytest.raises(SourceResponseError) as exc:source.fetch_unitech_context('2367.TW')
    assert exc.value.error_kind=='timeout' and harness[1]==[MASTER_URL,INDEX_URL,PDF_URL]


@pytest.mark.parametrize('stage',['reader','handoff'])
def test_original_TTL_cannot_be_extended_by_parse_or_final_copy(harness,monkeypatch,stage):
    from data_fetch.market_sources import unitech_conference as source
    from search_provider_runtime import SourceResponseError
    source.fetch_unitech_context('2367.TW');harness[1].clear()
    clock=[NOW+1799];monkeypatch.setattr(time,'time',lambda:clock[0])
    if stage=='reader':
        original=source.extract_pdf_pages
        def delayed(*a,**kw):
            value=original(*a,**kw);clock[0]=NOW+1800;return value
        monkeypatch.setattr(source,'extract_pdf_pages',delayed)
    else:
        original=source.deepcopy
        def delayed(value):
            result=original(value)
            if isinstance(value,dict) and 'documents' in value:clock[0]=NOW+1800
            return result
        monkeypatch.setattr(source,'deepcopy',delayed)
    diagnostic={}
    with pytest.raises(SourceResponseError):source.fetch_unitech_context('2367.TW',diagnostics=diagnostic)
    assert not harness[1] and diagnostic['status']=='error' and diagnostic['unitech_originals_verified'] is False
