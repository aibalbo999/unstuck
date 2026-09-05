"""Offline regressions for dependency-scoped, version-bound context digests."""

import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

import agent_runtime  # Initialize the compatibility package before digest modules.
from agent_runtime.repair_context import install_repair_attempt_context
from assistant_context import _format_previous
from context_digest_payload import _build_context_digest_prompt, _fallback_context_digest_payload
from context_digest_runtime import _digest_input_hash
import context_digest_tasks as tasks
from workflow_chief_editor import run_chief_editor_synthesis


def make_context(pipeline="v2"):
    return {
        "pipeline_id": pipeline,
        "prompt_version": "test-prompts-v1",
        "prompt_fingerprint": "test-fingerprint-v1",
        "analyses": {11: "總經證據", 12: "護城河證據", 13: "法證財務證據", 20: "管理層風險", 14: "估值前言" * 130 + "目標100", 15: "籌碼證據", 21: "紅軍風險"},
        "structured_outputs": {14: {"price_targets": {"基本情境": 100}}, 20: {"guidance": "保守"}, 21: {"risk": "客戶集中"}},
    }


@pytest.mark.parametrize("change", ["tail", "structured", "guidance", "red_team", "fingerprint", "output_version"])
def test_digest_hash_changes_with_all_real_upstream_inputs(change):
    context = make_context()
    changed = copy.deepcopy(context)
    if change == "tail":
        changed["analyses"][14] = context["analyses"][14][:-3] + "200"
    elif change == "structured":
        changed["structured_outputs"][14]["price_targets"]["基本情境"] = 200
    elif change == "guidance":
        changed["analyses"][20] = "管理層宣布下修"
    elif change == "red_team":
        changed["analyses"][21] = "新增重大客戶流失風險"
    elif change == "fingerprint":
        changed["prompt_fingerprint"] = "test-fingerprint-v2"
    else:
        changed["structured_outputs"][14]["schema_version"] = "valuation.v2"
    assert _digest_input_hash(16, changed) != _digest_input_hash(16, context)


@pytest.mark.parametrize("pipeline,final_agent,upstream", [("v1", 7, 11), ("v1", 7, 20), ("v1", 7, 21), ("v2", 16, 20), ("v2", 16, 21), ("v3", 19, 20), ("v3", 19, 21)])
def test_higher_numbered_upstream_agent_updates_invalidate_digest(pipeline, final_agent, upstream):
    context = {"pipeline_id": pipeline, "analyses": {upstream: "舊風險"}}
    changed = {"pipeline_id": pipeline, "analyses": {upstream: "新風險"}}
    assert _digest_input_hash(final_agent, context) != _digest_input_hash(final_agent, changed)


@pytest.mark.parametrize("pipeline,agent,excluded", [("v1", 4, 5), ("v1", 5, 4), ("v2", 14, 15), ("v2", 14, 16), ("v3", 18, 20), ("v4", 22, 23)])
def test_prompt_and_hash_exclude_peers_self_and_downstream(pipeline, agent, excluded):
    context = {"pipeline_id": pipeline, "analyses": {agent: "SELF_BODY", excluded: "EXCLUDED_BODY"}, "structured_outputs": {agent: {"decision": "SELF_DECISION"}, excluded: {"decision": "EXCLUDED_DECISION"}}}
    prompt = _build_context_digest_prompt(agent, context)
    assert all(marker not in prompt for marker in ("SELF_BODY", "SELF_DECISION", "EXCLUDED_BODY", "EXCLUDED_DECISION"))
    changed = copy.deepcopy(context)
    changed["analyses"][excluded] = "CHANGED_EXCLUDED_BODY"
    changed["structured_outputs"][excluded]["decision"] = "CHANGED_EXCLUDED_DECISION"
    assert _digest_input_hash(agent, context) == _digest_input_hash(agent, changed)


