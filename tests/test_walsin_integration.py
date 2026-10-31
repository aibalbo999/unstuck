"""Issuer PDF routing and bounded role projections preserve original evidence."""
from copy import deepcopy
from types import SimpleNamespace
import sys

import pytest

PROVIDER = 'Walsin official conference presentation'
SHA = '8cd60978a0130763166c32c4854e697575445b7c8891f20c7f12bd9cd2534dcd'


def test_public_1605_routing_prefers_issuer_without_touching_mops(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import mops_presentation
    expected = {'ticker': '1605.TW', 'source': PROVIDER, 'documents': [{'page_count': 11}]}
    calls = []
    def acquire(ticker, **options):
        calls.append((ticker, options))
        return expected
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.walsin_conference',
                        SimpleNamespace(supports_walsin=lambda t: t == '1605.TW', fetch_walsin_context=acquire))
    monkeypatch.setattr(mops_presentation, 'fetch_presentation_context', lambda *a, **kw: {'source': 'MOPS'})
    assert fetcher.fetch_free_earnings_call_context('1605.TW', force_refresh=True, use_cache=False) == expected
    assert len(calls) == 1 and calls[0][1]['force_refresh'] is True
    assert calls[0][1]['use_cache'] is False


@pytest.mark.parametrize('kind', ['timeout', 'lease_lost', 'single_flight_busy', 'guard_storage_unavailable', 'cooldown'])
def test_walsin_failure_never_retries_mops(monkeypatch, kind):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import mops_presentation
    from search_provider_runtime import SourceResponseError
    def fail(*a, **kw):
        raise SourceResponseError(kind)
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.walsin_conference',
                        SimpleNamespace(supports_walsin=lambda t: t == '1605.TW', fetch_walsin_context=fail))
    monkeypatch.setattr(mops_presentation, 'fetch_presentation_context', lambda *a, **kw: {'source': 'MOPS'})
    with pytest.raises(SourceResponseError) as caught:
        fetcher.fetch_free_earnings_call_context('1605.TW')
    assert caught.value.error_kind == kind


def context():
    return {'coverage_status': 'partial', 'coverage_notes': ['圖像未抽取，不是逐字稿'],
            'documents': [{'source': PROVIDER, 'document_kind': 'presentation', 'ticker': '1605.TW',
                           'projection_policy': 'walsin-presentation-role-v1', 'content_sha256': SHA,
                           'page_count': 11, 'native_text_coverage': 'complete', 'text_extraction_complete': True,
                           'q_and_a_transcript_available': False, 'financial_statement_complete': False,
                           'full_visual_content_verified': False,
                           'content_periods': ['2026H1', '2026Q2', 'comparisons and future projections'],
                           'unit_scope_caution': '金額為十億元，破折號不當零',
                           'period_scope_caution': 'Q3展望為8月的公司說法',
                           'native_editorial_caution': 'p4 EBITDA與YoY矛盾',
                           'cash_scope_caution': '現金17.9含避險資產0.2，並非17.7',
                           'role_page_allowlist': list(range(1, 12)),
                           'pages': [{'page_number': n, 'text': '營收 市場 產品 展望 風險 ' * 2} for n in range(1, 12)]}]}


def test_role_allowlist_is_fixed_and_preserves_partial_semantics():
    from conference_presentation_prompt import presentation_prompt_context
    value = context(); before = deepcopy(value)
    for role in (3, 5, 12):
        projected = presentation_prompt_context(value, role)
        assert projected['transcript_available'] is False
        assert projected['coverage_status'] == 'partial'
        doc = projected['documents'][0]
        assert {p['page_number'] for p in doc['pages']} == {1, 2, 3, 8, 9, 10}
        assert doc['excluded_native_text_pages'] == [4, 5, 6, 7, 11]
        assert doc['role_page_allowlist'] == [1, 2, 3, 8, 9, 10]
        for key in ('q_and_a_transcript_available', 'financial_statement_complete', 'full_visual_content_verified',
                    'content_periods', 'unit_scope_caution', 'period_scope_caution', 'native_editorial_caution', 'cash_scope_caution'):
            assert doc[key] == value['documents'][0][key]
    assert value == before


