"""Agent 7 must see the exact attributed sources accepted by its quote validator."""
import copy
import json

import pytest

from agent_runtime import prompting
from research_assumption_contract import _upstream, assess_reconciliation
from state_memory import initialize_agent_state
from test_gemma_state_references import expand_references, financial_payload, state_payload


def case():
    peers = [{'ticker': f'PEER{i}', 'as_of': '2026-09-25', 'price': 123,
              'missing': None, 'zero': 0, 'flag': False,
              'warning': '同業非本公司；數字與來源仍須核對。' * 12} for i in range(20)]
    data = {'ticker': 'TEST.TW', 'company_name': '測試公司', 'dynamic_peer_metrics': peers}
    state = initialize_agent_state(data)
    state.tool_results = {f'agent_{a}_preload': {'peer_context': {'dynamic_peer_metrics': copy.deepcopy(peers)}} for a in (4, 5)}
    growth = '【完整成長原文】' + '保留風險與反證。' * 4000 + '利潤率隨產能利用率修復，但尚缺時間表。'
    context = {'pipeline_id': 'v1', 'agent_state': state,
               'analyses': {4: '估值以2025年度EPS為基期。', '5': growth},
               'structured_outputs': {'4': {'analysis_markdown': '估值以2025年度EPS為基期。', 'other': ['缺少資本支出假設', 0, False, {}]}}}
    return data, context


@pytest.mark.parametrize('model', ['gemini-3.5-flash-lite', 'gemma-4-31b-it'])
@pytest.mark.parametrize('repair', [False, True])
def test_complete_agent_sources_visible_in_initial_and_repair_without_mutating_evidence(model, repair):
    data, context = case()
    context['_prompt_model_id'] = model
    if repair:
        context.update(_audit_retry_instruction='逐項核對原文引用。', _model_sequence_override={7: [model]})
    before = copy.deepcopy((data, context))
    prompt = prompting.build_prompt(7, data, context)
    assert '【Agent 4／5 逐字對照來源】' in prompt
    catalog = json.JSONDecoder().raw_decode(prompt.split('【Agent 4／5 逐字對照來源】\n', 1)[1])[0]
    assert catalog == {str(a): list(dict.fromkeys(_upstream(context, a))) for a in (4, 5)}
    assert 'valuation_quote' in prompt and 'growth_quote' in prompt
    assert '改寫或摘要' in prompt
    assert (data, context) == before
    # All State evidence paths/values must round trip, including null/0/false.
    raw_state = prompting.build_state_view_section(7, context, max_analysis_chars=14000,
                                                    dense=model.startswith('gemma'), compact_json=not model.startswith('gemma'))
    assert '$prompt_ref' in prompt
    assert expand_references(state_payload(prompt), financial_payload(prompt)) == state_payload(raw_state)
    assert prompt.endswith(prompting.OUTPUT_CLEANLINESS_RULE)


@pytest.mark.parametrize('change', ['boolean', 'date', 'order', 'missing', 'marker'])
def test_research_reference_keeps_nonidentical_peer_evidence_full(change):
    data, context = case()
    peers = context['agent_state'].tool_results['agent_4_preload']['peer_context']['dynamic_peer_metrics']
    if change == 'boolean': peers[0]['zero'] = False
    if change == 'date': peers[0]['as_of'] = '2026-09-24'
    if change == 'order': peers.reverse()
    if change == 'missing': del peers[0]['missing']
    if change == 'marker': peers[0]['reserved'] = {'$prompt_ref': 'financial#/external'}
    prompt = prompting.build_prompt(7, data, context)
    assert state_payload(prompt)['tool_results']['agent_4_preload']['peer_context']['dynamic_peer_metrics'] == peers


@pytest.mark.parametrize('agent', [4, 5, 16, 19, 24])
def test_attributed_catalog_and_peer_references_are_scoped_to_agent7(agent):
    data, context = case()
    prompt = prompting.build_prompt(agent, data, context)
    assert '【Agent 4／5 逐字對照來源】' not in prompt
    assert '$prompt_ref' not in prompt


def test_omitted_financial_template_cannot_create_dangling_references(monkeypatch):
    data, context = case()
    monkeypatch.setitem(prompting.ANALYSIS_PROMPTS, 7, '只核對前序引用')
    prompt = prompting.build_prompt(7, data, context)
    assert '$prompt_ref' not in prompt
    assert '【Agent 4／5 逐字對照來源】' in prompt


def test_visible_catalog_does_not_allow_wrong_agent_or_financial_quotes():
    data, context = case()
    prompting.build_prompt(7, data, context)
    rows = [{'topic': topic, 'status': 'unassessed', 'valuation_quote': '', 'growth_quote': '',
             'rationale': '上游缺乏同期間假設，不推定一致'}
            for topic in ('baseline', 'period', 'growth', 'capex_margin', 'calculation')]
    value = {'status': 'unassessed', 'checks': rows, 'pending_recalculation': False}
    assert assess_reconciliation(value, context)['issues'] == []
    rows[0]['valuation_quote'] = '利潤率隨產能利用率修復'
    rows[1]['growth_quote'] = '估值以2025年度EPS為基期。'
    assert set(assess_reconciliation(value, context)['issues']) == {'unsupported_valuation_quote', 'unsupported_growth_quote'}
