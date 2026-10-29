from copy import deepcopy
import time
import pytest
from data_fetch.market_sources import taiwanmobile_conference as source

NOW=1793275200.0
DATES=[('3Q26','will be held','Thursday, November 12, 2026'),('2Q26','was held','Friday, August 14, 2026'),('1Q26','was held','Wednesday, May 13, 2026'),('4Q25','was held','Friday, March 13, 2026')]
def index():
 cards=[]
 for q,tense,day in DATES:
  link=f'<a href="{source.PDF_URL}">Conference Call Transcript</a>'if q=='2Q26'else''
  cards.append(f'<article class="modal"><div class="modal-body"><p class="p">The {q} results webcast {tense} at 04:00 p.m. on {day}. We went through the financial highlights.</p>{link}</div></article>')
 return ('<html><head><title>'+source.INDEX_TITLE+'</title></head><body><h1>Results Conference Call</h1>'+''.join(cards)+'</body></html>').encode()

@pytest.fixture(autouse=True)
def now(monkeypatch):monkeypatch.setattr(time,'time',lambda:NOW)

def test_latest_past_call_and_future_event_are_distinct():
 s=source.select_transcript(index(),NOW)
 assert s['event_date']=='2026-08-14'and s['content_period']=='2026Q2'
 assert s['upcoming_event']['date']=='2026-11-12'and s['pdf_url']==source.PDF_URL

@pytest.mark.parametrize('change',['foreign_url','period','future_now','missing_card','wrong_weekday','duplicate'])
def test_index_contradictions_are_not_silently_downgraded(change,monkeypatch):
 raw=index()
 if change=='foreign_url':raw=raw.replace(source.PDF_URL.encode(),b'https://other.example/transcript.pdf')
 elif change=='period':raw=raw.replace(b'The 2Q26',b'The 3Q26')
 elif change=='future_now':monkeypatch.setattr(time,'time',lambda:1794528000.0)
 elif change=='missing_card':raw=raw.replace(b'3Q26 results',b'Unknown results')
 elif change=='wrong_weekday':raw=raw.replace(b'Friday, August',b'Thursday, August')
 else:raw=raw.replace(b'</body>',raw[raw.index(b'<article'):raw.index(b'</article>')+10]+b'</body>')
 with pytest.raises(ValueError):source.select_transcript(raw,NOW)

@pytest.mark.parametrize('change',['ticker','legal','ubn','instrument','alias','forbidden','company'])
def test_context_identity_conflicts_fail_closed(change):
 data={'ticker':'3045.TW','instrument_type':'EQUITY','company_name':'台灣大 / Taiwan Mobile Co., Ltd.','company_identity':{'ticker':'3045.TW','stock_id':'3045','legal_name':source.LEGAL,'official_name':'台灣大','official_ubn':source.UBN,'allowed_aliases':['台灣大','TWM','3045.TW'],'forbidden_aliases':[]}}
 assert source.validate_context(data,'3045.TW')
 if change=='ticker':data['company_identity']['stock_id']='2412'
 elif change=='legal':data['company_identity']['legal_name']='中華電信股份有限公司'
 elif change=='ubn':data['company_identity']['official_ubn']='00000000'
 elif change=='instrument':data['instrument_type']='ETF'
 elif change=='alias':data['company_identity']['allowed_aliases'].append('Other Telecom')
 elif change=='forbidden':data['company_identity']['forbidden_aliases']=['TWM']
 else:data['company_name']='Other Telecom'
 assert not source.validate_context(data,'3045.TW')

def test_only_exact_routes_are_admitted():
 from data_fetch.market_sources.taiwanmobile_conference_transport import contract
 for url in (source.MASTER_URL,source.INDEX_URL,source.PDF_URL):assert contract(url)[0]>0
 for url in (source.PDF_URL+'?token=x',source.PDF_URL.replace('https:','http:'),source.PDF_URL.replace('english.taiwanmobile.com','other.example')):
  with pytest.raises(Exception):contract(url)

def test_source_does_not_alias_another_issuer():
 assert source.supports('3045.TW')and source.supports('3045')
 assert not source.supports('3045.TWO')and not source.supports('2412.TW')

