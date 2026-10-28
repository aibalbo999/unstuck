from copy import deepcopy
import json

import pytest

from prompt_builder import format_data_for_prompt


@pytest.mark.parametrize('compact', [False, True])
def test_same_digits_and_annual_balances_do_not_certify_quote_ratio(compact):
    data = {
        'ticker': '1623.TW', 'company_name': '大東電', 'financial_currency': 'TWD',
        'debt_to_equity': '70.65%', 'total_debt_raw': 2_898_373_120,
        'total_equity_history': [4.102306], 'years': ['2026'],
        'free_cash_flow_raw': -461_411_616,
        'debt_to_equity_basis': {'definition_status': 'verified', 'period_end': '2026-06-30'},
    }
    before = deepcopy(data)
    text = format_data_for_prompt(data, compact=compact)
    payload = json.loads(text.split('【財務資料 JSON】\n', 1)[1].split('\n\n【使用規則】', 1)[0])
    ratio = payload['balance_sheet']['debt_to_equity_basis']
    assert ratio['definition_status'] == ratio['period_status'] == 'unverified'
    assert ratio['numerator_twd'] is None and ratio['denominator_twd'] is None
    assert ratio['period_end'] is None
    assert payload['balance_sheet']['debt_to_equity_pct'] == 70.65
    assert payload['cash_flow']['free_cash_flow_basis']['period_status'] == 'unverified'
    assert '不得自行解釋成總負債／股東權益' in text
    assert '不得改稱 TTM' in text
    assert data == before
