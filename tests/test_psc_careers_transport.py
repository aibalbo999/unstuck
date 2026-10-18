"""Anonymous read protocol, source refusal and process/cache bounds."""
import base64
from hashlib import sha256
import json
import time

import pytest

from search_provider_runtime import SourceResponseError

JOB_ID = '1613781649555324659'


@pytest.fixture
def transport(monkeypatch):
    from data_fetch.market_sources import psc_careers_transport as module
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for name in module.PROXY_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(module, 'proxy_url_for_request', lambda *a: None)
    monkeypatch.setattr(module, 'cooldown_state', lambda *a: None)
    monkeypatch.setattr(module, 'observe_http_response', lambda *a: None)
    return module


def parts(url, status=200, extra=b'', **meta):
    return {'body': b'public DWR callback', 'process_started': True,
            'headers': f'HTTP/2 {status}\r\nContent-Type: text/javascript;charset=UTF-8\r\n'.encode() + extra + b'\r\n',
            'metadata': json.dumps({'http_code': status, 'url_effective': url, 'num_redirects': 0, **meta}).encode()}


@pytest.mark.parametrize('job_id', [None, JOB_ID])
def test_fixed_public_read_uses_no_login_cookie_or_session_token_and_has_total_deadline(transport, monkeypatch, job_id):
    calls = []
    url = transport.DETAIL_API if job_id else transport.LIST_API
    def collect(argv, deadline, **kwargs):
        calls.append((argv, deadline, kwargs)); return parts(url), 0, None
    monkeypatch.setattr(transport, 'collect_capped_process', collect)
    start = time.monotonic(); http = transport.PscCareersHttp(start + 20)
    receipt = http._download(job_id, {})
    argv, end, limits = calls[0]; body = argv[argv.index('--data-binary') + 1]
    assert len(calls) == 1 and argv[-1] == url and limits['body_limit'] == 500000
    assert 0 < end - start <= 5.1 and http.http_request_count == 1
    assert '\nscriptSessionId=\n' in body and 'c0-param0=number:9900000736' in body
    assert not any(x in argv for x in ('--insecure', '--location', '--user-agent', '--cookie', '--cookie-jar'))
    assert '--disable' in argv and argv[argv.index('--retry') + 1] == '0'
    assert base64.b64decode(receipt['body_b64']) == b'public DWR callback'


@pytest.mark.parametrize('job_id', [True, 1234, '', '../private', '1\nc0-methodName=getResume', 'abc', '0' * 19])
def test_invalid_job_identifiers_never_start_http_or_load_cache(transport, monkeypatch, job_id):
    monkeypatch.setattr(transport, 'shared_fetch', lambda *a, **k: pytest.fail('invalid identity cache'))
    monkeypatch.setattr(transport, 'collect_capped_process', lambda *a, **k: pytest.fail('invalid identity child'))
    http = transport.PscCareersHttp(time.monotonic() + 20)
    with pytest.raises(SourceResponseError): http.get_receipt(job_id)
    assert http.http_request_count == 0


@pytest.mark.parametrize('status,kind', [(401, 'authentication'), (403, 'access_denied'), (429, 'rate_limited'),
                                        (503, 'server_error'), (302, 'http_error')])
def test_refusal_is_not_retried_and_preserves_retry_after_even_if_body_times_out(transport, monkeypatch, status, kind):
    failures = []
    monkeypatch.setattr(transport, 'remember_failure', lambda key, exc: failures.append(exc))
    monkeypatch.setattr(transport, 'collect_capped_process', lambda *a, **k: (
        parts(transport.LIST_API, status, b'Retry-After: 600\r\n'), 28, 'timeout'))
    http = transport.PscCareersHttp(time.monotonic() + 20)
    with pytest.raises(SourceResponseError) as error: http._download(None, {})
    assert error.value.error_kind == kind and error.value.response.headers['retry-after'] == '600'
    assert len(failures) == (0 if status == 302 else 1) and http.http_request_count == 1


