"""Public Lien Hwa collector; exact saved originals only, no runtime networking."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import base64,importlib,json,time
import pytest
ROOT=Path(__file__).parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261014/conference-resilience/lienhwa-research'
MASTER=ROOT/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
NOW=1791974000.0

def valid_data():
 return {'ticker':'1229.TW','company_name':'聯華 / Lien Hwa Industrial Holdings Corporation','raw_company_name':'Lien Hwa Industrial Holdings Corporation','instrument_type':'EQUITY','quote_type':'EQUITY','company_identity':{'ticker':'1229.TW','stock_id':'1229','official_name':'聯華','legal_name':'聯華實業控股股份有限公司','official_ubn':'11996904','instrument_type':'EQUITY','allowed_aliases':['聯華','LHIHC','1229.TW','1229'],'english_names':['Lien Hwa Industrial Holdings Corporation'],'forbidden_aliases':[]}}

@pytest.fixture
def harness(monkeypatch):
 import cache_store
 from cache_backends import InMemoryCache
 from data_fetch.market_sources import lienhwa_conference_transport as t
 cache_store.set_cache_backend(InMemoryCache());monkeypatch.setattr(time,'time',lambda:NOW)
 bodies={t.MASTER_URL:MASTER.read_bytes(),t.INDEX_URL:(D/'index.body').read_bytes(),t.EVENT_URL:(D/'event.body').read_bytes(),t.PDF_URL:(D/'material.body').read_bytes()};calls=[]
 def download(self,url,diagnostic):
  raw=bodies[url];calls.append(url);self.http_request_count+=1
  ctype='text/csv' if url==t.MASTER_URL else 'application/pdf' if url==t.PDF_URL else 'text/html'
  metadata={'http_status':200,'effective_url':url,'num_redirects':0,'size_download':len(raw),'content_type':ctype,'content_length':len(raw),'method':'GET','proxy_used':0,'cache_control':'no-cache'}
  if url==t.MASTER_URL:
   from data_fetch.market_sources import official_issuer_master
   metadata=official_issuer_master.master_metadata(metadata,raw,{})
  else:metadata.update(pragma='no-cache',expires='0',age=None,cf_cache_status='')
  diagnostic.update(http_request_sent=True,http_status=200,response_metadata=metadata)
  return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),'request_method':'GET','request_body':None,'response_metadata':metadata}
 monkeypatch.setattr(t.ConferenceHttp,'download_original',download)
 yield bodies,calls
 cache_store.reset_cache_store_for_tests()

def test_public_company_original_yields_only_qualified_partial_presentation(request):
 try:source=importlib.import_module('data_fetch.market_sources.lienhwa_conference')
 except ModuleNotFoundError as exc:
  if exc.name!='data_fetch.market_sources.lienhwa_conference':raise
  value={}
 else:
  fixture=request.getfixturevalue('harness');d={}
  value=source.fetch_lienhwa_context('1229.TW',diagnostics=d)
  assert source.validate_context(valid_data(),'1229.TW')
  assert d['http_request_count']==4 and d['lienhwa_originals_verified'] is True
  assert source.verify_context(value,'1229.TW',max_age=1800)
 docs=value.get('documents',[])
 assert len(docs)==1,'Saved official presentation has no implemented company-source collector'
 doc=docs[0]
 assert doc['page_count']==len(doc['pages'])==30 and doc['coverage_status']=='partial'
 assert doc['native_text_coverage']=='partial' and doc['missing_text_pages']==[2,3,6,11,12,21]
 assert doc['excluded_native_text_pages']==[15] and doc['role_page_allowlist']==[1,22,24,25]
 assert doc['q_and_a_transcript_available'] is False and doc['full_content_coverage_verified'] is False
 assert doc['event_date']=='2026-09-30' and doc['event_time']=='15:30' and doc['published_at'] is None
 assert doc['content_period']==value['period']==''

from data_fetch.market_sources.lienhwa_conference_transport import MASTER_URL,INDEX_URL,EVENT_URL,PDF_URL

def test_shared_private_master_keeps_new_pdf_as_one_fresh_body_acquisition(harness,monkeypatch):
    from data_fetch.market_sources import lienhwa_conference as source
    from data_fetch.market_sources.lienhwa_conference_transport import ConferenceHttp
    original=ConferenceHttp.download_original
    def private_master(self,url,diagnostic):
        value=original(self,url,diagnostic)
        if url==MASTER_URL:value['response_metadata']['cache_control']='private'
        return value
    monkeypatch.setattr(ConferenceHttp,'download_original',private_master)
    first=source.fetch_lienhwa_context('1229.TW')
    monkeypatch.setattr(time,'time',lambda:NOW+10)
    diagnostics={};second=source.fetch_lienhwa_context('1229.TW',force_refresh=True,diagnostics=diagnostics)
    assert harness[1]==[MASTER_URL,INDEX_URL,EVENT_URL,PDF_URL,INDEX_URL,EVENT_URL,PDF_URL]
    proof=second['lienhwa_conference_receipt']
    assert proof['identity']['cache_hit'] is True and proof['identity']['retrieved_at']==NOW
    assert proof['pdf']['cache_hit'] is False and proof['pdf']['retrieved_at']==NOW+10
    assert diagnostics['http_request_count']==3 and diagnostics['cache_hit'] is False
    assert diagnostics['fetched_at_epoch']==NOW+10 and diagnostics['lienhwa_originals_verified'] is True
    assert source.verify_context(first,'1229.TW',max_age=1800)
    assert source.verify_context(second,'1229.TW',max_age=1800)


def test_verify_final_expiry_does_not_add_unbudgeted_storage_after_last_deadline_check(harness,monkeypatch):
    import inspect
    from types import SimpleNamespace
    from data_fetch.market_sources import lienhwa_conference as source, official_issuer_master as master
    from data_fetch.market_sources.lienhwa_conference_transport import ConferenceHttp
    original=ConferenceHttp.download_original
    def private(self,url,diagnostic):
        value=original(self,url,diagnostic)
        if url==MASTER_URL:value['response_metadata']['cache_control']='private'
        return value
    monkeypatch.setattr(ConferenceHttp,'download_original',private)
    source.fetch_lienhwa_context('1229.TW')
    value=source.fetch_lienhwa_context('1229.TW')
    clock=[time.monotonic()];deadline=clock[0]+2
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=lambda:NOW))
    real=master._stored
    def slow_final_read():
        if any(frame.function=='_originals_fresh' for frame in inspect.stack()):clock[0]+=3
        return real()
    monkeypatch.setattr(master,'_stored',slow_final_read)
    assert source.verify_context(value,'1229.TW',deadline=deadline,max_age=1800)
    assert clock[0]<deadline, 'storage was added after the final caller deadline check'


@pytest.mark.parametrize('options',[{}, {'force_refresh':True}, {'use_cache':False}])
def test_no_store_does_not_reuse_old_raw_or_context(harness,monkeypatch,options):
    from data_fetch.market_sources import lienhwa_conference as source
    import cache_store
    first=source.fetch_lienhwa_context('1229.TW')
    monkeypatch.setattr(time,'time',lambda:NOW+10)
    second=source.fetch_lienhwa_context('1229.TW',**options)
    assert len(harness[1])==8 and second['fetched_at_epoch']==NOW+10
    assert first['fetched_at_epoch']==NOW
    entries=cache_store.get_cache_backend()._entries
    assert all('body_b64'not in str(row) and 'documents'not in str(row) for row in entries.values())
    assert source.verify_context(first,'1229.TW',max_age=1800)


@pytest.mark.parametrize('change',['root_name','alias','ubn','quote','forbidden','foreign_suffix'])
def test_identity_does_not_borrow_good_name_to_hide_contradiction(change):
    from data_fetch.market_sources.lienhwa_conference import validate_context
    v=valid_data()
    if change=='root_name':v['company_name']='ARES'
    elif change=='alias':v['company_identity']['english_names']={}
    elif change=='ubn':v['company_identity']['official_ubn']='00000000'
    elif change=='quote':v['quote_type']='ETF'
    elif change=='forbidden':v['company_identity']['forbidden_aliases']=['聯華']
    else:v['raw_company_name']='KINIK Electric Co.,Ltd. unrelated'
    assert not validate_context(v,'1229.TW')


@pytest.mark.parametrize('change',['expiry','epoch','cache','metadata','manifest','proof_bool','digit','semantics'])
def test_saved_original_replay_rejects_retiming_and_semantic_tamper(harness,change):
    from data_fetch.market_sources import lienhwa_conference as source
    v=source.fetch_lienhwa_context('1229.TW'); r=v['lienhwa_conference_receipt']['pdf']
    if change=='expiry':r['fresh_until_epoch']-=1
    elif change=='epoch':r['retrieved_at']+=1
    elif change=='cache':r['cache_hit']=True
    elif change=='metadata':r['response_metadata']['content_length']=1
    elif change=='manifest':r['acquisition_manifest']['raw_response_sha256']='0'*64
    elif change=='proof_bool':v['documents'][0]['lienhwa_glyph_evidence']['raw_bytes_rewritten']=0
    elif change=='digit':v['documents'][0]['pages'][6]['text']+=' 99999'
    else:v['documents'][0]['coverage_status']='complete'
    assert source.verify_context(v,'1229.TW',max_age=1800)is False


def test_failed_http_admission_keeps_120_seconds_even_force(harness,monkeypatch):
    from data_fetch.market_sources import lienhwa_conference as source
    from data_fetch.market_sources.lienhwa_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    calls=[]
    def fail(self,url,diagnostic):
        self.http_request_count+=1; calls.append(url); diagnostic['http_request_sent']=True
        raise SourceResponseError('rate_limited',status_code=429)
    monkeypatch.setattr(ConferenceHttp,'download_original',fail)
    for options in ({},{'force_refresh':True},{'use_cache':False}):
        with pytest.raises(SourceResponseError):source.fetch_lienhwa_context('1229.TW',**options)
    assert calls==[MASTER_URL]


@pytest.mark.parametrize('stage',['reader','handoff','components'])
def test_total_deadline_includes_projection_and_copy(harness,monkeypatch,stage):
    from data_fetch.market_sources import lienhwa_conference as source
    from search_provider_runtime import SourceResponseError
    from types import SimpleNamespace
    clock=[time.monotonic()];expired=clock[0]+26
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=lambda:NOW))
    if stage=='reader':
        real=source.extract_lienhwa_presentation_pages
        def delayed(*a,**k):v=real(*a,**k);clock[0]=expired;return v
        monkeypatch.setattr(source,'extract_lienhwa_presentation_pages',delayed)
    else:
        real=source.deepcopy
        def delayed(v):
            out=real(v)
            if stage=='handoff'and isinstance(v,dict)and'documents'in v or stage=='components'and isinstance(v,list):clock[0]=expired
            return out
        monkeypatch.setattr(source,'deepcopy',delayed)
    with pytest.raises(SourceResponseError)as e:source.fetch_lienhwa_context('1229.TW')
    assert e.value.error_kind=='timeout'


def test_historical_saved_replay_does_not_claim_current_acquisition(harness,monkeypatch):
    from data_fetch.market_sources import lienhwa_conference as source
    value=source.fetch_lienhwa_context('1229.TW')
    original=deepcopy(value)
    monkeypatch.setattr(time,'time',lambda:NOW+1801)
    assert source.verify_context(value,'1229.TW',max_age=1800)is False
    assert source.verify_context(value,'1229.TW',max_age=86400)is True
    assert value==original and len(harness[1])==4
    monkeypatch.setattr(time,'time',lambda:NOW+86400)
    assert source.verify_context(value,'1229.TW',max_age=86400)is False


def test_preplanted_success_cache_cannot_supply_lienhwa_body(harness):
    import cache_store
    from data_fetch.market_sources import lienhwa_conference as source
    from data_fetch.market_sources.lienhwa_conference_transport import ConferenceHttp
    key=ConferenceHttp.raw_cache_prefix+PDF_URL
    fake={'value':{'body_b64':'YmFk','fetched_at_epoch':NOW},'fetched_at_epoch':NOW,'fresh_until_epoch':NOW+1800}
    cache_store.set_cache_json(key,fake,ttl_seconds=1800)
    value=source.fetch_lienhwa_context('1229.TW')
    assert value['documents'][0]['page_count']==30 and len(harness[1])==4
    assert cache_store.get_cache_json(key)==fake


@pytest.mark.parametrize('advance',['budget','validation_age'])
def test_final_diagnostic_handoff_cannot_return_expired_success(harness,monkeypatch,advance):
    from types import SimpleNamespace
    from data_fetch.market_sources import lienhwa_conference as source
    from search_provider_runtime import SourceResponseError
    mono=[time.monotonic()];epoch=[NOW]
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:mono[0],time=lambda:epoch[0]))
    class Diagnostic(dict):
        def update(self,*a,**kw):
            super().update(*a,**kw)
            if self.get('lienhwa_originals_verified'):
                if advance=='budget':mono[0]+=26
                else:epoch[0]+=1800
    diagnostic=Diagnostic()
    with pytest.raises(SourceResponseError)as caught:source.fetch_lienhwa_context('1229.TW',diagnostics=diagnostic)
    assert caught.value.error_kind==('timeout'if advance=='budget'else'original_expired')
    assert diagnostic['lienhwa_originals_verified']is False
    assert all(k not in diagnostic for k in ('coverage_status','cache_hit','stale','fetched_at_epoch'))
    assert diagnostic['http_request_count']==4 and diagnostic['http_request_sent']is True


@pytest.mark.parametrize('proof',['lienhwa_glyph_evidence'])
def test_public_source_rejects_worker_proof_tamper_even_when_pages_match(harness,monkeypatch,proof):
    from data_fetch.market_sources import lienhwa_conference as source
    from search_provider_runtime import SourceResponseError
    real=source.extract_lienhwa_presentation_pages
    def tamper(*a,**kw):
        value=real(*a,**kw);value[proof]['raw_bytes_rewritten']=0;return value
    monkeypatch.setattr(source,'extract_lienhwa_presentation_pages',tamper)
    with pytest.raises(SourceResponseError):source.fetch_lienhwa_context('1229.TW')


@pytest.mark.parametrize('change',['missing_latest','future_latest','duplicate','master','publisher','wrong_pdf','wrong_event','truncated','event_day','event_time','event_canonical'])
def test_unknown_or_incomplete_latest_never_uses_old_material(harness,change):
    from data_fetch.market_sources import lienhwa_conference as source
    from search_provider_runtime import SourceResponseError
    from bs4 import BeautifulSoup
    if change=='master':harness[0][MASTER_URL]=harness[0][MASTER_URL].replace(b'11996904',b'11996905')
    elif change.startswith('event_'):
        raw=harness[0][EVENT_URL]
        if change=='event_day':raw=raw.replace('2026年09月30日'.encode(),'2026年12月30日'.encode())
        elif change=='event_time':raw=raw.replace('15點30分'.encode(),'16點30分'.encode())
        else:raw=raw.replace(EVENT_URL.encode(),b'https://other.example/event')
        harness[0][EVENT_URL]=raw
    elif change=='publisher':harness[0][INDEX_URL]=harness[0][INDEX_URL].replace('聯華實業控股股份有限公司'.encode(),b'Other issuer')
    elif change=='truncated':harness[0][INDEX_URL]=harness[0][INDEX_URL][:-20]
    else:
        soup=BeautifulSoup(harness[0][INDEX_URL],'html.parser');listing=soup.select_one('.newsAndDownloadList');rows=listing.select(':scope > li')
        if change=='missing_latest':rows[0].decompose()
        elif change=='future_latest':
            new=soup.new_tag('li');new.append(BeautifulSoup('<h3><a href="https://www.lhicholdings.com/new">2026年第三季 法人說明會資訊</a></h3>','html.parser'));listing.append(new)
        elif change=='duplicate':listing.append(deepcopy(rows[0]))
        elif change=='wrong_pdf':rows[0].select_one('h3 a')['onclick']="window.open('https://other.example/x.pdf')"
        else:rows[2].select_one('h3 a')['href']='https://other.example/event'
        harness[0][INDEX_URL]=str(soup).encode()
    with pytest.raises(SourceResponseError):source.fetch_lienhwa_context('1229.TW')
    assert PDF_URL not in harness[1]


def test_date_unknown_publication_and_mixed_financial_periods_remain_explicit(harness):
    from data_fetch.market_sources import lienhwa_conference as source
    v=source.fetch_lienhwa_context('1229.TW');d=v['documents'][0]
    assert d['published_at'] is None and d['content_period']==v['period']==''
    assert d['role_page_allowlist']==[1,22,24,25] and d['excluded_native_text_pages']==[15]
    assert d['text_extraction_complete'] is False and d['financial_statement_complete'] is False
    assert d['pages'][1]['text']=='' and d['pages'][28]['text']=='29'
    assert '年底年售電量' in d['pages'][14]['text']
    assert d['event_time']=='15:30' and d['event_timezone']=='Asia/Taipei'

@pytest.mark.parametrize('change',['allowlist','omissions','period','disclaimer','unseen','qa','complete','receipt_missing'])
def test_partial_source_cannot_be_promoted_or_retimed_by_saved_payload(harness,change):
    from data_fetch.market_sources import lienhwa_conference as s
    v=s.fetch_lienhwa_context('1229.TW');d=v['documents'][0]
    if change=='allowlist':d['role_page_allowlist'].append(15)
    elif change=='omissions':d['missing_text_pages']=[]
    elif change=='period':v['period']='2026Q2'
    elif change=='disclaimer':d['pages'][1]['text']='guaranteed growth'
    elif change=='unseen':d['native_editorial_caution']=''
    elif change=='qa':d['q_and_a_transcript_available']=True
    elif change=='complete':d['native_text_coverage']='complete'
    else:v['lienhwa_conference_receipt'].pop('event')
    assert s.verify_context(v,'1229.TW',max_age=1800) is False


def test_reader_timeout_never_turns_into_metadata_success(harness,monkeypatch):
    from data_fetch.market_sources import lienhwa_conference as s
    from source_pdf_reader import SourcePdfError
    from search_provider_runtime import SourceResponseError
    def fail(*a,**kw):raise SourcePdfError('timeout')
    monkeypatch.setattr(s,'extract_lienhwa_presentation_pages',fail);d={}
    with pytest.raises(SourceResponseError) as caught:s.fetch_lienhwa_context('1229.TW',diagnostics=d)
    assert caught.value.error_kind=='timeout' and d['lienhwa_originals_verified'] is False
    assert d['http_request_count']==4 and 'fetched_at_epoch' not in d


def test_other_ticker_does_not_touch_source(harness):
    from data_fetch.market_sources import lienhwa_conference as s
    assert s.fetch_lienhwa_context('2330.TW')=={} and not harness[1]


def test_actual_current_report_identity_supports_exact_truncated_caller_alias():
    from data_fetch.market_sources import lienhwa_conference as s
    evidence=json.loads((ROOT/'docs/evidence/source-acquisition/20261014/lienhwa-conference-integration/author/current-identity.json').read_text())
    data=evidence['context']
    assert 'LIEN HWA INDUSTRIAL HOLDINGS CO' in data['company_identity']['english_names']
    assert s.validate_context(data,'1229.TW')
    changed=deepcopy(data);changed['company_identity']['english_names'][-1]+=' UNRELATED'
    assert s.validate_context(changed,'1229.TW') is False


def test_full_visual_coverage_is_explicitly_false(harness):
    from data_fetch.market_sources import lienhwa_conference as s
    d=s.fetch_lienhwa_context('1229.TW')['documents'][0]
    assert d.get('full_visual_content_verified') is False


@pytest.mark.parametrize('bucket',['documents','materials'])
@pytest.mark.parametrize('remaining_marker',['projection_policy','lienhwa_glyph_evidence'])
def test_stripped_typed_document_still_requires_original_verification(bucket,remaining_marker):
    from data_fetch.market_sources import lienhwa_conference as s
    marker = s.PROJECTION_POLICY if remaining_marker=='projection_policy' else False
    value={bucket:[{remaining_marker:marker,'title':'Unverified presentation'}]}
    assert s.is_marked(value) is True
    assert s.verify_context(value,'1229.TW',max_age=1800) is False
    assert s.is_marked({bucket:[{'title':'Unrelated ordinary conference'}]}) is False


def test_short_master_expiry_rechecked_after_last_material_replay(harness,monkeypatch):
    from data_fetch.market_sources import lienhwa_conference as source
    from data_fetch.market_sources.lienhwa_conference_transport import ConferenceHttp
    from search_provider_runtime import SourceResponseError
    native=ConferenceHttp.download_original;epoch=[NOW]
    def short(self,url,diagnostic):
        value=native(self,url,diagnostic)
        if url==MASTER_URL:value['response_metadata']['cache_control']='max-age=5'
        return value
    monkeypatch.setattr(ConferenceHttp,'download_original',short)
    monkeypatch.setattr(time,'time',lambda:epoch[0])
    real=source.original_bytes;reads=[]
    def late(receipt,url,**kw):
        raw=real(receipt,url,**kw)
        if url==PDF_URL:
            reads.append(url)
            if len(reads)==2:epoch[0]=NOW+5.1
        return raw
    monkeypatch.setattr(source,'original_bytes',late);d={}
    with pytest.raises(SourceResponseError):source.fetch_lienhwa_context('1229.TW',diagnostics=d)
    assert d['lienhwa_originals_verified'] is False and d['http_request_count']==4


@pytest.mark.parametrize('change',['event_epoch_bool','event_epoch_nan','manifest_http','manifest_missing','event_cache_int','event_complete_int'])
def test_typed_event_receipt_cannot_be_forged(harness,change):
    from data_fetch.market_sources import lienhwa_conference as s
    v=s.fetch_lienhwa_context('1229.TW');r=v['lienhwa_conference_receipt']['event']
    if change=='event_epoch_bool':r['retrieved_at']=True
    elif change=='event_epoch_nan':r['retrieved_at']=float('nan')
    elif change=='manifest_http':r['acquisition_manifest']['http_status']=200
    elif change=='manifest_missing':r.pop('acquisition_manifest')
    elif change=='event_cache_int':r['cache_hit']=0
    else:r['response_complete']=1
    assert s.verify_context(v,'1229.TW',max_age=1800) is False
