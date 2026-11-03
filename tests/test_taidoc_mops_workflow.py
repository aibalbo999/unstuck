"""Historical published material uses normal caches and unchanged report gates."""
from hashlib import sha256
import asyncio
import json
from pathlib import Path
import time

import pytest

from test_mops_presentation import harness as common_harness

D = Path(__file__).resolve().parents[1] / 'docs/evidence/source-acquisition/20261103/taidoc-mops'
NOW = json.loads((D / 'research-material.json').read_text())['receipt']['retrieved_at'] + 1


def valid_data():
    return {'ticker': '4736.TW', 'instrument_type': 'EQUITY', 'quote_type': 'EQUITY',
            'company_name': '泰博 / TaiDoc Technology Corporation', 'raw_company_name': 'TaiDoc Technology Corporation',
            'company_identity': {'ticker': '4736.TW', 'stock_id': '4736', 'official_name': '泰博',
                'legal_name': '泰博科技股份有限公司', 'official_ubn': '16584326', 'instrument_type': 'EQUITY',
                'display_name': '泰博 / TaiDoc Technology Corporation',
                'english_names': ['TaiDoc Technology Corporation'],
                'allowed_aliases': ['泰博', '4736.TW', '4736', 'TaiDoc Technology Corporation'], 'forbidden_aliases': []}}


@pytest.fixture
def packet(common_harness, monkeypatch):
    from data_fetch.market_sources import mops_presentation as m
    from mops_material_transport import index_request
    bodies, calls = common_harness
    bodies['master'] = (D / 'fixture-master.body').read_bytes()
    bodies['4736.TW:material'] = (D / 'research-material.pdf').read_bytes()
    monkeypatch.setattr(time, 'time', lambda: NOW)
    def index(ticker, year, deadline, diagnostics):
        assert ticker == '4736.TW' and year in (2026, 2025)
        raw = (D / ('fixture-index-' + str(year) + '.body')).read_bytes()
        spec = index_request(ticker, year); calls.append(ticker + ':index:' + str(year))
        diagnostics.update(http_request_sent=True, http_request_count=1, http_status=200,
            response_complete=True, response_sha256=sha256(raw).hexdigest(), response_metadata={
                'http_status': 200, 'effective_url': spec['url'], 'num_redirects': 0, 'size_download': len(raw),
                'content_type': 'text/html', 'content_length': len(raw), 'method': 'POST', 'proxy_used': 0})
        return raw
    monkeypatch.setattr(m, 'download_conference_index', index)
    return calls


def test_complete_packet_keeps_image_and_glyph_gaps_but_projects_qualified_whole_pages(packet, monkeypatch):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    from data_fetch.market_sources import mops_presentation as m
    from conference_presentation_prompt import presentation_prompt_context
    diagnostic = {}
    value = fetch_free_earnings_call_context('4736.TW', diagnostics=diagnostic, force_refresh=False, use_cache=True)
    assert m.verify_context(value, '4736.TW') and diagnostic['http_request_count'] == 4
    assert packet == ['master', '4736.TW:index:2026', '4736.TW:index:2025', '4736.TW:material']
    doc = value['documents'][0]
    assert len(doc['pages']) == doc['page_count'] == 23 and doc['garbled_pages'] == [14]
    assert doc['native_text_coverage'] == 'partial' and not doc['financial_statement_complete']
    assert not doc['text_extraction_complete'] and not doc['full_content_coverage_verified']
    assert '影像' in doc['period_scope_caution'] and 'In Clinical Trials' in doc['period_scope_caution']
    for role, expected in {3: [1, 3, 11], 5: [1, 3, 8, 9, 11], 12: [1, 3, 11]}.items():
        projection = presentation_prompt_context(value, role)['documents'][0]
        assert [p['page_number'] for p in projection['pages']] == expected
        assert all(p['content_truncated'] is False for p in projection['pages'])
    packet.clear(); warm = {}
    again = fetch_free_earnings_call_context('4736.TW', diagnostics=warm, force_refresh=False, use_cache=True)
    assert not packet and warm['cache_hit'] is True and warm['http_request_count'] == 0
    assert again['documents'] == value['documents']
    monkeypatch.setattr(time, 'time', lambda: NOW + 1800)
    assert not m.verify_context(value, '4736.TW')


def test_unqualified_roles_cannot_read_retained_image_financials_or_marketing_pages(packet):
    from data_fetch.market_sources import mops_presentation as m
    from conference_presentation_prompt import presentation_prompt_context
    value = m.fetch_presentation_context('4736.TW')
    assert len(value['documents'][0]['pages']) == 23
    for role in (1, 2, 4, 6, 7, 11, 20, 21):
        assert not presentation_prompt_context(value, role).get('documents')


