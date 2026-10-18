"""Public boundary checks. Original private-data replay cases remain local."""
from types import SimpleNamespace
import sys

def test_public_metadata_gap_prefers_verified_hiwin_original(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    expected = {'ticker': '2049.TW', 'source': 'HIWIN official conference presentation', 'documents': [{'page_count': 13, 'native_text_coverage': 'complete'}]}
    calls = []

    def fetch(ticker, **options):
        calls.append((ticker, options))
        return expected
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.hiwin_conference', SimpleNamespace(supports_hiwin=lambda t: t == '2049.TW', fetch_hiwin_context=fetch))
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', lambda *a, **kw: {'source': 'MOPS', 'materials': []})
    assert fetcher.fetch_free_earnings_call_context('2049.TW', force_refresh=True, use_cache=False) == expected
    assert len(calls) == 1 and calls[0][1]['force_refresh'] is True
from copy import deepcopy
import asyncio
import pytest

def test_hiwin_role_view_keeps_period_and_units_limits():
    from conference_presentation_prompt import presentation_prompt_context
    context = {'coverage_status': 'partial', 'coverage_notes': ['財務數字未經會計師查核，圖形不完整。'], 'documents': [{'source': 'HIWIN official conference presentation', 'document_kind': 'presentation', 'ticker': '2049.TW', 'page_count': 13, 'projection_policy': 'hiwin-presentation-role-v1', 'content_sha256': 'ebb6150526e26f75787f30db984ecac363ee95997770c905530491eaf078affb', 'event_date': '2026-05-08', 'content_periods': ['2026Q1', '2025Q1–Q4 comparisons'], 'published_at': None, 'language': 'en', 'event_time': None, 'unit_scope_caution': 'NT$ million, % of sales and NT$ per share differ', 'financial_scope_caution': '2026Q1 versus2025Q1-Q4; NT$ million differs from EPS per share', 'forward_looking_caution': 'Future expectations are not realized results', 'q_and_a_transcript_available': False, 'known_native_text_omissions': [{'page_number': 6, 'issue': 'chart_image'}], 'pages': [{'page_number': n, 'text': '營收 市場 產品 展望 風險 ' * 100} for n in range(1, 45)]}]}
    before = deepcopy(context)
    for role in (3, 5, 12):
        projected = presentation_prompt_context(context, role)
        assert projected['transcript_available'] is False
        doc = projected['documents'][0]
        for field in ('content_periods', 'language', 'event_time', 'unit_scope_caution', 'financial_scope_caution', 'forward_looking_caution', 'q_and_a_transcript_available', 'known_native_text_omissions'):
            assert doc[field] == context['documents'][0][field]
        assert sum((len(p['text']) for p in doc['pages'])) <= 6000
        assert projected['coverage_notes'] == context['coverage_notes']
        assert projected['coverage_status'] == 'partial'
    assert presentation_prompt_context(context, 1) == {}
    assert context == before

@pytest.mark.parametrize('change', ['projection_policy', 'content_sha256'])
def test_hiwin_roles_reject_unknown_revision_or_projection(change):
    from conference_presentation_prompt import presentation_prompt_context
    doc = {'source': 'HIWIN official conference presentation', 'document_kind': 'presentation', 'projection_policy': 'hiwin-presentation-role-v1', 'content_sha256': 'ebb6150526e26f75787f30db984ecac363ee95997770c905530491eaf078affb', 'pages': [{'page_number': 9, 'text': 'Revenue net income earnings per share'}]}
    assert presentation_prompt_context({'documents': [doc]}, 5)['documents']
    doc[change] = 'unknown'
    for role in (3, 5, 12):
        assert not presentation_prompt_context({'documents': [doc]}, role).get('documents')

@pytest.mark.parametrize('kind', ['timeout', 'lease_lost', 'single_flight_busy', 'guard_storage_unavailable'])
def test_hiwin_guard_or_budget_failure_never_starts_metadata_fallback(monkeypatch, kind):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import hiwin_conference as source
    from search_provider_runtime import SourceResponseError

    def fail(*a, **kw):
        raise SourceResponseError(kind)
    monkeypatch.setattr(source, 'fetch_hiwin_context', fail)
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', lambda *a, **kw: pytest.fail('guard failure reached fallback'))
    with pytest.raises(SourceResponseError) as caught:
        fetcher.fetch_free_earnings_call_context('2049.TW')
    assert caught.value.error_kind == kind

def test_hiwin_receipt_never_enters_role_prompt():
    from prompt_evidence import prompt_evidence_copy
    value = {'data': {'hiwin_conference_receipt': {'internal_path': '/private/raw'}, 'hiwin_glyph_evidence': {'internal_digest': 'test'}, 'documents': [{'text': '營收'}]}}
    before = deepcopy(value)
    assert prompt_evidence_copy(value) == {'data': {'documents': [{'text': '營收'}]}}
    assert value == before

@pytest.mark.parametrize('data', [False, [], 'bad', {'ticker': '2049.TW', 'company_name': '上銀', 'quote_type': 'ETF'}])
def test_hiwin_provider_rejects_bad_original_before_acquisition(monkeypatch, data):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest

    def forbidden(*a, **kw):
        pytest.fail('invalid original reached external acquisition')
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', forbidden)
    result = enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('2049.TW'), {'data': data})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block'
    assert result.audit['record_count'] == result.audit['http_request_count'] == 0
    assert result.audit['http_request_sent'] is False

