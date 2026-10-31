"""New holding acquisitions carry complete originals through both public paths."""
import gzip
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from test_official_financial_institution_xbrl import filing


FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition'


def acquired(monkeypatch):
    import data_fetch.market_sources.financial_institution_xbrl as source
    from data_fetch.market_sources.official_xbrl_financial import INDEX_URL
    index = gzip.decompress((FIXTURES / 'bank_2834_index_captured_20261011.html.gz').read_bytes()).replace(b'2834', b'2885')
    calls = []
    def request(client, method, url, *, data=None):
        calls.append(url)
        if url == INDEX_URL:
            assert method == 'POST' and data['co_id'] == '2885'
            return index
        query = parse_qs(urlsplit(url).query)
        assert method == 'GET' and query['co_id'] == ['2885'] and query['report_id'] == ['C']
        return filing(int(query['year'][0]), issuer='2885')
    monkeypatch.setattr(source, '_bounded_request', request)
    return source.fetch_financial_institution_histories('2885.TW', client=object()), calls


def test_public_holding_fetch_preserves_five_complete_originals_with_distinct_verified_schema(monkeypatch):
    from official_response_evidence import read_response
    from data_fetch.annual_financial_source_provider import project_source_value
    value, calls = acquired(monkeypatch)
    assert value['schema'] == 'financial_holding_consolidated.v2'
    assert value['statement_taxonomy'] == 'financial_holding' and value['currency'] == 'TWD'
    assert len(calls) == 6
    for doc in value['documents']:
        assert doc['statement_taxonomy'] == 'financial_holding'
        assert read_response(doc['source_record_archive']) == filing(doc['year'], issuer='2885')
    projected = project_source_value(value, '2885.TW')
    assert projected is not None and projected['net_revenue_history'] == [0.0014] * 5
    assert projected['revenue_history'] == projected['gross_profit_history'] == projected['operating_income_history'] == [None] * 5


@pytest.mark.parametrize('change', ['missing_archive', 'missing_marker', 'missing_currency',
                                  'wrong_scope', 'wrong_issuer', 'changed_fact', 'changed_sha'])
def test_holding_full_original_contract_rejects_unbound_or_changed_receipts(monkeypatch, change):
    from data_fetch.annual_financial_source_provider import project_source_value
    from prompt_builder_helpers import _prompt_financial_institution_history
    value, _ = acquired(monkeypatch)
    if change == 'missing_archive':
        value['documents'][0].pop('source_record_archive')
    elif change == 'missing_marker':
        value.pop('statement_taxonomy')
        for document in value['documents']:
            document.pop('statement_taxonomy')
    elif change == 'missing_currency':
        value.pop('currency')
    elif change == 'wrong_scope':
        value['report_scope'] = 'individual'
    elif change == 'wrong_issuer':
        value['ticker'] = '2884.TW'
    elif change == 'changed_fact':
        value['raw_twd_by_year']['2021']['net_revenue'] += 1
    elif change == 'changed_sha':
        value['documents'][0]['sha256'] = '0' * 64
    assert project_source_value(value, '2885.TW') is None
    assert _prompt_financial_institution_history({'ticker': '2885.TW', 'sector_specific_financials': value}) == {}


def test_complete_holding_normal_extraction_avoids_redundant_sdk_and_finmind(monkeypatch):
    from data_fetch import yfinance_extractors as source
    from test_financial_institution_history_projection import NoAnnualSdk
    value, _ = acquired(monkeypatch)
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '0')
    monkeypatch.setattr(source, 'fetch_financial_institution_histories', lambda ticker: deepcopy(value))
    monkeypatch.setattr(source, 'fetch_finmind_financial_statement_fallback',
                        lambda *a, **kw: pytest.fail('complete holding must avoid redundant FinMind'))
    data = source.extract_financial_histories(NoAnnualSdk(), '2885.TW', [], industry_context='金融保險')
    assert data['financial_history_basis']['statement_schema'] == 'financial_holding_consolidated.v2'
    assert data['net_revenue_history'] == [0.0014] * 5 and data['revenue_history'] == [None] * 5


def test_public_holding_source_only_refresh_preserves_quote_conclusions_and_quality_gates(monkeypatch, tmp_path):
    import asyncio
    import json
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from test_report_annual_financial_source_refresh import report, init_db, events
    import data_fetch.market_sources.financial_institution_xbrl as native
    value, _ = acquired(monkeypatch)
    init_db()
    storage, name, keys, old = report('2885.TW')
    old['data'].update(company_name='元大金', sector='Financial Services', industry='Financial Conglomerates')
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    monkeypatch.setattr(native, 'fetch_financial_institution_histories', lambda ticker: deepcopy(value))
    response = asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
        refresh_service=StockDataService(), source='financial_statements', return_refreshed_data=True))
    saved = json.loads(storage.get_report(keys.data_key).content)
    assert saved['data']['financial_history_basis']['statement_schema'] == 'financial_holding_consolidated.v2'
    assert saved['data']['net_revenue_history'] == [0.0014] * 5
    assert saved['data']['revenue_history'] == [None] * 5
    assert response['analysis_text_stale'] is True and saved['analysis_evidence'] == old['analysis_evidence']
    for key in ['current_price', 'revenue_ttm_raw', 'free_cash_flow_raw', 'operating_cash_flow_raw', 'recent_catalysts', 'earnings_call']:
        assert saved['data'][key] == old['data'][key]
    for gate in ['report_lint', 'final_audit', 'evidence_exit_gate', 'content_credibility', 'report_conformance']:
        assert saved[gate] == old[gate]
    assert storage.get_report(keys.html_key).content == storage.get_report(keys.md_key).content == b'original conclusions'
    assert len(events()) == 1 and events()[0]['source'] == 'financial_statements' and events()[0]['record_count'] == 5


def test_holding_archive_failure_stops_without_implicit_network_repeat(monkeypatch):
    import official_response_evidence
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    seen = []
    def unavailable(*args, **kwargs):
        seen.append(kwargs['source_url'])
        raise OSError('archive unavailable')
    monkeypatch.setattr(official_response_evidence, 'archive_response', unavailable)
    with pytest.raises(FilingError, match='archive is unreadable'):
        acquired(monkeypatch)
    assert len(seen) == 1


def test_missing_all_holding_original_markers_cannot_enter_public_prompt_raw_history(monkeypatch):
    import json
    from data_fetch.annual_financial_source_provider import project_source_value
    from prompt_builder import format_data_for_prompt
    value, _ = acquired(monkeypatch)
    value.pop('statement_taxonomy')
    for document in value['documents']:
        document.pop('statement_taxonomy')
        document.pop('source_record_archive')
    value['raw_twd_by_year']['2021']['net_revenue'] = 987654321000
    assert project_source_value(value, '2885.TW') is None
    encoded = format_data_for_prompt({'ticker': '2885.TW', 'sector_specific_financials': value})
    payload = json.loads(encoded.split('【財務資料 JSON】\n', 1)[1].split('\n\n【使用規則】', 1)[0])
    assert payload['history']['financial_institution'] == {}
