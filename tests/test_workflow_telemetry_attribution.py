"""Node telemetry must describe the current result, not nominal or stale state."""

import asyncio
import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from workflow_telemetry import with_node_telemetry  # noqa: E402
from agent_runtime.attempt_telemetry import (  # noqa: E402
    build_agent_node_receipt,
    reset_node_attempt_telemetry,
)
from agent_runtime.llm_call_events import llm_model_call_event, llm_model_response_event  # noqa: E402


def _run(result=None, *, state=None, node_name="agent_22", agent_num=22, failure=None, factory=None):
    records = []
    services = SimpleNamespace(telemetry_callback=records.append)

    async def node(_state):
        nonlocal result
        if failure is not None:
            raise failure
        if factory is not None:
            result = factory()
            if inspect.isawaitable(result):
                result = await result
        return result

    call = with_node_telemetry(node_name, node, services, agent_num=agent_num)
    if failure is None:
        returned = asyncio.run(call(state or {}))
        assert returned is result
    else:
        with pytest.raises(type(failure)):
            asyncio.run(call(state or {}))
    assert len(records) == 1
    return records[0]


def test_success_without_same_result_receipt_is_not_model_or_quality_evidence():
    record = _run({"analyses": {"22": "completed draft"}})

    assert record["status"] == "success"
    assert record["model"] is None
    assert record["quality_gate_pass"] is None


def test_previous_state_usage_and_retries_are_never_attributed_to_this_node():
    record = _run(
        {"analyses": {"22": "new draft without usage"}},
        state={
            "llm_token_usage": {"22": {"input_tokens": 8765, "output_tokens": 4321}},
            "agent_quality_retry_counts": {"22": 9},
        },
    )

    assert record["input_tokens"] is None
    assert record["output_tokens"] is None
    assert record["retry_count"] == 0
    assert record["cache_hit"] is False


LITE = "gemini-3.5-flash-lite"


def _call(context, model=LITE):
    llm_model_call_event(context, 22, model, "fixture", timeout_seconds=1)


def _response(context, model=LITE, *, usage=None):
    llm_model_response_event(context, 22, model, "fixture", "accepted response", SimpleNamespace(keys=[]),
                             None, timeout_seconds=1, response={"usage": usage})


def _seal(context, *, quality=None, text="accepted response"):
    result = {"analyses": {"22": text}}
    result["node_telemetry"] = build_agent_node_receipt(context, 22, result, quality_gate_pass=quality)
    return result


def test_actual_fallback_response_is_attributed_instead_of_nominal_gemma():
    def node():
        context = {}
        reset_node_attempt_telemetry(context, 22)
        _call(context, "gemma-4-31b-it")
        _call(context)
        _response(context, usage={"input_tokens": 123, "output_tokens": 45})
        return _seal(context)

    record = _run(factory=node)
    assert record["model"] == LITE
    assert record["input_tokens"] == 123
    assert record["output_tokens"] == 45
    assert record["retry_count"] == 0  # The Gemma attempt was not a Lite retry.
    assert record["quality_gate_pass"] is None


def test_response_without_usage_clears_prior_attempt_tokens_and_counts_current_retries():
    def node():
        context = {}
        reset_node_attempt_telemetry(context, 22)
        _call(context)
        _response(context, usage={"input_tokens": 999, "output_tokens": 999})
        _call(context)
        _response(context)
        return _seal(context)

    record = _run(factory=node)
    assert record["model"] == LITE
    assert record["input_tokens"] is None
    assert record["output_tokens"] is None
    assert record["retry_count"] == 1


@pytest.mark.parametrize("verdict", [True, False, None, "true"])
def test_only_explicit_boolean_same_result_quality_verdict_is_reported(verdict):
    def node():
        context = {}
        reset_node_attempt_telemetry(context, 22)
        _call(context)
        _response(context)
        return _seal(context, quality=verdict)

    record = _run(factory=node)
    assert record["quality_gate_pass"] is (verdict if type(verdict) is bool else None)


def test_result_changed_after_receipt_sealing_is_not_attributed():
    def node():
        context = {}
        reset_node_attempt_telemetry(context, 22)
        _call(context)
        _response(context)
        result = _seal(context, quality=True)
        result["analyses"]["22"] = "a different output"
        return result

    record = _run(factory=node)
    assert record["model"] is None
    assert record["quality_gate_pass"] is None


def test_receipt_cannot_be_reused_by_later_node_invocation():
    receipts = []

    def node():
        context = {}
        reset_node_attempt_telemetry(context, 22)
        _call(context)
        _response(context)
        result = _seal(context, quality=True)
        receipts.append(result)
        return result

    _run(factory=node)
    record = _run(receipts[0])
    assert record["model"] is None
    assert record["quality_gate_pass"] is None


