"""Native Yahoo Taiwan transport; all network I/O is replaced with offline fixtures."""
from contextlib import contextmanager
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from data_fetch.enrichment_providers import YahooProvider
from data_fetch.types import FetchRequest
from test_yahoo_taiwan_news import context, isolation


def test_regional_provider_uses_native_seam_with_original_quality_gate(monkeypatch):
    from data_fetch.market_sources import yahoo_taiwan_news as regional
    calls=[]
    @contextmanager
    def native(method,url,**kwargs):
        calls.append((method,url,kwargs))
        body=Path(__file__).parent / 'fixtures/source_acquisition/yahoo_tw_5314_news_20260927.html'
        yield httpx.Response(200,content=body.read_bytes(),request=httpx.Request(method,url))
    monkeypatch.setattr(regional,'curl_stream',native,raising=False)
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert len(calls)==1
    assert len(result.value)==3 and result.status=='degraded_enrichment'
    assert result.audit['raw_count']==10 and result.audit['rejected_reason_counts']=={'historical':7}


@pytest.fixture
def transfer(monkeypatch):
    """Only unit fake I/O may ignore the test flag; an accidental spawn fails."""
    from data_fetch.market_sources import yahoo_taiwan_transport as native
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    for name in native.PROXY_ENV:
        monkeypatch.delenv(name,raising=False)
    monkeypatch.setattr(native.subprocess,'Popen',lambda *_a,**_k:pytest.fail('real network child forbidden'))
    monkeypatch.setattr(native,'_curl_version',lambda *_:'8.7.1')
    return native


def outcome(body=b'page',status=200,rc=0,failure=None,headers=None,metadata=None):
    import json
    url='https://tw.stock.yahoo.com/quote/5314/news'
    header=f'HTTP/2 {status}\r\n'.encode()+(headers or b'Content-Type: text/html\r\n')+b'\r\n'
    meta={'http_code':status,'http_version':'2','url_effective':url,'num_redirects':0} if metadata is None else metadata
    return {'body':body,'headers':header,'metadata':json.dumps(meta).encode(),'process_started':True},rc,failure


def invoke(native,diagnostics=None,**kwargs):
    import time
    diagnostics={} if diagnostics is None else diagnostics
    with native.curl_stream('GET','https://tw.stock.yahoo.com/quote/5314/news',
                            deadline=time.monotonic()+12,diagnostics=diagnostics,**kwargs) as response:
        return response,diagnostics


def test_native_get_retains_genuine_defaults_and_original_url(transfer,monkeypatch):
    native=transfer; calls=[]
    def collect(argv,deadline,**kwargs):
        calls.append((argv,deadline,kwargs))
        return outcome()
    monkeypatch.setattr(native,'_collect',collect)
    response,diagnostic=invoke(native)
    assert response.status_code==200 and response.content==b'page'
    assert len(calls)==1
    argv=calls[0][0]
    assert argv[:3]==['/usr/bin/curl','--disable','--silent']
    assert argv[-1]=='https://tw.stock.yahoo.com/quote/5314/news'
    assert not any(arg in argv for arg in ('--location','--user-agent','--header','--user','--netrc','--insecure','--compressed'))
    assert argv[argv.index('--retry')+1]=='0'
    assert float(argv[argv.index('--max-time')+1])<=9
    assert diagnostic['http_request_sent'] is True and diagnostic['transport_http_version']=='2'
    assert diagnostic['_transport_capture']['response_hash_scope']=='full_received_body'


@pytest.mark.parametrize('rc,failure',[(28,None),(1,'timeout'),(63,'response_too_large'),(2,'transport_error')])
def test_received_refusal_and_retry_after_survive_body_failure(transfer,monkeypatch,rc,failure):
    native=transfer
    monkeypatch.setattr(native,'_collect',lambda *a,**k:outcome(b'partial',429,rc,failure,b'Retry-After: 1200\r\n'))
    response,diag=invoke(native)
    assert response.status_code==429 and response.headers['Retry-After']=='1200'
    assert response.content==b''
    assert diag['_transport_capture']['response_complete'] is False
    assert 'response_sha256' not in diag['_transport_capture']
    assert 'captured_prefix_sha256' in diag['_transport_capture']