@pytest.mark.parametrize("pipeline,agent,upstream", [("v1", 7, 21), ("v2", 16, 21), ("v3", 19, 20), ("v4", 24, 23)])
def test_previous_context_includes_true_upstream_body_and_structured(pipeline, agent, upstream):
    context = {"pipeline_id": pipeline, "analyses": {upstream: "UPSTREAM_BODY"}, "structured_outputs": {str(upstream): {"risk": "UPSTREAM_STRUCTURED"}}}
    prompt = _format_previous(context, agent)
    assert "UPSTREAM_BODY" in prompt and "UPSTREAM_STRUCTURED" in prompt


class FakeRotator:
    def get_key(self, *_args):
        return "offline-key"

    async def async_get_key(self, *_args):
        return "offline-key"


@pytest.fixture
def offline_digest(monkeypatch):
    calls = []

    def generate(_key, _model, prompt):
        calls.append(prompt)
        return SimpleNamespace(text=json.dumps({"decision_relevant_facts": [f"GENERATED_{len(calls)}"]}))

    async def generate_async(*args):
        return generate(*args)

    monkeypatch.setattr(tasks, "_generate_context_digest_content", generate)
    monkeypatch.setattr(tasks, "_generate_context_digest_content_async", generate_async)
    monkeypatch.setattr(tasks, "response_text", lambda response: response.text)
    monkeypatch.setattr(tasks, "_context_digest_model_sequence", lambda: ["offline-model"])
    monkeypatch.setattr(tasks, "_get_cached_context_digest", lambda _key: None)
    monkeypatch.setattr(tasks, "_store_cached_context_digest", lambda *_args: None)
    monkeypatch.setattr(tasks, "_record_context_digest_success", lambda *_args: None)
    monkeypatch.setattr(tasks, "_is_context_digest_model_circuit_open", lambda *_args: False)
    return calls


def ensure(context, async_mode):
    if async_mode:
        asyncio.run(tasks.ensure_context_digest_async(16, context, FakeRotator()))
    else:
        tasks.ensure_context_digest(16, context, FakeRotator())


@pytest.mark.parametrize("async_mode", [False, True])
def test_existing_digest_reused_only_for_matching_input_version(async_mode, offline_digest):
    context = make_context()
    ensure(context, async_mode)
    first = context["context_digests"][16]
    ensure(context, async_mode)
    assert len(offline_digest) == 1 and context["context_digests"][16] == first
    context["structured_outputs"][14]["price_targets"]["基本情境"] = 200
    ensure(context, async_mode)
    assert len(offline_digest) == 2
    assert context["context_digests"][16] != first


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("agent_key", [16, "16"])
def test_unversioned_checkpoint_digest_is_regenerated(async_mode, agent_key, offline_digest):
    context = make_context()
    context["context_digests"] = {agent_key: '{"decision_relevant_facts":["LEGACY_UNVERIFIED"]}'}
    ensure(context, async_mode)
    assert len(offline_digest) == 1
    assert "LEGACY_UNVERIFIED" not in _format_previous(context, 16)


@pytest.mark.parametrize("async_mode", [False, True])
def test_versioned_digest_survives_json_checkpoint_round_trip(async_mode, offline_digest):
    context = make_context()
    ensure(context, async_mode)
    context.pop("_digest_hash_map", None)
    restored = json.loads(json.dumps(context))
    ensure(restored, async_mode)
    assert len(offline_digest) == 1
    assert "GENERATED_1" in _format_previous(restored, 16)


def test_using_digest_without_ensure_still_rejects_stale_version(offline_digest):
    context = make_context()
    ensure(context, False)
    context["analyses"][21] = "新的紅軍風險"
    assert "GENERATED_1" not in _format_previous(context, 16)


def test_repair_drops_consumer_digest_and_does_not_expose_downstream(offline_digest):
    context = make_context()
    ensure(context, False)
    context["analyses"][16] = "DOWNSTREAM_OLD_BUY"
    context["structured_outputs"][16] = {"decision": "DOWNSTREAM_OLD_BUY"}
    install_repair_attempt_context(context, 14, reflection_instruction="", retry_instruction="", model_sequence=[])
    assert not context["context_digests"].get(16)
    assert "DOWNSTREAM_OLD_BUY" not in _format_previous(context, 14)