@pytest.fixture
def acquisition(monkeypatch):
 import csv,io,base64
 from hashlib import sha256
 from cache_backends import InMemoryCache
 import cache_store
 from data_fetch.market_sources.taiwanmobile_conference_transport import ConferenceHttp
 cache_store.set_cache_backend(InMemoryCache())
 stream=io.StringIO();fields=['公司代號','公司名稱','公司簡稱','營利事業統一編號','網址','英文簡稱','出表日期'];writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
 for n in range(499):writer.writerow(dict.fromkeys(fields,str(n)))
 writer.writerow(dict(zip(fields,['3045',source.LEGAL,'台灣大',source.UBN,'www.taiwanmobile.com','TWM','1151029'])))
 pdf=b'%PDF-unit-contract-only';pages=[{'page_number':n,'text':('1 Taiwan Mobile 2Q26 Results Conference Call August 14, 2026 'if n==1 else str(n)+' ')+'Issuer narrative revenue capital cash and risks remain company statements.'}for n in range(1,13)]
 native={'content_sha256':sha256(pdf).hexdigest(),'page_count':12,'pages':pages,'coverage_status':'complete','empty_pages':[],'garbled_pages':[],'parser_version':'6.19.0'}
 monkeypatch.setattr(source,'KNOWN_SHA',sha256(pdf).hexdigest());monkeypatch.setattr(source,'PAGE_TEXT_SHA256',tuple(sha256(p['text'].encode()).hexdigest()for p in pages));monkeypatch.setattr(source,'extract_pdf_pages',lambda *a,**k:deepcopy(native))
 bodies={source.MASTER_URL:stream.getvalue().encode(),source.INDEX_URL:index(),source.PDF_URL:pdf};calls=[]
 def download(self,url,diagnostic):
  raw=bodies[url];calls.append(url);self.http_request_count+=1;diagnostic.update(http_request_sent=True,http_status=200,response_bytes=len(raw),response_sha256=sha256(raw).hexdigest())
  return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),'http_status':200,'response_complete':True,'request_method':'GET','http_status_observed':True,'fetched_at_epoch':NOW}
 monkeypatch.setattr(ConferenceHttp,'download_original',download)
 yield bodies,calls,native
 cache_store.reset_cache_store_for_tests()

def test_acquired_native_text_preserves_partial_truth_and_warm_cache(acquisition):
 diagnostic={};v=source.fetch_context('3045.TW',diagnostics=diagnostic)
 assert len(v['documents'][0]['pages'])==12 and v['transcript_available']
 assert not v['documents'][0]['transcript_accuracy_independently_verified']
 assert v['coverage_status']=='partial'and not v['documents'][0]['full_content_coverage_verified']
 assert v['period']=='2026Q2'and v['upcoming_event']['period']=='2026Q3'
 assert diagnostic['http_request_count']==3 and not diagnostic['cache_hit']
 assert source.verify_context(v,'3045.TW')
 d={};warm=source.fetch_context('3045.TW',diagnostics=d)
 assert d['http_request_count']==0 and d['cache_hit']and warm['fetched_at_epoch']==v['fetched_at_epoch']
 assert len(acquisition[1])==3

@pytest.mark.parametrize('change',['text','event_date','period','issuer','receipt_time','extra_field','full_truth'])
def test_context_and_receipt_tampering_never_qualifies(acquisition,change):
 v=source.fetch_context('3045.TW')
 if change=='text':v['documents'][0]['pages'][0]['text']+=' edited'
 elif change=='event_date':v['date']='2026-11-12'
 elif change=='period':v['period']='2026Q3'
 elif change=='issuer':v['ticker']='2412.TW'
 elif change=='receipt_time':v['taiwanmobile_conference_receipt']['pdf']['retrieved_at']+=1
 elif change=='extra_field':v['documents'][0]['source_truth']='verified'
 else:v['documents'][0]['full_content_coverage_verified']=True
 assert not source.verify_context(v,'3045.TW')

def test_unknown_revision_is_not_replaced_with_saved_known_body(acquisition):
 acquisition[0][source.PDF_URL]=b'%PDF-new-unqualified-revision'
 with pytest.raises(Exception):source.fetch_context('3045.TW')

def test_active_native_cooldown_prevents_new_http(acquisition):
 import cache_store
 from data_fetch.market_sources.taiwanmobile_conference_transport import ConferenceHttp
 cache_store.set_cache_json(ConferenceHttp._admission_key(source.MASTER_URL),{'retry_at':NOW+120},ttl_seconds=120)
 with pytest.raises(Exception):source.fetch_context('3045.TW')
 assert acquisition[1]==[]


