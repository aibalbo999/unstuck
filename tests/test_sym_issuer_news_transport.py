"""Public native boundary with process/archive seams; never real HTTP."""
from copy import deepcopy
from hashlib import sha256
import json
import time
from types import SimpleNamespace
import pytest
from test_sym_issuer_news import harness, fetch, NOW
from data_fetch.market_sources import sym_issuer_news_transport as t
from search_provider_runtime import SourceResponseError, scope_key

NATIVE_DOWNLOAD = t.SymNewsHttp.download_original


@pytest.fixture
def native(harness, monkeypatch):
    monkeypatch.setattr(t.SymNewsHttp, 'download_original', NATIVE_DOWNLOAD)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for key in t.PROXY_ENV: monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(t, 'proxy_url_for_request', lambda *a: None)
    controls, calls = {}, []
    def process(args, deadline, **options):
        raw = harness[0][args[-1]]; status = controls.get('status', 200)
        calls.append((args, deadline, options))
        policy = controls.get('cache_control', 'no-cache, private')
        headers = (f'HTTP/2 {status}\r\nContent-Type: text/html\r\nContent-Length: {len(raw)}\r\nCache-Control: {policy}\r\n'
                   + controls.get('extra', '') + '\r\n').encode()
        metadata = {'http_code': status, 'url_effective': args[-1], 'num_redirects': 0,
                    'size_download': len(raw), 'content_type': 'text/html', 'method': 'GET', 'proxy_used': 0}
        metadata.update(controls.get('metadata', {}))
        return {'process_started': True, 'body': controls.get('body', raw), 'headers': headers,
                'metadata': json.dumps(metadata).encode()}, controls.get('rc', 0), None
    monkeypatch.setattr(t, 'collect_capped_process', process)
    return controls, calls


def test_exact_native_receipt_and_no_success_cache(native):
    import cache_store
    controls, calls = native; deadline = time.monotonic() + 25
    raw, receipt = t.SymNewsHttp(deadline).get_receipt(t.ARTICLES[0])
    assert t.original_bytes(receipt, t.ARTICLES[0]) == raw
    assert receipt['cache_hit'] is False and receipt['retrieval_policy'] == 'always_native_no_success_cache'
    assert receipt['response_metadata']['cache_control'] == 'no-cache, private'
    args, stop, options = calls[0]
    assert float(args[args.index('--max-time') + 1]) <= 5 and float(args[args.index('--connect-timeout') + 1]) <= 2
    assert args[args.index('--retry') + 1] == '0' and args[args.index('--max-redirs') + 1] == '0'
    assert not any(x in args for x in ('--location', '--insecure', '--cookie', '--range', '--proxy', '--compressed'))
    assert options['body_limit'] == 1_048_576 and stop <= deadline
    t.SymNewsHttp(time.monotonic() + 25).get_receipt(t.ARTICLES[0])
    assert len(calls) == 2
    assert all('body_b64' not in str(value) for value in cache_store.get_cache_backend()._entries.values())


@pytest.mark.parametrize('url', [t.INDEX + '?page=2', t.ARTICLES[0] + '#section', t.ARTICLES[0].replace('https:', 'http:'),
                                t.ARTICLES[0].replace('www.sym-global.com', 'www.sym-global.com.evil.test'),
                                t.GLOBAL + 'news-events-page999', 'https://127.0.0.1/', t.TAIWAN + 'newslist-55-page584'])
def test_unknown_or_held_url_cannot_start_http(native, url):
    with pytest.raises(SourceResponseError): t.SymNewsHttp(time.monotonic() + 25).get_receipt(url)
    assert native[1] == []


@pytest.mark.parametrize('change', ['401', '403', '429', '500', 'redirect', 'effective_url', 'status_bool', 'redirect_bool',
                                   'method', 'proxy', 'length', 'duplicate_length', 'encoding', 'partial', 'timeout', 'mime', 'challenge'])
def test_native_failures_remain_guarded_without_retry(native, change):
    controls, calls = native
    if change.isdigit(): controls['status'] = int(change)
    elif change == 'redirect': controls['metadata'] = {'num_redirects': 1}
    elif change == 'effective_url': controls['metadata'] = {'url_effective': t.INDEX}
    elif change == 'status_bool': controls['metadata'] = {'http_code': True}
    elif change == 'redirect_bool': controls['metadata'] = {'num_redirects': False}
    elif change == 'method': controls['metadata'] = {'method': 'POST'}
    elif change == 'proxy': controls['metadata'] = {'proxy_used': 1}
    elif change == 'length': controls['body'] = b'incomplete'
    elif change == 'duplicate_length': controls['extra'] = 'Content-Length: 1\r\n'
    elif change == 'encoding': controls['extra'] = 'Content-Encoding: gzip\r\n'
    elif change == 'partial': controls['rc'] = 18
    elif change == 'timeout': controls['rc'] = 28
    elif change == 'mime': controls['metadata'] = {'content_type': 'application/json'}
    else:
        raw = b'captcha'; controls.update(body=raw, metadata={'size_download': len(raw)})
    for options in ({}, {'force_refresh': True}, {'use_cache': False}):
        with pytest.raises(SourceResponseError): t.SymNewsHttp(time.monotonic() + 25, **options).get_receipt(t.ARTICLES[0])
    assert len(calls) == 1


