"""Ordinary issuer curl behavior, with every subprocess replaced before I/O."""
import hashlib
import json
import time

import pytest

from search_provider_runtime import SourceResponseError


@pytest.fixture
def transport(monkeypatch):
    import bounded_curl_process
    import company_conference_transport as module
    import external_http_client
    # Never allow a test that removes the guard to execute a real child.
    monkeypatch.setattr(bounded_curl_process.subprocess, 'Popen', lambda *a, **k: pytest.fail('no subprocess'))
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for name in module.PROXY_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(external_http_client, 'proxy_url_for_request', lambda *_a: None)
    monkeypatch.setattr(module, '_VERSION', '8.7.1')
    monkeypatch.setattr(module, 'collect_capped_process', lambda *a, **k: pytest.fail('unexpected transfer'))
    return module


def parts(url, *, status=200, raw=None, extra_headers=b'', metadata=None, started=True):
    pdf = url.endswith('.pdf')
    raw = raw if raw is not None else b'%PDF-offline' if pdf else b'<html>offline</html>'
    kind = b'application/pdf' if pdf else b'text/html'
    meta = {'http_code': status, 'url_effective': url, 'num_redirects': 0, 'http_version': '2'}
    if metadata is not None:
        meta = metadata
    return {'body': raw, 'headers': f'HTTP/2 {status}\r\n'.encode() + b'content-type: '+kind+b'\r\n'+extra_headers,
            'metadata': json.dumps(meta).encode(), 'process_started': started}


@pytest.mark.parametrize('pdf', [False, True])
def test_single_allowlisted_get_has_caps_deadline_and_default_identity(transport, monkeypatch, pdf):
    m = transport; url = 'https://www.myson.com.tw/public/uploads/pdf/5314_2026.pdf' if pdf else m.INDEX_URL
    calls = []; returned = parts(url); deadline = time.monotonic() + 0.25
    def collect(argv, end, **kwargs):
        calls.append((argv, end, kwargs)); return returned, 0, None
    monkeypatch.setattr(m, 'collect_capped_process', collect)
    diag = {}
    assert m.download(url, deadline=deadline, diagnostics=diag) == returned['body']
    assert len(calls) == 1
    argv, end, kwargs = calls[0]
    assert argv[:2] == [m.CURL, '--disable'] and argv[-1] == url
    assert not {'--location', '-L', '--user-agent', '-A', '--cookie', '--user', '--proxy', '--insecure'} & set(argv)
    assert argv[argv.index('--retry')+1] == '0'
    assert argv[argv.index('--max-redirs')+1] == '0'
    assert argv[argv.index('--proto')+1] == '=https'
    assert 0 < float(argv[argv.index('--max-time')+1]) <= 0.25
    assert end == deadline and kwargs['headers'] is True
    assert kwargs['body_limit'] == (16 if pdf else 2)*1024*1024
    assert argv[argv.index('--max-filesize')+1] == str(kwargs['body_limit'])
    assert diag['http_request_sent'] is True and diag['response_complete'] is True
    assert diag['response_hash_scope'] == 'full_received_body'
    assert diag['response_sha256'] == hashlib.sha256(returned['body']).hexdigest()
    assert diag['transport_http_version'] == '2' and diag['transport_client'] == 'native_curl'
    assert 'captured_prefix_sha256' not in diag


@pytest.mark.parametrize('url', [
    'http://www.myson.com.tw/gov_info', 'https://www.myson.com.tw/gov_info?x=1',
    'https://www.myson.com.tw.evil.invalid/gov_info', 'https://www.myson.com.tw@127.0.0.1/gov_info',
    'https://www.myson.com.tw/public/uploads/pdf/../secret.pdf',
    'https://www.myson.com.tw/public/uploads/pdf/a.pdf?redirect=x',
    'https://other.invalid/a.pdf',
])
def test_url_allowlist_denies_before_any_process(transport, url):
    diag = {}
    with pytest.raises(SourceResponseError) as error:
        transport.download(url, deadline=time.monotonic()+1, diagnostics=diag)
    assert error.value.error_kind == 'transport_url_invalid'
    assert diag['http_request_sent'] is False


def test_test_flag_denies_before_capability_or_transfer(transport, monkeypatch):
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '1')
    monkeypatch.setattr(transport, '_version', lambda *a: pytest.fail('no capability child'))
    diag = {}
    with pytest.raises(SourceResponseError) as error:
        transport.download(transport.INDEX_URL, deadline=time.monotonic()+1, diagnostics=diag)
    assert error.value.error_kind == 'test_network_disabled' and diag['http_request_sent'] is False


@pytest.mark.parametrize('mode', ['application', 'environment'])
def test_proxy_policy_checked_in_original_url_provider_order_and_never_bypassed(transport, monkeypatch, mode):
    import external_http_client
    calls = []
    def proxy(url, provider):
        calls.append((url, provider));return 'http://secret.invalid' if mode == 'application' else None
    monkeypatch.setattr(external_http_client, 'proxy_url_for_request', proxy)
    if mode == 'environment':monkeypatch.setenv('HTTPS_PROXY', 'http://secret.invalid')
    diag = {}
    with pytest.raises(SourceResponseError) as error:
        transport.download(transport.INDEX_URL, deadline=time.monotonic()+1, diagnostics=diag)
    assert calls == [(transport.INDEX_URL, 'MYSON official conference presentation')]
    assert error.value.error_kind == 'proxy_configuration_unsupported'
    assert diag['http_request_sent'] is False and 'secret' not in str(diag)


