"""Keep an annual conversion tool separate from any TTM cash-flow evidence."""
from copy import deepcopy
import json

import pytest

from prompt_builder import format_data_for_prompt


MARKER = 'FCF conversion 期間契約'
FORMULA = 'latest annual FCF / latest annual net income'


def data():
    return {
        'ticker': '7777.TW', 'company_name': '測試公司',
        'years': ['2023', '2024'],
        'fcf_history': [0.12, -0.18], 'net_income_history': [0.4, 0.6],
        'free_cash_flow_raw': -246_800_000,
        'source_freshness': {'free_cash_flow': {'period_type': 'TTM',
            'period_start': '2024-07-01', 'period_end': '2025-06-30'}},
    }


def parse(text):
    return json.loads(text.split('【財務資料 JSON】\n', 1)[1].split('\n\n【使用規則】', 1)[0])


@pytest.mark.parametrize('options', [{}, {'compact': True}, {'dense': True},
                                    {'role_scoped': True}, {'compact_json': True}])
def test_annual_formula_adds_period_contract_without_rebinding_ttm(options):
    source = data()
    source['_prompt_agent_num'] = 2
    before = deepcopy(source)
    text = format_data_for_prompt(source, **options)
    result = parse(text)
    calculation = result['deterministic_financial_tool_results']['calculations']['latest_fcf_conversion']
    assert calculation == {'fcf_conversion_pct': -30.0, 'formula': FORMULA}
    assert result['ttm_financials']['net_income_billion_twd'] is None
    assert result['source_freshness'] == source['source_freshness']
    rule = next(line for line in text.splitlines() if MARKER in line)
    for phrase in ('latest_fcf_conversion', FORMULA, '年度', '正文', 'evidence_items',
                   'freshness_note', '同公司', '同報表範圍', '同幣別', '同起訖期間',
                   '已核實', 'TTM 淨利分母', '未評估', '不得沿用年度比率'):
        assert phrase in rule
    assert 'history' in rule and '年度無法綁定時' in rule
    assert 'headline_or_snippet' in text and '前序 Agent 重述不構成獨立佐證' in text
    assert source == before


@pytest.mark.parametrize('tool', [
    {}, {'calculations': {}},
    {'calculations': {'latest_fcf_conversion': {'fcf_conversion_pct': 10}}},
    {'calculations': {'latest_fcf_conversion': {'fcf_conversion_pct': 10, 'formula': 'TTM FCF / TTM net income'}}},
    {'calculations': {'latest_fcf_conversion': {'fcf_conversion_pct': 10, 'formula': None}}},
    {'calculations': {'latest_fcf_conversion': None}},
])
def test_missing_or_nonannual_formula_does_not_assert_annual_basis(monkeypatch, tool):
    monkeypatch.setattr('prompt_builder.build_financial_tool_context', lambda _: deepcopy(tool))
    assert MARKER not in format_data_for_prompt(data())


def test_missing_histories_does_not_invent_conversion_or_year():
    source = data()
    del source['fcf_history']
    del source['net_income_history']
    text = format_data_for_prompt(source)
    assert MARKER not in text
    assert 'latest_fcf_conversion' not in parse(text)['deterministic_financial_tool_results']['calculations']


def test_formula_without_year_keeps_instruction_conditional(monkeypatch):
    tool = {'calculations': {'latest_fcf_conversion': {
        'fcf_conversion_pct': -30, 'formula': FORMULA}}}
    monkeypatch.setattr('prompt_builder.build_financial_tool_context', lambda _: deepcopy(tool))
    text = format_data_for_prompt({})
    rule = next(line for line in text.splitlines() if MARKER in line)
    assert '年度無法綁定時' in rule and '不得猜造年份' in rule
    assert parse(text)['deterministic_financial_tool_results'] == tool


@pytest.mark.parametrize('agent', [11, 20, 22])
def test_role_without_financial_tool_is_not_told_it_has_annual_result(agent):
    source = data()
    source['_prompt_agent_num'] = agent
    text = format_data_for_prompt(source, role_scoped=True)
    assert 'deterministic_financial_tool_results' not in parse(text)
    assert MARKER not in text
