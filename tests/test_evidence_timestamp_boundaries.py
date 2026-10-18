"""ISO source timestamps must not create financial claims or hide real ones."""
import pytest
from evidence_exit_gate_claims import extract_numeric_claims
from evidence_exit_gate import evaluate_report_evidence

TIMES = 'Yahoo 2026-10-06T10:06:12.040742+00:00；官方 2026-10-06T10:03:51.883541+00:00'

@pytest.mark.parametrize('text', [TIMES, '- **實際取得時間:** '+TIMES,
    '| 來源 | '+TIMES+' |', '官方 2026-10-06T10:03:51Z；Yahoo 2026-10-06T10:06:12Z'])
def test_multiple_complete_timestamps_are_not_financial_numbers(text):
    assert extract_numeric_claims(text) == []

@pytest.mark.parametrize('text', ['股價：999 元；'+TIMES, TIMES+'；股價：999 元'])
def test_timestamp_does_not_hide_wrong_price(text):
    gate = evaluate_report_evidence(text, {'data': {'current_price': 167.0}})
    assert len(gate['sampled_claims']) == 1
    assert gate['sampled_claims'][0]['status'] == 'mismatch'

def test_timestamp_does_not_hide_wrong_share_quantity():
    gate = evaluate_report_evidence('Foreign：999；'+TIMES,
        {'data': {'institutional_trading': {'net_buy_thousand_shares_by_category': {'foreign': 1.0}}}})
    assert len(gate['sampled_claims']) == 1
    assert gate['sampled_claims'][0]['status'] == 'mismatch'

@pytest.mark.parametrize('date,value,status', [('2026-09-04', 210, 'verified'),
    ('2026-09-03', 210, 'mismatch'), ('2026-09-04', 999, 'mismatch')])
def test_actual_price_date_context_still_selects_exact_bar(date, value, status):
    text = f'第一壓力區：{value} 元（{date} 當日高點）。\n'+TIMES
    snapshot = {'data': {'daily_market_data': {'interval': '1d', 'bars': [
        {'date': '2026-09-04', 'high': 210.0}, {'date': '2026-09-03', 'high': 190.0}]}}}
    gate = evaluate_report_evidence(text, snapshot)
    assert len(gate['sampled_claims']) == 1
    assert gate['sampled_claims'][0]['status'] == status


def test_invalid_calendar_timestamp_is_not_silently_exempted():
    claims = extract_numeric_claims('Yahoo 2026-13-06T10:06:12Z；官方 2026-10-06T10:03:51Z')
    assert len(claims) == 1
    assert claims[0]['reported_value'] == 6.0
