"""Owned normal batch, native checks, no research/HTTP/cache inflation."""
import json,time
from copy import deepcopy
import httpx,pytest
from test_current_104_postings import packets,raw,ISSUER,JOB
from test_current_104_evidence import DATA
from data_fetch.market_sources import current_104_transport as t,current_104_evidence as e
from data_fetch.types import FetchRequest
from provider_correlation import correlation_scope,source_operation


def setup(monkeypatch, *, kind='normal'):
 calls=[];a,b=packets()
 monkeypatch.setattr(e,'verified_issuer',lambda issuer,now=None:issuer==ISSUER)
 def get(url,**kwargs):
  calls.append((url,kwargs));data=raw(a if url==e.list_url(ISSUER)else b)
  request=httpx.Request('GET',url)
  return httpx.Response(200,content=data,headers={'content-type':'application/json'},request=request)
 monkeypatch.setattr(t,'sync_get',get)
 return calls


def fetch(**options):
 request=FetchRequest.from_ticker(ISSUER['ticker'],**options)
 with correlation_scope(replace=True,ticker=ISSUER['ticker'],fetch_id='test-fetch'),source_operation('alternative_data',e.PROVIDER):
  return t.fetch_current_advertisements(request,DATA,ISSUER,primary={'status':'unavailable','reason_code':'exact_employer_unverified'})


def test_complete_native_batch_and_second_hit_do_not_resend_or_extend(monkeypatch):
 from cache_store import get_cache_json
 from data_trust import source_record_count
 calls=setup(monkeypatch);r=fetch();assert r is not None
 assert r.status=='success'and r.audit['record_count']==1
 assert r.audit['http_request_count']==2 and r.audit['http_request_sent']is True
 assert len(calls)==2 and all(k['timeout']<=5 and k['params']=={} for _,k in calls)
 assert source_record_count('alternative_data',{**DATA,'alternative_data':r.value})==1
 before=get_cache_json(e.cache_key(ISSUER));r2=fetch();after=get_cache_json(e.cache_key(ISSUER))
 assert len(calls)==2 and before==after
 assert r2.audit['cache_hit']is True and r2.audit['http_request_count']==0 and r2.audit['http_request_sent']is False
 assert r2.value==r.value

@pytest.mark.parametrize('options',[{'record_provider_sla':False},{'force_refresh':True}])
def test_research_and_force_do_not_enter_new_normal_cache_or_native_path(monkeypatch,options):
 calls=setup(monkeypatch)
 assert fetch(**options)is None and calls==[]

@pytest.mark.parametrize('status',[None,403,429,504])
def test_primary_transport_failure_cannot_switch_to_new_endpoint(monkeypatch,status):
 calls=setup(monkeypatch)
 request=FetchRequest.from_ticker(ISSUER['ticker'])
 with correlation_scope(replace=True,ticker=ISSUER['ticker'],fetch_id='f'),source_operation('alternative_data',e.PROVIDER):
  r=t.fetch_current_advertisements(request,DATA,ISSUER,primary={'transport_failed':True,'http_status':status})
 assert r is None and not calls

@pytest.mark.parametrize('kind',['off','redirect','different_url','cache','mime','truncated','timeout','oversize'])
def test_bad_response_or_selected_detail_does_not_create_success(monkeypatch,kind):
 a,b=packets();monkeypatch.setattr(e,'verified_issuer',lambda issuer,now=None:True)
 def get(url,**kwargs):
  if kind=='timeout':raise httpx.ReadTimeout('no response')
  data=raw(a if url==e.list_url(ISSUER)else b)
  if kind=='off'and url!=e.list_url(ISSUER):
   d=deepcopy(b);d['data']['switch']='off';data=raw(d)
  if kind=='truncated':data=data[:-3]
  if kind=='oversize':data=b'x'*300001
  response=httpx.Response(200,content=data,headers={'content-type':'text/html'if kind=='mime'else'application/json'},request=httpx.Request('GET',url+'/other'if kind=='different_url'else url))
  if kind=='cache':response.from_cache=True
  if kind=='redirect':response.history=[httpx.Response(302)]
  return response
 monkeypatch.setattr(t,'sync_get',get)
 assert fetch()is None


def test_no_source_operation_cannot_invent_native_fetch_identity(monkeypatch):
 calls=setup(monkeypatch)
 assert t.fetch_current_advertisements(FetchRequest.from_ticker(ISSUER['ticker']),DATA,ISSUER)is None
 assert not calls
