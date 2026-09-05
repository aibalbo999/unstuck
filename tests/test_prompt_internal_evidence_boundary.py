"""Offline regressions for the state-to-prompt internal RAG boundary."""

import copy
import json

import pytest

from agent_runtime import prompting
from llm_rate_limits import estimate_text_tokens
import state_memory
from state_memory import initialize_agent_state, state_view_for


ROLES = (4, 14, 21, 7, 16, 19)
VECTOR_VALUE = 0.12345678901234567
CANONICAL_PATH = "quant_metrics.calculations.dcf_scenarios_default.base.price_per_share_twd"


def make_state():
    state = initialize_agent_state(
        {"ticker": "1623C21", "company_name": "Boundary fixture", "revenue_history": [100, 120]},
        run_id="offline-prompt-boundary",
    )
    state.quant_metrics = {
        "calculations": {"dcf_scenarios_default": {"base": {"price_per_share_twd": 123.45}}},
        "unit_contract": {"price": "twd_per_share"},
    }
    state.tool_results = {
        "rag_index": {
            "metadata": {"source": "INTERNAL_INDEX_ONLY"},
            "chunks": [
                {"text": "UNRETRIEVED_INDEX_TEXT", "embedding": [VECTOR_VALUE] * 3072 if i < 13 else None}
                for i in range(48)
            ],
        },
        "calculate_dcf": {"value": 123.45, "unit": "twd_per_share", "canonical_path": CANONICAL_PATH},
        "retrieved_evidence": [
            {
                "text": "RETRIEVED_EVIDENCE", "source": "filing.pdf#page=7",
                "canonical_path": CANONICAL_PATH,
                "metadata": {"embedding": [VECTOR_VALUE], "vector": [VECTOR_VALUE]},
            }
        ],
    }
    return state


