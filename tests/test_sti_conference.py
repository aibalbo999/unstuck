from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import base64
import time
import pytest
ROOT=Path(__file__).parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261014/free-entrance-next/sti2480'
I=D
MASTER_FILE=ROOT/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
MASTER_URL='https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX_URL='https://www.sti.com.tw/earnings-call'
PDF_URL='https://www.sti.com.tw/documents/36928/0/115Q2%E6%95%A6%E9%99%BD%E6%B3%95%E8%AA%AASTI_CHN.pdf/899302f6-faa3-f301-c6b7-f7dd8f4dbcbd?t=1785826779822'
NOW=1791927600.0

@pytest.fixture
def harness(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch.market_sources import sti_conference as source
    cache_store.set_cache_backend(InMemoryCache());monkeypatch.setattr(time,'time',lambda:NOW)
    bodies={MASTER_URL:MASTER_FILE.read_bytes(),INDEX_URL:(I/'index.body').read_bytes(),PDF_URL:(D/'presentation.body').read_bytes()};calls=[]
    if hasattr(source,'ConferenceHttp'):
        from data_fetch.market_sources.sti_conference_transport import request_spec
        def download(self,url,diagnostic):
            raw=bodies[url];calls.append(url);self.http_request_count+=1
            diagnostic.update(http_request_sent=True,http_status=200,status='complete',response_bytes=len(raw),response_sha256=sha256(raw).hexdigest())
            return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),**request_spec(url),'response_metadata':{'http_status':200,'effective_url':url,'num_redirects':0,'size_download':len(raw),'content_type':'text/csv' if url==MASTER_URL else 'text/html' if url==INDEX_URL else 'application/pdf','content_length':len(raw),'method':request_spec(url)['request_method'],'proxy_used':0}}
        monkeypatch.setattr(source.ConferenceHttp,'download_original',download)
    yield bodies,calls
    cache_store.reset_cache_store_for_tests()

def valid_data():
    return {'ticker':'2480.TW','instrument_type':'EQUITY','company_name':'敦陽科 / Stark Technology Inc.',
            'raw_company_name':'STARK TECHNOLOGY INC','company_identity':{'ticker':'2480.TW','stock_id':'2480',
                'official_name':'敦陽科','legal_name':None,'display_name':'敦陽科 / Stark Technology Inc.',
                'allowed_aliases':['敦陽科','2480','2480.TW','敦陽科 / Stark Technology Inc.','STARK TECHNOLOGY INC'],
                'english_names':['Stark Technology Inc.','STARK TECHNOLOGY INC'],'forbidden_aliases':[]}}

def test_public_missing_body_recovers_exact_official_Chinese_original(harness):
    from data_fetch.market_sources import sti_conference as source
    diagnostics={};value=source.fetch_sti_context('2480.TW',diagnostics=diagnostics)
    assert value.get('documents'), 'metadata-only event must recover its full published official Chinese presentation'
    doc=value['documents'][0]
    assert value['date']==doc['event_date']=='2026-08-05'
    assert doc.get('event_time') is None and doc['published_at'] is None
    assert doc['page_count']==44 and len(doc['pages'])==44
    assert doc['content_periods']==['2026Q2','2026H1','2025H1','2025-12-31']
    assert doc['document_kind']=='presentation' and doc['language']=='zh-TW'
    assert doc['native_text_coverage']=='complete' and doc['coverage_status']==value['coverage_status']=='partial'
    assert doc['sti_glyph_evidence']['raw_bytes_rewritten'] is False
    assert not doc['q_and_a_transcript_available'] and not value['transcript_available']
    assert doc['subsidiary_scope_caution'] and doc['financial_scope_caution'] and doc['known_native_text_omissions']
    assert harness[1]==[MASTER_URL,INDEX_URL,PDF_URL]
    assert diagnostics['http_request_count']==3 and not diagnostics['cache_hit'] and diagnostics['sti_originals_verified']
    assert source.verify_context(value,'2480.TW',max_age=1800)


@pytest.mark.parametrize('elapsed,kind',[(24.,'cache_receipt_invalid'),(25.,'timeout'),(26.,'timeout')])
def test_late_receipt_storage_failure_preserves_cause_and_http_truth(harness,monkeypatch,elapsed,kind):
    import cache_store
    from data_fetch.market_sources import sti_conference as source
    from data_fetch.market_sources.sti_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    source.fetch_sti_context('2480.TW');harness[1].clear()
    baseline=time.monotonic();clock=[baseline]
    monkeypatch.setattr(time,'monotonic',lambda:clock[0])
    original=cache_store.get_cache_json
    target='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+MASTER_URL).encode()).hexdigest()
    reads=[];cause=OSError('isolated delayed cache read failure')
    def delayed_error(key):
        if key==target:
            reads.append(key)
            if len(reads)==2:
                clock[0]=baseline+elapsed
                raise cause
        return original(key)
    monkeypatch.setattr(cache_store,'get_cache_json',delayed_error)
    diagnostic={}
    with pytest.raises(SourceResponseError) as error:
        source.fetch_sti_context('2480.TW',diagnostics=diagnostic)
    assert error.value.error_kind==diagnostic['error_kind']==kind
    chain=[];current=error.value
    while current is not None:
        chain.append(current);current=current.__cause__
    assert chain[-1] is cause
    assert any(isinstance(exc,SourceResponseError) and exc.error_kind=='cache_receipt_invalid' for exc in chain)
    assert all(error.value.diagnostic.get(key)==value for key,value in diagnostic.items())
    assert diagnostic['sti_originals_verified'] is False
    assert diagnostic['http_request_count']==0 and diagnostic['http_request_sent'] is False
    assert len(diagnostic['component_statuses'])==1
    assert diagnostic['component_statuses'][0]['cache_hit'] is True
    assert len(reads)==2 and not harness[1]

