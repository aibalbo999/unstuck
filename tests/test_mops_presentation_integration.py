"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
import sys
from types import SimpleNamespace
import pytest

@pytest.mark.parametrize('ticker', ['2330.TW'])
def test_public_free_path_uses_qualified_published_body(monkeypatch, ticker):
    from data_fetch import earnings_call_fetcher as fetcher
    value = {'ticker': ticker, 'documents': [{'document_kind': 'presentation'}]}
    seen = []

    def fetch(ticker, **options):
        seen.append((ticker, options))
        return value
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.mops_presentation', SimpleNamespace(supports=lambda s: s in {'2330.TW', '1229.TW'}, fetch_presentation_context=fetch))
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', lambda *a, **kw: {'materials': []})
    actual = fetcher.fetch_free_earnings_call_context(ticker, force_refresh=True, use_cache=False)
    assert actual == value, 'published full original must reach the normal free provider'
    assert len(seen) == 1 and seen[0][1]['force_refresh'] and (not seen[0][1]['use_cache'])

def test_shared_presentation_role_preserves_format_and_missing_hidden_limits():
    from conference_presentation_prompt import presentation_prompt_context
    doc = {'source': 'MOPS published presentation', 'document_kind': 'presentation', 'ticker': '1229.TW', 'language': 'en', 'file_format': 'pptx', 'page_count': 30, 'total_slide_count': 32, 'hidden_pages': [31, 32], 'event_date': '2026-09-30', 'material_file_date': '2026-09-30', 'content_period': '2026Q2', 'missing_text_pages': [2, 3, 21, 29], 'coverage_status': 'partial', 'native_text_coverage': 'partial', 'forward_looking_caution': 'Forecasts are not realized facts.', 'financial_scope_caution': 'Parent, subsidiary, quarter and year-to-date scopes differ.', 'known_native_text_omissions': [{'page_number': 2, 'issue': 'image_only_disclaimer'}], 'q_and_a_transcript_available': False, 'period_scope_caution': 'H1 is cumulative half-year, not standalone Q2.', 'embedded_object_count': 4, 'external_relationship_count': 0, 'financial_statement_complete': False, 'pages': [{'page_number': 4, 'text': 'Revenue cash operating outlook'}]}
    context = {'documents': [doc], 'coverage_status': 'partial', 'coverage_notes': ['Image omissions remain.']}
    before = deepcopy(context)
    for role in (3, 5, 12):
        result = presentation_prompt_context(context, role)['documents'][0]
        for key in ('file_format', 'hidden_pages', 'total_slide_count', 'material_file_date', 'content_period', 'financial_scope_caution', 'forward_looking_caution', 'known_native_text_omissions', 'q_and_a_transcript_available', 'period_scope_caution', 'embedded_object_count', 'external_relationship_count', 'financial_statement_complete'):
            assert result.get(key) == doc[key]
    assert context == before

def test_internal_post_receipt_is_not_in_role_prompt():
    from prompt_evidence import prompt_evidence_copy
    assert prompt_evidence_copy({'mops_material_receipt': {'request_body': 'private-proof'}, 'title': 'public'}) == {'title': 'public'}

@pytest.mark.parametrize('cached', [False, True])
def test_acquisition_audit_counts_one_body_and_no_new_warm_success(cached):
    from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
    result = {'value': {'documents': [{}]}, 'audit': {'status': 'success', 'record_count': 3}}
    diagnostic = {'mops_material_workflow': True, 'mops_material_originals_verified': True, 'cache_hit': cached, 'http_request_sent': True, 'http_request_count': 2, 'actual_provider': 'MOPS published presentation', 'coverage_status': 'native_presentation_text_partial'}
    apply_earnings_call_audit(result, diagnostic)
    assert result['audit']['record_count'] == 1
    if cached:
        assert result['audit']['status'] == 'skipped_fresh_cache'
from test_mops_presentation import valid_data

@pytest.mark.parametrize('data', [False, [], 'bad', {'ticker': '2330.TW', 'company_name': '聯華', 'quoteType': 'EQUITY'}, {'ticker': '1229.TW', 'company_name': '聯華', 'quoteType': 'ETF'}])
def test_provider_invalid_context_stops_before_any_HTTP(monkeypatch, data):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', lambda *a, **kw: pytest.fail('invalid original reached acquisition'))
    result = enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('1229.TW'), {'data': data})
    assert result.status == 'unavailable' and result.audit['http_request_count'] == 0 and (not result.audit['http_request_sent'])

