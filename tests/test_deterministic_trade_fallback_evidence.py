"""Local no-trade fallback is attributable without inventing model completion."""
import asyncio
from copy import deepcopy

import pytest

from agent_runtime.deterministic_fallbacks import _deterministic_structured_fallback
from analysis_input_provenance import freeze_analysis_inputs
from report_analysis_completeness import assess_report_analysis_completeness
from trade_source_contract import bind_source_prompt, source_block


def context_with_prompt():
    data = {"ticker": "2305.TW", "current_price": 20, "quant_metrics": {"rsi": 50}}
    freeze_analysis_inputs(data)
    context = {"pipeline_id": "v4", "data": data, "analyses": {22: "technical", 23: "risk", 24: "bad draft"},
               "structured_outputs": {}, "blocking_issues": ["Agent 24: invalid output"]}
    block, catalog, fingerprint = source_block(data)
    bind_source_prompt(context, block, block, catalog, fingerprint)
    context["_trade_completion_receipt"] = {"diagnostics": {"finish_reasons": ["MAX_TOKENS"]}}
    return context


def run_fallback(context, data=None):
    assert _deterministic_structured_fallback(24, context["data"] if data is None else data,
                                            context, "bad draft")[0]
    return context["structured_outputs"][24]


@pytest.mark.parametrize("finish", ["STOP", "MAX_TOKENS", None])
def test_local_fallback_records_degraded_origin_without_borrowing_provider_finish(finish, monkeypatch):
    from agent_runtime.quality_structured_outputs import try_parse_structured_output

    context = context_with_prompt()
    if finish:
        context["_trade_completion_receipt"]["diagnostics"]["finish_reasons"] = [finish]
    else:
        context.pop("_trade_completion_receipt")
    original_manifest = deepcopy(context["_trade_source_manifest"])
    output = run_fallback(context)
    assessment = output.get("source_assessment", {})
    assert assessment.get("status") == "degraded"
    assert assessment["origin"] == "local_deterministic_fallback"
    assert set(assessment["reason_codes"]) >= {"deterministic_fallback", "source_evidence_unverified"}
    assert assessment["source_binding"] == "prompt_manifest_only"
    assert assessment["source_fingerprint"] == original_manifest["fingerprint"]
    assert assessment["output_completion"] == {
        "status": "local_fallback", "basis": "deterministic_no_trade_policy",
        "provider_finish_observed": False, "finish_reasons": [],
    }
    assert "_trade_completion_receipt" not in context
    assert context["_trade_source_manifest"] == original_manifest
    assert output["trade_direction"] == "Neutral" and output["risk_level"] == "High"
    assert output["stop_loss"] == "N/A"
    assert all(output[field] == [] for field in ("support_source_refs", "resistance_source_refs", "catalyst_source_refs"))
    monkeypatch.setattr("agent_runtime.quality_structured_outputs.process_agent_response",
                        lambda *a, **kw: pytest.fail("local output must not be reparsed as provider output"))
    assert try_parse_structured_output(24, context["analyses"][24], context)[0]
    assert context["structured_outputs"][24]["source_assessment"] == assessment
    assert assess_report_analysis_completeness(context)["status"] == "degraded"


@pytest.mark.parametrize("invalid", ["absent", "hidden", "changed_input", "changed_catalog", "different_argument"])
def test_unproven_prompt_is_unknown_and_cannot_be_saved_as_fallback_source(invalid):
    from workflow_trade_evidence import successful_trade_evidence
    from analysis_dependencies import record_result_provenance
    from report_analysis_evidence import capture_analysis_evidence

    context = context_with_prompt()
    data = context["data"]
    if invalid == "absent": context.pop("_trade_source_manifest")
    elif invalid == "hidden": context["_trade_source_manifest"]["visible"] = False
    elif invalid == "changed_input": data["current_price"] = 21
    elif invalid == "changed_catalog": context["_trade_source_manifest"]["catalog"]["unexpected"] = 21
    else: data = {**data, "current_price": 21}
    assessment = run_fallback(context, data).get("source_assessment", {})
    assert assessment.get("source_binding") == "unknown"
    assert not assessment.get("source_fingerprint")
    record_result_provenance(24, context)
    assert successful_trade_evidence(context) == {}
    assert capture_analysis_evidence(context)["sections"]["trade_source_manifest"]["status"] == "unknown"


def test_repair_limit_fallback_survives_graph_cold_context_and_evidence_capture(monkeypatch):
    from agent_runtime.repair_loop import _repair_agent_output
    from config import MAX_PER_JOB_REPAIR_ATTEMPTS
    from report_analysis_evidence import capture_analysis_evidence
    from workflow_context import graph_delta_from_legacy_context, legacy_context_from_graph
    from workflow_services import initialize_graph_state, create_default_workflow_services

    context = context_with_prompt()
    original_manifest = deepcopy(context["_trade_source_manifest"])
    context["repair_attempt_counts"] = {24: MAX_PER_JOB_REPAIR_ATTEMPTS}
    monkeypatch.setattr("agent_runtime.repair_loop.run_single_agent", lambda *a, **kw: pytest.fail("unexpected provider call"))
    assert _repair_agent_output(24, context["data"], context, object(), ["bad output"])[0]
    state = initialize_graph_state(context["data"], pipeline_id="v4")
    state.update(graph_delta_from_legacy_context(context))
    restored = legacy_context_from_graph(state, create_default_workflow_services(rotator=object()))
    assessment = restored["structured_outputs"][24].get("source_assessment", {})
    assert assessment.get("output_completion", {}).get("status") == "local_fallback"
    assert restored["_trade_source_manifest"] == original_manifest
    assert capture_analysis_evidence(restored)["sections"]["trade_source_manifest"]["data"] == original_manifest
    assert assess_report_analysis_completeness(restored)["status"] == "degraded"


@pytest.mark.parametrize("outcome", ["rejected", "exception", "accepted"])
@pytest.mark.parametrize("execution", ["sync", "async"])
def test_repair_transaction_keeps_private_evidence_with_its_accepted_output(outcome, execution):
    from agent_runtime.repair_transaction import preserve_failed_repair

    context = context_with_prompt()
    before = deepcopy(context)

    def repair(agent, data, candidate):
        # Mutate nested evidence to exercise the real clone boundary as well.
        candidate["_trade_source_manifest"]["catalog"]["changed"] = 1
        candidate["_trade_completion_receipt"]["diagnostics"]["finish_reasons"] = ["STOP"]
        candidate["analyses"][24] = "candidate"
        if outcome == "exception":
            raise RuntimeError("fixture interruption")
        return outcome == "accepted", "fixture"

    async def async_repair(*args):
        return repair(*args)

    def execute():
        if execution == "async":
            return asyncio.run(preserve_failed_repair(async_repair)(24, context["data"], context))
        return preserve_failed_repair(repair)(24, context["data"], context)

    if outcome == "exception":
        with pytest.raises(RuntimeError, match="fixture interruption"):
            execute()
    else:
        execute()
    if outcome == "accepted":
        assert context["analyses"][24] == "candidate"
        assert context["_trade_source_manifest"]["catalog"]["changed"] == 1
        assert context["_trade_completion_receipt"]["diagnostics"]["finish_reasons"] == ["STOP"]
    else:
        assert context["analyses"] == before["analyses"]
        assert context["_trade_source_manifest"] == before["_trade_source_manifest"]
        assert context["_trade_completion_receipt"] == before["_trade_completion_receipt"]
