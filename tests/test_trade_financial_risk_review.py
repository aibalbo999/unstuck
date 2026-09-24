"""Independent acceptance-path regressions for the deterministic FCF guard."""

import asyncio
import copy
import hashlib
import json

import pytest

from agent_runtime import quality_gates, step_cache
from agent_runtime.quality_structured_outputs import try_parse_structured_output
from agent_runtime.trade_source_repair import repair_trade_sources
from structured_output_normalizer import structured_output_to_report_text
from structured_output_runtime import process_agent_response
from trade_financial_risk import FINANCIAL_RISK_POLICY_VERSION, NEGATIVE_FCF_WARNING
from trade_source_contract import bind_source_prompt
from test_trade_source_completion import setup_payload
from workflow_checkpoints import open_sqlite_checkpointer
from workflow_quality_drafts import (
    checkpoint_draft_scope,
    checkpoint_unvalidated_draft,
    quality_draft_node,
)


def _context():
    data = {"ticker": "offline.TW", "free_cash_flow_raw": -1}
    context = {"pipeline_id": "v4", "ticker": "offline.TW", "data": data,
               "analyses": {22: "technical", 23: "flow"}, "structured_outputs": {}}
    catalog = {"short_term_market_context": {"technical_indicators": {
        "availability": "available", "source": "fixture", "as_of": "2026-09-24",
        "sma_20": 95, "sma_5": 110,
    }}}
    encoded = json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    bind_source_prompt(context, encoded, encoded, catalog, hashlib.sha256(encoded.encode()).hexdigest())
    return context


def _accepted(context):
    raw = json.dumps({**setup_payload(), "risk_level": "Low"})
    text = process_agent_response(24, raw, context, completion_diagnostics={"finish_reasons": ["STOP"]})
    return raw, text


