"""Delivered recommendation guidance matches the existing numeric contract."""
import asyncio
import copy
import json

import pytest

from agent_runtime.prompting import build_prompt
from agent_runtime.repair_diagnostics import recommendation_repair_diagnostic
from agent_runtime.repair_reflection import build_audit_retry_instruction
from forward_consistency_checker import check_recommendation_return_alignment


MARKER = '推薦與報酬數值契約'


@pytest.mark.parametrize('label,target', [('持有', 1250), ('持有', 960), ('買入', 1000), ('放空', 1000)])
def test_rejection_guidance_does_not_offer_unimplemented_explanation_or_price_override(label, target):
    issues = check_recommendation_return_alignment(label, 948, target)
    assert issues
    text = '\n'.join(issues)
    assert '文字說明不豁免數值門檻' in text
    assert '依來源證據重新檢查' in text
    assert '不可為過關任意改價或改分類' in text
    for misleading in ('需要降低建議等級或提高目標價', '應升格為「買入」', '或說明折讓原因'):
        assert misleading not in text


@pytest.mark.parametrize('label,target,rejected', [
    ('BUY', 114.99, True), ('BUY', 115, False),
    ('HOLD', 104.99, True), ('HOLD', 105, False),
    ('HOLD', 130, False), ('HOLD', 130.01, True),
    ('SHORT', 85, False), ('SHORT', 85.01, True),
    ('AVOID', 135, False),
])
def test_existing_numeric_boundaries_are_unchanged(label, target, rejected):
    assert bool(check_recommendation_return_alignment(label, 100, target)) is rejected


@pytest.mark.parametrize('agent,pipeline', [(7, 'v1'), (16, 'v2'), (19, 'v3')])
def test_initial_assembled_prompt_explains_numeric_contract_and_research_stances(agent, pipeline):
    prompt = build_prompt(agent, {'ticker': 'TEST', 'company_name': '測試公司', 'current_price': 948}, {'pipeline_id': pipeline})
    assert MARKER in prompt
    assert all(text in prompt for text in ('買入≥15%', '持有≥5%且≤30%', '放空≤-15%'))
    assert '文字說明不豁免數值門檻' in prompt
    assert '持有不是所有等待／觀察的代稱' in prompt
    assert '避免表示本研究不新增部位' in prompt
    assert '不代表實際零持倉' in prompt
    assert '不可預設選避免' in prompt


@pytest.mark.parametrize('agent,pipeline', [(4, 'v1'), (15, 'v2'), (18, 'v3'), (24, 'v4'), (7, 'v4')])
def test_non_recommendation_roles_do_not_receive_contract_diagnostic(agent, pipeline):
    data = {'ticker': 'TEST', 'company_name': '測試公司', 'current_price': 948}
    context = {'pipeline_id': pipeline, 'structured_outputs': {7: {'recommendation': {'建議': '持有'}}}}
    assert MARKER not in build_prompt(agent, data, context)
    retry = build_audit_retry_instruction(agent, ['目前問題'], data=data, context=context)
    assert '【前次決策數值診斷' not in retry


def context_for(agent, pipeline, key):
    return {'pipeline_id': pipeline, 'data': {'ticker': 'TEST', 'company_name': '測試公司', 'current_price': 100}, 'structured_outputs': {
        key: {'recommendation': {'建議': '持有', '12個月': 'NT$120–130'}},
        99: {'recommendation': {'建議': '買入', '12個月': 'NT$999'}},
    }}


@pytest.mark.parametrize('agent,pipeline', [(7, 'v1'), (16, 'v2'), (19, 'v3')])
@pytest.mark.parametrize('string_key', [False, True])
def test_diagnostic_uses_actual_mode_and_latest_candidate_without_mutation(agent, pipeline, string_key):
    key = str(agent) if string_key else agent
    context = context_for(agent, pipeline, key)
    before = copy.deepcopy(context)
    initial = recommendation_repair_diagnostic(context, context['data'])
    assert '稽核採用價：125；隱含報酬 25.0%' in initial
    assert 'NT$999' not in initial
    assert context == before
    context['structured_outputs'][key]['recommendation']['12個月'] = 'NT$140'
    before = copy.deepcopy(context['structured_outputs'])
    current = build_audit_retry_instruction(agent, ['另有逐字引文問題'], context=context, data=context['data'])
    assert '稽核採用價：140；隱含報酬 40.0%' in current
    assert 'NT$120–130' not in current
    assert MARKER in current and '文字說明不豁免數值門檻' in current
    assert context['structured_outputs'] == before
    assert ('short_setup' in current) is (agent == 19)
    if agent != 19:
        assert '製造業風險應逐項討論' not in current


def test_preflight_and_retry_derive_limits_from_same_gate_source(monkeypatch):
    from forward_consistency_checker import RECOMMENDATION_RETURN_GATES
    monkeypatch.setitem(RECOMMENDATION_RETURN_GATES['持有'], 'max_expected_return_pct', 29.0)
    context = context_for(7, 'v1', 7)
    for text in (build_prompt(7, context['data'], context),
                 build_audit_retry_instruction(7, ['目前問題'], context=context, data=context['data'])):
        assert '持有≥5%且≤29%' in text
        assert '持有≥5%且≤30%' not in text


