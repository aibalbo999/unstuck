"""Early bounded repair retains the final decision and money-unit gates."""
import asyncio
from copy import deepcopy

import pytest

from financial_output_validator import validate_analysis_output
from research_assumption_contract import TOPICS, assess_reconciliation


def test_actual_industry_loss_with_adversative_prefix_is_caught_before_render():
    data = {'ticker': '2367.TW', 'company_name': '燿華', 'financial_currency': 'TWD',
            'net_income_ttm_raw': -459064563.75}
    text = '儘管 TTM 淨利仍為負值（-0.46 億元），但市場預期 Forward EPS 可達 2.89 元。'
    assert any('財務金額單位紅線' in issue for issue in validate_analysis_output(11, text, data))
    assert not validate_analysis_output(11, text.replace('-0.46', '-4.59'), data)


@pytest.mark.parametrize('text', ['儘管同業 TTM 淨利 -0.46 億元。',
    '儘管預估 TTM 淨利 -0.46 億元。', '若 TTM 淨利降至 -0.46 億元，再重新評估。',
    '2024 年淨利 -0.46 億元。', 'TTM EPS -0.46 元。'])
def test_other_owner_projection_period_or_dimension_cannot_borrow_current_net_income(text):
    assert not validate_analysis_output(11, text, {'ticker': '2367.TW', 'company_name': '燿華',
        'financial_currency': 'TWD', 'net_income_ttm_raw': -459064563.75})


@pytest.mark.parametrize('defect', ['return_alignment', 'growth_quote'])
@pytest.mark.parametrize('repair_succeeds', [True, False])
def test_existing_single_quality_rewrite_handles_a_decision_defect_before_final_audit(monkeypatch, defect, repair_succeeds):
    from agent_runtime import quality_gates as gates
    source4 = '估值採相對本益比，基本情境為40.80元。'
    source5 = r'成長計算公式：Revenue = Base \times (1 + g)^5。'
    context = {'ticker': '6282.TW', 'pipeline_id': 'v1', 'data': {
        'ticker': '6282.TW', 'company_name': '康舒', 'current_price': 43.15,
        'data_trust': {'score': 91, 'status': 'fresh'}},
        'analyses': {4: source4, 5: source5}, 'structured_outputs': {}, 'blocking_issues': []}
    original_data = deepcopy(context['data'])
    original_sources = deepcopy(context['analyses'])
    calls = []

    def candidate(rewritten):
        reconciliation = {'status': 'aligned', 'pending_recalculation': False, 'checks': [
            {'topic': topic, 'status': 'aligned', 'valuation_quote': source4, 'growth_quote': source5,
             'rationale': '依照兩個角色原文核對；沒有重算價格。'} for topic in TOPICS]}
        if defect == 'growth_quote' and not rewritten:
            reconciliation['checks'][-1]['growth_quote'] = source5.replace('\\times', '\\\\times')
        output = {'recommendation': {'建議': '持有' if defect == 'return_alignment' and not rewritten else '避免',
            '短期目標（3個月）': 'NT$40.80', '中期目標（6個月）': 'NT$40.80',
            '長期目標（12個月）': 'NT$40.80', '長期潛力（5年）': '未評估', '信心指數': '5/10'},
            'assumption_reconciliation': reconciliation,
            'assumption_reconciliation_assessment': assess_reconciliation(reconciliation, context),
            'analysis_markdown': '風險未釐清，不增加新部位；不代表帳戶持倉。'}
        context['structured_outputs'][7] = output
        return output['analysis_markdown']

    async def initial(*args, **kwargs):
        calls.append('initial')
        return candidate(False)

    async def rewrite(*args, **kwargs):
        calls.append('rewrite')
        return candidate(repair_succeeds)

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(gates, 'initial_or_checkpointed_draft', initial)
    monkeypatch.setattr(gates, 'run_single_agent_async', rewrite)
    monkeypatch.setattr(gates, 'ensure_context_digest_async', noop)
    monkeypatch.setattr(gates, 'ensure_agent_rag_context_async', noop)
    monkeypatch.setattr(gates, 'checkpoint_unvalidated_draft', noop)
    asyncio.run(gates.run_agent_with_quality_gates_async(7, context['data'], context, None))
    assert calls == ['initial', 'rewrite']
    assert context['agent_quality_retry_counts'][7] == 1
    assert context['structured_outputs'][7]['recommendation']['長期目標（12個月）'] == 'NT$40.80'
    assert context['data'] == original_data
    assert {n: context['analyses'][n] for n in (4, 5)} == original_sources
    if repair_succeeds:
        assert not context['blocking_issues']
    else:
        from agent_runtime.repair_state import repair_contract_issues
        from agent_runtime.deterministic_fallback_audit import clear_agent_blocking_issues
        assert repair_contract_issues(7, context)
        assert context['blocking_issues'] and all(item.startswith('Agent 7 ') for item in context['blocking_issues'])
        context['blocking_issues'].append('Agent 11 unrelated failure')
        clear_agent_blocking_issues(context, 7)
        assert context['blocking_issues'] == ['Agent 11 unrelated failure']
        assert repair_contract_issues(7, context)  # Clearing a marker never validates the candidate.