def test_non200_full_body_hash_is_preserved_without_news_body(transfer,monkeypatch):
    import hashlib
    native=transfer
    monkeypatch.setattr(native,'_collect',lambda *a,**k:outcome(b'not news',404))
    response,diag=invoke(native)
    assert response.status_code==404 and response.content==b''
    assert diag['_transport_capture']['response_sha256']==hashlib.sha256(b'not news').hexdigest()


@pytest.mark.parametrize('reason',['proxy','env_proxy','test_flag','capability'])
def test_local_refusals_have_zero_transfer_and_no_http_claim(monkeypatch,reason):
    import time
    from data_fetch.market_sources import yahoo_taiwan_transport as native
    from search_provider_runtime import SourceResponseError
    monkeypatch.setattr(native.subprocess,'Popen',lambda *a,**k:pytest.fail('no process allowed'))
    monkeypatch.setattr(native,'_collect',lambda *a,**k:pytest.fail('no transfer allowed'))
    monkeypatch.setattr(native,'_curl_version',lambda *_:(_ for _ in ()).throw(SourceResponseError('curl_unavailable')))
    if reason!='test_flag':monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    if reason=='env_proxy':monkeypatch.setenv('HTTPS_PROXY','http://user:secret@private-proxy.invalid')
    diagnostics={}
    with pytest.raises(SourceResponseError) as caught:
        with native.curl_stream('GET','https://tw.stock.yahoo.com/quote/5314/news',deadline=time.monotonic()+12,
                                diagnostics=diagnostics,proxy='http://secret@proxy.invalid' if reason=='proxy' else None):pass
    assert diagnostics['http_request_sent'] is False
    assert 'secret' not in str(caught.value) and 'secret' not in repr(diagnostics)


@pytest.mark.parametrize('rc,failure,kind',[(28,None,'timeout'),(63,None,'response_too_large'),(1,None,'transport_error'),(0,'response_headers_too_large','response_headers_too_large')])
def test_partial_200_is_error_and_never_news(transfer,monkeypatch,rc,failure,kind):
    from search_provider_runtime import SourceResponseError
    native=transfer
    monkeypatch.setattr(native,'_collect',lambda *a,**k:outcome(b'partial html',200,rc,failure))
    with pytest.raises(SourceResponseError) as caught:invoke(native)
    assert caught.value.error_kind==kind and caught.value.status_code==200


def test_regional_refusal_keeps_retry_after_capture_and_persistent_guard(transfer,monkeypatch):
    from data_fetch.market_sources import yahoo_taiwan_news as regional
    from search_provider_runtime import cooldown_state
    native=transfer
    monkeypatch.setattr(native,'_collect',lambda *a,**k:outcome(b'partial',429,28,None,b'Retry-After: 1200\r\n'))
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.status=='error' and result.audit['http_status']==429
    assert result.audit['response_hash_scope']=='captured_prefix' and result.audit['response_bytes']==7
    assert result.audit['transport_client']=='native_curl'
    assert cooldown_state(regional.GUARD_KEY)['retry_at']-regional.time.time()>=1199


def test_partial_retry_after_line_is_not_used():
    from data_fetch.market_sources.yahoo_taiwan_transport import _received_headers
    status,headers=_received_headers(b'HTTP/2 429\r\nContent-Type: text/html\r\nRetry-After: 36')
    assert status==429 and headers=={'content-type':'text/html'}
    assert _received_headers(b'HTTP/2 429\r\nRetry-After: 3600\r\n\r\n')[1]['retry-after']=='3600'


