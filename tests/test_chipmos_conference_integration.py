"""The exact translated original crosses provider/report/prompt boundaries honestly."""
from copy import deepcopy
import asyncio
import json
import pytest
from test_chipmos_conference import harness, valid_data


def test_chipmos_transcript_role_keeps_translation_limits_and_bounded_text():
    from conference_presentation_prompt import presentation_prompt_context
    context = {'coverage_notes': ['Official transcript may contain material errors or omissions.'],
               'documents': [{'source': 'ChipMOS official translated conference transcript',
                   'projection_policy': 'chipmos-translated-transcript-role-v1',
                   'document_kind': 'transcript', 'ticker': '8150.TW', 'page_count': 8,
                   'event_date': '2026-08-11', 'content_period': '2026Q2',
                   'published_at': None, 'language': 'en', 'translated_from_language': 'zh',
                   'translation_accuracy_verified': False,
                   'transcript_accuracy_independently_verified': False,
                   'xref_validation_evidence': {'internal_original_path': '/private/cache/a.pdf'},
                   'pages': [{'page_number': n, 'text': 'revenue customer outlook future risk ' * 100}
                             for n in range(1, 9)]}]}
    before = deepcopy(context)
    for role in (3, 5, 12):
        projected = presentation_prompt_context(context, role)
        assert projected.get('transcript_available') is True
        doc = projected['documents'][0]
        assert doc['published_at'] is None and doc['translation_accuracy_verified'] is False
        assert doc['transcript_accuracy_independently_verified'] is False
        assert doc['content_period'] == '2026Q2'
        assert 'xref_validation_evidence' not in doc
        assert sum(len(p['text'].split()) for p in doc['pages']) <= 200
        assert '翻譯' in projected['evidence_policy'] and '未驗證' in projected['evidence_policy']
        assert projected['coverage_notes'] == context['coverage_notes']
    assert presentation_prompt_context(context, 1) == {}
    assert context == before


def test_chipmos_internal_receipt_is_removed_recursively_without_mutation():
    from prompt_evidence import prompt_evidence_copy
    value = {'data': {'chipmos_conference_receipt': {'internal_path': '/private/raw'},
                     'documents': [{'text': 'revenue', 'xref_validation_evidence': {'object_offsets': [1]}}]}}
    before = deepcopy(value)
    clean = prompt_evidence_copy(value)
    assert clean == {'data': {'documents': [{'text': 'revenue'}]}}
    assert value == before


@pytest.mark.parametrize('data', [False, [], 'bad', {'ticker': '8150.TW', 'company_name': '南茂', 'quote_type': 'ETF'}])
def test_chipmos_provider_rejects_invalid_original_before_external_fetch(monkeypatch, data):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest
    def forbidden(*a, **kw):
        pytest.fail('invalid original context reached acquisition')
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', forbidden)
    result = enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('8150.TW'), {'data': data})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block'
    assert result.audit['record_count'] == result.audit['http_request_count'] == 0
    assert result.audit['http_request_sent'] is False


@pytest.mark.parametrize('tamper', [False, True])
def test_chipmos_public_source_only_preserves_existing_analysis(harness, tmp_path, monkeypatch, tamper):
    from fastapi import HTTPException
    from data_fetch import enrichment_providers
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from report_analysis_evidence import capture_analysis_evidence
    from storage.report_storage import InMemoryStorage
    from test_report_refresh_acquisition_audit import init_db, events
    from test_unitech_tcfhc_source_integration import saved_target, assert_preserved
    init_db(); storage = InMemoryStorage()
    filename, keys, before = saved_target(storage, '8150.TW', '南茂')
    before['data'].update(valid_data())
    before['analysis_evidence'] = capture_analysis_evidence({'data': before['data']}, generated_at=before['generated_at'])
    storage.save_report(keys.data_key, json.dumps(before).encode(), content_type='application/json')
    original = storage.get_report(keys.data_key).content
    if tamper:
        real = enrichment_providers.fetch_free_earnings_call_context
        def acquire(*a, **kw):
            value = real(*a, **kw)
            value['documents'][0]['translation_accuracy_verified'] = True
            return value
        monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', acquire)
    provider = enrichment_providers.EarningsCallProvider()
    provider_fetch = provider.fetch
    def with_context(request, context=None):
        assert context['data'] == before['data']
        return provider_fetch(request, context)
    monkeypatch.setattr(provider, 'fetch', with_context)
    service = StockDataService(registry=ProviderRegistry([provider]))
    call = refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
        refresh_service=service, source='earnings_call', return_refreshed_data=True)
    if tamper:
        with pytest.raises(HTTPException) as caught:
            asyncio.run(call)
        assert caught.value.status_code == 502
        assert storage.get_report(keys.data_key).content == original
    else:
        result = asyncio.run(call)
        after = json.loads(storage.get_report(keys.data_key).content)
        doc = after['data']['earnings_call']['documents'][0]
        assert doc['page_count'] == len(doc['pages']) == 8
        assert doc['translation_accuracy_verified'] is False
        assert after['data']['recent_catalysts'] == before['data']['recent_catalysts']
        assert result['analysis_text_stale'] is True
        assert_preserved(storage, keys, before, after)
    observed = events()
    assert len(observed) == 1 and observed[0]['source'] == 'earnings_call'
    assert len(harness[1]) == 3


def test_chipmos_public_cold_and_warm_body_status(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from data_fetch.market_sources.chipmos_conference import PROVIDER
    request = FetchRequest.from_ticker('8150.TW')
    cold = EarningsCallProvider().fetch(request, {'data': valid_data()})
    warm = EarningsCallProvider().fetch(request, {'data': valid_data()})
    assert cold.provider == warm.provider == PROVIDER
    assert cold.audit['status'] == 'success' and cold.audit['record_count'] == 1
    assert cold.audit['http_request_count'] == 3 and cold.audit['http_request_sent'] is True
    assert warm.audit['status'] == 'skipped_fresh_cache' and warm.audit['cache_hit'] is True
    assert warm.audit['http_request_count'] == 0 and warm.audit['http_request_sent'] is False
    assert cold.value['documents'] == warm.value['documents'] and len(harness[1]) == 3
    for key in ('identity', 'index', 'pdf'):
        assert cold.value['chipmos_conference_receipt'][key]['retrieved_at'] == warm.value['chipmos_conference_receipt'][key]['retrieved_at']


def test_chipmos_failed_body_provenance_survives_index_fallback_error(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import chipmos_conference as source
    from search_provider_runtime import SourceResponseError
    def body(*a, **kw):
        error = SourceResponseError('invalid_response')
        error.diagnostic.update(http_request_count=2, http_request_sent=True, specific_original='bad PDF')
        raise error
    def index(*a, **kw):
        raise SourceResponseError('unavailable')
    monkeypatch.setattr(source, 'fetch_chipmos_context', body)
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', index)
    with pytest.raises(SourceResponseError) as caught:
        fetcher.fetch_free_earnings_call_context('8150.TW')
    original = caught.value.diagnostic['component_statuses']['ChipMOS_transcript']
    assert original['specific_original'] == 'bad PDF' and original['http_request_count'] == 2