@pytest.mark.parametrize('status,kind', [(403,'access_denied'), (429,'rate_limited'), (503,'server_error')])
@pytest.mark.parametrize('rc,failure', [(0,None), (28,'timeout'), (63,'response_too_large')])
def test_received_http_refusal_and_retry_after_survive_body_errors(transport, monkeypatch, status, kind, rc, failure):
    returned = parts(transport.INDEX_URL, status=status, raw=b'refusal', extra_headers=b'Retry-After: 3600\r\n')
    monkeypatch.setattr(transport, 'collect_capped_process', lambda *a, **k: (returned,rc,failure))
    diag = {}
    with pytest.raises(SourceResponseError) as error:
        transport.download(transport.INDEX_URL, deadline=time.monotonic()+1, diagnostics=diag)
    assert error.value.error_kind == kind and error.value.status_code == status
    assert error.value.response.headers['retry-after'] == '3600'
    assert diag['http_status'] == status and diag['http_request_sent'] is True
    complete = rc == 0
    assert diag['response_complete'] is complete
    assert diag['response_hash_scope'] == ('full_received_body' if complete else 'captured_prefix')
    assert diag['response_sha256' if complete else 'captured_prefix_sha256'] == hashlib.sha256(b'refusal').hexdigest()
    assert ('captured_prefix_sha256' if complete else 'response_sha256') not in diag


def test_truncated_retry_after_is_not_misreported_as_smaller_delay(transport, monkeypatch):
    returned = parts(transport.INDEX_URL,status=429,extra_headers=b'Retry-After: 36')
    monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:(returned,28,'timeout'))
    with pytest.raises(SourceResponseError) as error:
        transport.download(transport.INDEX_URL,deadline=time.monotonic()+1,diagnostics={})
    assert error.value.status_code == 429 and 'retry-after' not in error.value.response.headers


@pytest.mark.parametrize('rc,failure,started', [(28,'timeout',True), (63,'response_too_large',True), (None,'spawn_failed',False)])
def test_transfer_failure_is_never_a_success_or_an_invented_http(transport, monkeypatch, rc, failure, started):
    returned = {'body':b'prefix','headers':b'','metadata':b'','process_started':started}
    monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:(returned,rc,failure))
    diag = {}
    with pytest.raises(SourceResponseError) as error:
        transport.download(transport.INDEX_URL,deadline=time.monotonic()+1,diagnostics=diag)
    assert error.value.error_kind == failure and error.value.status_code is None
    assert diag['http_request_sent'] is started and diag['response_complete'] is False
    assert 'response_sha256' not in diag


@pytest.mark.parametrize('case', ['redirect','metadata','encoding','pdf_signature'])
def test_noncanonical_or_wrong_format_response_not_accepted(transport, monkeypatch, case):
    url = transport.INDEX_URL if case != 'pdf_signature' else 'https://www.myson.com.tw/public/uploads/pdf/new.pdf'
    returned = parts(url, raw=b'html' if case == 'pdf_signature' else None)
    kind = 'unexpected_content_type'
    if case == 'redirect':
        returned = parts(url,status=302,extra_headers=b'Location: https://evil.invalid/\r\n');kind='http_error'
    if case == 'metadata':
        returned = parts(url,metadata={'http_code':200,'url_effective':url,'num_redirects':1});kind='transport_metadata_invalid'
    if case == 'encoding':returned['headers'] += b'Content-Encoding: gzip\r\n';kind='unsupported_content_encoding'
    monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:(returned,0,None))
    with pytest.raises(SourceResponseError) as error:
        transport.download(url,deadline=time.monotonic()+1,diagnostics={})
    assert error.value.error_kind == kind


def test_cold_capability_probe_shares_deadline_and_cached_version_is_local(transport, monkeypatch):
    monkeypatch.setattr(transport,'_VERSION',None); calls=[]; deadline=time.monotonic()+0.1
    def version(argv,end,**kwargs):
        calls.append((argv,end,kwargs));return {'body':b'curl 8.7.1 (test)'},0,None
    monkeypatch.setattr(transport,'collect_capped_process',version)
    assert transport._version(deadline) == '8.7.1'
    assert transport._version(deadline) == '8.7.1'
    assert len(calls)==1 and calls[0][0]==[transport.CURL,'--disable','--version']
    assert calls[0][1] <= deadline and calls[0][2]['body_limit']==4096


def test_unsupported_capability_stops_without_get(transport, monkeypatch):
    monkeypatch.setattr(transport,'_VERSION',None);calls=[]
    def version(argv,*a,**k):calls.append(argv);return {'body':b'curl 8.3.0 (test)'},0,None
    monkeypatch.setattr(transport,'collect_capped_process',version)
    diag={}
    with pytest.raises(SourceResponseError) as error:
        transport.download(transport.INDEX_URL,deadline=time.monotonic()+1,diagnostics=diag)
    assert error.value.error_kind=='curl_body_cap_unsupported' and diag['http_request_sent'] is False
    assert len(calls)==1 and calls[0][-1]=='--version'