def test_cold_then_warm_preserves_epoch_and_has_zero_HTTP(harness,monkeypatch):
    from data_fetch.market_sources import sti_conference as source
    first=source.fetch_sti_context('2480.TW');harness[1].clear();monkeypatch.setattr(time,'time',lambda:NOW+1790)
    d={};again=source.fetch_sti_context('2480.TW',diagnostics=d)
    assert not harness[1] and d['http_request_count']==0 and d['cache_hit'] is True
    assert again['fetched_at_epoch']==first['fetched_at_epoch']==NOW and source.verify_context(again,'2480.TW',max_age=1800)

@pytest.mark.parametrize('expire_pdf',[False,True])
def test_cache_status_tracks_qualified_body_not_metadata_HTTP(harness,monkeypatch,expire_pdf):
    import cache_store
    from data_fetch.market_sources import sti_conference as source
    from data_fetch.market_sources.sti_conference_transport import ConferenceHttp
    source.fetch_sti_context('2480.TW');harness[1].clear()
    expired=[PDF_URL] if expire_pdf else [MASTER_URL,INDEX_URL]
    for url in expired:
        key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+url).encode()).hexdigest();cache_store.set_cache_json(key,{},ttl_seconds=1)
    monkeypatch.setattr(time,'time',lambda:NOW+2);d={};value=source.fetch_sti_context('2480.TW',diagnostics=d)
    assert harness[1]==expired and d['http_request_count']==len(expired) and d['cache_hit'] is not expire_pdf
    assert value['fetched_at_epoch']==(NOW+2 if expire_pdf else NOW)

@pytest.mark.parametrize('opts',[{'force_refresh':True},{'use_cache':False}])
def test_force_or_uncached_refreshes_all_three_originals(harness,opts):
    from data_fetch.market_sources import sti_conference as source
    source.fetch_sti_context('2480.TW');harness[1].clear();source.fetch_sti_context('2480.TW',**opts)
    assert harness[1]==[MASTER_URL,INDEX_URL,PDF_URL]

@pytest.mark.parametrize('warm',[False,True])
def test_reader_timeout_preserves_real_HTTP_and_no_success(harness,monkeypatch,warm):
    from data_fetch.market_sources import sti_conference as source
    from source_pdf_reader import SourcePdfError
    from search_provider_runtime import SourceResponseError
    if warm:source.fetch_sti_context('2480.TW');harness[1].clear()
    def timeout(*a,**kw):raise SourcePdfError('timeout')
    monkeypatch.setattr(source,'extract_sti_presentation_pages',timeout);d={}
    with pytest.raises(SourceResponseError) as err:source.fetch_sti_context('2480.TW',diagnostics=d)
    assert err.value.error_kind=='timeout' and d['status']=='error' and d['sti_originals_verified'] is False
    assert d['http_request_count']==(0 if warm else 3) and 'coverage_status' not in d

@pytest.mark.parametrize('stage',['reader','equality','handoff','components'])
def test_total_deadline_includes_all_parsing_projection_and_copy(harness,monkeypatch,stage):
    from data_fetch.market_sources import sti_conference as source
    from search_provider_runtime import SourceResponseError
    from types import SimpleNamespace
    clock=[time.monotonic()];expired=clock[0]+26
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=lambda:NOW))
    if stage=='reader':
        original=source.extract_sti_presentation_pages
        def delayed(*a,**kw):v=original(*a,**kw);clock[0]=expired;return v
        monkeypatch.setattr(source,'extract_sti_presentation_pages',delayed)
    elif stage=='equality':
        original=source._context
        class Delayed(dict):
            def __eq__(self,other):v=super().__eq__(other);clock[0]=expired;return v
        monkeypatch.setattr(source,'_context',lambda *a,**kw:Delayed(original(*a,**kw)))
    else:
        original=source.deepcopy
        def delayed(v):
            result=original(v)
            if stage=='handoff' and isinstance(v,dict) and 'documents' in v or stage=='components' and isinstance(v,list):clock[0]=expired
            return result
        monkeypatch.setattr(source,'deepcopy',delayed)
    with pytest.raises(SourceResponseError) as err:source.fetch_sti_context('2480.TW')
    assert err.value.error_kind=='timeout'

