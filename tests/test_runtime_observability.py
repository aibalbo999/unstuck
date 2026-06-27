import asyncio
import sys
import subprocess
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import api  # noqa: E402
import api_observability_service  # noqa: E402
import api_quota_service  # noqa: E402
import api_usage_store  # noqa: E402
import context_digest_tasks  # noqa: E402
import job_observability  # noqa: E402
import job_store  # noqa: E402
import job_store_maintenance  # noqa: E402
import provider_sla  # noqa: E402
from data_fetch import FetchResult  # noqa: E402
from data_trust import DATA_SNAPSHOT_SCHEMA_VERSION, unknown_data_trust  # noqa: E402
from reporting import ReportBundle  # noqa: E402
from reporting.cover import _build_cover_generation_config  # noqa: E402
import analysis_jobs  # noqa: E402


def test_job_store_indexes_events_and_cancel_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))

    job_id = job_store.create_job("2449.TW", "both")
    job_store.append_event(
        job_id,
        {
            "type": "status",
            "phase": "model_call",
            "level": "info",
            "message": "calling model",
        },
    )

    rows = job_store.query_events(job_id, event_type="status", phase="model_call")
    assert rows[0]["payload"]["message"] == "calling model"
    assert rows[0]["event_type"] == "status"
    assert rows[0]["phase"] == "model_call"

    assert job_store.request_job_cancel(job_id, "cancel please") is True
    assert job_store.is_job_cancel_requested(job_id) is True
    assert job_store.find_active_job("2449.TW", "both") == {}


def test_job_store_preserves_terminal_state_invariants(monkeypatch, tmp_path):
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))

    job_id = job_store.create_job("2449.TW", "both")
    assert job_store.request_job_cancel(job_id, "stop now") is True

    job_store.update_job(job_id, "done", filename="should-not-win.html")
    cancelled = job_store.get_job(job_id)

    assert cancelled["status"] == "cancelled"
    assert cancelled["filename"] is None
    assert "stop now" in cancelled["error"]

    job_store.update_job(job_id, "done", filename="late.html")
    job_store.update_job(job_id, "error", error="late error")
    still_cancelled = job_store.get_job(job_id)

    assert still_cancelled["status"] == "cancelled"
    assert still_cancelled["filename"] is None
    assert "stop now" in still_cancelled["error"]


def test_abandoned_local_jobs_are_scoped_to_worker_owner(monkeypatch, tmp_path):
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    job_store.reset_job_store_for_tests()

    mine = job_store.create_job("2449.TW", "v1", worker_instance_id="server-a")
    other = job_store.create_job("2330.TW", "v1", worker_instance_id="server-b")
    legacy = job_store.create_job("AAPL", "v1")
    job_store.update_job(mine, "running")
    job_store.update_job(other, "running")
    job_store.update_job(legacy, "running")

    abandoned = job_store.mark_incomplete_jobs_abandoned("restart cleanup", worker_instance_id="server-a")

    assert abandoned == 1
    assert job_store.get_job(mine)["status"] == "error"
    assert job_store.get_job(mine)["cancel_requested"] == 1
    assert job_store.get_job(other)["status"] == "running"
    assert job_store.get_job(legacy)["status"] == "running"


def test_api_no_longer_owns_local_runtime_abandonment_cleanup():
    source = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")

    assert "acquire_local_runtime_instance_lock" not in source
    assert "_mark_abandoned_local_jobs" not in source
    assert "mark_incomplete_jobs_abandoned" not in source