@pytest.mark.parametrize('key', ['projection_policy', 'content_sha256'])
def test_roles_reject_unknown_revision(key):
    from conference_presentation_prompt import presentation_prompt_context
    value = context(); value['documents'][0][key] = 'unknown'
    assert not presentation_prompt_context(value, 3).get('documents')


def test_private_originals_do_not_enter_prompt():
    from prompt_evidence import prompt_evidence_copy
    value = {'data': {'walsin_conference_receipt': {'private': 'archive'},
                      'text': '原件摘要'}}
    assert prompt_evidence_copy(value) == {'data': {'text': '原件摘要'}}


@pytest.mark.parametrize('marker', [
    {'walsin_conference_receipt': None},
    {'source': PROVIDER}, {'projection_policy': 'walsin-presentation-role-v1'},
    {'url': 'https://www.walsin.com/wp-content/uploads/2026/08/%E3%80%90PBA%E3%80%912026Q2-%E6%B3%95%E8%AA%AA%E6%9C%83%E5%A0%B1%E5%91%8A%E6%AA%94_EN.pdf'},
])
def test_no_store_originals_cannot_become_payload_cache(monkeypatch, marker):
    from data_fetch import cache_helpers
    calls = []
    monkeypatch.setattr(cache_helpers, 'set_cache_json', lambda *a, **kw: calls.append(a))
    value = {'ticker': '1605.TW', 'earnings_call': {'documents': [marker]}}
    original = deepcopy(value)
    cache_helpers._cache_financial_data(value, '1605.TW')
    assert not calls
    assert value == original


def test_source_observation_is_one_qualified_partial_document():
    from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
    result = {'value': context(), 'audit': {'status': 'success', 'record_count': 30}}
    apply_earnings_call_audit(result, {'walsin_presentation_workflow': True,
        'walsin_originals_verified': True, 'actual_provider': PROVIDER,
        'coverage_status': 'qualified_partial_presentation', 'http_request_count': 3,
        'http_request_sent': True, 'cache_hit': False})
    assert result['audit']['record_count'] == 1
    assert result['audit']['http_request_count'] == 3
    assert result['value']['coverage_status'] == 'partial'


def test_invalid_caller_is_attributed_to_selected_issuer_provider(monkeypatch):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context',
                        lambda *a, **kw: pytest.fail('invalid context reached network boundary'))
    result = enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('1605.TW'),
        {'data': {'ticker': '1605.TW', 'company_name': '華新', 'quote_type': 'ETF'}})
    assert result.provider == PROVIDER
    assert result.audit['event_kind'] == 'local_block'
    assert result.audit['record_count'] == result.audit['http_request_count'] == 0


from test_walsin_conference import harness, valid_data


@pytest.mark.parametrize('tamper', [None, 'missing_page', 'scope', 'receipt'])
def test_saved_source_preserves_analysis_and_rejects_incomplete_proof(harness, tmp_path, monkeypatch, tamper):
    import asyncio
    import json
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
    filename, keys, before = saved_target(storage, '1605.TW', '華新')
    before['data'].update(valid_data())
    before['analysis_evidence'] = capture_analysis_evidence({'data': before['data']}, generated_at=before['generated_at'])
    storage.save_report(keys.data_key, json.dumps(before).encode(), content_type='application/json')
    original = storage.get_report(keys.data_key).content
    if tamper:
        acquire = enrichment_providers.fetch_free_earnings_call_context
        def corrupted(*args, **kwargs):
            value = acquire(*args, **kwargs)
            if tamper == 'missing_page':
                value['documents'][0]['pages'].pop()
            elif tamper == 'scope':
                value['documents'][0]['financial_statement_complete'] = True
            else:
                del value['walsin_conference_receipt']
            return value
        monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', corrupted)
    service = StockDataService(registry=ProviderRegistry([enrichment_providers.EarningsCallProvider()]))
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
        assert doc['page_count'] == len(doc['pages']) == 11
        assert doc['native_text_coverage'] == 'complete'
        assert doc['missing_text_pages'] == []
        assert doc['q_and_a_transcript_available'] is False
        assert result['analysis_text_stale'] is True
        assert_preserved(storage, keys, before, after)
    ledger = events()
    assert len(ledger) == 1 and ledger[0]['source'] == 'earnings_call'
    assert len(harness[1]) == 3
