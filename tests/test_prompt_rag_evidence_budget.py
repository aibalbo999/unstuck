"""Keep retrieved evidence bounded without cutting citations or JSON records."""

import copy
import json

import pytest

from agent_runtime import prompting
from llm_rate_limits import estimate_text_tokens
from rag_runtime.queries import _format_results
from rag_runtime.types import RagChunk, RagSearchResult
from state_memory import initialize_agent_state


def rag_evidence(count=8, size=500):
    return _format_results([
        RagSearchResult(
            chunk=RagChunk(str(i), f"filing.pdf#page={i}", json.dumps({"canonical_path": f"source.records[{i}]", "text": "e" * size, "end": f"END_{i}"}), {}),
            score=1.0,
        ) for i in range(count)
    ], 4)


def build(rag_text, monkeypatch, *, role=4, compact=False, token_budget=20_000):
    data = {"ticker": "2330.TW", "company_name": "Evidence fixture"}
    context = {"analyses": {}, "agent_state": initialize_agent_state(data), "rag_context": {role: rag_text}, "_primary_probe_prompt": compact}
    before = copy.deepcopy((data, context))
    monkeypatch.setattr(prompting, "get_agent_prompt_token_budget", lambda _role: token_budget)
    prompt = prompting.build_prompt(role, data, context)
    assert (data, context) == before
    return prompt


@pytest.mark.parametrize("compact", [False, True])
def test_large_retrieval_keeps_complete_records_and_all_tail_rules(monkeypatch, compact):
    rag = rag_evidence(count=16, size=2000)

    prompt = build(rag, monkeypatch, compact=compact)

    assert "RAG evidence budget" in prompt
    assert prompt.endswith(prompting.OUTPUT_CLEANLINESS_RULE)
    assert "\u3010Prompt budget guard\u3011" not in prompt
    records = [json.loads(line) for line in prompt.splitlines() if line.startswith('{"canonical_path": "source.records[')]
    assert 0 < len(records) < 16 if not compact else len(records) < 16
    for record in records:
        index = int(record["canonical_path"].split("[")[1].rstrip("]"))
        assert record["end"] == f"END_{index}"
        assert f"filing.pdf#page={index}" in prompt


def test_unstructured_oversize_json_is_omitted_as_one_unit(monkeypatch):
    rag = json.dumps({"canonical_path": "source.large_record", "text": "x" * 100_000, "end": "RECORD_END"})

    prompt = build(rag, monkeypatch)

    assert "RAG evidence budget" in prompt
    assert '"canonical_path": "source.large_record"' not in prompt
    assert prompt.endswith(prompting.OUTPUT_CLEANLINESS_RULE)


def test_small_retrieved_evidence_remains_verbatim(monkeypatch):
    rag = rag_evidence(count=1, size=40)

    assert rag in build(rag, monkeypatch)


def test_rag_budget_uses_each_agents_existing_model_budget(monkeypatch):
    import settings.models as models

    monkeypatch.setitem(models.AGENT_MODELS, 4, "ordinary-model")
    monkeypatch.setitem(models.AGENT_MODELS, 14, "gemini-large-fixture")
    monkeypatch.setattr(models, "LARGE_CONTEXT_MODEL_PATTERN", "gemini-large")
    monkeypatch.setattr(models, "RAG_MAX_CONTEXT_CHARS", 2500)
    monkeypatch.setattr(models, "RAG_MAX_CHUNKS_PER_AGENT", 2)
    monkeypatch.setattr(models, "RAG_LARGE_CONTEXT_CHARS", 12_000)
    monkeypatch.setattr(models, "RAG_LARGE_CONTEXT_CHUNKS", 8)
    rag = rag_evidence()

    small = build(rag, monkeypatch, role=4)
    large = build(rag, monkeypatch, role=14)

    assert small.count('"canonical_path": "source.records[') == 2
    assert large.count('"canonical_path": "source.records[') == 8


def test_template_context_uses_same_bounded_retrieval(monkeypatch):
    monkeypatch.setitem(prompting.ANALYSIS_PROMPTS, 4, "{{ rag_context }}\n{{ context.rag_context[4] }}")

    prompt = build(rag_evidence(count=16, size=2000), monkeypatch)

    assert "RAG evidence budget" in prompt
    assert prompt.count("RAG evidence budget") == 3
    assert estimate_text_tokens(prompt) <= 20_000
    assert '"end": "END_15"' not in prompt


def test_rag_allowance_uses_remaining_input_tokens(monkeypatch):
    from agent_runtime import prompt_budget

    monkeypatch.setattr(prompt_budget, "get_agent_rag_budget", lambda _role: (100_000, 30))
    rag = rag_evidence(count=16, size=500)
    bounded = prompt_budget.bound_agent_rag_context(rag, 4, token_budget_func=lambda _role: 1600)

    assert estimate_text_tokens(bounded) <= 400
    assert "RAG evidence budget" in bounded
    assert '"end": "END_0"' in bounded


def test_unknown_token_budget_still_respects_configured_rag_limit(monkeypatch):
    from agent_runtime import prompt_budget

    monkeypatch.setattr(prompt_budget, "get_agent_rag_budget", lambda _role: (1800, 2))
    bounded = prompt_budget.bound_agent_rag_context(rag_evidence(), 4, token_budget_func=lambda _role: 0)

    assert len(bounded) <= 1800
    assert bounded.count('"canonical_path": "source.records[') == 2


def test_empty_rag_stays_empty_when_retrieval_is_disabled(monkeypatch):
    from agent_runtime import prompt_budget

    monkeypatch.setattr(prompt_budget, "get_agent_rag_budget", lambda _role: (0, 0))

    assert prompt_budget.bound_agent_rag_context("", 4) == ""
