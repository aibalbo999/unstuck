"""The fixed-page source uses a hard child deadline and capped body pipes."""
import json
import os
import sys
import time
import pytest
from search_provider_runtime import SourceResponseError

@pytest.fixture
def transport(monkeypatch):
    from data_fetch.market_sources import construction_cohort_transport as source
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK","0")
    for name in source.PROXY_ENV:monkeypatch.delenv(name,raising=False)
    monkeypatch.setattr(source,"proxy_url_for_request",lambda *a:None)
    return source

def parts(url,status=200,body=b"<html>public</html>",headers=b""):
    return {"body":body,"headers":f"HTTP/2 {status}\r\nContent-Type: text/html\r\n".encode()+headers+b"\r\n",
            "metadata":json.dumps({"http_code":status,"url_effective":url,"num_redirects":0}).encode(),
            "process_started":True}

def test_fixed_url_transfer_is_capped_no_retry_no_redirect_and_has_hard_deadline(transport,monkeypatch):
    calls=[]
    def collect(argv,end,**kw):
        calls.append((argv,end,kw))
        return parts(argv[-1]),0,None
    monkeypatch.setattr(transport,"collect_capped_process",collect)
    started=time.monotonic()
    assert transport.download_html(transport.ISSUER_URL,deadline=started+12).startswith(b"<html>")
    argv,end,kw=calls[0]
    assert end<=started+6.1 and kw=={"body_limit":250000,"headers":True}
    assert argv[-1]==transport.ISSUER_URL and "--disable" in argv
    assert argv[argv.index("--retry")+1]=="0" and argv[argv.index("--max-redirs")+1]=="0"
    assert "--insecure" not in argv and "-k" not in argv

@pytest.mark.parametrize("kind",["network_disabled","bad_url","proxy","expired"])
def test_unavailable_admission_never_starts_network_child(transport,monkeypatch,kind):
    monkeypatch.setattr(transport,"collect_capped_process",lambda *a,**k:pytest.fail("unexpected child"))
    url=transport.ISSUER_URL;deadline=time.monotonic()+1
    if kind=="network_disabled":monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK","1")
    elif kind=="bad_url":url="https://other.invalid/"
    elif kind=="proxy":monkeypatch.setattr(transport,"proxy_url_for_request",lambda *a:"http://secret.invalid")
    elif kind=="expired":deadline=time.monotonic()-1
    with pytest.raises(SourceResponseError):transport.download_html(url,deadline=deadline)

@pytest.mark.parametrize("status,kind",[(403,"access_denied"),(429,"rate_limited"),(503,"server_error")])
def test_received_http_refusal_survives_body_timeout_and_retains_retry_after(transport,monkeypatch,status,kind):
    p=parts(transport.ISSUER_URL,status,headers=b"Retry-After: 3600\r\n")
    monkeypatch.setattr(transport,"collect_capped_process",lambda *a,**k:(p,28,"timeout"))
    with pytest.raises(SourceResponseError) as e:transport.download_html(transport.ISSUER_URL,deadline=time.monotonic()+1)
    assert e.value.error_kind==kind and e.value.response.headers["retry-after"]=="3600"

@pytest.mark.parametrize("behavior",["drip","overflow"])
def test_real_no_network_child_is_stopped_reaped_and_bounded(transport,monkeypatch,behavior):
    import subprocess
    from bounded_curl_process import collect_capped_process
    created=[];real_popen=subprocess.Popen
    def spawn(*a,**kw):
        assert a[0][0]==sys.executable and kw["shell"] is False
        child=real_popen(*a,**kw);created.append(child);return child
    monkeypatch.setattr(subprocess,"Popen",spawn)
    code="import os,sys,time\nfd={HEADER_FD}\nos.write(fd,b'HTTP/2 200\\r\\nContent-Type: text/html\\r\\n\\r\\n')\n"
    if behavior=="overflow":code+="sys.stdout.buffer.write(b'x'*300000);sys.stdout.flush();time.sleep(5)\n"
    else:code+="\nfor i in range(100):\n sys.stdout.write('x');sys.stdout.flush();time.sleep(.03)\n"
    def collect(_argv,end,**kw):
        return collect_capped_process([sys.executable,"-c",code],end,**kw)
    monkeypatch.setattr(transport,"collect_capped_process",collect)
    start=time.monotonic()
    with pytest.raises(SourceResponseError) as e:transport.download_html(transport.ISSUER_URL,deadline=start+.25)
    assert e.value.error_kind==("timeout" if behavior=="drip" else "response_too_large")
    assert time.monotonic()-start<1.5 and len(created)==1
    with pytest.raises(ProcessLookupError):os.kill(created[0].pid,0)
