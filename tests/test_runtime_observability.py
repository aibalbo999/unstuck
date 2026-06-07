import sys
import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import api  # noqa: E402
import job_observability  # noqa: E402
import job_store  # noqa: E402
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
    alerts = provider_sla.get_provider_sla_alerts()
    assert alerts and alerts[0]["provider"] == "yfinance"
    assert "windows" in alerts[0]


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
            "metadata": {"model_id": "gemma-4-31b-it", "timeout_seconds": 15.0},
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

    payload = job_observability.build_active_jobs_snapshot(db_path=str(tmp_path / "jobs.sqlite3"))

    assert payload["active_count"] == 1
    job = payload["jobs"][0]
    assert job["job_id"] == job_id
    assert job["last_event"]["phase"] == "llm_model_error"
    assert job["llm_error_counts"]["gemma-4-31b-it:timeout"] == 1


def test_active_jobs_api(monkeypatch):
    async def fake_active_jobs_payload(limit=10, event_limit=80):
        return {"jobs": [], "active_count": 0}

    monkeypatch.setattr(api.api_observability_service, "build_active_jobs_payload", fake_active_jobs_payload)

    client = TestClient(api.app)
    response = client.get("/api/observability/active-jobs")

    assert response.status_code == 200
    assert response.json()["active_count"] == 0


def test_api_uses_lifespan_and_router_modules():
    source = (ROOT / "backend" / "api.py").read_text(encoding="utf-8")

    assert "@app.on_event" not in source
    assert "FastAPI(lifespan=lifespan)" in source
    assert "validate_runtime_settings()" in source
    assert "include_router" in source
    assert "api_routes.analysis" in source


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
        {"id": 2, "payload": {"type": "progress", "current": 1, "total": 13, "name": "Agent 1"}, "created_at": 2.0},
        {"id": 3, "payload": {"type": "done", "filename": "2449_TW_v2_report.html", "pipeline_id": "both", "last_pipeline_id": "v2"}, "created_at": 3.0},
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


def test_cancel_analysis_endpoint_requests_cancel(monkeypatch):
    cancelled = []
    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "")
    monkeypatch.setattr(api, "get_job", lambda job_id: {"job_id": job_id, "ticker": "2449", "pipeline_id": "both", "status": "running"})
    monkeypatch.setattr(api, "request_job_cancel", lambda job_id, reason: cancelled.append((job_id, reason)) or True)

    client = TestClient(api.app)
    response = client.post("/api/analyze/2449/cancel?job_id=job-1&pipeline=both")

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


def test_unconfigured_mutation_token_is_localhost_only(monkeypatch):
    class FakeClient:
        def __init__(self, host):
            self.host = host

    class FakeRequest:
        headers = {}

        def __init__(self, host):
            self.client = FakeClient(host)

    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "")

    api.require_mutation_authorized(FakeRequest("127.0.0.1"))
    api.require_mutation_authorized(FakeRequest("testclient"))
    with pytest.raises(HTTPException):
        api.require_mutation_authorized(FakeRequest("203.0.113.10"))


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
