"""Amount display instructions never rescale canonical inputs or per-share prices."""
import copy
import json

import pytest

from prompt_builder import format_data_for_prompt
from agent_runtime.prompting import build_prompt
from google_prompt_safety import sanitize_google_prompt


@pytest.mark.parametrize('options', [{}, {'compact': True}, {'compact_json': True}, {'dense': True},
                                      {'role_scoped': True}])
def test_prompt_explains_chinese_amount_scale_and_preserves_canonical_data(options):
    data = {'ticker': 'TEST.TW', 'company_name': '測試公司', '_prompt_agent_num': 19,
            'years': ['2025'], 'revenue_history': [2.97], 'net_income_history': [1.63],
            'free_cash_flow_raw': -25_623_500, 'current_price': 26, 'eps_ttm_raw': 1.11}
    before = copy.deepcopy(data)
    text = format_data_for_prompt(data, **options)
    payload = json.JSONDecoder().raw_decode(text.split('【財務資料 JSON】\n', 1)[1])[0]
    units = payload['unit_contract']
    assert units['money'] == 'billion_twd'
    assert units['money_to_yi_twd'] == 10
    assert '十億新臺幣' in units['money_display_zh']
    assert '不可只把 billion_twd 改標為億元' in text
    assert '不適用每股價格、EPS、百分比或股數' in text
    assert payload['market_data']['current_price_twd'] == 26
    assert data == before


def test_final_agent_wire_includes_scale_explanation_without_changing_source():
    data = {'ticker': 'TEST.TW', 'company_name': '測試公司', 'years': ['2025'],
            'revenue_history': [2.97], 'net_income_history': [1.63], 'free_cash_flow_raw': -25_623_500}
    context = {'data': data, 'pipeline_id': 'v3', 'analyses': {}, 'structured_outputs': {}}
    text = sanitize_google_prompt(build_prompt(19, data, context))
    assert 'money_to_yi_twd' in text and '十億新臺幣' in text
    assert '不可只把 billion_twd 改標為億元' in text
    assert '來源期間' in text
