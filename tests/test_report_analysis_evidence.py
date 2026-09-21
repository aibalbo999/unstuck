"""Original analysis evidence survives replacement of the current data snapshot."""

import asyncio
from copy import deepcopy
import json
import pytest

from analysis_input_provenance import freeze_analysis_inputs
from data_trust_snapshot_integrity import verify_data_snapshot_integrity
from data_trust_snapshot_sanitizer import sanitize_for_snapshot
from report_persistence import report_bundle_keys_for_filename
from storage.report_storage import InMemoryStorage


def original_snapshot():
    data = {"ticker": "2330.TW", "current_price": 100,
            "quant_metrics": {"rsi": 61}, "source_audit": []}
    freeze_analysis_inputs(data, cutoff="2026-09-21T01:00:00Z")
    return {"ticker": "2330.TW", "pipeline": "v4", "generated_at": "2026-09-21T01:05:00Z",
            "data": sanitize_for_snapshot(data), "rerun_context": {"market_context_manifests": {"24": {"visible": True}}},
            "market_context_original_input_fingerprint": "a" * 64}


def refresh(snapshot, tmp_path, monkeypatch, price=105):
    import report_refresh_service
    monkeypatch.setattr(report_refresh_service, "upsert_report_metadata", lambda *a, **kw: {})
    filename = "2330_TW_v4_report_20260921_010500.html"
    keys = report_bundle_keys_for_filename(filename)
    storage = InMemoryStorage()
    storage.save_report(keys.html_key, b"<html></html>", content_type="text/html")
    storage.save_report(keys.data_key, json.dumps(snapshot).encode(), content_type="application/json")
    response = asyncio.run(report_refresh_service.refresh_report_data_snapshot(
        filename, output_dir=str(tmp_path), refresh_service=None, storage=storage,
        refreshed_data={"ticker": "2330.TW", "current_price": price, "source_audit": []}))
    return json.loads(storage.get_report(keys.data_key).content), response


def test_refresh_preserves_original_input_quant_and_manifest_across_cold_reads(tmp_path, monkeypatch):
    original = original_snapshot()
    first, response = refresh(original, tmp_path, monkeypatch)
    assert first["data"]["current_price"] == 105
    assert response["analysis_text_stale"] is True
    packet = first["analysis_evidence"]
    assert packet["status"] == "preserved"
    assert packet["sections"]["analysis_input"]["data"] == original["data"]
    assert packet["sections"]["quant_metrics"]["data"] == {"rsi": 61}
    assert packet["sections"]["market_context_manifests"]["data"] == original["rerun_context"]["market_context_manifests"]
    assert packet["analysis_input_hash"] == original["data"]["analysis_input_hash"]
    second, _ = refresh(first, tmp_path, monkeypatch, price=110)
    assert second["analysis_evidence"] == packet
    assert second["data"]["current_price"] == 110
    assert second["decision_validity_status"] == "needs_rerun"
    assert verify_data_snapshot_integrity(second)["valid"] is True


@pytest.mark.parametrize("change", ["missing_hash", "changed_data", "already_refreshed", "truncated"])
def test_legacy_without_original_proof_stays_unknown_even_after_more_refreshes(tmp_path, monkeypatch, change):
    original = original_snapshot()
    if change == "missing_hash":
        original["data"].pop("analysis_input_hash")
    elif change == "changed_data":
        original["data"]["current_price"] = 99
    elif change == "already_refreshed":
        original["snapshot_refreshed_at"] = "2026-09-21T02:00:00Z"
    else:
        original["snapshot_truncated"] = True
    first, _ = refresh(original, tmp_path, monkeypatch)
    assert first["analysis_evidence"]["status"] == "unknown"
    assert first["analysis_evidence"]["sections"] == {}
    # A valid receipt on the NEW data cannot retroactively prove the old input.
    freeze_analysis_inputs(first["data"])
    second, _ = refresh(first, tmp_path, monkeypatch, price=110)
    assert second["analysis_evidence"] == first["analysis_evidence"]


def test_modified_packet_is_not_rebuilt_from_replacement_data(tmp_path, monkeypatch):
    first, _ = refresh(original_snapshot(), tmp_path, monkeypatch)
    first["analysis_evidence"]["sections"]["quant_metrics"]["data"]["rsi"] = 999
    second, _ = refresh(first, tmp_path, monkeypatch)
    assert second["analysis_evidence"]["status"] == "unknown"
    assert second["analysis_evidence"]["reason_codes"] == ["invalid_analysis_evidence"]


