"""Fixed public route and bounded refusal/metadata behavior without network."""
import json

import pytest

from data_fetch.market_sources import honhai_conference_transport as transport
from search_provider_runtime import SourceResponseError


PDF_URL = 'https://image.honhai.com/upload/202608/law_talk/Hon_Hai_2Q26_Results_Transcript_Chinese_20260818_4465.pdf'


@pytest.mark.parametrize('url', [
    PDF_URL.replace('https:','http:'),PDF_URL.replace('image.honhai.com','example.com'),
    PDF_URL+'?x=1',PDF_URL+'#x',PDF_URL.replace('4465','04465'),
    PDF_URL.replace('4465','４４６５'),PDF_URL.replace('/law_talk/','/en/law_talk/'),
    PDF_URL.replace('image.honhai.com','user:pass@image.honhai.com'),PDF_URL.replace('image.honhai.com','image.honhai.com:443')])
def test_only_observed_issuer_route_shape_without_aliases_is_allowed(url):
    assert not transport.transcript_url(url)


@pytest.fixture
def fake_wire(monkeypatch):
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for key in transport.PROXY_ENV:
        monkeypatch.delenv(key, raising=False)
    import external_http_client
    monkeypatch.setattr(external_http_client, 'proxy_url_for_request', lambda *a: None)
    monkeypatch.setattr(transport, '_version', lambda *a: '8.4.0')
    monkeypatch.setattr(transport, 'observe_http_response', lambda *a: None)
    calls = []
    def install(status=200, mime='application/pdf', redirects=0, complete_url=PDF_URL):
        def collect(argv, deadline, **kwargs):
            calls.append((argv, deadline, kwargs))
            return {'body': b'%PDF-1.4 mock', 'headers': f'HTTP/1.1 {status} status\r\nContent-Type: {mime}\r\n\r\n'.encode(),
                    'metadata': json.dumps({'http_code': status, 'url_effective': complete_url,
                                            'num_redirects': redirects}).encode(), 'process_started': True}, 0, None
        monkeypatch.setattr(transport, 'collect_capped_process', collect)
    return calls, install


def test_single_native_get_keeps_body_limit_no_retry_redirect_or_credentials(fake_wire):
    calls, install = fake_wire
    install()
    details = {}
    assert transport.download(PDF_URL, deadline=transport.time.monotonic()+20, diagnostics=details).startswith(b'%PDF-')
    assert len(calls) == 1 and calls[0][2]['body_limit'] == 8*1024*1024
    argv = calls[0][0]
    assert argv[argv.index('--retry')+1] == '0' and argv[argv.index('--max-redirs')+1] == '0'
    assert float(argv[argv.index('--max-time')+1]) <= 5
    assert '--http1.1' in argv
    assert '--insecure' not in argv and '--cookie' not in argv and '--proxy' not in argv
    assert details['response_complete'] is True and details['http_status'] == 200

def test_new_single_event_page_has_own_oneMB_cap_without_changing_PDF_cap(fake_wire):
    calls,_=fake_wire
    from unittest.mock import patch
    result={'body':b'<html>original</html>','headers':b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n','metadata':json.dumps({'http_code':200,'url_effective':transport.PAGE_URL,'num_redirects':0}).encode(),'process_started':True}
    with patch.object(transport,'collect_capped_process',lambda argv,*a,**k:calls.append((argv,a,k))or(result,0,None)):
        assert transport.download(transport.PAGE_URL,deadline=transport.time.monotonic()+20,diagnostics={})==b'<html>original</html>'
    assert calls[0][2]['body_limit']==1_000_000 and '--http1.1'in calls[0][0]


@pytest.mark.parametrize('status,kind', [(403, 'access_denied'), (429, 'rate_limited'), (504, 'server_error')])
def test_refusal_is_preserved_without_retry(fake_wire, status, kind):
    calls, install = fake_wire
    install(status=status)
    with pytest.raises(SourceResponseError) as raised:
        transport.download(PDF_URL, deadline=transport.time.monotonic()+20, diagnostics={})
    assert raised.value.error_kind == kind and len(calls) == 1


def test_native_effective_url_change_is_not_silently_followed(fake_wire):
    calls, install = fake_wire
    install(redirects=1, complete_url=PDF_URL+'&extra=1')
    with pytest.raises(SourceResponseError) as raised:
        transport.download(PDF_URL, deadline=transport.time.monotonic()+20, diagnostics={})
    assert raised.value.error_kind == 'transport_metadata_invalid' and len(calls) == 1
