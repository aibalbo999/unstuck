"""Candidate routes remain opt-in and cannot escape explicit role overrides."""

import asyncio
import json

import config
import pytest
from settings.model_candidates import load_lite_candidate_flags

from agent_runtime import repair_loop, routing
from agent_runtime.quality_retry import quality_retry_model_sequence


LITE = "gemini-3.5-flash-lite"
BASE = ["gemini-3.8-flash", "gemini-3.6-flash"]
CRITICAL = (4, 7, 14, 16, 19, 24)


@pytest.fixture(autouse=True)
def routes(monkeypatch):
    monkeypatch.setattr(routing, "AGENT_MODELS", {agent: BASE[0] for agent in (*CRITICAL, 11)})
    monkeypatch.setattr(routing, "AGENT_FALLBACK_MODELS", {agent: BASE[1:] for agent in (*CRITICAL, 11)})
    monkeypatch.setattr(routing, "AUDIT_MODEL", BASE[0])
    monkeypatch.setattr(routing, "AUDIT_FALLBACK_MODELS", BASE[1:])
    monkeypatch.setattr(config, "CRITICAL_LITE_FALLBACK_AGENTS", {}, raising=False)
    monkeypatch.setattr(config, "AUDIT_REWRITE_LITE_FALLBACK_AGENTS", {}, raising=False)


@pytest.mark.parametrize("agent", CRITICAL)
def test_explicit_role_opt_in_adds_lite_to_runtime_and_quality_route(monkeypatch, agent):
    monkeypatch.setattr(config, "CRITICAL_LITE_FALLBACK_AGENTS", {agent: True}, raising=False)
    assert routing.get_runtime_model_sequence(agent, {}) == [*BASE, LITE]
    assert quality_retry_model_sequence(agent, {}) == [*BASE, LITE]
    assert routing.get_audit_model_sequence() == BASE


@pytest.mark.parametrize("flag", [False, None, "true", "false", 1, {}, []])
def test_non_boolean_opt_in_is_closed(monkeypatch, flag):
    monkeypatch.setattr(config, "CRITICAL_LITE_FALLBACK_AGENTS", {24: flag}, raising=False)
    assert routing.get_runtime_model_sequence(24, {}) == BASE


def test_candidate_defaults_and_unknown_role_are_closed(monkeypatch):
    for agent in CRITICAL:
        assert routing.get_runtime_model_sequence(agent, {}) == BASE
    monkeypatch.setattr(config, "CRITICAL_LITE_FALLBACK_AGENTS", {11: True, 999: True}, raising=False)
    assert routing.get_runtime_model_sequence(11, {}) == BASE


@pytest.mark.parametrize("override", [[], ["explicit-only"], [LITE, LITE]])
def test_explicit_context_route_is_never_expanded(monkeypatch, override):
    monkeypatch.setattr(config, "CRITICAL_LITE_FALLBACK_AGENTS", {24: True}, raising=False)
    context = {"_model_sequence_override": {24: override}}
    assert routing.get_runtime_model_sequence(24, context) == list(dict.fromkeys(override))


def test_opt_in_does_not_duplicate_configured_candidate(monkeypatch):
    monkeypatch.setattr(config, "CRITICAL_LITE_FALLBACK_AGENTS", {24: True}, raising=False)
    monkeypatch.setitem(routing.AGENT_FALLBACK_MODELS, 24, [LITE, BASE[1]])
    assert routing.get_runtime_model_sequence(24, {}) == [BASE[0], LITE, BASE[1]]


@pytest.mark.parametrize("agent", [4, 7, 11, 14, 16, 19, 24])
def test_audit_rewrite_candidate_is_role_scoped_and_not_reflection(monkeypatch, agent):
    monkeypatch.setattr(config, "AUDIT_REWRITE_LITE_FALLBACK_AGENTS", {agent: True})
    assert routing.get_audit_rewrite_model_sequence(agent) == [*BASE, LITE]
    assert routing.get_audit_rewrite_model_sequence(999) == BASE
    assert routing.get_audit_model_sequence() == BASE
    assert routing.get_runtime_model_sequence(agent, {}) == BASE


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("override", [None, [], ["explicit-only"]])
def test_rewrite_loop_uses_separate_audit_policy_then_restores_prior_override(monkeypatch, asynchronous, override):
    monkeypatch.setattr(config, "AUDIT_REWRITE_LITE_FALLBACK_AGENTS", {24: True})
    monkeypatch.setattr(repair_loop, "repair_429_circuit_state", lambda _: {"open": False})
    seen = []

    def provider(agent, data, context, rotator, **kwargs):
        seen.append(list(context["_model_sequence_override"][agent]))
        return "[Agent 24 執行失敗：offline fixture]"

    async def provider_async(*args, **kwargs):
        return provider(*args, **kwargs)

    monkeypatch.setattr(repair_loop, "run_single_agent", provider)
    monkeypatch.setattr(repair_loop, "run_single_agent_async", provider_async)
    context = {"pipeline_id": "v4", "analyses": {24: "accepted previous"}}
    if override is not None:
        context["_model_sequence_override"] = {24: override}
    args = (24, {}, context, object(), ["offline issue"])
    result = (asyncio.run(repair_loop._repair_agent_output_async(*args)) if asynchronous
              else repair_loop._repair_agent_output(*args))
    assert result[0] is False
    assert seen == [[*BASE, LITE]]
    assert context["analyses"][24] == "accepted previous"
    assert context.get("_model_sequence_override") == (None if override is None else {24: override})


def test_general_opt_in_does_not_enable_audit_rewrite_candidate(monkeypatch):
    monkeypatch.setattr(config, "CRITICAL_LITE_FALLBACK_AGENTS", {24: True})
    assert routing.get_runtime_model_sequence(24, {}) == [*BASE, LITE]
    assert routing.get_audit_rewrite_model_sequence(24) == BASE


@pytest.mark.parametrize("bad_value", ["true", "false", False, 1, None, [], {}])
def test_candidate_setting_only_accepts_literal_json_true(bad_value):
    name = "CRITICAL_LITE_FALLBACK_AGENTS_JSON"
    flags, audit = load_lite_candidate_flags({}, {
        name: json.dumps({"24": bad_value, "16": True, "999": True, "11": True}),
    })
    assert flags == {16: True}
    assert audit == {}


def test_empty_or_malformed_environment_cannot_enable_profile_candidate():
    name = "CRITICAL_LITE_FALLBACK_AGENTS_JSON"
    profile = {"critical_lite_fallback_agents": {"24": True}}
    assert load_lite_candidate_flags(profile, {}) == ({24: True}, {})
    for raw in ("", "{bad", "[]", "null", "true", '{}'):
        assert load_lite_candidate_flags(profile, {name: raw}) == ({}, {})


def test_candidate_loader_is_role_scoped_and_does_not_mutate_inputs():
    profile = {"critical_lite_fallback_agents": {"24": True, "11": True},
               "audit_rewrite_lite_fallback_agents": {"11": True, "999": True}}
    before = json.dumps(profile)
    assert load_lite_candidate_flags(profile, {}) == ({24: True}, {11: True})
    assert json.dumps(profile) == before
    assert load_lite_candidate_flags({}, {}) == ({}, {})