@pytest.mark.parametrize('stage',['reader','equality','handoff','components'])
def test_original_TTL_is_checked_after_final_work(harness,monkeypatch,stage):
    from data_fetch.market_sources import sti_conference as source
    from search_provider_runtime import SourceResponseError
    source.fetch_sti_context('2480.TW');harness[1].clear();clock=[NOW+1799]
    monkeypatch.setattr(time,'time',lambda:clock[0])
    if stage=='reader':
        original=source.extract_sti_presentation_pages
        def delayed(*a,**kw):v=original(*a,**kw);clock[0]=NOW+1800;return v
        monkeypatch.setattr(source,'extract_sti_presentation_pages',delayed)
    elif stage=='equality':
        original=source._context
        class Delayed(dict):
            def __eq__(self,other):v=super().__eq__(other);clock[0]=NOW+1800;return v
        monkeypatch.setattr(source,'_context',lambda *a,**kw:Delayed(original(*a,**kw)))
    else:
        original=source.deepcopy
        def delayed(v):
            result=original(v)
            if stage=='handoff' and isinstance(v,dict) and 'documents' in v or stage=='components' and isinstance(v,list):clock[0]=NOW+1800
            return result
        monkeypatch.setattr(source,'deepcopy',delayed)
    d={}
    with pytest.raises(SourceResponseError):source.fetch_sti_context('2480.TW',diagnostics=d)
    assert not harness[1] and d['status']=='error' and not d['sti_originals_verified']

@pytest.mark.parametrize('kind',['timeout','access_denied','rate_limited'])
def test_error_admission_blocks_normal_force_and_uncached_without_repeat_HTTP(harness,monkeypatch,kind):
    from data_fetch.market_sources import sti_conference as source
    from data_fetch.market_sources.sti_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    calls=[]
    def bad(self,url,diagnostic):
        self.http_request_count+=1;calls.append(url);diagnostic.update(http_request_sent=True)
        raise SourceResponseError(kind)
    monkeypatch.setattr(ConferenceHttp,'download_original',bad)
    for opts in ({},{'force_refresh':True},{'use_cache':False}):
        d={}
        with pytest.raises(SourceResponseError):source.fetch_sti_context('2480.TW',diagnostics=d,**opts)
        assert not d['sti_originals_verified'] and d['status']=='error'
    assert calls==[MASTER_URL]

def test_cooldown_storage_not_writable_sends_zero_HTTP(harness,monkeypatch):
    import cache_store
    from data_fetch.market_sources import sti_conference as source
    from search_provider_runtime import SourceResponseError
    def bad(*a,**kw):raise OSError('read-only')
    monkeypatch.setattr(cache_store,'set_cache_json',bad)
    d={}
    with pytest.raises(SourceResponseError):source.fetch_sti_context('2480.TW',diagnostics=d)
    assert not harness[1] and d['http_request_count']==0 and not d['sti_originals_verified']

@pytest.mark.parametrize('url',[PDF_URL+'?x=1',PDF_URL+'#x',PDF_URL.replace('https:','http:'),PDF_URL.replace('www.sti.com.tw','www.sti.com.tw.evil.example'),INDEX_URL+'?YEAR=2026',MASTER_URL+'?x=1'])
def test_transport_only_exact_original_URLs(harness,url):
    from data_fetch.market_sources.sti_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):ConferenceHttp(time.monotonic()+25).get_receipt(url)
    assert not harness[1]

def test_simultaneous_master_requests_share_one_native_acquisition(harness):
    from concurrent.futures import ThreadPoolExecutor
    from data_fetch.market_sources.sti_conference_transport import ConferenceHttp
    from threading import Barrier
    gate=Barrier(2)
    def request():
        gate.wait();return ConferenceHttp(time.monotonic()+25).get_receipt(MASTER_URL)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:request(),range(2)))
    assert harness[1]==[MASTER_URL] and results[0][0]==results[1][0]
    assert sorted(v[1]['cache_hit'] for v in results)==[False,True]

def test_doc_boolean_flag_cannot_be_impersonated_by_integer(harness):
    from data_fetch.market_sources import sti_conference as source
    value=source.fetch_sti_context('2480.TW');value['documents'][0]['binary_complete']=1
    assert source.verify_context(value,'2480.TW') is False

@pytest.mark.parametrize('url',[MASTER_URL,INDEX_URL,PDF_URL])
@pytest.mark.parametrize('stage',['reader','handoff'])
def test_shorter_shared_expiry_cannot_cross_projection_or_delivery(harness,monkeypatch,url,stage):
    import cache_store
    from data_fetch.market_sources import sti_conference as source
    from data_fetch.market_sources.sti_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    source.fetch_sti_context('2480.TW');harness[1].clear()
    key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+url).encode()).hexdigest()
    row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+2;cache_store.set_cache_json(key,row,ttl_seconds=1800)
    clock=[NOW+1];monkeypatch.setattr(time,'time',lambda:clock[0])
    if stage=='reader':
        original=source.extract_sti_presentation_pages
        def delayed(*a,**kw):v=original(*a,**kw);clock[0]=NOW+3;return v
        monkeypatch.setattr(source,'extract_sti_presentation_pages',delayed)
    else:
        original=source.deepcopy
        def delayed(value):
            v=original(value)
            if isinstance(value,dict) and 'documents' in value:clock[0]=NOW+3
            return v
        monkeypatch.setattr(source,'deepcopy',delayed)
    d={}
    with pytest.raises(SourceResponseError):source.fetch_sti_context('2480.TW',diagnostics=d)
    assert not harness[1] and not d['sti_originals_verified']

