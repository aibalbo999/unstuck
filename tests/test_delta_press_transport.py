from contextlib import contextmanager
from copy import deepcopy
import json,time
import pytest
import cache_store
from provider_correlation import correlation_scope,source_operation
from search_provider_runtime import SourceResponseError
from data_fetch.market_sources import delta_press_transport as module
from data_fetch.market_sources.delta_press_parse import INDEX
from data_fetch.market_sources.delta_press_evidence import PROVIDER
from delta_press_fixtures import index,URL

DATA={'ticker':'2308.TW','quote_type':'EQUITY','company_name':'台達電','company_identity':{
 'ticker':'2308.TW','instrument_type':'EQUITY','official_name':'台達電','legal_name':'台達電子工業股份有限公司','official_ubn':'34051920'}}

@contextmanager
def flow():
    with correlation_scope(replace=True,ticker='2308.TW',fetch_id='test-source-fetch'),source_operation('recent_catalysts',PROVIDER):yield

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(module,'current_master',lambda *a:(b'unit-boundary',{}))
    c=module.DeltaPressHttp(deepcopy(DATA),record_provider_sla=True);events=[];cooldowns=[]
    monkeypatch.setattr(c,'_emit',lambda d,r=None:events.append((deepcopy(d),deepcopy(r))))
    monkeypatch.setattr(module,'observe_http_response',lambda r:None)
    monkeypatch.setattr(module,'remember_failure',lambda key,error:cooldowns.append(error))
    return c,events,cooldowns

def parts(raw=None,status=200,**meta):
    raw=raw if raw is not None else index()
    values={'http_code':status,'url_effective':INDEX,'ssl_verify_result':0,'proxy_used':0,'num_redirects':0,'size_download':len(raw)};values.update(meta)
    return {'body':raw,'headers':f'HTTP/2 {status}\r\nContent-Type: text/html; charset=utf-8\r\nRetry-After: 60\r\n\r\n'.encode(),'metadata':json.dumps(values).encode(),'process_started':True}

def test_native_consume_records_only_fully_checked_transport(client):
    c,events,cooldowns=client
    with flow():r=c._consume(INDEX,parts(),0,None,{'url':INDEX})
    assert r['native_transport']['response_complete']is True and c.http_request_count==1
    assert events[0][0]['response_complete']and events[0][1]==r and not cooldowns
    assert 'raw_response_path'not in json.dumps(r)

@pytest.mark.parametrize('change',[{'ssl_verify_result':1},{'proxy_used':1},{'num_redirects':1},{'size_download':1},{'http_code':None},{'url_effective':'https://evil.example/'}])
def test_incomplete_or_untrusted_metadata_never_native_success(client,change):
    c,events,_=client
    with flow(),pytest.raises(SourceResponseError):c._consume(INDEX,parts(**change),0,None,{'url':INDEX})
    assert not events[-1][0]['response_complete']and events[-1][1]is None

@pytest.mark.parametrize('status',[403,429,503,504])
def test_real_status_retry_after_preserved_and_failed(client,status):
    c,events,cooldowns=client
    with flow(),pytest.raises(SourceResponseError)as caught:c._consume(INDEX,parts(status=status),0,None,{'url':INDEX})
    assert caught.value.response.status_code==status and caught.value.response.headers['Retry-After']=='60'
    assert events[-1][0]['http_status']==status and events[-1][1]is None
    assert len(cooldowns)==1

def test_later_timeout_does_not_inherit_index_status(client):
    c,events,_=client
    with flow():
        c._consume(INDEX,parts(),0,None,{'url':INDEX})
        failure={'body':b'','headers':b'','metadata':b'{}','process_started':True}
        with pytest.raises(SourceResponseError)as caught:c._consume(INDEX,failure,-9,'timeout',{'url':INDEX})
    assert caught.value.status_code is None and events[-1][0]['http_status']is None
    assert events[-1][0]['http_request_sent']is None and not events[-1][0]['http_status_observed']
    assert c.process_count==2 and c.http_request_count==1

@pytest.mark.parametrize('change',['length','encoding','mime','timeout','empty'])
def test_body_contract_failures_are_preserved_not_qualified(client,change):
    c,events,_=client;p=parts();rc=0;error=None
    if change=='length':p['headers']=p['headers'].replace(b'\r\n\r\n',b'\r\nContent-Length: 1\r\n\r\n')
    elif change=='encoding':p['headers']=p['headers'].replace(b'\r\n\r\n',b'\r\nContent-Encoding: gzip\r\n\r\n')
    elif change=='mime':p['headers']=p['headers'].replace(b'text/html',b'application/json')
    elif change=='timeout':rc=28;error='timeout'
    elif change=='empty':p=parts(raw=b'')
    with flow(),pytest.raises(SourceResponseError):c._consume(INDEX,p,rc,error,{'url':INDEX})
    assert events[-1][1]is None and not events[-1][0]['response_complete']

