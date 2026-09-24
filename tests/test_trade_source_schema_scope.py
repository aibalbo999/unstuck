"""The provider schema and rendered instruction must describe the enforced catalog."""
from structured_output_risk_models import SwingTradeSetup
from structured_outputs import build_structured_output_instruction


def test_trade_source_descriptions_use_the_enforced_visible_catalog():
    properties = SwingTradeSetup.model_json_schema()['properties']
    instruction = build_structured_output_instruction(24)
    for role in ('support_source_refs', 'resistance_source_refs', 'catalyst_source_refs'):
        description = properties[role]['description']
        assert 'trade-source' in description
        assert 'short_term_market_context' in description
        assert 'State 或' not in description
        assert '上游 evidence' not in description
        line = next(line for line in instruction.splitlines() if f'"{role}"' in line)
        assert 'short_term_market_context' in line
        assert 'State' not in line
    assert '完整可見' in instruction


def test_source_guidance_schema_does_not_reuse_old_normalized_agent24_cache(monkeypatch):
    from agent_runtime import step_cache
    from test_agent_step_output_contract import _inputs, _legacy_key
    data, context = _inputs()
    previous = _legacy_key(24, data, context, extra_fields={
        'institutional_evidence_contract': 'typed-flow:v2',
        'trade_source_contract_version': 'trade-sources:v2-completion:v7',
    })
    cache = {previous: {'text': 'normalized under permissive State reference guidance'}}
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_ENABLED', True)
    monkeypatch.setattr(step_cache, 'get_cache_json', cache.get)
    current = step_cache.build_agent_step_cache_key(24, data, context, 'gemini-test', 'unchanged source')
    assert step_cache.get_cached_agent_step(current) is None
    # Agent23 shares institutional input but its output guidance did not change.
    assert step_cache.build_agent_step_cache_key(23, data, context, 'gemini-test', 'unchanged source') == _legacy_key(
        23, data, context, extra_fields={'institutional_evidence_contract': 'typed-flow:v2'})