def test_provider_sla_aggregates_source_audit(monkeypatch, tmp_path):
    monkeypatch.setattr(provider_sla, "TASK_DB_PATH", str(tmp_path / "provider.sqlite3"))

    provider_sla.record_source_audit_entries(
        [
            {"source": "market_data", "provider": "yfinance", "status": "success", "duration_ms": 100, "record_count": 3},
            {"source": "market_data", "provider": "yfinance", "status": "error", "duration_ms": 50, "record_count": 0, "message": "boom"},
            {"source": "recent_catalysts", "provider": "Google Search", "status": "skipped_fresh_cache", "duration_ms": 0},
        ]
    )

    summary = provider_sla.get_provider_sla_summary()
    yfinance = next(row for row in summary if row["provider"] == "yfinance")
    assert yfinance["attempts"] == 2
    assert yfinance["success_count"] == 1
    assert yfinance["error_count"] == 1
    assert yfinance["success_rate"] == 0.5
    assert yfinance["avg_duration_ms"] == 75
    assert yfinance["windows"]["last_1h"]["attempts"] == 2
    assert yfinance["windows"]["last_1h"]["success_rate"] == 0.5
    assert yfinance["alert_level"] == "warning"
    google = next(row for row in summary if row["provider"] == "Google Search")
    assert google["attempts"] == 1
    assert google["skipped_fresh_cache_count"] == 1
    assert google["success_rate"] == 1.0
    assert google["windows"]["last_1h"]["success_rate"] == 1.0
    assert google["alert_level"] == "ok"
    alerts = provider_sla.get_provider_sla_alerts()
    assert alerts and alerts[0]["provider"] == "yfinance"
    assert "windows" in alerts[0]


def test_provider_sla_tracks_not_configured_without_alerting(monkeypatch, tmp_path):
    monkeypatch.setattr(provider_sla, "TASK_DB_PATH", str(tmp_path / "provider.sqlite3"))

    provider_sla.record_source_audit_entries(
        [
            {"source": "recent_catalysts", "provider": "Google Search", "status": "not_configured", "duration_ms": 0},
            {"source": "recent_catalysts", "provider": "Google Search", "status": "not_configured", "duration_ms": 0},
            {"source": "recent_catalysts", "provider": "Google Search", "status": "not_configured", "duration_ms": 0},
        ]
    )

    summary = provider_sla.get_provider_sla_summary()
    google = next(row for row in summary if row["provider"] == "Google Search")
    assert google["attempts"] == 3
    assert google["availability_attempts"] == 0
    assert google["not_configured_count"] == 3
    assert google["success_rate"] == 1.0
    assert google["alert_level"] == "ok"
    assert provider_sla.get_provider_sla_alerts() == []


def test_provider_sla_api_returns_alerts(monkeypatch):
    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [{"provider": "fake", "alert_level": "warning"}])
    monkeypatch.setattr(api, "get_provider_sla_alerts", lambda limit=100: [{"provider": "fake", "alert_level": "warning"}])

    client = TestClient(api.app)
    response = client.get("/api/observability/provider-sla")

    assert response.status_code == 200
    assert response.json()["alerts"][0]["provider"] == "fake"


def test_provider_sla_api_applies_window_server_side(monkeypatch):
    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [{
        "source": "market_data",
        "provider": "fake",
        "attempts": 10,
        "success_count": 10,
        "error_count": 0,
        "success_rate": 1.0,
        "avg_duration_ms": 10,
        "total_records": 10,
        "last_status": "success",
        "last_message": "",
        "alert_level": "ok",
        "alert_message": "",
        "windows": {
            "last_24h": {
                "attempts": 3,
                "success_count": 1,
                "error_count": 2,
                "success_rate": 0.3333,
                "avg_duration_ms": 20,
                "total_records": 1,
            }
        },
    }])
    monkeypatch.setattr(api, "get_provider_sla_alerts", lambda limit=100: [])

    client = TestClient(api.app)
    response = client.get("/api/observability/provider-sla", params={"window": "last_24h"})

    assert response.status_code == 200
    body = response.json()
    assert body["selected_window"] == "last_24h"
    assert body["providers"][0]["attempts"] == 3
    assert body["providers"][0]["success_rate"] == 0.3333
    assert body["providers"][0]["alert_level"] == "critical"
    assert body["alerts"][0]["provider"] == "fake"


def test_provider_sla_window_without_samples_does_not_reuse_stale_alert(monkeypatch):
    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [{
        "source": "recent_catalysts",
        "provider": "fake-news",
        "attempts": 10,
        "availability_attempts": 10,
        "success_count": 1,
        "error_count": 0,
        "success_rate": 0.1,
        "avg_duration_ms": 10,
        "total_records": 1,
        "last_status": "unavailable",
        "last_message": "older outage",
        "alert_level": "critical",
        "alert_message": "older outage",
        "windows": {
            "last_1h": {
                "attempts": 0,
                "availability_attempts": 0,
                "success_count": 0,
                "error_count": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0,
                "total_records": 0,
            }
        },
    }])
    monkeypatch.setattr(api, "get_provider_sla_alerts", lambda limit=100: [{"provider": "fake-news", "alert_level": "critical"}])

    client = TestClient(api.app)
    response = client.get("/api/observability/provider-sla", params={"window": "last_1h"})

    assert response.status_code == 200
    body = response.json()
    assert body["providers"][0]["attempts"] == 0
    assert body["providers"][0]["alert_level"] == "ok"
    assert body["providers"][0]["alert_message"] == ""
    assert body["alerts"] == []


