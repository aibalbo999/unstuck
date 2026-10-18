"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
import asyncio
import pytest

def test_sigurd_role_view_keeps_period_and_subsidiary_limits():
    from conference_presentation_prompt import presentation_prompt_context
    context = {'coverage_status': 'partial', 'coverage_notes': ['財務數字未經會計師查核，圖形不完整。'], 'documents': [{'source': 'Sigurd official conference presentation', 'document_kind': 'presentation', 'ticker': '6257.TW', 'page_count': 23, 'event_date': '2026-10-06', 'content_periods': ['2026Q2', '2026Jan-Sep'], 'published_at': None, 'language': 'en', 'event_time': '14:30', 'event_time_Taipei': '14:30', 'subsidiary_scope_caution': '新唐不可混為華邦母公司', 'financial_scope_caution': 'Quarterly and Jan-Sep figures have different periods', 'q_and_a_transcript_available': False, 'known_native_text_omissions': [{'page_number': 18, 'issue': 'chart_image'}], 'pages': [{'page_number': n, 'text': '營收 市場 產品 展望 風險 ' * 100} for n in range(1, 24)]}]}
    before = deepcopy(context)
    for role in (3, 5, 12):
        projected = presentation_prompt_context(context, role)
        assert projected['transcript_available'] is False
        doc = projected['documents'][0]
        for field in ('content_periods', 'language', 'event_time', 'event_time_Taipei', 'subsidiary_scope_caution', 'financial_scope_caution', 'q_and_a_transcript_available', 'known_native_text_omissions'):
            assert doc[field] == context['documents'][0][field]
        assert sum((len(p['text']) for p in doc['pages'])) <= 6000
        assert projected['coverage_notes'] == context['coverage_notes']
        assert projected['coverage_status'] == 'partial'
    assert presentation_prompt_context(context, 1) == {}
    assert context == before

def test_sigurd_receipt_never_enters_role_prompt():
    from prompt_evidence import prompt_evidence_copy
    value = {'data': {'sigurd_conference_receipt': {'internal_path': '/private/raw'}, 'sigurd_glyph_evidence': {'internal_digest': 'test'}, 'documents': [{'text': '營收'}]}}
    before = deepcopy(value)
    assert prompt_evidence_copy(value) == {'data': {'documents': [{'text': '營收'}]}}
    assert value == before

@pytest.mark.parametrize('data', [False, [], 'bad', {'ticker': '6257.TW', 'company_name': '矽格', 'quote_type': 'ETF'}])
def test_sigurd_provider_rejects_bad_original_before_acquisition(monkeypatch, data):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest

    def forbidden(*a, **kw):
        pytest.fail('invalid original reached external acquisition')
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', forbidden)
    result = enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('6257.TW'), {'data': data})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block'
    assert result.audit['record_count'] == result.audit['http_request_count'] == 0
    assert result.audit['http_request_sent'] is False

def test_sigurd_source_service_preserves_original_context():
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
    context = {'data': {'ticker': '6257.TW', 'company_name': '矽格'}, 'original_ticker': '6257.TW'}
    asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('6257.TW'), 'earnings_call', context=context))
    assert seen == [context]

def test_sigurd_english_role_selection_preserves_relevant_late_page():
    from conference_presentation_prompt import presentation_prompt_context
    context = {'documents': [{'source': 'Sigurd official conference presentation', 'document_kind': 'presentation', 'page_count': 23, 'pages': [{'page_number': n, 'text': ('outlook strategy future risk ' if n == 23 else 'Company introduction ') * 70} for n in range(1, 24)]}]}
    result = presentation_prompt_context(context, 12)
    assert 23 in [page['page_number'] for page in result['documents'][0]['pages']]
    assert context['documents'][0]['pages'][22]['text'].startswith('outlook')

def test_sigurd_failed_body_provenance_survives_index_fallback_error(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import sigurd_conference as source
    from search_provider_runtime import SourceResponseError

    def body(*a, **kw):
        error = SourceResponseError('invalid_response')
        error.diagnostic.update(http_request_count=2, http_request_sent=True, specific_original='bad PDF')
        raise error

    def index(*a, **kw):
        raise SourceResponseError('unavailable')
    monkeypatch.setattr(source, 'fetch_sigurd_context', body)
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', index)
    with pytest.raises(SourceResponseError) as caught:
        fetcher.fetch_free_earnings_call_context('6257.TW')
    original = caught.value.diagnostic['component_statuses']['Sigurd_presentation']
    assert original['specific_original'] == 'bad PDF' and original['http_request_count'] == 2
