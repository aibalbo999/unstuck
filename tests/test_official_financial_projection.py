"""New official analysis inputs never retroactively date saved quote scalars."""
from copy import deepcopy

import pytest

from test_tewc_quarterly_reference import reference


def input_data():
    return {'ticker': '1623.TW', 'company_name': '大東電', 'financial_currency': 'TWD',
            'free_cash_flow_raw': -461411616, 'operating_cash_flow_raw': -189755008,
            'free_cash_flow': 'NT$-4.61億 (-0.46B)', 'operating_cash_flow': 'NT$-1.90億 (-0.19B)',
            'total_debt_raw': 2898373120, 'total_cash_raw': 1234000,
            'debt_to_equity': '70.65%', 'net_income_ttm_raw': 860640000,
            'net_income_ttm_source': 'trailingEPS_times_shares', 'unrelated': {'keep': [1, 2]}}


def projected():
    from official_financial_projection import project_official_financials
    return project_official_financials(input_data(), reference())


def test_projection_selects_only_cashflows_and_preserves_original_quote():
    from official_financial_projection import project_official_financials, read_official_financial_projection
    original = input_data(); before = deepcopy(original); source = reference(); source_before = deepcopy(source)
    data = project_official_financials(original, source)
    assert original == before and source == source_before
    assert data['free_cash_flow_raw'] == 8850000
    assert data['operating_cash_flow_raw'] == 12000000
    assert data['free_cash_flow'] == 'NT$0.09億 (0.01B)'
    assert data['operating_cash_flow'] == 'NT$0.12億 (0.01B)'
    for key in ('total_debt_raw', 'total_cash_raw', 'debt_to_equity', 'net_income_ttm_raw', 'unrelated'):
        assert data[key] == original[key]
    assert data['original_quote_financials']['values']['free_cash_flow_raw'] == -461411616
    assert data['original_quote_financials']['values']['free_cash_flow'] == 'NT$-4.61億 (-0.46B)'
    checked = read_official_financial_projection(data)
    assert checked['status'] == 'verified_official_analysis_projection'
    facts = checked['facts']
    assert facts['report_scope'] == 'individual'
    assert (facts['period_start'], facts['period_end']) == ('2025-07-01', '2026-06-30')
    assert facts['cashflows']['ttm']['ppe_purchase'] == -2250000
    assert facts['cashflows']['ttm']['intangible_purchase'] == -900000
    assert facts['raw_scalar_period_verified'] is False
    assert facts['historical_pit_verified'] is False
    assert facts['industrial_dcf_applicable'] is False
    assert 'raw_response_path' not in str(facts)


@pytest.mark.parametrize('field', ['analysis_input_hash', 'analysis_input_cutoff', '_analysis_input_evidence'])
def test_projection_cannot_mutate_a_frozen_analysis(field):
    from official_financial_projection import project_official_financials
    data = input_data(); data[field] = 'frozen'
    with pytest.raises(ValueError, match='frozen'):
        project_official_financials(data, reference())


@pytest.mark.parametrize('damage', ['issuer', 'currency', 'source', 'selected_fcf', 'selected_ocf',
                                  'facts', 'original', 'fingerprint', 'path', 'fcf_display', 'ocf_display'])
def test_replay_does_not_trust_saved_flags_or_selected_values(damage):
    from official_financial_projection import read_official_financial_projection
    data = projected(); value = data['official_financial_projection']
    if damage == 'issuer': data['ticker'] = '2330.TW'
    elif damage == 'currency': data['financial_currency'] = 'USD'
    elif damage == 'source': value['reference']['quarterly_document']['sha256'] = '0' * 64
    elif damage == 'selected_fcf': data['free_cash_flow_raw'] = -461411616
    elif damage == 'selected_ocf': data['operating_cash_flow_raw'] += 1
    elif damage == 'facts': value['facts']['period_start'] = '2026-01-01'
    elif damage == 'original': data['original_quote_financials']['values']['free_cash_flow_raw'] = 8850000
    elif damage == 'fingerprint': value['sha256'] = '0' * 64
    elif damage == 'fcf_display': data['free_cash_flow'] = 'NT$-4.61億 (-0.46B)'
    elif damage == 'ocf_display': data['operating_cash_flow'] = 'unverified text'
    else: value['reference']['quarterly_document']['raw_receipt']['raw_response_path'] = '/tmp/secret-original.gz'
    assert read_official_financial_projection(data) is None


