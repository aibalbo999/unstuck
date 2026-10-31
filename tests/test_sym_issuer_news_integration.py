"""SYM supplement crosses the actual public provider and saved-news boundaries."""
from copy import deepcopy
from datetime import datetime, timezone
import time

import pytest

from test_sym_issuer_news import harness, valid_data, fetch, NOW
from test_issuer_news import Http as LegacyHttp


def legacy_http():
    class OriginalTimeHttp(LegacyHttp):
        def get(self, url):
            raw = super().get(url)
            self.components[-1]['fetched_at_epoch'] = NOW - 300
            return raw
    return OriginalTimeHttp('2206.TW')


def test_public_saved_record_verifier_admits_brand_original_without_downgrade(harness):
    from data_fetch.market_sources.issuer_news import verified_issuer_news
    from data_fetch.market_sources.sym_issuer_news import PUBLISHER
    records, _ = fetch()
    assert verified_issuer_news(records[0], valid_data(), today=datetime.fromtimestamp(NOW, timezone.utc).date()) == PUBLISHER
    altered = deepcopy(records[0])
    altered['issuer_news_receipt']['policy'] = 'first-party-issuer-news-v1'
    assert verified_issuer_news(altered, valid_data()) is None


def test_public_provider_keeps_corporate_and_adds_global_as_one_publisher(harness, monkeypatch):
    from data_fetch.market_sources import issuer_news
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.types import FetchRequest
    from news_freshness_policy import apply_news_freshness
    monkeypatch.setattr(issuer_news, 'IssuerNewsHttp', lambda deadline: legacy_http())
    result = IssuerNewsProvider().fetch(FetchRequest.from_ticker('2206.TW'), {'data': valid_data()})
    assert result.status == 'success' and len(result.value) == 3
    assert any('sanyang.com.tw/busnessnews-page' in r['link'] for r in result.value)
    assert sum('sym-global.com/newsroom-page' in r['link'] for r in result.value) == 2
    projection = valid_data()
    apply_news_freshness(projection, records=result.value, cutoff=NOW)
    assert len(projection['recent_catalysts']) == 3
    assert projection['news_selection']['publisher_count'] == 1
    assert result.audit['window_complete'] is False
    assert result.audit['fetched_at_epoch'] == NOW - 300


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

    data = valid_data(); data['quoteType'] = 'ETF'
    snapshot = {'ticker': '2206.TW', 'data': data,
                'source_audit': [{'source': 'market_data', 'status': 'success', 'fetched_at_epoch': time.time() - 20}]}
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
            return ProviderResult('recent_catalysts', self.name, 'unavailable', value=[],
                                  audit={'source': 'recent_catalysts', 'provider': self.name,
                                         'status': 'unavailable', 'record_count': 0})
    class Registry:
        def for_request(self, request, source):
            return [Provider()]
    context = {'data': valid_data()}
    request = FetchRequest.from_ticker('2206.TW', record_provider_sla=False)
    asyncio.run(StockDataService(registry=Registry()).fetch_source_async(request, 'issuer_news', context=context))
    assert seen == [context]


@pytest.mark.parametrize('partial', [False, True])
def test_actual_source_refresh_preserves_other_data_and_news_quality_gate(harness, monkeypatch, partial):
    import asyncio
    from data_fetch.market_sources import issuer_news
    from data_fetch.service import StockDataService
    from report_source_refresh import fetch_report_source_data
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    from test_sanyang_news_bundle import partial_global
    monkeypatch.setattr(issuer_news, 'IssuerNewsHttp', lambda deadline: legacy_http())
    if partial:
        partial_global(monkeypatch)
    old_record, _ = issuer_news.fetch_recent_issuer_news('2206.TW', now=datetime.fromtimestamp(NOW, timezone.utc))
    old = valid_data()
    old.update(recent_catalysts=old_record, current_price=45., financial_currency='TWD',
               revenue_ttm_raw=1234000000, years=['2021', '2022', '2023', '2024', '2025'],
               social_sentiment=[{'text': 'old social'}], report_quality_gate={'passed': False, 'reason': 'source_gap'})
    audits = [{'source': 'market_data', 'provider': 'saved quote', 'status': 'success', 'fetched_at_epoch': NOW - 600, 'record_count': 1},
              {'source': 'financial_statements', 'provider': 'saved finance', 'status': 'success', 'fetched_at_epoch': NOW - 700, 'record_count': 5}]
    snapshot = {'ticker': '2206.TW', 'data': old, 'source_audit': audits}
    before = deepcopy(snapshot)
    merged = asyncio.run(fetch_report_source_data(snapshot, 'issuer_news', StockDataService()))
    assert snapshot == before
    assert len(merged['recent_catalysts']) == (2 if partial else 3)
    assert merged['source_audit'][:2] == audits
    audit = merged['source_audit'][-1]
    assert audit['status'] == ('degraded_enrichment' if partial else 'success')
    assert audit['fetched_at_epoch'] == NOW - 300 and audit['window_complete'] is False
    assert merged['news_selection']['publisher_count'] == 1
    for key in ('company_identity', 'current_price', 'financial_currency', 'revenue_ttm_raw', 'years', 'social_sentiment', 'report_quality_gate'):
        assert merged[key] == old[key]
    assert not search_quality_satisfied([SearchResult(r['title'], r['text'], r['link'], r['publisher'], r['date'])
                                         for r in merged['recent_catalysts']], max_results=8, query='三陽工業', require_recent=True,
                                         cutoff=datetime.fromtimestamp(NOW, timezone.utc))


@pytest.mark.parametrize('tamper', ['remove_policy', 'false_http_count'])
def test_source_merge_rejects_tampered_bundle_even_with_valid_articles(harness, monkeypatch, tamper):
    from data_fetch.market_sources import issuer_news
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.types import FetchRequest
    from report_source_refresh import _merge_issuer_news
    from fastapi import HTTPException
    monkeypatch.setattr(issuer_news, 'IssuerNewsHttp', lambda deadline: legacy_http())
    result = IssuerNewsProvider().fetch(FetchRequest.from_ticker('2206.TW'), {'data': valid_data()})
    audit = deepcopy(result.audit); audit['fetch_id'] = 'isolated-test'
    if tamper == 'remove_policy':
        audit.pop('selection_policy')
    else:
        audit['http_request_count'] += 1
    with pytest.raises(HTTPException) as error:
        _merge_issuer_news(valid_data(), [], result.value, [audit], '2206.TW')
    assert error.value.status_code == 502
