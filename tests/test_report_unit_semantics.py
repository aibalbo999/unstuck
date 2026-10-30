"""Observed mode-C/B errors must reach the shared repair and final-audit gates."""
from copy import deepcopy

import pytest

from financial_output_validator import validate_analysis_output


def flows():
    return {'ticker': '1623.TW', 'institutional_trading': {
        'source': 'FinMind TaiwanStockInstitutionalInvestorsBuySell',
        'latest_date': '2026-10-16', 'lookback_trading_days': 30,
        'total_net_buy_thousand_shares': -155.34,
        'net_buy_thousand_shares_by_category': {
            'foreign': -160.83, 'investment_trust': 0, 'dealer': 5.49}}}


def unit_issues(agent, text, data):
    return [issue for issue in validate_analysis_output(agent, text, data)
            if issue.startswith(('法人', '負債比率口徑紅線'))]


@pytest.mark.parametrize('agent', [1, 7, 14, 15, 16, 18, 19, 23, 24])
@pytest.mark.parametrize('text', [
    '近30個交易日法人合計賣超155.34千張。',
    '外資近30個交易日累計淨賣超160.83千張。',
    '自營商近30個交易日買超5.49千張。',
])
def test_saved_mode_c_unit_corruption_is_blocked_across_modes(agent, text):
    assert unit_issues(agent, text, flows())


@pytest.mark.parametrize('text', [
    '近30個交易日法人合計賣超155.34千股。',
    '外資近30個交易日累計淨賣超160.83張。',
    '外資近30個交易日累計淨賣超0.16083千張。',
    '自營商近30個交易日買超5490股。',
    '若未來外資近30個交易日賣超50千張，才重新評估。',
])
def test_correct_flow_conversion_and_future_threshold_are_preserved(text):
    data = flows(); before = deepcopy(data)
    assert unit_issues(19, text, data) == []
    assert data == before


@pytest.mark.parametrize('agent', [18, 19, 23, 24])
@pytest.mark.parametrize('unit', ['千股（千張）', '千股(千張)', '千股／千張', '千股（160.83千張）'])
def test_alternate_unit_cannot_hide_thousand_fold_corruption(agent, unit):
    assert unit_issues(agent, f'外資近30個交易日累計淨賣超160.83{unit}。', flows())


@pytest.mark.parametrize('unit', ['千股（張）', '千股(張)', '千股（160.83張）', '千股（0.16083千張）', '千股／張'])
def test_equivalent_alternate_units_remain_valid(unit):
    assert unit_issues(19, f'外資近30個交易日累計淨賣超160.83{unit}。', flows()) == []


def test_future_alternate_units_do_not_become_observed_flows():
    assert unit_issues(19, '若外資近30個交易日賣超160.83千股（千張），才重新評估。', flows()) == []


def test_new_cross_mode_amount_comparison_does_not_infer_missing_period():
    # Unknown scope remains unverified; mode D's existing strict gate stays intact.
    text = '外資近5個交易日賣超160.83千張。'
    assert unit_issues(19, text, flows()) == []
    assert unit_issues(23, text, flows())


@pytest.mark.parametrize('agent', [3, 7, 14, 16, 19, 24])
@pytest.mark.parametrize('text', [
    '負債比率高達74.66%，在高利率環境下，財務成本壓抑獲利品質。',
    '負債比率約74.7%。',
    '| 負債比率 | 74.66% |',
    '負債佔資產比率為74.66%。',
])
def test_saved_mode_b_debt_equity_mislabel_is_blocked(agent, text):
    assert unit_issues(agent, text, {'debt_to_equity': '74.66%'})


@pytest.mark.parametrize('text', [
    '負債權益比為74.66%，反映債務相對股東權益的比例。',
    'D/E為74.66%；負債比率尚未提供，不可推算。',
    '若負債比率高於74.66%，應重新評估。',
    '預估負債比率74.66%。',
    '負債比率並非74.66%，而是另一個尚未核實的指標。',
    '錯誤示例：「負債比率74.66%」，不可採用。',
    '「負債比率74.66%」是誤寫，正確名稱為負債權益比。',
    '2025年負債比率74.66%。',
    '負債比率74.66%（2025年）。',
    '同業負債比率74.66%。',
    '負債比率為42.3%。',
])
def test_debt_ratio_check_keeps_correct_names_and_unmatched_scopes(text):
    assert unit_issues(16, text, {'debt_to_equity': '74.66%'}) == []


@pytest.mark.parametrize('value', [None, True, 'N/A', 'NaN%', float('inf'), float('nan')])
def test_unknown_debt_equity_value_is_not_fabricated(value):
    assert unit_issues(16, '負債比率74.66%。', {'debt_to_equity': value}) == []


def test_final_audit_rejects_the_new_defects_before_publication():
    from final_audit import run_final_report_audit
    from report_publication_gate import assert_report_publishable, ReportPublicationBlockedError
    data = flows(); data['debt_to_equity'] = '74.66%'
    result = run_final_report_audit({
        'pipeline_id': 'v3', 'agent_sequence': [18, 19], 'data': data,
        'analyses': {18: '外資近30個交易日賣超160.83千張。', 19: '負債比率74.66%。'},
        'parsed': {}, 'structured_outputs': {},
    }, append_section=False)
    assert any('法人單位／數值紅線' in issue for issue in result['critical'])
    assert any('負債比率口徑紅線' in issue for issue in result['critical'])
    with pytest.raises(ReportPublicationBlockedError):
        assert_report_publishable({'final_audit': result})


def test_all_modes_receive_metric_names_and_flow_unit_guidance():
    from prompt_builder import format_data_for_prompt
    prompt = format_data_for_prompt({'ticker': '6488.TWO', 'debt_to_equity': '74.66%'})
    assert 'debt_to_equity_pct' in prompt
    assert '不得自行解釋成總負債／股東權益' in prompt
    assert '不同期間的權益乘數' in prompt
    assert '1千股=1張' in prompt


def annual_cash_flow():
    from analysis_input_provenance import freeze_analysis_inputs
    data = {'ticker': '6488.TWO', 'company_name': '環球晶', 'currency': 'TWD', 'financial_currency': 'TWD',
            'years': ['2025'], 'fcf_history': [-20.760323], 'unit_contract': {'money': 'billion_twd'}}
    freeze_analysis_inputs(data)
    return data


@pytest.mark.parametrize('prefix', [
    '根據2025年財務數據，最新',
    '- **獲利品質與盈餘含金量檢視**：根據2025年財務數據，最新',
])
def test_real_annual_fcf_error_is_repaired_before_rendering(prefix):
    issues = validate_analysis_output(13, prefix + '自由現金流為-20.76億新臺幣。', annual_cash_flow())
    assert any('財務金額單位紅線' in issue for issue in issues)


@pytest.mark.parametrize('text', [
    '- **獲利品質與盈餘含金量檢視**：根據2025年財務數據，最新自由現金流為-207.60億新臺幣。',
    '同業台積電：根據2025年財務數據，最新自由現金流為-20.76億元。',
    '根據2025年Q2財務數據，最新自由現金流為-20.76億元。',
    '預估2025年自由現金流為-20.76億元。',
])
def test_annual_fcf_scope_and_correct_conversion_are_preserved(text):
    assert not any('財務金額單位紅線' in issue for issue in validate_analysis_output(13, text, annual_cash_flow()))
