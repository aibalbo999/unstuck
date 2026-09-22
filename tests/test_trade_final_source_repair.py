"""Final quality/identity rewrites must receive the single source repair budget."""
import asyncio
import json
import pytest
from agent_runtime import quality_gates
from structured_output_runtime import process_agent_response
from test_trade_source_completion import setup_payload
from test_trade_source_repair_integration_review import context


def run_case(monkeypatch, *, initially_degraded=False, invalid_repair=False):
    ctx = context()
    calls = []
    async def noop(*args, **kwargs): pass
    async def skip(*args, **kwargs): return None
    monkeypatch.setattr(quality_gates, 'get_runtime_model_sequence', lambda *a: ['offline'])
    monkeypatch.setattr(quality_gates, 'apply_deterministic_agent_skip', skip)
    monkeypatch.setattr(quality_gates, 'ensure_context_digest_async', noop)
    monkeypatch.setattr(quality_gates, 'ensure_agent_rag_context_async', noop)
    monkeypatch.setattr(quality_gates, 'emit_status_async', noop)
    monkeypatch.setattr(quality_gates, 'sanitize_model_output', lambda x: x)
    monkeypatch.setattr(quality_gates, 'validate_prompt_leakage', lambda *a: [])
    monkeypatch.setattr(quality_gates, 'validate_company_identity', lambda *a: [])
    monkeypatch.setattr(quality_gates, 'append_quality_warnings', lambda agent, text, data: text)
    monkeypatch.setattr(quality_gates, 'validate_analysis_output',
                        lambda *a: ['original quality issue'] if len(calls) == 1 else
                        ['bad repair quality'] if invalid_repair and len(calls) == 3 else [])
    async def model(agent, data, context, rotator):
        calls.append('source' if context.get('_trade_source_repair_attempted') else 'normal')
        payload = setup_payload()
        if (len(calls) == 1 and initially_degraded) or (len(calls) == 2 and not initially_degraded):
            payload['support_source_refs'] = []
        return process_agent_response(agent, json.dumps(payload), context)
    monkeypatch.setattr(quality_gates, 'run_single_agent_async', model)
    # Keep this test's provider boundary isolated while running the actual quality
    # retry / structured parser / final source-repair orchestration.
    monkeypatch.setattr(__import__('agent_runtime.quality_retry', fromlist=['x']),
                        'get_runtime_model_sequence', lambda *a: ['offline'])
    asyncio.run(quality_gates.run_agent_with_quality_gates_async(24, {}, ctx, None))
    return ctx, calls


def test_source_repair_follows_quality_rewrite(monkeypatch):
    ctx, calls = run_case(monkeypatch)
    assert calls == ['normal', 'normal', 'source']
    assert ctx['structured_outputs'][24]['source_assessment']['status'] == 'source_bound'
    assert ctx['structured_outputs'][24]['source_assessment']['repair_attempted'] is True


def test_quality_rewrite_that_fixes_sources_does_not_spend_extra_source_repair(monkeypatch):
    ctx, calls = run_case(monkeypatch, initially_degraded=True)
    assert calls == ['normal', 'normal']
    assert ctx['structured_outputs'][24]['source_assessment']['status'] == 'source_bound'


def test_final_source_candidate_cannot_bypass_quality_checks(monkeypatch):
    ctx, calls = run_case(monkeypatch, invalid_repair=True)
    assert calls == ['normal', 'normal', 'source']
    assert any('bad repair quality' in x for x in ctx['blocking_issues'])
