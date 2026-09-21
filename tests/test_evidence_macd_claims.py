"""Real 2033 MACD evidence regression and conservative semantic boundaries."""
import pytest
from evidence_exit_gate import evaluate_report_evidence

REAL_LINE = '- **MACD 指標**：MACD 柱狀體維持正值（macd: 2.87, macd_signal: 2.32, histogram: 0.56），多方動能持續延續。'


def snapshot(**changes):
    return {'data': {'technical_indicators': {
        'as_of': '2026-09-21', 'source': 'yfinance 5y history', 'availability': 'available',
        'missing_indicators': [], 'macd': 2.87231687, 'macd_signal': 2.31690068,
        'macd_histogram': 0.55541619, **changes}, 'current_price': 2.87}}


def claims(text=REAL_LINE, **changes):
    return evaluate_report_evidence(text, snapshot(**changes), sample_ratio=1, max_sample=100)['sampled_claims']


def test_real_macd_each_explicit_assignment_maps_to_its_exact_field():
    result = claims()
    assert len(result) == 3
    assert [r['matched_path'] for r in result] == [f'data.technical_indicators.{k}' for k in ('macd', 'macd_signal', 'macd_histogram')]
    assert all(r['status'] == 'verified' and r['candidate_count'] == 1 for r in result)


@pytest.mark.parametrize('field', ['macd', 'macd_signal', 'macd_histogram'])
def test_wrong_value_cannot_borrow_other_equal_macd_field(field):
    result = claims(**{field: 9.5})
    assert result[['macd', 'macd_signal', 'macd_histogram'].index(field)]['status'] == 'mismatch'


def test_swapped_macd_and_histogram_values_cannot_cross_match():
    result = claims(macd=0.55541619, macd_histogram=2.87231687)
    assert result[0]['status'] == result[2]['status'] == 'mismatch'
    assert result[0]['candidate_count'] == result[2]['candidate_count'] == 1


@pytest.mark.parametrize('number', [0, -0.5])
def test_macd_signed_or_zero_observations_are_valid(number):
    assert claims(f'macd: {number}', macd=number)[0]['status'] == 'verified'


@pytest.mark.parametrize('changes', [
    {'source': None}, {'source': 'unknown'}, {'as_of': None}, {'as_of': '2026-02-30'},
    {'availability': 'unavailable'}, {'macd': None}, {'macd': True}, {'macd': float('nan')},
    {'missing_indicators': ['macd']},
])
def test_missing_source_or_scalar_cannot_use_unvalidated_macd(changes):
    assert claims('macd: 2.87', **changes)[0]['status'] == 'unverifiable'


@pytest.mark.parametrize('text', [
    'macd: 2.87%', 'macd: 2.87張', '2026-09-20 macd: 2.87', '9/20 macd: 2.87',
    '昨日 macd: 2.87', '預估 macd: 2.87', '新聞報導 macd: 2.87',
    'macd: 2.87, macd: 9.5', 'macd: 2.87, macd: N/A',
    'MACD histogram: 2.87', 'MACD 指標: 2.87',
])
def test_ambiguous_wrong_basis_or_units_do_not_verify(text):
    assert all(r['status'] != 'verified' for r in claims(text))


def test_same_observation_date_and_explicit_histogram_alias():
    assert claims('2026-09-21 macd_histogram: 0.56')[0]['status'] == 'verified'


def test_full_line_duplicate_is_not_hidden_by_display_excerpt():
    text = 'macd: 2.87 ' + ' ' * 170 + ', macd: 9.5'
    assert all(r['status'] == 'unverifiable' for r in claims(text))
