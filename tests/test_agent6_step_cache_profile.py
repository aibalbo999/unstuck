"""Agent 6 generation settings bind its normalized cache without touching peers."""
from copy import deepcopy

import pytest

from agent_runtime import generation_config, step_cache


def inputs():
    data = {'ticker': '1623.TW', 'company_name': '大東電'}
    context = {'ticker': '1623.TW', 'data': deepcopy(data), 'pipeline_id': 'v1',
               'analyses': {5: 'Original growth analysis'}, 'structured_outputs': {},
               'data_snapshot_hash': 'frozen-input-v1', 'prompt_version': 'same-prompt'}
    return data, context


def key(role=6, *, data=None, context=None, model='gemini-3.6-flash', prompt='Same prompt'):
    if data is None or context is None:
        data, context = inputs()
    return step_cache.build_agent_step_cache_key(role, data, context, model, prompt)


def select_temperature(monkeypatch, temperature):
    profile = {**generation_config.generation_profile(6), 'temperature': temperature}
    monkeypatch.setitem(generation_config.AGENT_GENERATION_PROFILES, 6, profile)


def test_agent6_temperature_change_invalidates_normalized_step(monkeypatch):
    select_temperature(monkeypatch, .60)
    before = key()
    select_temperature(monkeypatch, .25)
    assert key() != before


@pytest.mark.parametrize('role', [r for r in range(1, 25) if r != 6])
def test_only_agent6_profile_change_keeps_every_other_role_key_unchanged(monkeypatch, role):
    select_temperature(monkeypatch, .60)
    before = key(role)
    select_temperature(monkeypatch, .25)
    assert key(role) == before


def test_identical_profile_values_have_a_stable_key_regardless_of_dict_order(monkeypatch):
    profile = generation_config.generation_profile(6)
    before = key()
    monkeypatch.setitem(generation_config.AGENT_GENERATION_PROFILES, 6,
                        dict(reversed(list(profile.items()))))
    assert key() == before


@pytest.mark.parametrize('field,value', [('top_p', .90), ('max_output_tokens', 4096)])
def test_other_agent6_generation_changes_also_invalidate_its_step(monkeypatch, field, value):
    before = key()
    profile = {**generation_config.generation_profile(6), field: value}
    monkeypatch.setitem(generation_config.AGENT_GENERATION_PROFILES, 6, profile)
    assert key() != before


@pytest.mark.parametrize('changed', ['model', 'prompt', 'snapshot', 'upstream'])
def test_model_prompt_input_and_upstream_revisions_still_invalidate_step(changed):
    data, context = inputs()
    before = key(data=data, context=context)
    model, prompt = 'gemini-3.6-flash', 'Same prompt'
    if changed == 'model':
        model = 'gemini-3.8-flash'
    elif changed == 'prompt':
        prompt = 'Revised prompt'
    elif changed == 'snapshot':
        context['data_snapshot_hash'] = 'frozen-input-v2'
    else:
        context['analyses'][5] = 'Revised growth analysis'
    assert key(data=data, context=context, model=model, prompt=prompt) != before


def test_key_calculation_has_no_cache_io_and_preserves_inputs_and_output_budget(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Key construction must not access cache storage')
    monkeypatch.setattr(step_cache, 'get_cache_json', forbidden)
    monkeypatch.setattr(step_cache, 'set_cache_json', forbidden)
    data, context = inputs()
    before_data, before_context = deepcopy(data), deepcopy(context)
    profile = generation_config.generation_profile(6)
    before = key(data=data, context=context)
    assert key(data=data, context=context) == before
    assert data == before_data and context == before_context
    assert generation_config.generation_profile(6) == profile
    assert profile['max_output_tokens'] == 8192