def test_shorter_cache_expiry_is_preserved_without_epoch_renewal(harness,monkeypatch):
    import cache_store
    from data_fetch.market_sources import sti_conference as source
    from data_fetch.market_sources.sti_conference_transport import ConferenceHttp
    source.fetch_sti_context('2480.TW');harness[1].clear()
    key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+PDF_URL).encode()).hexdigest()
    row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+10;cache_store.set_cache_json(key,row,ttl_seconds=1800)
    monkeypatch.setattr(time,'time',lambda:NOW+5);d={};value=source.fetch_sti_context('2480.TW',diagnostics=d)
    proof=value['sti_conference_receipt']['pdf']
    assert proof['retrieved_at']==value['fetched_at_epoch']==NOW and proof['fresh_until_epoch']==NOW+10
    assert not harness[1] and d['cache_hit'] is True and d['http_request_count']==0
    monkeypatch.setattr(time,'time',lambda:NOW+10)
    assert source.verify_context(value,'2480.TW') is False

@pytest.mark.parametrize('expiry',[True,float('inf'),float('nan'),-1,NOW,NOW+1801,'1791927800',10**500])
def test_invalid_or_extended_receipt_expiry_is_rejected(harness,expiry):
    from data_fetch.market_sources import sti_conference as source
    value=source.fetch_sti_context('2480.TW');value['sti_conference_receipt']['pdf']['fresh_until_epoch']=expiry
    assert source.verify_context(value,'2480.TW') is False

def test_complete_archive_is_revalidated_after_final_copy(harness,monkeypatch):
    from data_fetch.market_sources import sti_conference as source
    from search_provider_runtime import SourceResponseError
    original=source.deepcopy;saved={}
    def corrupt_at_handoff(value):
        copied=original(value)
        if isinstance(value,dict) and 'sti_conference_receipt' in value:
            path=Path(value['sti_conference_receipt']['pdf']['raw_response_path'])
            saved[path]=path.read_bytes();path.write_bytes(b'corrupt gzip')
        return copied
    monkeypatch.setattr(source,'deepcopy',corrupt_at_handoff);d={}
    try:
        with pytest.raises(SourceResponseError):source.fetch_sti_context('2480.TW',diagnostics=d)
        assert not d['sti_originals_verified']
    finally:
        for path,raw in saved.items():path.write_bytes(raw)

def test_receipt_alone_cannot_extend_saved_shorter_deadline(harness,monkeypatch):
    import cache_store
    from data_fetch.market_sources import sti_conference as source
    from data_fetch.market_sources.sti_conference_transport import ConferenceHttp
    source.fetch_sti_context('2480.TW');harness[1].clear()
    key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+PDF_URL).encode()).hexdigest()
    row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+10;cache_store.set_cache_json(key,row,ttl_seconds=1800)
    monkeypatch.setattr(time,'time',lambda:NOW+5);value=source.fetch_sti_context('2480.TW')
    assert value['sti_conference_receipt']['pdf']['fresh_until_epoch']==NOW+10
    value['sti_conference_receipt']['pdf']['fresh_until_epoch']=NOW+20
    monkeypatch.setattr(time,'time',lambda:NOW+15)
    assert source.verify_context(value,'2480.TW',max_age=1800) is False
    assert not harness[1]

def test_newer_same_bytes_cache_row_cannot_renew_older_receipt(harness,monkeypatch):
    from data_fetch.market_sources import sti_conference as source
    from data_fetch.market_sources.sti_conference_transport import ConferenceHttp
    old=source.fetch_sti_context('2480.TW');harness[1].clear()
    monkeypatch.setattr(time,'time',lambda:NOW+5)
    raw,new=ConferenceHttp(time.monotonic()+25,force_refresh=True).get_receipt(PDF_URL)
    assert new['retrieved_at']==NOW+5 and old['sti_conference_receipt']['pdf']['retrieved_at']==NOW
    old['sti_conference_receipt']['pdf']['fresh_until_epoch']=NOW+1800
    assert source.verify_context(old,'2480.TW',max_age=1800) is False
    assert harness[1]==[PDF_URL]

@pytest.mark.parametrize('state',['missing','storage_unavailable'])
def test_saved_receipt_requires_independent_cache_observation(harness,monkeypatch,state):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import sti_conference as source
    value=source.fetch_sti_context('2480.TW');harness[1].clear()
    if state=='missing':cache_store.set_cache_backend(InMemoryCache())
    else:
        def unavailable(*args):raise RuntimeError('storage unavailable')
        monkeypatch.setattr(cache_store,'get_cache_json',unavailable)
    assert source.verify_context(value,'2480.TW',max_age=1800) is False
    assert not harness[1]

