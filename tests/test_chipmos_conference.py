"""Public boundary checks. Original private-data replay cases remain local."""
import time
import pytest
from data_fetch.market_sources.chipmos_conference_transport import PDF_URL

def valid_data():
    return {'ticker': '8150.TW', 'quote_type': 'EQUITY', 'company_name': '南茂 / ChipMOS TECHNOLOGIES INC.', 'company_identity': {'stock_id': '8150', 'official_name': '南茂', 'legal_name': None, 'allowed_aliases': ['南茂', '8150', '8150.TW', '南茂 / ChipMOS TECHNOLOGIES INC.'], 'english_names': ['ChipMOS TECHNOLOGIES INC.', 'CHIPMOS TECHNOLOGIES INC'], 'forbidden_aliases': []}}

@pytest.mark.parametrize('change', ['ticker', 'instrument_type', 'quote_type', 'quoteType', 'stock_id', 'official_ubn', 'legal_name', 'forbidden', 'allowed', 'english', 'badlist', 'identity', 'name', 'raw_name'])
def test_caller_identity_fail_closed(change):
    from data_fetch.market_sources.chipmos_conference import validate_context
    data = valid_data()
    assert validate_context(data, '8150.TW')
    if change == 'ticker':
        data['ticker'] = '8150.TWO'
    elif change in {'instrument_type', 'quote_type', 'quoteType'}:
        data[change] = 'ETF'
    elif change == 'stock_id':
        data['company_identity'][change] = '8151'
    elif change == 'official_ubn':
        data['company_identity'][change] = '00000000'
    elif change == 'legal_name':
        data['company_identity'][change] = '其他公司'
    elif change == 'forbidden':
        data['company_identity']['forbidden_aliases'] = ['*ChipMOS*']
    elif change == 'allowed':
        data['company_identity']['allowed_aliases'] += ['華邦電']
    elif change == 'english':
        data['company_identity']['english_names'] = ['Winbond']
    elif change == 'badlist':
        data['company_identity']['allowed_aliases'] = '南茂'
    elif change == 'identity':
        data['company_identity'] = False
    elif change == 'name':
        data['company_name'] = '南茂 / 其他公司'
    else:
        data['raw_company_name'] = 'Other Corp'
    assert not validate_context(data, '8150.TW')

@pytest.mark.parametrize('budget', [3, 25])
def test_native_request_budget_no_retry_redirect_proxy_or_cookie(monkeypatch, budget):
    from cache_backends import InMemoryCache
    import cache_store, json
    from data_fetch.market_sources import issuer_news_transport as base
    from data_fetch.market_sources.chipmos_conference_transport import ConferenceHttp
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

@pytest.mark.parametrize('change', ['display_name', 'combined_forbidden'])
def test_explicit_identity_display_and_combined_forbidden_alias_are_bound(change):
    from data_fetch.market_sources.chipmos_conference import validate_context
    data = valid_data()
    if change == 'display_name':
        data['company_identity']['display_name'] = '華邦電'
    else:
        data['company_identity']['forbidden_aliases'] = ['南茂 / ChipMOS']
    assert not validate_context(data, '8150.TW')
