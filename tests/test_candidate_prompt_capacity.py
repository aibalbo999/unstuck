"""Candidate budgets never buy admission by deleting canonical evidence."""

import copy
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_catalog import AGENT_NAMES
from agent_runtime import prompt_budget, prompting
from agent_runtime.generation_config import estimate_agent_input_tokens
from agent_runtime.single_agent_admission import _preflight_model_input_capacity
from agent_runtime.single_agent_prompt import build_model_prompt
from fixtures.data_payloads import fresh_audited_payload
from llm_input_capacity import InputCapacityExceededError
from state_memory import initialize_agent_state
from test_agent19_lossless_prompt_json import assert_lossless, financial_json, STRING_TOKEN


LITE = "gemini-3.5-flash-lite"


def state_json(prompt):
    text = prompt.split("【AgentState view】\n", 1)[1].split("\n", 1)[1]
    return json.JSONDecoder().raw_decode(text)[0]


@pytest.mark.parametrize("agent", sorted(AGENT_NAMES))
@pytest.mark.parametrize("repair", [False, True])
def test_every_candidate_uses_lossless_financial_and_state_json(monkeypatch, agent, repair):
    data = fresh_audited_payload()
    data["institutional_trading"]["verbatim"] = '  原文 "quote" x\ty\nz\\w  '
    context = {"pipeline_id": "v4" if agent >= 22 else "v3", "analyses": {},
               "agent_state": initialize_agent_state(data, run_id="lossless-fixture")}
    if repair:
        context["_audit_retry_instruction"] = "REPAIR_RULE_KEEP_ALL_SOURCE_RECORDS"
    before = copy.deepcopy((data, context))
    captures = []
    formatter = prompting.format_data_for_prompt
    def capture(payload, **options):
        result = formatter(payload, **options)
        captures.append((payload, options, result))
        return result
    monkeypatch.setattr(prompting, "format_data_for_prompt", capture)

    actual = build_model_prompt(agent, data, context, LITE, False, prompt_builder=prompting.build_prompt)

    payload, options, result = captures[0]
    assert options.get("compact_json") is True
    assert_lossless(formatter(payload), result)
    pretty_state = prompting.build_state_view_section(agent, context, compact_json=False)
    assert state_json(actual) == state_json(pretty_state)
    encoded = json.dumps(state_json(pretty_state), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    assert encoded in actual
    assert STRING_TOKEN.findall(encoded) == STRING_TOKEN.findall(
        json.dumps(state_json(pretty_state), ensure_ascii=False, indent=2, allow_nan=False))
    assert actual.endswith(prompting.OUTPUT_CLEANLINESS_RULE)
    if repair:
        assert "REPAIR_RULE_KEEP_ALL_SOURCE_RECORDS" in actual
    # Only final-source manifests may be recorded; temporary model overrides vanish.
    assert data == before[0]
    assert context["agent_state"] == before[1]["agent_state"]
    assert "_prompt_model_id" not in context and "_primary_probe_prompt" not in context


def test_candidate_budget_uses_attempted_model_and_counts_request_overhead(monkeypatch):
    # Settings reload tests may replace sys.modules['config']; patch the
    # import-time binding used by the consumer, not a newly imported facade.
    from agent_runtime.prompt_budget import config
    from agent_runtime import generation_config

    monkeypatch.setattr(prompt_budget, "AGENT_MODELS", {4: "primary-large"})
    monkeypatch.setattr(prompt_budget, "get_model_context_token_limit", lambda model: 100_000)
    monkeypatch.setattr(prompt_budget, "PROMPT_CONTEXT_RESPONSE_TOKEN_BUDGET", 8000)
    monkeypatch.setattr(prompt_budget, "PROMPT_CONTEXT_SAFETY_MARGIN_TOKENS", 1000)
    monkeypatch.setattr(config, "MODEL_INPUT_TOKEN_LIMITS", {"primary-large": 90000, LITE: 64000})
    monkeypatch.setattr(config, "TPM_LIMITS", {"primary-large": 200000, LITE: 60000})
    monkeypatch.setattr(generation_config, "estimate_agent_input_tokens", lambda agent, model, prompt: 2000)

    assert prompt_budget.get_agent_prompt_token_budget(4, model_id=LITE) == 57000
    assert prompt_budget.get_agent_prompt_token_budget(4) == 87000


def test_context_ceiling_reserves_actual_output_and_keeps_unknown_distinct(monkeypatch):
    from agent_runtime.prompt_budget import config

    monkeypatch.setattr(config, "get_model_context_token_limit", lambda model: 8000 if model == "known" else 0)
    monkeypatch.setattr(config, "PROMPT_CONTEXT_SAFETY_MARGIN_TOKENS", 100)
    monkeypatch.setattr(config, "PROMPT_CONTEXT_RESPONSE_TOKEN_BUDGET", 999999)
    assert prompt_budget.get_agent_context_input_token_limit(4, "known") == 8000 - 6144 - 100
    assert prompt_budget.get_agent_context_input_token_limit(20, "known") == 8000 - 1024 - 100
    assert prompt_budget.get_agent_context_input_token_limit(4, "unknown") is None


def test_complete_oversized_source_reaches_admission_instead_of_middle_slicing(monkeypatch):
    from agent_runtime.single_agent_admission import config

    data = fresh_audited_payload()
    data["institutional_trading"]["records"] = [{"index": i, "quote": f"KEEP_SOURCE_{i:03d} " * 20}
                                                for i in range(80)]
    context = {"pipeline_id": "v4", "analyses": {}, "agent_state": initialize_agent_state(data)}
    monkeypatch.setattr(config, "MODEL_INPUT_TOKEN_LIMITS", {LITE: 5000})
    monkeypatch.setattr(config, "TPM_LIMITS", {})

    prompt = build_model_prompt(24, data, context, LITE, False, prompt_builder=prompting.build_prompt)

    financial = json.loads(financial_json(prompt))
    assert financial["institutional_trading"]["records"] == data["institutional_trading"]["records"]
    assert "Prompt budget guard" not in prompt
    assert "【trade-source:" in prompt
    assert prompt.endswith(prompting.OUTPUT_CLEANLINESS_RULE)
    assert estimate_agent_input_tokens(24, LITE, prompt) > 5000
    with pytest.raises(InputCapacityExceededError) as caught:
        _preflight_model_input_capacity(24, LITE, prompt)
    assert caught.value.basis == "local_input_budget"
    assert caught.value.limit == 5000


def test_generic_guard_keeps_whole_prompt_for_route_admission():
    prompt = "SOURCE_START\n" + "CANONICAL_SOURCE_MIDDLE " * 500 + "\nMANDATORY_END_RULE"
    assert prompt_budget.enforce_prompt_token_budget(prompt, 4, lambda _: 100) == prompt


@pytest.mark.parametrize("asynchronous", [False, True])
def test_context_window_without_local_caps_rejects_before_provider_and_falls_back(monkeypatch, asynchronous):
    import llm_rate_limits
    from agent_runtime import llm_calls, single_agent, single_agent_admission
    from agent_runtime.model_policy import MODEL_CIRCUITS_KEY

    monkeypatch.setattr(llm_rate_limits, "create_shared_llm_limiter", lambda: None)
    monkeypatch.setattr(single_agent.config, "MODEL_INPUT_TOKEN_LIMITS", {})
    monkeypatch.setattr(single_agent.config, "TPM_LIMITS", {})
    monkeypatch.setattr(single_agent.config, "PROMPT_CONTEXT_SAFETY_MARGIN_TOKENS", 100)
    monkeypatch.setattr(single_agent.config, "get_model_context_token_limit", lambda model: 4196 if model == "small-context" else 100000)
    monkeypatch.setattr(single_agent, "get_runtime_model_sequence", lambda *_: ["small-context", "large-context"])
    monkeypatch.setattr(single_agent, "build_prompt", lambda *_: "Full source remains unchanged. " * 100)
    monkeypatch.setattr(single_agent, "get_cached_agent_step", lambda *_: None)
    monkeypatch.setattr(single_agent, "store_cached_agent_step", lambda *_, **__: None)
    sent = []
    def generate(key, model, agent, prompt):
        sent.append((model, prompt))
        return SimpleNamespace(text="A complete analysis section. " * 20)
    async def generate_async(*args):
        return generate(*args)
    monkeypatch.setattr(llm_calls, "_generate_content", generate)
    monkeypatch.setattr(llm_calls, "_generate_content_async", generate_async)
    context = {}
    rotator = llm_rate_limits.KeyRotator(["offline-fixture"])

    if asynchronous:
        result = asyncio.run(single_agent.run_single_agent_async(2, {}, context, rotator))
    else:
        result = single_agent.run_single_agent(2, {}, context, rotator)

    assert "complete" in result
    assert sent == [("large-context", "Full source remains unchanged. " * 100)]
    assert not context.get(MODEL_CIRCUITS_KEY)
    with pytest.raises(InputCapacityExceededError) as caught:
        single_agent_admission._preflight_model_input_capacity(2, "small-context", sent[0][1])
    assert caught.value.limit == 0
    assert caught.value.basis == "configured_context_window"


@pytest.mark.skipif(not os.getenv("CANDIDATE_CAPACITY_CHECKPOINT"), reason="optional private JSON checkpoint")
def test_real_checkpoint_lossless_capacity_replay(monkeypatch):
    """Replay only prompt construction; no database, workflow or provider calls."""
    from workflow_context import legacy_context_from_graph

    state = json.loads(Path(os.environ["CANDIDATE_CAPACITY_CHECKPOINT"]).read_text())
    context = legacy_context_from_graph(state, SimpleNamespace(progress_callback=None, cancel_check=None))
    original = copy.deepcopy((context["data"], context["agent_state"]))
    formatter, state_builder = prompting.format_data_for_prompt, prompting.build_state_view_section
    rows = []
    for agent in (22, 23, 24):
        for repair in (False, True):
            ctx = copy.deepcopy(context)
            if repair:
                ctx["_audit_retry_instruction"] = "Keep every financial source and quoted evidence."
            def before_financial(data, **options):
                options["compact_json"] = agent in {19, 24}
                return formatter(data, **options)
            def before_state(*args, **options):
                options["compact_json"] = False
                return state_builder(*args, **options)
            with monkeypatch.context() as patch:
                patch.setattr(prompting, "format_data_for_prompt", before_financial)
                patch.setattr(prompting, "build_state_view_section", before_state)
                old = build_model_prompt(agent, ctx["data"], ctx, LITE, False, prompt_builder=prompting.build_prompt)
            new = build_model_prompt(agent, ctx["data"], ctx, LITE, False, prompt_builder=prompting.build_prompt)
            assert json.loads(financial_json(old)) == json.loads(financial_json(new))
            assert STRING_TOKEN.findall(financial_json(old)) == STRING_TOKEN.findall(financial_json(new))
            old_view, new_view = state_json(old), state_json(new)
            assert old_view == new_view
            def without_json(prompt):
                text = prompt.replace(financial_json(prompt), "", 1)
                tail = text.split("【AgentState view】\n", 1)[1].split("\n", 1)[1]
                _, end = json.JSONDecoder().raw_decode(tail)
                return text.replace(tail[:end], "", 1)
            assert without_json(old) == without_json(new)
            old_tokens, new_tokens = (estimate_agent_input_tokens(agent, LITE, item) for item in (old, new))
            assert new_tokens < old_tokens
            rows.append({"agent": agent, "repair": repair, "old_bytes": len(old.encode()), "new_bytes": len(new.encode()),
                         "old_input_tokens": old_tokens, "new_input_tokens": new_tokens,
                         "financial_and_state_equal": True, "other_prompt_bytes_equal": True})
    assert (context["data"], context["agent_state"]) == original
    print(json.dumps({"candidate": LITE, "checkpoint_unchanged": True, "rows": rows}, ensure_ascii=False))
