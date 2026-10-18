"""Fixed public route and bounded refusal/metadata behavior without network."""
import json

import pytest

from data_fetch.market_sources import uk_conference_transport as transport
from search_provider_runtime import SourceResponseError


PDF_URL = 'https://www.uk.com.tw/v_comm/inc/download_file.asp?re_id=2174&fid=42331'


@pytest.mark.parametrize('url', [
    PDF_URL.replace('https:', 'http:'), PDF_URL.replace('www.uk.com.tw', 'example.com'),
    PDF_URL + '&fid=1', PDF_URL + '#fragment', PDF_URL.replace('re_id=2174', 're_id=2175'),
    PDF_URL.replace('fid=42331', 'fid=042331'), PDF_URL.replace('fid=42331', 'fid=１２３'),
])
def test_only_published_fixed_issuer_document_contract_is_allowed(url):
    assert not transport.presentation_url(url)


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
    assert '--insecure' not in argv and '--cookie' not in argv and '--proxy' not in argv
    assert details['response_complete'] is True and details['http_status'] == 200


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
