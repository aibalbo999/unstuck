import asyncio
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from data_fetch.types import FetchRequest, ProviderResult
from data_fetch.provider_base import DataProvider
from data_fetch.provider_registry import ProviderRegistry


def source_value():
    return {'status': 'partial', 'actual_provider': 'TWSE official disclosures',
            'coverage_notes': ['Daily snapshot, not complete history'], 'documents': [
        {'document_id': 'event-1', 'ticker': '2330.TW', 'title': '董事會公告',
         'source_type': 'official_disclosure', 'document_kind': 'announcement',
         'text': '董事會通過資本支出。' * 1000, 'summary': '董事會通過資本支出。',
         'url': 'https://openapi.twse.com.tw/v1/opendata/t187ap04_L',
         'published_at': '2026-01-02', 'coverage_status': 'text_available'}]}


class DocumentsProvider(DataProvider):
    source = 'official_disclosures'
    name = 'TWSE/TPEx official disclosures'
    calls = 0

    def fetch(self, request, context=None):
        self.calls += 1
        return ProviderResult(self.source, self.name, 'degraded_enrichment', source_value(),
            {'source': self.source, 'provider': self.name, 'status': 'degraded_enrichment',
             'record_count': 1, 'fetched_at_epoch': time.time(), 'coverage_status': 'partial'})


def test_cached_core_gets_documents_without_refetching_quote_or_news(monkeypatch):
    import data_fetch.workflow as workflow
    provider = DocumentsProvider()
    registry = ProviderRegistry([provider])
    cached = {'ticker': '2330.TW', '_cache_hit': True, 'current_price': 100,
              'recent_catalysts': [], 'source_audit': []}
    monkeypatch.setattr(workflow, 'schema_compatible_cached_payload', lambda *_: cached)
    monkeypatch.setattr(workflow, 'fresh_cached_payload', lambda *_: dict(cached))
    monkeypatch.setattr(workflow, 'cache_financial_payload', lambda *_: None)
    result = asyncio.run(workflow.fetch_payload_async(FetchRequest.from_ticker('2330.TW'), registry))
    assert provider.calls == 1
    assert result['official_disclosures']['documents'][0]['document_id'] == 'event-1'
    assert result['recent_catalysts'] == []
    assert result['current_price'] == 100
    assert result['source_freshness']['official_disclosures']['fetched_at_epoch'] > 0
    assert {row['source'] for row in result['source_audit']} == {'official_disclosures'}


def test_skip_optional_on_cached_core_never_fetches_documents(monkeypatch):
    import data_fetch.workflow as workflow
    provider = DocumentsProvider()
    cached = {'ticker': '2330.TW', '_cache_hit': True}
    monkeypatch.setattr(workflow, 'schema_compatible_cached_payload', lambda *_: cached)
    monkeypatch.setattr(workflow, 'fresh_cached_payload', lambda *_: dict(cached))
    result = asyncio.run(workflow.fetch_payload_async(FetchRequest.from_ticker('2330.TW', skip_optional_http=True), ProviderRegistry([provider])))
    assert provider.calls == 0
    assert 'official_disclosures' not in result


def test_sources_are_separate_counted_and_role_scoped():
    from data_trust import source_record_count
    from source_applicability import source_is_applicable
    from agent_runtime.prompting import data_for_agent_prompt
    from prompt_builder_helpers import _agent_context
    data = {'ticker': '2330.TW', 'official_disclosures': source_value(), 'recent_catalysts': []}
    assert source_record_count('official_disclosures', data) == 1
    assert source_record_count('official_disclosures', {'official_disclosures': {'status': 'partial', 'documents': []}}) == 0
    assert source_record_count('recent_catalysts', data) == 0
    assert not source_is_applicable('official_disclosures', {'ticker': 'AAPL'})
    assert not source_is_applicable('official_disclosures', {'ticker': '0050.TW', 'quote_type': 'ETF'})
    assert 'official_disclosures' not in _agent_context(data_for_agent_prompt(20, data))
    assert 'official_disclosures' not in _agent_context(data_for_agent_prompt(11, data))
    context = _agent_context(data_for_agent_prompt(13, data))['official_disclosures']
    assert len(context['documents'][0]['text']) <= 1000
    assert context['documents'][0]['content_truncated'] is True
    assert len(data['official_disclosures']['documents'][0]['text']) > 1000


