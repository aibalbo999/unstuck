from copy import deepcopy
import json
from pathlib import Path

import pytest

from prompt_builder import format_data_for_prompt


def payload(data, **kwargs):
    text = format_data_for_prompt(data, **kwargs)
    return json.loads(text.split('【財務資料 JSON】\n', 1)[1].split('\n\n【使用規則】', 1)[0]), text


def example():
    return {
        'ticker': '1623.TW', 'company_name': '大東電',
        'years': ['2022', '2023', '2024', '2025'],
        'revenue_history': [3.9, 4.22, 5.48, 6.61],
        'revenue_cagr_5yr': '19.2%',
    }


@pytest.mark.parametrize('options', [{}, {'compact': True}, {'dense': True},
                                    {'role_scoped': True}, {'compact_json': True}])
def test_four_annual_observations_are_three_period_cagr_not_five(options):
    data = example()
    before = deepcopy(data)
    result, text = payload(data, **options)
    growth = result['growth']
    assert growth['revenue_cagr_pct'] == 19.2282
    assert growth['revenue_cagr_5yr_pct'] is None
    assert growth['revenue_cagr_legacy_pct'] == 19.2
    basis = growth['revenue_cagr_basis']
    assert basis['start_year'] == '2022'
    assert basis['end_year'] == '2025'
    assert basis['periods'] == 3
    assert basis['period_status'] == 'bound_to_history_rows'
    assert basis['source_period_verified'] is False
    assert result['deterministic_financial_tool_results']['calculations']['revenue_cagr']['period_basis'] == basis
    assert '不得從 legacy 欄位名稱推定五年' in text
    assert data == before


def test_only_six_consecutive_observations_bind_five_period_compatibility_value():
    data = example()
    data.update(years=['2020', '2021', '2022', '2023', '2024', '2025'],
                revenue_history=[1, 1.1, 1.21, 1.331, 1.4641, 1.61051],
                revenue_cagr_5yr='99%')
    result, _ = payload(data)
    growth = result['growth']
    assert growth['revenue_cagr_pct'] == growth['revenue_cagr_5yr_pct'] == 10
    assert growth['revenue_cagr_legacy_pct'] == 99
    assert growth['revenue_cagr_basis']['periods'] == 5


@pytest.mark.parametrize('updates', [
    {'years': []},
    {'years': ['2022', '2023', '2025', '2026']},
    {'years': ['2022', '2023', '2023', '2025']},
    {'years': ['2025', '2024', '2023', '2022']},
    {'years': ['2022', '2023', '2024']},
    {'years': ['2022', '2023', '2024', '2025Q4']},
    {'revenue_history': [3.9, None, 5.48, 6.61]},
    {'revenue_history': [3.9, 0, 5.48, 6.61]},
    {'revenue_history': [3.9, -1, 5.48, 6.61]},
    {'revenue_history': [3.9, True, 5.48, 6.61]},
])
def test_unknown_or_irregular_history_does_not_certify_legacy_period(updates):
    data = example()
    data.update(updates)
    before = deepcopy(data)
    result, _ = payload(data)
    growth = result['growth']
    assert growth['revenue_cagr_pct'] is None
    assert growth['revenue_cagr_5yr_pct'] is None
    assert growth['revenue_cagr_legacy_pct'] == 19.2
    basis = growth['revenue_cagr_basis']
    assert basis['period_status'] == 'unverified'
    assert basis['start_year'] is basis['end_year'] is basis['periods'] is None
    assert data == before


def test_prompt_row_trimming_does_not_change_full_calculation_period():
    data = example()
    data['_prompt_history_year_limit'] = 2
    result, _ = payload(data)
    assert len(result['history']['rows']) == 2
    assert result['growth']['revenue_cagr_basis']['periods'] == 3
    assert result['growth']['revenue_cagr_basis']['start_year'] == '2022'


def test_agent_instructions_use_actual_period_binding():
    prompts = Path(__file__).resolve().parents[1] / 'backend' / 'prompts'
    agents = json.loads((prompts / 'agents.json').read_text())
    text = json.dumps(agents, ensure_ascii=False)
    assert '不足五年時明列實際起訖年度與 CAGR 期數' in text
    for path in (prompts / 'agents.json', prompts / 'runtime_rules.json'):
        text = path.read_text()
        assert 'growth.revenue_cagr_5yr_pct' not in text
        assert 'growth.revenue_cagr_basis' in text