@pytest.mark.parametrize('meta', [{'url_effective': 'https://evil.test/'}, {'num_redirects': 1}, {'http_code': 201}])
def test_destination_or_redirect_mismatch_does_not_admit_a_receipt(transport, monkeypatch, meta):
    monkeypatch.setattr(transport, 'collect_capped_process', lambda *a, **k: (parts(transport.LIST_API, **meta), 0, None))
    with pytest.raises(SourceResponseError): transport.PscCareersHttp(time.monotonic() + 20)._download(None, {})


def test_cooldown_starts_zero_requests(transport, monkeypatch):
    monkeypatch.setattr(transport, 'cooldown_state', lambda *a: {'until': time.time() + 600})
    monkeypatch.setattr(transport, 'collect_capped_process', lambda *a, **k: pytest.fail('cooldown request'))
    http = transport.PscCareersHttp(time.monotonic() + 20)
    with pytest.raises(SourceResponseError): http._download(None, {})
    assert http.http_request_count == 0


def cached_value(transport):
    raw = b'original public response'
    return {'url': transport.LIST_API, 'method': 'POST', 'request_identity': {'cust_id': '9900000736', 'job_id': None},
            'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest()}


@pytest.mark.parametrize('stamp', [float('nan'), float('inf'), True, 10**500, 0, -1, time.time() + 600])
def test_invalid_cache_epochs_never_admit_bytes(transport, monkeypatch, stamp):
    monkeypatch.setattr(transport, 'shared_fetch', lambda *a, **k: (
        cached_value(transport), {'cache_hit': True, 'fetched_at_epoch': stamp}))
    with pytest.raises(SourceResponseError): transport.PscCareersHttp(time.monotonic() + 20).get_receipt()


def test_cache_preserves_original_body_hash_epoch_and_no_new_http(transport, monkeypatch):
    original, stamp = cached_value(transport), time.time() - 100
    monkeypatch.setattr(transport, 'shared_fetch', lambda *a, **k: (
        original, {'cache_hit': True, 'fetched_at_epoch': stamp}))
    http = transport.PscCareersHttp(time.monotonic() + 20)
    receipt = http.get_receipt()
    assert receipt['fetched_at_epoch'] == stamp and http.http_request_count == 0
    assert http.components[0]['http_request_sent'] is False and http.components[0]['cache_hit'] is True
    original['body_b64'] = base64.b64encode(b'changed public response').decode()
    with pytest.raises(SourceResponseError): http.get_receipt()


@pytest.mark.parametrize('behavior', ['drip', 'overflow'])
def test_real_slow_or_large_child_is_stopped_and_reaped(transport, monkeypatch, behavior):
    import os
    import subprocess
    import sys
    from bounded_curl_process import collect_capped_process
    created, real = [], subprocess.Popen
    def spawn(*a, **k):
        child = real(*a, **k); created.append(child); return child
    monkeypatch.setattr(subprocess, 'Popen', spawn)
    code = "import os,sys,time\nos.write({HEADER_FD},b'HTTP/2 200\\r\\nContent-Type: text/javascript\\r\\n\\r\\n')\n"
    code += ("sys.stdout.buffer.write(b'x'*510000);sys.stdout.flush();time.sleep(5)\n" if behavior == 'overflow' else
             "for i in range(100):\n sys.stdout.write('x');sys.stdout.flush();time.sleep(.03)\n")
    monkeypatch.setattr(transport, 'collect_capped_process', lambda argv, end, **kw: collect_capped_process(
        [sys.executable, '-c', code], end, **kw))
    start = time.monotonic(); http = transport.PscCareersHttp(start + .25)
    with pytest.raises(SourceResponseError) as error: http._download(None, {})
    assert error.value.error_kind == ('timeout' if behavior == 'drip' else 'response_too_large')
    assert time.monotonic() - start < 1.5 and http.http_request_count == 1 and len(created) == 1
    with pytest.raises(ProcessLookupError): os.kill(created[0].pid, 0)