def test_active_jobs_observability_summarizes_latest_events(monkeypatch, tmp_path):
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    job_store.reset_job_store_for_tests()
    job_id = job_store.create_job("2449.TW", "both")
    job_store.append_event(
        job_id,
        {
            "type": "status",
            "phase": "llm_model_call",
            "level": "info",
            "message": "calling",
            "agent_num": 12,
            "pipeline_id": "v2",
            "metadata": {"model_id": "gemma-4-31b-it", "timeout_seconds": 15.0, "estimated_tokens": 4096},
        },
    )
    job_store.append_event(
        job_id,
        {
            "type": "status",
            "phase": "llm_model_error",
            "level": "warning",
            "message": "failed",
            "agent_num": 12,
            "pipeline_id": "v2",
            "metadata": {"model_id": "gemma-4-31b-it", "error_category": "timeout"},
        },
    )
    job_store.append_event(
        job_id,
        {
            "type": "status",
            "phase": "llm_server_error_retry",
            "level": "warning",
            "message": "retry server error",
            "agent_num": 12,
            "pipeline_id": "v2",
            "metadata": {"model_id": "gemma-4-31b-it"},
        },
    )

    payload = job_observability.build_active_jobs_snapshot(db_path=str(tmp_path / "jobs.sqlite3"))

    assert payload["active_count"] == 1
    job = payload["jobs"][0]
    assert job["job_id"] == job_id
    assert job["last_event"]["phase"] == "llm_server_error_retry"
    assert job["stage_summary"]["phase"] == "llm_server_error_retry"
    assert job["stage_summary"]["llm_retry_count_sampled"] == 1
    assert job["stage_summary"]["llm_error_count_sampled"] == 1
    assert job["llm_error_counts"]["gemma-4-31b-it:timeout"] == 1
    assert job["llm_retry_counts"]["gemma-4-31b-it"] == 1
    assert job["token_estimate"]["sampled_total"] == 4096
    assert job["token_estimate"]["latest"] == 4096
    assert job["token_estimate"]["mode"] == "display_only"


def test_active_jobs_api(monkeypatch):
    async def fake_active_jobs_payload(limit=10, event_limit=80):
        return {"jobs": [], "active_count": 0}

    monkeypatch.setattr(api_observability_service, "build_active_jobs_payload", fake_active_jobs_payload)

    client = TestClient(api.app)
    response = client.get("/api/observability/active-jobs")

    assert response.status_code == 200
    assert response.json()["active_count"] == 0


def test_api_quota_observability_api(monkeypatch):
    async def fake_api_quota_payload(summary_fetcher):
        return {"services": [{"service": "Gemini / Google AI", "configured": True}], "timezone": "Asia/Taipei"}

    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    client = TestClient(api.app)
    response = client.get("/api/observability/api-quotas")

    assert response.status_code == 200
    assert response.json()["services"][0]["service"] == "Gemini / Google AI"


def test_api_usage_ledger_records_llm_job_events(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs.sqlite3"
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(db_path))
    monkeypatch.setattr(api_usage_store, "API_USAGE_DB_PATH", str(db_path))
    job_store.reset_job_store_for_tests()
    api_usage_store.reset_api_usage_store_for_tests()

    job_id = job_store.create_job("2449.TW", "v2")
    job_store.append_event(job_id, {
        "type": "status",
        "phase": "llm_model_call",
        "level": "info",
        "message": "calling",
        "metadata": {"model_id": "gemini-2.5-pro"},
    })
    usage_before_provider = api_usage_store.summarize_llm_usage_since(datetime.fromtimestamp(0, tz=timezone.utc))
    assert usage_before_provider["observed_calls_since_reset"] == 0

    job_store.append_event(job_id, {
        "type": "status",
        "phase": "llm_provider_request",
        "level": "info",
        "message": "provider request",
        "metadata": {"model_id": "gemini-2.5-pro", "key_slot": 1, "key_count": 2},
    })
    job_store.append_event(job_id, {
        "type": "status",
        "phase": "llm_model_error",
        "level": "warning",
        "message": "429 quota exhausted",
        "metadata": {"model_id": "gemini-2.5-pro", "error_category": "quota"},
    })

    usage = api_usage_store.summarize_llm_usage_since(datetime.fromtimestamp(0, tz=timezone.utc))

    assert usage["observed_calls_since_reset"] == 1
    assert usage["observed_model_calls"]["gemini-2.5-pro"] == 1
    assert usage["observed_quota_errors_since_reset"] == 1
    assert usage["recent_quota_events"][0]["model_id"] == "gemini-2.5-pro"