def test_render_capture_separates_hash_unverified_input_from_known_quant_and_manifest():
    from report_analysis_evidence import capture_analysis_evidence
    context = original_snapshot()
    context["data"]["enrichment_after_freeze"] = True
    context["_trade_source_manifest"] = {"visible": True, "fingerprint": "b" * 64, "catalog": {"close": 100}}
    packet = capture_analysis_evidence(context)
    assert packet["status"] == "partial"
    assert packet["capture_boundary"] == "report_render"
    assert packet["input_verification"] == "unknown"
    assert packet["sections"]["analysis_input"] == {"status": "unknown"}
    assert packet["sections"]["quant_metrics"]["data"] == {"rsi": 61}
    assert packet["sections"]["trade_source_manifest"]["data"] == context["_trade_source_manifest"]


def test_evidence_is_bounded_without_truncating_or_relabeling_an_input():
    from report_analysis_evidence import capture_analysis_evidence, MAX_ANALYSIS_EVIDENCE_BYTES, validate_analysis_evidence
    context = original_snapshot()
    context["data"]["financial_rows"] = ["x" * 1024] * 600
    freeze_analysis_inputs(context["data"])
    packet = capture_analysis_evidence(context)
    assert len(json.dumps(packet).encode()) < MAX_ANALYSIS_EVIDENCE_BYTES
    assert packet["status"] == "partial"
    assert packet["sections"]["analysis_input"]["status"] == "omitted"
    assert "data" not in packet["sections"]["analysis_input"]
    assert packet["sections"]["analysis_input"]["fingerprint"]
    assert packet["sections"]["quant_metrics"]["data"] == {"rsi": 61}
    assert validate_analysis_evidence(packet) == packet


def test_sensitive_keys_and_private_runtime_context_are_not_copied():
    from report_analysis_evidence import capture_analysis_evidence
    context = original_snapshot()
    context["data"]["nested"] = {"api_key": "SECRET_A", "authorization": "SECRET_B", "safe": 12}
    context["data"]["_private"] = "SECRET_C"
    context["analyses"] = {"24": "SECRET_D"}
    context["prompt"] = "SECRET_E"
    freeze_analysis_inputs(context["data"])
    packet = capture_analysis_evidence(context)
    assert "SECRET_" not in json.dumps(packet)
    assert packet["sections"]["analysis_input"]["data"]["nested"] == {"safe": 12}


def test_capture_records_original_market_input_identity_when_renderer_has_not_added_it():
    from market_context_manifest import market_input_fingerprint
    from report_analysis_evidence import capture_analysis_evidence
    context = original_snapshot()
    context.pop("market_context_original_input_fingerprint")
    expected = market_input_fingerprint(context["data"])
    context["rerun_context"]["market_context_manifests"] = {"7": {"input_fingerprint": expected}}
    packet = capture_analysis_evidence(context)
    assert packet["market_context_original_input_fingerprint"] == expected


def test_snapshot_governance_keeps_packet_and_does_not_mutate_original():
    from data_trust_snapshot import build_data_snapshot
    from report_analysis_evidence import capture_analysis_evidence
    context = original_snapshot()
    packet = capture_analysis_evidence(context)
    context["analysis_evidence"] = packet
    before = deepcopy(context)
    snapshot = build_data_snapshot(context, max_bytes=3000)
    assert snapshot["analysis_evidence"] == packet
    assert context == before
    assert verify_data_snapshot_integrity(snapshot)["valid"]


def test_renderer_captures_before_size_governance_and_packet_survives_refresh(tmp_path, monkeypatch):
    import reporting.renderer as renderer
    from reporting.types import ReportRequest
    async def html(context):
        return "<html>Report</html>"
    monkeypatch.setattr(renderer, "generate_html_report_async", html)
    monkeypatch.setattr(renderer, "generate_markdown_report", lambda context: "Report")
    monkeypatch.setattr(renderer, "_lint_or_repair", lambda html, md: (html, md, {"status": "passed"}))
    monkeypatch.setattr(renderer, "evaluate_report_evidence", lambda *a, **kw: {})
    monkeypatch.setattr(renderer, "evaluate_content_credibility", lambda *a, **kw: {})
    monkeypatch.setattr(renderer, "evaluate_report_conformance", lambda *a, **kw: {})
    context = original_snapshot()
    context["_trade_source_manifest"] = {"visible": True, "fingerprint": "b" * 64, "catalog": {"close": 100}}
    bundle = asyncio.run(renderer.ReportRenderer().render_async(ReportRequest(
        context=context, pipeline_id="v4", generated_at=context["generated_at"])))
    packet = bundle.data_snapshot["analysis_evidence"]
    assert packet["capture_boundary"] == "report_render"
    assert packet["original_generated_at"] == context["generated_at"]
    assert packet["sections"]["trade_source_manifest"]["data"] == context["_trade_source_manifest"]
    refreshed, _ = refresh(bundle.data_snapshot, tmp_path, monkeypatch)
    assert refreshed["analysis_evidence"] == packet
    assert verify_data_snapshot_integrity(refreshed)["valid"]


