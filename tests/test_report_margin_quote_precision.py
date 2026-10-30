"""Bind margin claims and quote formatting without changing financial evidence."""
from copy import deepcopy
from decimal import Decimal
import json

import pytest

from financial_output_validator import validate_analysis_output
from research_assumption_contract import TOPICS, assess_reconciliation
from research_quote_fidelity import restore_reconciliation_quotes
from structured_output_normalizer_basic import _display_price_target


MARGINS = {'profit_margin_provider': '3.0%', 'profit_margin': '2.8%'}


@pytest.mark.parametrize('text', [
    '[護城河評分]\n品牌影響力: 3.0\n成本優勢: 3.0\n[/護城河評分]\n2025 年淨利率 0.5%，TTM 校準後淨利率 2.7841%。',
    '2025 年淨利率 0.5%。若淨負債降至 3.0 billion_twd 以下，則重新評估。',
    '毛利率3.0%，淨利率2.8%。',
    '淨利率2.8%，本益比23.0倍。',
])
def test_unrelated_score_debt_or_other_ratio_cannot_be_bound_as_net_margin(text):
    assert not any('淨利率口徑紅線' in issue for issue in validate_analysis_output(3, text, MARGINS))


@pytest.mark.parametrize('text', ['本公司目前淨利率為3.0%。', 'TTM淨利率：3.0%。',
    '淨利率3%，不是校準後口徑。', '本公司淨利率3.0%，低於同業。',
    'Yahoo原始淨利率3.0%，作為正式估值口徑。'])
def test_actual_provider_margin_still_requires_calibrated_basis(text):
    assert any('淨利率口徑紅線' in issue for issue in validate_analysis_output(3, text, MARGINS))


def test_an_unrelated_warning_cannot_waive_an_actual_incorrect_margin():
    text = 'Yahoo原始資料僅供資料源對照。\n本公司目前淨利率3.0%。'
    assert any('淨利率口徑紅線' in issue for issue in validate_analysis_output(3, text, MARGINS))


@pytest.mark.parametrize('text', ['Yahoo原始淨利率3.0%，不採用；校準後為2.8%。',
    '若未來淨利率達3.0%，再重新評估。', '同業淨利率3.0%，本公司淨利率2.8%。',
    '2025年淨利率3.0%，不代表當前TTM。'])
def test_raw_source_warning_projection_or_other_scope_is_not_a_current_margin(text):
    assert not any('淨利率口徑紅線' in issue for issue in validate_analysis_output(3, text, MARGINS))


def test_current_table_margin_is_bound_to_its_own_column():
    text = '| 項目 | 毛利率 | 淨利率 |\n| --- | --- | --- |\n| 本公司 | 30.0% | 3.0% |'
    assert any('淨利率口徑紅線' in issue for issue in validate_analysis_output(3, text, MARGINS))
    assert not any('淨利率口徑紅線' in issue for issue in validate_analysis_output(3, text.replace('3.0% |', '2.8% |'), MARGINS))


def reconciliation(quote):
    return {'status': 'unassessed', 'pending_recalculation': False,
        'checks': [{'topic': topic, 'status': 'unassessed', 'valuation_quote': '',
            'growth_quote': quote if topic == 'baseline' else '', 'rationale': '尚缺可比成長假設。'}
            for topic in TOPICS]}


def test_table_inline_source_reference_does_not_hide_a_separate_bold_witness():
    source = '| SOM | **35.3644 billion_twd** (約新臺幣353.64億元) | `data.ttm_financials` |'
    quote = '35.3644 billion_twd (約新臺幣353.64億元)'
    context = {'analyses': {5: source}}
    value = reconciliation(quote)
    before = deepcopy(value)
    restored, receipt = restore_reconciliation_quotes(value, context, json.dumps(value))
    literal = '**35.3644 billion_twd** (約新臺幣353.64億元)'
    assert restored['checks'][0]['growth_quote'] == literal
    assert not assess_reconciliation(restored, context)['issues']
    witness = receipt['changes'][0]['sources'][0]
    assert source[witness['start']:witness['end']] == literal
    assert receipt['changes'][0]['source_agent'] == 5
    assert value == before and restored['status'] == 'unassessed'


@pytest.mark.parametrize('source', [
    '| `前文**成長10%**後文` | 資料 |',
    '| ``前文**成長10%**後文 `code` `` | 資料 |',
    '| `未結束 | 前文**成長10%**後文 |',
    '```\n前文**成長10%**後文\n```',
    '    前文**成長10%**後文',
])
def test_code_or_unbalanced_delimiters_cannot_authorize_bold_reconstruction(source):
    value = reconciliation('前文成長10%後文')
    context = {'analyses': {5: source}}
    restored, receipt = restore_reconciliation_quotes(value, context, 'raw')
    assert restored == value and receipt is None
    assert assess_reconciliation(restored, context)['issues']


@pytest.mark.parametrize('quote', ['35.3645 billion_twd (約新臺幣353.64億元)',
    '35.3644 billion_twd(約新臺幣353.64億元)', '35.3644 billion_twd...353.64億元'])
def test_quote_numbers_spacing_and_omissions_remain_verbatim_requirements(quote):
    source = '| **35.3644 billion_twd** (約新臺幣353.64億元) | `ref` |'
    value = reconciliation(quote)
    context = {'analyses': {5: source}}
    restored, receipt = restore_reconciliation_quotes(value, context, 'raw')
    assert restored == value and receipt is None
    assert assess_reconciliation(restored, context)['issues']


@pytest.mark.parametrize('value,expected', [(46.5, 'NT$46.50'), (34.68, 'NT$34.68'),
    (54.62, 'NT$54.62'), (46.567, 'NT$46.567'), (0.0125, 'NT$0.0125'), (1000, 'NT$1,000')])
def test_target_prices_keep_stored_precision_in_all_report_surfaces(value, expected):
    from reporting.target_price_text import target_price_text
    from reporting.evidence_matrix_basis import price_target_basis
    from reporting.summary_cards import build_price_target_cards_html
    assert _display_price_target(value) == expected
    assert target_price_text(value) == expected
    assert target_price_text(Decimal(str(value))) == expected
    assert target_price_text(str(value)) == expected
    assert price_target_basis({'基本情境': value}) == f'基本情境: {expected}'
    assert expected in build_price_target_cards_html({'基本情境': value}, value)


@pytest.mark.parametrize('value', [None, True, False, 0, -1, float('nan'), float('inf')])
def test_missing_or_invalid_price_does_not_become_a_zero_target(value):
    from reporting.target_price_text import target_price_text
    assert _display_price_target(value) == target_price_text(value) == 'N/A'


def test_broken_numeric_accessor_remains_a_missing_price_not_a_render_failure():
    from reporting.target_price_text import target_price_text
    class BrokenFloat(float):
        def __float__(self):
            raise RuntimeError('unavailable numeric accessor')
    assert _display_price_target(BrokenFloat(46.5)) == 'N/A'
    assert target_price_text(BrokenFloat(46.5)) == 'N/A'


def test_price_display_cache_policy_only_changes_valuation_roles(monkeypatch):
    import report_price_format
    from agent_runtime.step_cache import build_agent_step_cache_key
    def keys():
        return {n: build_agent_step_cache_key(n, {'ticker': '2367.TW'}, {}, 'test', 'same complete prompt')
                for n in (3, 4, 7, 14, 16, 19, 21, 24)}
    before = keys()
    monkeypatch.setattr(report_price_format, 'POLICY', 'isolated-other-display-version')
    after = keys()
    assert {n for n in before if before[n] != after[n]} == {4, 14}
