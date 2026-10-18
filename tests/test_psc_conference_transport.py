"""Fixed anonymous HTTPS, unchanged URLs, capped bodies and no transport retry."""
import json,time
import pytest
from data_fetch.market_sources import psc_conference_transport as transport
from search_provider_runtime import SourceResponseError

PDF='https://www.pscnet.com.tw/upload/pscnet/file/20260826164426662249.pdf'
ANNOUNCEMENT='https://www.pscnet.com.tw/pscnetAbout/newsContent.do?sub_id=BIG_MESSAGE_SUB_ID&id=6ba2dc9d7a00000062fb548c63075544'

@pytest.fixture
def seam(monkeypatch):
    calls=[];response={'status':200,'body':b'<html>complete</html>','mime':'text/html','complete':True}
    for key in transport.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    monkeypatch.setattr(transport,'_version',lambda d:'curl 8.7.1 test')
    def collect(argv,deadline,**kwargs):
        calls.append((argv,deadline,kwargs));url=argv[-1]
        return {'body':response['body'],'headers':f"HTTP/1.1 {response['status']} OK\r\nContent-Type: {response['mime']}\r\n\r\n".encode(),
                'metadata':json.dumps({'http_code':response['status'],'url_effective':url,'num_redirects':0}).encode(),
                'process_started':True},0,None if response['complete']else 'response_too_large'
    monkeypatch.setattr(transport,'collect_capped_process',collect)
    return calls,response

@pytest.mark.parametrize('url',[transport.HOME_URL,transport.INDEX_URL,ANNOUNCEMENT,PDF])
def test_published_route_uses_same_url_anonymous_bound(seam,url):
    calls,response=seam
    if url==PDF:response.update(body=b'%PDF-whole',mime='application/pdf')
    diag={};assert transport.download(url,deadline=time.monotonic()+20,diagnostics=diag)==response['body']
    argv,deadline,limits=calls[0]
    assert len(calls)==1 and argv[-1]==url and '--location'not in argv and '--insecure'not in argv
    assert argv[argv.index('--retry')+1]=='0'and argv[argv.index('--max-redirs')+1]=='0'
    assert float(argv[argv.index('--max-time')+1])<=5 and limits['body_limit']==(8*1024*1024 if url==PDF else 700000)
    assert diag['http_status']==200 and diag['response_complete']is True and diag['transport_request_profile']=='curl_default'

@pytest.mark.parametrize('status,reason',[(403,'access_denied'),(429,'rate_limited'),(503,'server_error'),(302,'http_error')])
def test_refusal_is_preserved_without_redirect_or_retry(seam,status,reason):
    calls,response=seam;response['status']=status
    with pytest.raises(SourceResponseError)as exc:transport.download(transport.HOME_URL,deadline=time.monotonic()+20,diagnostics={})
    assert exc.value.error_kind==reason and len(calls)==1

def test_body_prefix_is_not_complete_original(seam):
    calls,response=seam;response['complete']=False;diag={}
    with pytest.raises(SourceResponseError):transport.download(transport.HOME_URL,deadline=time.monotonic()+20,diagnostics=diag)
    assert diag['response_complete']is False and diag['response_hash_scope']=='captured_prefix'and len(calls)==1

@pytest.mark.parametrize('url',['https://wwwuat.pscnet.com.tw/upload/pscnet/file/20260826164426662249.pdf',
                               'https://www.pscnet.com.tw.example/upload/pscnet/file/20260826164426662249.pdf',
                               'http://www.pscnet.com.tw/upload/pscnet/file/20260826164426662249.pdf',
                               'https://www.pscnet.com.tw/pscnetAbout/about.do;jsessionid=fake'])
def test_unknown_route_does_not_start_native_process(seam,url):
    with pytest.raises(SourceResponseError):transport.download(url,deadline=time.monotonic()+20,diagnostics={})
    assert seam[0]==[]
