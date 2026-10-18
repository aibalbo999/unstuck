"""Public boundary checks. Original private-data replay cases remain local."""
import time
import pytest
MASTER_URL = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX_URL = 'https://www.sti.com.tw/earnings-call'
PDF_URL = 'https://www.sti.com.tw/documents/36928/0/115Q2%E6%95%A6%E9%99%BD%E6%B3%95%E8%AA%AASTI_CHN.pdf/899302f6-faa3-f301-c6b7-f7dd8f4dbcbd?t=1785826779822'
NOW = 1791927600.0

def valid_data():
    return {'ticker': '2480.TW', 'instrument_type': 'EQUITY', 'company_name': '敦陽科 / Stark Technology Inc.', 'raw_company_name': 'STARK TECHNOLOGY INC', 'company_identity': {'ticker': '2480.TW', 'stock_id': '2480', 'official_name': '敦陽科', 'legal_name': None, 'display_name': '敦陽科 / Stark Technology Inc.', 'allowed_aliases': ['敦陽科', '2480', '2480.TW', '敦陽科 / Stark Technology Inc.', 'STARK TECHNOLOGY INC'], 'english_names': ['Stark Technology Inc.', 'STARK TECHNOLOGY INC'], 'forbidden_aliases': []}}

@pytest.mark.parametrize('change', ['ticker', 'quote', 'root_stock', 'root_ubn', 'root_legal', 'root_name', 'raw_name', 'identity', 'display', 'legal', 'short', 'ubn', 'allowed', 'english', 'list_type', 'forbidden'])
def test_independent_caller_identity_fields_cannot_borrow_good_aliases(change):
    from data_fetch.market_sources.sti_conference import validate_context
    data = valid_data()
    assert validate_context(data, '2480.TW')
    identity = data['company_identity']
    if change == 'ticker':
        data['ticker'] = '4919.TW'
    elif change == 'quote':
        data['quote_type'] = 'ETF'
    elif change == 'root_stock':
        data['stock_id'] = '4919'
    elif change == 'root_ubn':
        data['official_ubn'] = '00000000'
    elif change == 'root_legal':
        data['legal_name'] = '新唐科技股份有限公司'
    elif change == 'root_name':
        data['company_name'] = '敦陽科 / Nuvoton'
    elif change == 'raw_name':
        data['raw_company_name'] = 'Nuvoton'
    elif change == 'identity':
        data['company_identity'] = False
    elif change == 'display':
        identity['display_name'] = '新唐'
    elif change == 'legal':
        identity['legal_name'] = '新唐科技股份有限公司'
    elif change == 'short':
        identity['official_name'] = '新唐'
    elif change == 'ubn':
        identity['official_ubn'] = '00000000'
    elif change == 'allowed':
        identity['allowed_aliases'].append('新唐')
    elif change == 'english':
        identity['english_names'].append('Nuvoton')
    elif change == 'list_type':
        identity['allowed_aliases'] = 'STI'
    else:
        identity['forbidden_aliases'] = ['*STI / 敦陽科*']
    assert not validate_context(data, '2480.TW')

