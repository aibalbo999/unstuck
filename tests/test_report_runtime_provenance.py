from model_execution_provenance import model_executions_from_events
from report_reproducibility import build_reproducibility_packet
from data_trust_snapshot import build_data_snapshot
from analysis_input_provenance import freeze_analysis_inputs
from analysis_job_provenance import attach_model_executions


def test_report_packet_records_actual_final_model_and_fallback_route():
    context = {
        "ticker": "2308.TW",
        "pipeline_id": "v2",
        "model_id": "configured-but-not-executed",
        "agent_sequence": (11, 16),
        "analysis_input_cutoff": "2026-09-09T00:01:02+00:00",
        "model_executions": {
            11: {
                "agent_num": 11,
                "model_id": "gemini-primary",
                "route_index": 0,
                "route_considered": ["gemini-primary"],
                "provider_call_models": ["gemini-primary"],
                "route_skipped": [],
                "failed_models": [],
                "fallback_used": False,
                "cache_hit": False,
            },
            16: {
                "agent_num": 16,
                "model_id": "gemini-fallback",
                "route_index": 1,
                "route_considered": ["gemini-primary", "gemini-fallback"],
                "provider_call_models": ["gemini-primary", "gemini-fallback"],
                "route_skipped": [],
                "failed_models": [],
                "fallback_used": True,
                "cache_hit": False,
            },
        },
        "data": {
            "source_audit": [
                {"provider": "first", "fetched_at": "2026-09-09T08:00:00+08:00"},
                {"provider": "last", "fetched_at": "2026-09-09T00:01:00+00:00"},
            ],
        },
    }

    packet = build_reproducibility_packet(context, {}, "2026-09-09T00:03:00+00:00")

    assert packet["model_id"] == "gemini-fallback"
    assert packet["analysis_input_cutoff"] == "2026-09-09T00:01:02+00:00"
    assert packet["analysis_input_hash"] == ""
    assert packet["input_bundle_observed_at"] == "2026-09-09T00:01:00+00:00"
    assert packet["input_first_available_at"] == ""
    assert packet["source_publication_at"] == ""
    assert packet["source_provenance_coverage"] == "incomplete"
    assert packet["model_executions"] == [
        {**context["model_executions"][11], "generation_policy_version": "", "generation_config": {}},
        {**context["model_executions"][16], "generation_policy_version": "", "generation_config": {}},
    ]


def test_model_execution_receipt_distinguishes_skipped_provider_and_cache_routes():
    def event(phase, model, *, agent=24):
        return {"payload": {"pipeline_id": "v4", "agent_num": agent, "phase": phase,
                            "metadata": {"model_id": model}}}

    receipts = model_executions_from_events([
        event("model_circuit_open", "primary-model"),
        event("model_fallback", "fallback-model"),
        event("llm_provider_request", "fallback-model"),
        event("agent_step_cache_hit", "fallback-model"),
        event("llm_model_response", "ignored-other-pipeline") | {"payload": {"pipeline_id": "v3"}},
    ], "v4")

    assert receipts[24] == {
        "agent_num": 24,
        "model_id": "fallback-model",
        "route_index": 1,
        "route_considered": ["primary-model", "fallback-model"],
        "provider_call_models": ["fallback-model"],
        "route_skipped": ["primary-model"],
        "failed_models": [],
        "fallback_used": True,
        "cache_hit": True,
        "generation_policy_version": "",
        "generation_config": {},
    }


def test_model_execution_receipt_keeps_secret_safe_generation_settings():
    receipts = model_executions_from_events([{
        "payload": {
            "pipeline_id": "v4",
            "agent_num": 24,
            "phase": "llm_model_response",
            "metadata": {
                "model_id": "gemini-3.8-flash",
                "generation_policy_version": "agent-generation:v1",
                "generation_config": {
                    "temperature": 0.2,
                    "top_p": 0.85,
                    "max_output_tokens": 2048,
                    "thinking_level": "medium",
                    "api_key": "must-not-survive",
                },
            },
        },
    }], "v4")

    assert receipts[24]["generation_policy_version"] == "agent-generation:v1"
    assert receipts[24]["generation_config"] == {
        "temperature": 0.2,
        "top_p": 0.85,
        "max_output_tokens": 2048,
        "thinking_level": "medium",
    }


def test_job_provenance_attaches_only_persisted_successful_model_routes():
    context = {}
    events = [
        {"payload": {"pipeline_id": "v4", "agent_num": 22, "phase": "llm_model_call",
                     "metadata": {"model_id": "model-a"}}},
        {"payload": {"pipeline_id": "v4", "agent_num": 22, "phase": "llm_provider_request",
                     "metadata": {"model_id": "model-a"}}},
        {"payload": {"pipeline_id": "v4", "agent_num": 22, "phase": "llm_model_response",
                     "metadata": {"model_id": "model-a"}}},
    ]

    attach_model_executions(context, events, "v4")

    assert context["model_executions"][22]["model_id"] == "model-a"
    assert context["model_executions"][22]["provider_call_models"] == ["model-a"]


def test_snapshot_keeps_small_oos_evaluation_inputs_when_rerun_context_is_trimmed():
    context = {
        "ticker": "2308.TW",
        "pipeline_id": "v4",
        "data": {"ticker": "2308.TW"},
        "parsed": {
            "recommendation": {"建議": "買入"},
            "price_targets": {"合理價": 101},
            "trade_setup": {
                "trade_direction": "Long",
                "entry_zone": [90, 92],
                "target_price": 105,
                "stop_loss": 88,
            },
        },
        "analyses": {24: "x" * 20_000},
        "structured_outputs": {24: {"large": "y" * 20_000}},
    }

    snapshot = build_data_snapshot(context, max_bytes=2_000)

    assert snapshot["oos_evaluation_inputs"] == {
        "pipeline_id": "v4",
        "recommendation": {"建議": "買入"},
        "price_targets": {"合理價": 101},
        "trade_setup": {
            "trade_direction": "Long",
            "entry_zone": [90, 92],
            "target_price": 105,
            "stop_loss": 88,
        },
    }
    assert "parsed" not in snapshot["rerun_context"]


def test_freeze_analysis_inputs_runs_after_mode_memory_and_is_stable():
    mode_data = {
        "ticker": "2308.TW",
        "quant_metrics": {"price": 100},
        "temporal_memory": {"prior_report": "evidence"},
    }

    receipt = freeze_analysis_inputs(mode_data, cutoff="2026-09-09T00:01:02+00:00")

    assert receipt == {
        "analysis_input_cutoff": "2026-09-09T00:01:02+00:00",
        "analysis_input_hash": mode_data["analysis_input_hash"],
    }
    assert len(receipt["analysis_input_hash"]) == 64
    assert mode_data["analysis_input_cutoff"] == receipt["analysis_input_cutoff"]
    assert freeze_analysis_inputs(dict(mode_data), cutoff=receipt["analysis_input_cutoff"]) == receipt
