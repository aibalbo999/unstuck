"""Independent bounded public-interface probes for the two exact issuer routes."""
from copy import deepcopy
import asyncio
import json
import pytest

from test_unitech_conference import harness as unitech_harness
from test_tcfhc_issuer_news import native_news


@pytest.mark.parametrize('kind', ['lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'])
def test_unitech_lifecycle_abort_does_not_launch_other_source(monkeypatch, kind):
    from data_fetch import earnings_call_fetcher as wrapper
    from data_fetch.market_sources import unitech_conference as source
    from search_provider_runtime import SourceResponseError
    seen = []
    def abort(*a, **kw):
        seen.append('unitech')
        raise SourceResponseError(kind)
    monkeypatch.setattr(source, 'fetch_unitech_context', abort)
    monkeypatch.setattr(wrapper, '_fetch_official_index_context', lambda *a, **kw: pytest.fail('typed abort launched fallback'))
    with pytest.raises(SourceResponseError) as caught:
        wrapper.fetch_free_earnings_call_context('2367.TW')
    assert caught.value.error_kind == kind and seen == ['unitech']


def test_unitech_remote_failure_stays_in_successful_official_fallback_components(monkeypatch):
    from data_fetch import earnings_call_fetcher as wrapper
    from data_fetch.market_sources import unitech_conference as source
    from search_provider_runtime import SourceResponseError
    def failed(*a, **kw):
        e = SourceResponseError('server_error', status_code=503)
        e.diagnostic.update(actual_provider=source.PROVIDER, unitech_presentation_workflow=True,
                            http_request_sent=True, http_request_count=2)
        raise e
    def fallback(ticker, *, diagnostics, **kw):
        diagnostics.update(actual_provider='MOPS investor conference', http_request_sent=True,
                           http_request_count=1, component_statuses={'index': {'http_status': 200}})
        return {'ticker': ticker, 'source': 'MOPS investor conference', 'date': '2026-10-10'}
    monkeypatch.setattr(source, 'fetch_unitech_context', failed)
    monkeypatch.setattr(wrapper, '_fetch_official_index_context', fallback)
    d = {}
    v = wrapper.fetch_free_earnings_call_context('2367.TW', diagnostics=d)
    assert v['source'] == d['actual_provider'] == 'MOPS investor conference'
    assert d['component_statuses']['Unitech_presentation']['error_kind'] == 'server_error'
    assert d['component_statuses']['Unitech_presentation']['http_request_count'] == 2
    assert 'unitech_originals_verified' not in d


@pytest.mark.parametrize('target', ['2367.TW', '5880.TW'])
def test_changed_request_cannot_reuse_other_exact_issuer_context(monkeypatch, target):
    from data_fetch import enrichment_providers
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.market_sources import issuer_news
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', lambda *a, **kw: pytest.fail('cross-issuer HTTP'))
    monkeypatch.setattr(issuer_news, 'fetch_recent_issuer_news', lambda *a, **kw: pytest.fail('cross-issuer HTTP'))
    provider = enrichment_providers.EarningsCallProvider() if target == '2367.TW' else IssuerNewsProvider()
    r = provider.fetch(FetchRequest.from_ticker(target), {'data': {'ticker': '3042.TW', 'quote_type': 'EQUITY', 'company_name': '晶技'}})
    assert r.status == 'unavailable' and r.audit['event_kind'] == 'local_block'
    assert r.audit['http_request_sent'] is False and r.audit['record_count'] == 0


def test_public_source_only_rejects_removed_receipt_with_recognizable_unitech_URL(unitech_harness, monkeypatch, tmp_path):
    from fastapi import HTTPException
    from data_fetch import enrichment_providers
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_refresh_acquisition_audit import init_db
    from test_unitech_tcfhc_source_integration import saved_target
    init_db()
    storage = InMemoryStorage()
    filename, keys, before = saved_target(storage, '2367.TW', '燿華')
    original = storage.get_report(keys.data_key).content
    fetch = enrichment_providers.fetch_free_earnings_call_context
    def remove_marker(*a, **kw):
        value = fetch(*a, **kw)
        value.pop('unitech_conference_receipt')
        value['source'] = 'MOPS investor conference'
        value['source_url'] = 'https://mops.twse.com.tw/'
        value['documents'][0]['source'] = 'MOPS investor conference'
        return value
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', remove_marker)
    service = StockDataService(registry=ProviderRegistry([enrichment_providers.EarningsCallProvider()]))
    call = refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
                                        refresh_service=service, source='earnings_call')
    with pytest.raises(HTTPException) as caught:
        asyncio.run(call)
    assert caught.value.status_code == 502
    assert storage.get_report(keys.data_key).content == original
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content == b'original conclusions'


