"""New free originals reach real provider and report boundaries without loose identity."""
from copy import deepcopy
import asyncio
import json
import pytest
from test_unitech_conference import harness as unitech_harness
from test_tcfhc_issuer_news import native_news
from test_shared_provider_cache import memory_cache


def test_tcfhc_parent_news_has_a_free_provider_route():
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.types import FetchRequest
    registry = ProviderRegistry()
    for ticker in ('5880.TW', '5880'):
        assert 'Verified issuer news' in registry.provider_names(FetchRequest.from_ticker(ticker), 'recent_catalysts')
    assert 'Verified issuer news' not in registry.provider_names(FetchRequest.from_ticker('5880.TWO'), 'recent_catalysts')


def test_unitech_private_receipt_is_not_agent_prompt_content():
    from prompt_evidence import prompt_evidence_copy
    value = {'ticker': '2367.TW', 'unitech_conference_receipt': {'raw_response_path': '/internal/cache/original.gz'}}
    before = deepcopy(value)
    assert 'unitech_conference_receipt' not in prompt_evidence_copy(value)
    assert value == before


def test_unitech_role_view_preserves_missing_charts_and_ownership_notice():
    from conference_presentation_prompt import presentation_prompt_context
    document = {'document_kind': 'presentation', 'source': 'Unitech official conference presentation',
                'page_count': 16, 'pages': [{'page_number': 9, 'text': '財務概況與未來展望'}],
                'known_native_text_omissions': [{'page_number': 9, 'issue': 'chart_values_not_extracted'}],
                'ownership_confidentiality_notice_present': True, 'commercial_reuse_permission_verified': False,
                'content_period': None, 'event_date_basis': 'issuer_index_and_PDF_cover',
                'event_status': 'announced_past_not_independently_verified', 'event_time': '14:00',
                'event_timezone': None}
    before = deepcopy(document)
    for role in (3, 5, 12):
        projected = presentation_prompt_context({'documents': [document]}, role)['documents'][0]
        for field in ('known_native_text_omissions', 'ownership_confidentiality_notice_present',
                      'commercial_reuse_permission_verified', 'content_period', 'event_date_basis',
                      'event_status', 'event_time', 'event_timezone'):
            assert field in projected and projected[field] == document[field]
    assert document == before


@pytest.mark.parametrize('target', ['2367.TW', '5880.TW'])
@pytest.mark.parametrize('malformed', [False, [], 'not a data mapping', 3])
def test_new_provider_rejects_explicit_invalid_data_before_acquisition(monkeypatch, target, malformed):
    from data_fetch import enrichment_providers
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.market_sources import issuer_news
    from data_fetch.types import FetchRequest
    def forbidden(*a, **kw):
        pytest.fail('malformed original context reached an external source')
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', forbidden)
    monkeypatch.setattr(issuer_news, 'fetch_recent_issuer_news', forbidden)
    provider = enrichment_providers.EarningsCallProvider() if target == '2367.TW' else IssuerNewsProvider()
    result = provider.fetch(FetchRequest.from_ticker(target), {'data': malformed})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block'
    assert result.audit['http_request_count'] == result.audit['record_count'] == 0


def saved_target(storage, ticker, name):
    from test_report_source_refresh import saved_report
    from report_analysis_evidence import capture_analysis_evidence
    filename, keys, value = saved_report(storage)
    def replace(item):
        if isinstance(item, str): return item.replace('6214.TW', ticker).replace('精誠', name)
        if isinstance(item, dict): return {k: replace(v) for k, v in item.items()}
        if isinstance(item, list): return [replace(v) for v in item]
        return item
    value = replace(value)
    value['data']['quote_type'] = 'EQUITY'
    value['data']['social_sentiment'] = {'original': 'old independently dated sample'}
    value['data']['recent_catalysts'] = [{'title': name + '原有新聞', 'date': '2026-10-12',
        'text': name + '原有新闻事实', 'source': 'other publisher', 'link': 'https://example.org/old-news'}]
    value['analysis_evidence'] = capture_analysis_evidence({'data': value['data']}, generated_at=value['generated_at'])
    storage.save_report(keys.data_key, json.dumps(value).encode(), content_type='application/json')
    return filename, keys, value


