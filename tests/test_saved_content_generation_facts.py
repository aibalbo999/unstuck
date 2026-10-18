"""Public boundary checks. Original private-data replay cases remain local."""
import pytest
from financial_tools import build_financial_tool_context

def test_display_conversions_do_not_convert_eps_shares_or_create_missing_fcf():
    data = {'ticker': 'TEST.TW', 'current_price': 10, 'eps_ttm_raw': 1.2, 'shares_outstanding_raw': 1000}
    tool = build_financial_tool_context(data)
    assert not any((row['field'] in {'eps', 'shares_raw', 'free_cash_flow_raw'} for row in tool['money_display_receipts']))

@pytest.mark.parametrize('mode,agent', [('v1', 1), ('v2', 14), ('v3', 19), ('v4', 24)])
def test_money_receipts_reach_actual_prompt_wire_for_each_mode_without_changing_mode_purpose(mode, agent):
    from agent_runtime.prompting import build_prompt
    data = {'ticker': 'TEST.TW', 'company_name': 'Test', 'current_price': 26, 'free_cash_flow_raw': -25623500}
    context = {'data': data, 'pipeline_id': mode, 'analyses': {}, 'structured_outputs': {}}
    prompt = build_prompt(agent, data, context)
    assert 'money_display_receipts' in prompt and '-0.256235' in prompt
    if mode != 'v4':
        assert '逐引用價格輸入收據' not in prompt and '同日同價格基準的可重算相對位置' not in prompt

def test_real_company_amount_on_same_line_is_still_checked_with_unit_definition():
    from evidence_exit_gate import evaluate_report_evidence
    markdown = '歷史營收、淨利等資料單位為 Billion TWD (10億台幣)；2025年淨利為10億元。'
    source = {'data': {'financial_currency': 'TWD', 'years': ['2025'], 'net_income_history': [0.1]}}
    result = evaluate_report_evidence(markdown, source)
    assert result['failed_count'] >= 1 and result['verdict'] == 'rejected'
    assert any((row.get('financial_metric') == '淨利' and row.get('financial_actual') for row in result['sampled_claims']))
