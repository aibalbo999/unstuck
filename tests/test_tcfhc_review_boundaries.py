from hashlib import sha256
import time
import threading
import pytest
import test_tcfhc_conference as h
from test_tcfhc_conference import harness

@pytest.mark.parametrize('field',['historical_point_in_time_verified','finality_guaranteed','stale'])
def test_raw_receipt_cannot_claim_unsupported_verification_or_stale_freshness(harness,field):
 from data_fetch.market_sources import tcfhc_conference as s
 value=s.fetch_tcfhc_context('5880.TW');value['tcfhc_qa_receipt']['qa'][field]=True
 assert not s.verify_context(value,'5880.TW')

def test_lock_wait_respects_remaining_total_deadline(monkeypatch):
 import shared_provider_cache as c
 from data_fetch.market_sources.tcfhc_conference_transport import ConferenceHttp
 from search_provider_runtime import SourceResponseError
 digest=sha256(('tcfhc-qa-raw:v1:'+h.QA).encode()).hexdigest();lock=c._local_lock(digest)
 held=threading.Event();release=threading.Event()
 def holder():
  with lock:held.set();release.wait(3)
 thread=threading.Thread(target=holder);thread.start();assert held.wait(1)
 monkeypatch.setattr(ConferenceHttp,'_download',lambda *a:pytest.fail('expired deadline download'))
 start=time.monotonic()
 try:
  with pytest.raises(SourceResponseError):ConferenceHttp(start+.03).get_receipt(h.QA)
  elapsed=time.monotonic()-start
 finally:release.set();thread.join()
 assert elapsed<.15,f'30ms budget took{elapsed:.3f}s'

@pytest.mark.parametrize('opts',[{'force_refresh':True},{'use_cache':False}])
def test_public_explicit_fresh_acquisition_flags_reach_issuer_transport(harness,opts):
 from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
 fetch_free_earnings_call_context('5880.TW');harness[1].clear()
 fetch_free_earnings_call_context('5880.TW',**opts)
 assert harness[1]==[h.INDEX,h.EVENT,h.QA]

@pytest.mark.parametrize('name',['華航','玉山金'])
def test_correct_identity_must_not_mask_conflicting_display_name(harness,name):
 from data_fetch.enrichment_providers import EarningsCallProvider
 from data_fetch.types import FetchRequest
 data={'ticker':'5880.TW','quote_type':'EQUITY','company_name':name,'company_identity':{'ticker':'5880.TW','official_name':'合庫金'}}
 result=EarningsCallProvider().fetch(FetchRequest.from_ticker('5880.TW'),{'data':data})
 assert result.status=='unavailable'and not harness[1]

@pytest.mark.parametrize('key,value',[('forbidden_aliases',True),('forbidden_aliases',123),('allowed_aliases',123),('english_names',123)])
def test_malformed_alias_lists_fail_closed_before_acquisition(harness,key,value):
 from data_fetch.enrichment_providers import EarningsCallProvider
 from data_fetch.types import FetchRequest
 data={'ticker':'5880.TW','quote_type':'EQUITY','company_name':'合庫金','company_identity':{'ticker':'5880.TW','official_name':'合庫金',key:value}}
 result=EarningsCallProvider().fetch(FetchRequest.from_ticker('5880.TW'),{'data':data})
 assert result.status=='unavailable'and not harness[1]

def test_actual_bilingual_display_name_is_accepted(harness):
 from data_fetch.market_sources.tcfhc_conference import validate_context
 assert validate_context({'ticker':'5880.TW','quote_type':'EQUITY','company_name':'合庫金 / Taiwan Cooperative Financial Holding Co., Ltd.','company_identity':{'ticker':'5880.TW','official_name':'合庫金','legal_name':None}},'5880.TW')

@pytest.mark.parametrize('warm',[False,True])
def test_one_verified_qa_document_has_record_count_one(harness,warm):
 from data_fetch.enrichment_providers import EarningsCallProvider
 from data_fetch.types import FetchRequest
 p=EarningsCallProvider();request=FetchRequest.from_ticker('5880.TW')
 if warm:p.fetch(request)
 r=p.fetch(request)
 assert len(r.value['documents'])==1
 assert r.audit['record_count']==1, 'dict property count is not source document count'

@pytest.mark.parametrize('warm',[False,True])
def test_one_verified_qa_document_has_record_count_one(harness,warm):
 from data_fetch.enrichment_providers import EarningsCallProvider
 from data_fetch.types import FetchRequest
 p=EarningsCallProvider();request=FetchRequest.from_ticker('5880.TW')
 if warm:p.fetch(request)
 r=p.fetch(request)
 assert len(r.value['documents'])==1
 assert r.audit['record_count']==1, 'dict property count is not source document count'

@pytest.mark.parametrize('status',[200,429])
def test_unwritable_guard_storage_blocks_new_native_http(monkeypatch,status):
 import cache_store,search_provider_runtime
 from cache_backends import InMemoryCache
 from data_fetch.market_sources import issuer_news_transport as base,tcfhc_conference_transport as t
 from test_tcfhc_conference_transport import response
 cache_store.set_cache_backend(InMemoryCache());calls=[]
 def cannot_write(*a,**kw):raise OSError('read-only guard storage')
 monkeypatch.setattr(cache_store,'set_cache_json',cannot_write)
 monkeypatch.setattr(search_provider_runtime,'set_cache_json',cannot_write)
 monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
 for key in base.PROXY_ENV:monkeypatch.delenv(key,raising=False)
 monkeypatch.setattr(base,'proxy_url_for_request',lambda *a:None)
 monkeypatch.setattr(base,'observe_http_response',lambda *a:None)
 def native(argv,*a,**kw):calls.append(argv);return response(argv,status)
 monkeypatch.setattr(base,'collect_capped_process',native)
 errors=[]
 try:
  for _ in range(2):
   try:t.ConferenceHttp(time.monotonic()+20).get_receipt(h.QA)
   except t.SourceResponseError as exc:errors.append(exc.error_kind)
   else:errors.append('success')
  assert not calls, f'guard writes unavailable but native HTTP count={len(calls)} outcomes={errors}'
  assert errors==['guard_storage_unavailable']*2
 finally:cache_store.reset_cache_store_for_tests()
