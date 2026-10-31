from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import base64
import time
import pytest
from data_fetch.market_sources.chipmos_conference_transport import MASTER_URL, INDEX_URL, PDF_URL

ROOT = Path(__file__).parents[1]
D = ROOT / 'docs/evidence/source-acquisition/20261014/source-gap-priorities/chipmos-source'
MASTER_FILE = ROOT / 'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
INDEX_FILE = ROOT / 'tests/fixtures/source_acquisition/chipmos_conference_20261014_index.html'
NOW = 1791926000.0

@pytest.fixture
def harness(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch.market_sources.chipmos_conference_transport import ConferenceHttp
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time,'time',lambda:NOW)
    bodies={MASTER_URL:MASTER_FILE.read_bytes(), INDEX_URL:INDEX_FILE.read_bytes(), PDF_URL:(D/'transcript-2026q2.body').read_bytes()}
    calls=[]
    def download(self,url,diagnostic):
        raw=bodies[url];calls.append(url);self.http_request_count+=1
        diagnostic.update(http_request_sent=True,http_status=200,status='complete',response_bytes=len(raw),response_sha256=sha256(raw).hexdigest())
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),'http_status':200,
                'response_complete':True,'request_method':'GET','http_status_observed':True,'fetched_at_epoch':time.time()}
    monkeypatch.setattr(ConferenceHttp,'download_original',download)
    yield bodies,calls
    cache_store.reset_cache_store_for_tests()


def test_public_chipmos_context_returns_complete_translated_original_with_limits(harness):
    from data_fetch.market_sources.chipmos_conference import fetch_chipmos_context
    diagnostic={};value=fetch_chipmos_context('8150.TW',diagnostics=diagnostic)
    assert value.get('documents'), 'published ChipMOS translated transcript must fill the actual metadata-only body gap'
    doc=value['documents'][0]
    assert value['date']==doc['event_date']=='2026-08-11'
    assert value['period']==doc['content_period']=='2026Q2' and doc['event_time_Taipei']=='15:00'
    assert doc['page_count']==8 and len(doc['pages'])==8
    assert doc['document_kind']=='transcript' and doc['projection_policy']=='chipmos-translated-transcript-role-v1'
    assert doc['language']=='en' and doc['translated_from_language']=='zh-TW'
    assert not doc['translation_accuracy_verified'] and not doc['transcript_accuracy_independently_verified']
    assert doc['published_at'] is None and doc['material_file_date'] is None
    assert value['coverage_status']==doc['coverage_status']=='partial' and not doc['full_content_coverage_verified']
    assert value['transcript_available'] and doc['native_text_coverage']=='complete'
    assert 'DISCLAIMER' in doc['pages'][6]['text'] and 'MATERIAL ERRORS' in doc['pages'][7]['text']
    assert harness[1]==[MASTER_URL,INDEX_URL,PDF_URL]
    assert diagnostic['http_request_count']==3 and diagnostic['chipmos_originals_verified'] is True
    from data_fetch.market_sources.chipmos_conference import verify_context
    assert verify_context(value,'8150.TW',max_age=1800)

@pytest.mark.parametrize('ticker',['8150.TWO','8151.TW','bad',None,8150])
def test_wrong_market_or_issuer_never_requests(harness,ticker):
    from data_fetch.market_sources.chipmos_conference import fetch_chipmos_context
    assert fetch_chipmos_context(ticker)=={} and not harness[1]


def valid_data():
    return {'ticker':'8150.TW','quote_type':'EQUITY','company_name':'南茂 / ChipMOS TECHNOLOGIES INC.',
            'company_identity':{'stock_id':'8150','official_name':'南茂','legal_name':None,
                'allowed_aliases':['南茂','8150','8150.TW','南茂 / ChipMOS TECHNOLOGIES INC.'],
                'english_names':['ChipMOS TECHNOLOGIES INC.','CHIPMOS TECHNOLOGIES INC'],'forbidden_aliases':[]}}


