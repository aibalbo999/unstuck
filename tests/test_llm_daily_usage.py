import json
from datetime import datetime
from zoneinfo import ZoneInfo


def row(at, operation, *, status="success", kind=None, usage=None, units=0, model="model-a"):
    metadata = {"key_slot": 3, "api_key": "do-not-expose"}
    if kind:
        metadata["error_kind"] = kind
    if usage is not None:
        metadata["response_diagnostics"] = {"usage": usage}
    return {"created_at": datetime.fromisoformat(at).timestamp(), "operation": operation,
            "status": status, "model_id": model, "units": units, "metadata_json": json.dumps(metadata)}


def profile(rows, *, timezone="Asia/Taipei"):
    import llm_daily_usage
    return llm_daily_usage.build_daily_usage_profile(
        rows, now=datetime.fromisoformat("2026-09-05T20:00:00+08:00"), days=2,
        timezone=timezone, ledger_started_at=datetime.fromisoformat("2026-09-01T00:00:00+08:00").timestamp(),
    )


def test_daily_profile_counts_requests_not_plans_or_responses():
    result = profile([
        row("2026-09-04T10:00:00+08:00", "llm_model_call", units=1),
        row("2026-09-04T10:00:01+08:00", "llm_provider_request", units=1),
        row("2026-09-04T10:00:02+08:00", "llm_model_response", usage={"input_tokens": 100, "output_tokens": 10}),
        row("2026-09-05T10:00:01+08:00", "llm_provider_request", units=1),
        row("2026-09-05T10:00:02+08:00", "llm_provider_request", units=1),
    ])
    assert result["complete_days"]["requests"] == 1
    assert result["complete_days"]["average_requests"] == 0.5
    assert result["today"]["requests"] == 2
    assert result["models"]["model-a"]["success_events"] == 1
    assert result["models"]["model-a"]["input_tokens"]["p95"] == 100
    assert "do-not-expose" not in json.dumps(result)


def test_daily_profile_separates_local_blocks_and_provider_errors():
    result = profile([
        row("2026-09-04T10:00:00+08:00", "llm_model_error", status="quota_error", kind="ModelCircuitOpenError"),
        row("2026-09-04T10:00:01+08:00", "llm_model_error", status="quota_error", kind="AllKeysRpdDisabledError"),
        row("2026-09-04T10:00:02+08:00", "llm_model_error", status="quota_error", kind="ClientError"),
        row("2026-09-04T10:00:03+08:00", "llm_model_error", status="quota_error", kind="InputCapacityExceededError"),
        row("2026-09-04T10:00:04+08:00", "llm_model_error", status="error", kind="AgentShortResponseError", usage={"input_tokens": 200}),
    ])
    model = result["models"]["model-a"]
    assert model["local_blocks"] == 3
    assert model["provider_quota_errors"] == 1
    assert model["other_errors"] == 1
    assert model["input_tokens"]["total"] == 200


def test_missing_usage_stays_unknown_and_bad_values_are_not_counts():
    result = profile([
        row("2026-09-04T10:00:00+08:00", "llm_model_response"),
        row("2026-09-04T10:00:01+08:00", "llm_model_response", usage={"input_tokens": True}),
        row("2026-09-04T10:00:02+08:00", "llm_model_response", usage={"input_tokens": -1}),
    ])
    tokens = result["models"]["model-a"]["input_tokens"]
    assert tokens["total"] is None
    assert tokens["p95"] is None
    assert tokens["samples"] == 0
    assert tokens["coverage_pct"] == 0


def test_pacific_daily_boundary_and_rolling_minute_peak():
    result = profile([
        row("2026-09-05T14:59:50+08:00", "llm_provider_request", units=1),
        row("2026-09-05T15:00:10+08:00", "llm_provider_request", units=1),
        row("2026-09-05T15:01:10+08:00", "llm_provider_request", units=1),
    ], timezone="America/Los_Angeles")
    assert result["today"]["requests"] == 2
    assert result["daily"][-2]["requests"] == 1
    assert result["peak_requests_60s"] == 2


def test_partial_ledger_day_is_not_in_complete_day_average():
    import llm_daily_usage
    at = datetime(2026, 9, 4, 12, tzinfo=ZoneInfo("Asia/Taipei"))
    result = llm_daily_usage.build_daily_usage_profile(
        [row(at.isoformat(), "llm_provider_request", units=1)],
        now=datetime(2026, 9, 5, 20, tzinfo=at.tzinfo), days=2,
        ledger_started_at=at.timestamp(),
    )
    assert result["complete_days"]["count"] == 0
    assert result["complete_days"]["average_requests"] is None


def test_store_reader_uses_canonical_ledger_and_adds_daily_profile(tmp_path):
    import api_usage_store
    db = tmp_path / "ops.sqlite3"
    api_usage_store.record_api_usage(service="Gemini / Google AI", provider="google_ai", operation="llm_provider_request",
                                     units=1, model_id="model-a", db_path=db, created_at=100)
    assert hasattr(api_usage_store, "summarize_llm_daily_usage")
    result = api_usage_store.summarize_llm_daily_usage(now=datetime.fromtimestamp(200, ZoneInfo("UTC")), days=2, db_path=db)
    assert result["today"]["requests"] == 1


def test_api_quota_exposes_daily_demand_separate_from_provider_limits(monkeypatch, tmp_path):
    import api_quota_service
    import api_usage_store
    monkeypatch.setattr(api_usage_store, "API_USAGE_DB_PATH", str(tmp_path / "ops.sqlite3"))
    api_usage_store.reset_api_usage_store_for_tests()
    api_usage_store.record_api_usage(service="Gemini / Google AI", provider="google_ai", operation="llm_provider_request", model_id="model-a")
    payload = api_quota_service.build_api_quota_payload(lambda _: [])
    service = payload["services"][0]
    assert service["usage"]["daily_profile"]["today"]["requests"] == 1
    assert service["usage"]["quota_day_profile"]["timezone"] == "America/Los_Angeles"
    assert service["limit_basis"] == "local_configuration_not_verified_provider_quota"
    assert payload["model_policy"]["provider_limits_verified"] is False
    assert "input_token_limits" in payload["model_policy"]