@pytest.mark.parametrize('agent,pipeline', [(7, 'v1'), (16, 'v2'), (19, 'v3')])
def test_assembled_retry_delivers_exact_contract_once_without_losing_other_rules_or_sources(agent, pipeline):
    from forward_consistency_checker import recommendation_contract_guidance
    from prompt_rules import build_final_audit_preflight_rule
    context = context_for(agent, pipeline, agent)
    context['rag_context'] = {agent: 'SOURCE_RECORD_2026：營收 55 億元，來源完整保留。'}
    context['_audit_retry_instruction'] = build_audit_retry_instruction(
        agent, ['既有問題須保留'], data=context['data'], context=context)
    before = copy.deepcopy(context)
    rule = recommendation_contract_guidance()
    assert context['_audit_retry_instruction'].count(rule) == 1  # Standalone remains complete.
    initial_preflight = build_final_audit_preflight_rule(agent, pipeline)
    prompt = build_prompt(agent, context['data'], context)
    assert prompt.count(rule) == 1
    assert context['_audit_retry_instruction'] in prompt
    assert context['rag_context'][agent] in prompt
    for line in initial_preflight.splitlines():
        if rule not in line:
            assert line in prompt
    assert context['structured_outputs'] == before['structured_outputs']
    assert context['rag_context'] == before['rag_context']
    assert context['data'] == before['data']


@pytest.mark.parametrize('variant', ['partial', 'changed_limit', 'embedded', 'quoted'])
def test_incomplete_or_non_instruction_copy_does_not_suppress_canonical_preflight(variant):
    from forward_consistency_checker import recommendation_contract_guidance
    rule = recommendation_contract_guidance()
    retry = {'partial': rule[:-1], 'changed_limit': rule.replace('≤30%', '≤31%'),
             'embedded': '原稿引用：' + rule, 'quoted': '> ' + rule}[variant]
    context = context_for(7, 'v1', 7)
    context['_audit_retry_instruction'] = retry
    prompt = build_prompt(7, context['data'], context)
    assert '\n- ' + rule in prompt
    assert retry in prompt


@pytest.mark.parametrize('asynchronous', [False, True])
def test_actual_bounded_repair_refreshes_numeric_diagnostic_after_unrelated_rewrite(monkeypatch, asynchronous):
    from agent_runtime import repair_loop
    from research_assumption_contract import TOPICS
    from structured_output_runtime import process_agent_response

    def candidate(target):
        return {'recommendation': {'建議': '持有', '長期目標（12個月）': target},
                'analysis_markdown': '研究結論仍須更多證據確認，不把未知資料當作已驗證。',
                'assumption_reconciliation': {'status': 'unassessed', 'pending_recalculation': False,
                    'checks': [{'topic': topic, 'status': 'unassessed', 'valuation_quote': '',
                                'growth_quote': '', 'rationale': '缺少可供對照的來源。'} for topic in TOPICS]}}
    context = {'pipeline_id': 'v1', 'data': {'current_price': 100}, 'analyses': {}, 'structured_outputs': {}}
    context['analyses'][7] = process_agent_response(7, json.dumps(candidate('NT$120–130'), ensure_ascii=False),
        context, completion_diagnostics={'finish_reasons': ['STOP']})
    instructions = []
    def run(agent, data, ctx, rotator, **kwargs):
        instructions.append(ctx['_audit_retry_instruction'])
        target = 'NT$140' if len(instructions) == 1 else 'NT$110'
        value = candidate(target)
        if len(instructions) == 1:
            value['assumption_reconciliation']['status'] = 'aligned'
        return process_agent_response(7, json.dumps(value, ensure_ascii=False), ctx,
                                      completion_diagnostics={'finish_reasons': ['STOP']})
    async def run_async(*args, **kwargs):
        return run(*args, **kwargs)
    async def reflect_async(*args, **kwargs):
        return '依本次資料重寫。'
    monkeypatch.setattr(repair_loop, 'run_single_agent', run)
    monkeypatch.setattr(repair_loop, 'run_single_agent_async', run_async)
    monkeypatch.setattr(repair_loop, 'generate_audit_reflection', lambda *args, **kwargs: '依本次資料重寫。')
    monkeypatch.setattr(repair_loop, 'generate_audit_reflection_async', reflect_async)
    monkeypatch.setattr(repair_loop, 'repair_429_circuit_state', lambda *args: {})
    monkeypatch.setattr(repair_loop, 'get_audit_rewrite_model_sequence', lambda *args: ['offline'])
    args = (7, context['data'], context, None, ['另有逐字引文問題'])
    result = asyncio.run(repair_loop._repair_agent_output_async(*args)) if asynchronous else repair_loop._repair_agent_output(*args)
    assert result[0], result
    assert len(instructions) == 2
    assert '稽核採用價：125；隱含報酬 25.0%' in instructions[0]
    assert '稽核採用價：140；隱含報酬 40.0%' in instructions[1]
    assert '文字說明不豁免數值門檻' in instructions[1]
    assert context['repair_attempt_counts'][7] == 2
