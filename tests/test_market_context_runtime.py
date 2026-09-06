"""The accepted output keeps the manifest for its actual model attempt."""

import asyncio
import copy
from types import SimpleNamespace

import pytest

from test_market_context_manifest import source_data


@pytest.mark.parametrize("sync", [False, True])
def test_fallback_output_keeps_fallback_manifest_and_not_failed_primary(monkeypatch, sync):
    from agent_runtime import single_agent, prompting
    from agent_runtime.retry_policy import AgentMissingModelError
    from market_context_manifest import prompt_fingerprint

    data = source_data()
    context = {"pipeline_id": "v1", "data": data, "market_context_contract_version": "market_context.v1"}
    attempted = {}
    monkeypatch.setattr(single_agent, "get_runtime_model_sequence", lambda *a: ["primary", "fallback"])
    monkeypatch.setattr(single_agent, "get_cached_agent_step", lambda *a: None)
    monkeypatch.setattr(single_agent, "store_cached_agent_step", lambda *a, **k: None)
    monkeypatch.setattr(prompting, "get_agent_prompt_token_budget", lambda *a: 0)

    def invoke(agent, ctx, rotator, model, prompt, **kwargs):
        attempted[model] = prompt
        if model == "primary":
            raise AgentMissingModelError("fixture route absent")
        return "Final decision waits for confirmation. " * 15

    async def invoke_async(*args, **kwargs):
        return invoke(*args, **kwargs)

    monkeypatch.setattr(single_agent, "_run_agent_once", invoke)
    monkeypatch.setattr(single_agent, "_run_agent_once_async", invoke_async)

    async def run():
        if sync:
            return single_agent.run_single_agent(7, data, context, SimpleNamespace(keys=["fixture"]))
        return await single_agent.run_single_agent_async(7, data, context, SimpleNamespace(keys=["fixture"]))

    assert "Final decision" in asyncio.run(run())
    manifest = context.get("market_context_manifests", {}).get(7)
    assert manifest is not None, "Successful output must adopt its actual prompt manifest"
    assert manifest["prompt_hash"] == prompt_fingerprint(attempted["fallback"])
    assert len(manifest["sources"]["international_news_context"]["visible_refs"]) == 3
    assert manifest["prompt_hash"] != prompt_fingerprint(attempted["primary"])


def test_cache_roundtrip_preserves_independent_manifest_and_requires_match(monkeypatch):
    from agent_runtime import step_cache
    from market_context_manifest import build_source_blocks, build_market_context_manifest

    data = source_data()
    blocks = build_source_blocks(data, agent_num=7)
    prompt = "\n".join(block["text"] for block in blocks)
    manifest = build_market_context_manifest(data, prompt, blocks, agent_num=7)
    context = {"data": data, "market_context_contract_version": "market_context.v1",
               "market_context_manifests": {7: manifest}, "_market_context_attempt_manifests": {7: manifest},
               "structured_outputs": {7: {"analysis_markdown": "decision"}}}
    saved = {}
    monkeypatch.setattr(step_cache, "AGENT_STEP_CACHE_ENABLED", True)
    monkeypatch.setattr(step_cache, "AGENT_STEP_CACHE_SECONDS", 100)
    monkeypatch.setattr(step_cache, "set_cache_json", lambda key, payload, ttl: saved.update(copy.deepcopy(payload)))
    step_cache.store_cached_agent_step("fixture", agent_num=7, context=context, model_id="fixture", text="decision")
    assert saved.get("market_context_manifest") == manifest
    assert step_cache.cached_market_context_matches(context, 7, saved, prompt)
    assert not step_cache.cached_market_context_matches(context, 7, {"text": "legacy"}, prompt)
    changed = copy.deepcopy(saved)
    changed["market_context_manifest"]["prompt_hash"] = "0" * 64
    assert not step_cache.cached_market_context_matches(context, 7, changed, prompt)
    restored = {"market_context_contract_version": "market_context.v1"}
    step_cache.restore_cached_agent_step(restored, 7, saved)
    saved["market_context_manifest"]["items"].clear()
    assert restored["market_context_manifests"][7]["items"]


def test_failed_primary_structured_output_cannot_be_adopted_as_plain_fallback(monkeypatch):
    from agent_runtime import single_agent, prompting
    from agent_runtime.retry_policy import AgentMissingModelError

    data = source_data()
    context = {"pipeline_id": "v1", "data": data, "market_context_contract_version": "market_context.v1"}
    monkeypatch.setattr(single_agent, "get_runtime_model_sequence", lambda *a: ["primary", "fallback"])
    monkeypatch.setattr(single_agent, "get_cached_agent_step", lambda *a: None)
    monkeypatch.setattr(single_agent, "store_cached_agent_step", lambda *a, **k: None)
    monkeypatch.setattr(prompting, "get_agent_prompt_token_budget", lambda *a: 0)

    async def invoke(agent, ctx, rotator, model, prompt, **kwargs):
        if model == "primary":
            ctx.setdefault("structured_outputs", {})[agent] = {"analysis_markdown": "PRIMARY_REJECTED", "recommendation": {"建議": "持有"}}
            raise AgentMissingModelError("fixture route absent after rejected response")
        return "FALLBACK_ACCEPTED " * 30

    monkeypatch.setattr(single_agent, "_run_agent_once_async", invoke)
    result = asyncio.run(single_agent.run_single_agent_async(7, data, context, SimpleNamespace(keys=["fixture"])))
    assert "FALLBACK_ACCEPTED" in result
    assert "PRIMARY_REJECTED" not in result
    assert 7 not in context.get("structured_outputs", {})


def test_plain_cache_restore_clears_previous_structured_output_and_manifest():
    from agent_runtime.step_cache import restore_cached_agent_step

    context = {"market_context_contract_version": "market_context.v1", "structured_outputs": {"7": {"stale": True}},
               "market_context_manifests": {7: {"stale": True}, "7": {"stale": True}}}
    restore_cached_agent_step(context, 7, {"text": "cached plain output"})
    assert not context["structured_outputs"]
    assert not context["market_context_manifests"]


def test_cancelled_market_attempt_restores_prior_output_without_touching_other_agents():
    from market_context_manifest import market_output_attempt

    context = {"market_context_contract_version": "market_context.v1", "structured_outputs": {7: {"prior": True}, 6: {"safe": True}},
               "market_context_manifests": {7: {"prior": True}}}
    original = copy.deepcopy(context)
    with pytest.raises(asyncio.CancelledError):
        with market_output_attempt(context, 7):
            assert 7 not in context["structured_outputs"]
            context["structured_outputs"][7] = {"new": True}
            raise asyncio.CancelledError()
    assert context == original


def test_legacy_attempt_preserves_existing_runtime_behavior():
    from market_context_manifest import market_output_attempt

    context = {"structured_outputs": {7: {"legacy": True}}}
    with pytest.raises(ValueError):
        with market_output_attempt(context, 7):
            context["structured_outputs"][7] = {"legacy update": True}
            raise ValueError("legacy failure")
    assert context["structured_outputs"][7] == {"legacy update": True}
