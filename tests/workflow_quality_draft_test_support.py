"""Shared workflow-quality draft fixtures for SQLite and PostgreSQL tests."""

import asyncio
import copy

import pytest
from langgraph.graph import END, START, StateGraph

from agent_runtime import quality_gates, quality_retry
from agent_runtime.deferred import AgentDeferredError
from state_memory import initialize_agent_state
from workflow_services import create_default_workflow_services
from workflow_state import AgentGraphState, agent_state_to_graph


def initial_state():
    state = agent_state_to_graph(initialize_agent_state(
        {"ticker": "2330.TW", "company_name": "Draft fixture", "current_price": 100},
        run_id="quality-draft-run",
    ), pipeline_id="v1")
    state.update(analyses={}, structured_outputs={}, prompt_fingerprint="prompt-v1")
    return state


@pytest.fixture
def quality_runtime(monkeypatch):
    calls = {"initial": [], "rewrite": [], "validated": [], "parsed": [], "published": 0, "nodes_returned": []}
    control = {"deferred": True, "raw_size": 10, "parallel": False, "deferred_agents": {4, 14}, "wait_for_sibling": False}
    events = []

    async def context_digest(agent_num, context, *_args, **_kwargs):
        context.setdefault("context_digests", {}).setdefault(agent_num, f"digest-{agent_num}")

    async def rag(agent_num, context, *_args, **_kwargs):
        context.setdefault("rag_context", {}).setdefault(agent_num, f"retrieved-evidence-{agent_num}")

    async def status(*_args, **kwargs):
        events.append(kwargs)

    async def generate(agent_num, data, context, rotator):
        if context.get("_audit_retry_instruction"):
            calls["rewrite"].append((agent_num, context["analyses"][agent_num]))
            if control["parallel"]:
                while len(calls["rewrite"]) < 2:
                    await asyncio.sleep(0)
            if control["wait_for_sibling"] and agent_num == 4:
                while 14 not in calls["nodes_returned"]:
                    await asyncio.sleep(0)
            if control["deferred"] and agent_num in control["deferred_agents"]:
                raise AgentDeferredError(agent_num, [{"model_id": "offline-model", "retry_wait_seconds": 60}])
            context["structured_outputs"][agent_num] = {"approved": True}
            return f"validated-result-{agent_num}"
        calls["initial"].append(agent_num)
        context["structured_outputs"][agent_num] = {"unvalidated_value": agent_num}
        return f"unvalidated-draft-{agent_num}:" + "x" * control["raw_size"]

    def parse(agent_num, text, context):
        calls["parsed"].append((agent_num, text, copy.deepcopy(context["structured_outputs"].get(agent_num))))
        return True, text

    def validate(agent_num, text, data):
        calls["validated"].append((agent_num, text))
        return ["arithmetic must be checked"] if text.startswith("unvalidated-draft-") else []

    monkeypatch.setattr(quality_gates, "run_single_agent_async", generate)
    monkeypatch.setattr(quality_gates, "ensure_context_digest_async", context_digest)
    monkeypatch.setattr(quality_gates, "ensure_agent_rag_context_async", rag)
    monkeypatch.setattr(quality_gates, "emit_status_async", status)
    monkeypatch.setattr(quality_gates, "emit_log", lambda *_args: None)
    monkeypatch.setattr(quality_retry, "emit_log", lambda *_args: None)
    monkeypatch.setattr(quality_gates, "get_runtime_model_sequence", lambda *_args: ["offline-model"])
    monkeypatch.setattr(quality_retry, "get_runtime_model_sequence", lambda *_args: ["offline-model"])
    monkeypatch.setattr(quality_gates, "validate_analysis_output", validate)
    monkeypatch.setattr(quality_gates, "validate_company_identity", lambda *_args: [])
    monkeypatch.setattr(quality_gates, "validate_prompt_leakage", lambda *_args: [])
    monkeypatch.setattr(quality_gates, "append_quality_warnings", lambda _agent, text, _data: text)
    monkeypatch.setattr(quality_gates, "_try_parse_structured_output", parse)
    return calls, control, events


def builder_for(calls, agents=(4,)):
    services = create_default_workflow_services(rotator=object())
    builder = StateGraph(AgentGraphState)
    names = []
    for agent_num in agents:
        name = f"agent_{agent_num}"
        names.append(name)

        async def agent_node(state, agent_num=agent_num):
            result = await services.run_agent(agent_num, state)
            calls["nodes_returned"].append(agent_num)
            return result

        builder.add_node(name, agent_node)
        builder.add_edge(START, name)

    async def publish(state):
        calls["published"] += 1
        return {"status": "done"}

    builder.add_node("publish", publish)
    builder.add_edge(names, "publish")
    builder.add_edge("publish", END)
    return builder


@pytest.fixture(params=["structured", "identity"])
def intermediate_quality_runtime(request, monkeypatch, quality_runtime):
    calls, control, events = quality_runtime
    generated = []

    async def generate(agent_num, data, context, rotator):
        if context.get("_audit_retry_instruction"):
            calls["rewrite"].append((agent_num, context["analyses"][agent_num]))
            if control.get("audit_failure"):
                return "[Agent 4 \u57f7\u884c\u5931\u6557: empty response]"
            if control["deferred"]:
                raise AgentDeferredError(agent_num, [{"model_id": "offline-model", "retry_wait_seconds": 60}])
            context["structured_outputs"][agent_num] = {"approved": True}
            return "validated-result-4"
        text = "bad-json" if not generated else f"repaired-draft-{len(generated)}"
        generated.append(text)
        context["structured_outputs"][agent_num] = {"draft": text}
        return text

    def parse(agent_num, text, context):
        calls["parsed"].append((agent_num, text, copy.deepcopy(context["structured_outputs"].get(agent_num))))
        return request.param != "structured" or text != "bad-json", text

    def validate(agent_num, text, data):
        calls["validated"].append((agent_num, text))
        return [] if text == "validated-result-4" else ["arithmetic must be checked"]

    monkeypatch.setattr(quality_gates, "run_single_agent_async", generate)
    monkeypatch.setattr(quality_gates, "_try_parse_structured_output", parse)
    monkeypatch.setattr(quality_gates, "validate_analysis_output", validate)
    monkeypatch.setattr(quality_gates, "validate_company_identity", lambda text, _data:
                        ["wrong company"] if request.param == "identity" and text == "bad-json" else [])
    return calls, control, generated


__all__ = [
    "builder_for",
    "initial_state",
    "intermediate_quality_runtime",
    "quality_runtime",
]
