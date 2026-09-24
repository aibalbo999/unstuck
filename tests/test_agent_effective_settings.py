"""Effective policies must be observable without revealing credentials or prompts."""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_routes.observability import ObservabilityRouteDeps, create_observability_router
from data_trust_snapshot_sanitizer import sanitize_for_snapshot


def test_agent_settings_endpoint_reports_process_scope_and_every_registered_agent():
    from agent_catalog import AGENT_NAMES

    app = FastAPI()
    app.include_router(create_observability_router(ObservabilityRouteDeps(
        get_provider_sla_summary=lambda _: [],
        get_provider_sla_alerts=lambda _: [],
        get_task_queue=lambda: None,
    )))
    response = TestClient(app).get("/api/observability/agent-settings")
    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_scope"] == "api_process"
    assert payload["worker_settings_verified"] is False
    assert {row["agent_num"] for row in payload["agents"]} == set(AGENT_NAMES)
    assert len(payload["effective_settings_sha256"]) == 64


def test_snapshot_preserves_only_validated_generation_fields_not_tokens_or_prompts():
    payload = {"metadata": {"generation_config": {
        "temperature": 0.25, "top_p": 0.9, "max_output_tokens": 6144,
        "thinking_level": "low", "api_key": "private-key", "access_token": "private-token",
        "system_instruction": "private-prompt", "response_schema": {"secret": "private-schema"},
    }, "access_token": "private-token"}}
    result = sanitize_for_snapshot(payload)
    assert result == {"metadata": {"generation_config": {
        "temperature": 0.25, "top_p": 0.9, "max_output_tokens": 6144, "thinking_level": "low",
    }}}
    malicious = sanitize_for_snapshot({"generation_config": {
        "max_output_tokens": "private-key", "temperature": float("nan"),
        "top_p": {"api_key": "private-key"}, "thinking_level": "private-key",
    }})
    assert malicious == {"generation_config": {}}
    assert sanitize_for_snapshot({"generation_config": {
        "temperature": 10 ** 1000, "top_p": -(10 ** 1000),
        "max_output_tokens": 10 ** 1000,
    }}) == {"generation_config": {}}
    assert "private-" not in json.dumps(result)


def test_effective_route_and_hash_include_role_flags_and_generation_overrides(monkeypatch):
    # Settings reload tests may replace sys.modules['config']; patch the policy
    # module's actual import-time binding, just as the running process reads it.
    from agent_effective_settings import config
    from agent_effective_settings import build_agent_settings_payload
    from agent_runtime import routing
    from agent_runtime.generation_config import AGENT_GENERATION_PROFILES

    monkeypatch.setitem(routing.AGENT_MODELS, 7, "gemini-3.8-flash")
    monkeypatch.setitem(routing.AGENT_FALLBACK_MODELS, 7, ["gemini-3.6-flash"])
    monkeypatch.setitem(config.CRITICAL_LITE_FALLBACK_AGENTS, 7, False)
    before = build_agent_settings_payload()
    monkeypatch.setitem(config.CRITICAL_LITE_FALLBACK_AGENTS, 7, True)
    after = build_agent_settings_payload()
    row = next(row for row in after["agents"] if row["agent_num"] == 7)
    assert row["configured_fallback_models"] == ["gemini-3.6-flash"]
    assert row["effective_model_sequence"] == ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
    assert before["effective_settings_sha256"] != after["effective_settings_sha256"]
    assert before["model_routes_file_sha256"] == after["model_routes_file_sha256"]
    monkeypatch.setitem(AGENT_GENERATION_PROFILES[7], "max_output_tokens", 5120)
    changed = build_agent_settings_payload()
    assert changed["effective_settings_sha256"] != after["effective_settings_sha256"]
    monkeypatch.setitem(config.TPM_LIMITS, config.EMBEDDING_MODEL, 12345)
    assert build_agent_settings_payload()["effective_settings_sha256"] != changed["effective_settings_sha256"]


def test_effective_snapshot_uses_actual_tool_schema_thinking_and_candidate_capacity(monkeypatch):
    from agent_effective_settings import config
    from agent_effective_settings import build_agent_settings_payload
    from agent_runtime.generation_config import build_generation_config
    from agent_runtime.prompt_budget import get_agent_context_input_token_limit, get_agent_prompt_token_budget

    monkeypatch.setattr(config, "LLM_API_KEYS_BY_PROVIDER", {"google": ["private-key"], "openai": []})
    payload = build_agent_settings_payload()
    by_agent = {row["agent_num"]: row for row in payload["agents"]}
    assert by_agent[2]["output_contract"]["effective_tools"] == ["calculate_cagr"]
    assert by_agent[4]["output_contract"]["effective_tools"] == []
    assert by_agent[6]["output_contract"]["reasoning_mode"] == "single_model_simulated_debate"
    assert by_agent[24]["output_contract"]["deterministic_risk_policy"] == "negative-fcf:v1"
    assert payload["auxiliary_roles"]["chief_editor"]["execution_kind"] == "deterministic"
    assert by_agent[4]["output_contract"]["native_schema_enabled"] is bool(build_generation_config(4).response_schema)
    for candidate in by_agent[24]["candidates"]:
        assert candidate["supplementary_context_budget_tokens"] == get_agent_prompt_token_budget(24, model_id=candidate["model_id"])
        assert candidate["configured_context_input_ceiling_tokens"] == get_agent_context_input_token_limit(24, candidate["model_id"])
    assert payload["quota_scope"]["project_mapping_status"] == "unknown"
    assert payload["quota_scope"]["independent_project_count"] is None
    assert "private-key" not in json.dumps(payload)
    assert "system_instruction\"" not in json.dumps(payload)
    assert "analysis_prompts" not in json.dumps(payload)


def test_worker_generation_provenance_survives_rerun_persistence_and_sse(monkeypatch):
    from types import SimpleNamespace
    import agent_effective_settings as settings
    from agent_runtime.llm_call_events import llm_provider_request_event
    from api_routes.analysis_sse_payloads import sanitize_replay_payload
    from model_execution_provenance import model_executions_from_events, normalized_model_executions
    import report_rerun_jobs as jobs

    settings.process_settings_sha256.cache_clear()
    events = []
    monkeypatch.setattr(jobs, "is_job_cancel_requested", lambda _: False)
    monkeypatch.setattr(jobs, "append_event", lambda job, event: events.append(event))
    event = llm_provider_request_event({"pipeline_id": "v4"}, 24, "gemini-3.8-flash", "private-prompt",
                                       SimpleNamespace(keys=["private-key"]), "private-key", timeout_seconds=120)
    jobs._append_progress_event("job", "report.html", "final_recommendation", event)
    replay = sanitize_replay_payload(events[0], job_id="job")
    assert replay["metadata"]["generation_config"]["max_output_tokens"] == 4096
    assert replay["metadata"]["effective_settings_sha256"] == settings.build_agent_settings_payload()["effective_settings_sha256"]
    assert replay["metadata"]["settings_snapshot_scope"] == "executing_process"
    assert "private-" not in json.dumps(replay)
    replay["phase"] = "llm_model_response"
    records = model_executions_from_events([{"payload": replay}], "v4")
    receipt = normalized_model_executions({"model_executions": records})[0]
    assert receipt["effective_settings_sha256"] == replay["metadata"]["effective_settings_sha256"]
    assert receipt["generation_config"]["max_output_tokens"] == 4096
    settings.process_settings_sha256.cache_clear()
