"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
import data_fetch.market_sources.twse_security_identity as source
from data_fetch.market_sources.official_company_legal_name import URLS
from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition'
EPOCH = 1791701709.0

@pytest.fixture(autouse=True)
def isolated_circuit(monkeypatch):
    import os
    from provider_resilience import clear_provider_circuits, clear_provider_throttles
    assert os.environ.get('STOCK_AGENT_TEST_NO_NETWORK') == '1'
    clear_provider_circuits(source.PROVIDER)
    clear_provider_throttles(source.PROVIDER)
    monkeypatch.setattr(source, 'time', SimpleNamespace(time=lambda: EPOCH + 60, monotonic=time.monotonic))
    yield
    clear_provider_circuits(source.PROVIDER)
    clear_provider_throttles(source.PROVIDER)

def native(monkeypatch, *, change=None, cached=False):
    calls = []
    identity = (FIXTURES / 'eink8069_isin_native_20261011.html').read_bytes()
    master = (FIXTURES / 'tpex_complete_company_master_native_20261011.json').read_bytes()

    def get(self, url):
        calls.append(url)
        assert url in {source.query_url('8069.TWO'), URLS['.TWO']}
        raw = master if url == URLS['.TWO'] else identity
        if change:
            raw = change(url, raw)
        self.components.append({'url': url, 'cache_hit': cached, 'http_request_sent': not cached, 'http_request_count': 0 if cached else 1, 'fetched_at_epoch': EPOCH})
        self.http_request_count += 0 if cached else 1
        return raw
    monkeypatch.setattr(IssuerNewsHttp, 'get', get)
    return calls

@pytest.mark.parametrize('ticker,fixture', [('8069.TW', 'eink8069_isin_native_20261011.html'), ('6669.TWO', 'twse_isin_6669_captured_20261011.html')])
def test_suffix_must_match_explicit_native_market(ticker, fixture):
    with pytest.raises(ValueError):
        source.parse_security((FIXTURES / fixture).read_bytes(), ticker, EPOCH)

def test_OTC_receipt_cannot_substitute_listed_master_or_market_suffix(monkeypatch):
    native(monkeypatch)
    value = source.fetch_security_identity('8069.TWO', diagnostics={})
    assert source.verified_security_identity(value, '8069.TWO')
    changed = deepcopy(value)
    changed['source_record_archive']['otc_master']['source_url'] = URLS['.TW']
    assert not source.verified_security_identity(changed, '8069.TWO')
    changed = deepcopy(value)
    changed['source_record_archive']['listed_master'] = changed['source_record_archive'].pop('otc_master')
    assert not source.verified_security_identity(changed, '8069.TWO')
    assert not source.verified_security_identity(value, '8069.TW')