def test_valid_empty_snapshot_has_fresh_acquisition_without_implying_complete_coverage():
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_freshness import source_is_stale
    now = time.time()
    value = {'documents': [], 'status': 'partial', 'retrieval_status': 'valid_empty',
             'fetched_at_epoch': now, 'actual_provider': 'TWSE official disclosures'}
    data = {'ticker': '2330.TW', 'source_audit': [{'source': 'official_disclosures',
        'provider': 'TWSE official disclosures', 'status': 'degraded_enrichment',
        'record_count': 0, 'fetched_at_epoch': now}]}
    result = _merge_optional_http_bundle(data, {'official_disclosures': value},
        refreshed_sources=['official_disclosures'], source_errors={})
    latest = result['source_audit'][-1]
    assert latest['status'] == 'degraded_enrichment'
    assert latest['stale'] is False
    assert not latest.get('error_kind')
    assert not source_is_stale(result, 'official_disclosures', now_epoch=now + 10)
    assert source_is_stale(result, 'official_disclosures', now_epoch=now + 301)
    assert result['official_disclosures']['status'] == 'partial'


def test_skipped_document_collection_does_not_invent_acquisition_time():
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    value = {'documents': [], 'status': 'partial', 'retrieval_status': 'skipped',
             'fetched_at_epoch': None}
    data = {'ticker': '2330.TW', 'source_audit': []}
    result = _merge_optional_http_bundle(data, {'official_disclosures': value},
        refreshed_sources=['official_disclosures'], source_errors={})
    assert result['source_audit'][-1].get('fetched_at') is None
    assert result.get('source_freshness', {}).get('official_disclosures', {}).get('fetched_at_epoch') is None


def test_document_search_endpoint_is_read_only_bounded_and_rejects_bad_filters(tmp_path, monkeypatch):
    import source_document_index as index
    from api_routes.observability import ObservabilityRouteDeps, create_observability_router
    db = tmp_path / 'operational.sqlite3'
    monkeypatch.setattr(index, '_database_path', lambda: db)
    app = FastAPI()
    app.include_router(create_observability_router(ObservabilityRouteDeps(lambda *_: [], lambda *_: [], lambda: None)))
    with TestClient(app) as client:
        response = client.get('/api/observability/source-documents', params={'ticker': '2330.TW'})
        assert response.status_code == 200
        assert response.json()['documents'] == []
        assert not db.exists()
        for params in ({'ticker': '2330.TW', 'limit': 101}, {'ticker': 'AAPL'},
                       {'ticker': '2330.TW', 'since': 'bad'}, {'ticker': '2330.TW', 'kind': 'news'}):
            assert client.get('/api/observability/source-documents', params=params).status_code == 422


def test_unverified_ir_is_visible_in_capabilities_but_never_scheduled():
    from data_fetch.optional_provider_plan import collect_optional_providers
    registry = ProviderRegistry()
    request = FetchRequest.from_ticker('2330.TW')
    ir = registry.first_provider(request, 'company_ir')
    assert ir.capability()['execute_in_workflow'] is False
    assert ir.capability()['live_verification'] == 'blocked_access_denied'
    providers, _ = collect_optional_providers(request, registry, {'ticker': '2330.TW'}, '2330.TW')
    assert all(provider.source != 'company_ir' for provider in providers)
    assert any(provider.source == 'official_disclosures' for provider in providers)


def test_snapshot_retains_acquired_text_while_model_input_has_bounded_exact_excerpt():
    import json
    from data_trust import build_data_snapshot, verify_data_snapshot_integrity
    from prompt_builder import format_data_for_prompt
    from agent_runtime.prompting import data_for_agent_prompt
    data = {'ticker': '2330.TW', 'official_disclosures': source_value()}
    snapshot = build_data_snapshot({'ticker': '2330.TW', 'data': data}, pipeline_id='v2')
    assert verify_data_snapshot_integrity(snapshot)['valid']
    stored = snapshot['data']['official_disclosures']['documents'][0]['text']
    assert stored == data['official_disclosures']['documents'][0]['text']
    for compact in (False, True):
        prompt = format_data_for_prompt(data_for_agent_prompt(13, data), compact=compact)
        encoded = prompt.split('【財務資料 JSON】\n', 1)[1].split('\n\n【使用規則】', 1)[0]
        excerpt = json.loads(encoded)['agent_context']['official_disclosures']['documents'][0]['text']
        assert excerpt == stored[:1000]
