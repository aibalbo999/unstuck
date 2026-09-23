"""Bound actual financial amounts to the same metric, period, currency and unit."""
import copy
import json
import os
from pathlib import Path

import pytest

from financial_output_validator import validate_analysis_output


def data():
    return {'ticker': 'TEST.TW', 'financial_currency': 'TWD', 'currency': 'TWD',
            'years': ['2024', '2025'], 'revenue_history': [0.63, 2.97],
            'net_income_history': [0.27, 1.63], 'fcf_history': [0.31, 0.99],
            'free_cash_flow_raw': -25623500.0}


def issues(text, source=None, agent=19):
    return [x for x in validate_analysis_output(agent, text, data() if source is None else source)
            if x.startswith('財務金額單位紅線')]


# Verbatim sentences from 5314's accepted 2026-09-23 22:11:52 candidate.
ACTUAL = ('對照財務現實，雖然2025年營收達2.97億新台幣、淨利達1.63億新台幣，'
          '但股價對應之PB高達17.5倍。\n'
          '根據財務資料與計算工具結果，最新TTM自由現金流為負數（-0.0256億新台幣），'
          '顯示帳面獲利未能有效轉化為實質現金流入。')


@pytest.mark.parametrize('agent', [17, 18, 19])
def test_live_prose_money_errors_are_rejected_with_same_period_source(agent):
    result = issues(ACTUAL, agent=agent)
    assert len(result) == 3
    assert any('data.revenue_history[1]' in x and '29.7億' in x for x in result)
    assert any('data.net_income_history[1]' in x and '16.3億' in x for x in result)
    assert any('data.free_cash_flow_raw' in x and '-0.256235億' in x for x in result)
    assert all('原值' in x and '來源' in x for x in result)


@pytest.mark.parametrize('text', [
    '2025年營收29.7億元、淨利16.3億新台幣。最新TTM自由現金流為-0.2562億元。',
    '2025年營收2.97十億元，淨利1.63B TWD。最新TTM FCF為-0.0256 billion TWD。',
    '2025年營收2,970,000,000元，淨利1,630,000,000 TWD。最新TTM自由現金流-25,623,500元。',
    '2024年營收6.3億、淨利2.7億；2025年營收29.7億、淨利16.3億。',
    '2025年營收約30億元；TTM自由現金流約-0.26億元。',
    '最新TTM自由現金流為負數0.256235億新台幣。',
])
def test_correct_units_periods_negative_and_rounding_are_not_rejected(text):
    assert issues(text) == []


@pytest.mark.parametrize('text', [
    '2025年營收297億元。', '2025年營收2970億元。', '2025年營收0.297億元。',
    '2025年淨利0.0163十億元。', 'TTM自由現金流為0.256235億元。',
    '2025年營收2.97億，淨利0億。',
])
def test_scale_sign_and_false_zero_errors_are_not_accepted(text):
    assert issues(text)


@pytest.mark.parametrize('text', [
    '2023年營收2.97億。', '營收2.97億。', '去年營收2.97億。',
    '2025年8月營收2.97億、淨利1.63億。', '2025年Q2營收2.97億。',
    '2025年第一季淨利1.63億。', '2025年上半年營收2.97億。',
    '2025年营收2.97億。',  # Deliberately outside the bounded Traditional Chinese vocabulary.
    '2025年營收年增率2.97%。', '2025年每股淨利1.63元。', '2025年淨利率1.63%。',
    '2025年營收2.97億美元。', '2025年營收USD 2.97B。', '2025年營收2.97億股。',
    '2025年營收2.97。', '2025年營收2.97倍。',
    '2025年自由現金流為0.0256億。', '截至2024年TTM自由現金流-0.0256億。',
    '若2025年營收2.97億，則重新評估。', '預估2025年營收2.97億。',
    '假設2025年淨利1.63億。', '2025年營收目標2.97億。',
    '錯誤示例：「2025年營收2.97億」，不可採用。',
    '「2025年淨利1.63億」是誤寫，正確為16.3億。',
    '2025年營收並非2.97億，而是29.7億。',
    '## 假設情境\n2025年營收2.97億。',
    '2025年營收2.97億/股。', '2025年營收NaN億元。',
])
def test_unsupported_period_units_projections_and_quoted_errors_are_not_false_positives(text):
    assert issues(text) == []


@pytest.mark.parametrize('field,value', [
    ('financial_currency', 'USD'), ('financial_currency', None),
    ('years', ['2025', '2025']), ('years', None),
    ('revenue_history', None), ('revenue_history', [0.63]),
    ('revenue_history', [0.63, None]), ('revenue_history', [0.63, True]),
    ('revenue_history', [0.63, float('nan')]), ('revenue_history', [0.63, float('inf')]),
])
def test_unverifiable_source_never_becomes_fabricated_zero_or_comparable(field, value):
    source = data();source[field] = value
    assert issues('2025年營收2.97億。', source) == []