@pytest.mark.parametrize('elapsed,kind',[(24.,'cache_receipt_invalid'),(25.,'timeout'),(26.,'timeout')])
def test_late_receipt_storage_failure_preserves_cause_and_http_truth(harness,monkeypatch,elapsed,kind):
    import cache_store
    from data_fetch.market_sources import chipmos_conference as source
    from data_fetch.market_sources.chipmos_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    source.fetch_chipmos_context('8150.TW');harness[1].clear()
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
        source.fetch_chipmos_context('8150.TW',diagnostics=diagnostic)
    assert error.value.error_kind==diagnostic['error_kind']==kind
    chain=[];current=error.value
    while current is not None:
        chain.append(current);current=current.__cause__
    assert chain[-1] is cause
    assert any(isinstance(exc,SourceResponseError) and exc.error_kind=='cache_receipt_invalid' for exc in chain)
    assert all(error.value.diagnostic.get(key)==value for key,value in diagnostic.items())
    assert diagnostic['chipmos_originals_verified'] is False
    assert diagnostic['http_request_count']==0 and diagnostic['http_request_sent'] is False
    assert len(diagnostic['component_statuses'])==1
    assert diagnostic['component_statuses'][0]['cache_hit'] is True
    assert len(reads)==2 and not harness[1]

@pytest.mark.parametrize('change',['ticker','instrument_type','quote_type','quoteType','stock_id','official_ubn','legal_name','forbidden','allowed','english','badlist','identity','name','raw_name'])
def test_caller_identity_fail_closed(change):
    from data_fetch.market_sources.chipmos_conference import validate_context
    data=valid_data();assert validate_context(data,'8150.TW')
    if change=='ticker':data['ticker']='8150.TWO'
    elif change in {'instrument_type','quote_type','quoteType'}:data[change]='ETF'
    elif change=='stock_id':data['company_identity'][change]='8151'
    elif change=='official_ubn':data['company_identity'][change]='00000000'
    elif change=='legal_name':data['company_identity'][change]='其他公司'
    elif change=='forbidden':data['company_identity']['forbidden_aliases']=['*ChipMOS*']
    elif change=='allowed':data['company_identity']['allowed_aliases']+=['華邦電']
    elif change=='english':data['company_identity']['english_names']=['Winbond']
    elif change=='badlist':data['company_identity']['allowed_aliases']='南茂'
    elif change=='identity':data['company_identity']=False
    elif change=='name':data['company_name']='南茂 / 其他公司'
    else:data['raw_company_name']='Other Corp'
    assert not validate_context(data,'8150.TW')


