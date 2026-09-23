"""Repair requests retain prior failures and diagnose the rejected decision."""
import asyncio
import copy
import json

import pytest

from agent_runtime import quality_retry, repair_loop
from agent_runtime.deterministic_fallback_mode_contracts import short_setup_fallback
from agent_runtime.repair_candidates import reject_candidate
from agent_runtime.repair_reflection import build_audit_retry_instruction


MANUFACTURING = '製造業情境紅線：必須討論產能、CapEx、折舊、良率與客戶議價風險。'


def context_for(key=19):
    from workflow_context import legacy_context_from_graph
    from workflow_services import initialize_graph_state, create_default_workflow_services
    context = legacy_context_from_graph(initialize_graph_state(
        {'ticker': 'TEST', 'current_price': 26}, pipeline_id='v3'),
        create_default_workflow_services(rotator=object()))
    context['analyses'] = {key: '前次決策正文'}
    context['structured_outputs'] = {key: {'recommendation': {
        '建議': '持有', '長期目標（12個月）': 'NT$18–24'}, 'short_setup': short_setup_fallback()}}
    return context


@pytest.mark.parametrize('key', [19, '19'])
def test_immediate_quality_retry_sees_rejected_values_before_clearing_output(key, monkeypatch):
    context = context_for(key)
    before = copy.deepcopy(context)
    monkeypatch.setattr(quality_retry, 'quality_retry_model_sequence', lambda *_: ['configured-model'])
    quality_retry.install_quality_retry_context(context, 19, [MANUFACTURING])
    instruction = context['_audit_retry_instruction']
    assert 'NT$18–24' in instruction
    assert '21' in instruction and '-19.2%' in instruction and '26' in instruction
    assert MANUFACTURING in instruction
    assert '不可為通過門檻而調高目標價' in instruction
    assert 'market_context_assessment' in instruction
    assert not context['structured_outputs']
    assert context['data'] == before['data']


@pytest.mark.parametrize('asynchronous', [False, True])
def test_quality_failure_survives_graph_roundtrip_and_audit_rewrites(asynchronous, monkeypatch):
    context = context_for()
    monkeypatch.setattr(quality_retry, 'quality_retry_model_sequence', lambda *_: ['configured-model'])
    prior = quality_retry.install_quality_retry_context(context, 19, [MANUFACTURING])
    quality_retry.restore_quality_retry_context(context, prior)
    # Immediate rewrite fixes manufacturing but introduces negative HOLD return.
    context['structured_outputs'] = context_for()['structured_outputs']
    from workflow_context import graph_delta_from_legacy_context, legacy_context_from_graph
    from workflow_services import initialize_graph_state, create_default_workflow_services
    state = initialize_graph_state(context['data'], pipeline_id='v3')
    state.update(json.loads(json.dumps(graph_delta_from_legacy_context(context))))
    context = legacy_context_from_graph(state, create_default_workflow_services(rotator=object()))
    calls = []

    def provider(agent, data, ctx, rotator, **kwargs):
        calls.append(ctx['_audit_retry_instruction'])
        ctx['structured_outputs'][19] = {
            'recommendation': {'建議': '持有', '長期目標（12個月）': 'NT$20' if len(calls) == 1 else 'NT$28'},
            'short_setup': short_setup_fallback(),
        }
        return '## 決策\n依據已提供資料重新評估。'

    async def provider_async(*args, **kwargs):
        return provider(*args, **kwargs)

    monkeypatch.setattr(repair_loop, 'run_single_agent', provider)
    monkeypatch.setattr(repair_loop, 'run_single_agent_async', provider_async)
    monkeypatch.setattr(repair_loop, 'repair_429_circuit_state', lambda _: {'open': False})
    args = 19, context['data'], context, object(), ['建議/報酬矛盾：現價26、目標21']
    ok, message = asyncio.run(repair_loop._repair_agent_output_async(*args)) if asynchronous else repair_loop._repair_agent_output(*args)
    assert ok, message
    assert len(calls) == 2
    assert all(MANUFACTURING in prompt for prompt in calls)
    assert '-19.2%' in calls[0] and '-23.1%' in calls[1]
    assert context['repair_attempt_counts'][19] == 2
    assert context['structured_outputs'][19]['recommendation']['長期目標（12個月）'] == 'NT$28'


def test_history_is_bounded_and_does_not_follow_changed_inputs():
    context = context_for()
    for n in range(30):
        reject_candidate(context, 19, context['data'], f'draft {n}', [f'歷史退件-{n}'])
    instruction = build_audit_retry_instruction(19, ['目前問題'], data=context['data'], context=context)
    assert '歷史退件-29' in instruction
    assert '歷史退件-0\n' not in instruction
    context['data'] = {**context['data'], 'current_price': 100}
    instruction = build_audit_retry_instruction(19, ['目前問題'], data=context['data'], context=context)
    assert '歷史退件-' not in instruction


@pytest.mark.parametrize('price', [None, 0, float('nan'), float('inf'), 'invalid'])
def test_diagnostic_does_not_fabricate_missing_or_invalid_prices(price):
    context = context_for()
    context['data']['current_price'] = price
    before = copy.deepcopy(context['structured_outputs'])
    instruction = build_audit_retry_instruction(19, ['需修正'], data=context['data'], context=context)
    assert '-19.2%' not in instruction
    assert context['structured_outputs'] == before
