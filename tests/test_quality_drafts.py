import asyncio
import copy

import pytest
from langgraph.graph import END, START, StateGraph

from agent_runtime import quality_gates, quality_retry
from agent_runtime.deferred import AgentDeferredError
from agent_runtime.retry_policy import AgentConfigurationError, AgentRetryableError
from workflow_graph import AGENT_RETRY_POLICY, is_retryable_workflow_error


ORIGINAL = "Financial draft with an unresolved arithmetic issue."
FAILURE = "[Agent 2 執行失敗：empty response]"
ISSUES = ["arithmetic issue"]


async def noop(*_args, **_kwargs):
    pass


def draft_context(key=2):
    return {
        "analyses": {key: ORIGINAL},
        "structured_outputs": {key: {"value": [1]}, 7: {"untouched": True}},
        "_audit_retry_instruction": "previous instruction",
        "_model_sequence_override": {2: ["configured-model"], 7: ["other-model"]},
    }


async def rewrite(context, run_agent, emit_status=noop, parse=None):
    return await quality_retry.retry_after_agent_quality_issues(
        2, {}, context, object(), None, ISSUES,
        agent_position=1, agent_total=1, agent_name="finance",
        pipeline_id="v1", pipeline_label="A", run_agent_async=run_agent,
        emit_status=emit_status,
        parse_structured_output=parse or (lambda agent, text, ctx: (True, text)),
    )


@pytest.mark.parametrize("key", [2, "2"])
def test_failed_rewrite_raises_nonretryable_error_and_retains_draft(key):
    context = draft_context(key)
    before = copy.deepcopy(context)
    events = []

    async def fail(_agent, _data, ctx, _rotator):
        ctx["structured_outputs"][2] = {"failed_attempt": True}
        return FAILURE

    async def status(*_args, **kwargs):
        events.append(kwargs)

    with pytest.raises(quality_retry.AgentQualityDraftError) as caught:
        asyncio.run(rewrite(context, fail, status))

    error = caught.value
    assert type(error) is quality_retry.AgentQualityDraftError
    assert not isinstance(error, AgentRetryableError)
    assert is_retryable_workflow_error(error) is False
    assert error.agent_num == 2
    assert error.detail == FAILURE
    for field in before:
        assert context[field] == before[field]
    assert context["blocking_issues"] == ["Agent 2 finance: arithmetic issue"]
    failures = [event for event in events if event["phase"] == "agent_quality_retry_failed"]
    assert len(failures) == 1
    assert failures[0]["metadata"]["draft_text"] == ORIGINAL
    assert failures[0]["metadata"]["retry_error"] == FAILURE


def test_failed_rewrite_without_original_still_raises_quality_error():
    context = draft_context()
    context["analyses"] = {}

    async def fail(*_args):
        return FAILURE

    with pytest.raises(quality_retry.AgentQualityDraftError) as caught:
        asyncio.run(rewrite(context, fail))

    assert type(caught.value) is quality_retry.AgentQualityDraftError
    assert context["blocking_issues"] == ["Agent 2 finance: arithmetic issue"]


@pytest.mark.parametrize("previous_instruction", [None, "previous instruction"])
def test_empty_route_install_does_not_mutate_context(previous_instruction):
    context = draft_context()
    context["_model_sequence_override"][2] = []
    if previous_instruction is None:
        context.pop("_audit_retry_instruction")
    before = copy.deepcopy(context)

    with pytest.raises(AgentConfigurationError):
        quality_retry.install_quality_retry_context(context, 2, ISSUES)

    assert context == before


def test_successful_rewrite_preserves_configured_routes_and_restores_context():
    context = draft_context()
    context["_model_sequence_override"][2] = ["configured-model", "fallback", "configured-model"]
    before = copy.deepcopy(context)

    async def success(_agent, _data, ctx, _rotator):
        assert ctx["_model_sequence_override"][2] == ["configured-model", "fallback"]
        return "Rewritten draft."

    def parse(_agent, text, ctx):
        ctx["structured_outputs"][2] = {"corrected": True}
        return True, text

    assert asyncio.run(rewrite(context, success, parse=parse)) == "Rewritten draft."
    assert context["structured_outputs"][2] == {"corrected": True}
    assert context["_model_sequence_override"] == before["_model_sequence_override"]
    assert context["_audit_retry_instruction"] == before["_audit_retry_instruction"]
    assert not context.get("blocking_issues")


