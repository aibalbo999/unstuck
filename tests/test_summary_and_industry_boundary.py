"""Generated summaries and unstructured industry text retain evidence gates."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from research_assumption_contract import TOPICS
from structured_output_runtime import process_agent_response


def summary_context():
    return {'pipeline_id': 'v1', 'data': {'ticker': '6282.TW', 'company_name': '康舒',
        'financial_currency': 'TWD', 'free_cash_flow_raw': -168490256, 'current_price': 43.15},
        'parsed': {'recommendation': {'建議': '持有', '長期目標（12個月）': 'NT$48.50'}},
        'analyses': {}, 'structured_outputs': {}}


@pytest.mark.parametrize('async_mode', [False, True])
@pytest.mark.parametrize('summary', [
    '研究分類為持有。TTM 自由現金流為負值（-0.1685 億元），現金流仍待改善。',
    '研究分類為中性觀察。TTM 自由現金流為負值（-1.6849 億元），現金流仍待改善。',
])
def test_generated_bad_summary_is_not_adopted(async_mode, summary, monkeypatch):
    import tear_sheet_tasks as tasks
    import agent_runtime.llm_waiting as waiting
    class FakeRotator:
        pass
    calls = []
    def response(*args, **kwargs):
        calls.append('one_provider_call')
        return SimpleNamespace(text=summary, candidates=[SimpleNamespace(finish_reason='STOP')])
    async def response_async(*args, **kwargs):
        return response(*args, **kwargs)
    async def key_async(*args, **kwargs):
        return 'offline-placeholder'
    monkeypatch.setattr(tasks, 'KeyRotator', FakeRotator)
    monkeypatch.setattr(tasks, '_tear_sheet_model_sequence', lambda: ['gemini-fixture'])
    monkeypatch.setattr(tasks, 'response_text', lambda item: item.text)
    monkeypatch.setattr(tasks, '_generate_tear_sheet_content', response)
    monkeypatch.setattr(tasks, '_generate_tear_sheet_content_async', response_async)
    monkeypatch.setattr(waiting, 'acquire_key', lambda *a, **kw: 'offline-placeholder')
    monkeypatch.setattr(waiting, 'acquire_key_async', key_async)
    context = summary_context()
    original = deepcopy(context)
    if async_mode:
        asyncio.run(tasks.ensure_tear_sheet_summary_async(context, FakeRotator()))
    else:
        tasks.ensure_tear_sheet_summary(context, FakeRotator())
    assert context.get('tear_sheet_summary') != summary
    assert context.get('tear_sheet_validation', {}).get('status') == 'rejected'
    assert any(('金額' if '-0.1685' in summary else '分類') in item
               for item in context['tear_sheet_validation']['issues'])
    assert context['data'] == original['data'] and context['parsed'] == original['parsed']
    assert calls == ['one_provider_call']


def test_literal_but_unrelated_growth_quote_cannot_certify_calculation():
    quote4 = '由於 TTM 自由現金流為負值，目前 DCF 不可用。'
    quote5 = '隨全球衛星發射量增加，地面接收站與衛星載體電源需求具備長期成長空間。'
    context = {'pipeline_id': 'v1', 'data': {'current_price': 43.15},
               'analyses': {4: quote4, 5: quote5}, 'structured_outputs': {}}
    rows = [{'topic': topic, 'status': 'unassessed', 'valuation_quote': '', 'growth_quote': '',
             'rationale': '沒有同主題證據，不判定一致。'} for topic in TOPICS]
    rows[-1].update(status='aligned', valuation_quote=quote4, growth_quote=quote5,
                    rationale='雙方皆認定 DCF 不可用，計算邏輯一致。')
    payload = {'recommendation': {'建議': '持有', '長期目標（12個月）': 'NT$48.50'},
               'analysis_markdown': '保持風險與資料限制，不補造價格。',
               'assumption_reconciliation': {'status': 'unassessed', 'pending_recalculation': False, 'checks': rows}}
    process_agent_response(7, json.dumps(payload, ensure_ascii=False), context,
                           completion_diagnostics={'finish_reasons': ['STOP']})
    assessment = context['structured_outputs'][7]['assumption_reconciliation_assessment']
    assert assessment['issues']
    assert any(item.get('topic') == 'calculation' and item.get('field') == 'growth_quote'
               for item in assessment.get('semantic_issues', []))
    assert context['structured_outputs'][7]['assumption_reconciliation']['checks'][-1]['growth_quote'] == quote5


def test_unstructured_industry_preserves_provider_truncation_as_a_failure():
    context = {'pipeline_id': 'v2', 'data': {'financial_currency': 'TWD',
        'net_income_ttm_raw': -459064563.75}, 'analyses': {}, 'structured_outputs': {}}
    text = '## 總體經濟\n高利率增加融資壓力。\n## 產業週期\n需求轉型。\n## 宏觀結論\n* **理由：**'
    process_agent_response(11, text, context, completion_diagnostics={'finish_reasons': ['MAX_TOKENS']})
    receipt = (context['structured_outputs'].get(11) or {}).get('output_completion') or {}
    assert receipt.get('status') == 'incomplete'
    assert 'provider_output_incomplete' in receipt.get('issues', [])


def test_correct_summary_keeps_source_data_and_records_the_validation_receipt():
    from summary_consistency import accept_summary, summary_reference_prompt
    context = summary_context()
    original = deepcopy(context)
    text = '研究分類為持有。TTM 自由現金流為 -1.6849 億元，來源稱TTM但起訖期間未核實。'
    assert accept_summary(text, context, diagnostics={'finish_reasons': ['STOP']})
    assert context['tear_sheet_summary'] == text
    assert context['tear_sheet_validation']['status'] == 'accepted'
    assert context['data'] == original['data'] and context['parsed'] == original['parsed']
    assert '-1.68490256 億元' in summary_reference_prompt(context)
    from workflow_context import graph_delta_from_legacy_context
    delta = graph_delta_from_legacy_context(context)
    assert delta['structured_outputs']['tear_sheet']['summary_validation']['status'] == 'accepted'


@pytest.mark.parametrize('mutation', ['too_long', 'truncated', 'wrong_class'])
def test_summary_guard_does_not_cut_off_text_or_relabel_model_prose(mutation):
    from summary_consistency import accept_summary
    context = summary_context()
    text = '研究分類為持有。TTM 自由現金流為 -1.6849 億元。'
    diagnostics = {'finish_reasons': ['STOP']}
    if mutation == 'too_long':
        text += '完整風險應保留。' * 150
    elif mutation == 'truncated':
        diagnostics = {'finish_reasons': ['MAX_TOKENS']}
    else:
        text = text.replace('持有', '買入')
    assert not accept_summary(text, context, diagnostics=diagnostics)
    assert context['tear_sheet_summary'] != text
    assert '綜合建議為「持有」' in context['tear_sheet_summary']
    assert context['structured_outputs']['tear_sheet']['summary_validation']['status'] == 'rejected'


@pytest.mark.parametrize('left,right,aligned', [
    ('期間為未來1年。', '期間為未來12個月。', True),
    ('期間為未來五年。', '期間為未來5年。', True),
    ('期間為2026年展望。', '期間為未來5年。', False),
    ('期間從2026年開始，未來1年。', '期間從2026年開始，未來5年。', False),
    ('2025年為營收基期。', '2024年為營收基期。', False),
])
def test_topic_period_witnesses_do_not_equate_different_horizons(left, right, aligned):
    from research_assumption_contract import AssumptionCheck
    from research_quote_semantics import semantic_issues
    row = AssumptionCheck(topic='period', status='aligned', valuation_quote=left,
                          growth_quote=right, rationale='必須實際核對共同期間，不由背景推定。')
    assert bool(semantic_issues([row])) is not aligned