def test_structured_context_obeys_total_budget_and_preserves_source_slices():
    context = make_context()
    context["analyses"] = {11: "MACRO_SOURCE", 12: "BUSINESS_SOURCE", 13: "FORENSIC_SOURCE", 20: "GUIDANCE_SOURCE"}
    context["structured_outputs"] = {12: {"reason": "X" * 5000, "score": 7}, 20: {"guidance": "謹慎"}}
    prompt = _format_previous(context, 14, max_total_chars=1000)
    assert len(prompt) <= 1000
    assert all(marker in prompt for marker in ("MACRO_SOURCE", "BUSINESS_SOURCE", "FORENSIC_SOURCE", "GUIDANCE_SOURCE"))
    if "【已解析結構化輸出】\n" in prompt:
        structured = prompt.split("【已解析結構化輸出】\n", 1)[1]
        json.JSONDecoder().raw_decode(structured)


@pytest.mark.parametrize("budget", [0, 1, 20, 79, 80, 100, 200, 1000])
def test_context_budget_also_bounds_omission_notices(budget):
    context = make_context()
    context["context_digests"] = {16: "unversioned"}
    assert len(_format_previous(context, 16, max_total_chars=budget)) <= budget


@pytest.mark.parametrize("async_mode", [False, True])
def test_stale_persistent_digest_is_not_promoted_to_current(async_mode, offline_digest, monkeypatch):
    monkeypatch.setattr(tasks, "_get_cached_context_digest", lambda _key: '{"decision_relevant_facts":["PERSISTENT_LEGACY"]}')
    context = make_context()
    ensure(context, async_mode)
    assert len(offline_digest) == 1
    assert "PERSISTENT_LEGACY" not in _format_previous(context, 16)


def test_digest_prompt_has_only_one_structured_evidence_copy():
    context = {"pipeline_id": "v2", "analyses": {12: "business"}, "structured_outputs": {12: {"risk": "UNIQUE_STRUCTURED_EVIDENCE"}}}
    assert _build_context_digest_prompt(14, context).count("UNIQUE_STRUCTURED_EVIDENCE") == 1


def test_digest_boundary_handles_dict_subclasses_and_excludes_internal_payload():
    class HostileDict(dict):
        def get(self, *_args):
            raise RuntimeError("use native mapping access")

        def items(self):
            raise RuntimeError("use native mapping access")

        def __bool__(self):
            raise RuntimeError("use native mapping access")

    class InternalOnly:
        def __deepcopy__(self, _memo):
            raise AssertionError("internal payload must not be traversed")

    context = HostileDict(pipeline_id="v2", analyses=HostileDict({11: "MACRO_SOURCE"}), structured_outputs=HostileDict({12: HostileDict(score=7, vector=InternalOnly())}))
    prompt = _build_context_digest_prompt(14, context)
    assert "MACRO_SOURCE" in prompt and '"score": 7' in prompt
    assert "vector" not in prompt
    assert _digest_input_hash(14, context)


def test_fallback_digest_scopes_completed_agents_and_outputs_to_real_dependencies():
    context = make_context()
    context["analyses"][16] = "DOWNSTREAM_BODY"
    context["structured_outputs"][16] = {"decision": "DOWNSTREAM_DECISION"}
    payload = _fallback_context_digest_payload(14, context, "offline")
    assert 16 not in payload["completed_agents"]
    assert "DOWNSTREAM" not in json.dumps(payload)


def test_chief_editor_does_not_claim_conflicts_resolved_from_field_presence():
    context = {"pipeline_id": "v2", "data": {"ticker": "TEST", "company_name": "Fixture"}, "parsed": {"price_targets": {"熊市情境": 70, "基本情境": 100, "牛市情境": 130}, "recommendation": {"建議": "買入", "信心": "高", "12個月": "300"}}, "final_audit": {"status": "passed", "warnings": ["目標價 300 與三情境區間不一致"], "critical": []}}
    before = copy.deepcopy(context)
    result = run_chief_editor_synthesis(context)
    resolutions = result["structured_outputs"]["chief_editor"]["resolved_contradictions"]
    assert not any("已收斂" in line for line in resolutions)
    assert any("目標價 300 與三情境區間不一致" in line for line in resolutions)
    assert context == before
