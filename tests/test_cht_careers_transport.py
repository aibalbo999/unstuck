from copy import deepcopy
from hashlib import sha256
import json,time
import pytest
from test_shared_provider_cache import memory_cache
from data_fetch.market_sources.cht_careers_transport import ChtCareersHttp,allowed_url
from data_fetch.market_sources.cht_careers import INDEX_URL,receipt_body
from search_provider_runtime import SourceResponseError


def parts(body=b'<html>public</html>',status=200):
 return {'process_started':True,'body':body,'headers':f'HTTP/2 {status}\r\nContent-Type: text/html; charset=utf-8\r\n\r\n'.encode(),
 'metadata':json.dumps({'http_code':status,'url_effective':INDEX_URL,'ssl_verify_result':0,'proxy_used':0,'num_redirects':0,'size_download':len(body)}).encode()}


def test_native_response_archive_and_shared_cache_never_invent_new_warm_http(monkeypatch):
 calls=[]
 def download(self,url,diag):calls.append(url);return self._consume(url,parts(),0,None,diag)
 monkeypatch.setattr(ChtCareersHttp,'_download',download)
 first=ChtCareersHttp();a=first.read(INDEX_URL);second=ChtCareersHttp();b=second.read(INDEX_URL)
 assert calls==[INDEX_URL]and a==b and first.http_request_count==1 and second.http_request_count==0
 assert second.components[0]['cache_hit']is True and second.components[0]['http_request_sent']is False
 assert receipt_body(a,INDEX_URL,time.time())==b'<html>public</html>'

@pytest.mark.parametrize('status',[401,402,403,429,503,504])
def test_refusal_is_retained_as_one_confirmed_request_without_retry(status):
 client=ChtCareersHttp();d={}
 with pytest.raises(SourceResponseError):client._consume(INDEX_URL,parts(status=status),0,None,d)
 assert client.http_request_count==1 and d['http_request_sent']is True and d['http_status']==status


def test_unconfirmed_connection_timeout_does_not_claim_an_http_response():
 p=parts(body=b'');p['headers']=b'';m=json.loads(p['metadata']);m['http_code']=0;p['metadata']=json.dumps(m).encode();c=ChtCareersHttp();d={}
 with pytest.raises(SourceResponseError):c._consume(INDEX_URL,p,28,'timeout',d)
 assert c.http_request_count==0 and d['http_request_sent']is None

@pytest.mark.parametrize('field,value',[('ssl_verify_result',1),('proxy_used',1),('num_redirects',1),('size_download',999),('url_effective','https://example.com/'),('ssl_verify_result',False)])
def test_tampered_transport_metadata_never_becomes_a_source_original(field,value):
 p=parts();m=json.loads(p['metadata']);m[field]=value;p['metadata']=json.dumps(m).encode()
 with pytest.raises(SourceResponseError):ChtCareersHttp()._consume(INDEX_URL,p,0,None,{})

@pytest.mark.parametrize('url',['https://example.com/','http://www.cht.com.tw/','https://rmis.cht.com.tw/portal/jobs/login.jsp','https://rmis.cht.com.tw/portal/jobs/jobdetail.jsp?foo=bar'])
def test_only_public_source_contract_urls_can_reach_transport(url):
 with pytest.raises(ValueError):allowed_url(url)


def test_same_operation_never_repeats_an_uncertain_or_completed_url(monkeypatch):
 monkeypatch.setattr(ChtCareersHttp,'_download',lambda self,u,d:self._consume(u,parts(),0,None,d))
 c=ChtCareersHttp();c.read(INDEX_URL)
 with pytest.raises(SourceResponseError):c.read(INDEX_URL)
 assert c.http_request_count==1


def test_native_ms950_listing_archives_original_bytes():
 from data_fetch.market_sources.cht_careers import LIST_URL
 raw='<html>中華電信股份有限公司</html>'.encode('cp950');p=parts(raw)
 p['headers']=b'HTTP/2 200\r\nContent-Type: text/html; charset=MS950\r\n\r\n'
 m=json.loads(p['metadata']);m['url_effective']=LIST_URL;p['metadata']=json.dumps(m).encode()
 c=ChtCareersHttp();proof=c._consume(LIST_URL,p,0,None,{})
 assert proof['encoding']=='cp950' and receipt_body(proof,LIST_URL,time.time())==raw
 assert c.http_request_count==1


def test_passive_receipt_sqlite_failure_preserves_native_source_result(monkeypatch):
 import sqlite3,provider_sla,provider_correlation
 monkeypatch.setattr(provider_correlation,'current_correlation',lambda:{'ticker':'2412.TW','fetch_id':'isolated-test'})
 def broken(*a,**kw):raise sqlite3.OperationalError('isolated unavailable observation store')
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',broken)
 client=ChtCareersHttp(record_provider_sla=True)
 proof=client._consume(INDEX_URL,parts(),0,None,{})
 assert receipt_body(proof,INDEX_URL,time.time())==b'<html>public</html>'
 assert client.http_request_count==1