@pytest.mark.parametrize('change',['ticker','legal','short','ubn','english','domain','partial','duplicate','future','old'])
def test_current_complete_master_binds_exact_issuer(harness,change):
    import csv,io
    from data_fetch.market_sources import chipmos_conference as source
    raw=harness[0][MASTER_URL];rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))));r=next(r for r in rows if r['公司代號']=='8150')
    bad={'ticker':('公司代號','8151'),'legal':('公司名稱','他公司'),'short':('公司簡稱','南茂別名'),'ubn':('營利事業統一編號','16130043'),'english':('英文簡稱','ChipMOS Subsidiary'),'domain':('網址','www.chipmos.com.evil.example'),'future':('出表日期','1151015'),'old':('出表日期','1150901')}
    if change in bad:r[bad[change][0]]=bad[change][1]
    elif change=='partial':rows=[r]
    else:rows.append(deepcopy(r))
    o=io.StringIO();w=csv.DictWriter(o,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    with pytest.raises(ValueError):source.parse_master(o.getvalue().encode(),NOW)


@pytest.mark.parametrize('old,new',[(b'2026-8-11 03:00PM',b'2026-8-12 03:00PM'),(b'2026-08-11',b'2026-08-12'),
    (b'3:00PM',b'4:00PM'),(b'Second Quarter 2026 Results Conference Call',b'First Quarter 2026 Results Conference Call'),
    (b'English Translated Transcript:',b'English Presentation:'),(b'Mandarin (English Translated Replay)',b'English'),
    (b'en_pdf_1857263878.pdf',b'en_pdf_1857263878.pdf?download=1'),
    (b'../../upfiles/ADUpload/english/en_pdf_1857263878.pdf',b'https://other.example/transcript.pdf'),
    (b'(TWSE: 8150)',b'(TWSE: 8151)')])
def test_index_role_date_time_language_route_and_issuer_bound(harness,old,new):
    from data_fetch.market_sources import chipmos_conference as source
    assert old in harness[0][INDEX_URL]
    with pytest.raises(ValueError):source.select_transcript(harness[0][INDEX_URL].replace(old,new),NOW)


def test_newer_event_without_any_attachment_does_not_fallback_to_old_transcript(harness):
    from bs4 import BeautifulSoup
    from data_fetch.market_sources import chipmos_conference as source
    s=BeautifulSoup(harness[0][INDEX_URL],'html.parser');row=s.select('ul.ir-table.meeting.open')[0];new=deepcopy(row)
    cells=new.find_all('li',recursive=False);cells[0].string='2026 Q3 Results Conference Call';cells[1].string='2026-10-13';cells[2].string='3:00PM'
    for c in cells[3:]:c.clear()
    row.insert_before(new)
    with pytest.raises(ValueError):source.select_transcript(str(s).encode(),NOW)


def test_same_day_second_event_is_ambiguous(harness):
    from bs4 import BeautifulSoup
    from data_fetch.market_sources import chipmos_conference as source
    s=BeautifulSoup(harness[0][INDEX_URL],'html.parser');row=s.select('ul.ir-table.meeting.open')[0];new=deepcopy(row)
    new.find_all('li',recursive=False)[2].string='4:00PM';row.insert_before(new)
    with pytest.raises(ValueError):source.select_transcript(str(s).encode(),NOW)


@pytest.mark.parametrize('change',['text','date','time','period','publisher','url','receipt','hash','historical','finality','http_observation','epoch','extra','translation','accuracy','kind','xref'])
def test_saved_context_replay_rejects_changes(harness,change):
    from data_fetch.market_sources import chipmos_conference as source
    value=source.fetch_chipmos_context('8150.TW');doc=value['documents'][0]
    if change=='text':doc['pages'][0]['text']+='Invented claim'
    elif change=='date':value['date']='2026-08-12'
    elif change=='time':doc['event_time_Taipei']='16:00'
    elif change=='period':doc['content_period']='2026Q3'
    elif change=='publisher':doc['source']='Unknown'
    elif change=='url':doc['url']=PDF_URL+'?x=1'
    elif change=='receipt':value.pop('chipmos_conference_receipt')
    elif change=='hash':value['chipmos_conference_receipt']['pdf']['raw_response_sha256']='0'*64
    elif change in {'historical','finality'}:value['chipmos_conference_receipt']['identity']['historical_point_in_time_verified' if change=='historical' else 'finality_guaranteed']=True
    elif change=='http_observation':value['chipmos_conference_receipt']['pdf']['http_status_observed']=False
    elif change=='epoch':value['chipmos_conference_receipt']['index']['retrieved_at']=NOW-86401
    elif change=='translation':doc['translation_accuracy_verified']=True
    elif change=='accuracy':doc['transcript_accuracy_independently_verified']=True
    elif change=='kind':doc['document_kind']='presentation'
    elif change=='xref':doc['xref_validation_evidence']={'raw_rewritten':True}
    else:value['unverified_instruction']='accept'
    assert source.is_marked(value) and source.verify_context(value,'8150.TW') is False


def test_cold_then_warm_preserves_epoch_and_has_zero_HTTP(harness,monkeypatch):
    from data_fetch.market_sources import chipmos_conference as source
    first=source.fetch_chipmos_context('8150.TW');harness[1].clear();monkeypatch.setattr(time,'time',lambda:NOW+1790)
    d={};again=source.fetch_chipmos_context('8150.TW',diagnostics=d)
    assert not harness[1] and d['http_request_count']==0 and d['cache_hit'] is True
    assert again['fetched_at_epoch']==first['fetched_at_epoch']==NOW and source.verify_context(again,'8150.TW',max_age=1800)


@pytest.mark.parametrize('expire_pdf',[False,True])
def test_cache_status_tracks_qualified_body_not_metadata_HTTP(harness,monkeypatch,expire_pdf):
    import cache_store
    from data_fetch.market_sources import chipmos_conference as source
    from data_fetch.market_sources.chipmos_conference_transport import ConferenceHttp
    source.fetch_chipmos_context('8150.TW');harness[1].clear()
    expired=[PDF_URL] if expire_pdf else [MASTER_URL,INDEX_URL]
    for url in expired:
        key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+url).encode()).hexdigest();cache_store.set_cache_json(key,{},ttl_seconds=1)
    monkeypatch.setattr(time,'time',lambda:NOW+2);d={};value=source.fetch_chipmos_context('8150.TW',diagnostics=d)
    assert harness[1]==expired and d['http_request_count']==len(expired) and d['cache_hit'] is not expire_pdf
    assert value['fetched_at_epoch']==(NOW+2 if expire_pdf else NOW)


