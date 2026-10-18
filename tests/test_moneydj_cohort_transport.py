"""The one public cohort request is capped and refuses alternate destinations."""
import json
import os
import sys
import time

import pytest
from search_provider_runtime import SourceResponseError


@pytest.fixture
def transport(monkeypatch):
    from data_fetch.market_sources import moneydj_cohort_transport as module
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    for key in module.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(module,'proxy_url_for_request',lambda *a:None)
    return module


def parts(transport, *, status=200, extra=b'', **metadata):
    return {'body':b'<html>public cohort</html>','process_started':True,
            'headers':f'HTTP/2 {status}\r\nContent-Type: text/html\r\n'.encode()+extra+b'\r\n',
            'metadata':json.dumps({'http_code':status,'url_effective':transport.URL,'num_redirects':0,**metadata}).encode()}


def test_one_fixed_ordinary_request_has_tls_size_and_wall_time_bounds(transport,monkeypatch):
    calls=[]
    def collect(argv,deadline,**kwargs):
        calls.append((argv,deadline,kwargs));return parts(transport),0,None
    monkeypatch.setattr(transport,'collect_capped_process',collect)
    diagnostic={};start=time.monotonic()
    assert transport.download_html(deadline=start+8,diagnostics=diagnostic).startswith(b'<html>')
    argv,end,limits=calls[0]
    assert len(calls)==1 and argv[-1]==transport.URL and 0<end-start<=8
    assert argv[argv.index('--proto')+1]=='=https' and argv[argv.index('--retry')+1]=='0'
    assert '--insecure' not in argv and '--location' not in argv and '--user-agent' not in argv
    assert limits['body_limit']==200000 and diagnostic['http_request_sent'] is True


@pytest.mark.parametrize('change',[{'url_effective':'https://wrong.example/'},{'num_redirects':1},{'http_code':201}])
def test_redirect_or_effective_destination_mismatch_is_rejected(transport,monkeypatch,change):
    monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:(parts(transport,**change),0,None))
    with pytest.raises(SourceResponseError):transport.download_html(deadline=time.monotonic()+1)


@pytest.mark.parametrize('status,kind',[(403,'access_denied'),(429,'rate_limited'),(503,'server_error'),(307,'http_error')])
def test_real_http_refusal_survives_body_failure_and_retains_retry_after(transport,monkeypatch,status,kind):
    monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:(parts(transport,status=status,extra=b'Retry-After: 1800\r\n'),28,'timeout'))
    diagnostic={}
    with pytest.raises(SourceResponseError) as error:transport.download_html(deadline=time.monotonic()+1,diagnostics=diagnostic)
    assert error.value.error_kind==kind and error.value.response.headers['retry-after']=='1800'
    assert diagnostic['http_request_sent'] is True


def test_expired_or_proxy_block_starts_no_child(transport,monkeypatch):
    monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:pytest.fail('blocked request must start no child'))
    diagnostic={}
    with pytest.raises(SourceResponseError):transport.download_html(deadline=time.monotonic()-1,diagnostics=diagnostic)
    assert diagnostic['http_request_sent'] is False
    monkeypatch.setattr(transport,'proxy_url_for_request',lambda *a:'http://proxy.invalid')
    with pytest.raises(SourceResponseError):transport.download_html(deadline=time.monotonic()+1,diagnostics=diagnostic)
    assert diagnostic['http_request_sent'] is False


@pytest.mark.parametrize('behavior',['drip','overflow'])
def test_capped_real_child_is_stopped_and_reaped_without_network(transport,monkeypatch,behavior):
    import subprocess
    from bounded_curl_process import collect_capped_process
    created=[];real=subprocess.Popen
    def spawn(*args,**kwargs):
        child=real(*args,**kwargs);created.append(child);return child
    monkeypatch.setattr(subprocess,'Popen',spawn)
    code="import os,sys,time\nfd={HEADER_FD}\nos.write(fd,b'HTTP/2 200\\r\\nContent-Type: text/html\\r\\n\\r\\n')\n"
    code+=("sys.stdout.buffer.write(b'x'*210000);sys.stdout.flush();time.sleep(5)\n" if behavior=='overflow'
           else "\nfor i in range(100):\n sys.stdout.write('x');sys.stdout.flush();time.sleep(.03)\n")
    monkeypatch.setattr(transport,'collect_capped_process',lambda argv,end,**kwargs:collect_capped_process([sys.executable,'-c',code],end,**kwargs))
    start=time.monotonic()
    with pytest.raises(SourceResponseError) as error:transport.download_html(deadline=start+.25)
    assert error.value.error_kind==('timeout' if behavior=='drip' else 'response_too_large')
    assert time.monotonic()-start<1.5 and len(created)==1
    with pytest.raises(ProcessLookupError):os.kill(created[0].pid,0)