def test_api_quota_payload_uses_persistent_usage_ledger(monkeypatch, tmp_path):
    db_path = tmp_path / "api_usage.sqlite3"
    monkeypatch.setattr(api_usage_store, "API_USAGE_DB_PATH", str(db_path))
    api_usage_store.reset_api_usage_store_for_tests()
    timestamp = datetime.now(timezone.utc).timestamp()
    api_usage_store.record_api_usage(
        service="Gemini / Google AI",
        provider="google_ai",
        operation="llm_model_call",
        model_id="gemini-2.5-pro",
        units=1,
        created_at=timestamp,
    )
    api_usage_store.record_provider_audit_usage(
        {"source": "recent_catalysts", "provider": "Google Search", "status": "success"},
        created_at=timestamp,
    )
    api_usage_store.record_provider_audit_usage(
        {"source": "market_data", "provider": "FMP quote", "status": "error", "message": "quota"},
        created_at=timestamp,
    )

    payload = api_quota_service.build_api_quota_payload(lambda limit=100: [
        {"source": "recent_catalysts", "provider": "Google Search", "last_status": "success", "alert_level": "ok"},
        {"source": "market_data", "provider": "FMP quote", "last_status": "error", "alert_level": "warning"},
    ])

    gemini = next(item for item in payload["services"] if item["service"] == "Gemini / Google AI")
    google = next(item for item in payload["services"] if item["service"] == "Google Custom Search")
    fmp = next(item for item in payload["services"] if item["service"] == "Financial Modeling Prep")
    assert gemini["usage"]["observed_calls_since_reset"] == 1
    assert gemini["usage"]["ledger_source"] == "api_usage_events"
    assert google["usage"]["observed_24h_attempts"] == 1
    assert fmp["usage"]["observed_24h_errors"] == 1


def test_provider_usage_counts_real_fmp_stable_quote_attempts_only(monkeypatch, tmp_path):
    db_path = tmp_path / "api_usage.sqlite3"
    monkeypatch.setattr(api_usage_store, "API_USAGE_DB_PATH", str(db_path))
    api_usage_store.reset_api_usage_store_for_tests()
    timestamp = datetime.now(timezone.utc).timestamp()
    api_usage_store.record_provider_audit_usage(
        {"source": "market_data", "provider": "FMP stable quote", "status": "success"},
        created_at=timestamp,
    )
    api_usage_store.record_provider_audit_usage(
        {
            "source": "market_data",
            "provider": "FMP stable quote",
            "status": "unavailable",
            "message": "核心市場欄位已有資料，略過 FMP quote fallback。",
        },
        created_at=timestamp,
    )

    payload = api_quota_service.build_api_quota_payload(lambda limit=100: [
        {"source": "market_data", "provider": "FMP stable quote", "last_status": "success", "alert_level": "ok"},
    ])

    fmp = next(item for item in payload["services"] if item["service"] == "Financial Modeling Prep")
    assert fmp["usage"]["observed_24h_attempts"] == 1
    assert fmp["usage"]["observed_24h_errors"] == 0