def test_deferred_rewrite_keeps_original_exception_and_restores_context():
    context = draft_context()
    before = copy.deepcopy(context)
    deferred = AgentDeferredError(2, [{"model_id": "configured-model", "retry_wait_seconds": 18000}])

    async def defer(*_args):
        raise deferred

    with pytest.raises(AgentDeferredError) as caught:
        asyncio.run(rewrite(context, defer))

    assert caught.value is deferred
    for field in before:
        assert context[field] == before[field]


def test_async_cancellation_propagates_and_restores_route_overrides():
    context = draft_context()
    before = copy.deepcopy(context)

    async def cancel(*_args):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(rewrite(context, cancel))

    assert context["_model_sequence_override"] == before["_model_sequence_override"]
    assert context["_audit_retry_instruction"] == before["_audit_retry_instruction"]


def test_workflow_does_not_retry_or_publish_failed_quality_draft():
    calls, published = [], []
    context = draft_context()

    async def fail(*_args):
        calls.append(True)
        return FAILURE

    async def agent(_state):
        await rewrite(context, fail)
        return {}

    async def publish(_state):
        published.append(True)
        return {}

    graph = StateGraph(dict)
    graph.add_node("agent", agent, retry_policy=AGENT_RETRY_POLICY)
    graph.add_node("publish", publish)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", "publish")
    graph.add_edge("publish", END)

    with pytest.raises(quality_retry.AgentQualityDraftError) as caught:
        asyncio.run(graph.compile().ainvoke({}))

    assert type(caught.value) is quality_retry.AgentQualityDraftError
    assert calls == [True]
    assert published == []


def test_quality_gate_propagates_draft_error_without_returning_report_content(monkeypatch):
    context = draft_context()
    original = "ROA 23.6% × 權益乘數 1.252 = 29.5%，與 ROE 39.1% 的落差來自應付帳款營運槓桿。"
    calls = []

    async def generate(*_args):
        calls.append(True)
        return original if len(calls) == 1 else FAILURE

    monkeypatch.setattr(quality_gates, "run_single_agent_async", generate)
    monkeypatch.setattr(quality_gates, "ensure_context_digest_async", noop)
    monkeypatch.setattr(quality_gates, "ensure_agent_rag_context_async", noop)
    monkeypatch.setattr(quality_gates, "emit_status_async", noop)
    monkeypatch.setattr(quality_gates, "_try_parse_structured_output", lambda agent, text, ctx: (True, text))

    with pytest.raises(quality_retry.AgentQualityDraftError):
        asyncio.run(quality_gates.run_agent_with_quality_gates_async(2, {}, context, object()))

    assert len(calls) == 2
    assert context["analyses"][2] == original
    assert context["blocking_issues"]


def test_quality_gate_preserves_status_fields_and_model_getter(monkeypatch):
    events = []
    context = draft_context()
    context.update({"agent_positions": {2: 3}, "agent_total": 10, "pipeline_id": "v1", "pipeline_label": "A"})

    async def success(*_args):
        return "Financial analysis completed."

    async def status(_callback, _message, **kwargs):
        events.append(kwargs)

    monkeypatch.setattr(quality_gates, "get_runtime_model_sequence", lambda *_: ["configured-model"])
    monkeypatch.setattr(quality_gates, "run_single_agent_async", success)
    monkeypatch.setattr(quality_gates, "ensure_context_digest_async", noop)
    monkeypatch.setattr(quality_gates, "ensure_agent_rag_context_async", noop)
    monkeypatch.setattr(quality_gates, "emit_status_async", status)
    monkeypatch.setattr(quality_gates, "_try_parse_structured_output", lambda agent, text, ctx: (True, text))

    completed, _text = asyncio.run(quality_gates.run_agent_with_quality_gates_async(2, {}, context, object()))

    assert completed == 2
    assert {event["phase"] for event in events} >= {"started", "rag_retrieval", "model_call", "quality_gate"}
    expected = {"current": 3, "total": 10, "name": quality_gates.AGENT_NAMES[2], "agent_num": 2, "pipeline_id": "v1", "pipeline_label": "A"}
    assert all({key: event[key] for key in expected} == expected for event in events)
