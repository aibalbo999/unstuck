"""Missing transcripts must not spend a model call during dependency rebuild."""
import asyncio
import copy

import pytest

from agent_runtime import repair_loop
from agent_runtime.deterministic_skips import deterministic_agent_result


def context(data):
    return {"pipeline_id": "v3", "data": data, "analyses": {20: "previous result"},
            "structured_outputs": {}, "blocking_issues": ["external:keep"]}


def run(asynchronous, data, ctx):
    args = (20, data, ctx, object(), ["上游分析已更正，請依目前上游重新產生分析。"])
    if asynchronous:
        return asyncio.run(repair_loop._repair_agent_output_async(*args))
    return repair_loop._repair_agent_output(*args)


def forbid_provider(monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail("A missing transcript must not trigger reflection or a model request")
    async def forbidden_async(*a, **kw):
        forbidden()
    monkeypatch.setattr(repair_loop, "run_single_agent", forbidden)
    monkeypatch.setattr(repair_loop, "run_single_agent_async", forbidden_async)
    monkeypatch.setattr(repair_loop, "generate_audit_reflection", forbidden)
    monkeypatch.setattr(repair_loop, "generate_audit_reflection_async", forbidden_async)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("counts", [{}, {20: 2}])
def test_missing_transcript_rebuild_uses_existing_source_absence_result(monkeypatch, asynchronous, counts):
    data = {"ticker": "TEST", "earnings_call": {"status": "unavailable", "transcript": "  "}}
    ctx = context(data)
    ctx["repair_attempt_counts"] = copy.deepcopy(counts)
    expected_ctx = context(data)
    expected = deterministic_agent_result(20, data, expected_ctx)
    forbid_provider(monkeypatch)
    ok, message = run(asynchronous, data, ctx)
    assert ok, message
    assert ctx["analyses"][20] == expected
    assert ctx["structured_outputs"][20] == expected_ctx["structured_outputs"][20]
    assert ctx["structured_outputs"][20]["confidence"] == 0
    assert ctx["structured_outputs"][20]["highlights"] == []
    assert ctx["repair_attempt_counts"] == counts
    assert "external:keep" in ctx["blocking_issues"]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_deterministic_repair_still_respects_quality_rejection(monkeypatch, asynchronous):
    data = {"ticker": "TEST"}
    ctx = context(data)
    before = copy.deepcopy(ctx)
    forbid_provider(monkeypatch)
    monkeypatch.setattr("agent_runtime.repair_absent_source.validate_analysis_output", lambda *a: ["fixture quality rejection"])
    ok, message = run(asynchronous, data, ctx)
    assert not ok
    assert "fixture quality rejection" in message
    for field in ("analyses", "structured_outputs", "blocking_issues"):
        assert ctx[field] == before[field]


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("source", ["data", "normalized_state"])
def test_available_transcript_keeps_normal_model_repair(monkeypatch, asynchronous, source):
    data = {"ticker": "TEST", "earnings_call": {"transcript": "管理層原文：成本改善。"}}
    ctx = context(data)
    if source == "normalized_state":
        from state_memory import initialize_agent_state
        ctx["agent_state"] = initialize_agent_state(data, run_id="transcript-repair")
        ctx["agent_state"].normalized_financials["earnings_call"] = data.pop("earnings_call")
    calls = []
    def generated(*args, **kwargs):
        calls.append(args[0])
        return "## 管理層分析\n逐字稿提及成本改善，仍需後續財報驗證。"
    async def generated_async(*args, **kwargs):
        return generated(*args, **kwargs)
    monkeypatch.setattr(repair_loop, "run_single_agent", generated)
    monkeypatch.setattr(repair_loop, "run_single_agent_async", generated_async)
    monkeypatch.setattr(repair_loop, "repair_429_circuit_state", lambda *a: {"open": False})
    ok, message = run(asynchronous, data, ctx)
    assert ok, message
    assert calls == [20]
    assert "法說會逐字稿缺漏" not in ctx["analyses"][20]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_cancellation_precedes_deterministic_repair(monkeypatch, asynchronous):
    data = {"ticker": "TEST"}
    ctx = context(data)
    def cancelled():
        raise asyncio.CancelledError("job cancelled")
    ctx["_cancel_check"] = cancelled
    forbid_provider(monkeypatch)
    before = copy.deepcopy(ctx)
    with pytest.raises(asyncio.CancelledError):
        run(asynchronous, data, ctx)
    for field in ("analyses", "structured_outputs", "blocking_issues"):
        assert ctx[field] == before[field]
