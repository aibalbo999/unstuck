import json,time
import pytest
from test_shared_provider_cache import memory_cache
from test_ncc_mobile_peer_cohort import data
from data_fetch.market_sources import ncc_mobile_peer_cohort as s
from data_fetch.market_sources.ncc_mobile_peer_transport import MobileHttp
from search_provider_runtime import SourceResponseError


def parts(status=200):
 raw=json.dumps(data(),ensure_ascii=False).encode()
 return {'process_started':True,'body':raw,'headers':f'HTTP/2 {status}\r\nContent-Type: application/json\r\n\r\n'.encode(),
  'metadata':json.dumps({'http_code':status,'url_effective':s.SOURCE_URL,'ssl_verify_result':0,'proxy_used':0,'num_redirects':0,'size_download':len(raw)}).encode()}


def test_shared_warm_original_has_zero_new_http_and_unchanged_acquisition_time(monkeypatch):
 calls=[]
 def download(self,d):calls.append(1);return self._consume(parts(),0,None,d)
 monkeypatch.setattr(MobileHttp,'_download',download)
 first=MobileHttp(time.monotonic()+5);a,pa=first.get();second=MobileHttp(time.monotonic()+5);b,pb=second.get()
 assert a==b and pa==pb and calls==[1]and first.http_request_count==1 and second.http_request_count==0
 assert second.components[0]['http_request_sent']is False and second.components[0]['cache_hit']is True

@pytest.mark.parametrize('status',[401,402,403,429,503,504])
def test_real_refusal_is_retained_once_without_retry(status):
 c=MobileHttp(time.monotonic()+5);d={}
 with pytest.raises(SourceResponseError):c._consume(parts(status),0,None,d)
 assert c.http_request_count==1 and d['http_request_sent']is True and d['http_status']==status


def test_unknown_timeout_is_not_an_http_success_or_known_local_block():
 p=parts();p['headers']=b'';p['metadata']=b'{}';p['body']=b'';c=MobileHttp(time.monotonic()+5);d={}
 with pytest.raises(SourceResponseError):c._consume(p,28,'timeout',d)
 assert c.http_request_count==0 and d['http_request_sent']is None

@pytest.mark.parametrize('field,value',[('url_effective','https://example.com'),('proxy_used',1),('ssl_verify_result',1),('ssl_verify_result',False),('num_redirects',1),('size_download',2)])
def test_unbound_native_metadata_never_becomes_accepted_original(field,value):
 p=parts();m=json.loads(p['metadata']);m[field]=value;p['metadata']=json.dumps(m).encode()
 with pytest.raises(SourceResponseError):MobileHttp(time.monotonic()+5)._consume(p,0,None,{})


def test_challenge_body_is_rejected_even_when_status_is_200():
 p=parts();p['body']=b'<html>security challenge</html>';m=json.loads(p['metadata']);m['size_download']=len(p['body']);p['metadata']=json.dumps(m).encode()
 with pytest.raises(SourceResponseError):MobileHttp(time.monotonic()+5)._consume(p,0,None,{})


def test_passive_observation_store_failure_does_not_break_native_result(monkeypatch):
 import sqlite3,provider_sla,provider_correlation
 monkeypatch.setattr(provider_correlation,'current_correlation',lambda:{'ticker':'2412.TW','fetch_id':'isolated-test','operation_id':'isolated-operation'})
 def fail(*a,**kw):raise sqlite3.OperationalError('isolated unavailable store')
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',fail)
 monkeypatch.setattr(provider_correlation,'current_source_identity',lambda:('dynamic_peer_metrics','FinMind/yfinance'))
 from data_fetch.market_sources.ncc_mobile_peer_transport import receipt_observation_scope
 c=MobileHttp(time.monotonic()+5)
 with receipt_observation_scope(True):value=c._consume(parts(),0,None,{})
 assert value['receipt']['http_status']==200 and c.http_request_count==1