@pytest.mark.parametrize('ticker', ['2330.TW', '1229.TW', '2838.TW', '2845.TW', '3703.TW', '2023.TW', '1104.TW', '3531.TWO', '1102.TW', '1216.TW', '1301.TW', '2353.TW', '2382.TW'])
def test_source_service_passes_original_identity(ticker):
    import asyncio
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest, ProviderResult
    seen = []

    class Provider(EarningsCallProvider):

        def fetch(self, request, context=None):
            seen.append(context)
            return ProviderResult(self.source, self.name, 'unavailable', value={})
    context = {'data': valid_data(ticker), 'original_ticker': ticker}
    asyncio.run(StockDataService(registry=ProviderRegistry([Provider()])).fetch_source_async(FetchRequest.from_ticker(ticker), 'earnings_call', context=context))
    assert seen == [context]

@pytest.mark.parametrize('ticker', ['2838.TW', '2845.TW', '3703.TW', '2023.TW', '1104.TW', '3531.TWO', '1102.TW', '1216.TW', '1301.TW', '2353.TW', '2382.TW'])
def test_expanded_profiles_reject_wrong_report_identity_before_fetch(ticker):
    import asyncio
    from fastapi import HTTPException
    from report_source_refresh import fetch_report_source_data

    class Service:
        _fetcher = None

        async def fetch_source_async(self, *args, **kwargs):
            pytest.fail('conflicting report identity reached provider')
    data = valid_data(ticker)
    data['company_identity']['official_ubn'] = '11111111'
    snapshot = {'ticker': ticker, 'data': data, 'source_audit': [{'source': 'earnings_call', 'status': 'unavailable'}]}
    with pytest.raises(HTTPException) as exc:
        asyncio.run(fetch_report_source_data(snapshot, 'earnings_call', Service()))
    assert exc.value.status_code == 400

@pytest.mark.parametrize('ticker', ['2838.TW', '2845.TW', '3703.TW', '2023.TW', '1104.TW', '3531.TWO', '1102.TW', '1216.TW', '1301.TW', '2353.TW', '2382.TW'])
def test_report_source_route_preserves_expanded_profile_identity(ticker):
    import asyncio
    from fastapi import HTTPException
    from report_source_refresh import fetch_report_source_data
    seen = []

    class Service:
        _fetcher = None

        async def fetch_source_async(self, request, source, *, context=None):
            seen.append(context)
            return SimpleNamespace(data={'ticker': ticker, 'earnings_call': {}}, source_audit=[])
    data = valid_data(ticker)
    snapshot = {'ticker': ticker, 'data': data, 'source_audit': [{'source': 'earnings_call', 'status': 'unavailable'}]}
    with pytest.raises(HTTPException):
        asyncio.run(fetch_report_source_data(snapshot, 'earnings_call', Service()))
    assert seen == [{'data': data}]

def test_transport_failure_is_reported_before_attempting_material_replay(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from report_source_refresh import fetch_report_source_data
    from data_fetch.market_sources import mops_presentation as source
    monkeypatch.setattr(source, 'verify_context', lambda *a, **k: pytest.fail('failed acquisition has no original to replay'))

    class Service:
        _fetcher = None

        async def fetch_source_async(self, *args, **kwargs):
            return SimpleNamespace(data={'ticker': '2023.TW', 'earnings_call': {}}, source_audit=[{'source': 'earnings_call', 'provider': source.PROVIDER, 'status': 'error', 'error_kind': 'timeout', 'record_count': 0, 'http_request_sent': True}])
    snapshot = {'ticker': '2023.TW', 'data': valid_data('2023.TW'), 'source_audit': [{'source': 'earnings_call', 'status': 'unavailable'}]}
    with pytest.raises(HTTPException) as exc:
        asyncio.run(fetch_report_source_data(snapshot, 'earnings_call', Service()))
    assert exc.value.status_code == 502 and '逾時' in exc.value.detail
