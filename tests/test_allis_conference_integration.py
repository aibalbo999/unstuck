"""Public boundary checks. Original private-data replay cases remain local."""
from types import SimpleNamespace
import sys

def test_public_metadata_gap_prefers_verified_allis_original(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    expected = {'ticker': '1514.TW', 'source': 'Allis official conference presentation', 'documents': [{'page_count': 29, 'native_text_coverage': 'complete'}]}
    calls = []

    def fetch(ticker, **options):
        calls.append((ticker, options))
        return expected
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.allis_conference', SimpleNamespace(supports_allis=lambda t: t == '1514.TW', fetch_allis_context=fetch))
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', lambda *a, **kw: {'source': 'MOPS', 'materials': []})
    assert fetcher.fetch_free_earnings_call_context('1514.TW', force_refresh=True, use_cache=False) == expected
    assert len(calls) == 1 and calls[0][1]['force_refresh'] is True
from copy import deepcopy
import asyncio
import pytest

def test_allis_role_view_keeps_period_and_subsidiary_limits():
    from conference_presentation_prompt import presentation_prompt_context
    context = {'coverage_status': 'partial', 'coverage_notes': ['財務數字未經會計師查核，圖形不完整。'], 'documents': [{'source': 'Allis official conference presentation', 'document_kind': 'presentation', 'ticker': '1514.TW', 'page_count': 29, 'event_date': '2026-08-27', 'content_periods': ['2026Q2', '2026H1'], 'published_at': None, 'language': 'zh-TW', 'event_time': None, 'subsidiary_scope_caution': '敦陽資訊不可混為亞力技母公司', 'financial_scope_caution': 'H1 EPS is in TWD, other table values in TWD thousands; distinct balance-sheet dates', 'forward_looking_caution': 'Remaining performance obligations are future delivery, not recognized revenue', 'q_and_a_transcript_available': False, 'known_native_text_omissions': [{'page_number': 18, 'issue': 'chart_image'}], 'pages': [{'page_number': n, 'text': '營收 市場 產品 展望 風險 ' * 100} for n in range(1, 45)]}]}
    before = deepcopy(context)
    for role in (3, 5, 12):
        projected = presentation_prompt_context(context, role)
        assert projected['transcript_available'] is False
        doc = projected['documents'][0]
        for field in ('content_periods', 'language', 'event_time', 'subsidiary_scope_caution', 'financial_scope_caution', 'forward_looking_caution', 'q_and_a_transcript_available', 'known_native_text_omissions'):
            assert doc[field] == context['documents'][0][field]
        assert sum((len(p['text']) for p in doc['pages'])) <= 6000
        assert projected['coverage_notes'] == context['coverage_notes']
        assert projected['coverage_status'] == 'partial'
    assert presentation_prompt_context(context, 1) == {}
    assert context == before

def test_allis_receipt_never_enters_role_prompt():
    from prompt_evidence import prompt_evidence_copy
    value = {'data': {'allis_conference_receipt': {'internal_path': '/private/raw'}, 'allis_glyph_evidence': {'internal_digest': 'test'}, 'documents': [{'text': '營收'}]}}
    before = deepcopy(value)
    assert prompt_evidence_copy(value) == {'data': {'documents': [{'text': '營收'}]}}
    assert value == before

@pytest.mark.parametrize('data', [False, [], 'bad', {'ticker': '1514.TW', 'company_name': '亞力', 'quote_type': 'ETF'}])
def test_allis_provider_rejects_bad_original_before_acquisition(monkeypatch, data):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest

    def forbidden(*a, **kw):
        pytest.fail('invalid original reached external acquisition')
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', forbidden)
    result = enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('1514.TW'), {'data': data})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block'
    assert result.audit['record_count'] == result.audit['http_request_count'] == 0
    assert result.audit['http_request_sent'] is False

def test_allis_source_service_preserves_original_context():
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
    context = {'data': {'ticker': '1514.TW', 'company_name': '亞力'}, 'original_ticker': '1514.TW'}
    asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('1514.TW'), 'earnings_call', context=context))
    assert seen == [context]

def test_allis_failed_body_provenance_survives_index_fallback_error(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import allis_conference as source
    from search_provider_runtime import SourceResponseError

    def body(*a, **kw):
        error = SourceResponseError('invalid_response')
        error.diagnostic.update(http_request_count=2, http_request_sent=True, specific_original='bad PDF')
        raise error

    def index(*a, **kw):
        raise SourceResponseError('unavailable')
    monkeypatch.setattr(source, 'fetch_allis_context', body)
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', index)
    with pytest.raises(SourceResponseError) as caught:
        fetcher.fetch_free_earnings_call_context('1514.TW')
    original = caught.value.diagnostic['component_statuses']['Allis_presentation']
    assert original['specific_original'] == 'bad PDF' and original['http_request_count'] == 2

@pytest.mark.parametrize('caller', ['workflow', 'compatibility'])
@pytest.mark.parametrize('marker', [{'allis_conference_receipt': None}, {'projection_policy': 'allis-presentation-role-v1'}, {'source': 'Allis official conference presentation'}, {'allis_glyph_evidence': False}, {'url': 'https://www.allis.com.tw/zh-tw/download/file/42604'}])
def test_all_aggregate_cache_callers_respect_no_store_without_mutation(monkeypatch, caller, marker):
    from data_fetch import cache_helpers
    from data_fetch.payload_cache import cache_financial_payload
    from financial_data import _cache_financial_data
    writes = []
    monkeypatch.setattr(cache_helpers, 'set_cache_json', lambda *a, **k: writes.append((a, k)))
    data = {'ticker': '1514.TW', 'earnings_call': {'documents': [{'pages': [{'page_number': 1, 'text': 'private original'}], **marker}]}}
    before = deepcopy(data)
    (cache_financial_payload if caller == 'workflow' else _cache_financial_data)(data, '1514.TW')
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
