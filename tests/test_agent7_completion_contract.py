"""Research fallback must reserve room for a complete evidenced JSON response."""
import asyncio

import pytest

from agent_runtime import generation_config as generation
from agent_runtime import step_cache
from google_prompt_safety import sanitize_google_generation_config


@pytest.mark.parametrize('model', ['gemini-3-flash-preview', 'google:gemini-3-flash-preview', 'models/gemini-3-flash-preview'])
def test_preview_research_completion_bounds_thinking_without_raising_token_budget(model):
    base = generation.build_generation_config(7, 'unchanged system')
    original = base.model_dump(exclude_none=True)
    adjusted = generation.apply_model_generation_policy(base, model, 7)
    assert adjusted.thinking_config.thinking_level.value == 'LOW'
    assert generation.generation_event_metadata(7, model)['thinking_level'] == 'low'
    actual = adjusted.model_dump(exclude_none=True)
    actual.pop('thinking_config')
    assert actual == original
    assert adjusted.max_output_tokens == 6144
    assert base.model_dump(exclude_none=True) == original
    delivered = sanitize_google_generation_config(adjusted)
    assert delivered.thinking_config.thinking_level.value == 'LOW'
    assert delivered.response_schema == sanitize_google_generation_config(base).response_schema


def test_research_change_leaves_other_routes_and_roles_unchanged():
    config = generation.build_generation_config(7)
    for model in ['gemini-3.6-flash', 'gemma-4-31b-it', 'unknown-model', 'openai:gemini-3-flash-preview']:
        assert generation.apply_model_generation_policy(config, model, 7) is config
    assert generation.apply_model_generation_policy(config, 'gemini-3.8-flash', 7).thinking_config.thinking_level.value == 'MEDIUM'
    assert generation.apply_model_generation_policy(config, 'gemini-3.5-flash-lite', 7).thinking_config.thinking_level.value == 'MEDIUM'
    assert generation.apply_model_generation_policy(config, 'gemini-3-flash-preview', 16) is config


@pytest.mark.parametrize('mode', ['sync', 'async', 'stream'])
def test_delivered_research_request_keeps_sources_and_one_call(monkeypatch, mode):
    prompt = '完整來源起點\n' + '原始來源 2026-09-25 營收55億元 0 false null\n' * 200 + '完整來源終點'
    observed = []
    def generate(key, model, text, config, **kwargs):
        observed.append((text, config))
        return object()
    async def generate_async(*args, **kwargs):
        return generate(*args, **kwargs)
    monkeypatch.setattr(generation, 'generate_content', generate)
    monkeypatch.setattr(generation, 'generate_content_async', generate_async)
    monkeypatch.setattr(generation, 'generate_content_stream_async', generate_async)
    if mode == 'sync':
        generation._generate_content('synthetic', 'gemini-3-flash-preview', 7, prompt)
    elif mode == 'async':
        asyncio.run(generation._generate_content_async('synthetic', 'gemini-3-flash-preview', 7, prompt))
    else:
        asyncio.run(generation._generate_content_stream_async('synthetic', 'gemini-3-flash-preview', 7, prompt))
    assert len(observed) == 1 and observed[0][0] == prompt
    config = observed[0][1]
    assert config.thinking_config.thinking_level.value == 'LOW'
    assert config.max_output_tokens == 6144
    assert config.response_schema == generation.build_generation_config(7).response_schema
    system = config.system_instruction
    assert '完整 JSON' in system
    assert 'assumption_reconciliation' in system and '逐字' in system
    assert 'market_context_assessment' in system and 'source_refs' in system
    assert '不得為通過檢查改寫研究分類或補造價格' in system
    assert 'sufficiently long and detailed' not in system


def test_research_system_rule_preserves_quality_priority_and_other_preview_roles():
    from research_assumption_contract import AssumptionCheck, TOPICS
    system = generation.google_safe_agent_system_instruction(7, 'gemini-3-flash-preview')
    assert '完整性與品質規則優先於此篇幅目標' in system
    assert '資料不足' in system and '反證' in system
    schema_topics = AssumptionCheck.model_json_schema()['properties']['topic']['enum']
    assert list(TOPICS) == schema_topics
    assert '、'.join(schema_topics) in system
    assert 'pending_recalculation' in system
    assert 'comprehensive, highly detailed, and complete analysis' in generation.google_safe_agent_system_instruction(6, 'gemini-3-flash-preview')


def test_research_step_identity_changes_with_completion_policy_only_for_agent7(monkeypatch):
    data={'ticker':'TEST'};context={'pipeline_id':'v1'}
    old7=step_cache.build_agent_step_cache_key(7,data,context,'gemini-3-flash-preview','same prompt')
    old19=step_cache.build_agent_step_cache_key(19,data,context,'gemini-3-flash-preview','same prompt')
    monkeypatch.setattr(generation,'AGENT7_COMPLETION_POLICY','test-policy-change')
    assert step_cache.build_agent_step_cache_key(7,data,context,'gemini-3-flash-preview','same prompt') != old7
    assert step_cache.build_agent_step_cache_key(19,data,context,'gemini-3-flash-preview','same prompt') == old19
