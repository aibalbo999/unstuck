"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
import asyncio
import pytest

def test_sti_role_view_keeps_period_and_subsidiary_limits():
    from conference_presentation_prompt import presentation_prompt_context
    context = {'coverage_status': 'partial', 'coverage_notes': ['財務數字未經會計師查核，圖形不完整。'], 'documents': [{'source': 'STI official conference presentation', 'document_kind': 'presentation', 'ticker': '2480.TW', 'page_count': 44, 'event_date': '2026-08-05', 'content_periods': ['2026Q2', '2026H1'], 'published_at': None, 'language': 'zh-TW', 'event_time': None, 'subsidiary_scope_caution': '敦陽資訊不可混為敦陽科技母公司', 'financial_scope_caution': 'H1 EPS is in TWD, other table values in TWD thousands; distinct balance-sheet dates', 'forward_looking_caution': 'Remaining performance obligations are future delivery, not recognized revenue', 'q_and_a_transcript_available': False, 'known_native_text_omissions': [{'page_number': 18, 'issue': 'chart_image'}], 'pages': [{'page_number': n, 'text': '營收 市場 產品 展望 風險 ' * 100} for n in range(1, 45)]}]}
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

def test_sti_receipt_never_enters_role_prompt():
    from prompt_evidence import prompt_evidence_copy
    value = {'data': {'sti_conference_receipt': {'internal_path': '/private/raw'}, 'sti_glyph_evidence': {'internal_digest': 'test'}, 'documents': [{'text': '營收'}]}}
    before = deepcopy(value)
    assert prompt_evidence_copy(value) == {'data': {'documents': [{'text': '營收'}]}}
    assert value == before

@pytest.mark.parametrize('data', [False, [], 'bad', {'ticker': '2480.TW', 'company_name': '敦陽科', 'quote_type': 'ETF'}])
def test_sti_provider_rejects_bad_original_before_acquisition(monkeypatch, data):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest

    def forbidden(*a, **kw):
        pytest.fail('invalid original reached external acquisition')
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', forbidden)
    result = enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('2480.TW'), {'data': data})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block'
    assert result.audit['record_count'] == result.audit['http_request_count'] == 0
    assert result.audit['http_request_sent'] is False

def test_sti_source_service_preserves_original_context():
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
    context = {'data': {'ticker': '2480.TW', 'company_name': '敦陽科'}, 'original_ticker': '2480.TW'}
    asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('2480.TW'), 'earnings_call', context=context))
    assert seen == [context]

def test_sti_failed_body_provenance_survives_index_fallback_error(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import sti_conference as source
    from search_provider_runtime import SourceResponseError

    def body(*a, **kw):
        error = SourceResponseError('invalid_response')
        error.diagnostic.update(http_request_count=2, http_request_sent=True, specific_original='bad PDF')
        raise error

    def index(*a, **kw):
        raise SourceResponseError('unavailable')
    monkeypatch.setattr(source, 'fetch_sti_context', body)
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', index)
    with pytest.raises(SourceResponseError) as caught:
        fetcher.fetch_free_earnings_call_context('2480.TW')
    original = caught.value.diagnostic['component_statuses']['STI_presentation']
    assert original['specific_original'] == 'bad PDF' and original['http_request_count'] == 2
