"""Issuer PDF routing and bounded role projections preserve original evidence."""
from copy import deepcopy
from types import SimpleNamespace
import sys

import pytest

PROVIDER = 'InnoCare official conference presentation'
SHA = 'a702ecdd7db0fd322885b2627de483508ae9a3ee7250aa4d5c3d50879eb15dad'


def test_public_6861_routing_prefers_issuer_without_touching_mops(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import mops_presentation
    expected = {'ticker': '6861.TW', 'source': PROVIDER, 'documents': [{'page_count': 11}]}
    calls = []
    def acquire(ticker, **options):
        calls.append((ticker, options))
        return expected
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.innocare_conference',
                        SimpleNamespace(supports_innocare=lambda t: t == '6861.TW', fetch_innocare_context=acquire))
    monkeypatch.setattr(mops_presentation, 'fetch_presentation_context', lambda *a, **kw: {'source': 'MOPS'})
    assert fetcher.fetch_free_earnings_call_context('6861.TW', force_refresh=True, use_cache=False) == expected
    assert len(calls) == 1 and calls[0][1]['force_refresh'] is True
    assert calls[0][1]['use_cache'] is False


@pytest.mark.parametrize('kind', ['timeout', 'lease_lost', 'single_flight_busy', 'guard_storage_unavailable', 'cooldown'])
def test_innocare_failure_never_retries_mops(monkeypatch, kind):
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.market_sources import mops_presentation
    from search_provider_runtime import SourceResponseError
    def fail(*a, **kw):
        raise SourceResponseError(kind)
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.innocare_conference',
                        SimpleNamespace(supports_innocare=lambda t: t == '6861.TW', fetch_innocare_context=fail))
    monkeypatch.setattr(mops_presentation, 'fetch_presentation_context', lambda *a, **kw: {'source': 'MOPS'})
    with pytest.raises(SourceResponseError) as caught:
        fetcher.fetch_free_earnings_call_context('6861.TW')
    assert caught.value.error_kind == kind


def context():
    import json
    from pathlib import Path
    p=Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261015/next-source-recovery/innocare-extraction.json'
    r=json.loads(p.read_text())
    return {'coverage_status':'partial','coverage_notes':['圖像未抽取，不是逐字稿'],
        'documents':[{'source':PROVIDER,'document_kind':'presentation','ticker':'6861.TW',
        'projection_policy':'innocare-presentation-role-v1','content_sha256':SHA,'page_count':19,
        'native_text_coverage':'partial','text_extraction_complete':False,'financial_statement_complete':False,
        'full_visual_content_verified':False,'q_and_a_transcript_available':False,
        'content_periods':['2026H1','2026Q2','2026H2 outlook'],'forward_looking_caution':'預計時程，不是已經完成',
        'period_scope_caution':'H1/Q2實績與2H展望分開','role_page_allowlist':list(range(1,20)),'pages':r['pages']}]}


def test_role_allowlist_is_fixed_and_preserves_partial_semantics():
    from conference_presentation_prompt import presentation_prompt_context
    value=context();before=deepcopy(value)
    for role in (3,5,12):
        p=presentation_prompt_context(value,role)
        assert p['transcript_available']is False and p['coverage_status']=='partial'
        d=p['documents'][0];pages=d['pages']
        assert {x['page_number']for x in pages}<={2,3,4,15}
        text=' '.join(x['text']for x in pages)
        assert '28% 29% 27%'not in text and '14% 12% 13%'not in text
        assert '預計9月底' in text and '11月初' in text
        assert d['forward_looking_caution']=='預計時程，不是已經完成'
        assert d['role_chart_text_omission_pages']==[4,15]
    assert value==before


@pytest.mark.parametrize('key',['projection_policy','content_sha256'])
def test_roles_reject_unknown_revision(key):
    from conference_presentation_prompt import presentation_prompt_context
    value = context(); value['documents'][0][key] = 'unknown'
    assert not presentation_prompt_context(value, 3).get('documents')


def test_private_originals_do_not_enter_prompt():
    from prompt_evidence import prompt_evidence_copy
    value = {'data': {'innocare_conference_receipt': {'private': 'archive'},
                      'text': '原件摘要'}}
    assert prompt_evidence_copy(value) == {'data': {'text': '原件摘要'}}


@pytest.mark.parametrize('marker', [
    {'innocare_conference_receipt': None},
    {'source': PROVIDER}, {'projection_policy': 'innocare-presentation-role-v1'},
    {'url': 'https://www.innocare-x.com/wp-content/uploads/2026/09/20260910142650_0_e8f3ed.pdf'},
])
def test_no_store_originals_cannot_become_payload_cache(monkeypatch, marker):
    from data_fetch import cache_helpers
    calls = []
    monkeypatch.setattr(cache_helpers, 'set_cache_json', lambda *a, **kw: calls.append(a))
    value = {'ticker': '6861.TW', 'earnings_call': {'documents': [marker]}}
    original = deepcopy(value)
    cache_helpers._cache_financial_data(value, '6861.TW')
    assert not calls
    assert value == original


def test_source_observation_is_one_qualified_partial_document():
    from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
    result = {'value': context(), 'audit': {'status': 'success', 'record_count': 30}}
    apply_earnings_call_audit(result, {'innocare_presentation_workflow': True,
        'innocare_originals_verified': True, 'actual_provider': PROVIDER,
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
    result = enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('6861.TW'),
        {'data': {'ticker': '6861.TW', 'company_name': '睿生光電', 'quote_type': 'ETF'}})
    assert result.provider == PROVIDER
    assert result.audit['event_kind'] == 'local_block'
    assert result.audit['record_count'] == result.audit['http_request_count'] == 0


from test_innocare_conference import harness, valid_data


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
    filename, keys, before = saved_target(storage, '6861.TW', '睿生光電')
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
                del value['innocare_conference_receipt']
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
        assert doc['page_count'] == len(doc['pages']) == 19
        assert doc['native_text_coverage'] == 'partial'
        assert doc['missing_text_pages'] == [1,19]
        assert doc['q_and_a_transcript_available'] is False
        assert result['analysis_text_stale'] is True
        assert_preserved(storage, keys, before, after)
    ledger = events()
    assert len(ledger) == 1 and ledger[0]['source'] == 'earnings_call'
    assert len(harness[1]) == 3

@pytest.mark.parametrize('change',['chart_as_text','unverified_completion','page_id_boolean'])
def test_role_projection_rejects_content_tampering_even_if_digest_label_is_unchanged(change):
    from conference_presentation_prompt import presentation_prompt_context
    v=context();d=v['documents'][0]
    if change=='chart_as_text':d['pages'][3]['text']='營收占比已達43%'
    elif change=='unverified_completion':d['pages'][14]['text']=d['pages'][14]['text'].replace('預計9月底','已於9月底')
    else:d['pages'][0]['page_number']=True
    for role in (3,5,12):assert not presentation_prompt_context(v,role).get('documents')