def test_frozen_input_survives_enrichment_and_checkpoint_without_entering_prompt():
    from prompt_evidence import prompt_evidence_copy
    from report_analysis_evidence import capture_analysis_evidence
    from workflow_services import initialize_graph_state
    from workflow_context import input_data_from_state
    data = {"ticker": "2330.TW", "current_price": 100, "quant_metrics": {"rsi": 61}}
    receipt = freeze_analysis_inputs(data, cutoff="2026-09-21T01:00:00Z")
    original = sanitize_for_snapshot(data)
    assert isinstance(data.get("_analysis_input_evidence"), str)
    assert "_analysis_input_evidence" not in prompt_evidence_copy(data)
    data["quant_metrics"]["rsi"] = 70
    data["enriched"] = True
    state = initialize_graph_state(data, pipeline_id="v4")
    resumed = input_data_from_state(json.loads(json.dumps(state)))
    packet = capture_analysis_evidence({"data": resumed})
    assert packet["input_verification"] == "hash_verified"
    assert packet["analysis_input_hash"] == receipt["analysis_input_hash"]
    assert packet["sections"]["analysis_input"]["data"] == original
    assert packet["sections"]["quant_metrics"]["data"] == {"rsi": 61}
    assert packet["sections"]["render_quant_metrics"]["data"] == {"rsi": 70}


def test_refreeze_replaces_private_receipt_without_changing_hash_contract_or_recursing():
    import hashlib
    from report_analysis_evidence import capture_analysis_evidence
    data = {"ticker": "2330.TW", "current_price": 100}
    first = freeze_analysis_inputs(data, cutoff="2026-09-21T01:00:00Z")
    data["current_price"] = 105
    second = freeze_analysis_inputs(data, cutoff="2026-09-21T02:00:00Z")
    expected = hashlib.sha256(json.dumps({"ticker": "2330.TW", "current_price": 105}, ensure_ascii=False,
                                        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert second["analysis_input_hash"] == expected != first["analysis_input_hash"]
    packet = capture_analysis_evidence({"data": data})
    assert packet["sections"]["analysis_input"]["data"]["current_price"] == 105
    assert "_analysis_input_evidence" not in json.dumps(packet)


def test_frozen_input_survives_real_sqlite_checkpoint_retry(tmp_path):
    from langgraph.graph import END, START, StateGraph
    from workflow_checkpoints import execute_persistent_graph
    from workflow_state import AgentGraphState
    from workflow_context import input_data_from_state
    from report_analysis_evidence import capture_analysis_evidence
    data = {"ticker": "2330.TW", "current_price": 100, "quant_metrics": {"rsi": 61}}
    freeze_analysis_inputs(data)
    calls = []
    def builder(fail):
        graph = StateGraph(AgentGraphState)
        async def enrich(state):
            calls.append("enrich")
            enriched = deepcopy(state["raw_financial_data"])
            enriched["input"]["quant_metrics"]["rsi"] = 70
            return {"raw_financial_data": enriched}
        async def finish(state):
            if fail:
                raise RuntimeError("fixture deferred work")
            return {"status": "done"}
        graph.add_node("enrich", enrich)
        graph.add_node("finish", finish)
        graph.add_edge(START, "enrich")
        graph.add_edge("enrich", "finish")
        graph.add_edge("finish", END)
        return graph
    async def run(fail, initial):
        return await execute_persistent_graph(graph_builder=builder(fail), initial_state=initial,
            thread_id="evidence-resume", checkpoint_path=tmp_path / "isolated-checkpoint.sqlite3")
    with pytest.raises(RuntimeError, match="fixture deferred work"):
        asyncio.run(run(True, {"raw_financial_data": {"input": data}, "pipeline_id": "v4"}))
    resumed = asyncio.run(run(False, {"raw_financial_data": {"input": {"current_price": 999}}}))
    packet = capture_analysis_evidence({"data": input_data_from_state(resumed)})
    assert calls == ["enrich"]
    assert packet["sections"]["analysis_input"]["data"]["current_price"] == 100
    assert packet["sections"]["quant_metrics"]["data"] == {"rsi": 61}
    assert packet["sections"]["render_quant_metrics"]["data"] == {"rsi": 70}


def test_frozen_receipt_mismatch_is_unknown_instead_of_rebuilding_from_current_data():
    from report_analysis_evidence import capture_analysis_evidence
    data = {"current_price": 100}
    freeze_analysis_inputs(data)
    data["analysis_input_hash"] = "a" * 64
    packet = capture_analysis_evidence({"data": data})
    assert packet["status"] == "unknown"
    assert packet["reason_codes"] == ["invalid_frozen_analysis_evidence"]
