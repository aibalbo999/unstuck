import httpx
import pytest
from data_fetch import annual_workforce_provider as w
from provider_acquisition import observation_kind

@pytest.mark.parametrize('error',[httpx.ConnectTimeout,httpx.ReadTimeout])
def test_unknown_transport_does_not_claim_confirmed_http_or_erase_failure(monkeypatch,error):
 def fail(*a,**kw):raise error('timeout')
 monkeypatch.setattr(w,'sync_get',fail);meta={}
 with pytest.raises(error):w._tracked_dataset_fetch(w.URLS['.TW'],meta)
 assert meta['http_request_sent'] is None and meta['http_request_count']==0
 assert observation_kind({'provider':w.PROVIDER,'source':'annual_workforce','status':'error','record_count':0,'message':'failed','details':meta})=='failed_count'

def test_real_httpx_response_confirms_exact_leg_once(monkeypatch):
 url=w.URLS['.TW'];body=b'[]';calls=[]
 def get(u,**kw):calls.append(u);return httpx.Response(200,content=body,request=httpx.Request('GET',u))
 monkeypatch.setattr(w,'sync_get',get);meta={};raw=w._tracked_dataset_fetch(url,meta)
 assert raw=='[]' and calls==[url]
 assert meta['http_request_sent'] is True and meta['http_request_count']==1
 assert meta['http_status']==200

@pytest.mark.parametrize('status',[401,403,429,503,504])
def test_known_refusal_retains_actual_status_without_retry(monkeypatch,status):
 url=w.URLS['.TW'];response=httpx.Response(status,content=b'refused',request=httpx.Request('GET',url));calls=[]
 def fail(u,**kw):calls.append(u);raise httpx.HTTPStatusError('refused',request=response.request,response=response)
 monkeypatch.setattr(w,'sync_get',fail);meta={}
 with pytest.raises(httpx.HTTPStatusError):w._tracked_dataset_fetch(url,meta)
 assert calls==[url] and meta['http_request_sent'] is True and meta['http_request_count']==1
 assert meta['http_status']==status

def test_success_without_native_response_is_not_http_evidence(monkeypatch):
 monkeypatch.setattr(w,'_fetch_dataset',lambda u:'[]');meta={}
 assert w._tracked_dataset_fetch(w.URLS['.TW'],meta)=='[]'
 assert meta['http_request_sent'] is None and meta['http_request_count']==0

def test_safety_only_value_cannot_supply_workforce_response_identity(monkeypatch):
 from datetime import date
 import json,hashlib
 from test_annual_occupational_safety import _row
 from data_fetch.annual_occupational_safety import URLS as safety_urls
 from data_fetch.types import FetchRequest
 import data_fetch.annual_occupational_safety as safety
 body={w.URLS['.TW']:b'[]',safety_urls['.TW']:json.dumps([_row()]).encode()}
 monkeypatch.setattr(w,'sync_get',lambda u,**kw:httpx.Response(200,content=body[u],request=httpx.Request('GET',u)))
 monkeypatch.setattr(w,'shared_fetch',lambda key,cb,**kw:(cb(),{'cache_hit':False,'stale':False}))
 monkeypatch.setattr(w,'_today',lambda:date(2026,10,17));monkeypatch.setattr(safety,'_today',lambda:date(2026,10,17))
 result=w.AnnualWorkforceProvider().fetch(FetchRequest.from_ticker('2330.TW'))
 assert result.audit['record_count']==0 and result.audit['raw_count']==0
 assert result.audit['response_sha256']==hashlib.sha256(b'[]').hexdigest()
 assert result.audit['report_year'] is None
 related,=result.audit['related_entries']
 assert related['record_count']==1 and related['response_sha256']!=result.audit['response_sha256']

