"""Exercise the deployed profile through the real quota and fallback boundaries."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_runtime import llm_calls, routing, single_agent
from agent_runtime.deferred import AgentDeferredError
from agent_runtime.quality_retry import quality_retry_model_sequence
import llm_rate_limits
import settings.models as model_settings


PROFILE = Path(__file__).resolve().parents[1] / "backend/model_routes_usage_aware_free.json"
FLASH = "gemini-3.8-flash"
LITE = "gemini-3.5-flash-lite"
OLD_BACKUPS = ("gemini-3-flash-preview", "gemini-3.6-flash")


@pytest.fixture
def downgrade_profile(monkeypatch):
    profile = json.loads(PROFILE.read_text())
    for name in tuple(model_settings.os.environ):
        if name.startswith(("AGENT_MODEL_", "AGENT_MODELS_JSON", "AGENT_FALLBACK_MODELS", "DEFAULT_ANALYSIS_FALLBACK_MODELS")):
            monkeypatch.delenv(name)
    monkeypatch.setattr(model_settings, "MODEL_ROUTES", profile)
    monkeypatch.setattr(model_settings, "DEFAULT_ANALYSIS_MODEL", profile["default_analysis_model"])
    monkeypatch.setattr(model_settings, "DEFAULT_DECISION_MODEL", profile["default_decision_model"])
    monkeypatch.setattr(routing, "AGENT_MODELS", model_settings._load_agent_models())
    monkeypatch.setattr(routing, "AGENT_FALLBACK_MODELS", model_settings._load_agent_fallbacks())
    monkeypatch.setattr(routing, "AUDIT_MODEL", profile["audit_model"])
    monkeypatch.setattr(routing, "AUDIT_FALLBACK_MODELS", profile["audit_fallback_models"])
    monkeypatch.setattr(llm_rate_limits, "create_shared_llm_limiter", lambda: None)
    for attr, section in (("RPD_LIMITS", "rpd_limits"), ("RPM_LIMITS", "rpm_limits"),
                          ("TPM_LIMITS", "tpm_limits"), ("MODEL_INPUT_TOKEN_LIMITS", "input_token_limits")):
        monkeypatch.setattr(llm_rate_limits, attr, profile[section])
    return profile


@pytest.mark.parametrize("entry", ["async", "sync", "sync_in_event_loop"])
@pytest.mark.parametrize("available", [FLASH, LITE, None])
def test_6409_oversize_primary_and_exhausted_backups_continue_or_defer(monkeypatch, downgrade_profile, entry, available):
    profile = downgrade_profile
    rotator = llm_rate_limits.KeyRotator(["offline-slot-one", "offline-slot-two"])
    exhausted = [*OLD_BACKUPS]
    if available != FLASH:
        exhausted.append(FLASH)
    if available is None:
        exhausted.append(LITE)
    for model in exhausted:
        limit = profile["rpd_limits"][model]
        for key in rotator.keys:
            assert rotator._daily_budget.reserve(key, model, limit, rotator.keys, request_units=limit)
            # Only confirmed provider feedback excludes a route in this profile.
            rotator.disable_rpd_until_reset(key, model)

    prompt = "Preserved source evidence for the 6409 analysis. " * 30
    monkeypatch.setattr(single_agent, "build_prompt", lambda *_: prompt)
    monkeypatch.setattr(single_agent, "get_cached_agent_step", lambda *_: None)
    saved = []
    monkeypatch.setattr(single_agent, "store_cached_agent_step", lambda *a, **kw: saved.append(kw))
    # Reproduce the measured request size without fetching live stock evidence.
    monkeypatch.setattr(llm_calls, "estimate_agent_input_tokens", lambda *_: 20156)
    sent = []

    def generate(key, model, agent, full_prompt):
        sent.append((model, full_prompt))
        return SimpleNamespace(text="Complete analysis with preserved evidence and limitations. " * 20)

    async def generate_async(*args):
        return generate(*args)

    monkeypatch.setattr(llm_calls, "_generate_content", generate)
    monkeypatch.setattr(llm_calls, "_generate_content_async", generate_async)
    context = {}

    async def invoke_in_loop():
        if entry == "sync_in_event_loop":
            return single_agent.run_single_agent(11, {}, context, rotator)
        return await single_agent.run_single_agent_async(11, {}, context, rotator)

    def invoke():
        return single_agent.run_single_agent(11, {}, context, rotator) if entry == "sync" else asyncio.run(invoke_in_loop())

    if available is None:
        with pytest.raises(AgentDeferredError):
            invoke()
        assert not sent and not saved
    else:
        assert "Complete analysis" in invoke()
        assert sent == [(available, prompt)]
        assert saved[-1]["model_id"] == available
        events = context["_runtime_events"]
        assert any(e.get("phase") == "model_fallback" and e["metadata"]["model_id"] == available for e in events)
        assert any(e.get("phase") == "llm_model_response" and e["metadata"]["model_id"] == available for e in events)
    for model in exhausted:
        assert set(rotator._daily_remaining(model).values()) == {0}


def test_critical_roles_and_audit_keep_lite_out_of_routes(downgrade_profile):
    for agent in (4, 7, 14, 16, 19, 24):
        route = routing.get_agent_model_sequence(agent)
        assert FLASH in route
        assert LITE not in route
        assert "gemini-embedding-2" not in route
    audit = routing.get_audit_model_sequence()
    assert FLASH in audit
    assert LITE not in audit
    context = {"_model_sequence_override": {11: audit}}
    assert routing.get_runtime_model_sequence(11, context) == audit
    assert quality_retry_model_sequence(11, context) == audit


def test_general_agents_keep_downgrade_for_quality_rewrite(downgrade_profile):
    for agent in routing.AGENT_MODELS:
        if agent in (4, 7, 14, 16, 19, 24):
            continue
        route = routing.get_agent_model_sequence(agent)
        assert route[-2:] == [FLASH, LITE]
        assert len(route) == len(set(route))
        assert quality_retry_model_sequence(agent, {}) == [model for model in route if model != "gemma-4-31b-it"]


def test_quality_priority_keeps_valuation_and_audit_on_flash(downgrade_profile):
    gemma = downgrade_profile['default_analysis_model']
    for role in (4, 14):
        assert gemma not in routing.get_agent_model_sequence(role)
    assert gemma not in routing.get_audit_model_sequence()


def test_quality_rewrite_escalates_from_gemma(downgrade_profile):
    sequence = quality_retry_model_sequence(11, {})
    assert downgrade_profile['default_analysis_model'] not in sequence
    assert sequence[0] in OLD_BACKUPS