def _assert_guard(context, text, raw):
    output = context["structured_outputs"][24]
    assert output["risk_level"] == "High"
    assert text.count(NEGATIVE_FCF_WARNING) == 1
    assert "風險：High" in text and "TTM" not in text
    assert output["trade_direction"] == "Long"
    assert output["source_assessment"]["status"] == "source_bound"
    assert output["source_assessment"]["output_completion"]["raw_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert output["source_assessment"]["output_completion"]["finish_reasons"] == ["STOP"]
    assert output["financial_risk_assessment"] == {
        "policy_version": FINANCIAL_RISK_POLICY_VERSION,
        "reason": "negative_free_cash_flow", "input_path": "data.free_cash_flow_raw",
        "value": -1.0, "unit": "twd", "period": "not_verified",
    }


@pytest.mark.parametrize("legacy", [False, True])
def test_step_cache_acceptance_enforces_policy_and_keeps_source_completion_receipts(monkeypatch, legacy):
    context = _context()
    raw, text = _accepted(context)
    if legacy:
        output = context["structured_outputs"][24]
        output.pop("financial_risk_assessment")
        output["risk_level"] = "Low"
        output["core_catalyst"] = setup_payload()["core_catalyst"]
        text = structured_output_to_report_text(24, output, raw)
    writes = []
    monkeypatch.setattr(step_cache, "AGENT_STEP_CACHE_ENABLED", True)
    monkeypatch.setattr(step_cache, "AGENT_STEP_CACHE_SECONDS", 60)
    monkeypatch.setattr(step_cache, "set_cache_json", lambda key, payload, ttl: writes.append(payload))
    step_cache.store_cached_agent_step("offline", agent_num=24, context=context, model_id="offline", text=text)
    cached = copy.deepcopy(writes[0])
    restored = _context()
    assert step_cache.cached_market_context_matches(restored, 24, cached, "prompt")
    restored_text = step_cache.restore_cached_agent_step(restored, 24, cached)
    ok, result = try_parse_structured_output(24, restored_text, restored)
    assert ok
    _assert_guard(restored, result, raw)
    assert writes[0] == cached


def test_financial_policy_revision_invalidates_only_trade_step_cache(monkeypatch):
    import trade_financial_risk

    context = _context()
    def key(agent):
        return step_cache.build_agent_step_cache_key(agent, context["data"], context, "offline", "prompt")
    before = {agent: key(agent) for agent in (23, 24)}
    monkeypatch.setattr(trade_financial_risk, "FINANCIAL_RISK_POLICY_VERSION", "negative-fcf:next")
    assert key(24) != before[24]
    assert key(23) == before[23]


def test_sqlite_cold_quality_draft_is_guarded_without_regeneration(tmp_path, monkeypatch):
    path = tmp_path / "draft.sqlite3"
    original = _context()
    raw, _ = _accepted(original)
    output = original["structured_outputs"][24]
    output.pop("financial_risk_assessment")
    output["risk_level"] = "Low"
    output["core_catalyst"] = setup_payload()["core_catalyst"]
    legacy_text = structured_output_to_report_text(24, output, raw)

    async def persist():
        async with open_sqlite_checkpointer(path) as saver:
            with checkpoint_draft_scope(saver, "financial-review"):
                async with quality_draft_node(24, {"data": original["data"]}, original):
                    await checkpoint_unvalidated_draft(24, legacy_text, original)
    asyncio.run(persist())

    async def noop(*args, **kwargs):
        pass
    async def no_generation(*args, **kwargs):
        pytest.fail("restored valid draft must not call the model")
    monkeypatch.setattr(quality_gates, "get_runtime_model_sequence", lambda *args: ["offline"])
    monkeypatch.setattr(quality_gates, "apply_deterministic_agent_skip", noop)
    monkeypatch.setattr(quality_gates, "emit_status_async", noop)
    monkeypatch.setattr(quality_gates, "ensure_context_digest_async", no_generation)
    monkeypatch.setattr(quality_gates, "ensure_agent_rag_context_async", no_generation)
    monkeypatch.setattr(quality_gates, "run_single_agent_async", no_generation)
    restored = _context()
    async def resume():
        async with open_sqlite_checkpointer(path) as saver:
            with checkpoint_draft_scope(saver, "financial-review"):
                async with quality_draft_node(24, {"data": restored["data"]}, restored):
                    return await quality_gates.run_agent_with_quality_gates_async(24, restored["data"], restored, None)
    agent, result = asyncio.run(resume())
    assert agent == 24
    _assert_guard(restored, result, raw)
    assert not restored.get("blocking_issues")


def test_source_repair_cannot_undo_financial_risk_guard():
    context = _context()
    broken = {**setup_payload(), "support_source_refs": [], "risk_level": "Low"}
    original = process_agent_response(24, json.dumps(broken), context,
                                      completion_diagnostics={"finish_reasons": ["STOP"]})
    assert context["structured_outputs"][24]["trade_direction"] == "Neutral"
    assert context["structured_outputs"][24]["risk_level"] == "High"
    calls = []
    async def repaired(agent, data, context, rotator):
        raw, text = _accepted(context)
        calls.append(raw)
        return text
    text = asyncio.run(repair_trade_sources(original, context["data"], context, None, repaired))
    assert len(calls) == 1
    _assert_guard(context, text, calls[0])
    assert context["structured_outputs"][24]["source_assessment"]["repair_attempted"]


@pytest.mark.parametrize("execution", ["sync", "async"])
def test_final_repair_limit_fallback_keeps_negative_fcf_warning_and_local_origin(monkeypatch, execution):
    from agent_runtime import repair_loop
    from config import MAX_PER_JOB_REPAIR_ATTEMPTS

    context = _context()
    _, text = _accepted(context)
    context["analyses"][24] = text
    context["repair_attempt_counts"] = {24: MAX_PER_JOB_REPAIR_ATTEMPTS}
    monkeypatch.setattr(repair_loop, "run_single_agent", lambda *a, **kw: pytest.fail("unexpected provider call"))
    async def no_model(*args, **kwargs):
        pytest.fail("unexpected provider call")
    monkeypatch.setattr(repair_loop, "run_single_agent_async", no_model)
    args = (24, context["data"], context, object(), ["invalid output"])
    result = (repair_loop._repair_agent_output(*args) if execution == "sync"
              else asyncio.run(repair_loop._repair_agent_output_async(*args)))
    assert result[0]
    output = context["structured_outputs"][24]
    assert output["trade_direction"] == "Neutral" and output["risk_level"] == "High"
    assert NEGATIVE_FCF_WARNING in output["core_catalyst"]
    assert NEGATIVE_FCF_WARNING in context["analyses"][24]
    assert output["financial_risk_assessment"]["value"] == -1
    assert output["source_assessment"]["output_completion"]["status"] == "local_fallback"
    assert output["source_assessment"]["output_completion"]["finish_reasons"] == []