def test_timeout_unknown_survives_persistence_and_failure_denominator(monkeypatch):
 from data_fetch.types import FetchRequest
 from provider_observation_details import observation_details
 def fail(*a,**kw):raise httpx.ConnectTimeout('failed')
 def shared(key,callback,**kw):
  try:return callback(),{'cache_hit':False,'stale':False}
  except httpx.ConnectTimeout:return None,{'cache_hit':False,'error_kind':'ConnectTimeout','stale':False}
 monkeypatch.setattr(w,'sync_get',fail);monkeypatch.setattr(w,'shared_fetch',shared)
 result=w.AnnualWorkforceProvider().fetch(FetchRequest.from_ticker('2330.TW'))
 for audit in [result.audit,*result.audit['related_entries']]:
  assert audit['http_request_sent'] is None and audit['http_request_count']==0
  saved=observation_details(audit)
  assert saved.get('http_request_sent') is not False
  assert observation_kind({'source':audit['source'],'provider':audit['provider'],'status':audit['status'],'record_count':audit['record_count'],'message':audit['message'],'details':saved})=='failed_count'

@pytest.mark.parametrize('kind',['wrong_url','wrong_method','unbound_response','cached_response'])
def test_unbound_or_cached_response_never_confirms_this_http_leg(monkeypatch,kind):
 url=w.URLS['.TW'];request=httpx.Request('POST'if kind=='wrong_method'else'GET',url+'/wrong'if kind=='wrong_url'else url)
 response=httpx.Response(200,content=b'[]',**({}if kind=='unbound_response'else{'request':request}))
 if kind=='cached_response':response.from_cache=True
 monkeypatch.setattr(w,'sync_get',lambda *a,**kw:response);meta={}
 assert w._tracked_dataset_fetch(url,meta)=='[]'
 assert meta['http_request_sent'] is None and meta['http_request_count']==0

def test_header_receipt_survives_body_read_failure(monkeypatch):
 url=w.URLS['.TW'];response=httpx.Response(200,stream=httpx.ByteStream(b'[]'),request=httpx.Request('GET',url))
 monkeypatch.setattr(w,'sync_get',lambda *a,**kw:response);meta={}
 with pytest.raises(httpx.ResponseNotRead):w._tracked_dataset_fetch(url,meta)
 assert meta['http_request_sent'] is True and meta['http_request_count']==1 and meta['http_status']==200
 assert 'response_sha256'not in meta

@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_real_shared_cache_cold_then_warm_keeps_http_and_ttl_boundaries(monkeypatch, tmp_path, backend):
 from datetime import date
 import json
 import cache_store
 from cache_backends import InMemoryCache, SqliteCacheBackend
 from test_annual_occupational_safety import _row
 from test_annual_workforce_source import LISTED
 from data_fetch.types import FetchRequest
 from data_fetch.annual_occupational_safety import URLS as safety_urls
 import data_fetch.annual_occupational_safety as safety
 cache_store.set_cache_backend(InMemoryCache() if backend=="memory" else SqliteCacheBackend(tmp_path/"cache.sqlite3"))
 body={w.URLS['.TW']:json.dumps([LISTED]).encode(),safety_urls['.TW']:json.dumps([_row()]).encode()};calls=[]
 def get(u,**kw):calls.append(u);return httpx.Response(200,content=body[u],request=httpx.Request('GET',u))
 monkeypatch.setattr(w,'sync_get',get);monkeypatch.setattr(w,'_today',lambda:date(2026,10,17));monkeypatch.setattr(safety,'_today',lambda:date(2026,10,17))
 try:
  first=w.AnnualWorkforceProvider().fetch(FetchRequest.from_ticker('2330.TW'))
  second=w.AnnualWorkforceProvider().fetch(FetchRequest.from_ticker('2330.TW'))
  assert first.audit['record_count']==second.audit['record_count']==1
  assert len(calls)==2
  assert first.audit['http_request_sent'] is True and first.audit['http_request_count']==1
  assert second.audit['cache_hit'] is True and second.audit['http_request_sent'] is False and second.audit['http_request_count']==0
  assert first.audit['fetched_at_epoch']==second.audit['fetched_at_epoch']
  assert second.audit['response_sha256']==first.audit['response_sha256']
 finally:cache_store.reset_cache_store_for_tests()
