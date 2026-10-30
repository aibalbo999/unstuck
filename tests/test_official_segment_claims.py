"""Qualified product cells cannot certify issuer totals or other scopes."""
import copy
import pytest

from evidence_exit_gate import evaluate_report_evidence


def source():
    return {'ticker': '1623.TW', 'company_name': '大東電', 'financial_currency': 'TWD',
            'years': ['2025'], 'revenue_history': [6.61],
            'official_segment_reference': {'schema': 'test-replay-token'}}


@pytest.fixture
def replay(monkeypatch):
    from data_fetch.market_sources import tewc_segment_reference as module
    value = {'schema': module.SCHEMA, 'status': 'issuer_presentation_cells_verified',
        'ticker': '1623.TW', 'report_scope': 'issuer_presentation_product', 'audited': False,
        'historical_pit_verified': False, 'native_acquisition': False,
        'freshness_status': 'not_revalidated', 'archive_evidence_replay': True,
        'document': {'source_url': 'https://example.test/qualified-original.pdf',
                     'raw_response_sha256': 'a' * 64, 'page_number': 14,
                     'original_retrieved_at': 1792000000.0},
        'facts': {
            '2025': {'period_start': '2025-01-01', 'period_end': '2025-12-31', 'currency': 'TWD',
                     'net_operating_revenue_twd': 2703969000, 'company_revenue_proportion_pct': 40.93,
                     'provenance': {'page_number': 14, 'source_row': 'Extra-high Voltage Cables', 'source_column': '2025', 'source_unit': 'NTD Thousand'}},
            '2026Q1': {'period_start': '2026-01-01', 'period_end': '2026-03-31', 'currency': 'TWD',
                       'net_operating_revenue_twd': 1022772000, 'company_revenue_proportion_pct': 54.92,
                       'provenance': {'page_number': 14, 'source_row': 'Extra-high Voltage Cables', 'source_column': '2026Q1', 'source_unit': 'NTD Thousand'}}}}
    def read(reference, ticker):
        assert reference == {'schema': 'test-replay-token'} and ticker == '1623.TW'
        return copy.deepcopy(value)
    monkeypatch.setattr(module, 'replay_segment_reference', read)
    return value


def amounts(text, data=None):
    result = evaluate_report_evidence(text, {'data': data or source()})
    assert result['coverage_complete']
    return [c for c in result['sampled_claims'] if c.get('financial_amount')]


@pytest.mark.parametrize('text,period', [
    ('數據依據：2025 年特高壓電纜（Extra-high Voltage Cables）營收達27.04億元，佔比40.93%。', '2025'),
    ('根據公司法說會簡報（原頁14），2025年特高壓電纜營收27.04億元，營收佔比為40.93%。', '2025'),
    ('本公司2026年Q1特高壓電纜營收10.22772億元。', '2026Q1'),
])
def test_only_replayed_issuer_product_cell_verifies(replay, text, period):
    checked = amounts(text)[0]
    assert checked['status'] == 'verified'
    assert checked['financial_period'] == period
    assert checked['financial_reporting_scope'] == 'issuer_presentation_product'
    assert checked['source_audited'] is False
    assert checked['historical_point_in_time_verified'] is False
    assert checked['source_freshness_status'] == 'not_revalidated'
    assert checked['source_row'] == 'Extra-high Voltage Cables'


def test_wrong_product_amount_is_not_saved_by_matching_issuer_total(replay):
    checked = amounts('2025年特高壓電纜營收66.1億元。')[0]
    assert checked['status'] == 'mismatch'
    assert checked['expected_value_raw_twd'] == 2703969000


@pytest.mark.parametrize('text', [
    '同業華通2025年特高壓電纜營收27.04億元。',
    '未知公司2025年特高壓電纜營收27.04億元。',
    '2024年特高壓電纜營收27.04億元。',
    '2026年Q2特高壓電纜營收10.22772億元。',
    '2025年中高壓電纜營收27.04億元。',
    '2025年特高壓電纜合併營收27.04億元。',
    '2025年特高壓電纜個別財報營收27.04億元。',
    '2025年特高壓電纜營收27.04億元（合併）。',
    '2025年特高壓電纜營收27.04億元（同業華通）。',
    '2025年特高壓電纜營收27.04億元（美元）。',
    '預期2025年特高壓電纜營收27.04億元。',
    '若2025年特高壓電纜營收27.04億元。',
    '特高壓電纜營收27.04億元。',
])
def test_other_product_owner_period_scope_or_future_stays_unknown(replay, text):
    assert all(c['status'] == 'unverifiable' for c in amounts(text))


def test_missing_or_failed_replay_cannot_be_replaced_by_caller_facts(replay):
    data = source(); data.pop('official_segment_reference')
    data['facts'] = replay['facts']
    assert amounts('2025年特高壓電纜營收27.04億元。', data)[0]['status'] == 'unverifiable'
    replay['status'] = 'unverified'
    assert amounts('2025年特高壓電纜營收27.04億元。')[0]['status'] == 'unverifiable'


def test_existing_frozen_receipt_chain_is_replayed_without_changing_input(monkeypatch, replay):
    from data_fetch.market_sources import tewc_segment_reference as module
    data = source(); data.pop('official_segment_reference')
    data['earnings_call'] = {'tewc_conference_receipt': {'private_test_receipt': True}}
    before = copy.deepcopy(data)
    def verify(reference, ticker):
        assert reference == {'schema': module.SCHEMA, 'ticker': '1623.TW',
                             'conference_receipt': {'private_test_receipt': True}}
        return copy.deepcopy(replay)
    monkeypatch.setattr(module, 'replay_segment_reference', verify)
    checked = amounts('2025年特高壓電纜營收27.04億元。', data)[0]
    assert checked['status'] == 'verified'
    assert 'earnings_call.tewc_conference_receipt' in checked['matched_path']
    assert data == before


def test_invalid_existing_chain_is_not_a_body_text_fallback(monkeypatch):
    from data_fetch.market_sources import tewc_segment_reference as module
    data = source(); data.pop('official_segment_reference')
    data['earnings_call'] = {'tewc_conference_receipt': {}, 'transcript_excerpt': '2025特高壓27.04億元'}
    monkeypatch.setattr(module, 'replay_segment_reference', lambda *args: {'status': 'unverified'})
    assert amounts('2025年特高壓電纜營收27.04億元。', data)[0]['status'] == 'unverifiable'


@pytest.mark.parametrize('scope', ['合併財報產品營收', '經查核產品營收', '個別財報產品營收', 'Audited consolidated product revenue'])
@pytest.mark.parametrize('template', ['## {}\n', '{}：\n- '])
def test_presentation_product_cell_does_not_certify_parent_or_heading_audit_scope(replay, scope, template):
    text = template.format(scope) + '2025年特高壓電纜營收27.04億元。'
    assert all(c['status'] != 'verified' for c in amounts(text))