def test_taidoc_uses_bounded_material_allocation_without_extending_workflow(packet, monkeypatch):
    from data_fetch.market_sources import mops_presentation as m
    assert m.PROFILES['4736.TW']['material_wire_seconds'] == 15.
    original = m.download_published_material
    observed = []
    start = time.monotonic()
    def download(spec, *, deadline, diagnostics, wire_budget_seconds):
        observed.append((spec['ticker'], wire_budget_seconds, deadline))
        return original(spec, deadline=deadline, diagnostics=diagnostics,
                        wire_budget_seconds=wire_budget_seconds)
    monkeypatch.setattr(m, 'download_published_material', download)
    value = m.fetch_presentation_context('4736.TW', force_refresh=False, use_cache=True)
    assert len(observed) == 1 and observed[0][:2] == ('4736.TW', 15.)
    assert 0 < observed[0][2] - start <= 25.1
    assert m.verify_context(value, '4736.TW')


@pytest.mark.parametrize('damage', ['role_whitelist', 'image_fact', 'clinical_claim', 'scope', 'period', 'absence'])
def test_changed_scope_period_or_role_pages_never_reach_prompts(packet, damage):
    from data_fetch.market_sources import mops_presentation as m
    from conference_presentation_prompt import presentation_prompt_context
    value = m.fetch_presentation_context('4736.TW'); doc = value['documents'][0]
    if damage == 'role_whitelist': doc['role_page_allowlist']['5'] = list(range(1, 24))
    elif damage == 'image_fact': doc['pages'][4]['text'] += '\nCurrent net profit 1065'
    elif damage == 'clinical_claim': doc['pages'][10]['text'] = doc['pages'][10]['text'].replace('In Clinical Trials', 'Approved')
    elif damage == 'scope': doc['financial_statement_complete'] = True
    elif damage == 'period': doc['period_scope_caution'] = '2025.01~09 is FY2026 TTM'
    else: value['mops_material_receipt'].pop('absence_current_index')
    assert not m.verify_context(value, '4736.TW')
    assert not presentation_prompt_context(value, 5).get('documents')


@pytest.mark.parametrize('damage', ['ticker', 'ubn', 'instrument'])
def test_foreign_context_is_blocked_before_a_provider_send(monkeypatch, damage):
    from data_fetch.market_sources import mops_presentation as m
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    data = valid_data()
    if damage == 'ticker': data['ticker'] = '4737.TW'
    elif damage == 'ubn': data['company_identity']['official_ubn'] = '11111111'
    else: data['instrument_type'] = 'ETF'
    monkeypatch.setattr(m, 'fetch_presentation_context', lambda *a, **k: pytest.fail('invalid context sent HTTP'))
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('4736.TW'), {'data': data})
    assert result.audit['error_kind'] == 'context_unverified' and result.audit['http_request_sent'] is False


def test_source_refresh_preserves_original_analysis_and_records_one_acquisition(packet, tmp_path):
    from data_fetch import enrichment_providers
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from report_analysis_evidence import capture_analysis_evidence
    from storage.report_storage import InMemoryStorage
    from test_report_refresh_acquisition_audit import init_db, events
    from test_unitech_tcfhc_source_integration import saved_target, assert_preserved
    init_db(); storage = InMemoryStorage()
    filename, keys, before = saved_target(storage, '4736.TW', '泰博'); before['data'].update(valid_data())
    before['analysis_evidence'] = capture_analysis_evidence({'data': before['data']}, generated_at=before['generated_at'])
    storage.save_report(keys.data_key, json.dumps(before).encode(), content_type='application/json')
    service = StockDataService(registry=ProviderRegistry([enrichment_providers.EarningsCallProvider()]))
    result = asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
        refresh_service=service, source='earnings_call', return_refreshed_data=True))
    after = json.loads(storage.get_report(keys.data_key).content)
    assert_preserved(storage, keys, before, after)
    assert result['analysis_text_stale'] is True and len(after['data']['earnings_call']['documents'][0]['pages']) == 23
    audit = events(); assert len(audit) == 1 and audit[0]['status'] == 'success' and audit[0]['record_count'] == 1
    details = json.loads(audit[0]['details_json'])
    assert details['http_request_sent'] is True and details['http_request_count'] == 4
    assert len(details['original_http_receipts']) == 4