def test_hiwin_source_service_preserves_original_context():
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
    context = {'data': {'ticker': '2049.TW', 'company_name': '上銀'}, 'original_ticker': '2049.TW'}
    asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('2049.TW'), 'earnings_call', context=context))
    assert seen == [context]

def test_hiwin_failed_body_provenance_survives_index_fallback_error(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import hiwin_conference as source
    from search_provider_runtime import SourceResponseError

    def body(*a, **kw):
        error = SourceResponseError('invalid_response')
        error.diagnostic.update(http_request_count=2, http_request_sent=True, specific_original='bad PDF')
        raise error

    def index(*a, **kw):
        raise SourceResponseError('unavailable')
    monkeypatch.setattr(source, 'fetch_hiwin_context', body)
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', index)
    with pytest.raises(SourceResponseError) as caught:
        fetcher.fetch_free_earnings_call_context('2049.TW')
    original = caught.value.diagnostic['component_statuses']['HIWIN_presentation']
    assert original['specific_original'] == 'bad PDF' and original['http_request_count'] == 2

@pytest.mark.parametrize('caller', ['workflow', 'compatibility'])
@pytest.mark.parametrize('marker', [{'hiwin_conference_receipt': None}, {'projection_policy': 'hiwin-presentation-role-v1'}, {'source': 'HIWIN official conference presentation'}, {'hiwin_glyph_evidence': False}, {'url': 'https://www.hiwin.tw/uploadfiles/file/conference/20260508_final_E.pdf'}])
def test_all_aggregate_cache_callers_respect_no_store_without_mutation(monkeypatch, caller, marker):
    from data_fetch import cache_helpers
    from data_fetch.payload_cache import cache_financial_payload
    from financial_data import _cache_financial_data
    writes = []
    monkeypatch.setattr(cache_helpers, 'set_cache_json', lambda *a, **k: writes.append((a, k)))
    data = {'ticker': '2049.TW', 'earnings_call': {'documents': [{'pages': [{'page_number': 1, 'text': 'private original'}], **marker}]}}
    before = deepcopy(data)
    (cache_financial_payload if caller == 'workflow' else _cache_financial_data)(data, '2049.TW')
    assert writes == [] and data == before

@pytest.mark.parametrize('caller', ['workflow', 'compatibility'])
def test_other_issuers_keep_existing_payload_cache(monkeypatch, caller):
    from data_fetch import cache_helpers
    from data_fetch.payload_cache import cache_financial_payload
    from financial_data import _cache_financial_data
    writes = []
    monkeypatch.setattr(cache_helpers, 'set_cache_json', lambda *a, **k: writes.append((a, k)))
    data = {'ticker': '2330.TW', 'company_name': '台積電', 'earnings_call': {'documents': [{'source': 'Other issuer', 'pages': []}]}}
    before = deepcopy(data)
    (cache_financial_payload if caller == 'workflow' else _cache_financial_data)(data, '2330.TW')
    assert len(writes) == 1 and writes[0][0][0] == 'financial_data:2330.TW' and (data == before)