def test_maintenance_api_summarizes_and_cleans_job_history(monkeypatch, mutation_headers):
    now = 2_000_000.0
    old = now - 40 * 24 * 60 * 60
    monkeypatch.setattr(job_store_maintenance.time, "time", lambda: now)

    job_id = job_store.create_job("6282", "both")
    job_store.update_job(job_id, "done")
    with sqlite3.connect(job_store.TASK_DB_PATH) as conn:
        conn.execute("UPDATE analysis_jobs SET created_at = ?, updated_at = ? WHERE job_id = ?", (old, old, job_id))
        conn.executemany(
            """
            INSERT INTO analysis_jobs (job_id, ticker, pipeline_id, status, created_at, updated_at)
            VALUES (?, '6282', 'both', 'done', ?, ?)
            """,
            [(f"old-{index}", old, old) for index in range(20)],
        )
        conn.executemany(
            "INSERT INTO analysis_events (job_id, payload, created_at) VALUES (?, '{}', ?)",
            [(f"old-{index}", old) for index in range(20)],
        )
        conn.execute(
            "INSERT INTO analysis_events (job_id, payload, created_at) VALUES ('orphan', '{}', ?)",
            (old,),
        )

    client = TestClient(api.app)
    summary_response = client.get("/api/maintenance/storage-summary", headers=mutation_headers)
    cleanup_response = client.post(
        "/api/maintenance/cleanup-analysis-history",
        params={"retention_days": 30, "keep_recent_jobs": 0, "write": "true"},
        headers=mutation_headers,
    )

    assert summary_response.status_code == 200
    history = summary_response.json()["summary"]["task_db"]["analysis_history"]
    assert history["stale_terminal_jobs"] == 1
    assert history["orphan_events"] == 1
    assert cleanup_response.status_code == 200
    result = cleanup_response.json()["result"]
    assert result["deleted_jobs"] == 21
    assert result["deleted_events"] == 22


def test_maintenance_cleanup_api_defaults_to_dry_run(monkeypatch, mutation_headers):
    now = 2_000_000.0
    old = now - 40 * 24 * 60 * 60
    monkeypatch.setattr(job_store_maintenance.time, "time", lambda: now)

    job_id = job_store.create_job("6282", "both")
    job_store.update_job(job_id, "done")
    with sqlite3.connect(job_store.TASK_DB_PATH) as conn:
        conn.execute("UPDATE analysis_jobs SET created_at = ?, updated_at = ? WHERE job_id = ?", (old, old, job_id))

    client = TestClient(api.app)
    response = client.post(
        "/api/maintenance/cleanup-analysis-history",
        params={"retention_days": 30, "keep_recent_jobs": 0},
        headers=mutation_headers,
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["dry_run"] is True
    assert result["deleted_jobs"] == 0
    assert job_store.get_job(job_id)["status"] == "done"


def test_api_uses_lifespan_and_router_modules():
    source = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")

    assert "@app.on_event" not in source
    assert "FastAPI(lifespan=lifespan)" in source
    assert "validate_runtime_settings()" in source
    assert "create_watchlist_scheduler_task" not in source
    assert "create_decision_tracking_scheduler_task" not in source
    assert "_cleanup_reports_forever" not in source
    assert "include_router" in source
    assert "api_routes.analysis" in source
    for legacy_function in [
        "parse_recommendation_summary",
        "get_reports",
        "delete_report",
        "provider_sla_summary",
        "refresh_report_data_snapshot",
        "rerun_report_analysis",
    ]:
        assert f"def {legacy_function}(" not in source


def test_runtime_policy_script_is_non_strict_for_local_runtime():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_runtime.py")],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Python" in result.stdout


def test_analyze_sse_contract_streams_job_progress_and_done(monkeypatch):
    streamed_events = [
        {"id": 1, "payload": {"type": "status", "message": "start", "pipeline_id": "both"}, "created_at": 1.0},
        {"id": 2, "payload": {"type": "progress", "current": 1, "total": 22, "name": "Agent 1"}, "created_at": 2.0},
        {"id": 3, "payload": {"type": "done", "filename": "2449_TW_v3_report.html", "pipeline_id": "both", "last_pipeline_id": "v3"}, "created_at": 3.0},
    ]

    class FakeQueue:
        def enqueue(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(api, "has_api_keys", lambda: True)
    monkeypatch.setattr(api, "analysis_task_queue", FakeQueue())
    monkeypatch.setattr(api, "create_job", lambda ticker, pipeline_id="v1": "job-stream")
    monkeypatch.setattr(api, "find_active_job", lambda ticker, pipeline_id="v1": {})
    monkeypatch.setattr(api, "get_job", lambda job_id: {"job_id": job_id, "ticker": "2449", "pipeline_id": "both", "status": "running"})
    monkeypatch.setattr(api, "get_events_since", lambda job_id, after_id=0: [event for event in streamed_events if event["id"] > after_id])

    client = TestClient(api.app)
    with client.stream("GET", "/api/analyze/2449?pipeline=both") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "job"' in text
    assert "id: 2" in text
    assert '"type": "progress"' in text
    assert '"type": "done"' in text


def test_cancel_analysis_endpoint_requests_cancel(monkeypatch, mutation_headers):
    cancelled = []
    monkeypatch.setattr(api, "get_job", lambda job_id: {"job_id": job_id, "ticker": "2449", "pipeline_id": "both", "status": "running"})
    monkeypatch.setattr(api, "request_job_cancel", lambda job_id, reason: cancelled.append((job_id, reason)) or True)

    client = TestClient(api.app)
    response = client.post("/api/analyze/2449/cancel?job_id=job-1&pipeline=both", headers=mutation_headers)

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert cancelled and cancelled[0][0] == "job-1"


def test_mutation_endpoints_require_admin_token_when_configured(monkeypatch):
    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "secret-token")
    monkeypatch.setattr(api, "get_job", lambda job_id: {"job_id": job_id, "ticker": "2449", "pipeline_id": "both", "status": "running"})
    monkeypatch.setattr(api, "request_job_cancel", lambda job_id, reason: True)

    client = TestClient(api.app)
    denied = client.post("/api/analyze/2449/cancel?job_id=job-1&pipeline=both")
    allowed = client.post(
        "/api/analyze/2449/cancel?job_id=job-1&pipeline=both",
        headers={"X-Admin-Token": "secret-token"},
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True
    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "")


def test_unconfigured_mutation_token_requires_runtime_header_even_on_localhost(monkeypatch):
    class FakeClient:
        def __init__(self, host):
            self.host = host

    class FakeRequest:
        def __init__(self, host, headers=None):
            self.client = FakeClient(host)
            self.headers = headers or {}

    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "")
    monkeypatch.setattr(api, "RUNTIME_MUTATION_API_TOKEN", "runtime-test-token", raising=False)

    with pytest.raises(HTTPException):
        api.require_mutation_authorized(FakeRequest("127.0.0.1"))
    api.require_mutation_authorized(FakeRequest("127.0.0.1", {"x-mutation-token": "runtime-test-token"}))
    with pytest.raises(HTTPException):
        api.require_mutation_authorized(FakeRequest("203.0.113.10"))


