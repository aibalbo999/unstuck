from copy import deepcopy
import json

import pytest

from memo_output_completion import incomplete_memo_roles
from structured_output_runtime import process_agent_response


@pytest.mark.parametrize('agent', [2, 3, 4, 7, 12, 13, 14, 16, 18, 19, 21, 24])
def test_deterministic_fallback_cannot_erase_observed_truncation(agent, monkeypatch):
    from agent_runtime.deterministic_fallbacks import _deterministic_structured_fallback
    from agent_runtime import step_cache
    context = {'pipeline_id': 'v2', 'agent_sequence': [agent], 'analyses': {}, 'data': {}}
    text = process_agent_response(agent, '{"analysis_markdown":"truncated', context,
                                  completion_diagnostics={'finish_reasons': ['MAX_TOKENS']})
    context['analyses'][agent] = text
    before = deepcopy(context)
    assert incomplete_memo_roles(context)
    assert not _deterministic_structured_fallback(agent, {}, context, text)[0]
    assert context == before
    writes = []
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_ENABLED', True)
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_SECONDS', 60)
    monkeypatch.setattr(step_cache, 'set_cache_json', lambda *args: writes.append(args))
    step_cache.store_cached_agent_step('offline', agent_num=agent, context=context, model_id='offline', text=text)
    assert not writes


@pytest.mark.parametrize('agent', [3, 4, 14, 21, 22, 23, 24])
@pytest.mark.parametrize('diagnostics', [None, {}, {'stream_completed': True}])
@pytest.mark.parametrize('transformed', [False, True])
@pytest.mark.parametrize('original_diagnostics', [
    {'finish_reasons': ['MAX_TOKENS']}, {'finish_reasons': ['SAFETY']},
    {'finish_reasons': ['STOP'], 'stream_completed': False},
])
def test_special_contract_retains_provider_fact_after_reparse(agent, diagnostics, transformed, original_diagnostics):
    if agent == 24:
        from test_trade_source_completion import setup_payload
        payload = setup_payload()
    elif agent in {22, 23}:
        from test_memo_output_completion import raw
        payload = raw()
    else:
        from test_assessment_raw_completion import payload as assessment_payload
        payload = assessment_payload(agent)
    raw = json.dumps(payload, ensure_ascii=False)
    if transformed:
        raw = '<think>內部草稿</think>\n' + raw
    context = {'pipeline_id': 'v4', 'data': {}}
    text = process_agent_response(agent, raw, context, completion_diagnostics=original_diagnostics)
    before = deepcopy(incomplete_memo_roles(context))
    assert before
    process_agent_response(agent, text if transformed else raw, context, completion_diagnostics=diagnostics)
    assert incomplete_memo_roles(context) == before


def test_partial_candidate_identity_can_be_snapshotted_without_prediction_eligibility():
    from report_publication_identity import replay_context, publication_identity
    context = {'data': {'ticker': '2367.TW'}, 'pipeline_id': 'v2'}
    process_agent_response(12, '截斷文字', context, completion_diagnostics={'finish_reasons': ['MAX_TOKENS']})
    prepared = replay_context(context, '2026-10-18T15:03:16+00:00')
    assert prepared['publication_generated_at'] == '2026-10-18T15:03:16+00:00'
    assert prepared['publication_identity']['kind'] == 'partial_analysis'
    assert prepared['decision_validity_status'] == 'partial_analysis'
    assert publication_identity(prepared)['prediction_eligible'] is False


@pytest.mark.parametrize('agent', [2, 12, 13])
def test_observed_truncating_fallbacks_bound_thinking_without_raising_output_budget(agent):
    from agent_runtime.generation_config import build_generation_config, apply_model_generation_policy, generation_profile
    for model in ('gemini-3-flash-preview', 'gemini-3.6-flash', 'gemini-3.8-flash'):
        base = build_generation_config(agent)
        config = apply_model_generation_policy(base, model, agent)
        assert config.thinking_config.thinking_level.lower() == 'low'
        assert config.max_output_tokens == generation_profile(agent)['max_output_tokens']
        assert config.tools == base.tools
        assert config.automatic_function_calling == base.automatic_function_calling