def test_projection_rejects_unverified_source_without_partial_mutation():
    from official_financial_projection import project_official_financials
    data = input_data(); before = deepcopy(data); source = reference()
    source['quarterly_document']['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='unverified'):
        project_official_financials(data, source)
    assert data == before


def test_official_basis_and_raw_quote_basis_stay_distinct():
    from financial_fact_binding import financial_basis, basis_text, debt_ratio_basis
    data = projected(); basis = financial_basis(data)
    fact = basis['facts']['free_cash_flow_raw']
    assert fact['amount_twd'] == '8850000' and fact['period_status'] == 'verified'
    assert fact['period_start'] == '2025-07-01' and fact['period_end'] == '2026-06-30'
    assert fact['report_scope'] == 'individual' and fact['raw_scalar_period_verified'] is False
    assert basis['facts']['net_income_ttm_raw']['period_status'] == 'unverified'
    assert '2025-07-01' in basis_text(basis)
    debt = debt_ratio_basis(data)
    assert debt['numerator_twd'] == 2800000 and debt['denominator_twd'] == 6000000
    assert debt['period_end'] == '2026-06-30'
    assert debt['raw_scalar_definition_verified'] is False
    assert debt['raw_scalar_period_verified'] is False
    assert debt['source_path'] != 'data.debt_to_equity'
    assert debt['ratios']['debt_including_leases_to_equity_pct'] != debt['ratios']['total_liabilities_to_equity_pct']
    assert debt_ratio_basis()['definition_status'] == 'unverified'
    assert financial_basis(input_data())['facts']['free_cash_flow_raw']['period_status'] == 'unverified'


def test_official_basis_fails_closed_after_receipt_damage():
    from financial_fact_binding import financial_basis, debt_ratio_basis
    data = projected()
    data['official_financial_projection']['reference']['annual_document']['sha256'] = '0' * 64
    assert financial_basis(data)['facts']['free_cash_flow_raw']['period_status'] == 'unverified'
    assert debt_ratio_basis(data)['definition_status'] == 'unverified'


def test_only_exact_official_period_amount_and_owner_is_admitted():
    from financial_fact_binding import period_assertion_issues
    data = projected()
    text = '本公司官方個別財報 TTM 自由現金流為 0.0885 億元，涵蓋 2025-07-01 至 2026-06-30，期間已核實。'
    assert not period_assertion_issues(text, data)
    assert period_assertion_issues(text)
    for wrong in (text.replace('2025-07-01', '2025-01-01'), text.replace('0.0885', '-4.61411616'),
                  text.replace('本公司', '台積電'), text.replace('個別', '合併'),
                  text.replace('億元', '億美元')):
        assert period_assertion_issues(wrong, data), wrong


def test_legacy_period_guards_remain_and_no_cross_sentence_borrowing():
    from financial_fact_binding import period_assertion_issues
    data = projected()
    assert period_assertion_issues('本公司 TTM 自由現金流的期間已核實。', data)
    text = ('本公司官方個別財報 TTM 自由現金流為 0.0885 億元，涵蓋 2025-07-01 至 2026-06-30。'
            '舊 quote 即期自由現金流為 -4.61411616 億元，期間已核實。')
    assert period_assertion_issues(text, data)


def test_repeated_projection_does_not_overwrite_original_provenance():
    from official_financial_projection import project_official_financials
    data = projected()
    with pytest.raises(ValueError, match='existing'):
        project_official_financials(data, reference())


def test_excessive_numeric_precision_fails_closed_without_crashing_prose_guard():
    from financial_fact_binding import period_assertion_issues
    text = ('本公司官方個別財報 TTM 自由現金流為 0.' + '0' * 1000 + '1 億元，'
            '涵蓋 2025-07-01 至 2026-06-30，期間已核實。')
    assert period_assertion_issues(text, projected())


@pytest.mark.parametrize('replacement', ['future', 'expected', 'other_issuer', 'euro', 'jpy',
                                       'gbp', 'outflow', 'trailing_currency', 'wrong_conversion'])
def test_complete_official_period_sentence_cannot_borrow_a_valid_prefix(replacement):
    from financial_fact_binding import period_assertion_issues
    from official_financial_projection import official_fcf_period_statement_matches
    text = '本公司官方個別財報TTM自由現金流為0.0885億元，涵蓋2025-07-01至2026-06-30，期間已核實'
    if replacement == 'future': text = text.replace('涵蓋', '未來涵蓋')
    elif replacement == 'expected': text = text.replace('涵蓋', '預期涵蓋')
    elif replacement == 'other_issuer': text += '，此為台積電資料'
    elif replacement == 'euro': text = text.replace('億元', '億歐元')
    elif replacement == 'jpy': text = text.replace('億元', '億日圓')
    elif replacement == 'gbp': text = text.replace('億元', '億英鎊')
    elif replacement == 'outflow': text = text.replace('億元', '億元（淨流出）')
    elif replacement == 'trailing_currency': text += '，本段均以歐元計價'
    else: text += '，原始金額 8850000 TWD，等於 8.85 billion_twd'
    data = projected()
    assert official_fcf_period_statement_matches(text, data) is False
    assert period_assertion_issues(text, data)


def test_exact_generated_basis_and_consistent_direction_still_pass_period_guard():
    from financial_fact_binding import basis_text, financial_basis, period_assertion_issues
    from official_financial_projection import official_fcf_period_statement_matches
    data = projected()
    line = next(line for line in basis_text(financial_basis(data)).splitlines() if '官方個別財報' in line)
    assert official_fcf_period_statement_matches(line, data)
    assert not period_assertion_issues(line, data)
    assert not official_fcf_period_statement_matches(line.replace('8850000 TWD', '8850001 TWD'), data)
    text = '本公司官方個別財報TTM自由現金流為0.0885億元（淨流入），涵蓋2025-07-01至2026-06-30，期間已核實'
    assert official_fcf_period_statement_matches(text, data)
