"""Bounded observed envelopes and immediately cited annual profit endpoints."""
import copy
import hashlib
import json

import pytest

from evidence_financial_amounts import check_financial_amount, extract_financial_amounts


def data():
    return {'ticker': '1623.TW', 'company_name': '大東電', 'financial_currency': 'TWD',
            'years': ['2022', '2023', '2024', '2025'], 'net_income_history': [.09, .41, .73, .82],
            'recent_monthly_revenue': [f'2026年{month}月: NT${value}億' for month, value in
                                       enumerate(['4.77', '3.56', '6.03', '6.19', '4.82', '5.19'], 4)]}


def checked(text, source=None):
    snapshot = {'data': data() if source is None else source}
    return [check_financial_amount(claim, snapshot, 1) for claim in extract_financial_amounts(text, [])]


RANGE = '本公司2026年近6個月單月營收在3.56億至6.19億元區間波動。'
PROFIT = '淨利由0.09十億新臺幣（0.9億元）增長至0.82十億新臺幣（8.2億元）。（來源：history.rows；2022-2025年歷史損益表）'


def test_saved_six_month_envelope_checks_both_bounds():
    claims = checked(RANGE)
    assert len(claims) == 2 and all(c['status'] == 'verified' for c in claims)
    assert [c['financial_range_side'] for c in claims] == ['lower', 'upper']
    assert all(c['financial_period'] == '2026-04..2026-09' for c in claims)
    assert all(c['financial_latest_window_verified'] is False for c in claims)
    assert all(c['independent_primary_source_verified'] is False for c in claims)
    assert all(c['verification_scope'] == 'snapshot_monthly_window_envelope_consistency' for c in claims)


@pytest.mark.parametrize('lower,upper,statuses', [
    ('3.00', '7.00', ['verified', 'verified']),
    ('3.57', '6.19', ['mismatch', 'verified']),
    ('3.56', '6.18', ['verified', 'mismatch']),
    ('3.58', '6.17', ['mismatch', 'mismatch']),
])
def test_envelope_is_containment_not_forced_extrema(lower, upper, statuses):
    claims = checked(RANGE.replace('3.56', lower).replace('6.19', upper))
    assert len(claims) == 2
    assert [c['status'] for c in claims] == statuses


def test_parenthetical_range_conversions_must_match_their_own_bound():
    text = RANGE.replace('3.56億', '3.00億（30百萬元）').replace('6.19億元', '7.00億元（700百萬元）')
    claims = checked(text)
    assert len(claims) == 4
    assert [c['status'] for c in claims] == ['verified', 'mismatch', 'verified', 'verified']


def test_range_alias_repair_uses_its_primary_bound_and_converges():
    from financial_money_claims import financial_money_claim_issues
    wrong = RANGE.replace('3.56億', '3.00億（30百萬元）')
    alias = checked(wrong)[1]
    assert alias['status'] == 'mismatch'
    assert alias['expected_value_raw_twd'] == 300000000
    assert alias['matched_value'] == 300
    assert alias['financial_range_comparison_reference'] == 'reported_range_primary'
    assert alias['source_value'] == 3.56
    assert alias['matched_path'] == 'data.recent_monthly_revenue[1]'
    assert alias['financial_range_observed_extreme_raw_twd'] == 356000000
    issues = financial_money_claim_issues(wrong, data())
    assert len(issues) == 1 and '正確換算為3億' in issues[0]
    assert '正確換算為3.56億' not in issues[0]
    corrected = wrong.replace('30百萬元', '300百萬元')
    assert all(c['status'] == 'verified' for c in checked(corrected))
    assert financial_money_claim_issues(corrected, data()) == []