@pytest.mark.parametrize('change',['body','hash','epoch','url','http','complete','observed','deadline','future_observation'])
def test_replay_binds_strict_independent_raw_cache_metadata(harness,monkeypatch,change):
    import cache_store
    from data_fetch.market_sources import sti_conference as source
    from data_fetch.market_sources.sti_conference_transport import ConferenceHttp
    value=source.fetch_sti_context('2480.TW');harness[1].clear()
    key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+PDF_URL).encode()).hexdigest()
    row=cache_store.get_cache_json(key);payload=row['value']
    if change=='body':payload['body_b64']=base64.b64encode(b'different body').decode()
    elif change=='hash':payload['sha256']='0'*64
    elif change=='epoch':payload['fetched_at_epoch']=NOW-1
    elif change=='url':payload['url']=INDEX_URL
    elif change=='http':payload['http_status']=True
    elif change=='complete':payload['response_complete']=1
    elif change=='observed':payload['http_status_observed']=False
    elif change=='deadline':row['fresh_until_epoch']=True
    else:row['fetched_at_epoch']=NOW+1
    cache_store.set_cache_json(key,row,ttl_seconds=1800)
    assert source.verify_context(value,'2480.TW',max_age=1800) is False
    assert not harness[1]

@pytest.mark.parametrize('ticker',['2480.TWO','4919.TW','2345.TW','bad',None,2480])
def test_wrong_issuer_or_market_sends_no_http(harness,ticker):
    from data_fetch.market_sources import sti_conference as source
    assert source.fetch_sti_context(ticker)=={} and not harness[1]

@pytest.mark.parametrize('change',['ticker','quote','root_stock','root_ubn','root_legal','root_name','raw_name','identity','display','legal','short','ubn','allowed','english','list_type','forbidden'])
def test_independent_caller_identity_fields_cannot_borrow_good_aliases(change):
    from data_fetch.market_sources.sti_conference import validate_context
    data=valid_data();assert validate_context(data,'2480.TW')
    identity=data['company_identity']
    if change=='ticker':data['ticker']='4919.TW'
    elif change=='quote':data['quote_type']='ETF'
    elif change=='root_stock':data['stock_id']='4919'
    elif change=='root_ubn':data['official_ubn']='00000000'
    elif change=='root_legal':data['legal_name']='新唐科技股份有限公司'
    elif change=='root_name':data['company_name']='敦陽科 / Nuvoton'
    elif change=='raw_name':data['raw_company_name']='Nuvoton'
    elif change=='identity':data['company_identity']=False
    elif change=='display':identity['display_name']='新唐'
    elif change=='legal':identity['legal_name']='新唐科技股份有限公司'
    elif change=='short':identity['official_name']='新唐'
    elif change=='ubn':identity['official_ubn']='00000000'
    elif change=='allowed':identity['allowed_aliases'].append('新唐')
    elif change=='english':identity['english_names'].append('Nuvoton')
    elif change=='list_type':identity['allowed_aliases']='STI'
    else:identity['forbidden_aliases']=['*STI / 敦陽科*']
    assert not validate_context(data,'2480.TW')

@pytest.mark.parametrize('change',['code','legal','short','ubn','english','domain','partial','duplicate','future','old','row_shape'])
def test_complete_master_identity_and_date_bound(harness,change):
    import csv,io
    from data_fetch.market_sources import sti_conference as source
    rows=list(csv.DictReader(io.StringIO(harness[0][MASTER_URL].decode('utf-8-sig'))))
    row=next(r for r in rows if r['公司代號']=='2480')
    edits={'code':('公司代號','4919'),'legal':('公司名稱','新唐科技股份有限公司'),'short':('公司簡稱','新唐'),
           'ubn':('營利事業統一編號','23218023'),'english':('英文簡稱','Nuvoton'),'domain':('網址','https://www.sti.com.tw.evil/'),
           'future':('出表日期','1151015'),'old':('出表日期','1150901')}
    if change in edits:row[edits[change][0]]=edits[change][1]
    elif change=='partial':rows=[row]
    elif change=='duplicate':rows.append(deepcopy(row))
    out=io.StringIO();w=csv.DictWriter(out,fieldnames=list(row));w.writeheader()
    if change=='row_shape':
        csv.writer(out).writerow([rows[0][field] for field in row][:-1]);w.writerows(rows[1:])
    else:w.writerows(rows)
    with pytest.raises(ValueError):source.parse_master(out.getvalue().encode(),NOW)