@pytest.fixture
def native_harness(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store, json
    from data_fetch.market_sources import sti_conference_transport as transport
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
    for key in transport.PROXY_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(transport, 'proxy_url_for_request', lambda *a: None)
    calls = []
    mutation = {}

    def native(argv, deadline, *, body_limit, headers):
        calls.append((argv, deadline, body_limit, headers))
        url = argv[-1]
        spec = transport.request_spec(url)
        ctype = 'text/html' if url == INDEX_URL else 'text/csv' if url == MASTER_URL else 'application/pdf'
        raw = b'<html>public index</html>' if url == INDEX_URL else b'%PDF-guard-test'
        raw = mutation.get('body', raw)
        meta = {'http_code': 200, 'url_effective': url, 'num_redirects': 0, 'size_download': len(raw), 'content_type': ctype, 'method': spec['request_method'], 'proxy_used': 0}
        meta.update(mutation.get('meta', {}))
        header = 'HTTP/1.1 ' + str(mutation.get('status', 200)) + ' OK\r\nContent-Type: ' + ctype + '\r\nContent-Length: ' + str(len(raw)) + '\r\n' + mutation.get('headers', '') + '\r\n'
        return ({'process_started': True, 'body': raw, 'headers': header.encode(), 'metadata': json.dumps(meta).encode()}, mutation.get('rc', 0), mutation.get('error'))
    monkeypatch.setattr(transport, 'collect_capped_process', native)
    yield (transport, calls, mutation)
    cache_store.reset_cache_store_for_tests()

@pytest.mark.parametrize('url', [MASTER_URL, INDEX_URL, PDF_URL])
@pytest.mark.parametrize('budget', [3, 25])
def test_native_request_exact_method_form_limits_metadata_and_warm_zero_HTTP(native_harness, url, budget):
    transport, calls, _ = native_harness
    http = transport.ConferenceHttp(time.monotonic() + budget)
    raw, receipt = http.get_receipt(url)
    args, deadline, limit, headers = calls[0]
    assert len(calls) == 1 and 0 < float(args[args.index('--max-time') + 1]) <= min(5, budget)
    assert float(args[args.index('--connect-timeout') + 1]) <= 2 and limit == transport.contract(url)[0]
    assert args[args.index('--retry') + 1] == '0' and args[args.index('--max-redirs') + 1] == '0'
    assert '--location' not in args and '--cookie' not in args and ('--proxy' not in args)
    assert '--data' not in args and '--request' not in args
    assert {k: receipt[k] for k in ('request_method', 'request_body')} == transport.request_spec(url)
    assert receipt['http_status'] == 200 and receipt['response_complete'] is True and (receipt['cache_hit'] is False)
    assert receipt['response_metadata']['size_download'] == len(raw)
    assert transport.original_bytes(receipt, url, max_age=1800) == raw
    warm = transport.ConferenceHttp(time.monotonic() + 25)
    again, proof = warm.get_receipt(url)
    assert len(calls) == 1 and warm.http_request_count == 0 and (proof['cache_hit'] is True)
    assert proof['retrieved_at'] == receipt['retrieved_at'] and proof['fresh_until_epoch'] == receipt['fresh_until_epoch']

@pytest.mark.parametrize('change', ['401', '403', '429', '504', '302', 'timeout', 'partial', 'size', 'method', 'redirect', 'effective', 'type', 'proxy', 'encoding', 'header_size', 'challenge', 'challenge_zh'])
def test_native_failures_cannot_become_full_original_or_repeat_during_admission(native_harness, change):
    from search_provider_runtime import SourceResponseError
    transport, calls, mutation = native_harness
    if change.isdigit():
        mutation.update(status=int(change), meta={'http_code': int(change)})
    elif change == 'timeout':
        mutation['rc'] = 28
    elif change == 'partial':
        mutation['rc'] = 18
    elif change == 'size':
        mutation['meta'] = {'size_download': 1}
    elif change == 'method':
        mutation['meta'] = {'method': 'POST'}
    elif change == 'redirect':
        mutation['meta'] = {'num_redirects': 1}
    elif change == 'effective':
        mutation['meta'] = {'url_effective': INDEX_URL + '?co_id=2480'}
    elif change == 'type':
        mutation['meta'] = {'content_type': 'application/pdf'}
    elif change == 'proxy':
        mutation['meta'] = {'proxy_used': 1}
    elif change == 'encoding':
        mutation['headers'] = 'Content-Encoding: gzip\r\n'
    elif change == 'header_size':
        mutation['headers'] = 'Content-Length: 100000\r\n'
    elif change == 'challenge_zh':
        mutation['body'] = '<html>因為安全性考量 驗證碼</html>'.encode()
    else:
        mutation['body'] = b'<html>FOR SECURITY REASONS PAGE CAN NOT BE ACCESSED</html>'
    for options in ({}, {'force_refresh': True}, {'use_cache': False}):
        with pytest.raises(SourceResponseError):
            transport.ConferenceHttp(time.monotonic() + 25, **options).get_receipt(INDEX_URL)
    assert len(calls) == 1

def test_GET_singleflight_shares_exact_request(native_harness):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    transport, calls, _ = native_harness
    gate = Barrier(2)

    def request():
        gate.wait()
        return transport.ConferenceHttp(time.monotonic() + 25).get_receipt(INDEX_URL)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request(), range(2)))
    assert len(calls) == 1 and results[0][0] == results[1][0]
    assert sorted((r[1]['cache_hit'] for r in results)) == [False, True]

