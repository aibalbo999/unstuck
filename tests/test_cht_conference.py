"""Public boundary checks. Original private-data replay cases remain local."""
import time
import pytest
from data_fetch.market_sources.cht_conference_transport import PDF_URL, PUBLISHED_PDF_URL

def valid_data():
    return {'ticker': '2412.TW', 'instrument_type': 'EQUITY', 'company_name': '中華電 / Chunghwa Telecom Co., Ltd.', 'raw_company_name': 'Chunghwa Telecom Co., Ltd.', 'company_identity': {'ticker': '2412.TW', 'stock_id': '2412', 'official_name': '中華電', 'legal_name': None, 'display_name': '中華電 / Chunghwa Telecom Co., Ltd.', 'allowed_aliases': ['中華電', '2412', '2412.TW', '中華電 / Chunghwa Telecom Co., Ltd.', 'CHT'], 'english_names': ['Chunghwa Telecom Co., Ltd.', 'CHT'], 'forbidden_aliases': []}}

@pytest.mark.parametrize('change', ['ticker', 'instrument', 'legal', 'ubn', 'alias', 'forbidden', 'name', 'bool'])
def test_identity_context_contradictions_rejected(change):
    from data_fetch.market_sources.cht_conference import validate_context
    data = valid_data()
    assert validate_context(data, '2412.TW')
    if change == 'ticker':
        data['company_identity']['stock_id'] = '2412A'
    elif change == 'instrument':
        data['quoteType'] = 'ETF'
    elif change == 'legal':
        data['company_identity']['legal_name'] = '中華電信子公司'
    elif change == 'ubn':
        data['company_identity']['official_ubn'] = '00000000'
    elif change == 'alias':
        data['company_identity']['allowed_aliases'].append('中華電構')
    elif change == 'forbidden':
        data['company_identity']['forbidden_aliases'].append('CHT')
    elif change == 'name':
        data['raw_company_name'] = 'Other Telecom Co., Ltd.'
    else:
        data['company_identity']['stock_id'] = True
    assert not validate_context(data, '2412.TW')

@pytest.mark.parametrize('budget', [3, 25])
@pytest.mark.parametrize('pdf_url', [PDF_URL, PUBLISHED_PDF_URL])
def test_native_request_budget_no_retry_redirect_proxy_or_cookie(monkeypatch, budget, pdf_url):
    from cache_backends import InMemoryCache
    import cache_store, json
    from data_fetch.market_sources import issuer_news_transport as base
    from data_fetch.market_sources.cht_conference_transport import ConferenceHttp
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
    raw, receipt = http.get_receipt(pdf_url)
    argv, deadline, limit, headers = calls[0]
    assert len(calls) == 1 and 0 < float(argv[argv.index('--max-time') + 1]) <= min(5, budget)
    assert float(argv[argv.index('--connect-timeout') + 1]) <= 2 and limit == 8 * 1024 * 1024
    assert argv[argv.index('--retry') + 1] == '0' and argv[argv.index('--max-redirs') + 1] == '0'
    assert '--location' not in argv and '--cookie' not in argv and ('--proxy' not in argv)
    assert receipt['http_status'] == 200 and receipt['response_complete'] is True and (receipt['cache_hit'] is False)
    cache_store.reset_cache_store_for_tests()