@pytest.mark.parametrize('opts',[{'force_refresh':True},{'use_cache':False}])
def test_force_or_uncached_refreshes_all_three_originals(harness,opts):
    from data_fetch.market_sources import chipmos_conference as source
    source.fetch_chipmos_context('8150.TW');harness[1].clear();source.fetch_chipmos_context('8150.TW',**opts)
    assert harness[1]==[MASTER_URL,INDEX_URL,PDF_URL]


@pytest.mark.parametrize('warm',[False,True])
def test_reader_timeout_preserves_real_HTTP_and_no_success(harness,monkeypatch,warm):
    from data_fetch.market_sources import chipmos_conference as source
    from source_pdf_reader import SourcePdfError
    from search_provider_runtime import SourceResponseError
    if warm:source.fetch_chipmos_context('8150.TW');harness[1].clear()
    def timeout(*a,**kw):raise SourcePdfError('timeout')
    monkeypatch.setattr(source,'extract_chipmos_transcript_pages',timeout);d={}
    with pytest.raises(SourceResponseError) as err:source.fetch_chipmos_context('8150.TW',diagnostics=d)
    assert err.value.error_kind=='timeout' and d['status']=='error' and d['chipmos_originals_verified'] is False
    assert d['http_request_count']==(0 if warm else 3) and 'coverage_status' not in d


@pytest.mark.parametrize('stage',['reader','equality','handoff','components'])
def test_total_deadline_includes_all_parsing_projection_and_copy(harness,monkeypatch,stage):
    from data_fetch.market_sources import chipmos_conference as source
    from search_provider_runtime import SourceResponseError
    from types import SimpleNamespace
    clock=[time.monotonic()];expired=clock[0]+26
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=lambda:NOW))
    if stage=='reader':
        original=source.extract_chipmos_transcript_pages
        def delayed(*a,**kw):v=original(*a,**kw);clock[0]=expired;return v
        monkeypatch.setattr(source,'extract_chipmos_transcript_pages',delayed)
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
    with pytest.raises(SourceResponseError) as err:source.fetch_chipmos_context('8150.TW')
    assert err.value.error_kind=='timeout'


@pytest.mark.parametrize('stage',['reader','equality','handoff','components'])
def test_original_TTL_is_checked_after_final_work(harness,monkeypatch,stage):
    from data_fetch.market_sources import chipmos_conference as source
    from search_provider_runtime import SourceResponseError
    source.fetch_chipmos_context('8150.TW');harness[1].clear();clock=[NOW+1799]
    monkeypatch.setattr(time,'time',lambda:clock[0])
    if stage=='reader':
        original=source.extract_chipmos_transcript_pages
        def delayed(*a,**kw):v=original(*a,**kw);clock[0]=NOW+1800;return v
        monkeypatch.setattr(source,'extract_chipmos_transcript_pages',delayed)
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
    with pytest.raises(SourceResponseError):source.fetch_chipmos_context('8150.TW',diagnostics=d)
    assert not harness[1] and d['status']=='error' and not d['chipmos_originals_verified']