def test_failure_marker_survives_storage_loss_after_actual_http(native_harness, monkeypatch):
    import cache_store
    from search_provider_runtime import SourceResponseError
    transport, calls, mutation = native_harness
    mutation.update(status=429, meta={'http_code': 429})
    original = transport.collect_capped_process

    def native(*a, **kw):
        parts = original(*a, **kw)

        def unavailable(*a, **kw):
            raise OSError('isolated write loss after HTTP')
        monkeypatch.setattr(cache_store, 'set_cache_json', unavailable)
        import search_provider_runtime
        monkeypatch.setattr(search_provider_runtime, 'set_cache_json', unavailable)
        return parts
    monkeypatch.setattr(transport, 'collect_capped_process', native)
    for options in ({}, {'force_refresh': True}, {'use_cache': False}):
        with pytest.raises(SourceResponseError):
            transport.ConferenceHttp(time.monotonic() + 25, **options).get_receipt(INDEX_URL)
    assert len(calls) == 1
    assert cache_store.get_cache_json(transport.ConferenceHttp._admission_key(INDEX_URL))['retry_at'] == NOW + 120

def test_GET_receipt_metadata_false_cannot_impersonate_zero(native_harness):
    transport, _, _ = native_harness
    _, receipt = transport.ConferenceHttp(time.monotonic() + 25).get_receipt(INDEX_URL)
    receipt['response_metadata']['proxy_used'] = False
    with pytest.raises(ValueError):
        transport.original_bytes(receipt, INDEX_URL, max_age=1800)

@pytest.mark.parametrize('state', [{'retry_at': NOW + 100, 'error_kind': 'access_denied'}, {'retry_at': True}, {'retry_at': float('nan')}, {'retry_at': NOW - 1, 'next_request_at': NOW + 3}])
def test_original_host_guard_is_not_bypassed(native_harness, state):
    import cache_store
    from urllib.parse import urlsplit
    from search_provider_runtime import SourceResponseError, scope_key
    transport, calls, _ = native_harness
    key = scope_key(transport.HTTP_PROVIDER, endpoint=urlsplit(INDEX_URL).hostname)
    cache_store.set_cache_json(key, state, ttl_seconds=1000)
    for options in ({}, {'force_refresh': True}, {'use_cache': False}):
        with pytest.raises(SourceResponseError):
            transport.ConferenceHttp(time.monotonic() + 25, **options).get_receipt(INDEX_URL)
    assert not calls and cache_store.get_cache_json(key) == state

@pytest.mark.parametrize('suffix', ['', ' HOLDINGS', ' EVIL'])
def test_exact_existing_english_identity_alias_requires_full_equality(suffix):
    from data_fetch.market_sources.sti_conference import validate_context
    data = valid_data()
    alias = 'STARK TECHNOLOGY' + suffix
    data['company_identity']['english_names'].append(alias)
    data['company_identity']['allowed_aliases'].append(alias)
    assert validate_context(data, '2480.TW') is (not suffix)

@pytest.mark.parametrize('extra', ['Content-Length: 1\r\n', 'Content-Type: text/html\r\n', 'Content-Encoding: identity\r\nContent-Encoding: gzip\r\n', 'Retry-After: 1\r\nRetry-After: 2\r\n'])
def test_duplicate_protected_headers_keep_actual_HTTP_status(native_harness, extra):
    from search_provider_runtime import SourceResponseError
    transport, calls, mutation = native_harness
    mutation['headers'] = extra
    http = transport.ConferenceHttp(time.monotonic() + 25)
    with pytest.raises(SourceResponseError):
        http.get_receipt(INDEX_URL)
    assert len(calls) == 1 and http.http_request_count == 1
    assert http.components[-1]['http_request_sent'] is True
    assert http.components[-1]['http_status'] == 200
