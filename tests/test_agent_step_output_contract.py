"""Changed output contracts must not reuse previously normalized step outputs."""

import hashlib
import json

import pytest

from agent_runtime import step_cache


def _inputs():
    return {"ticker": "TEST", "current_price": 30}, {
        "ticker": "TEST", "data_snapshot_hash": "fixed-snapshot",
        "prompt_version": "fixed-prompt", "market_context_contract_version": None,
    }


def _legacy_key(agent, data, context):
    # Frozen pre-release key contract: intentionally lacks an output version.
    fields = {
        "ticker": "TEST", "data_snapshot_hash": "fixed-snapshot",
        "agent_id": str(agent), "prompt_version": "fixed-prompt",
        "model_id": "gemini-test",
        "prompt_hash": hashlib.sha256(b"unchanged source").hexdigest(),
        "upstream_input_hash": step_cache.upstream_input_hash(agent, context),
        "market_context_contract_version": None,
    }
    encoded = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "agent_step:" + hashlib.sha256(encoded.encode()).hexdigest()


@pytest.mark.parametrize("agent", [7, 16, 18, 19, 20, 21, 24])
def test_changed_output_roles_do_not_reuse_legacy_keys(agent):
    data, context = _inputs()
    current = step_cache.build_agent_step_cache_key(agent, data, context, "gemini-test", "unchanged source")
    assert current != _legacy_key(agent, data, context)


@pytest.mark.parametrize("agent", [1, 4, 13, 17, 22])
def test_unaffected_roles_keep_exact_legacy_keys(agent):
    data, context = _inputs()
    current = step_cache.build_agent_step_cache_key(agent, data, context, "gemini-test", "unchanged source")
    assert current == _legacy_key(agent, data, context)


@pytest.mark.parametrize("agent", [7, 16, 18, 19, 20, 21, 24])
def test_output_version_bump_changes_only_affected_role_keys(monkeypatch, agent):
    data, context = _inputs()
    before = step_cache.build_agent_step_cache_key(agent, data, context, "gemini-test", "unchanged source")
    monkeypatch.setattr(step_cache, "AGENT_OUTPUT_CONTRACT_VERSION", "future-contract")
    after = step_cache.build_agent_step_cache_key(agent, data, context, "gemini-test", "unchanged source")
    assert (before != after) is (agent in {7, 16, 18, 19, 20, 21})