@pytest.mark.parametrize('kind',['timeout','access_denied','rate_limited'])
def test_error_admission_blocks_normal_force_and_uncached_without_repeat_HTTP(harness,monkeypatch,kind):
    from data_fetch.market_sources import chipmos_conference as source
    from data_fetch.market_sources.chipmos_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    calls=[]
    def bad(self,url,diagnostic):
        self.http_request_count+=1;calls.append(url);diagnostic.update(http_request_sent=True)
        raise SourceResponseError(kind)
    monkeypatch.setattr(ConferenceHttp,'download_original',bad)
    for opts in ({},{'force_refresh':True},{'use_cache':False}):
        d={}
        with pytest.raises(SourceResponseError):source.fetch_chipmos_context('8150.TW',diagnostics=d,**opts)
        assert not d['chipmos_originals_verified'] and d['status']=='error'
    assert calls==[MASTER_URL]


def test_cooldown_storage_not_writable_sends_zero_HTTP(harness,monkeypatch):
    import cache_store
    from data_fetch.market_sources import chipmos_conference as source
    from search_provider_runtime import SourceResponseError
    def bad(*a,**kw):raise OSError('read-only')
    monkeypatch.setattr(cache_store,'set_cache_json',bad)
    d={}
    with pytest.raises(SourceResponseError):source.fetch_chipmos_context('8150.TW',diagnostics=d)
    assert not harness[1] and d['http_request_count']==0 and not d['chipmos_originals_verified']


@pytest.mark.parametrize('url',[PDF_URL+'?x=1',PDF_URL+'#x',PDF_URL.replace('https:','http:'),PDF_URL.replace('www.chipmos.com','www.chipmos.com.evil.example'),INDEX_URL+'?YEAR=2026',MASTER_URL+'?x=1'])
def test_transport_only_exact_original_URLs(harness,url):
    from data_fetch.market_sources.chipmos_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):ConferenceHttp(time.monotonic()+25).get_receipt(url)
    assert not harness[1]


def test_simultaneous_master_requests_share_one_native_acquisition(harness):
    from concurrent.futures import ThreadPoolExecutor
    from data_fetch.market_sources.chipmos_conference_transport import ConferenceHttp
    from threading import Barrier
    gate=Barrier(2)
    def request():
        gate.wait();return ConferenceHttp(time.monotonic()+25).get_receipt(MASTER_URL)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:request(),range(2)))
    assert harness[1]==[MASTER_URL] and results[0][0]==results[1][0]
    assert sorted(v[1]['cache_hit'] for v in results)==[False,True]


@pytest.mark.parametrize('change',['truncated','different_document','extra_pdf_bytes'])
def test_incomplete_or_unknown_original_fails_before_projection(harness,change):
    from data_fetch.market_sources import chipmos_conference as source
    from search_provider_runtime import SourceResponseError
    if change=='truncated':harness[0][PDF_URL]=harness[0][PDF_URL][:-100]
    elif change=='different_document':harness[0][PDF_URL]=(D/'presentation-2026q2.body').read_bytes()
    else:harness[0][PDF_URL]+=b'\n'
    d={}
    with pytest.raises(SourceResponseError):source.fetch_chipmos_context('8150.TW',diagnostics=d)
    assert d['http_request_count']==3 and not d['chipmos_originals_verified']


def test_doc_boolean_flag_cannot_be_impersonated_by_integer(harness):
    from data_fetch.market_sources import chipmos_conference as source
    value=source.fetch_chipmos_context('8150.TW');value['documents'][0]['binary_complete']=1
    assert source.verify_context(value,'8150.TW') is False