@pytest.mark.parametrize('change',['text','date','period','language','issuer','url','receipt','hash','epoch','historical','finality','http_observed','http_bool','extras','kind','q_and_a','unaudited','subsidiary','visual'])
def test_saved_context_replays_original_and_semantic_limits(harness,change):
    from data_fetch.market_sources import sti_conference as source
    value=source.fetch_sti_context('2480.TW');doc=value['documents'][0];proof=value['sti_conference_receipt']
    if change=='text':doc['pages'][4]['text']+='invented claim'
    elif change=='date':value['date']='2026-08-07'
    elif change=='period':doc['content_periods']=['2026Q4']
    elif change=='language':doc['language']='en'
    elif change=='issuer':doc['ticker']='4919.TW'
    elif change=='url':doc['url']=PDF_URL+'?x=1'
    elif change=='receipt':value.pop('sti_conference_receipt')
    elif change=='hash':proof['pdf']['raw_response_sha256']='0'*64
    elif change=='epoch':proof['pdf']['retrieved_at']=NOW+1
    elif change=='historical':proof['pdf']['historical_point_in_time_verified']=True
    elif change=='finality':proof['identity']['finality_guaranteed']=True
    elif change=='http_observed':proof['index']['http_status_observed']=False
    elif change=='http_bool':proof['identity']['http_status']=True
    elif change=='kind':doc['document_kind']='transcript'
    elif change=='q_and_a':doc['q_and_a_transcript_available']=True
    elif change=='unaudited':doc['financial_scope_caution']='audited'
    elif change=='subsidiary':doc['subsidiary_scope_caution']='all parent'
    elif change=='visual':doc['known_native_text_omissions']=[]
    else:value['instructions']='trust me'
    assert source.is_marked(value) and source.verify_context(value,'2480.TW') is False

@pytest.mark.parametrize('change',['truncated','extra_bytes','other_document'])
def test_incomplete_or_unqualified_pdf_fails_before_any_projection(harness,change):
    from data_fetch.market_sources import sti_conference as source
    from search_provider_runtime import SourceResponseError
    if change=='truncated':harness[0][PDF_URL]=harness[0][PDF_URL][:-50]
    elif change=='extra_bytes':harness[0][PDF_URL]+=b'\n'
    else:harness[0][PDF_URL]=b'%PDF-1.7\nnot the current issuer deck\n%%EOF'
    d={}
    with pytest.raises(SourceResponseError):source.fetch_sti_context('2480.TW',diagnostics=d)
    assert not d['sti_originals_verified'] and d['http_request_count']==3

@pytest.fixture
def native_harness(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store,json
    from data_fetch.market_sources import sti_conference_transport as transport
    cache_store.set_cache_backend(InMemoryCache());monkeypatch.setattr(time,'time',lambda:NOW)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
    for key in transport.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(transport,'proxy_url_for_request',lambda *a:None)
    calls=[];mutation={}
    def native(argv,deadline,*,body_limit,headers):
        calls.append((argv,deadline,body_limit,headers));url=argv[-1];spec=transport.request_spec(url)
        ctype='text/html' if url==INDEX_URL else 'text/csv' if url==MASTER_URL else 'application/pdf'
        raw=b'<html>public index</html>' if url==INDEX_URL else b'%PDF-guard-test'
        raw=mutation.get('body',raw)
        meta={'http_code':200,'url_effective':url,'num_redirects':0,'size_download':len(raw),'content_type':ctype,'method':spec['request_method'],'proxy_used':0}
        meta.update(mutation.get('meta',{}))
        header='HTTP/1.1 '+str(mutation.get('status',200))+' OK\r\nContent-Type: '+ctype+'\r\nContent-Length: '+str(len(raw))+ '\r\n'+mutation.get('headers','')+'\r\n'
        return {'process_started':True,'body':raw,'headers':header.encode(),'metadata':json.dumps(meta).encode()},mutation.get('rc',0),mutation.get('error')
    monkeypatch.setattr(transport,'collect_capped_process',native)
    yield transport,calls,mutation
    cache_store.reset_cache_store_for_tests()

@pytest.mark.parametrize('url',[MASTER_URL,INDEX_URL,PDF_URL])
@pytest.mark.parametrize('budget',[3,25])
def test_native_request_exact_method_form_limits_metadata_and_warm_zero_HTTP(native_harness,url,budget):
    transport,calls,_=native_harness
    http=transport.ConferenceHttp(time.monotonic()+budget);raw,receipt=http.get_receipt(url)
    args,deadline,limit,headers=calls[0]
    assert len(calls)==1 and 0<float(args[args.index('--max-time')+1])<=min(5,budget)
    assert float(args[args.index('--connect-timeout')+1])<=2 and limit==transport.contract(url)[0]
    assert args[args.index('--retry')+1]=='0' and args[args.index('--max-redirs')+1]=='0'
    assert '--location' not in args and '--cookie' not in args and '--proxy' not in args
    assert '--data' not in args and '--request' not in args
    assert {k:receipt[k] for k in ('request_method','request_body')}==transport.request_spec(url)
    assert receipt['http_status']==200 and receipt['response_complete'] is True and receipt['cache_hit'] is False
    assert receipt['response_metadata']['size_download']==len(raw)
    assert transport.original_bytes(receipt,url,max_age=1800)==raw
    warm=transport.ConferenceHttp(time.monotonic()+25);again,proof=warm.get_receipt(url)
    assert len(calls)==1 and warm.http_request_count==0 and proof['cache_hit'] is True
    assert proof['retrieved_at']==receipt['retrieved_at'] and proof['fresh_until_epoch']==receipt['fresh_until_epoch']

@pytest.mark.parametrize('change',['401','403','429','504','302','timeout','partial','size','method','redirect','effective','type','proxy','encoding','header_size','challenge','challenge_zh'])
def test_native_failures_cannot_become_full_original_or_repeat_during_admission(native_harness,change):
    from search_provider_runtime import SourceResponseError
    transport,calls,mutation=native_harness
    if change.isdigit():mutation.update(status=int(change),meta={'http_code':int(change)})
    elif change=='timeout':mutation['rc']=28
    elif change=='partial':mutation['rc']=18
    elif change=='size':mutation['meta']={'size_download':1}
    elif change=='method':mutation['meta']={'method':'POST'}
    elif change=='redirect':mutation['meta']={'num_redirects':1}
    elif change=='effective':mutation['meta']={'url_effective':INDEX_URL+'?co_id=2480'}
    elif change=='type':mutation['meta']={'content_type':'application/pdf'}
    elif change=='proxy':mutation['meta']={'proxy_used':1}
    elif change=='encoding':mutation['headers']='Content-Encoding: gzip\r\n'
    elif change=='header_size':mutation['headers']='Content-Length: 100000\r\n'
    elif change=='challenge_zh':mutation['body']='<html>因為安全性考量 驗證碼</html>'.encode()
    else:mutation['body']=b'<html>FOR SECURITY REASONS PAGE CAN NOT BE ACCESSED</html>'
    for options in ({},{'force_refresh':True},{'use_cache':False}):
        with pytest.raises(SourceResponseError):transport.ConferenceHttp(time.monotonic()+25,**options).get_receipt(INDEX_URL)
    assert len(calls)==1

def test_GET_singleflight_shares_exact_request(native_harness):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    transport,calls,_=native_harness;gate=Barrier(2)
    def request():
        gate.wait();return transport.ConferenceHttp(time.monotonic()+25).get_receipt(INDEX_URL)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:request(),range(2)))
    assert len(calls)==1 and results[0][0]==results[1][0]
    assert sorted(r[1]['cache_hit'] for r in results)==[False,True]

