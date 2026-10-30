"""Current FCF arithmetic must not borrow a preceding annual ratio's period."""
import pytest

from evidence_exit_gate import evaluate_report_evidence


def source():
    return {'ticker': '1623.TW', 'company_name': '大東電', 'financial_currency': 'TWD',
            'years': ['2024', '2025'], 'fcf_history': [0.08, -0.23],
            'free_cash_flow_raw': -461412000}


def claim(text, patch=None):
    result = evaluate_report_evidence(text, {'pipeline': 'v1', 'data': {**source(), **(patch or {})}})
    return [item for item in result['sampled_claims'] if item.get('financial_metric') in {'自由現金流', 'FCF'}][-1]


@pytest.mark.parametrize('text', [
    '2025年FCF轉換率為-28.05%，且即期自由現金流為-0.4614 billion_twd（淨流出約4.61億元）。',
    '2025年FCF轉換率為-28.05%，即期FCF缺口達4.61億元。',
    '即期FCF為-4.61億元。',
    '即期自由現金流淨流出4.61億元。',
])
def test_current_fcf_arithmetic_keeps_the_reporting_period_unverified(text):
    item = claim(text)
    assert item['status'] == 'unverifiable'
    assert item['matched_path'] == 'data.free_cash_flow_raw'
    assert item['financial_arithmetic_consistent'] is True
    assert item['financial_period_verified'] is False
    assert item['independent_primary_source_verified'] is False
    assert item['reported_value_raw_twd'] < 0


@pytest.mark.parametrize('value', ['-0.4614億元', '4.61億元', '-46.14億元', '0億元'])
def test_current_fcf_real_sign_and_scale_errors_still_fail(value):
    item = claim(f'2025年FCF轉換率為-28.05%，即期FCF為{value}。')
    assert item['status'] == 'mismatch'
    assert item['matched_path'] == 'data.free_cash_flow_raw'
    assert item['financial_arithmetic_consistent'] is False
    assert item['financial_period_verified'] is False


@pytest.mark.parametrize('text', [
    '即期FCF缺口達+4.61億元。',
    '即期FCF缺口達46.14億元。',
])
def test_deficit_word_cannot_erase_an_explicit_sign_or_scale_error(text):
    assert claim(text)['status'] == 'mismatch'


@pytest.mark.parametrize('text', [
    '2025年即期FCF為-4.61億元。',
    '即期TTM FCF為-4.61億元。',
    '截至2025年9月即期FCF為-4.61億元。',
    '同業即期FCF為-4.61億元。',
    '華通即期FCF為-4.61億元。',
    '同業2025年FCF轉換率-28.05%，即期FCF為-4.61億元。',
    '華通2025年FCF轉換率-28.05%，即期FCF為-4.61億元。',
    '## 2025年年度資料\n即期FCF為-4.61億元。',
    '即期FCF為-4.61億美元。',
    '以下金額均為美元，2025年FCF轉換率為-28.05%，即期FCF為-4.61億元。',
    '華通資料如下，2025年FCF轉換率為-28.05%，即期FCF為-4.61億元。',
    '截至2025年9月，本公司即期FCF為-4.61億元。',
    '2025年年度資料如下，本公司即期FCF為-4.61億元。',
    '2025年FCF資料如下，本公司即期FCF為-4.61億元。',
])
def test_current_label_never_fabricates_period_issuer_or_currency(text):
    item = claim(text)
    assert item['status'] == 'unverifiable'
    assert not item['matched_path']


@pytest.mark.parametrize('patch', [
    {'financial_currency': 'USD'}, {'financial_currency': None},
    {'free_cash_flow_raw': None}, {'free_cash_flow_raw': True},
    {'free_cash_flow_raw': float('nan')}, {'free_cash_flow_raw': '461412000'},
])
def test_missing_current_source_never_borrows_annual_history(patch):
    item = claim('2025年FCF轉換率為-28.05%，即期FCF為-2.3億元。', patch)
    assert item['status'] == 'unverifiable'
    assert not item['matched_path']


def test_explicit_annual_fcf_still_uses_annual_history():
    item = claim('2025年FCF為-2.3億元。')
    assert item['status'] == 'verified'
    assert item['matched_path'] == 'data.fcf_history[1]'
    assert claim('2025年FCF為-4.61億元。')['status'] == 'mismatch'


def test_latest_snapshot_timestamp_cannot_certify_the_current_source_period():
    item = claim('即期FCF為-4.61億元。', {'fetched_at': '2026-10-23T15:00:00+08:00'})
    assert item['status'] == 'unverifiable'
    assert item['financial_period_verified'] is False


def test_deficit_direction_does_not_leave_an_extra_positive_claim():
    result = evaluate_report_evidence('2025年FCF轉換率為-28.05%，即期FCF缺口達4.61億元。',
                                     {'pipeline': 'v1', 'data': source()})
    amounts = [item for item in result['sampled_claims'] if item.get('financial_metric') == 'FCF']
    assert len(amounts) == 1
    assert result['failed_count'] == 0
    assert amounts[0]['reported_value'] == -4.61