def test_normal_news_provider_new_metadata_cannot_count_cached_parent_as_new_body(native_news, monkeypatch):
    import time
    from hashlib import sha256
    from cache_store import set_cache_json
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.market_sources import issuer_news, tcfhc_issuer_news as source
    from data_fetch.types import FetchRequest
    from provider_acquisition import project_acquisition_events
    from test_tcfhc_issuer_news import NOW, MASTER, INDEX, PARENT, SPORTS, DATA
    clock = [NOW.timestamp()]
    monkeypatch.setattr(time, 'time', lambda: clock[0])
    monkeypatch.setattr(issuer_news, 'fetch_recent_issuer_news',
                        lambda ticker: source.fetch_recent_news(now=NOW))
    provider = IssuerNewsProvider()
    request = FetchRequest.from_ticker('5880.TW')
    first = provider.fetch(request, {'data': deepcopy(DATA)})
    assert first.status == 'success' and len(first.value) == 1
    old_epoch = first.value[0]['issuer_news_receipt']['source_record_archive']['article']['retrieved_at']
    for url in (MASTER, INDEX, SPORTS):
        key = 'shared_provider:v1:' + sha256((source.NewsHttp.raw_cache_prefix + url).encode()).hexdigest()
        set_cache_json(key, {}, ttl_seconds=1)
    clock[0] += 2
    second = provider.fetch(request, {'data': deepcopy(DATA)})
    assert second.status == 'skipped_fresh_cache' and second.audit['cache_hit'] is True
    assert second.audit['http_request_count'] == 3 and second.audit['http_request_sent'] is True
    assert second.value[0]['issuer_news_receipt']['source_record_archive']['article']['retrieved_at'] == old_epoch
    assert native_news[2][-1][0][-1] == SPORTS
    assert sum(call[0][-1] == PARENT for call in native_news[2]) == 1
    event = {**second.audit, 'created_at': clock[0], 'details_json': json.dumps(second.audit)}
    counts = project_acquisition_events([event], window='last_24h', now=clock[0])['sources'][0]
    assert counts['fresh_cache_count'] == 1 and counts['fetched_count'] == counts['fetch_attempts'] == 0


def test_parent_original_receipts_stay_private_after_public_freshness_normalization(monkeypatch):
    import time
    from test_tcfhc_issuer_news import NOW, Http, DATA
    from data_fetch.market_sources import tcfhc_issuer_news as source
    from news_freshness_policy import apply_news_only_freshness
    from prompt_evidence import prompt_evidence_copy
    monkeypatch.setattr(time, 'time', lambda: NOW.timestamp())
    rows, audit = source.fetch_recent_news(now=NOW, http=Http())
    data = deepcopy(DATA)
    apply_news_only_freshness(data, cutoff=NOW, records=rows)
    row = data['recent_catalysts'][0]
    assert source.verified_record(row, DATA, today=NOW.date()) == 'TCFHC'
    before = deepcopy(row)
    view = prompt_evidence_copy({'recent_catalysts': [row]})
    assert row == before
    assert not any(term in str(view) for term in ('raw_response_path', 'source_record_archive', 'body_b64'))
    assert view['recent_catalysts'][0]['publisher'] == 'TCFHC'
    assert view['recent_catalysts'][0]['source_role'] == 'issuer_statement'
    tampered = deepcopy(row)
    tampered['published_date'] = '2026-10-08T00:00:00+00:00'
    assert source.verified_record(tampered, DATA, today=NOW.date()) is None