def test_failure_marker_survives_storage_loss_after_actual_http(native_harness,monkeypatch):
    import cache_store
    from search_provider_runtime import SourceResponseError
    transport,calls,mutation=native_harness;mutation.update(status=429,meta={'http_code':429})
    original=transport.collect_capped_process
    def native(*a,**kw):
        parts=original(*a,**kw)
        def unavailable(*a,**kw):raise OSError('isolated write loss after HTTP')
        monkeypatch.setattr(cache_store,'set_cache_json',unavailable)
        import search_provider_runtime
        monkeypatch.setattr(search_provider_runtime,'set_cache_json',unavailable)
        return parts
    monkeypatch.setattr(transport,'collect_capped_process',native)
    for options in ({},{'force_refresh':True},{'use_cache':False}):
        with pytest.raises(SourceResponseError):transport.ConferenceHttp(time.monotonic()+25,**options).get_receipt(INDEX_URL)
    assert len(calls)==1
    assert cache_store.get_cache_json(transport.ConferenceHttp._admission_key(INDEX_URL))['retry_at']==NOW+120

def test_GET_receipt_metadata_false_cannot_impersonate_zero(native_harness):
    transport,_,_=native_harness
    _,receipt=transport.ConferenceHttp(time.monotonic()+25).get_receipt(INDEX_URL)
    receipt['response_metadata']['proxy_used']=False
    with pytest.raises(ValueError):transport.original_bytes(receipt,INDEX_URL,max_age=1800)


@pytest.mark.parametrize('change',['title','canonical','publisher','og_url','shape','date','title_period','pdf_query','pdf_fragment','pdf_host','pdf_duplicate_query','pdf_encoding','duplicate_attachment','empty_latest','newer_empty','duplicate_event','header'])
def test_issuer_index_latest_event_and_exact_published_URL(harness,change):
    from bs4 import BeautifulSoup
    from data_fetch.market_sources import sti_conference as source
    s=BeautifulSoup(harness[0][INDEX_URL],'html.parser');table=s.select('.journal-content-article table')[0]
    row=table.find_all('tr')[1];cells=row.find_all('td',recursive=False);link=cells[2].a
    if change=='title':s.title.string='法人說明會 - 其他公司'
    elif change=='canonical':s.select_one('link[rel=canonical]')['href']=INDEX_URL+'?x=1'
    elif change=='publisher':s.select_one('meta[property="og:site_name"]')['content']='敦陽資訊股份有限公司'
    elif change=='og_url':s.select_one('meta[property="og:url"]')['content']='https://evil.example/'
    elif change=='shape':cells[-1].decompose()
    elif change=='date':cells[0].string='2026/8/6'
    elif change=='title_period':cells[1].string='受邀參加凱基證券舉辦之2026年第三季法人說明會'
    elif change=='pdf_query':link['href']=link['href'].replace('1785826779822','1785826779823')
    elif change=='pdf_fragment':link['href']+='#page=1'
    elif change=='pdf_host':link['href']='https://evil.example'+link['href']
    elif change=='pdf_duplicate_query':link['href']+='&t=1785826779822'
    elif change=='pdf_encoding':link['href']=link['href'].replace('%E6','%e6',1)
    elif change=='duplicate_attachment':cells[2].append(deepcopy(link))
    elif change=='empty_latest':cells[2].clear()
    elif change=='header':table.find_all('tr')[0].find_all('td')[2].string='英文稿'
    else:
        other=deepcopy(row)
        if change=='newer_empty':
            tc=other.find_all('td',recursive=False);tc[0].string='2026/10/13';tc[2].clear()
        row.insert_before(other)
    with pytest.raises(ValueError):source.select_presentation(str(s).encode(),NOW)