@pytest.mark.parametrize('budget',[3,25])
def test_native_request_budget_no_retry_redirect_proxy_or_cookie(monkeypatch,budget):
    from cache_backends import InMemoryCache
    import cache_store,json
    from data_fetch.market_sources import issuer_news_transport as base
    from data_fetch.market_sources.chipmos_conference_transport import ConferenceHttp
    cache_store.set_cache_backend(InMemoryCache());calls=[]
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
    for key in base.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(base,'proxy_url_for_request',lambda *a:None)
    def native(argv,deadline,*,body_limit,headers):
        calls.append((argv,deadline,body_limit,headers));url=argv[-1]
        return {'process_started':True,'body':b'%PDF-guard-test','headers':b'HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\n\r\n',
                'metadata':json.dumps({'http_code':200,'url_effective':url,'num_redirects':0}).encode()},0,None
    monkeypatch.setattr(base,'collect_capped_process',native)
    http=ConferenceHttp(time.monotonic()+budget);raw,receipt=http.get_receipt(PDF_URL)
    argv,deadline,limit,headers=calls[0]
    assert len(calls)==1 and 0<float(argv[argv.index('--max-time')+1])<=min(5,budget)
    assert float(argv[argv.index('--connect-timeout')+1])<=2 and limit==8*1024*1024
    assert argv[argv.index('--retry')+1]=='0' and argv[argv.index('--max-redirs')+1]=='0'
    assert '--location' not in argv and '--cookie' not in argv and '--proxy' not in argv
    assert receipt['http_status']==200 and receipt['response_complete'] is True and receipt['cache_hit'] is False
    cache_store.reset_cache_store_for_tests()

@pytest.mark.parametrize('url',[MASTER_URL,INDEX_URL,PDF_URL])
@pytest.mark.parametrize('stage',['reader','handoff'])
def test_shorter_shared_expiry_cannot_cross_projection_or_delivery(harness,monkeypatch,url,stage):
    import cache_store
    from data_fetch.market_sources import chipmos_conference as source
    from data_fetch.market_sources.chipmos_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    source.fetch_chipmos_context('8150.TW');harness[1].clear()
    key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+url).encode()).hexdigest()
    row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+2;cache_store.set_cache_json(key,row,ttl_seconds=1800)
    clock=[NOW+1];monkeypatch.setattr(time,'time',lambda:clock[0])
    if stage=='reader':
        original=source.extract_chipmos_transcript_pages
        def delayed(*a,**kw):v=original(*a,**kw);clock[0]=NOW+3;return v
        monkeypatch.setattr(source,'extract_chipmos_transcript_pages',delayed)
    else:
        original=source.deepcopy
        def delayed(value):
            v=original(value)
            if isinstance(value,dict) and 'documents' in value:clock[0]=NOW+3
            return v
        monkeypatch.setattr(source,'deepcopy',delayed)
    d={}
    with pytest.raises(SourceResponseError):source.fetch_chipmos_context('8150.TW',diagnostics=d)
    assert not harness[1] and not d['chipmos_originals_verified']


def test_shorter_cache_expiry_is_preserved_without_epoch_renewal(harness,monkeypatch):
    import cache_store
    from data_fetch.market_sources import chipmos_conference as source
    from data_fetch.market_sources.chipmos_conference_transport import ConferenceHttp
    source.fetch_chipmos_context('8150.TW');harness[1].clear()
    key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+PDF_URL).encode()).hexdigest()
    row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+10;cache_store.set_cache_json(key,row,ttl_seconds=1800)
    monkeypatch.setattr(time,'time',lambda:NOW+5);d={};value=source.fetch_chipmos_context('8150.TW',diagnostics=d)
    proof=value['chipmos_conference_receipt']['pdf']
    assert proof['retrieved_at']==value['fetched_at_epoch']==NOW and proof['fresh_until_epoch']==NOW+10
    assert not harness[1] and d['cache_hit'] is True and d['http_request_count']==0
    monkeypatch.setattr(time,'time',lambda:NOW+10)
    assert source.verify_context(value,'8150.TW') is False


@pytest.mark.parametrize('expiry',[True,float('inf'),float('nan'),-1,NOW,NOW+1801,'1791927800',10**500])
def test_invalid_or_extended_receipt_expiry_is_rejected(harness,expiry):
    from data_fetch.market_sources import chipmos_conference as source
    value=source.fetch_chipmos_context('8150.TW');value['chipmos_conference_receipt']['pdf']['fresh_until_epoch']=expiry
    assert source.verify_context(value,'8150.TW') is False


@pytest.mark.parametrize('change',['display_name','combined_forbidden'])
def test_explicit_identity_display_and_combined_forbidden_alias_are_bound(change):
    from data_fetch.market_sources.chipmos_conference import validate_context
    data=valid_data()
    if change=='display_name':data['company_identity']['display_name']='華邦電'
    else:data['company_identity']['forbidden_aliases']=['南茂 / ChipMOS']
    assert not validate_context(data,'8150.TW')