def assert_no_internal_payload(value):
    encoded = json.dumps(value, default=str)
    for marker in ("INTERNAL_INDEX_ONLY", "UNRETRIEVED_INDEX_TEXT", str(VECTOR_VALUE)):
        assert marker not in encoded
    if isinstance(value, dict):
        assert not {"rag_index", "embedding", "embeddings", "vector", "vectors"}.intersection(value)
        for item in value.values():
            assert_no_internal_payload(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            assert_no_internal_payload(item)


@pytest.mark.parametrize("role", (*ROLES, "valuation", "final_risk_memo"))
@pytest.mark.parametrize("configured", [True, False], ids=["loaded-policy", "fallback-policy"])
def test_role_view_excludes_internal_payload_without_mutating_state(role, configured, monkeypatch):
    if not configured:
        monkeypatch.setattr(state_memory, "load_agent_prompt_config", lambda: {})
    state = make_state()
    before = state.model_dump(mode="json")

    view = state_view_for(role, state)

    assert state.model_dump(mode="json") == before
    assert_no_internal_payload(view)
    assert view["tool_results"]["calculate_dcf"] == before["tool_results"]["calculate_dcf"]
    assert view["tool_results"]["retrieved_evidence"][0]["text"] == "RETRIEVED_EVIDENCE"
    assert view["quant_metrics"] == before["quant_metrics"]
    view["tool_results"]["calculate_dcf"]["value"] = -1
    assert state.model_dump(mode="json") == before


@pytest.mark.parametrize("policy", [
    {"root": ["rag_index", "embedding", "vector", "tool_results"]},
    {"rag_index": ["chunks"], "embedding": ["values"], "vector": ["values"]},
    {"tool_results": ["rag_index", "calculate_dcf", "retrieved_evidence"]},
    {"root": ["tool_results", "raw_financial_data", "normalized_financials"]},
    {"normalized_financials": ["rag_index", "embedding", "vector", "revenue_history"]},
])
def test_configured_state_paths_cannot_reenable_internal_payload(policy, monkeypatch):
    state = make_state()
    state.normalized_financials.update({"rag_index": state.tool_results["rag_index"], "embedding": [VECTOR_VALUE], "vector": [VECTOR_VALUE]})
    state.raw_financial_data["nested"] = copy.deepcopy(state.normalized_financials)
    before = state.model_dump(mode="json")
    monkeypatch.setattr(state_memory, "load_agent_prompt_config", lambda: {"state_view_policy": {"custom": policy}})

    view = state_view_for("custom", state)

    assert state.model_dump(mode="json") == before
    assert_no_internal_payload(view)


@pytest.mark.parametrize("role", ROLES)
def test_full_prompt_is_nonmutating_and_independent_of_giant_index(role, monkeypatch):
    state = make_state()
    data = copy.deepcopy(state.normalized_financials)
    context = {"agent_state": state, "analyses": {}, "structured_outputs": {}, "rag_context": {role: "RETRIEVED_RAG_CONTEXT"}, "pipeline_id": "v1"}
    before_state, before_data, before_context = state.model_dump(mode="json"), copy.deepcopy(data), copy.deepcopy(context)
    monkeypatch.setattr(prompting, "get_agent_prompt_token_budget", lambda _role: 1_000_000)

    prompt = prompting.build_prompt(role, data, context)
    clean_state = state.model_copy(deep=True)
    clean_state.tool_results.pop("rag_index")
    clean_prompt = prompting.build_prompt(role, data, {**context, "agent_state": clean_state})

    assert state.model_dump(mode="json") == before_state
    assert data == before_data and context == before_context
    assert prompt == clean_prompt
    assert_no_internal_payload(prompt)
    assert "RETRIEVED_RAG_CONTEXT" in prompt and "RETRIEVED_EVIDENCE" in prompt
    assert CANONICAL_PATH in prompt and "123.45" in prompt
    assert estimate_text_tokens(prompt, response_budget=8192) < 30_000
    assert prompt.endswith(prompting.OUTPUT_CLEANLINESS_RULE)
    state_json = prompt.split("\u3010AgentState view\u3011\n", 1)[1].split("\n", 1)[1]
    decoded_view, _ = json.JSONDecoder().raw_decode(state_json)
    assert decoded_view["tool_results"]["calculate_dcf"]["value"] == 123.45


def test_template_data_and_context_cannot_bypass_internal_boundary(monkeypatch):
    state = make_state()
    data = {**state.normalized_financials, "nested": state.tool_results}
    context = {"agent_state": state, "data": data, "tool_results": state.tool_results, "rag_index": state.tool_results["rag_index"], "structured_outputs": {4: {"embedding": [VECTOR_VALUE], "value": 123.45}}, "analyses": {}}
    before = copy.deepcopy((data, context))
    monkeypatch.setitem(prompting.ANALYSIS_PROMPTS, 4, "{{ data }}\n{{ context }}\n{{ context.agent_state.tool_results }}")
    monkeypatch.setattr(prompting, "get_agent_prompt_token_budget", lambda _role: 1_000_000)

    prompt = prompting.build_prompt(4, data, context)

    assert (data, context) == before
    assert_no_internal_payload(prompt)
    assert "RETRIEVED_EVIDENCE" in prompt and CANONICAL_PATH in prompt


def test_excluded_payload_is_not_traversed_or_copied(monkeypatch):
    class InternalOnly:
        def __deepcopy__(self, memo):
            pytest.fail("Internal payload must be excluded before copying or serializing")

    state = make_state()
    state.tool_results["rag_index"] = InternalOnly()
    data = {**state.normalized_financials, "rag_index": InternalOnly()}
    context = {"agent_state": state, "rag_index": InternalOnly(), "analyses": {}}

    assert_no_internal_payload(state_view_for(4, state))
    assert_no_internal_payload(prompting.build_prompt(4, data, context))


def test_projection_preserves_model_and_dataclass_evidence_including_extra_fields():
    from pydantic import BaseModel, ConfigDict
    from prompt_evidence import prompt_evidence_copy
    from rag_runtime.types import RagChunk

    class Evidence(BaseModel):
        model_config = ConfigDict(extra="allow")
        canonical_path: str

    value = {
        "record": Evidence(canonical_path=CANONICAL_PATH, value=123.45, embedding=[VECTOR_VALUE]),
        "chunk": RagChunk("retrieved-1", "filing.pdf#page=7", "RETRIEVED_EVIDENCE", {}, [VECTOR_VALUE]),
        "history": [1.0] * 3072,
        "aliases": ({"EMBEDDINGS": [VECTOR_VALUE], "_vector": [VECTOR_VALUE], "vectors": [VECTOR_VALUE]},),
    }
    before = copy.deepcopy(value)

    projected = prompt_evidence_copy(value)

    assert_no_internal_payload(projected)
    assert projected["record"] == {"canonical_path": CANONICAL_PATH, "value": 123.45}
    assert projected["chunk"]["text"] == "RETRIEVED_EVIDENCE"
    assert projected["history"] == [1.0] * 3072
    assert value == before