@pytest.mark.parametrize('mutation', [
    lambda rows: rows[:-1],
    lambda rows: rows + [rows[-1]],
    lambda rows: rows[:-1] + [rows[0]],
    lambda rows: [rows[0].replace('2026年4月', '2025年12月'), *rows[1:]],
    lambda rows: [rows[0].replace('2026年4月', '2026年3月'), *rows[1:]],
    lambda rows: [rows[0].replace('NT$', 'US$'), *rows[1:]],
    lambda rows: [rows[0].replace('4.77', '9' * 40), *rows[1:]],
])
def test_incomplete_duplicate_cross_year_or_untyped_source_window_is_unknown(mutation):
    source = data(); source['recent_monthly_revenue'] = mutation(source['recent_monthly_revenue'])
    claims = checked(RANGE, source)
    assert len(claims) == 2
    assert all(c['status'] == 'unverifiable' and c['candidate_count'] == 0 for c in claims)


@pytest.mark.parametrize('text', [
    RANGE.replace('本公司', '同業大亞'), RANGE.replace('本公司', '未知公司'),
    '同業大亞：\n- ' + RANGE.replace('本公司', ''),
    '未知公司：\n- ' + RANGE.replace('本公司', ''),
    '- 單位為美元：\n  - ' + RANGE,
    '# 預測情境\n' + RANGE, '假設' + RANGE,
    RANGE.replace('2026年', '2025年'), RANGE.replace('近6個月', '近5個月'),
])
def test_range_cannot_borrow_owner_currency_forecast_or_period(text):
    claims = checked(text)
    assert claims and all(c['status'] == 'unverifiable' for c in claims)


def test_range_extra_alternative_stays_in_denominator():
    claims = checked(RANGE.replace('億元區間', '億元或10億元區間'))
    assert len(claims) == 3
    assert all(c['status'] == 'unverifiable' for c in claims)


@pytest.mark.parametrize('separator', ['，或', '，及', '，與', '，和', ', or', ', 或', '， 及 '])
@pytest.mark.parametrize('kind', ['range', 'profit_before_citation', 'profit_after_citation'])
def test_composite_extra_separator_preserves_every_amount_as_unknown(separator, kind):
    if kind == 'range':
        text = RANGE.replace('億元區間', '億元' + separator + '10億元區間')
        expected = 3
    elif kind == 'profit_before_citation':
        text = '本公司' + PROFIT.replace('。（來源', separator + '9.2億元。（來源')
        expected = 5
    else:
        text = '本公司' + PROFIT + separator + '9.2億元。'
        expected = 5
    claims = checked(text)
    assert len(claims) == expected
    assert all(c['status'] == 'unverifiable' for c in claims)


@pytest.mark.parametrize('text', [RANGE.replace('3.56', '9' * 400), RANGE.replace('6.19', '9' * 400),
                                  PROFIT.replace('0.82', '9' * 400)])
def test_new_series_invalid_amounts_preserve_denominator_and_json_safety(text):
    claims = checked(text)
    assert len(claims) == (4 if '淨利' in text else 2)
    assert all(c['status'] == 'unverifiable' for c in claims)
    assert any(c.get('financial_series_invalid_number') for c in claims)
    json.dumps(claims, allow_nan=False)


def test_monthly_envelope_mismatch_diagnostic_stays_serializable():
    from financial_money_claims import financial_money_claim_issues
    issues = financial_money_claim_issues(RANGE.replace('3.56', '4.00'), data())
    assert issues
    json.dumps(issues, allow_nan=False)


@pytest.mark.parametrize('text', [
    '本公司' + PROFIT.replace('0.82十億', '0.92十億'),
    '本公司2022至2025年淨利由0.09B成長至0.92B。',
])
def test_early_repair_diagnostics_include_the_second_series_endpoint(text):
    from financial_money_claims import financial_money_claim_issues
    issues = financial_money_claim_issues(text, data())
    assert any('2025' in issue and 'net_income_history[3]' in issue for issue in issues)


def test_formatted_monthly_source_does_not_crash_unit_error_diagnostic():
    from financial_money_claims import financial_money_claim_issues
    text = '本公司2026年4月至9月單月營收分別為4.77億、356億、6.03億、6.19億、4.82億與5.19億元。'
    issues = financial_money_claim_issues(text, data())
    assert issues
    json.dumps(issues, allow_nan=False)