@pytest.mark.parametrize('value', [None, True, float('nan'), float('inf'), 'unavailable'])
def test_ttm_invalid_raw_is_not_compared(value):
    source = data();source['free_cash_flow_raw'] = value
    assert issues('TTM自由現金流-0.0256億。', source) == []


def test_zero_and_negative_sources_are_valid_and_not_mutated():
    source = data();source['net_income_history'][1] = -1.63;source['free_cash_flow_raw'] = 0
    before = copy.deepcopy(source)
    assert issues('2025年淨利-16.3億。TTM自由現金流0元。', source) == []
    assert issues('2025年淨利16.3億。', source)
    assert source == before


def test_scope_does_not_cross_sentence_or_new_month_and_condition_does_not_hide_next_actual():
    assert issues('2025年營收29.7億。淨利1.63億。') == []
    assert issues('2025年營收29.7億、8月淨利1.63億。') == []
    assert issues('假設2024年營收0.63億。2025年營收2.97億。')


def test_final_audit_rejects_saved_5314_upstream_as_well_as_final_when_available():
    path = os.environ.get('FINANCIAL_MONEY_SNAPSHOT')
    if not path:
        pytest.skip('optional private complete report replay')
    from final_audit import run_final_report_audit
    snapshot = json.loads(Path(path).read_text());ctx = copy.deepcopy(snapshot['rerun_context'])
    ctx['data'] = snapshot['data']
    for field in ['analyses', 'structured_outputs']:
        ctx[field] = {int(k) if str(k).isdigit() else k:v for k,v in ctx[field].items()}
    before = copy.deepcopy(ctx['data'])
    audit = run_final_report_audit(ctx, append_section=False)
    for agent in [17, 18, 19]:
        found = audit['repair_agent_issues'].get(agent, audit['repair_agent_issues'].get(str(agent), []))
        assert any('財務金額單位紅線' in issue for issue in found)
    assert audit['critical'] and ctx['data'] == before


@pytest.mark.parametrize('text', [
    '2022年至2025年營收由0.2億元成長至29.7億元。',
    '2024-2025年營收由6.3億成長至29.7億。',
    '2025年營收、淨利分別為29.7億、16.3億。',
    '2025年淨利、營收依序為16.3億、29.7億。',
    '2025-09-16營收2.97億。',
    '截至2025/12/31淨利1.63億。',
    '2025年營收2.97億是預估，不是年度實績。',
])
def test_ambiguous_comparisons_assignments_and_dated_observations_do_not_borrow_annual(text):
    assert issues(text) == []


def test_actual_amount_before_unrelated_valuation_discussion_is_still_checked():
    assert issues('2025年淨利1.63億元與股價所隱含的估值有落差。')


@pytest.mark.parametrize('unit', ['million_twd', 'unknown', None, {'bad': 'unit'}])
def test_explicit_incompatible_history_unit_is_not_overridden(unit):
    source = data();source['unit_contract'] = {'money': unit}
    assert issues('2025年營收2.97億。', source) == []


@pytest.mark.parametrize('text', [
    '2025年以美元計價營收0.9億元。', '2025年營收0.9億港幣。',
    '2025年營收年增2.97億元。', '2025年淨利減少1.63億元。',
    '2025年前九月營收2.97億。', '2025年累計至8月底營收2.97億。',
])
def test_foreign_change_and_partial_year_amounts_are_outside_annual_scope(text):
    assert issues(text) == []


def test_other_currency_or_change_clause_does_not_hide_separate_actual_amount():
    assert len(issues('2025年營收2.97億元，美元升值帶來風險。')) == 1
    result = issues('2025年營收年增2.97億元，淨利1.63億元。')
    assert len(result) == 1 and 'net_income_history' in result[0]


def test_rounded_history_uncertainty_and_ordinary_difference_are_not_unit_errors():
    source = data();source['revenue_history'][1] = 0.02
    assert issues('2025年營收約2400萬元。', source) == []
    assert issues('2025年營收200萬元。', source)
    assert issues('2025年營收28億元。') == []  # Not a proven unit-scale error.
    source['revenue_history'][1] = 0
    assert issues('2025年營收400萬元。', source) == []  # Rounded zero is not exact zero.


@pytest.mark.parametrize('text', [
    '2025年營收由2.97億元增加至29.7億元。',
    '2025年營收去年2.97億元，今年29.7億元。',
])
def test_comparative_base_or_period_between_metric_and_value_is_not_current_annual(text):
    assert issues(text) == []