def test_research_or_missing_frame_never_uses_shared_fetch_or_network(monkeypatch,client):
    c,_,_=client
    monkeypatch.setattr(cache_store,'peek_cache_json',lambda key:None)
    def forbidden(*a,**kw):raise AssertionError('must not write a guard/cache or create an HTTP child')
    monkeypatch.setattr(module,'shared_fetch',forbidden);monkeypatch.setattr(module,'collect_capped_process',forbidden)
    with pytest.raises(SourceResponseError):c.get(INDEX)
    c=module.DeltaPressHttp(deepcopy(DATA),record_provider_sla=False)
    with flow(),pytest.raises(SourceResponseError):c.get(INDEX)

def test_unpublished_or_duplicate_requests_cannot_fetch(client,monkeypatch):
    c,_,_=client
    with pytest.raises(SourceResponseError):c.get(URL)
    c.seen.add(INDEX)
    with pytest.raises(SourceResponseError):c.get(INDEX)
    with pytest.raises(SourceResponseError):c.allow_attachment({'public':'flag'})

def test_same_existing_issuer_raw_key_is_used_and_unsupported_warm_owner_not_refetched(client,monkeypatch):
    c,_,_=client;seen=[]
    def cached(key,callback,**kwargs):seen.append((key,kwargs));return {'url':INDEX,'legacy_body':'not native receipt'}, {'cache_hit':True}
    monkeypatch.setattr(module,'shared_fetch',cached)
    with flow(),pytest.raises(ValueError):c.get(INDEX)
    assert seen[0][0]=='issuer-news-raw:v1:'+INDEX and seen[0][1]['use_cache']is True
    assert 'force_refresh'not in seen[0][1]and c.process_count==0

def test_declared_matching_length_is_accepted(client):
    c,_,_=client;p=parts();p['headers']=p['headers'].replace(b'\r\n\r\n',f'\r\nContent-Length: {len(p["body"])}\r\n\r\n'.encode())
    with flow():assert c._consume(INDEX,p,0,None,{'url':INDEX})['native_transport']['response_complete']

@pytest.mark.parametrize('raw',[b'HTTP/2 200\r\nContent-Type: text/html\r\n',b'HTTP/2 200\r\nContent-Type: text/html\r\nContent-Length: 1\r\nContent-Length: 1\r\n\r\n',b'HTTP/2 200\r\nContent-Type: text/html\r\n\r\nHTTP/bad\r\n',b'HTTP/2 2000\r\nContent-Type: text/html\r\n\r\n',b'HTTP/2 200\r\nContent-\xffLength: 1\r\n\r\n'])
def test_incomplete_duplicated_or_later_bad_headers_not_complete(raw):
    assert module.parse_headers(raw)[2]is False

@pytest.mark.parametrize('raw',[b'<html><head></head><body>The requested URL was rejected</body></html>',index()[:-40]])
def test_refusal_and_truncated_HTML_not_complete_success(client,raw):
    c,events,_=client
    with flow(),pytest.raises(SourceResponseError):c._consume(INDEX,parts(raw=raw),0,None,{'url':INDEX})
    assert events[-1][1]is None

def test_no_source_frame_cannot_claim_native_receipt(client):
    c,events,_=client
    with pytest.raises(SourceResponseError):c._consume(INDEX,parts(),0,None,{'url':INDEX})
    assert not events

@pytest.mark.parametrize('block',['proxy','cooldown','network'])
def test_external_block_never_spawns_curl(client,monkeypatch,block):
    c,_,_=client
    for key in module.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(module,'proxy_url_for_request',lambda *a:'http://proxy'if block=='proxy'else None)
    monkeypatch.setattr(module,'cooldown_state',lambda key:block=='cooldown')
    def forbidden(*a,**kw):raise AssertionError('must not launch curl')
    monkeypatch.setattr(module,'collect_capped_process',forbidden)
    with flow(),pytest.raises(SourceResponseError):c._download(INDEX,{'url':INDEX})
    assert c.process_count==0

def test_native_transport_fixed_budget_and_no_retry_or_redirect(client,monkeypatch):
    c,_,_=client;seen=[]
    for key in module.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    monkeypatch.setattr(module,'proxy_url_for_request',lambda *a:None)
    monkeypatch.setattr(module,'cooldown_state',lambda key:False)
    def boundary(argv,deadline,**kwargs):
        seen.append((argv,deadline,kwargs));return parts(),0,None
    monkeypatch.setattr(module,'collect_capped_process',boundary)
    with flow():c._download(INDEX,{'url':INDEX})
    argv,deadline,kwargs=seen[0]
    assert float(argv[argv.index('--max-time')+1])<=5
    assert float(argv[argv.index('--connect-timeout')+1])<=2
    assert argv[argv.index('--max-filesize')+1]=='1000000'
    assert argv[argv.index('--retry')+1]==argv[argv.index('--max-redirs')+1]=='0'
    assert argv[-1]==INDEX and kwargs['body_limit']==1000000
