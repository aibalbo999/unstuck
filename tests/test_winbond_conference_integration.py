"""Prepared slides stay source evidence across provider, refresh and prompts."""
from copy import deepcopy
import asyncio
import json
import pytest
from test_winbond_conference import harness, valid_data


def test_winbond_role_view_keeps_period_and_subsidiary_limits():
    from conference_presentation_prompt import presentation_prompt_context
    context = {'coverage_status': 'partial', 'coverage_notes': ['財務數字未經會計師查核，圖形不完整。'],
               'documents': [{'source': 'Winbond official conference presentation',
                   'document_kind': 'presentation', 'ticker': '2344.TW', 'page_count': 31,
                   'event_date': '2026-08-06', 'content_period': '2026Q2',
                   'published_at': None, 'language': 'zh-TW',
                   'subsidiary_scope_caution': '新唐不可混為華邦母公司',
                   'unaudited_financial_caution': True,
                   'q_and_a_transcript_available': False,
                   'known_native_text_omissions': [{'page_number': 18, 'issue': 'chart_image'}],
                   'pages': [{'page_number': n, 'text': '營收 市場 產品 展望 風險 ' * 100}
                             for n in range(1, 32)]}]}
    before = deepcopy(context)
    for role in (3, 5, 12):
        projected = presentation_prompt_context(context, role)
        assert projected['transcript_available'] is False
        doc = projected['documents'][0]
        for field in ('content_period', 'language', 'subsidiary_scope_caution',
                      'unaudited_financial_caution', 'q_and_a_transcript_available',
                      'known_native_text_omissions'):
            assert doc[field] == context['documents'][0][field]
        assert sum(len(p['text']) for p in doc['pages']) <= 6000
        assert projected['coverage_notes'] == context['coverage_notes']
        assert projected['coverage_status'] == 'partial'
    assert presentation_prompt_context(context, 1) == {}
    assert context == before


def test_winbond_receipt_never_enters_role_prompt():
    from prompt_evidence import prompt_evidence_copy
    value = {'data': {'winbond_conference_receipt': {'internal_path': '/private/raw'},
                     'documents': [{'text': '營收'}]}}
    before = deepcopy(value)
    assert prompt_evidence_copy(value) == {'data': {'documents': [{'text': '營收'}]}}
    assert value == before


@pytest.mark.parametrize('data', [False, [], 'bad', {'ticker': '2344.TW', 'company_name': '華邦電', 'quote_type': 'ETF'}])
def test_winbond_provider_rejects_bad_original_before_acquisition(monkeypatch, data):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest
    def forbidden(*a, **kw):
        pytest.fail('invalid original reached external acquisition')
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', forbidden)
    result = enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('2344.TW'), {'data': data})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block'
    assert result.audit['record_count'] == result.audit['http_request_count'] == 0
    assert result.audit['http_request_sent'] is False


def test_winbond_source_service_preserves_original_context():
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest, ProviderResult
    seen = []
    class Provider(EarningsCallProvider):
        def fetch(self, request, context=None):
            seen.append(context)
            return ProviderResult(self.source, self.name, 'unavailable', value={})
    service = StockDataService(registry=ProviderRegistry([Provider()]))
    context = {'data': {'ticker': '2344.TW', 'company_name': '華邦電'}, 'original_ticker': '2344.TW'}
    asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('2344.TW'), 'earnings_call', context=context))
    assert seen == [context]


@pytest.mark.parametrize('tamper', [False, True])
def test_winbond_public_source_only_preserves_existing_analysis(harness, tmp_path, monkeypatch, tamper):
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
    filename, keys, before = saved_target(storage, '2344.TW', '華邦電')
    before['data'].update(valid_data())
    before['analysis_evidence'] = capture_analysis_evidence({'data': before['data']}, generated_at=before['generated_at'])
    storage.save_report(keys.data_key, json.dumps(before).encode(), content_type='application/json')
    original = storage.get_report(keys.data_key).content
    if tamper:
        real = enrichment_providers.fetch_free_earnings_call_context
        def acquire(*a, **kw):
            value = real(*a, **kw)
            value['documents'][0]['q_and_a_transcript_available'] = True
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
        assert doc['page_count'] == len(doc['pages']) == 31
        assert doc['q_and_a_transcript_available'] is False
        assert after['data']['recent_catalysts'] == before['data']['recent_catalysts']
        assert result['analysis_text_stale'] is True
        assert_preserved(storage, keys, before, after)
    observed = events()
    assert len(observed) == 1 and observed[0]['source'] == 'earnings_call'
    assert len(harness[1]) == 3


def test_winbond_public_cold_and_warm_body_status(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from data_fetch.market_sources.winbond_conference import PROVIDER
    request = FetchRequest.from_ticker('2344.TW')
    cold = EarningsCallProvider().fetch(request, {'data': valid_data()})
    warm = EarningsCallProvider().fetch(request, {'data': valid_data()})
    assert cold.provider == warm.provider == PROVIDER
    assert cold.audit['status'] == 'success' and cold.audit['record_count'] == 1
    assert cold.audit['http_request_count'] == 3 and cold.audit['http_request_sent'] is True
    assert warm.audit['status'] == 'skipped_fresh_cache' and warm.audit['cache_hit'] is True
    assert warm.audit['http_request_count'] == 0 and warm.audit['http_request_sent'] is False
    assert cold.value['documents'] == warm.value['documents'] and len(harness[1]) == 3
    for key in ('identity', 'index', 'pdf'):
        assert cold.value['winbond_conference_receipt'][key]['retrieved_at'] == warm.value['winbond_conference_receipt'][key]['retrieved_at']


def test_winbond_failed_body_provenance_survives_index_fallback_error(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import winbond_conference as source
    from search_provider_runtime import SourceResponseError
    def body(*a, **kw):
        error = SourceResponseError('invalid_response')
        error.diagnostic.update(http_request_count=2, http_request_sent=True, specific_original='bad PDF')
        raise error
    def index(*a, **kw):
        raise SourceResponseError('unavailable')
    monkeypatch.setattr(source, 'fetch_winbond_context', body)
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', index)
    with pytest.raises(SourceResponseError) as caught:
        fetcher.fetch_free_earnings_call_context('2344.TW')
    original = caught.value.diagnostic['component_statuses']['Winbond_presentation']
    assert original['specific_original'] == 'bad PDF' and original['http_request_count'] == 2