@pytest.mark.parametrize('kind,state', [('host', {}), ('host', {'retry_at': True}), ('host', {'retry_at': NOW + 10}),
                                     ('host', {'next_request_at': NOW + 10}), ('admission', {}), ('admission', {'retry_at': False}),
                                     ('raw', []), ('raw', {}), ('raw', {'error_kind': 'timeout'}),
                                     ('raw', {'error_kind': 'timeout', 'retry_after_epoch': NOW + 10})])
def test_unknown_or_active_guard_fails_closed(native, kind, state):
    import cache_store
    url = t.INDEX
    key = (scope_key(t.HTTP_PROVIDER, endpoint='www.sym-global.com') if kind == 'host' else
           t.SymNewsHttp._admission_key(url) if kind == 'admission' else
           'shared_provider:v1:' + sha256((t.SymNewsHttp.raw_cache_prefix + url).encode()).hexdigest())
    cache_store.set_cache_json(key, state, ttl_seconds=120)
    with pytest.raises(SourceResponseError): t.SymNewsHttp(time.monotonic() + 25).get_receipt(url)
    assert native[1] == []


@pytest.mark.parametrize('operation', ['read', 'write', 'lease'])
def test_storage_failure_cannot_start_http(native, monkeypatch, operation):
    import cache_store
    original = cache_store.get_cache_json
    def broken(*a, **k): raise OSError('isolated guard unavailable')
    if operation == 'read': monkeypatch.setattr(cache_store, 'get_cache_json', broken)
    elif operation == 'write': monkeypatch.setattr(cache_store, 'set_cache_json', broken)
    else:
        monkeypatch.setattr(cache_store, 'get_cache_json', lambda key: {'retry_at': 0} if key.startswith(t.SymNewsHttp.admission_prefix) else original(key))
    with pytest.raises(SourceResponseError): t.SymNewsHttp(time.monotonic() + 25).get_receipt(t.INDEX)
    assert native[1] == []


def test_short_ttl_cannot_survive_final_archive_read(native, monkeypatch):
    # Positive max-age still limits validation even though no successful HTTP cache exists.
    controls, calls = native
    controls['cache_control'] = 'private, max-age=5'
    original = t.original_bytes; clock = [NOW]
    monkeypatch.setattr(time, 'time', lambda: clock[0])
    def delayed(*a, **k):
        raw = original(*a, **k); clock[0] += 5.1; return raw
    monkeypatch.setattr(t, 'original_bytes', delayed)
    with pytest.raises(SourceResponseError) as error: t.SymNewsHttp(time.monotonic() + 25).get_receipt(t.INDEX)
    assert error.value.error_kind == 'original_expired'
    assert len(calls) == 1


def test_lock_release_is_inside_whole_deadline(native, monkeypatch):
    from contextlib import contextmanager
    clock = [100.]
    @contextmanager
    def lock(*a, **k):
        yield True
        clock[0] = 126.
    monkeypatch.setattr(t, '_shared_lock', lock)
    monkeypatch.setattr(t, 'time', SimpleNamespace(time=lambda: NOW, monotonic=lambda: clock[0]))
    # _check is inherited and uses its original module clock; the collector's
    # caller budget is independently exercised in source tests.
    monkeypatch.setattr(t.SymNewsHttp, '_check', lambda self: (_ for _ in ()).throw(SourceResponseError('timeout')) if clock[0] >= self.deadline else None)
    with pytest.raises(SourceResponseError) as error: t.SymNewsHttp(125.).get_receipt(t.INDEX)
    assert error.value.error_kind == 'timeout'


def test_shared_csv_timeout_json_fallback_and_warm_master_keep_truthful_counts(harness, monkeypatch):
    from test_official_issuer_master_json import json_value
    original = t.IssuerMasterHttp.download_original; calls = []
    def fallback(self, url, diagnostic):
        calls.append(url); self.http_request_count += 1; diagnostic.update(http_request_sent=True, http_status=200)
        if url == t.MASTER: raise SourceResponseError('timeout', status_code=200)
        return deepcopy(json_value())
    monkeypatch.setattr(t.IssuerMasterHttp, 'download_original', fallback)
    records, audit = fetch()
    assert len(records) == 2 and audit['http_request_count'] == 8
    proof = records[0]['issuer_news_receipt']['source_record_archive']['master']
    assert proof['source_url'] == t.master.JSON_URL and 'wire_original' in proof
    assert audit['component_receipts'][0]['error_kind'] == 'timeout'
    monkeypatch.setattr(time, 'time', lambda: NOW + 10)
    records, audit = fetch()
    assert len(records) == 2 and audit['http_request_count'] == 6
    assert records[0]['issuer_news_receipt']['source_record_archive']['master']['retrieved_at'] == NOW
    assert calls == [t.MASTER, t.master.JSON_URL]


@pytest.mark.parametrize('kind', ['authentication', 'access_denied', 'rate_limited', 'guard_storage_unavailable', 'lease_lost', 'parse_error'])
def test_shared_master_terminal_failure_never_enters_brand_chain(harness, monkeypatch, kind):
    def fail(self, url, diagnostic): raise SourceResponseError(kind)
    monkeypatch.setattr(t.IssuerMasterHttp, 'download_original', fail)
    records, audit = fetch()
    assert not records and audit['error_kind'] == kind and harness[1] == []