@pytest.mark.parametrize("source", ["fallback_log", "deterministic_event"])
def test_deterministic_replacement_after_response_is_not_attributed_to_model(source):
    def node():
        context = {}
        reset_node_attempt_telemetry(context, 22)
        _call(context)
        _response(context, usage={"input_tokens": 123, "output_tokens": 45})
        if source == "fallback_log":
            context["deterministic_fallbacks"] = [{"agent_num": 22, "type": "deterministic_fallback"}]
        else:
            context["_runtime_events"] = [{"agent_num": 22, "phase": "agent_deterministic_result"}]
        return _seal(context, text="deterministic replacement")

    record = _run(factory=node)
    assert record["model"] is None
    assert record["input_tokens"] is None
    assert record["output_tokens"] is None
    assert record["cache_hit"] is False


def test_previous_deterministic_fallback_does_not_hide_new_model_response():
    def node():
        context = {"deterministic_fallbacks": [{"agent_num": 22, "type": "deterministic_fallback"}]}
        reset_node_attempt_telemetry(context, 22)
        _call(context)
        _response(context)
        return _seal(context)

    assert _run(factory=node)["model"] == LITE


def test_failed_new_call_does_not_inherit_an_earlier_response():
    def node():
        context = {}
        reset_node_attempt_telemetry(context, 22)
        _call(context)
        _response(context, usage={"input_tokens": 123, "output_tokens": 45})
        _call(context, "gemini-3.8-flash")
        return _seal(context)

    record = _run(factory=node)
    assert record["model"] is None
    assert record["input_tokens"] is None
    assert record["output_tokens"] is None


def test_execution_failure_return_does_not_adopt_old_successful_response():
    def node():
        context = {}
        reset_node_attempt_telemetry(context, 22)
        _call(context)
        _response(context, usage={"input_tokens": 123, "output_tokens": 45})
        # A later quality repair can exhaust routes at preflight, before another
        # model call is recorded, and return a workflow failure marker.
        return _seal(context, text="[Agent 22 執行失敗] 所有模型不可用")

    record = _run(factory=node)
    assert record["model"] is None
    assert record["input_tokens"] is None
    assert record["output_tokens"] is None


@pytest.mark.parametrize("run_sync", [False, True])
def test_step_cache_attribution_uses_cached_model_without_prior_tokens(monkeypatch, run_sync):
    from agent_runtime import single_agent

    cached = {"model_id": LITE, "text": "cached response"}
    monkeypatch.setattr(single_agent, "get_runtime_model_sequence", lambda *_: [LITE])
    monkeypatch.setattr(single_agent, "unavailable_model", lambda *_: None)
    monkeypatch.setattr(single_agent, "_build_model_prompt", lambda *_: "fixture")
    monkeypatch.setattr(single_agent, "get_cached_agent_step", lambda *_: cached)

    async def node():
        context = {"data": {}, "llm_token_usage": {22: {"input_tokens": 99, "output_tokens": 11}}}
        reset_node_attempt_telemetry(context, 22)
        _call(context)
        _response(context, usage={"input_tokens": 999, "output_tokens": 999})
        runner = single_agent.run_single_agent if run_sync else single_agent.run_single_agent_async
        text = runner(22, {}, context, SimpleNamespace())
        if inspect.isawaitable(text):
            text = await text
        return _seal(context, text=text)

    record = _run(factory=node)
    assert record["model"] == LITE
    assert record["cache_hit"] is True
    assert record["input_tokens"] is None
    assert record["output_tokens"] is None
    assert record["retry_count"] == 0


@pytest.mark.parametrize("run_sync", [False, True])
def test_transport_semantic_cache_preserves_provenance_and_nonbillable_usage(monkeypatch, run_sync):
    import llm_transport

    monkeypatch.setattr(llm_transport, "get_cached_llm_response", lambda *_: {
        "model_id": LITE, "text": "cached response", "usage": {"input_tokens": 123, "output_tokens": 45},
    })

    async def node():
        context = {}
        reset_node_attempt_telemetry(context, 22)
        _call(context)
        runner = llm_transport.generate_content if run_sync else llm_transport.generate_content_async
        response = runner("offline-key", LITE, "fixture", None)
        if inspect.isawaitable(response):
            response = await response
        llm_model_response_event(context, 22, LITE, "fixture", "cached response", SimpleNamespace(keys=[]),
                                 None, timeout_seconds=1, response=response)
        return _seal(context, text="cached response")

    record = _run(factory=node)
    assert record["model"] == LITE
    assert record["cache_hit"] is True
    assert record["input_tokens"] == 123
    assert record["output_tokens"] == 45
    assert record["retry_count"] == 0


@pytest.mark.parametrize("node_name", ["prepare_analysis", "final_audit", "tear_sheet", "chief_editor"])
def test_non_agent_nodes_have_no_nominal_single_model_attribution(node_name):
    record = _run({}, node_name=node_name, agent_num=None)

    assert record["model"] is None
    assert record["quality_gate_pass"] is None


def test_failed_node_does_not_invent_provider_model_or_quality_failure():
    record = _run(
        failure=RuntimeError("post-processing failed"),
        state={"llm_token_usage": {"22": {"input_tokens": 123, "output_tokens": 45}}},
    )

    assert record["status"] == "failed"
    assert record["model"] is None
    assert record["quality_gate_pass"] is None
    assert record["input_tokens"] is None
    assert record["output_tokens"] is None
