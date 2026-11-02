"""Public anonymous requests preserve refusal and cache provenance boundaries."""
import json
import time

import pytest

from search_provider_runtime import SourceResponseError


@pytest.fixture
def transport(monkeypatch):
    from data_fetch.market_sources import thsrc_careers_transport as t
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for key in t.PROXY_ENV: monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(t, 'proxy_url_for_request', lambda *a: None)
    monkeypatch.setattr(t, 'cooldown_state', lambda *a: None)
    monkeypatch.setattr(t, 'observe_http_response', lambda *a: None)
    return t


def parts(url, method, status=200):
    content_type = 'text/html' if method == 'GET' else 'text/javascript'
    return {'body': b'complete public original', 'process_started': True,
            'headers': f'HTTP/2 {status}\r\nContent-Type: {content_type}\r\nRetry-After: 600\r\n\r\n'.encode(),
            'metadata': json.dumps({'http_code': status, 'url_effective': url, 'num_redirects': 0}).encode()}


@pytest.mark.parametrize('key', ['index', 'tenant', 'listing', '964508496998000936'])
def test_exact_read_protocol_preserves_component_identity_and_has_no_credentials(transport, monkeypatch, key):
    calls = []; url, method, identity = transport.request_identity(key)
    def collect(argv, end, **kw): calls.append((argv, end, kw)); return parts(url, method), 0, None
    monkeypatch.setattr(transport, 'collect_capped_process', collect)
    start = time.monotonic(); client = transport.ThsrcCareersHttp(start + 20)
    result = client._download(key, {})
    assert result['request_identity'] == identity and result['url'] == url and result['method'] == method
    assert result['response_complete'] is True and result['response_bytes'] == 24
    argv, end, kw = calls[0]; assert client.http_request_count == 1 and end - start <= 5.1
    assert kw['body_limit'] == 500000
    assert not any(x in argv for x in ('--insecure', '--location', '--cookie', '--cookie-jar', '--user-agent'))
    assert ('--data-binary' in argv) == (method == 'POST')
    if method == 'POST':
        body = argv[argv.index('--data-binary') + 1]
        assert 'c0-param0=number:1900000134' in body and 'uno%3D16446274' in body
        assert '\nscriptSessionId=\n' in body


@pytest.mark.parametrize('status,kind', [(401, 'authentication'), (403, 'access_denied'),
    (429, 'rate_limited'), (503, 'server_error'), (302, 'http_error')])
def test_refusal_has_one_attempt_and_retains_retry_after(transport, monkeypatch, status, kind):
    failures = []; url, method, _ = transport.request_identity('listing')
    monkeypatch.setattr(transport, 'remember_failure', lambda key, exc: failures.append(exc))
    monkeypatch.setattr(transport, 'collect_capped_process', lambda *a, **k: (parts(url, method, status), 28, 'timeout'))
    client = transport.ThsrcCareersHttp(time.monotonic() + 20)
    with pytest.raises(SourceResponseError) as caught: client._download('listing', {})
    assert caught.value.error_kind == kind and caught.value.response.headers['retry-after'] == '600'
    assert client.http_request_count == 1 and len(failures) == (status != 302)


@pytest.mark.parametrize('key', [None, True, '', '../private', 'https://evil.test', '1\ngetResume'])
def test_invalid_components_never_load_cache_or_send_http(transport, monkeypatch, key):
    monkeypatch.setattr(transport, 'shared_fetch', lambda *a, **k: pytest.fail('invalid key loaded cache'))
    monkeypatch.setattr(transport, 'collect_capped_process', lambda *a, **k: pytest.fail('invalid key sent HTTP'))
    with pytest.raises(ValueError): transport.ThsrcCareersHttp(time.monotonic() + 20).get_receipt(key)


def test_local_cooldown_sends_nothing(transport, monkeypatch):
    monkeypatch.setattr(transport, 'cooldown_state', lambda *a: {'until': time.time() + 600})
    monkeypatch.setattr(transport, 'collect_capped_process', lambda *a, **k: pytest.fail('cooldown sent HTTP'))
    client = transport.ThsrcCareersHttp(time.monotonic() + 20)
    with pytest.raises(SourceResponseError): client._download('listing', {})
    assert client.http_request_count == 0
