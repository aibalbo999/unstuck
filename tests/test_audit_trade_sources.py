"""Audit rewrites use the existing attempt budget to fix new source defects."""
import asyncio
import copy
import json
import pytest
from agent_runtime import repair_loop
from agent_runtime.repair_state import repair_contract_issues
from structured_output_runtime import process_agent_response
from trade_source_contract import source_block, bind_source_prompt
from test_trade_catalog_expansion import data
from test_trade_source_completion import setup_payload


def context():
    value = data()
    ctx = {'pipeline_id': 'v4', 'ticker': value['ticker'], 'data': value,
           'structured_outputs': {}, 'analyses': {22: 'kept', 23: 'kept'}}
    block, catalog, fp = source_block(value)
    bind_source_prompt(ctx, block, block, catalog, fp)
    payload = setup_payload()
    payload.update(trade_direction='Neutral', core_catalyst='外資持續買超，暫時觀望。',
                   support_source_refs=[], resistance_source_refs=[], catalyst_source_refs=[])
    ctx['analyses'][24] = process_agent_response(24, json.dumps(payload), ctx)
    return ctx, payload


def test_audit_detects_source_defect_in_its_own_rewrite():
    ctx, _ = context()
    assert any('來源引用' in x for x in repair_contract_issues(24, ctx))


@pytest.mark.parametrize('kind', ['no_evidence', 'stale_input', 'stale_assessment', 'local_fallback'])
def test_source_repair_does_not_spend_on_unknown_or_local_evidence(kind):
    ctx, _ = context()
    if kind == 'no_evidence': ctx['_trade_source_manifest']['catalog'] = {}
    if kind == 'stale_input': ctx['data']['current_price'] = 999
    if kind == 'stale_assessment': ctx['structured_outputs'][24]['source_assessment']['source_fingerprint'] = 'different'
    if kind == 'local_fallback': ctx['structured_outputs'][24]['source_assessment']['output_completion'] = {'status': 'local_fallback'}
    assert not any('來源引用' in x for x in repair_contract_issues(24, ctx))


@pytest.mark.parametrize('asynchronous', [False, True])
@pytest.mark.parametrize('repaired', [False, True])
def test_audit_uses_at_most_original_two_attempts_then_explicit_fallback(monkeypatch, asynchronous, repaired):
    ctx, payload = context()
    calls = []
    def model(agent, value, context, rotator, **kwargs):
        calls.append(agent)
        candidate = copy.deepcopy(payload)
        if repaired and len(calls) == 2:
            candidate['core_catalyst'] = '等待法人連續買超後再重新評估。'
        return process_agent_response(24, json.dumps(candidate), context)
    async def async_model(*args, **kwargs): return model(*args, **kwargs)
    monkeypatch.setattr(repair_loop, 'run_single_agent', model)
    monkeypatch.setattr(repair_loop, 'run_single_agent_async', async_model)
    monkeypatch.setattr(repair_loop, 'get_audit_rewrite_model_sequence', lambda *a: ['offline'])
    monkeypatch.setattr(repair_loop, 'repair_429_circuit_state', lambda *a: {})
    for name in ('validate_analysis_output', 'validate_company_identity', 'validate_prompt_leakage'):
        monkeypatch.setattr(repair_loop, name, lambda *a: [])
    args = (24, ctx['data'], ctx, None, ['original audit issue'])
    ok, _ = asyncio.run(repair_loop._repair_agent_output_async(*args)) if asynchronous else repair_loop._repair_agent_output(*args)
    assert ok
    assert calls == [24, 24]
    assessment = ctx['structured_outputs'][24]['source_assessment']
    if repaired:
        assert assessment['status'] == 'observation'
        assert assessment['repair_attempted'] is True
    else:
        assert assessment['status'] == 'degraded'
        assert assessment['output_completion']['status'] == 'local_fallback'