def assert_preserved(storage, keys, before, after):
    for field in ('current_price', 'revenue_history', 'years', 'peer_discovery_results', 'social_sentiment'):
        assert after['data'][field] == before['data'][field]
    for field in ('analysis_evidence', 'report_lint', 'final_audit', 'evidence_exit_gate', 'content_credibility', 'report_conformance'):
        assert after[field] == before[field]
    assert before['source_audit'][0] in after['source_audit']
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content == b'original conclusions'


@pytest.mark.parametrize('tamper', [False, True])
def test_unitech_public_source_only_preserves_original_report(unitech_harness, tmp_path, monkeypatch, tamper):
    from fastapi import HTTPException
    from data_fetch import enrichment_providers
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_refresh_acquisition_audit import init_db, events
    init_db(); storage = InMemoryStorage()
    filename, keys, before = saved_target(storage, '2367.TW', '燿華')
    original = storage.get_report(keys.data_key).content
    if tamper:
        real = enrichment_providers.fetch_free_earnings_call_context
        def acquire(*a, **kw):
            value = real(*a, **kw)
            value['documents'][0]['pages'][0]['text'] += ' forged 99999'
            return value
        monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', acquire)
    provider = enrichment_providers.EarningsCallProvider()
    provider_fetch = provider.fetch
    def with_original_context(request, context=None):
        assert context['data'] == before['data']
        return provider_fetch(request, context)
    monkeypatch.setattr(provider, 'fetch', with_original_context)
    service = StockDataService(registry=ProviderRegistry([provider]))
    call = refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
        refresh_service=service, source='earnings_call', return_refreshed_data=True)
    if tamper:
        with pytest.raises(HTTPException) as caught: asyncio.run(call)
        assert caught.value.status_code == 502 and storage.get_report(keys.data_key).content == original
    else:
        response = asyncio.run(call)
        after = json.loads(storage.get_report(keys.data_key).content)
        assert after['data']['earnings_call']['documents'][0]['page_count'] == 16
        assert after['data']['recent_catalysts'] == before['data']['recent_catalysts']
        assert response['analysis_text_stale'] is True
        assert_preserved(storage, keys, before, after)
    observed = events()
    assert len(observed) == 1 and observed[0]['source'] == 'earnings_call'
    assert len(unitech_harness[1]) == 3


@pytest.mark.parametrize('tamper', [False, True])
def test_tcfhc_public_source_only_adds_parent_without_other_fetches(tmp_path, monkeypatch, tamper, native_news, memory_cache):
    import time
    from fastapi import HTTPException
    from test_tcfhc_issuer_news import NOW
    from data_fetch.market_sources import tcfhc_issuer_news as source
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_refresh_acquisition_audit import init_db, events
    monkeypatch.setattr(time, 'time', lambda: NOW.timestamp())
    original_fetch = source.fetch_recent_news
    def acquire(*, now, http=None):
        records, audit = original_fetch(now=now, http=http)
        if tamper: records[0]['publisher'] = 'invented independent publisher'
        return records, audit
    monkeypatch.setattr(source, 'fetch_recent_news', acquire)
    init_db(); storage = InMemoryStorage()
    filename, keys, before = saved_target(storage, '5880.TW', '合庫金')
    original = storage.get_report(keys.data_key).content
    provider = IssuerNewsProvider()
    provider_fetch = provider.fetch
    def with_original_context(request, context=None):
        assert context['data'] == before['data']
        return provider_fetch(request, context)
    monkeypatch.setattr(provider, 'fetch', with_original_context)
    service = StockDataService(registry=ProviderRegistry([provider]))
    call = refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
        refresh_service=service, source='issuer_news', return_refreshed_data=True)
    if tamper:
        with pytest.raises(HTTPException) as caught: asyncio.run(call)
        assert caught.value.status_code == 502 and storage.get_report(keys.data_key).content == original
    else:
        response = asyncio.run(call)
        after = json.loads(storage.get_report(keys.data_key).content)
        assert len(after['data']['recent_catalysts']) == 2
        old_news = before['data']['recent_catalysts'][0]
        assert any(row['link'] == old_news['link'] and row['text'] == old_news['text']
                   for row in after['data']['recent_catalysts'])
        assert after['data']['earnings_call'] == before['data']['earnings_call']
        assert response['analysis_text_stale'] is True
        assert_preserved(storage, keys, before, after)
    observed = events()
    assert len(observed) == 1 and observed[0]['source'] == 'recent_catalysts'
    assert len(native_news[2]) == 4