def test_provider_dispatch_and_exact_one_acquisition_audit(acquisition):
 from data_fetch.enrichment_providers import EarningsCallProvider
 from data_fetch.types import FetchRequest
 result=EarningsCallProvider().fetch(FetchRequest.from_ticker('3045.TW',force_refresh=False),context={'data':{'ticker':'3045.TW','company_name':'台灣大','instrument_type':'EQUITY'}})
 assert result.value['documents'][0]['document_kind']=='transcript'
 assert result.audit['provider']==source.PROVIDER and result.audit['record_count']==1
 assert result.audit['http_request_count']==3
 warm=EarningsCallProvider().fetch(FetchRequest.from_ticker('3045.TW',force_refresh=False),context={'data':{'ticker':'3045.TW','company_name':'台灣大'}})
 assert warm.audit['status']=='skipped_fresh_cache'and warm.audit['cache_hit']
 assert warm.audit['http_request_count']==0 and len(acquisition[1])==3

@pytest.mark.parametrize('data',[{'ticker':'2412.TW'}, {'ticker':'3045.TW','company_name':'中華電信股份有限公司'},'invalid'])
def test_provider_identity_rejects_before_any_http(acquisition,data):
 from data_fetch.enrichment_providers import EarningsCallProvider
 from data_fetch.types import FetchRequest
 result=EarningsCallProvider().fetch(FetchRequest.from_ticker('3045.TW'),context={'data':data})
 assert result.audit['error_kind']=='context_unverified'and result.audit['record_count']==0
 assert acquisition[1]==[]


def test_prompt_uses_bounded_english_excerpt_and_fails_closed_on_tampering(acquisition):
 from conference_transcript_prompt import transcript_prompt_context
 from conference_presentation_prompt import without_presentation_documents
 v=source.fetch_context('3045.TW')
 projected=transcript_prompt_context(v,3)
 assert projected['transcript_available']and projected['documents']
 assert sum(len(p['text'].split())for p in projected['documents'][0]['pages'])<=200
 assert projected['documents'][0]['language']=='en'
 assert not projected['documents'][0]['transcript_accuracy_independently_verified']
 assert 'documents'not in without_presentation_documents(v)
 v['documents'][0]['pages'][0]['text']+=' tampered'
 assert transcript_prompt_context(v,3)=={}


def test_full_body_is_not_written_to_reusable_payload_cache(acquisition):
 from data_fetch.cache_helpers import _contains_allis_no_store
 assert _contains_allis_no_store({'earnings_call':source.fetch_context('3045.TW')})


def test_pdf_timeout_is_not_reported_as_success(acquisition,monkeypatch):
 from source_pdf_reader import SourcePdfError
 from search_provider_runtime import SourceResponseError
 def timeout(*a,**k):raise SourcePdfError('timeout')
 monkeypatch.setattr(source,'extract_pdf_pages',timeout)
 with pytest.raises(SourceResponseError)as caught:source.fetch_context('3045.TW')
 assert caught.value.error_kind=='timeout'
 assert not caught.value.diagnostic['taiwanmobile_originals_verified']


def test_exact_vendor_short_label_is_supported_without_prefix_matching():
 data={'ticker':'3045.TW','company_identity':{'allowed_aliases':['TAIWAN MOBILE CO'],'english_names':['TAIWAN MOBILE CO']}}
 assert source.validate_context(data,'3045.TW')
 data['company_identity']['allowed_aliases']=['TAIWAN MOBILE CO OTHER']
 assert not source.validate_context(data,'3045.TW')


def test_independent_saved_deadline_cannot_be_extended(acquisition,monkeypatch):
 from data_fetch.market_sources import taiwanmobile_conference_transport as transport
 v=source.fetch_context('3045.TW')
 receipt=v['taiwanmobile_conference_receipt']['pdf'];receipt['fresh_until_epoch']+=1
 assert not source.verify_context(v,'3045.TW')


def test_corrupt_archived_body_is_rejected_not_crashed(acquisition,monkeypatch):
 import zlib
 v=source.fetch_context('3045.TW')
 def bad(*a,**k):raise zlib.error('corrupt archived bytes')
 monkeypatch.setattr(source,'original_bytes',bad)
 assert source.verify_context(v,'3045.TW')is False
