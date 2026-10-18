"""Public boundary checks. Original private-data replay cases remain local."""
import time
import pytest
from data_fetch.market_sources.winbond_conference_transport import PDF_URL

def valid_data():
    return {'ticker': '2344.TW', 'instrument_type': 'EQUITY', 'company_name': '華邦電 / Winbond Electronics Corporation', 'raw_company_name': 'Winbond Electronics Corporation', 'company_identity': {'ticker': '2344.TW', 'stock_id': '2344', 'official_name': '華邦電', 'legal_name': None, 'display_name': '華邦電 / Winbond Electronics Corporation', 'allowed_aliases': ['華邦電', '2344', '2344.TW', '華邦電 / Winbond Electronics Corporation', 'WINBOND ELECTRONIC CORP'], 'english_names': ['Winbond Electronics Corporation', 'WINBOND ELECTRONIC CORP'], 'forbidden_aliases': []}}

@pytest.mark.parametrize('budget', [3, 25])
def test_native_request_budget_no_retry_redirect_proxy_or_cookie(monkeypatch, budget):
    from cache_backends import InMemoryCache
    import cache_store, json
    from data_fetch.market_sources import issuer_news_transport as base
    from data_fetch.market_sources.winbond_conference_transport import ConferenceHttp
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

@pytest.mark.parametrize('change', ['ticker', 'quote', 'root_stock', 'root_ubn', 'root_legal', 'root_name', 'raw_name', 'identity', 'display', 'legal', 'short', 'ubn', 'allowed', 'english', 'list_type', 'forbidden'])
def test_independent_caller_identity_fields_cannot_borrow_good_aliases(change):
    from data_fetch.market_sources.winbond_conference import validate_context
    data = valid_data()
    assert validate_context(data, '2344.TW')
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
        data['company_name'] = '華邦電 / Nuvoton'
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
        identity['allowed_aliases'] = 'Winbond'
    else:
        identity['forbidden_aliases'] = ['*Winbond / 華邦電*']
    assert not validate_context(data, '2344.TW')