def test_server_deployment_mode_does_not_allow_or_expose_runtime_token(monkeypatch):
    class FakeRequest:
        headers = {"x-mutation-token": "runtime-test-token"}
        client = None

    monkeypatch.setattr(api, "DEPLOYMENT_MODE", "server", raising=False)
    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "", raising=False)
    monkeypatch.setattr(api, "RUNTIME_MUTATION_API_TOKEN", "runtime-test-token", raising=False)

    assert api.get_allowed_mutation_tokens() == set()
    assert api.get_client_config()["mutation_token"] == ""
    with pytest.raises(HTTPException):
        api.require_mutation_authorized(FakeRequest())


def test_client_config_exposes_runtime_mutation_header(monkeypatch):
    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "")
    monkeypatch.setattr(api, "RUNTIME_MUTATION_API_TOKEN", "runtime-test-token", raising=False)
    monkeypatch.setattr(api, "DEPLOYMENT_MODE", "local", raising=False)

    client = TestClient(api.app)
    response = client.get("/api/client-config")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["mutation_header"] == "X-Mutation-Token"
    assert response.json()["mutation_token"] == "runtime-test-token"


def test_client_config_does_not_expose_configured_admin_token(monkeypatch):
    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "long-lived-admin-token")
    monkeypatch.setattr(api, "RUNTIME_MUTATION_API_TOKEN", "runtime-test-token", raising=False)
    monkeypatch.setattr(api, "DEPLOYMENT_MODE", "local", raising=False)

    client = TestClient(api.app)
    response = client.get("/api/client-config")

    assert response.status_code == 200
    assert response.json()["mutation_token"] == "runtime-test-token"
    api.require_mutation_authorized(type("Req", (), {
        "headers": {"x-mutation-token": "runtime-test-token"},
        "client": None,
    })())
    api.require_mutation_authorized(type("Req", (), {
        "headers": {"x-admin-token": "long-lived-admin-token"},
        "client": None,
    })())


