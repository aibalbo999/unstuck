"""Public boundary checks. Original private-data replay cases remain local."""
import time
import pytest
from data_fetch.market_sources.csc_conference_transport import INDEX_URL, PDF_URL

def valid_data():
    return {'ticker': '2002.TW', 'instrument_type': 'EQUITY', 'company_name': '中鋼 / China Steel Corporation', 'raw_company_name': 'China Steel Corporation', 'company_identity': {'ticker': '2002.TW', 'stock_id': '2002', 'official_name': '中鋼', 'legal_name': None, 'display_name': '中鋼 / China Steel Corporation', 'allowed_aliases': ['中鋼', '2002', '2002.TW', '中鋼 / China Steel Corporation', 'CSC'], 'english_names': ['China Steel Corporation', 'CSC'], 'forbidden_aliases': []}}

@pytest.mark.parametrize('change', ['ticker', 'instrument', 'legal', 'ubn', 'alias', 'forbidden', 'name', 'bool'])
def test_identity_context_contradictions_rejected(change):
    from data_fetch.market_sources.csc_conference import validate_context
    data = valid_data()
    assert validate_context(data, '2002.TW')
    if change == 'ticker':
        data['company_identity']['stock_id'] = '2002A'
    elif change == 'instrument':
        data['quoteType'] = 'ETF'
    elif change == 'legal':
        data['company_identity']['legal_name'] = '中國鋼鐵結構股份有限公司'
    elif change == 'ubn':
        data['company_identity']['official_ubn'] = '00000000'
    elif change == 'alias':
        data['company_identity']['allowed_aliases'].append('中鋼構')
    elif change == 'forbidden':
        data['company_identity']['forbidden_aliases'].append('CSC')
    elif change == 'name':
        data['raw_company_name'] = 'China Steel Structure Co., Ltd.'
    else:
        data['company_identity']['stock_id'] = True
    assert not validate_context(data, '2002.TW')

@pytest.mark.parametrize('budget', [3, 25])
def test_native_request_budget_no_retry_redirect_proxy_or_cookie(monkeypatch, budget):
    from cache_backends import InMemoryCache
    import cache_store, json
    from data_fetch.market_sources import issuer_news_transport as base
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    cache_store.set_cache_backend(InMemoryCache())
    calls = []
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
    for key in base.PROXY_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(base, 'proxy_url_for_request', lambda *a: None)

    def native(argv, deadline, *, body_limit, headers):
        calls.append((argv, deadline, body_limit, headers))
        url = argv[-1]
        return ({'process_started': True, 'body': b'%PDF-guard-test', 'headers': b'HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\n\r\n', 'metadata': json.dumps({'http_code': 200, 'url_effective': url, 'num_redirects': 0}).encode()}, 0, None)
    monkeypatch.setattr(base, 'collect_capped_process', native)
    http = ConferenceHttp(time.monotonic() + budget)
    raw, receipt = http.get_receipt(PDF_URL)
    argv, deadline, limit, headers = calls[0]
    assert len(calls) == 1 and 0 < float(argv[argv.index('--max-time') + 1]) <= min(5, budget)
    assert float(argv[argv.index('--connect-timeout') + 1]) <= 2 and limit == 8 * 1024 * 1024
    assert argv[argv.index('--retry') + 1] == '0' and argv[argv.index('--max-redirs') + 1] == '0'
    assert '--location' not in argv and '--cookie' not in argv and ('--proxy' not in argv)
    assert receipt['http_status'] == 200 and receipt['response_complete'] is True and (receipt['cache_hit'] is False)
    cache_store.reset_cache_store_for_tests()

def test_native_csc_index_request_gets_targeted_timeout(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store, json
    from data_fetch.market_sources import issuer_news_transport as base
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for key in base.PROXY_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(base, 'proxy_url_for_request', lambda *a: None)
    calls = []
    body = b'<html></html>'

    def native(argv, deadline, *, body_limit, headers):
        calls.append((argv, deadline, body_limit, headers))
        url = argv[-1]
        return ({'process_started': True, 'body': body, 'headers': f'HTTP/2 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(body)}\r\n\r\n'.encode(), 'metadata': json.dumps({'http_code': 200, 'url_effective': url, 'num_redirects': 0, 'size_download': len(body), 'content_type': 'text/html', 'method': 'GET', 'proxy_used': 0}).encode()}, 0, None)
    monkeypatch.setattr(base, 'collect_capped_process', native)
    try:
        http = ConferenceHttp(time.monotonic() + 25, force_refresh=True)
        value = http._download(INDEX_URL, {'url': INDEX_URL})
        argv, deadline, limit, _ = calls[0]
        assert value['url'] == INDEX_URL and len(calls) == 1
        assert float(argv[argv.index('--max-time') + 1]) == 8
        assert float(argv[argv.index('--connect-timeout') + 1]) == 6
        assert argv[argv.index('--retry') + 1] == '0' and argv[argv.index('--max-redirs') + 1] == '0'
    finally:
        cache_store.reset_cache_store_for_tests()