def test_complete_archive_is_revalidated_after_final_copy(harness,monkeypatch):
    from data_fetch.market_sources import chipmos_conference as source
    from search_provider_runtime import SourceResponseError
    original=source.deepcopy;saved={}
    def corrupt_at_handoff(value):
        copied=original(value)
        if isinstance(value,dict) and 'chipmos_conference_receipt' in value:
            path=Path(value['chipmos_conference_receipt']['pdf']['raw_response_path'])
            saved[path]=path.read_bytes();path.write_bytes(b'corrupt gzip')
        return copied
    monkeypatch.setattr(source,'deepcopy',corrupt_at_handoff);d={}
    try:
        with pytest.raises(SourceResponseError):source.fetch_chipmos_context('8150.TW',diagnostics=d)
        assert not d['chipmos_originals_verified']
    finally:
        for path,raw in saved.items():path.write_bytes(raw)


def test_receipt_alone_cannot_extend_saved_shorter_deadline(harness,monkeypatch):
    import cache_store
    from data_fetch.market_sources import chipmos_conference as source
    from data_fetch.market_sources.chipmos_conference_transport import ConferenceHttp
    source.fetch_chipmos_context('8150.TW');harness[1].clear()
    key='shared_provider:v1:'+sha256((ConferenceHttp.raw_cache_prefix+PDF_URL).encode()).hexdigest()
    row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+10;cache_store.set_cache_json(key,row,ttl_seconds=1800)
    monkeypatch.setattr(time,'time',lambda:NOW+5);value=source.fetch_chipmos_context('8150.TW')
    assert value['chipmos_conference_receipt']['pdf']['fresh_until_epoch']==NOW+10
    value['chipmos_conference_receipt']['pdf']['fresh_until_epoch']=NOW+20
    monkeypatch.setattr(time,'time',lambda:NOW+15)
    assert source.verify_context(value,'8150.TW',max_age=1800) is False
    assert not harness[1]


def test_newer_same_bytes_cache_row_cannot_renew_older_receipt(harness,monkeypatch):
    from data_fetch.market_sources import chipmos_conference as source
    from data_fetch.market_sources.chipmos_conference_transport import ConferenceHttp
    old=source.fetch_chipmos_context('8150.TW');harness[1].clear()
    monkeypatch.setattr(time,'time',lambda:NOW+5)
    raw,new=ConferenceHttp(time.monotonic()+25,force_refresh=True).get_receipt(PDF_URL)
    assert new['retrieved_at']==NOW+5 and old['chipmos_conference_receipt']['pdf']['retrieved_at']==NOW
    old['chipmos_conference_receipt']['pdf']['fresh_until_epoch']=NOW+1800
    assert source.verify_context(old,'8150.TW',max_age=1800) is False
    assert harness[1]==[PDF_URL]


@pytest.mark.parametrize('state',['missing','storage_unavailable'])
def test_saved_receipt_requires_independent_cache_observation(harness,monkeypatch,state):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import chipmos_conference as source
    value=source.fetch_chipmos_context('8150.TW');harness[1].clear()
    if state=='missing':cache_store.set_cache_backend(InMemoryCache())
    else:
        def unavailable(*args):raise RuntimeError('storage unavailable')
        monkeypatch.setattr(cache_store,'get_cache_json',unavailable)
    assert source.verify_context(value,'8150.TW',max_age=1800) is False
    assert not harness[1]


@pytest.mark.parametrize('change',['body','hash','epoch','url','http','complete','observed','deadline','future_observation'])
def test_replay_binds_strict_independent_raw_cache_metadata(harness,monkeypatch,change):
    import cache_store
    from data_fetch.market_sources import chipmos_conference as source
    from data_fetch.market_sources.chipmos_conference_transport import ConferenceHttp
    value=source.fetch_chipmos_context('8150.TW');harness[1].clear()
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
    assert source.verify_context(value,'8150.TW',max_age=1800) is False
    assert not harness[1]
