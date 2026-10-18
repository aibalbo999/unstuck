"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
import time
import pytest
from test_sym_issuer_news import valid_data

@pytest.mark.parametrize('change', ['quoteType', 'ticker', 'company_identity'])
def test_public_provider_rejects_wrong_context_before_any_fetch(monkeypatch, change):
    from data_fetch.market_sources import issuer_news
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.types import FetchRequest
    calls = []
    monkeypatch.setattr(issuer_news, 'fetch_recent_issuer_news', lambda *a, **k: (calls.append(a) or [], {'status': 'error'}))
    data = valid_data()
    data[change] = {'quoteType': 'ETF', 'ticker': '2207.TW', 'company_identity': False}[change]
    result = IssuerNewsProvider().fetch(FetchRequest.from_ticker('2206.TW'), {'data': data})
    assert result.status in {'unavailable', 'error'}
    assert result.audit.get('error_kind') == 'context_unverified' and calls == []

def test_source_only_rejects_false_instrument_before_provider_call():
    import asyncio
    from fastapi import HTTPException
    from report_source_refresh import fetch_report_source_data
    calls = []

    class Service:
        _fetcher = None

        async def fetch_source_async(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise RuntimeError('Should not reach provider')
    data = valid_data()
    data['quoteType'] = 'ETF'
    snapshot = {'ticker': '2206.TW', 'data': data, 'source_audit': [{'source': 'market_data', 'status': 'success', 'fetched_at_epoch': time.time() - 20}]}
    with pytest.raises(HTTPException) as error:
        asyncio.run(fetch_report_source_data(snapshot, 'issuer_news', Service()))
    assert error.value.status_code == 400 and calls == []

@pytest.mark.parametrize('data', [False, [], 0, '', None])
def test_public_provider_rejects_explicit_malformed_context_without_network(monkeypatch, data):
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.types import FetchRequest
    from data_fetch.market_sources import sanyang_news_bundle

    def forbidden(**kwargs):
        pytest.fail('malformed context reached acquisition')
    monkeypatch.setattr(sanyang_news_bundle, 'fetch_recent_sanyang_news', forbidden)
    result = IssuerNewsProvider().fetch(FetchRequest.from_ticker('2206.TW'), {'data': data})
    assert result.status == 'unavailable'
    assert result.audit['error_kind'] == 'context_unverified'

def test_source_service_passes_existing_issuer_context_to_provider():
    import asyncio
    from data_fetch.service import StockDataService
    from data_fetch.types import FetchRequest, ProviderResult
    seen = []

    class Provider:
        name = 'Verified issuer news'

        async def fetch_async(self, request, context):
            seen.append(deepcopy(context))
            return ProviderResult('recent_catalysts', self.name, 'unavailable', value=[], audit={'source': 'recent_catalysts', 'provider': self.name, 'status': 'unavailable', 'record_count': 0})

    class Registry:

        def for_request(self, request, source):
            return [Provider()]
    context = {'data': valid_data()}
    request = FetchRequest.from_ticker('2206.TW', record_provider_sla=False)
    asyncio.run(StockDataService(registry=Registry()).fetch_source_async(request, 'issuer_news', context=context))
    assert seen == [context]
