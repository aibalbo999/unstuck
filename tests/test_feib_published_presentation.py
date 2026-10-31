"""FEIB public MOPS body through the shared collector and report boundary."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from test_mops_presentation import harness

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'docs/evidence/source-acquisition/20261016'
TICKER = '2845.TW'


def identity():
    return json.loads((D / 'feib-integration/identity.json').read_text())


@pytest.fixture
def feib(harness):
    bodies, calls = harness
    bodies[TICKER + ':index'] = (D / 'feib-mops-official-index/index/response.body').read_bytes()
    bodies[TICKER + ':material'] = (D / 'feib-mops-official-index/pdf/response.body').read_bytes()
    return bodies, calls


def acquire(**kwargs):
    from data_fetch.market_sources.mops_presentation import fetch_presentation_context
    return fetch_presentation_context(TICKER, **kwargs)


def test_published_feib_original_fills_body_with_original_scope(feib):
    value = acquire()
    assert len(value.get('documents', [])) == 1, 'FEIB qualified public original has no collector profile'
    document = value['documents'][0]
    assert len(document['pages']) == document['page_count'] == 23
    assert document['event_date'] == document['material_file_date'] == '2026-08-20'
    assert document['content_period'] == '2026Q2'
    assert document['native_text_coverage'] == 'complete' and document['coverage_status'] == 'partial'
    assert document['financial_statement_complete'] is False and value['transcript_available'] is False
    assert document['full_visual_content_verified'] is False and document['published_at'] is None
    assert document['role_page_allowlist'] == [1, 4, 16, 18, 23]
    assert feib[1] == ['master', TICKER + ':index', TICKER + ':material']


def test_public_provider_and_warm_cache_keep_one_acquisition(feib):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    provider = EarningsCallProvider(); request = FetchRequest.from_ticker(TICKER)
    cold = provider.fetch(request, {'data': identity()})
    warm = provider.fetch(request, {'data': identity()})
    assert cold.provider == 'MOPS published presentation'
    assert cold.audit['status'] == 'success' and cold.audit['record_count'] == 1
    assert cold.audit['http_request_count'] == 3 and cold.audit['http_request_sent'] is True
    assert warm.audit['status'] == 'skipped_fresh_cache' and warm.audit['cache_hit'] is True
    assert warm.audit['http_request_count'] == 0 and warm.audit['http_request_sent'] is False
    assert warm.value['documents'] == cold.value['documents'] and len(feib[1]) == 3
    assert warm.value['fetched_at_epoch'] == cold.value['fetched_at_epoch']


@pytest.mark.parametrize('change', ['group', 'ubn', 'alias', 'etf', 'market'])
def test_wrong_issuer_stops_before_http(feib, change):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    data = identity()
    if change == 'group': data['company_name'] = 'Far Eastern Group'
    elif change == 'ubn': data['company_identity']['official_ubn'] = '00000000'
    elif change == 'alias': data['company_identity']['allowed_aliases'].append('Far Eastern Group')
    elif change == 'etf': data['quote_type'] = 'ETF'
    else: data['company_identity']['ticker'] = '2845.TWO'
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker(TICKER), {'data': data})
    assert result.status == 'unavailable' and result.audit['http_request_count'] == 0
    assert not feib[1]


@pytest.mark.parametrize('change', ['filename', 'date', 'body', 'master'])
def test_new_or_conflicting_original_needs_qualification(feib, change):
    from search_provider_runtime import SourceResponseError
    bodies, _ = feib
    if change == 'filename': bodies[TICKER + ':index'] = bodies[TICKER + ':index'].replace(b'284520260820E002.pdf', b'284520260820E003.pdf')
    elif change == 'date': bodies[TICKER + ':index'] = bodies[TICKER + ':index'].replace(b'115/08/20', b'115/08/21')
    elif change == 'body': bodies[TICKER + ':material'] += b'\n'
    else: bodies['master'] = bodies['master'].replace(b'86517096', b'00000000')
    with pytest.raises(SourceResponseError): acquire()


@pytest.mark.parametrize('role', [3, 5, 12])
def test_roles_keep_full_disclaimer_and_separate_group_periods(feib, role):
    from conference_presentation_prompt import presentation_prompt_context, without_presentation_documents
    value = acquire(); before = deepcopy(value)
    document = presentation_prompt_context(value, role)['documents'][0]
    assert [p['page_number'] for p in document['pages']] == [1, 4, 16, 18, 23]
    assert all(not p['content_truncated'] and p['text'] == value['documents'][0]['pages'][p['page_number']-1]['text'] for p in document['pages'])
    assert len(document['pages'][-1]['text']) == 1777
    for k in ('subsidiary_scope_caution', 'period_scope_caution', 'unit_scope_caution',
              'financial_scope_caution', 'forward_looking_caution', 'identity_text_basis'):
        assert document[k] == value['documents'][0][k]
    assert document['financial_statement_complete'] is False
    assert value == before and 'documents' not in without_presentation_documents(value)


@pytest.mark.parametrize('change', ['text', 'missing_page', 'disclaimer', 'period', 'financial',
                                  'allowlist', 'source', 'ticker', 'parser', 'retiming', 'receipt'])
def test_modified_report_evidence_is_rejected(feib, change):
    from conference_presentation_prompt import presentation_prompt_context
    from data_fetch.market_sources.mops_presentation import verify_context
    value = acquire(); doc = value['documents'][0]
    if change == 'text': doc['pages'][3]['text'] += ' invented profit'
    elif change == 'missing_page': doc['pages'].pop(1)
    elif change == 'disclaimer': doc['pages'][-1]['text'] = 'No restrictions'
    elif change == 'period': doc['content_period'] = '2026Q3'
    elif change == 'financial': doc['financial_statement_complete'] = True
    elif change == 'allowlist': doc['role_page_allowlist'].append(2)
    elif change == 'source': doc['source'] = 'Other issuer'
    elif change == 'ticker': doc['ticker'] = '2845.TWO'
    elif change == 'parser': doc['parser_version'] = 'unknown'
    elif change == 'retiming': doc['retrieved_at_epoch'] = True
    else: value['mops_material_receipt']['material']['request']['request_body'] += '&other=1'
    assert not verify_context(value, TICKER)
    if change != 'receipt':
        assert not presentation_prompt_context(value, 3).get('documents')


@pytest.mark.parametrize('tamper', [False, True])
def test_public_refresh_saves_only_verified_new_body(feib, tmp_path, monkeypatch, tamper):
    import asyncio
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
    filename, keys, before = saved_target(storage, TICKER, '遠東銀')
    before['data'].update(identity())
    before['analysis_evidence'] = capture_analysis_evidence({'data': before['data']}, generated_at=before['generated_at'])
    storage.save_report(keys.data_key, json.dumps(before).encode(), content_type='application/json')
    original = storage.get_report(keys.data_key).content
    if tamper:
        real = enrichment_providers.fetch_free_earnings_call_context
        def edited(*args, **kwargs):
            value = real(*args, **kwargs)
            value['documents'][0]['financial_statement_complete'] = True
            return value
        monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', edited)
    service = StockDataService(registry=ProviderRegistry([enrichment_providers.EarningsCallProvider()]))
    call = refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
                                       refresh_service=service, source='earnings_call', return_refreshed_data=True)
    if tamper:
        with pytest.raises(HTTPException): asyncio.run(call)
        assert storage.get_report(keys.data_key).content == original
    else:
        result = asyncio.run(call)
        after = json.loads(storage.get_report(keys.data_key).content)
        assert len(after['data']['earnings_call']['documents'][0]['pages']) == 23
        assert_preserved(storage, keys, before, after)
        assert result['analysis_text_stale'] is True
    rows = events()
    successful = [r for r in rows if r['source'] == 'earnings_call' and r['status'] == 'success']
    # This injection runs after genuine original acquisition. The source ledger
    # keeps that outcome, while the independent save gate rejects altered data.
    assert len(successful) == 1 and len(rows) == 1