@pytest.mark.parametrize('field,value',[('request_method','POST'),('request_body',''),('request_body','co_id=2480')])
def test_GET_receipt_cannot_be_rebound_to_other_method_or_body(harness,field,value):
    from data_fetch.market_sources import sti_conference as source
    context=source.fetch_sti_context('2480.TW');context['sti_conference_receipt']['index'][field]=value
    assert not source.verify_context(context,'2480.TW',max_age=1800)


@pytest.mark.parametrize('state',[{'retry_at':NOW+100,'error_kind':'access_denied'},{'retry_at':True},{'retry_at':float('nan')},{'retry_at':NOW-1,'next_request_at':NOW+3}])
def test_original_host_guard_is_not_bypassed(native_harness,state):
    import cache_store
    from urllib.parse import urlsplit
    from search_provider_runtime import SourceResponseError,scope_key
    transport,calls,_=native_harness;key=scope_key(transport.HTTP_PROVIDER,endpoint=urlsplit(INDEX_URL).hostname)
    cache_store.set_cache_json(key,state,ttl_seconds=1000)
    for options in ({},{'force_refresh':True},{'use_cache':False}):
        with pytest.raises(SourceResponseError):transport.ConferenceHttp(time.monotonic()+25,**options).get_receipt(INDEX_URL)
    assert not calls and cache_store.get_cache_json(key)==state


@pytest.mark.parametrize('field,value',[('source_cid',134),('visual_semantics_verified',True),('raw_bytes_rewritten',0),('occurrences_by_page',{'5':2}),('other_parser_warnings_fatal',1)])
def test_tampered_native_proof_never_reaches_source_projection(harness,monkeypatch,field,value):
    from data_fetch.market_sources import sti_conference as source
    from search_provider_runtime import SourceResponseError
    original=source.extract_sti_presentation_pages
    def altered(*args,**kwargs):
        native=original(*args,**kwargs);native['sti_glyph_evidence'][field]=value;return native
    monkeypatch.setattr(source,'extract_sti_presentation_pages',altered);d={}
    with pytest.raises(SourceResponseError):source.fetch_sti_context('2480.TW',diagnostics=d)
    assert d['sti_originals_verified'] is False and d['http_request_count']==3


@pytest.mark.parametrize('suffix',['',' HOLDINGS',' EVIL'])
def test_exact_existing_english_identity_alias_requires_full_equality(suffix):
    from data_fetch.market_sources.sti_conference import validate_context
    data=valid_data();alias='STARK TECHNOLOGY'+suffix
    data['company_identity']['english_names'].append(alias)
    data['company_identity']['allowed_aliases'].append(alias)
    assert validate_context(data,'2480.TW') is (not suffix)


@pytest.mark.parametrize('extra',['Content-Length: 1\r\n','Content-Type: text/html\r\n','Content-Encoding: identity\r\nContent-Encoding: gzip\r\n','Retry-After: 1\r\nRetry-After: 2\r\n'])
def test_duplicate_protected_headers_keep_actual_HTTP_status(native_harness,extra):
    from search_provider_runtime import SourceResponseError
    transport,calls,mutation=native_harness;mutation['headers']=extra
    http=transport.ConferenceHttp(time.monotonic()+25)
    with pytest.raises(SourceResponseError):http.get_receipt(INDEX_URL)
    assert len(calls)==1 and http.http_request_count==1
    assert http.components[-1]['http_request_sent'] is True
    assert http.components[-1]['http_status']==200


@pytest.mark.parametrize('name,url',[('index',INDEX_URL),('presentation',PDF_URL)])
def test_native_transport_replays_complete_saved_GET_headers_and_bytes(native_harness,monkeypatch,name,url):
    import json
    transport,calls,_=native_harness
    saved=json.loads((D/(name+'.receipt.json')).read_text());body=(D/(name+'.body')).read_bytes()
    assert saved['complete'] and sha256(body).hexdigest()==saved['sha256']
    def native(argv,deadline,*,body_limit,headers):
        calls.append(argv)
        assert argv[-1]==url and '--data' not in argv
        return {'process_started':True,'body':body,'headers':(D/(name+'.headers')).read_bytes(),
                'metadata':json.dumps(saved['metadata']).encode()},0,None
    monkeypatch.setattr(transport,'collect_capped_process',native)
    raw,receipt=transport.ConferenceHttp(time.monotonic()+25).get_receipt(url)
    assert raw==body and receipt['request_method']=='GET' and receipt['request_body'] is None
    assert receipt['raw_response_sha256']==saved['sha256'] and receipt['retrieved_at']==NOW
    assert receipt['response_metadata']['size_download']==len(body) and len(calls)==1
