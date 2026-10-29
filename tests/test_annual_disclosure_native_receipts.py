from types import SimpleNamespace
import pytest
import httpx
from provider_correlation import correlation_scope
import provider_sla
from data_fetch import annual_workforce_provider as module

@pytest.mark.parametrize('suffix',['.TW','.TWO'])
@pytest.mark.parametrize('safety',[False,True])
def test_actual_dataset_request_has_separate_native_receipt(monkeypatch,suffix,safety):
 from data_fetch.annual_occupational_safety import URLS
 url=URLS[suffix] if safety else module.URLS[suffix];body=b'[]';calls=[];events=[]
 response=httpx.Response(200,content=body,request=httpx.Request("GET",url))
 def fetch(*args,**kw):calls.append((args,kw));return response
 monkeypatch.setattr(module,'sync_get',fetch);monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 with correlation_scope(replace=True,ticker='1623'+suffix,fetch_id='annual-fetch'):
  assert module._fetch_dataset(url)=='[]'
 assert len(calls)==1 and calls[0][1]['timeout']==8
 assert len(events)==1 and events[0]['source']==('esg_occupational_safety' if safety else 'annual_workforce')
 assert events[0]['event_kind']=='http_transport_receipt' and events[0]['record_count']==0
 assert events[0]['http_status']==200 and events[0]['response_bytes']==2
 assert events[0]['fetch_id']=='annual-fetch' and '[]' not in str(events)

@pytest.mark.parametrize('changed',[
 {'url':'https://other.example/data'}, {'from_cache':True}, {'status_code':None},
])
def test_unknown_or_cached_transport_not_claimed(monkeypatch,changed):
 url=module.URLS['.TW'];events=[]
 code=changed.get('status_code',200)
 response=(httpx.Response(code,content=b'[]',request=httpx.Request('GET',changed.get('url',url)))
           if type(code) is int else SimpleNamespace(url=url,status_code=code,content=b'[]'))
 response.from_cache=changed.get('from_cache',False)
 monkeypatch.setattr(module,'sync_get',lambda *a,**kw:response);monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 with correlation_scope(replace=True,ticker='1623.TW',fetch_id='annual-fetch'):assert module._fetch_dataset(url)=='[]'
 assert not events


def test_audit_failure_keeps_same_downloaded_bytes(monkeypatch):
 url=module.URLS['.TW'];response=httpx.Response(200,content=b'[]',request=httpx.Request('GET',url))
 monkeypatch.setattr(module,'sync_get',lambda *a,**kw:response)
 def fail(*a,**kw):raise RuntimeError('audit unavailable')
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',fail)
 with correlation_scope(replace=True,ticker='1623.TW',fetch_id='annual-fetch'):assert module._fetch_dataset(url)=='[]'


def test_http_exception_is_preserved_without_retry(monkeypatch):
 err=RuntimeError('original network exception');calls=[]
 def fail(*a,**kw):calls.append(1);raise err
 monkeypatch.setattr(module,'sync_get',fail)
 with pytest.raises(RuntimeError) as caught:module._fetch_dataset(module.URLS['.TW'])
 assert caught.value is err and len(calls)==1


@pytest.mark.parametrize('metadata',[
 {'ticker':'1623.TW'}, {'ticker':'AAPL','fetch_id':'x'},
 {'ticker':'1623.TWO','fetch_id':'x'}, {'ticker':'.TW','fetch_id':'x'},
])
def test_missing_fetch_or_wrong_issuer_market_cannot_supply_receipt(monkeypatch,metadata):
 url=module.URLS['.TW'];events=[]
 monkeypatch.setattr(module,'sync_get',lambda *a,**kw:httpx.Response(200,content=b'[]',request=httpx.Request('GET',url)))
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 with correlation_scope(replace=True,**metadata):assert module._fetch_dataset(url)=='[]'
 assert not events


@pytest.mark.parametrize('status',[429,503,504])
def test_http_error_receipt_preserves_exact_exception_without_retry(monkeypatch,status):
 import requests
 url=module.URLS['.TW'];response=httpx.Response(status,content=b'error body',request=httpx.Request('GET',url))
 err=requests.HTTPError('original error',response=response);calls=[];events=[]
 def fail(*a,**kw):calls.append(1);raise err
 monkeypatch.setattr(module,'sync_get',fail);monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 with correlation_scope(replace=True,ticker='1623.TW',fetch_id='annual-fetch'):
  with pytest.raises(requests.HTTPError) as caught:module._fetch_dataset(url)
 assert caught.value is err and len(calls)==1
 assert len(events)==1 and events[0]['http_status']==status and events[0]['status']=='error'
 assert events[0]['record_count']==0 and 'error body' not in str(events)


def test_oversized_body_keeps_existing_rejection_and_adds_no_success(monkeypatch):
 url=module.URLS['.TW'];events=[]
 monkeypatch.setattr(module,'sync_get',lambda *a,**kw:httpx.Response(200,content=b'X'*(module.MAX_BYTES+1),request=httpx.Request('GET',url)))
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 with correlation_scope(replace=True,ticker='1623.TW',fetch_id='annual-fetch'):
  with pytest.raises(ValueError,match='response size invalid'):module._fetch_dataset(url)
 assert not events


def test_shape_only_sdk_response_cannot_certify_native_http(monkeypatch):
 url=module.URLS['.TW'];events=[]
 monkeypatch.setattr(module,'sync_get',lambda *a,**kw:SimpleNamespace(url=url,status_code=200,content=b'[]'))
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 with correlation_scope(replace=True,ticker='1623.TW',fetch_id='annual-fetch'):assert module._fetch_dataset(url)=='[]'
 assert not events