def test_report_cover_config_does_not_send_unsupported_enhance_prompt():
    config = _build_cover_generation_config()
    payload = config.model_dump(exclude_none=True) if hasattr(config, "model_dump") else dict(config)

    assert "enhance_prompt" not in payload


def test_job_progress_completion_is_monotonic_for_parallel_agents(monkeypatch, tmp_path):
    events = []

    class FakeStockDataService:
        async def fetch_async(self, request):
            data = {
                "ticker": request.ticker,
                "company_name": "測試公司",
                "current_price": 100,
                "fetch_date": "2026年06月06日",
                "price_history": {},
            }
            return FetchResult(request=request, data=data, data_trust=unknown_data_trust())

    class FakePipelineRunner:
        async def run_async(self, request):
            request.progress_callback(3, 7, "Third Agent")
            request.progress_callback(2, 7, "Second Agent")
            data = request.data
            return type(
                "Result",
                (),
                {
                    "context": {
                        "ticker": data["ticker"],
                        "company_name": data["company_name"],
                        "data": data,
                        "pipeline_id": request.pipeline_id,
                        "analyses": {},
                        "structured_outputs": {},
                        "final_audit": {"status": "passed", "critical": [], "warnings": [], "corrections": []},
                    }
                },
            )()

    class FakeReportRenderer:
        async def render_async(self, request):
            snapshot = {
                "snapshot_schema_version": DATA_SNAPSHOT_SCHEMA_VERSION,
                "snapshot_truncated": False,
                "snapshot_size_bytes": 0,
                "snapshot_omitted_sections": [],
                "ticker": request.context["ticker"],
                "pipeline": request.pipeline_id,
                "generated_at": "2026-06-07T00:00:00+00:00",
                "data_schema_version": None,
                "source_freshness": {},
                "source_audit": [],
                "data_trust": unknown_data_trust(),
                "data": request.context["data"],
            }
            return ReportBundle(html="<html></html>", markdown="# report", data_snapshot=snapshot)

    monkeypatch.setattr(analysis_jobs, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(analysis_jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(analysis_jobs, "STOCK_DATA_SERVICE", FakeStockDataService())
    monkeypatch.setattr(analysis_jobs, "PIPELINE_RUNNER", FakePipelineRunner())
    monkeypatch.setattr(analysis_jobs, "REPORT_RENDERER", FakeReportRenderer())
    monkeypatch.setattr(analysis_jobs, "append_event", lambda job_id, payload: events.append(payload))
    monkeypatch.setattr(analysis_jobs, "update_job", lambda *args, **kwargs: None)
    monkeypatch.setattr(analysis_jobs, "is_job_cancel_requested", lambda job_id: False)

    import asyncio

    asyncio.run(analysis_jobs.run_stock_analysis_job_async("job-progress", "2449", "v1"))

    currents = [event["current"] for event in events if event["type"] == "progress"]
    assert currents == sorted(currents)
    assert currents[:2] == [1, 2]


def test_context_digest_hash_cache_reuses_successful_digest(monkeypatch):
    calls = {"llm": 0}

    class FakeDigestRotator:
        def get_key(self, *_args, **_kwargs):
            return "fake-key"

    def fake_generate(*_args, **_kwargs):
        calls["llm"] += 1
        return type("Response", (), {"text": "{\"decision_relevant_facts\":[\"摘要\"]}"})()

    monkeypatch.setattr(context_digest_tasks, "_generate_context_digest_content", fake_generate)
    monkeypatch.setattr(context_digest_tasks, "response_text", lambda response: response.text)

    context = {
        "pipeline_id": "v1",
        "analyses": {1: "商業模式", 2: "財務分析"},
        "structured_outputs": {},
        "agent_positions": {4: 4},
        "agent_total": 10,
    }

    context_digest_tasks.ensure_context_digest(4, context, FakeDigestRotator())
    first_digest = context["context_digests"].pop(4)
    context_digest_tasks.ensure_context_digest(4, context, FakeDigestRotator())

    assert calls["llm"] == 1
    assert context["context_digests"][4] == first_digest
    assert context["_digest_hash_map"]