def test_valid_wider_range_and_unknown_peer_do_not_generate_repair_errors():
    from financial_money_claims import financial_money_claim_issues
    assert financial_money_claim_issues(RANGE.replace('3.56', '3.00').replace('6.19', '7.00'), data()) == []
    assert financial_money_claim_issues(RANGE.replace('本公司', '同業大亞').replace('3.56', '4.00'), data()) == []


def test_postfix_citation_binds_four_profit_amounts_by_its_own_years():
    claims = checked('本公司' + PROFIT)
    assert len(claims) == 4
    assert [c['financial_period'] for c in claims] == ['2022', '2022', '2025', '2025']
    assert all(c['status'] == 'verified' for c in claims)
    assert all(c['independent_primary_source_verified'] is False for c in claims)


def test_actual_report_profit_context_never_borrows_ratio_years():
    text = '- **發現**：獲利能力顯著拉升，毛利率由2022年的9.7%提升至2025年的18.6%，營業利益率由6.4%增至15.3%，' + PROFIT
    claims = checked(text)
    assert len(claims) == 4 and all(c['status'] == 'verified' for c in claims)
    # The citation, rather than the ratio, owns the two years.
    changed = checked(text.replace('2022-2025年歷史損益表', '2023-2024年歷史損益表'))
    assert [c['financial_period'] for c in changed] == ['2023', '2023', '2024', '2024']
    assert all(c['status'] == 'mismatch' for c in changed)


@pytest.mark.parametrize('text', [
    '同業大亞' + PROFIT, '未知公司' + PROFIT,
    '同業大亞：\n- ' + PROFIT, '未知公司：\n- ' + PROFIT,
    '- 單位為美元：\n  - 本公司' + PROFIT,
    '# 預測情境\n本公司' + PROFIT, '假設本公司' + PROFIT,
    '本公司2024年' + PROFIT, '本公司TTM' + PROFIT,
    PROFIT.replace('2022-2025', '2025-2022'),
    PROFIT.replace('history.rows', 'peer.history.rows'),
    PROFIT.replace('歷史損益表', '預估損益表'),
    PROFIT.replace('。（來源', '。另一段敘述。（來源'),
    PROFIT.replace('；2022-2025年歷史損益表', ''),
])
def test_profit_citation_never_erases_incompatible_scope(text):
    claims = checked(text)
    assert len(claims) == 4
    assert all(c['status'] == 'unverifiable' for c in claims)


def test_wrong_profit_second_endpoint_and_conversion_are_mismatches():
    claims = checked('本公司' + PROFIT.replace('0.82十億', '0.92十億').replace('8.2億元', '9.2億元'))
    assert [c['status'] for c in claims] == ['verified', 'verified', 'mismatch', 'mismatch']


def test_future_six_yi_threshold_is_still_one_unverifiable_claim():
    claims = checked('可證偽條件：若單月營收連續三個月穩定維持在6億元以上，且單季EPS年增率轉正。')
    assert len(claims) == 1 and claims[0]['status'] == 'unverifiable'
    assert claims[0]['reported_value'] == 6


def test_refresh_and_damaged_original_packet_do_not_supply_a_new_month_window():
    from evidence_exit_gate import evaluate_report_evidence
    from report_analysis_evidence import capture_analysis_evidence
    original = data()
    original['analysis_input_hash'] = hashlib.sha256(json.dumps(original, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    original['analysis_input_cutoff'] = '2026-10-22T22:37:35.821148+00:00'
    packet = capture_analysis_evidence({'data': original})
    snapshot = {'data': data(), 'analysis_evidence': packet, 'refreshed_without_analysis_rerun': True}
    valid = evaluate_report_evidence(RANGE, snapshot)['sampled_claims']
    assert len(valid) == 2 and all(c['status'] == 'verified' for c in valid)
    assert all(c['matched_path'].startswith('analysis_evidence.sections.analysis_input.data.') for c in valid)
    damaged = copy.deepcopy(snapshot)
    damaged['analysis_evidence']['sections']['analysis_input']['data']['recent_monthly_revenue'][0] = '2026年4月: NT$0億'
    claims = evaluate_report_evidence(RANGE, damaged)['sampled_claims']
    assert len(claims) == 2 and all(c['status'] == 'unverifiable' for c in claims)
