"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
from types import SimpleNamespace
import sys
import pytest
PROVIDER = 'Lien Hwa official conference presentation'
SHA = 'a265012e09c64c1e890600fe3fd4151c819b9bf869f7f78dea88ec58ff73e268'

def test_public_1229_routing_prefers_issuer_without_touching_mops(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import mops_presentation
    expected = {'ticker': '1229.TW', 'source': PROVIDER, 'documents': [{'page_count': 30}]}
    calls = []

    def acquire(ticker, **options):
        calls.append((ticker, options))
        return expected
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.lienhwa_conference', SimpleNamespace(supports_lienhwa=lambda t: t == '1229.TW', fetch_lienhwa_context=acquire))
    monkeypatch.setattr(mops_presentation, 'fetch_presentation_context', lambda *a, **kw: {'source': 'MOPS'})
    assert fetcher.fetch_free_earnings_call_context('1229.TW', force_refresh=True, use_cache=False) == expected
    assert len(calls) == 1 and calls[0][1]['force_refresh'] is True
    assert calls[0][1]['use_cache'] is False

@pytest.mark.parametrize('kind', ['timeout', 'lease_lost', 'single_flight_busy', 'guard_storage_unavailable', 'cooldown'])
def test_lienhwa_failure_never_retries_mops(monkeypatch, kind):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import mops_presentation
    from search_provider_runtime import SourceResponseError

    def fail(*a, **kw):
        raise SourceResponseError(kind)
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.lienhwa_conference', SimpleNamespace(supports_lienhwa=lambda t: t == '1229.TW', fetch_lienhwa_context=fail))
    monkeypatch.setattr(mops_presentation, 'fetch_presentation_context', lambda *a, **kw: {'source': 'MOPS'})
    with pytest.raises(SourceResponseError) as caught:
        fetcher.fetch_free_earnings_call_context('1229.TW')
    assert caught.value.error_kind == kind

def context():
    return {'coverage_status': 'partial', 'coverage_notes': ['圖像未抽取，不是逐字稿'], 'documents': [{'source': PROVIDER, 'document_kind': 'presentation', 'ticker': '1229.TW', 'projection_policy': 'lienhwa-presentation-role-v1', 'content_sha256': SHA, 'page_count': 30, 'native_text_coverage': 'partial', 'text_extraction_complete': False, 'q_and_a_transcript_available': False, 'financial_statement_complete': False, 'full_visual_content_verified': False, 'content_periods': ['2026H1', '2026Q2', 'comparisons and future projections'], 'unit_scope_caution': 'EPS元與淨利佰萬元不可互換', 'period_scope_caution': 'H1不是Q2', 'native_editorial_caution': 'p15有被遮覆文字', 'role_page_allowlist': list(range(1, 31)), 'pages': [{'page_number': n, 'text': '營收 市場 產品 展望 風險 ' * 15} for n in range(1, 31)]}]}

def test_role_allowlist_is_fixed_and_preserves_partial_semantics():
    from conference_presentation_prompt import presentation_prompt_context
    value = context()
    before = deepcopy(value)
    for role in (3, 5, 12):
        projected = presentation_prompt_context(value, role)
        assert projected['transcript_available'] is False
        assert projected['coverage_status'] == 'partial'
        doc = projected['documents'][0]
        assert {p['page_number'] for p in doc['pages']} == {1, 22, 24, 25}
        assert doc['excluded_native_text_pages'] == [15]
        assert doc['role_page_allowlist'] == [1, 22, 24, 25]
        for key in ('q_and_a_transcript_available', 'financial_statement_complete', 'full_visual_content_verified', 'content_periods', 'unit_scope_caution', 'period_scope_caution', 'native_editorial_caution'):
            assert doc[key] == value['documents'][0][key]
    assert value == before

@pytest.mark.parametrize('key', ['projection_policy', 'content_sha256'])
def test_roles_reject_unknown_revision(key):
    from conference_presentation_prompt import presentation_prompt_context
    value = context()
    value['documents'][0][key] = 'unknown'
    assert not presentation_prompt_context(value, 3).get('documents')

def test_private_originals_do_not_enter_prompt():
    from prompt_evidence import prompt_evidence_copy
    value = {'data': {'lienhwa_conference_receipt': {'private': 'archive'}, 'lienhwa_glyph_evidence': {'private': 'glyph'}, 'text': '原件摘要'}}
    assert prompt_evidence_copy(value) == {'data': {'text': '原件摘要'}}

@pytest.mark.parametrize('marker', [{'lienhwa_conference_receipt': None}, {'lienhwa_glyph_evidence': False}, {'source': PROVIDER}, {'projection_policy': 'lienhwa-presentation-role-v1'}, {'url': 'https://www.lhicholdings.com/investors/3newsFile/Investor-Conference-dw-2026Q2_1/'}])
def test_no_store_originals_cannot_become_payload_cache(monkeypatch, marker):
    from data_fetch import cache_helpers
    calls = []
    monkeypatch.setattr(cache_helpers, 'set_cache_json', lambda *a, **kw: calls.append(a))
    value = {'ticker': '1229.TW', 'earnings_call': {'documents': [marker]}}
    original = deepcopy(value)
    cache_helpers._cache_financial_data(value, '1229.TW')
    assert not calls
    assert value == original

def test_source_observation_is_one_qualified_partial_document():
    from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
    result = {'value': context(), 'audit': {'status': 'success', 'record_count': 30}}
    apply_earnings_call_audit(result, {'lienhwa_presentation_workflow': True, 'lienhwa_originals_verified': True, 'actual_provider': PROVIDER, 'coverage_status': 'qualified_partial_presentation', 'http_request_count': 4, 'http_request_sent': True, 'cache_hit': False})
    assert result['audit']['record_count'] == 1
    assert result['audit']['http_request_count'] == 4
    assert result['value']['coverage_status'] == 'partial'

def test_invalid_caller_is_attributed_to_selected_issuer_provider(monkeypatch):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', lambda *a, **kw: pytest.fail('invalid context reached network boundary'))
    result = enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('1229.TW'), {'data': {'ticker': '1229.TW', 'company_name': '聯華', 'quote_type': 'ETF'}})
    assert result.provider == PROVIDER
    assert result.audit['event_kind'] == 'local_block'
    assert result.audit['record_count'] == result.audit['http_request_count'] == 0