def test_cold_capability_probe_uses_remaining_deadline_and_then_cache(monkeypatch):
    from data_fetch.market_sources import yahoo_taiwan_transport as native
    monkeypatch.setattr(native,'_CURL_VERSION',None)
    monkeypatch.setattr(native.time,'monotonic',lambda:100.0)
    calls=[]
    def probe(argv,deadline,**kwargs):
        calls.append(deadline)
        return {'body':b'curl 8.7.1 (fixture)\n'},0,None
    monkeypatch.setattr(native,'_collect',probe)
    assert native._curl_version(100.1)=='8.7.1'
    assert native._curl_version(100.01)=='8.7.1' and calls==[100.1]


@pytest.mark.parametrize('behavior', ['header_then_hang','done_then_hang','body_limit','header_limit','metadata_limit'])
def test_fixed_no_network_child_is_bounded_killed_and_reaped(monkeypatch,behavior):
    import os
    import subprocess
    import time
    from data_fetch.market_sources import yahoo_taiwan_transport as native
    real_popen=subprocess.Popen
    created=[]
    def spawn(*args,**kwargs):
        assert args[0][0]==sys.executable and kwargs['shell'] is False
        proc=real_popen(*args,**kwargs);created.append(proc);return proc
    monkeypatch.setattr(native.subprocess,'Popen',spawn)
    code="import os,sys,time\nfd={HEADER_FD}\nos.write(fd,b'HTTP/2 429\\r\\nRetry-After: 3600\\r\\n\\r\\n')\n"
    if behavior=='done_then_hang':code+="sys.stderr.write('{}');sys.stderr.flush()\n"
    if behavior=='body_limit':code+="sys.stdout.buffer.write(b'x'*1000);sys.stdout.flush()\n"
    if behavior=='header_limit':code+="os.write(fd,b'x'*70000)\n"
    if behavior=='metadata_limit':code+="sys.stderr.buffer.write(b'x'*70000);sys.stderr.flush()\n"
    code+="time.sleep(5)\n"
    started=time.monotonic()
    parts,rc,failure=native._collect([sys.executable,'-c',code],started+.2,body_limit=100,headers=True)
    assert time.monotonic()-started<1.5
    assert len(created)==1 and rc is not None and failure is not None
    assert len(parts['body'])<=100 and len(parts['headers'])<=65536 and len(parts['metadata'])<=65536
    assert native._received_headers(parts['headers'])[0]==429
    assert native._received_headers(parts['headers'])[1]['retry-after']=='3600'
    with pytest.raises(ProcessLookupError):os.kill(created[0].pid,0)


def test_spawn_failure_has_no_http_claim(transfer,monkeypatch):
    from search_provider_runtime import SourceResponseError
    native=transfer
    monkeypatch.setattr(native,'_collect',lambda *a,**k:({'body':b'','headers':b'','metadata':b'','process_started':False},None,'transport_error'))
    diagnostic={}
    with pytest.raises(SourceResponseError):invoke(native,diagnostic)
    assert diagnostic['http_request_sent'] is False and diagnostic['transport_process_started'] is False
    assert diagnostic['transport_http_response_received'] is False


@pytest.mark.parametrize('version',[b'curl 8.3.0 (fixture)\n',b'not curl'])
def test_unknown_or_old_curl_cannot_start_transfer(monkeypatch,version):
    import time
    from data_fetch.market_sources import yahoo_taiwan_transport as native
    from search_provider_runtime import SourceResponseError
    monkeypatch.setattr(native,'_CURL_VERSION',None)
    monkeypatch.setattr(native,'_collect',lambda *a,**k:({'body':version},0,None))
    with pytest.raises(SourceResponseError):native._curl_version(time.monotonic()+1)


def test_guarded_refusal_never_calls_native_collector(monkeypatch):
    from data_fetch.market_sources import yahoo_taiwan_news as regional
    from data_fetch.market_sources import yahoo_taiwan_transport as native
    monkeypatch.setattr(regional,'cooldown_state',lambda _:{'http_status':429,'error_kind':'rate_limited','retry_at':9999999999})
    monkeypatch.setattr(native,'_collect',lambda *a,**k:pytest.fail('guard must precede capability and GET'))
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.status=='error' and result.audit['http_request_sent'] is False
