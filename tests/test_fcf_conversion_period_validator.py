"""Annual conversion evidence cannot be relabeled as a TTM conversion ratio."""
from copy import deepcopy

import pytest

from financial_output_validator import validate_analysis_output


TOOL = 'data.deterministic_financial_tool_results.calculations.latest_fcf_conversion'
ISSUE = 'FCF 轉換率期間紅線'


def source():
    return {
        'ticker': '1623.TW', 'company_name': '大東電',
        'years': ['2024', '2025'], 'fcf_history': [0.08, -0.23],
        'net_income_history': [0.73, 0.82],
        'quant_metrics': {'calculations': {'latest_fcf_conversion': {
            'fcf_conversion_pct': -28.0488,
            'formula': 'latest annual FCF / latest annual net income',
        }}},
    }


def issues(text, data=None, agent=2):
    return [item for item in validate_analysis_output(agent, text, source() if data is None else data)
            if ISSUE in item]


@pytest.mark.parametrize('text', [
    f'TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'LTM自由現金流轉換率為-28%（來源：{TOOL}）。',
    f'近十二個月FCF轉換率為-28.0488%（來源：{TOOL}）。',
    f'FCF轉換率為-28.05%（來源：{TOOL}；TTM期間2025-07-01至2026-06-30）。',
    f'## TTM 現金流分析\nFCF轉換率為-28.05%（來源：{TOOL}）。',
    f'依據{TOOL}，本公司TTM FCF轉換率為-28.05%。',
    f'官方個別財報TTM自由現金流為-2.47億元，且FCF轉換率為-28.05%，顯示獲利尚未轉為現金流入。（來源：data.cash_flow.free_cash_flow_basis、{TOOL}；TTM期間2025-07-01至2026-06-30）；反證：2024年度曾有正FCF。',
    f'2025年度營收成長。本公司TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'同業2025年度FCF轉換率為10%，本公司TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'2025年度FCF轉換率為-28.05%。本公司TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'TTM FCF轉換率為-28.05%（來源：{TOOL}），若改善則重新評估。',
    f'TTM FCF轉換率為-30%（來源：{TOOL}）。',
    f'## 資料品質\n別項資料不足。\n## 已觀測現金流\n本公司TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
])
def test_explicit_ttm_claim_cannot_cite_annual_conversion_tool(text):
    result = issues(text)
    assert result
    assert 'latest_fcf_conversion' in result[0]
    assert '年度' in result[0]


@pytest.mark.parametrize('text', [
    f'2025年度FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'最新年度FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'TTM FCF為-2.47億元。2025年度FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'TTM FCF為-2.47億元，且2025年度FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'2025年度FCF轉換率為-28.05%（來源：{TOOL}），TTM FCF為-2.47億元。',
    f'## TTM 現金流\n2025年度FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'若TTM FCF轉換率為-28.05%（來源：{TOOL}），則重新評估。',
    f'TTM FCF轉換率為-28.05%是情境假設（來源：{TOOL}）。',
    f'TTM FCF轉換率並非-28.05%（來源：{TOOL}）。',
    f'錯誤示例：TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'TTM FCF轉換率為-28.05%是錯誤說法（來源：{TOOL}）。',
    f'不可把TTM FCF轉換率寫為-28.05%（來源：{TOOL}）。',
    f'TTM FCF轉換率為-28.05%（來源：{TOOL}），此值不可採用。',
    f'同業TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'華通TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'## 華通\nTTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'## 同業比較\nTTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    'TTM FCF轉換率為-28.05%。',  # Equal digits alone do not prove source reuse.
    'TTM FCF轉換率為-28.05%（來源：data.official_ttm_conversion）。',
    f'2025年度FCF轉換率為-28.05%（來源：{TOOL}）。TTM FCF轉換率為-28.05%。',
    f'2025年度FCF轉換率為-28.05%（來源：{TOOL}），TTM FCF轉換率為-28.05%。',
    f'2025年度FCF轉換率為-28.05%（來源：{TOOL}）及TTM FCF轉換率為-28.05%。',
    f'TTM FCF轉換率為-28.05%，年度淨利率為12.4%（來源：{TOOL}）。',
    f'TTM FCF轉換率為-28.05%（來源：華通、{TOOL}）。',
    f'TTM FCF轉換率為-28.05%（同業華通）（來源：{TOOL}）。',
    f'## TTM 分析\nFCF為-2.47億元。\n## 年度分析\nFCF轉換率為-28.05%（來源：{TOOL}）。',
    f'## 未來情境\nTTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'TTM淨利率為-28.05%（來源：{TOOL}）。',
])
def test_period_owner_source_and_nonactual_boundaries_are_not_global(text):
    assert not issues(text)


@pytest.mark.parametrize('patch', [
    {}, {'quant_metrics': {}},
    {'quant_metrics': {'calculations': {'latest_fcf_conversion': {'fcf_conversion_pct': -28.0488}}}},
    {'quant_metrics': {'calculations': {'latest_fcf_conversion': {'fcf_conversion_pct': None, 'formula': 'latest annual FCF / latest annual net income'}}}},
    {'quant_metrics': {'calculations': {'latest_fcf_conversion': {'fcf_conversion_pct': True, 'formula': 'latest annual FCF / latest annual net income'}}}},
    {'quant_metrics': {'calculations': {'latest_fcf_conversion': {'fcf_conversion_pct': -28.0488, 'formula': 'TTM FCF / TTM net income'}}}},
])
def test_missing_or_nonannual_tool_evidence_does_not_invent_a_mismatch(patch):
    assert not issues(f'TTM FCF轉換率為-28.05%（來源：{TOOL}）。', patch)


@pytest.mark.parametrize('agent', [2, 6, 7])
def test_wiring_rejects_relabeling_without_mutating_text_or_source(agent):
    data = source()
    original = deepcopy(data)
    text = f'本公司TTM FCF轉換率為-28.05%（來源：{TOOL}）。'
    assert issues(text, data, agent)
    assert data == original
    assert text == f'本公司TTM FCF轉換率為-28.05%（來源：{TOOL}）。'


@pytest.mark.parametrize('text', [
    f'同業華通：\n- TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'- 同業華通：\n  - TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'同業華通：\n* TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'同業華通：\n1. TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
])
def test_parent_peer_owner_is_inherited_only_by_its_list(text):
    assert not issues(text)


@pytest.mark.parametrize('text', [
    f'同業華通：\n- 本公司TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'同業華通：\n- 另有同業資料。\n## 本公司現金流\nTTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'- 同業華通：\n  - 另有同業資料。\n- TTM FCF轉換率為-28.05%（來源：{TOOL}）。',
    f'同業華通：\n- 另有同業資料。\nTTM FCF轉換率為-28.05%（來源：{TOOL}）。',
])
def test_explicit_target_or_end_of_parent_list_resets_inherited_owner(text):
    assert issues(text)
