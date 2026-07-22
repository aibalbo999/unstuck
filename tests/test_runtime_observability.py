import asyncio
import base64
import importlib
import importlib.util
import json
import sys
import subprocess
import sqlite3
from types import SimpleNamespace
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
import notification_delivery_observability as notification_observability  # noqa: E402
import queue_dashboard_payload  # noqa: E402
import queue_observability  # noqa: E402
import provider_sla  # noqa: E402
import provider_sla_alert_policy  # noqa: E402
import provider_sla_observability  # noqa: E402
import provider_sla_payload_shape  # noqa: E402
from data_fetch import FetchResult  # noqa: E402
from data_trust import DATA_SNAPSHOT_SCHEMA_VERSION, unknown_data_trust  # noqa: E402
from reporting import ReportBundle  # noqa: E402
import reporting.html_renderer as html_renderer  # noqa: E402
import analysis_jobs  # noqa: E402
import basic_auth  # noqa: E402


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
            {"source": "recent_catalysts", "provider": "Alternative Search", "status": "skipped_fresh_cache", "duration_ms": 0},
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
    search = next(row for row in summary if row["provider"] == "Alternative Search")
    assert search["attempts"] == 1
    assert search["skipped_fresh_cache_count"] == 1
    assert search["success_rate"] == 1.0
    assert search["windows"]["last_1h"]["success_rate"] == 1.0
    assert search["alert_level"] == "ok"
    alerts = provider_sla.get_provider_sla_alerts()
    assert alerts and alerts[0]["provider"] == "yfinance"
    assert "windows" in alerts[0]


def test_provider_sla_alert_policy_ignores_window_stats_truthiness_failures():
    class BrokenTruthDict(dict):
        def __bool__(self):
            raise RuntimeError("provider sla alert policy window stats truthiness unavailable")

    try:
        fields = provider_sla_alert_policy.provider_alert_fields({
            "provider": "fake",
            "last_status": "success",
            "windows": {
                "last_24h": BrokenTruthDict({
                    "attempts": 3,
                    "availability_attempts": 3,
                    "success_rate": 0.25,
                    "error_count": 0,
                }),
            },
        })
    except RuntimeError as exc:
        pytest.fail(f"provider alert policy should ignore malformed window truthiness: {exc}")

    assert fields["alert_level"] == "critical"
    assert fields["alert_basis"] == "last_24h"
    assert "fake last_24h資料取得率偏低" in fields["alert_message"]


def test_provider_sla_tracks_not_configured_without_alerting(monkeypatch, tmp_path):
    monkeypatch.setattr(provider_sla, "TASK_DB_PATH", str(tmp_path / "provider.sqlite3"))

    provider_sla.record_source_audit_entries(
        [
            {"source": "recent_catalysts", "provider": "Alternative Search", "status": "not_configured", "duration_ms": 0},
            {"source": "recent_catalysts", "provider": "Alternative Search", "status": "not_configured", "duration_ms": 0},
            {"source": "recent_catalysts", "provider": "Alternative Search", "status": "not_configured", "duration_ms": 0},
        ]
    )

    summary = provider_sla.get_provider_sla_summary()
    search = next(row for row in summary if row["provider"] == "Alternative Search")
    assert search["attempts"] == 3
    assert search["availability_attempts"] == 0
    assert search["not_configured_count"] == 3
    assert search["success_rate"] == 1.0
    assert search["alert_level"] == "ok"
    assert provider_sla.get_provider_sla_alerts() == []


def test_provider_sla_treats_unavailable_with_records_as_degraded_enrichment(monkeypatch, tmp_path):
    monkeypatch.setattr(provider_sla, "TASK_DB_PATH", str(tmp_path / "provider.sqlite3"))

    provider_sla.record_source_audit_entries(
        [
            {
                "source": "recent_catalysts",
                "provider": "cache",
                "status": "unavailable",
                "duration_ms": 0,
                "record_count": 5,
                "message": "快取來源已過期，等待重新抓取或 async 補強。",
            },
        ]
    )

    summary = provider_sla.get_provider_sla_summary()
    cache = next(row for row in summary if row["provider"] == "cache")
    assert cache["attempts"] == 1
    assert cache["unavailable_count"] == 0
    assert cache["degraded_enrichment_count"] == 1
    assert cache["success_rate"] == 1.0
    assert cache["last_status"] == "degraded_enrichment"


def test_provider_sla_api_returns_alerts(monkeypatch):
    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [{"provider": "fake", "alert_level": "warning"}])
    monkeypatch.setattr(api, "get_provider_sla_alerts", lambda limit=100: [{"provider": "fake", "alert_level": "warning"}])

    client = TestClient(api.app)
    response = client.get("/api/observability/provider-sla")

    assert response.status_code == 200
    assert response.json()["alerts"][0]["provider"] == "fake"


def test_prometheus_metrics_endpoint_exports_provider_sla_and_queue(monkeypatch):
    class FakeLocalQueue:
        def qsize(self):
            return 5

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [{
        "source": "market_data",
        "provider": "fake-provider",
        "attempts": 4,
        "success_rate": 0.75,
        "error_count": 1,
        "alert_level": "warning",
    }])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 3,
        "sent_count": 1,
        "failed_count": 2,
        "pending_count": 0,
        "retry_exhausted_count": 1,
        "channel_counts": {"telegram_webhook": 2, "local": 1},
        "failure_reason_counts": {"timeout": 1, "auth": 1},
        "health": "warning",
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=FakeLocalQueue(), active_tasks=[object(), object()]))

    client = TestClient(api.app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert 'stock_agent_provider_sla_success_rate{source="market_data",provider="fake-provider"} 0.75' in body
    assert 'stock_agent_provider_sla_attempts_total{source="market_data",provider="fake-provider"} 4' in body
    assert 'stock_agent_provider_sla_alert{source="market_data",provider="fake-provider",level="warning"} 1' in body
    assert 'stock_agent_queue_available{backend="local"} 1' in body
    assert 'stock_agent_queue_depth{queue="local"} 5' in body
    assert 'stock_agent_notification_delivery_count{status="failed"} 2' in body
    assert 'stock_agent_notification_delivery_count{status="retry_exhausted"} 1' in body
    assert 'stock_agent_notification_delivery_channel_count{channel="telegram_webhook"} 2' in body
    assert 'stock_agent_notification_delivery_failure_reason_count{reason="timeout"} 1' in body
    assert 'stock_agent_notification_delivery_failure_reason_count{reason="auth"} 1' in body
    assert 'stock_agent_notification_delivery_health{state="ok"} 0' in body
    assert 'stock_agent_notification_delivery_health{state="warning"} 1' in body


def test_prometheus_provider_labels_ignore_truthiness_failures(monkeypatch):
    class BrokenTruthLabel:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("prometheus label truthiness unavailable")

        def __str__(self):
            return self.value

    class FakeLocalQueue:
        def qsize(self):
            return 0

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [{
        "source": BrokenTruthLabel("market_data"),
        "provider": BrokenTruthLabel("fake-provider"),
        "attempts": 1,
        "success_rate": 1.0,
        "error_count": 0,
        "alert_level": "warning",
    }])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 0,
        "sent_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {},
        "failure_reason_counts": {},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=FakeLocalQueue(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'stock_agent_provider_sla_success_rate{source="market_data",provider="fake-provider"} 1' in body
    assert 'stock_agent_provider_sla_alert{source="market_data",provider="fake-provider",level="warning"} 1' in body


def test_prometheus_labels_reject_boolean_and_binary_values(monkeypatch):
    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [{
        "source": True,
        "provider": b"fake-provider",
        "attempts": 1,
        "success_rate": 1.0,
        "error_count": 0,
        "alert_level": "ok",
    }])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 2,
        "sent_count": 0,
        "failed_count": 2,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {True: 1},
        "failure_reason_counts": {memoryview(b"timeout"): 1},
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: {
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": 0,
        "queues": {},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'stock_agent_provider_sla_success_rate{source="unknown",provider="unknown"} 1' in body
    assert 'stock_agent_notification_delivery_channel_count{channel="unknown"} 1' in body
    assert 'stock_agent_notification_delivery_failure_reason_count{reason="unknown"} 1' in body
    assert 'source="True"' not in body
    assert 'provider="fake-provider"' not in body
    assert 'channel="True"' not in body
    assert 'reason="timeout"' not in body


def test_prometheus_numeric_metrics_reject_binary_values(monkeypatch):
    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [{
        "source": "market_data",
        "provider": "fake-provider",
        "attempts": b"4",
        "success_rate": b"0.75",
        "error_count": memoryview(b"2"),
        "alert_level": "ok",
    }])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 0,
        "sent_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {},
        "failure_reason_counts": {},
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: {
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": 0,
        "queues": {},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'stock_agent_provider_sla_success_rate{source="market_data",provider="fake-provider"} 0' in body
    assert 'stock_agent_provider_sla_attempts_total{source="market_data",provider="fake-provider"} 0' in body
    assert 'stock_agent_provider_sla_errors_total{source="market_data",provider="fake-provider"} 0' in body
    assert 'stock_agent_provider_sla_success_rate{source="market_data",provider="fake-provider"} 0.75' not in body
    assert 'stock_agent_provider_sla_attempts_total{source="market_data",provider="fake-provider"} 4' not in body
    assert 'stock_agent_provider_sla_errors_total{source="market_data",provider="fake-provider"} 2' not in body


def test_prometheus_provider_rows_ignore_mapping_failures(monkeypatch):
    class BrokenProviderRow:
        def __iter__(self):
            raise RuntimeError("prometheus provider row mapping unavailable")

    class FakeLocalQueue:
        def qsize(self):
            return 0

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [
        BrokenProviderRow(),
        {
            "source": "market_data",
            "provider": "fake-provider",
            "attempts": 2,
            "success_rate": 0.5,
            "error_count": 1,
            "alert_level": "warning",
        },
    ])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 0,
        "sent_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {},
        "failure_reason_counts": {},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=FakeLocalQueue(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'stock_agent_provider_sla_success_rate{source="market_data",provider="fake-provider"} 0.5' in body
    assert 'stock_agent_provider_sla_success_rate{source="",provider=""}' not in body


def test_prometheus_provider_summary_fetch_failure_keeps_other_metrics(monkeypatch):
    def broken_provider_summary(limit=100):
        raise RuntimeError("prometheus provider summary unavailable")

    monkeypatch.setattr(api, "get_provider_sla_summary", broken_provider_summary)
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 2,
        "sent_count": 1,
        "failed_count": 1,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {"telegram_webhook": 1},
        "failure_reason_counts": {"timeout": 1},
        "health": "warning",
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: {
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": 3,
        "queues": {},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'stock_agent_provider_sla_success_rate{source=' not in body
    assert 'stock_agent_queue_available{backend="rq"} 1' in body
    assert 'stock_agent_queue_depth{queue="stock-analysis"} 3' in body
    assert 'stock_agent_notification_delivery_count{status="failed"} 1' in body


def test_prometheus_provider_summary_ignores_non_iterable_payload(monkeypatch):
    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: object())
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 2,
        "sent_count": 1,
        "failed_count": 1,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {"telegram_webhook": 1},
        "failure_reason_counts": {"timeout": 1},
        "health": "warning",
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: {
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": 3,
        "queues": {},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'stock_agent_provider_sla_success_rate{source=' not in body
    assert 'stock_agent_queue_available{backend="rq"} 1' in body
    assert 'stock_agent_queue_depth{queue="stock-analysis"} 3' in body
    assert 'stock_agent_notification_delivery_count{status="failed"} 1' in body


def test_prometheus_provider_summary_preserves_rows_before_iterator_failure(monkeypatch):
    class PartiallyBrokenProviderSummary:
        def __iter__(self):
            yield {
                "source": "market_data",
                "provider": "fake-provider",
                "attempts": 2,
                "success_rate": 0.5,
                "error_count": 1,
                "alert_level": "warning",
            }
            raise RuntimeError("prometheus provider summary iterator unavailable")

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: PartiallyBrokenProviderSummary())
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 2,
        "sent_count": 1,
        "failed_count": 1,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {"telegram_webhook": 1},
        "failure_reason_counts": {"timeout": 1},
        "health": "warning",
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: {
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": 3,
        "queues": {},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'stock_agent_provider_sla_success_rate{source="market_data",provider="fake-provider"} 0.5' in body
    assert 'stock_agent_provider_sla_errors_total{source="market_data",provider="fake-provider"} 1' in body
    assert 'stock_agent_queue_available{backend="rq"} 1' in body
    assert 'stock_agent_notification_delivery_count{status="failed"} 1' in body


def test_prometheus_queue_snapshot_fetch_failure_keeps_other_metrics(monkeypatch):
    def broken_queue_snapshot(_task_queue):
        raise RuntimeError("prometheus queue snapshot unavailable")

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [{
        "source": "market_data",
        "provider": "fake-provider",
        "attempts": 2,
        "success_rate": 0.5,
        "error_count": 1,
        "alert_level": "warning",
    }])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 2,
        "sent_count": 1,
        "failed_count": 1,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {"telegram_webhook": 1},
        "failure_reason_counts": {"timeout": 1},
        "health": "warning",
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", broken_queue_snapshot)
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'stock_agent_provider_sla_success_rate{source="market_data",provider="fake-provider"} 0.5' in body
    assert 'stock_agent_queue_available{backend="unknown"} 0' in body
    assert 'stock_agent_queue_depth{queue="unknown"} 0' in body
    assert 'stock_agent_notification_delivery_count{status="failed"} 1' in body


def test_prometheus_notification_delivery_fetch_failure_keeps_other_metrics(monkeypatch):
    def broken_delivery_summary():
        raise RuntimeError("prometheus notification delivery summary unavailable")

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [{
        "source": "market_data",
        "provider": "fake-provider",
        "attempts": 2,
        "success_rate": 0.5,
        "error_count": 1,
        "alert_level": "warning",
    }])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", broken_delivery_summary)
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: {
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": 3,
        "queues": {},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'stock_agent_provider_sla_success_rate{source="market_data",provider="fake-provider"} 0.5' in body
    assert 'stock_agent_queue_available{backend="rq"} 1' in body
    assert 'stock_agent_queue_depth{queue="stock-analysis"} 3' in body
    assert 'stock_agent_notification_delivery_count{status="failed"} 0' in body
    assert 'stock_agent_notification_delivery_health{state="ok"} 1' in body
    assert 'stock_agent_notification_delivery_health{state="warning"} 0' in body


def test_prometheus_queue_snapshot_ignores_mapping_failures(monkeypatch):
    class BrokenQueueSnapshot:
        def __iter__(self):
            raise RuntimeError("prometheus queue snapshot mapping unavailable")

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 0,
        "sent_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {},
        "failure_reason_counts": {},
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: BrokenQueueSnapshot())
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    assert 'stock_agent_queue_available{backend="unknown"} 0' in response.text
    assert 'stock_agent_queue_depth{queue="unknown"} 0' in response.text


def test_prometheus_alert_level_ignores_truthiness_failures(monkeypatch):
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("prometheus alert level truthiness unavailable")

        def __str__(self):
            return self.value

    class FakeLocalQueue:
        def qsize(self):
            return 0

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [{
        "source": "market_data",
        "provider": "fake-provider",
        "attempts": 1,
        "success_rate": 0.5,
        "error_count": 1,
        "alert_level": BrokenTruthText("warning"),
    }])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 0,
        "sent_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {},
        "failure_reason_counts": {},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=FakeLocalQueue(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    assert 'stock_agent_provider_sla_alert{source="market_data",provider="fake-provider",level="warning"} 1' in response.text


def test_prometheus_queue_labels_ignore_truthiness_failures(monkeypatch):
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("prometheus queue label truthiness unavailable")

        def __str__(self):
            return self.value

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 0,
        "sent_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {},
        "failure_reason_counts": {},
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: {
        "backend": BrokenTruthText("rq"),
        "available": True,
        "queue_name": BrokenTruthText("stock-analysis"),
        "depth": 7,
        "queues": {BrokenTruthText("maintenance"): {"depth": 2}},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'stock_agent_queue_available{backend="rq"} 1' in body
    assert 'stock_agent_queue_depth{queue="stock-analysis"} 7' in body
    assert 'stock_agent_queue_depth{queue="maintenance"} 2' in body


def test_prometheus_queue_available_ignores_truthiness_failures(monkeypatch):
    class BrokenTruthBool:
        def __bool__(self):
            raise RuntimeError("prometheus queue availability truthiness unavailable")

        def __str__(self):
            return "true"

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 0,
        "sent_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {},
        "failure_reason_counts": {},
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: {
        "backend": "rq",
        "available": BrokenTruthBool(),
        "queue_name": "stock-analysis",
        "depth": 1,
        "queues": {},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    assert 'stock_agent_queue_available{backend="rq"} 1' in response.text


def test_prometheus_queue_maps_ignore_truthiness_failures(monkeypatch):
    class BrokenTruthDict(dict):
        def __bool__(self):
            raise RuntimeError("prometheus queue map truthiness unavailable")

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 0,
        "sent_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {},
        "failure_reason_counts": {},
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: {
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": 1,
        "queues": BrokenTruthDict({"maintenance": BrokenTruthDict({"depth": 2})}),
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    assert 'stock_agent_queue_depth{queue="maintenance"} 2' in response.text


def test_prometheus_named_queue_depth_preserves_malformed_detail_as_zero(monkeypatch):
    class BrokenQueueDetails:
        def __iter__(self):
            raise RuntimeError("prometheus named queue details unavailable")

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 0,
        "sent_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {},
        "failure_reason_counts": {},
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: {
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": 1,
        "queues": {"broken": BrokenQueueDetails()},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    assert 'stock_agent_queue_depth{queue="broken"} 0' in response.text


def test_prometheus_queue_depth_rejects_binary_numeric_values(monkeypatch):
    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 0,
        "sent_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {},
        "failure_reason_counts": {},
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: {
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": b"6",
        "queues": {"maintenance": {"depth": bytearray(b"3")}},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'stock_agent_queue_depth{queue="stock-analysis"} 0' in body
    assert 'stock_agent_queue_depth{queue="maintenance"} 0' in body
    assert 'stock_agent_queue_depth{queue="stock-analysis"} 6' not in body
    assert 'stock_agent_queue_depth{queue="maintenance"} 3' not in body


def test_prometheus_integer_metrics_ignore_conversion_failures(monkeypatch):
    class BrokenInt:
        def __int__(self):
            raise RuntimeError("prometheus integer conversion unavailable")

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [{
        "source": "market_data",
        "provider": "fake-provider",
        "attempts": BrokenInt(),
        "success_rate": 1.0,
        "error_count": BrokenInt(),
        "alert_level": "ok",
    }])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 0,
        "sent_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {},
        "failure_reason_counts": {},
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: {
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": BrokenInt(),
        "queues": {"maintenance": {"depth": BrokenInt()}},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'stock_agent_provider_sla_attempts_total{source="market_data",provider="fake-provider"} 0' in body
    assert 'stock_agent_provider_sla_errors_total{source="market_data",provider="fake-provider"} 0' in body
    assert 'stock_agent_queue_depth{queue="stock-analysis"} 0' in body
    assert 'stock_agent_queue_depth{queue="maintenance"} 0' in body


def test_prometheus_float_metrics_ignore_conversion_failures(monkeypatch):
    class BrokenFloat:
        def __float__(self):
            raise RuntimeError("prometheus float conversion unavailable")

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [{
        "source": "market_data",
        "provider": "fake-provider",
        "attempts": 1,
        "success_rate": BrokenFloat(),
        "error_count": 0,
        "alert_level": "ok",
    }])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 0,
        "sent_count": 0,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {},
        "failure_reason_counts": {},
    })
    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", lambda _task_queue: {
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": 0,
        "queues": {},
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=object(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    assert 'stock_agent_provider_sla_success_rate{source="market_data",provider="fake-provider"} 0' in response.text


def test_prometheus_notification_delivery_health_exports_stable_ok_and_warning_series(monkeypatch):
    class FakeLocalQueue:
        def qsize(self):
            return 0

    monkeypatch.setattr(api, "get_provider_sla_summary", lambda limit=100: [])
    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", lambda: {
        "total_count": 1,
        "sent_count": 1,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {"local": 1},
        "health": "ok",
    })
    monkeypatch.setattr(api, "analysis_task_queue", SimpleNamespace(queue=FakeLocalQueue(), active_tasks=[]))

    response = TestClient(api.app).get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'stock_agent_notification_delivery_health{state="ok"} 1' in body
    assert 'stock_agent_notification_delivery_health{state="warning"} 0' in body


def test_notification_delivery_metrics_ignore_summary_truthiness_failures():
    class BrokenTruthDict(dict):
        def __bool__(self):
            raise RuntimeError("notification delivery summary truthiness unavailable")

    def labels(**values):
        return "{" + ",".join(f'{key}="{value}"' for key, value in values.items()) + "}"

    lines = notification_observability.notification_delivery_prometheus_lines(
        BrokenTruthDict(
            {
                "total_count": 3,
                "sent_count": 1,
                "failed_count": 2,
                "pending_count": 0,
                "retry_exhausted_count": 1,
                "channel_counts": BrokenTruthDict({"telegram_webhook": 2}),
                "failure_reason_counts": BrokenTruthDict({"timeout": 2}),
            }
        ),
        labels,
    )

    assert 'stock_agent_notification_delivery_count{status="failed"} 2' in lines
    assert 'stock_agent_notification_delivery_count{status="retry_exhausted"} 1' in lines
    assert 'stock_agent_notification_delivery_channel_count{channel="telegram_webhook"} 2' in lines
    assert 'stock_agent_notification_delivery_failure_reason_count{reason="timeout"} 2' in lines
    assert 'stock_agent_notification_delivery_health{state="warning"} 1' in lines


def test_notification_delivery_dashboard_summary_normalizes_count_map_keys_for_json():
    class BrokenTruthLabel:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("notification delivery dashboard key truthiness unavailable")

        def __str__(self):
            return self.value

    payload = notification_observability.notification_delivery_dashboard_summary(
        {
            "total_count": 5,
            "sent_count": 0,
            "failed_count": 5,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {
                BrokenTruthLabel("telegram_webhook"): "2",
                memoryview(b"decoded_channel_should_not_leak"): "2",
                True: "1",
            },
            "failure_reason_counts": {
                "timeout": "2",
                b"auth_should_not_leak": "1",
                memoryview(b"timeout"): "2",
            },
        }
    )

    assert payload["channel_counts"] == {"telegram_webhook": 2, "unknown": 3}
    assert payload["failure_reason_counts"] == {"timeout": 2, "unknown": 3}
    assert json.loads(json.dumps(payload))["channel_counts"] == {"telegram_webhook": 2, "unknown": 3}


def test_notification_delivery_dashboard_summary_rejects_binary_and_boolean_counts():
    payload = notification_observability.notification_delivery_dashboard_summary(
        {
            "total_count": b"5",
            "sent_count": True,
            "failed_count": bytearray(b"3"),
            "pending_count": memoryview(b"2"),
            "retry_exhausted_count": b"1",
            "channel_counts": {"local": b"4", "webhook": True},
            "failure_reason_counts": {"timeout": memoryview(b"2"), "auth": bytearray(b"1")},
        }
    )

    assert payload["total_count"] == 0
    assert payload["sent_count"] == 0
    assert payload["failed_count"] == 0
    assert payload["pending_count"] == 0
    assert payload["retry_exhausted_count"] == 0
    assert payload["channel_counts"] == {"local": 0, "webhook": 0}
    assert payload["failure_reason_counts"] == {"timeout": 0, "auth": 0}
    assert payload["attention_required"] is False
    assert payload["health"] == "ok"


def test_notification_delivery_attention_required_ignores_summary_get_failures():
    class BrokenGetDict(dict):
        def get(self, *_args, **_kwargs):
            raise RuntimeError("notification delivery summary get unavailable")

    assert notification_observability.notification_delivery_attention_required(
        BrokenGetDict({"failed_count": 2, "retry_exhausted_count": 0})
    ) is True


def test_notification_delivery_metrics_ignore_count_conversion_failures():
    class BrokenInt:
        def __int__(self):
            raise RuntimeError("notification delivery count conversion unavailable")

    def labels(**values):
        return "{" + ",".join(f'{key}="{value}"' for key, value in values.items()) + "}"

    lines = notification_observability.notification_delivery_prometheus_lines(
        {
            "total_count": BrokenInt(),
            "sent_count": 1,
            "failed_count": BrokenInt(),
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"telegram_webhook": BrokenInt()},
            "failure_reason_counts": {"timeout": BrokenInt()},
        },
        labels,
    )

    assert 'stock_agent_notification_delivery_count{status="total"} 0' in lines
    assert 'stock_agent_notification_delivery_count{status="failed"} 0' in lines
    assert 'stock_agent_notification_delivery_channel_count{channel="telegram_webhook"} 0' in lines
    assert 'stock_agent_notification_delivery_failure_reason_count{reason="timeout"} 0' in lines
    assert 'stock_agent_notification_delivery_health{state="ok"} 1' in lines


def test_notification_delivery_metrics_reject_binary_and_boolean_counts():
    def labels(**values):
        return "{" + ",".join(f'{key}="{value}"' for key, value in values.items()) + "}"

    lines = notification_observability.notification_delivery_prometheus_lines(
        {
            "total_count": b"5",
            "sent_count": True,
            "failed_count": bytearray(b"3"),
            "pending_count": memoryview(b"2"),
            "retry_exhausted_count": b"1",
            "channel_counts": {"local": b"4"},
            "failure_reason_counts": {"timeout": memoryview(b"2")},
        },
        labels,
    )

    assert 'stock_agent_notification_delivery_count{status="total"} 0' in lines
    assert 'stock_agent_notification_delivery_count{status="sent"} 0' in lines
    assert 'stock_agent_notification_delivery_count{status="failed"} 0' in lines
    assert 'stock_agent_notification_delivery_count{status="pending"} 0' in lines
    assert 'stock_agent_notification_delivery_count{status="retry_exhausted"} 0' in lines
    assert 'stock_agent_notification_delivery_channel_count{channel="local"} 0' in lines
    assert 'stock_agent_notification_delivery_failure_reason_count{reason="timeout"} 0' in lines
    assert 'stock_agent_notification_delivery_health{state="ok"} 1' in lines
    assert 'stock_agent_notification_delivery_health{state="warning"} 0' in lines


def test_notification_delivery_metrics_sanitize_label_truthiness_failures():
    class BrokenTruthLabel:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("notification delivery label truthiness unavailable")

        def __str__(self):
            return self.value

    lines = notification_observability.notification_delivery_prometheus_lines(
        {
            "total_count": 2,
            "sent_count": 0,
            "failed_count": 2,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {BrokenTruthLabel("telegram_webhook"): 2},
            "failure_reason_counts": {BrokenTruthLabel("timeout"): 2},
        },
        api_observability_service._labels,
    )

    assert 'stock_agent_notification_delivery_channel_count{channel="telegram_webhook"} 2' in lines
    assert 'stock_agent_notification_delivery_failure_reason_count{reason="timeout"} 2' in lines


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


def test_provider_sla_window_selection_uses_string_safe_conversion():
    class BrokenTruthWindow:
        def __bool__(self):
            raise RuntimeError("provider sla window truthiness unavailable")

        def __str__(self):
            return " last_24h "

    payload = asyncio.run(api_observability_service.build_provider_sla_payload(
        lambda limit: [{
            "source": "market_data",
            "provider": "fake",
            "attempts": 10,
            "success_rate": 1.0,
            "windows": {"last_24h": {"attempts": 3, "success_rate": 1.0}},
        }],
        lambda limit: [],
        100,
        window=BrokenTruthWindow(),
    ))

    assert payload["selected_window"] == "last_24h"
    assert payload["providers"][0]["attempts"] == 3


def test_provider_sla_window_alerts_ignore_numeric_conversion_failures():
    class BrokenInt:
        def __int__(self):
            raise RuntimeError("provider sla integer conversion unavailable")

    class BrokenFloat:
        def __float__(self):
            raise RuntimeError("provider sla float conversion unavailable")

    providers = [{
        "source": "market_data",
        "provider": "fake",
        "alert_level": "critical",
        "alert_message": "stale outage",
        "windows": {
            "last_24h": {
                "attempts": BrokenInt(),
                "availability_attempts": BrokenInt(),
                "error_count": BrokenInt(),
                "success_rate": BrokenFloat(),
            },
        },
    }]

    windowed = api_observability_service.apply_provider_sla_window(providers, "last_24h")

    assert windowed[0]["selected_window"] == "last_24h"
    assert windowed[0]["alert_level"] == "ok"
    assert windowed[0]["alert_message"] == ""
    assert windowed[0]["alert_basis"] == "last_24h"


def test_provider_sla_window_stats_use_safe_output_conversion():
    class BrokenInt:
        def __int__(self):
            raise RuntimeError("provider sla window integer conversion unavailable")

    providers = [{
        "source": "market_data",
        "provider": "fake",
        "attempts": 10,
        "success_rate": 1.0,
        "windows": {
            "last_24h": {
                "attempts": BrokenInt(),
                "availability_attempts": BrokenInt(),
                "success_count": BrokenInt(),
                "error_count": BrokenInt(),
                "unavailable_count": BrokenInt(),
                "skipped_fresh_cache_count": BrokenInt(),
                "not_configured_count": BrokenInt(),
                "degraded_enrichment_count": BrokenInt(),
                "success_rate": float("inf"),
                "avg_duration_ms": float("nan"),
                "total_records": BrokenInt(),
            },
        },
    }]

    windowed = api_observability_service.apply_provider_sla_window(providers, "last_24h")

    assert windowed[0]["attempts"] == 0
    assert windowed[0]["availability_attempts"] == 0
    assert windowed[0]["success_count"] == 0
    assert windowed[0]["error_count"] == 0
    assert windowed[0]["unavailable_count"] == 0
    assert windowed[0]["skipped_fresh_cache_count"] == 0
    assert windowed[0]["not_configured_count"] == 0
    assert windowed[0]["degraded_enrichment_count"] == 0
    assert windowed[0]["success_rate"] == 0.0
    assert windowed[0]["avg_duration_ms"] == 0.0
    assert windowed[0]["total_records"] == 0
    assert windowed[0]["selected_window"] == "last_24h"
    assert windowed[0]["alert_level"] == "ok"


def test_provider_sla_apply_window_normalizes_nested_windows_output():
    class BrokenInt:
        def __int__(self):
            raise RuntimeError("provider sla apply window nested integer conversion unavailable")

    providers = [{
        "source": "market_data",
        "provider": "fake",
        "windows": {
            "last_24h": {
                "attempts": BrokenInt(),
                "success_rate": float("inf"),
                "avg_duration_ms": float("nan"),
                "total_records": BrokenInt(),
            },
        },
    }]

    windowed = api_observability_service.apply_provider_sla_window(providers, "last_24h")
    nested_stats = windowed[0]["windows"]["last_24h"]

    assert nested_stats["attempts"] == 0
    assert nested_stats["success_rate"] == 0.0
    assert nested_stats["avg_duration_ms"] == 0.0
    assert nested_stats["total_records"] == 0


def test_provider_sla_provider_windows_use_safe_numeric_output_conversion():
    class BrokenInt:
        def __int__(self):
            raise RuntimeError("provider sla nested window integer conversion unavailable")

    payload = asyncio.run(api_observability_service.build_provider_sla_payload(
        lambda limit: [{
            "provider": "summary-provider",
            "windows": {
                "last_24h": {
                    "attempts": BrokenInt(),
                    "availability_attempts": BrokenInt(),
                    "success_count": BrokenInt(),
                    "error_count": BrokenInt(),
                    "unavailable_count": BrokenInt(),
                    "skipped_fresh_cache_count": BrokenInt(),
                    "not_configured_count": BrokenInt(),
                    "degraded_enrichment_count": BrokenInt(),
                    "success_rate": float("inf"),
                    "avg_duration_ms": float("nan"),
                    "total_records": BrokenInt(),
                    "label": "kept",
                },
            },
        }],
        lambda limit: [],
        100,
        window="all",
    ))

    window_stats = payload["providers"][0]["windows"]["last_24h"]
    assert window_stats["attempts"] == 0
    assert window_stats["availability_attempts"] == 0
    assert window_stats["success_count"] == 0
    assert window_stats["error_count"] == 0
    assert window_stats["unavailable_count"] == 0
    assert window_stats["skipped_fresh_cache_count"] == 0
    assert window_stats["not_configured_count"] == 0
    assert window_stats["degraded_enrichment_count"] == 0
    assert window_stats["success_rate"] == 0.0
    assert window_stats["avg_duration_ms"] == 0.0
    assert window_stats["total_records"] == 0
    assert window_stats["label"] == "kept"


def test_provider_sla_provider_windows_keep_only_canonical_window_keys():
    payload = asyncio.run(api_observability_service.build_provider_sla_payload(
        lambda limit: [{
            "provider": "summary-provider",
            "windows": {
                " LAST_1H ": {"attempts": 1},
                "last_24h": {"attempts": 2},
                "experimental_5m": {"attempts": 3},
                "": {"attempts": 4},
            },
        }],
        lambda limit: [],
        100,
        window="all",
    ))

    assert payload["providers"][0]["windows"] == {
        "last_1h": {"attempts": 1},
        "last_24h": {"attempts": 2},
    }


def test_provider_sla_provider_windows_reject_binary_window_keys():
    payload = asyncio.run(api_observability_service.build_provider_sla_payload(
        lambda limit: [{
            "provider": "summary-provider",
            "windows": {
                "last_1h": {"attempts": 1},
                b"last_24h": {"attempts": 2},
                memoryview(b"last_7d"): {"attempts": 3},
            },
        }],
        lambda limit: [],
        100,
        window="all",
    ))

    assert payload["providers"][0]["windows"] == {
        "last_1h": {"attempts": 1},
    }


def test_provider_sla_window_alerts_ignore_status_truthiness_failures():
    class BrokenTruthText:
        def __bool__(self):
            raise RuntimeError("provider sla status truthiness unavailable")

        def __str__(self):
            return "error"

    providers = [{
        "source": "market_data",
        "provider": "fake",
        "attempts": 3,
        "success_rate": 1.0,
        "error_count": 0,
        "last_status": BrokenTruthText(),
        "windows": {"last_24h": {"attempts": 3, "success_rate": 1.0, "error_count": 0}},
    }]

    windowed = api_observability_service.apply_provider_sla_window(providers, "last_24h")

    assert windowed[0]["alert_level"] == "warning"
    assert "fake 最近有來源異常" in windowed[0]["alert_message"]
    assert windowed[0]["alert_basis"] == "last_24h"


def test_provider_sla_window_alerts_ignore_window_map_truthiness_failures():
    class BrokenTruthDict(dict):
        def __bool__(self):
            raise RuntimeError("provider sla window map truthiness unavailable")

    providers = [{
        "source": "market_data",
        "provider": "fake",
        "attempts": 10,
        "success_rate": 1.0,
        "error_count": 0,
        "alert_level": "critical",
        "alert_message": "stale outage",
        "windows": BrokenTruthDict({
            "last_24h": BrokenTruthDict({
                "attempts": 3,
                "availability_attempts": 3,
                "success_rate": 0.25,
                "error_count": 0,
            }),
        }),
    }]

    windowed = api_observability_service.apply_provider_sla_window(providers, "last_24h")

    assert windowed[0]["attempts"] == 3
    assert windowed[0]["success_rate"] == 0.25
    assert windowed[0]["alert_level"] == "critical"
    assert "fake last_24h資料取得率偏低" in windowed[0]["alert_message"]


def test_provider_sla_window_alerts_ignore_provider_row_mapping_failures():
    class BrokenProviderRow:
        def __iter__(self):
            raise RuntimeError("provider sla provider row mapping unavailable")

    windowed = api_observability_service.apply_provider_sla_window([BrokenProviderRow()], "last_24h")

    assert windowed == [{
        "selected_window": "last_24h",
        "alert_level": "ok",
        "alert_message": "",
        "alert_basis": "last_24h",
    }]


def test_provider_sla_alert_projection_ignores_provider_row_mapping_failures():
    class BrokenProviderRow:
        def __iter__(self):
            raise RuntimeError("provider sla alert row mapping unavailable")

    alerts = api_observability_service.alerts_from_providers([BrokenProviderRow()])

    assert alerts == []


def test_provider_sla_alert_projection_uses_string_safe_alert_level():
    class BrokenAlertLevel:
        def __hash__(self):
            raise RuntimeError("provider sla alert level hash unavailable")

        def __str__(self):
            return "warning"

    alerts = api_observability_service.alerts_from_providers([{
        "source": "market_data",
        "provider": "fake",
        "alert_level": BrokenAlertLevel(),
        "alert_message": "provider is stale",
    }])

    assert alerts == [{
        "source": "market_data",
        "provider": "fake",
        "alert_level": "warning",
        "alert_message": "provider is stale",
        "success_rate": None,
        "last_status": None,
        "alert_basis": None,
        "selected_window": "all",
        "windows": {},
    }]


def test_provider_sla_alert_projection_uses_safe_output_conversion():
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("provider sla alert text truthiness unavailable")

        def __str__(self):
            return self.value

    class BrokenWindows:
        def __iter__(self):
            raise RuntimeError("provider sla alert windows unavailable")

    alerts = api_observability_service.alerts_from_providers([{
        "source": BrokenTruthText(" market_data "),
        "provider": BrokenTruthText(" fake "),
        "alert_level": BrokenTruthText(" warning "),
        "alert_message": BrokenTruthText(" provider is stale "),
        "success_rate": float("inf"),
        "last_status": BrokenTruthText(" error "),
        "alert_basis": BrokenTruthText(" last_24h "),
        "selected_window": BrokenTruthText(" last_24h "),
        "windows": BrokenWindows(),
    }])

    assert alerts == [{
        "source": "market_data",
        "provider": "fake",
        "alert_level": "warning",
        "alert_message": "provider is stale",
        "success_rate": 0.0,
        "last_status": "error",
        "alert_basis": "last_24h",
        "selected_window": "last_24h",
        "windows": {},
    }]


def test_provider_sla_alert_projection_rejects_boolean_and_binary_text_fields():
    alerts = api_observability_service.alerts_from_providers([{
        "source": True,
        "provider": b"fake",
        "alert_level": "warning",
        "alert_message": memoryview(b"provider is stale"),
        "last_status": bytearray(b"error"),
        "alert_basis": True,
        "selected_window": memoryview(b"last_24h"),
    }])

    assert alerts == [{
        "source": "",
        "provider": "",
        "alert_level": "warning",
        "alert_message": "",
        "success_rate": None,
        "last_status": "",
        "alert_basis": "",
        "selected_window": "all",
        "windows": {},
    }]


def test_provider_sla_alert_projection_windows_use_safe_numeric_output_conversion():
    class BrokenInt:
        def __int__(self):
            raise RuntimeError("provider sla alert window integer conversion unavailable")

    alerts = api_observability_service.alerts_from_providers([{
        "provider": "fake",
        "alert_level": "warning",
        "windows": {
            "last_24h": {
                "attempts": BrokenInt(),
                "success_rate": float("-inf"),
                "avg_duration_ms": float("nan"),
                "total_records": BrokenInt(),
            },
        },
    }])

    assert alerts[0]["windows"]["last_24h"]["attempts"] == 0
    assert alerts[0]["windows"]["last_24h"]["success_rate"] == 0.0
    assert alerts[0]["windows"]["last_24h"]["avg_duration_ms"] == 0.0
    assert alerts[0]["windows"]["last_24h"]["total_records"] == 0


def test_provider_sla_all_window_projects_cumulative_alerts_safely():
    class BrokenAlertLevel:
        def __hash__(self):
            raise RuntimeError("provider sla cumulative alert level hash unavailable")

        def __str__(self):
            return "critical"

    class BrokenProviderRow:
        def __iter__(self):
            raise RuntimeError("provider sla cumulative alert row mapping unavailable")

    payload = asyncio.run(api_observability_service.build_provider_sla_payload(
        lambda limit: [{"provider": "summary-provider", "alert_level": "ok"}],
        lambda limit: [
            BrokenProviderRow(),
            {
                "source": "market_data",
                "provider": "fake",
                "alert_level": BrokenAlertLevel(),
                "alert_message": "provider outage",
            },
        ],
        100,
        window="all",
    ))

    assert payload["selected_window"] == "all"
    assert payload["providers"] == [{"provider": "summary-provider", "alert_level": "ok"}]
    assert payload["alerts"] == [{
        "source": "market_data",
        "provider": "fake",
        "alert_level": "critical",
        "alert_message": "provider outage",
        "success_rate": None,
        "last_status": None,
        "alert_basis": None,
        "selected_window": "all",
        "windows": {},
    }]


def test_provider_sla_all_window_projects_provider_rows_safely():
    class BrokenProviderRow:
        def __iter__(self):
            raise RuntimeError("provider sla cumulative provider row mapping unavailable")

    payload = asyncio.run(api_observability_service.build_provider_sla_payload(
        lambda limit: [BrokenProviderRow(), {"provider": "summary-provider", "alert_level": "ok"}],
        lambda limit: [],
        100,
        window="all",
    ))

    assert payload["selected_window"] == "all"
    assert payload["providers"] == [{}, {"provider": "summary-provider", "alert_level": "ok"}]
    assert payload["alerts"] == []


def test_provider_sla_all_window_provider_stats_use_safe_output_conversion():
    class BrokenInt:
        def __int__(self):
            raise RuntimeError("provider sla cumulative integer conversion unavailable")

    payload = asyncio.run(api_observability_service.build_provider_sla_payload(
        lambda limit: [{
            "provider": "summary-provider",
            "attempts": BrokenInt(),
            "availability_attempts": BrokenInt(),
            "success_count": BrokenInt(),
            "error_count": BrokenInt(),
            "unavailable_count": BrokenInt(),
            "skipped_fresh_cache_count": BrokenInt(),
            "not_configured_count": BrokenInt(),
            "degraded_enrichment_count": BrokenInt(),
            "success_rate": float("-inf"),
            "avg_duration_ms": float("nan"),
            "total_records": BrokenInt(),
        }],
        lambda limit: [],
        100,
        window="all",
    ))

    provider = payload["providers"][0]
    assert provider["attempts"] == 0
    assert provider["availability_attempts"] == 0
    assert provider["success_count"] == 0
    assert provider["error_count"] == 0
    assert provider["unavailable_count"] == 0
    assert provider["skipped_fresh_cache_count"] == 0
    assert provider["not_configured_count"] == 0
    assert provider["degraded_enrichment_count"] == 0
    assert provider["success_rate"] == 0.0
    assert provider["avg_duration_ms"] == 0.0
    assert provider["total_records"] == 0
    assert payload["selected_window"] == "all"
    assert payload["alerts"] == []


def test_provider_sla_all_window_provider_stats_reject_binary_and_boolean_values():
    payload = asyncio.run(api_observability_service.build_provider_sla_payload(
        lambda limit: [{
            "provider": "summary-provider",
            "attempts": b"4",
            "availability_attempts": True,
            "success_count": bytearray(b"3"),
            "error_count": memoryview(b"2"),
            "unavailable_count": b"1",
            "skipped_fresh_cache_count": True,
            "not_configured_count": bytearray(b"1"),
            "degraded_enrichment_count": memoryview(b"1"),
            "success_rate": b"0.75",
            "avg_duration_ms": True,
            "total_records": b"10",
            "windows": {
                "last_24h": {
                    "attempts": b"5",
                    "success_rate": memoryview(b"0.5"),
                    "avg_duration_ms": bytearray(b"12.5"),
                    "total_records": True,
                },
            },
        }],
        lambda limit: [],
        100,
        window="all",
    ))

    provider = payload["providers"][0]
    assert provider["attempts"] == 0
    assert provider["availability_attempts"] == 0
    assert provider["success_count"] == 0
    assert provider["error_count"] == 0
    assert provider["unavailable_count"] == 0
    assert provider["skipped_fresh_cache_count"] == 0
    assert provider["not_configured_count"] == 0
    assert provider["degraded_enrichment_count"] == 0
    assert provider["success_rate"] == 0.0
    assert provider["avg_duration_ms"] == 0.0
    assert provider["total_records"] == 0
    nested = provider["windows"]["last_24h"]
    assert nested["attempts"] == 0
    assert nested["success_rate"] == 0.0
    assert nested["avg_duration_ms"] == 0.0
    assert nested["total_records"] == 0


def test_provider_sla_selected_window_provider_stats_reject_binary_and_boolean_values():
    payload = asyncio.run(api_observability_service.build_provider_sla_payload(
        lambda limit: [{
            "provider": "summary-provider",
            "attempts": 10,
            "success_rate": 1.0,
            "windows": {
                "last_24h": {
                    "attempts": b"5",
                    "availability_attempts": bytearray(b"5"),
                    "success_count": memoryview(b"2"),
                    "error_count": True,
                    "success_rate": b"0.25",
                    "avg_duration_ms": memoryview(b"12.5"),
                    "total_records": bytearray(b"7"),
                },
            },
        }],
        lambda limit: [],
        100,
        window="last_24h",
    ))

    provider = payload["providers"][0]
    assert provider["attempts"] == 0
    assert provider["availability_attempts"] == 0
    assert provider["success_count"] == 0
    assert provider["error_count"] == 0
    assert provider["success_rate"] == 0.0
    assert provider["avg_duration_ms"] == 0.0
    assert provider["total_records"] == 0
    assert provider["alert_level"] == "ok"
    assert provider["alert_message"] == ""


def test_provider_sla_numeric_fields_ignore_row_mapping_failures():
    class BrokenProviderRow:
        def __iter__(self):
            raise RuntimeError("provider sla numeric row mapping unavailable")

    assert provider_sla_payload_shape.normalize_provider_sla_numeric_fields(BrokenProviderRow()) == {}


def test_provider_sla_payload_summary_fetch_failure_returns_empty_provider_lists():
    def broken_summary_fetcher(_limit):
        raise RuntimeError("provider sla summary unavailable")

    payload = asyncio.run(api_observability_service.build_provider_sla_payload(
        broken_summary_fetcher,
        lambda limit: [{
            "source": "market_data",
            "provider": "fake",
            "alert_level": "critical",
            "alert_message": "provider outage",
        }],
        100,
        window="last_24h",
    ))

    assert payload == {"providers": [], "alerts": [], "selected_window": "last_24h"}


def test_provider_sla_payload_alert_fetch_failure_keeps_provider_rows():
    def broken_alerts_fetcher(_limit):
        raise RuntimeError("provider sla alerts unavailable")

    payload = asyncio.run(api_observability_service.build_provider_sla_payload(
        lambda limit: [{"provider": "summary-provider", "alert_level": "ok"}],
        broken_alerts_fetcher,
        100,
        window="all",
    ))

    assert payload == {
        "providers": [{"provider": "summary-provider", "alert_level": "ok"}],
        "alerts": [],
        "selected_window": "all",
    }


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


def test_job_ops_dashboard_metrics_summarize_latency_telemetry_and_prompt_budget():
    assert importlib.util.find_spec("job_ops_dashboard_metrics") is not None
    metrics = importlib.import_module("job_ops_dashboard_metrics")
    latency_rows = [
        {"created_at": 0.0, "started_at": 10.0, "updated_at": 70.0, "finished_at": 70.0},
        {"created_at": 0.0, "started_at": 20.0, "updated_at": 200.0, "finished_at": 200.0},
        {"created_at": 0.0, "started_at": 30.0, "updated_at": 630.0, "finished_at": 630.0},
    ]
    telemetry_rows = [
        {
            "node_name": "valuation_agent",
            "model": "gemini-2.5-pro",
            "latency_ms": 1_000,
            "status": "success",
            "retry_count": 0,
            "input_tokens": 120,
            "output_tokens": 40,
            "cache_hit": True,
            "quality_gate_pass": 1,
        },
        {
            "node_name": "valuation_agent",
            "model": "gemini-2.5-pro",
            "latency_ms": 2_500,
            "status": "failed",
            "retry_count": 2,
            "input_tokens": 80,
            "output_tokens": 20,
            "cache_hit": False,
            "quality_gate_pass": 0,
            "error": "timeout waiting for model",
        },
    ]

    latency = metrics.job_latency_summary(latency_rows)
    telemetry = metrics.node_telemetry_summary(telemetry_rows)
    budget = metrics.prompt_budget_summary(telemetry_rows)

    assert latency["p50_seconds"] == 180.0
    assert latency["p95_seconds"] == 600.0
    node = telemetry["nodes"]["valuation_agent"]
    assert node["calls"] == 2
    assert node["failure_rate"] == 0.5
    assert node["quality_gate_failures"] == 1
    assert telemetry["models"]["gemini-2.5-pro"]["timeout_errors"] == 1
    assert budget["sample_size"] == 2
    assert budget["total_tokens"] == 260
    assert budget["cache_hit_count"] == 1


def test_ops_dashboard_summarizes_latency_stuck_jobs_and_node_telemetry(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs.sqlite3"
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(db_path))
    monkeypatch.setattr(job_observability, "TASK_DB_PATH", str(db_path))
    job_store.reset_job_store_for_tests()
    now = 20_000.0

    durations = [60.0, 180.0, 600.0]
    for index, duration in enumerate(durations):
        job_id = job_store.create_job(f"24{index}.TW", "v1")
        started_at = 1_000.0 + index * 1_000.0
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE analysis_jobs
                SET status = 'done', started_at = ?, finished_at = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (started_at, started_at + duration, started_at + duration, job_id),
            )
        job_store.record_node_telemetry(
            {
                "job_id": job_id,
                "ticker": f"24{index}.TW",
                "pipeline_id": "v1",
                "node_name": "valuation_agent",
                "model": "gemini-2.5-pro",
                "started_at": started_at,
                "finished_at": started_at + 1,
                "latency_ms": 1000 + index * 100,
                "status": "success",
                "retry_count": index,
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_hit": index == 0,
                "quality_gate_pass": True,
            }
        )

    stuck_job_id = job_store.create_job("9999.TW", "v2")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE analysis_jobs
            SET status = 'running', started_at = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (now - 2_400, now - 1_200, stuck_job_id),
        )
    job_store.record_node_telemetry(
        {
            "job_id": stuck_job_id,
            "ticker": "9999.TW",
            "pipeline_id": "v2",
            "node_name": "valuation_agent",
            "model": "gemini-2.5-pro",
            "started_at": now - 1_300,
            "finished_at": now - 1_290,
            "latency_ms": 2_500,
            "status": "failed",
            "retry_count": 2,
            "cache_hit": False,
            "quality_gate_pass": False,
            "error": "HTTP 429 quota exhausted token=secret-should-hide",
        }
    )

    payload = job_observability.build_ops_dashboard_snapshot(
        db_path=str(db_path),
        now=now,
        stuck_after_seconds=900,
    )

    assert payload["job_latency"]["completed_count"] == 3
    assert payload["job_latency"]["p50_seconds"] == 180.0
    assert payload["job_latency"]["p95_seconds"] == 600.0
    assert payload["job_latency"]["p99_seconds"] == 600.0
    assert payload["stuck_jobs"]["count"] == 1
    assert payload["stuck_jobs"]["jobs"][0]["job_id"] == stuck_job_id
    assert payload["stuck_jobs"]["jobs"][0]["seconds_since_update"] == 1200.0
    node = payload["node_telemetry"]["nodes"]["valuation_agent"]
    assert node["calls"] == 4
    assert node["failures"] == 1
    assert node["failure_rate"] == 0.25
    assert node["retry_count"] == 5
    assert node["cache_hit_rate"] == 0.25
    assert node["quality_gate_failures"] == 1
    model = payload["node_telemetry"]["models"]["gemini-2.5-pro"]
    assert model["calls"] == 4
    assert model["failures"] == 1
    assert model["rate_limit_errors"] == 1
    budget = payload["prompt_budget"]
    assert budget["sample_size"] == 4
    assert budget["tokenized_calls"] == 3
    assert budget["input_tokens"] == 300
    assert budget["output_tokens"] == 150
    assert budget["total_tokens"] == 450
    assert budget["cache_hit_count"] == 1
    assert budget["estimated_cached_input_tokens"] == 100
    assert budget["nodes"]["valuation_agent"]["avg_input_tokens"] == 100
    assert budget["models"]["gemini-2.5-pro"]["avg_total_tokens"] == 150
    route_budget = payload["model_route_budget"]
    assert route_budget["summary"]["estimated_cost_available"] is False
    assert route_budget["routes"]["v1/gemini-2.5-pro"]["total_tokens"] == 450
    assert route_budget["routes"]["v1/gemini-2.5-pro"]["billable_total_tokens"] == 300
    assert route_budget["routes"]["v1/gemini-2.5-pro"]["estimated_cost_usd"] is None
    assert "secret-should-hide" not in str(payload)


def test_queue_observability_reports_rq_depth_and_registries():
    class FakeRedis:
        def ping(self):
            return True

    class FakeRegistry:
        def __init__(self, count):
            self.count = count

    class FakeRqQueue:
        name = "stock-analysis"
        count = 7
        started_job_registry = FakeRegistry(2)
        deferred_job_registry = FakeRegistry(3)
        failed_job_registry = FakeRegistry(1)
        scheduled_job_registry = FakeRegistry(4)

    payload = queue_observability.snapshot_task_queue(
        SimpleNamespace(queue=FakeRqQueue(), redis=FakeRedis())
    )

    assert payload["backend"] == "rq"
    assert payload["available"] is True
    assert payload["queue_name"] == "stock-analysis"
    assert payload["depth"] == 7
    assert payload["registries"] == {
        "started": 2,
        "deferred": 3,
        "failed": 1,
        "scheduled": 4,
    }


def test_queue_observability_reports_per_queue_depths_for_tiered_rq():
    class FakeRedis:
        def ping(self):
            return True

    class FakeRqQueue:
        def __init__(self, name, count):
            self.name = name
            self.count = count

    task_queue = SimpleNamespace(
        queue=FakeRqQueue("analysis.high", 2),
        queues={
            "analysis.high": FakeRqQueue("analysis.high", 2),
            "analysis.normal": FakeRqQueue("analysis.normal", 5),
            "watchlist": FakeRqQueue("watchlist", 3),
        },
        redis=FakeRedis(),
    )

    payload = queue_observability.snapshot_task_queue(task_queue)

    assert payload["backend"] == "rq"
    assert payload["available"] is True
    assert payload["depth"] == 10
    assert payload["queues"] == {
        "analysis.high": {"depth": 2, "registries": {"started": 0, "deferred": 0, "failed": 0, "scheduled": 0}},
        "analysis.normal": {"depth": 5, "registries": {"started": 0, "deferred": 0, "failed": 0, "scheduled": 0}},
        "watchlist": {"depth": 3, "registries": {"started": 0, "deferred": 0, "failed": 0, "scheduled": 0}},
    }


def test_ops_dashboard_api(monkeypatch):
    async def fake_dashboard_payload(*_args, **_kwargs):
        return {"status": "ok", "jobs": {"active_count": 0}, "queue": {"available": True}}

    monkeypatch.setattr(api_observability_service, "build_ops_dashboard_payload", fake_dashboard_payload)

    client = TestClient(api.app)
    response = client.get("/api/observability/dashboard")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ops_dashboard_treats_enrichment_provider_critical_as_warning(monkeypatch):
    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "depth": 0, "registries": {"failed": 0}},
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {
            "selected_window": "last_24h",
            "alerts": [
                {
                    "source": "recent_catalysts",
                    "provider": "Alternative Search",
                    "alert_level": "critical",
                    "alert_message": "Alternative Search last_24h資料取得率偏低",
                }
            ],
        }

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": []}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "warning"
    assert payload["providers"]["core_critical_count"] == 0
    assert payload["providers"]["enrichment_critical_count"] == 1
    assert payload["providers"]["alerts"][0]["impact"] == "enrichment"


def test_ops_dashboard_payload_exposes_model_route_budget(monkeypatch):
    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {},
            "model_route_budget": {
                "schema_version": "model_route_budget.v1",
                "warnings": [{"id": "retry_storm", "route": "v2/gemini-2.5-pro"}],
            },
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "depth": 0, "registries": {"failed": 0}},
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": []}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["model_route_budget"]["schema_version"] == "model_route_budget.v1"
    assert payload["model_route_budget"]["warnings"][0]["id"] == "retry_storm"


def test_ops_dashboard_warns_on_notification_delivery_failures(monkeypatch):
    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "depth": 0, "registries": {"failed": 0}},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 3,
            "sent_count": 1,
            "failed_count": 2,
            "pending_count": 0,
            "retry_exhausted_count": 1,
            "channel_counts": {"telegram_webhook": 2, "local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": []}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "warning"
    assert payload["notification_delivery"]["health"] == "warning"
    assert payload["notification_delivery"]["retry_exhausted_count"] == 1
    assert payload["notification_delivery"]["channel_counts"]["telegram_webhook"] == 2


def test_ops_dashboard_queue_snapshot_failure_keeps_other_sections(monkeypatch):
    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )

    def broken_queue_snapshot(_task_queue):
        raise RuntimeError("ops dashboard queue snapshot unavailable")

    monkeypatch.setattr(api_observability_service, "snapshot_task_queue", broken_queue_snapshot)
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "critical"
    assert payload["queue"] == {"backend": "unknown", "available": False, "queue_name": "unknown", "depth": 0, "queues": {}}
    assert payload["jobs"] == {"active_count": 0}
    assert payload["job_latency"] == {"p95_seconds": 1.5}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_stuck_job_count_truthiness_keeps_other_sections(monkeypatch):
    class BrokenStuckJobCount:
        def __bool__(self):
            raise RuntimeError("ops dashboard stuck job count truthiness unavailable")

        def __int__(self):
            return 0

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": BrokenStuckJobCount(), "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"]["available"] is True
    assert payload["stuck_jobs"]["jobs"] == []
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_stuck_job_binary_count_does_not_raise_warning_or_leak_payload(monkeypatch):
    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": b"3", "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["stuck_jobs"]["count"] == 0
    assert json.loads(json.dumps(payload))["stuck_jobs"]["count"] == 0


def test_ops_dashboard_queue_available_truthiness_keeps_other_sections(monkeypatch):
    class AvailableWithBrokenTruthiness:
        def __bool__(self):
            raise RuntimeError("ops dashboard queue availability truthiness unavailable")

        def __str__(self):
            return "true"

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {
            "backend": "rq",
            "available": AvailableWithBrokenTruthiness(),
            "queue_name": "stock-analysis",
            "depth": 0,
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"]["available"] is True
    assert payload["jobs"] == {"active_count": 0}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_queue_metadata_uses_safe_output_conversion(monkeypatch):
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("ops dashboard queue metadata truthiness unavailable")

        def __str__(self):
            return self.value

    class BrokenQueueDepth:
        def __int__(self):
            raise RuntimeError("ops dashboard queue depth unavailable")

    class BrokenQueueMap:
        def __iter__(self):
            raise RuntimeError("ops dashboard queue map unavailable")

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {
            "backend": BrokenTruthText("rq"),
            "available": True,
            "queue_name": BrokenTruthText("stock-analysis"),
            "depth": BrokenQueueDepth(),
            "queues": BrokenQueueMap(),
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"] == {
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": 0,
        "queues": {},
    }
    assert payload["jobs"] == {"active_count": 0}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_named_queue_details_use_safe_output_conversion(monkeypatch):
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("ops dashboard named queue truthiness unavailable")

        def __str__(self):
            return self.value

    class BrokenQueueDetails:
        def __iter__(self):
            raise RuntimeError("ops dashboard named queue detail unavailable")

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {
            "backend": "rq",
            "available": True,
            "queue_name": "stock-analysis",
            "depth": 0,
            "queues": {
                BrokenTruthText("maintenance"): {"depth": 2, "registry": "started"},
                "broken": BrokenQueueDetails(),
            },
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"]["queues"] == {
        "maintenance": {"depth": 2, "registry": "started"},
        "broken": {},
    }
    assert payload["jobs"] == {"active_count": 0}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_named_queue_detail_fields_use_safe_output_conversion(monkeypatch):
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("ops dashboard named queue detail truthiness unavailable")

        def __str__(self):
            return self.value

    class BrokenQueueCount:
        def __int__(self):
            raise RuntimeError("ops dashboard named queue count unavailable")

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {
            "backend": "rq",
            "available": True,
            "queue_name": "stock-analysis",
            "depth": 0,
            "queues": {
                "maintenance": {
                    "depth": BrokenQueueCount(),
                    "registries": {BrokenTruthText("started"): BrokenQueueCount(), "failed": 3},
                    "registry": BrokenTruthText("started"),
                },
            },
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"]["queues"]["maintenance"] == {
        "depth": 0,
        "registries": {"started": 0, "failed": 3},
        "registry": "started",
    }
    assert payload["jobs"] == {"active_count": 0}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_queue_supplemental_fields_use_safe_output_conversion(monkeypatch):
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("ops dashboard queue supplemental truthiness unavailable")

        def __str__(self):
            return self.value

    class BrokenInt:
        def __int__(self):
            raise RuntimeError("ops dashboard queue supplemental integer unavailable")

    class BrokenFloat:
        def __float__(self):
            raise RuntimeError("ops dashboard queue supplemental float unavailable")

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {
            "backend": "rq",
            "available": True,
            "queue_name": "stock-analysis",
            "depth": 0,
            "queues": {},
            "registries": {BrokenTruthText("failed"): BrokenInt(), "scheduled": 4},
            "active_tasks": BrokenInt(),
            "oldest_queued_seconds": BrokenFloat(),
            "job_timeout_seconds": BrokenInt(),
            "error": BrokenTruthText("redis timeout"),
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"] == {
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": 0,
        "queues": {},
        "registries": {"failed": 0, "scheduled": 4},
        "active_tasks": 0,
        "oldest_queued_seconds": 0.0,
        "job_timeout_seconds": 0,
        "error": "redis timeout",
    }
    assert payload["jobs"] == {"active_count": 0}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_queue_dashboard_payload_rejects_boolean_and_binary_text_metadata():
    payload = queue_dashboard_payload.normalize_ops_queue_payload({
        "backend": True,
        "available": True,
        "queue_name": b"stock-analysis",
        "depth": 0,
        "queues": {
            b"maintenance": {
                "depth": 2,
                "registry": True,
                "note": memoryview(b"internal"),
            },
        },
        "error": True,
        b"debug": "should not leak",
    })

    assert payload["backend"] == "unknown"
    assert payload["queue_name"] == "unknown"
    assert payload["queues"] == {
        "unknown": {
            "depth": 2,
            "registry": "",
            "note": "",
        },
    }
    assert payload["error"] == ""
    assert "debug" not in payload


def test_queue_dashboard_payload_rejects_binary_integer_fields():
    payload = queue_dashboard_payload.normalize_ops_queue_payload({
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": b"6",
        "queues": {
            "maintenance": {
                "depth": bytearray(b"3"),
                "registries": {"failed": memoryview(b"2")},
            },
        },
        "registries": {"failed": b"4"},
        "active_tasks": True,
        "job_timeout_seconds": memoryview(b"900"),
    })

    assert payload["depth"] == 0
    assert payload["queues"]["maintenance"]["depth"] == 0
    assert payload["queues"]["maintenance"]["registries"] == {"failed": 0}
    assert payload["registries"] == {"failed": 0}
    assert payload["active_tasks"] == 0
    assert payload["job_timeout_seconds"] == 0


def test_queue_dashboard_payload_replaces_non_finite_age_with_zero():
    infinite = queue_dashboard_payload.normalize_ops_queue_payload({
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": 0,
        "oldest_queued_seconds": float("inf"),
    })
    nan = queue_dashboard_payload.normalize_ops_queue_payload({
        "backend": "rq",
        "available": True,
        "queue_name": "stock-analysis",
        "depth": 0,
        "oldest_queued_seconds": float("nan"),
    })

    assert infinite["oldest_queued_seconds"] == 0.0
    assert nan["oldest_queued_seconds"] == 0.0


def test_queue_dashboard_payload_rejects_binary_and_boolean_age_fields():
    for raw_age in (b"3600.5", bytearray(b"15.25"), memoryview(b"2.5"), True):
        payload = queue_dashboard_payload.normalize_ops_queue_payload({
            "backend": "rq",
            "available": True,
            "queue_name": "stock-analysis",
            "depth": 0,
            "oldest_queued_seconds": raw_age,
        })

        assert payload["oldest_queued_seconds"] == 0.0


def test_ops_dashboard_notification_delivery_summary_fetch_failure_keeps_other_sections(monkeypatch):
    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )

    def broken_delivery_summary():
        raise RuntimeError("ops dashboard notification delivery summary unavailable")

    monkeypatch.setattr(api_observability_service, "get_delivery_audit_summary", broken_delivery_summary, raising=False)

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"]["available"] is True
    assert payload["jobs"] == {"active_count": 0}
    assert payload["job_latency"] == {"p95_seconds": 1.5}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"
    assert payload["notification_delivery"]["total_count"] == 0
    assert payload["notification_delivery"]["failed_count"] == 0
    assert payload["notification_delivery"]["channel_counts"] == {}


def test_ops_dashboard_api_quota_payload_failure_keeps_other_sections(monkeypatch):
    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    def broken_api_quota_payload(_summary_fetcher):
        raise RuntimeError("ops dashboard api quota payload unavailable")

    monkeypatch.setattr(api_observability_service, "_build_api_quota_payload", broken_api_quota_payload)

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"]["available"] is True
    assert payload["jobs"] == {"active_count": 0}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": []}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_malformed_api_quota_payload_keeps_other_sections(monkeypatch):
    class BrokenApiQuotaPayload:
        def __iter__(self):
            raise RuntimeError("ops dashboard api quota payload mapping unavailable")

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def malformed_api_quota_payload(_summary_fetcher):
        return BrokenApiQuotaPayload()

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", malformed_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"]["available"] is True
    assert payload["jobs"] == {"active_count": 0}
    assert payload["job_latency"] == {"p95_seconds": 1.5}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": []}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_malformed_api_quota_services_keep_other_sections(monkeypatch):
    class BrokenApiQuotaServices:
        def __iter__(self):
            raise RuntimeError("ops dashboard api quota services unavailable")

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def malformed_api_quota_services(_summary_fetcher):
        return {"services": BrokenApiQuotaServices(), "timezone": "Asia/Taipei"}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", malformed_api_quota_services)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"]["available"] is True
    assert payload["jobs"] == {"active_count": 0}
    assert payload["job_latency"] == {"p95_seconds": 1.5}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [], "timezone": "Asia/Taipei"}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_job_snapshot_failure_keeps_other_sections(monkeypatch):
    def broken_ops_snapshot(**_kwargs):
        raise RuntimeError("ops dashboard job snapshot unavailable")

    monkeypatch.setattr(api_observability_service, "build_ops_dashboard_snapshot", broken_ops_snapshot)
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "warning"
    assert payload["queue"]["available"] is True
    assert payload["jobs"] == {}
    assert payload["job_latency"] == {}
    assert payload["stuck_jobs"] == {}
    assert payload["node_telemetry"] == {}
    assert payload["model_route_budget"] == {}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_job_unavailable_flag_truthiness_keeps_other_sections(monkeypatch):
    class UnavailableFlagWithBrokenTruthiness:
        def __bool__(self):
            raise RuntimeError("ops dashboard job unavailable flag truthiness unavailable")

        def __str__(self):
            return "true"

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "observability_unavailable": UnavailableFlagWithBrokenTruthiness(),
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "warning"
    assert payload["queue"]["available"] is True
    assert payload["jobs"] == {"active_count": 0}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_malformed_job_sections_fall_back_to_empty_sections(monkeypatch):
    class BrokenJobSection:
        def __iter__(self):
            raise RuntimeError("ops dashboard nested job section unavailable")

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": BrokenJobSection(),
            "job_latency": BrokenJobSection(),
            "stuck_jobs": BrokenJobSection(),
            "node_telemetry": BrokenJobSection(),
            "model_route_budget": BrokenJobSection(),
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"]["available"] is True
    assert payload["jobs"] == {}
    assert payload["job_latency"] == {}
    assert payload["stuck_jobs"] == {}
    assert payload["node_telemetry"] == {}
    assert payload["model_route_budget"] == {}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_malformed_job_payload_keeps_other_sections(monkeypatch):
    class BrokenJobPayload:
        def __iter__(self):
            raise RuntimeError("ops dashboard job payload mapping unavailable")

    monkeypatch.setattr(api_observability_service, "build_ops_dashboard_snapshot", lambda **_kwargs: BrokenJobPayload())
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "warning"
    assert payload["queue"]["available"] is True
    assert payload["jobs"] == {}
    assert payload["job_latency"] == {}
    assert payload["stuck_jobs"] == {}
    assert payload["node_telemetry"] == {}
    assert payload["model_route_budget"] == {}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_malformed_provider_payload_keeps_other_sections(monkeypatch):
    class BrokenProviderPayload:
        def __iter__(self):
            raise RuntimeError("ops dashboard provider payload mapping unavailable")

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def malformed_provider_payload(*_args, **_kwargs):
        return BrokenProviderPayload()

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", malformed_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"]["available"] is True
    assert payload["jobs"] == {"active_count": 0}
    assert payload["job_latency"] == {"p95_seconds": 1.5}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["providers"]["alert_count"] == 0
    assert payload["providers"]["alerts"] == []
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_provider_selected_window_uses_string_safe_output(monkeypatch):
    class ProviderWindowWithBrokenTruthiness:
        def __bool__(self):
            raise RuntimeError("ops dashboard provider selected window truthiness unavailable")

        def __str__(self):
            return "last_24h"

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def malformed_provider_window(*_args, **_kwargs):
        return {"selected_window": ProviderWindowWithBrokenTruthiness(), "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", malformed_provider_window)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"]["available"] is True
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["providers"]["alerts"] == []
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_malformed_provider_alerts_keep_other_sections(monkeypatch):
    class BrokenProviderAlerts:
        def __iter__(self):
            raise RuntimeError("ops dashboard provider alerts unavailable")

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def malformed_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": BrokenProviderAlerts()}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", malformed_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["queue"]["available"] is True
    assert payload["jobs"] == {"active_count": 0}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["providers"]["alert_count"] == 0
    assert payload["providers"]["alerts"] == []
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_keeps_core_provider_critical_as_critical(monkeypatch):
    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "depth": 0, "registries": {"failed": 0}},
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {
            "selected_window": "last_24h",
            "alerts": [
                {
                    "source": "market_data",
                    "provider": "yfinance",
                    "alert_level": "critical",
                    "alert_message": "yfinance last_24h資料取得率偏低",
                }
            ],
        }

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": []}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "critical"
    assert payload["providers"]["core_critical_count"] == 1
    assert payload["providers"]["enrichment_critical_count"] == 0
    assert payload["providers"]["alerts"][0]["impact"] == "core"


def test_ops_dashboard_provider_alert_source_truthiness_does_not_break_payload(monkeypatch):
    class CoreSourceWithBrokenTruthiness:
        def __bool__(self):
            raise RuntimeError("ops dashboard provider alert source truthiness unavailable")

        def __str__(self):
            return "market_data"

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {},
            "model_route_budget": {},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {
            "selected_window": "last_24h",
            "alerts": [
                {
                    "source": CoreSourceWithBrokenTruthiness(),
                    "provider": "yfinance",
                    "alert_level": "critical",
                    "alert_message": "yfinance last_24h資料取得率偏低",
                }
            ],
        }

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "critical"
    assert payload["queue"]["available"] is True
    assert payload["providers"]["core_critical_count"] == 1
    assert payload["providers"]["enrichment_critical_count"] == 0
    assert payload["providers"]["alerts"][0]["impact"] == "core"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}


def test_ops_dashboard_provider_alert_level_comparison_does_not_break_payload(monkeypatch):
    class CriticalAlertLevelWithBrokenComparison:
        def __eq__(self, _other):
            raise RuntimeError("ops dashboard provider alert level comparison unavailable")

        def __str__(self):
            return "critical"

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {},
            "model_route_budget": {},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {
            "selected_window": "last_24h",
            "alerts": [
                {
                    "source": "market_data",
                    "provider": "yfinance",
                    "alert_level": CriticalAlertLevelWithBrokenComparison(),
                    "alert_message": "yfinance last_24h資料取得率偏低",
                }
            ],
        }

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "critical"
    assert payload["queue"]["available"] is True
    assert payload["providers"]["critical_count"] == 1
    assert payload["providers"]["core_critical_count"] == 1
    assert payload["providers"]["alerts"][0]["alert_level"] == "critical"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}


def test_ops_dashboard_provider_alert_success_rate_uses_finite_output_conversion(monkeypatch):
    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {},
            "model_route_budget": {},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {
            "selected_window": "last_24h",
            "alerts": [
                {
                    "source": "market_data",
                    "provider": "yfinance",
                    "alert_level": "warning",
                    "alert_message": "yfinance last_24h資料取得率偏低",
                    "success_rate": float("inf"),
                },
                {
                    "source": "news",
                    "provider": "search",
                    "alert_level": "warning",
                    "alert_message": "search last_24h資料取得率偏低",
                    "success_rate": float("nan"),
                },
            ],
        }

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "warning"
    assert payload["queue"]["available"] is True
    assert [alert["success_rate"] for alert in payload["providers"]["alerts"]] == [0.0, 0.0]
    assert payload["providers"]["warning_count"] == 2
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}


def test_ops_dashboard_provider_alert_text_fields_use_safe_output_conversion(monkeypatch):
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("ops dashboard provider alert text truthiness unavailable")

        def __str__(self):
            return self.value

    class BrokenWindows:
        def __iter__(self):
            raise RuntimeError("ops dashboard provider alert windows unavailable")

    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {},
            "model_route_budget": {},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {
            "selected_window": "last_24h",
            "alerts": [{
                "source": BrokenTruthText(" market_data "),
                "provider": BrokenTruthText(" yfinance "),
                "alert_level": "warning",
                "alert_message": BrokenTruthText(" provider stale "),
                "success_rate": 0.5,
                "last_status": BrokenTruthText(" error "),
                "alert_basis": BrokenTruthText(" last_24h "),
                "selected_window": BrokenTruthText(" last_24h "),
                "windows": BrokenWindows(),
            }],
        }

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "warning"
    assert payload["providers"]["alerts"][0] == {
        "source": "market_data",
        "provider": "yfinance",
        "alert_level": "warning",
        "alert_message": "provider stale",
        "success_rate": 0.5,
        "last_status": "error",
        "alert_basis": "last_24h",
        "selected_window": "last_24h",
        "windows": {},
        "impact": "core",
    }
    assert payload["jobs"] == {"active_count": 0}
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}


def test_provider_sla_dashboard_alert_payload_ignores_mapping_get_failures():
    class BrokenGetDict(dict):
        def get(self, *_args, **_kwargs):
            raise RuntimeError("provider alert get accessor unavailable")

    payload = provider_sla_observability.dashboard_provider_alert_payload(
        BrokenGetDict(
            {
                "source": "market_data",
                "provider": "yfinance",
                "alert_level": "critical",
                "alert_message": "source unavailable",
                "success_rate": 0.25,
                "last_status": "error",
                "alert_basis": "last_24h",
                "selected_window": "last_24h",
                "windows": {"last_24h": {"attempts": 4, "success_rate": 0.25}},
            }
        ),
        core_sources={"market_data"},
    )

    assert payload["impact"] == "core"
    assert payload["provider"] == "yfinance"
    assert payload["alert_level"] == "critical"
    assert payload["windows"]["last_24h"]["attempts"] == 4


def test_ops_dashboard_legacy_alias(monkeypatch):
    async def fake_dashboard_payload(*_args, **_kwargs):
        return {"status": "ok", "jobs": {"active_count": 0}, "queue": {"available": True}}

    monkeypatch.setattr(api_observability_service, "build_ops_dashboard_payload", fake_dashboard_payload)

    client = TestClient(api.app)
    response = client.get("/api/ops/dashboard")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_healthz_and_readyz_routes(monkeypatch):
    monkeypatch.setattr(api, "build_readiness_payload", lambda **_kwargs: {"status": "ready", "checks": []})

    client = TestClient(api.app)
    health = client.get("/healthz")
    ready = client.get("/readyz")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_basic_auth_protects_read_endpoints_when_configured(monkeypatch):
    monkeypatch.setattr(basic_auth, "BASIC_AUTH_USERNAME", "operator", raising=False)
    monkeypatch.setattr(basic_auth, "BASIC_AUTH_PASSWORD", "correct-horse", raising=False)

    client = TestClient(api.app)
    credentials = base64.b64encode(b"operator:correct-horse").decode("ascii")

    health = client.get("/healthz")
    denied = client.get("/api/client-config")
    allowed = client.get("/api/client-config", headers={"Authorization": f"Basic {credentials}"})

    assert health.status_code == 200
    assert denied.status_code == 401
    assert denied.headers["www-authenticate"] == 'Basic realm="stock-agent", charset="UTF-8"'
    assert allowed.status_code == 200


def test_readyz_returns_503_when_runtime_dependency_fails(monkeypatch):
    monkeypatch.setattr(
        api,
        "build_readiness_payload",
        lambda **_kwargs: {
            "status": "not_ready",
            "checks": [{"name": "redis", "status": "fail", "message": "connection refused"}],
        },
    )

    client = TestClient(api.app)
    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


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


def test_pipeline_progress_callback_preserves_llm_stream_delta_payload():
    from analysis_job_progress import make_pipeline_progress_callback

    appended = []
    callback = make_pipeline_progress_callback(
        job_id="job-stream",
        pipeline_def={"short_label": "A", "label": "Mode A"},
        current_pipeline_id="v1",
        sequence_total=1,
        total_agents=3,
        completed_agent_offset=0,
        agent_count=3,
        cancel_check=lambda: None,
        append_event_func=lambda job_id, payload: appended.append((job_id, payload)),
    )

    callback({
        "type": "llm_stream_delta",
        "phase": "llm_stream_delta",
        "current": 1,
        "total": 3,
        "name": "Agent 1",
        "agent_num": 1,
        "message": "Agent 1 正在串流模型輸出...",
        "delta": "partial token text",
        "metadata": {"model_id": "gemini-test", "stream_sequence": 1},
    })

    assert appended == [
        (
            "job-stream",
            {
                "type": "llm_stream_delta",
                "message": "Agent 1 正在串流模型輸出...",
                "detail": "A Agent 1/3 · Agent 1",
                "current": 1,
                "total": 3,
                "phase": "llm_stream_delta",
                "level": None,
                "agent_num": 1,
                "metadata": {"model_id": "gemini-test", "stream_sequence": 1},
                "pipeline_id": "v1",
                "pipeline_label": "Mode A",
                "pipeline_current": 1,
                "pipeline_total": 3,
                "delta": "partial token text",
            },
        )
    ]


def test_api_usage_store_uses_short_busy_timeout_for_worker_contention(monkeypatch, tmp_path):
    db_path = tmp_path / "api_usage.sqlite3"
    monkeypatch.setattr(api_usage_store, "API_USAGE_DB_PATH", str(db_path))
    api_usage_store.reset_api_usage_store_for_tests()

    with api_usage_store._connect_for_path(db_path) as conn:
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]

    assert journal_mode == "wal"
    assert busy_timeout == 3000


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
        {"source": "market_data", "provider": "FMP quote", "status": "error", "message": "quota"},
        created_at=timestamp,
    )

    payload = api_quota_service.build_api_quota_payload(lambda limit=100: [
        {"source": "market_data", "provider": "FMP quote", "last_status": "error", "alert_level": "warning"},
    ])

    gemini = next(item for item in payload["services"] if item["service"] == "Gemini / Google AI")
    fmp = next(item for item in payload["services"] if item["service"] == "Financial Modeling Prep")
    assert gemini["usage"]["observed_calls_since_reset"] == 1
    assert gemini["usage"]["ledger_source"] == "api_usage_events"
    assert "Google Custom Search" not in {item["service"] for item in payload["services"]}
    assert fmp["usage"]["observed_24h_errors"] == 1


def test_api_quota_payload_rejects_binary_and_boolean_observation_fields(monkeypatch, tmp_path):
    db_path = tmp_path / "api_usage.sqlite3"
    monkeypatch.setattr(api_usage_store, "API_USAGE_DB_PATH", str(db_path))
    monkeypatch.setattr(
        api_quota_service,
        "RPD_LIMITS",
        {"gemini-2.5-pro": memoryview(b"1500"), "bool_limit": True, memoryview(b"leaky_limit"): 25},
    )
    api_usage_store.reset_api_usage_store_for_tests()

    payload = api_quota_service.build_api_quota_payload(lambda limit=100: [
        {
            "source": memoryview(b"internal_market_data"),
            "provider": "FMP quote",
            "last_status": True,
            "alert_level": bytearray(b"critical"),
            "success_rate": memoryview(b"0.75"),
        },
    ])

    gemini = next(item for item in payload["services"] if item["service"] == "Gemini / Google AI")
    fmp = next(item for item in payload["services"] if item["service"] == "Financial Modeling Prep")

    assert gemini["daily_limit"] == {"gemini-2.5-pro": 0, "bool_limit": 0}
    assert fmp["usage"]["providers"] == [
        {
            "source": "unknown",
            "provider": "FMP quote",
            "last_status": "unknown",
            "alert_level": "unknown",
            "success_rate": 0.0,
        }
    ]


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
    monkeypatch.setattr(api, "find_queue_backed_active_job", lambda ticker, pipeline_id="v1": {})
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


def test_mutation_endpoints_reject_legacy_admin_token_by_default(monkeypatch):
    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "secret-token")
    monkeypatch.setattr(api, "ALLOW_LEGACY_ADMIN_TOKEN", False, raising=False)
    monkeypatch.setattr(api, "get_job", lambda job_id: {"job_id": job_id, "ticker": "2449", "pipeline_id": "both", "status": "running"})
    monkeypatch.setattr(api, "request_job_cancel", lambda job_id, reason: True)

    client = TestClient(api.app)
    denied = client.post("/api/analyze/2449/cancel?job_id=job-1&pipeline=both")
    legacy_denied = client.post(
        "/api/analyze/2449/cancel?job_id=job-1&pipeline=both",
        headers={"X-Admin-Token": "secret-token"},
    )
    allowed = client.post(
        "/api/analyze/2449/cancel?job_id=job-1&pipeline=both",
        headers={"X-Mutation-Token": "secret-token"},
    )

    assert denied.status_code == 403
    assert legacy_denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True
    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "")


def test_legacy_admin_token_alias_can_be_temporarily_enabled(monkeypatch):
    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "secret-token")
    monkeypatch.setattr(api, "ALLOW_LEGACY_ADMIN_TOKEN", True, raising=False)

    api.require_mutation_authorized(type("Req", (), {
        "headers": {"x-admin-token": "secret-token"},
        "client": None,
    })())


def test_api_mutation_security_helper_builds_tokens_cors_and_authorization():
    assert importlib.util.find_spec("api_mutation_security") is not None
    security = importlib.import_module("api_mutation_security")
    rate_limit_calls = []

    assert security.allowed_mutation_tokens("local", "runtime-token", "configured-token") == {
        "runtime-token",
        "configured-token",
    }
    assert security.allowed_mutation_tokens("server", "runtime-token", "") == set()
    assert security.client_config("local", "runtime-token", "X-Mutation-Token") == {
        "mutation_header": "X-Mutation-Token",
        "mutation_token": "runtime-token",
        "deployment_mode": "local",
    }
    assert security.client_config("server", "runtime-token", "X-Mutation-Token")["mutation_token"] == ""
    assert security.cors_allow_methods("lan") == ["GET", "POST", "DELETE", "OPTIONS"]
    assert security.cors_allow_headers("prod", "X-Mutation-Token") == [
        "Content-Type",
        "X-Mutation-Token",
        "X-Admin-Token",
        "Last-Event-ID",
    ]

    class FakeRequest:
        headers = {"x-admin-token": "configured-token"}
        client = None

    security.require_mutation_authorized(
        FakeRequest(),
        check_mutation_rate_limit=lambda request, tokens, max_requests, window_seconds: rate_limit_calls.append(
            (tokens, max_requests, window_seconds)
        ),
        allow_legacy_admin_token=True,
        mutation_api_token="configured-token",
        runtime_mutation_token="runtime-token",
        deployment_mode="server",
        max_requests=3,
        window_seconds=60,
    )
    assert rate_limit_calls == [(["", "configured-token"], 3, 60)]


def test_mutation_authorization_rate_limits_repeated_attempts(monkeypatch):
    import mutation_rate_limit

    class FakeClient:
        host = "203.0.113.10"

    class FakeRequest:
        client = FakeClient()
        headers = {"x-mutation-token": "secret-token"}

    now = [1000.0]
    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "secret-token")
    monkeypatch.setattr(api, "MUTATION_RATE_LIMIT_MAX_REQUESTS", 2, raising=False)
    monkeypatch.setattr(api, "MUTATION_RATE_LIMIT_WINDOW_SECONDS", 60, raising=False)
    monkeypatch.setattr(mutation_rate_limit.time, "time", lambda: now[0])
    mutation_rate_limit.reset_mutation_rate_limiter_for_tests()

    api.require_mutation_authorized(FakeRequest())
    api.require_mutation_authorized(FakeRequest())
    with pytest.raises(HTTPException) as exc_info:
        api.require_mutation_authorized(FakeRequest())

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "60"
    now[0] += 61
    api.require_mutation_authorized(FakeRequest())


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
    with pytest.raises(HTTPException):
        api.require_mutation_authorized(type("Req", (), {
        "headers": {"x-admin-token": "long-lived-admin-token"},
        "client": None,
        })())


def test_async_html_report_rendering_does_not_generate_imagen_cover(monkeypatch):
    async def fail_cover_generation(context):
        raise AssertionError("Imagen cover generation should not run")

    monkeypatch.setattr(html_renderer, "prepare_report_cover_async", fail_cover_generation, raising=False)
    html = asyncio.run(html_renderer.generate_html_report_async({
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {"ticker": "2330.TW", "company_name": "台積電", "current_price": 100, "source_audit": []},
        "analyses": {},
        "parsed": {},
    }))

    assert "台積電" in html


def test_model_routes_no_longer_configure_imagen_report_covers():
    routes = (ROOT / "backend" / "model_routes.json").read_text(encoding="utf-8")
    settings = (ROOT / "backend" / "settings" / "models.py").read_text(encoding="utf-8")

    assert "report_cover_model" not in routes
    assert "report_cover_fallback_models" not in routes
    assert "imagen-4.0" not in routes
    assert "REPORT_COVER" not in settings


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


def test_context_digest_runtime_helpers_scope_hash_cache_key_and_event_metadata():
    runtime_path = ROOT / "backend" / "context_digest_runtime.py"
    assert runtime_path.exists()
    context_digest_runtime = importlib.import_module("context_digest_runtime")
    context = {
        "pipeline_id": "pipe-v1",
        "pipeline_label": "夜間批次",
        "prompt_version": "prompt-a",
        "agent_positions": {4: 2},
        "agent_total": 6,
        "analyses": {
            1: "商業模式" * 120,
            "2": "財務分析",
            4: "本輪 Agent 不應進 hash",
            5: "後續 Agent 不應進 hash",
            "peer": "非數字 key 不應進 hash",
        },
    }

    input_hash = context_digest_runtime._digest_input_hash(4, context)
    changed_non_inputs = dict(
        context,
        analyses={
            **context["analyses"],
            4: "本輪 Agent 改變仍不應進 hash",
            5: "後續 Agent 改變仍不應進 hash",
            "peer": "非數字 key 改變仍不應進 hash",
        },
    )
    changed_prior = dict(context, analyses={**context["analyses"], "2": "前序分析改變"})

    assert context_digest_runtime._digest_input_hash(4, changed_non_inputs) == input_hash
    assert context_digest_runtime._digest_input_hash(4, changed_prior) != input_hash

    cache_key = context_digest_runtime._context_digest_cache_key(4, input_hash, "gemini-a", context)
    changed_prompt_key = context_digest_runtime._context_digest_cache_key(
        4,
        input_hash,
        "gemini-a",
        dict(context, prompt_version="prompt-b"),
    )

    assert cache_key.startswith("context_digest:")
    assert changed_prompt_key != cache_key
    assert context_digest_runtime._context_digest_model_sequence()

    event = context_digest_runtime._agent_event_kwargs(
        context,
        4,
        "gemini-a",
        "context_digest_done",
        "摘要完成",
        level="warning",
    )

    assert event == {
        "phase": "context_digest_done",
        "level": "warning",
        "message": "摘要完成",
        "current": 2,
        "total": 6,
        "name": "投資銀行估值分析",
        "agent_num": 4,
        "pipeline_id": "pipe-v1",
        "pipeline_label": "夜間批次",
        "metadata": {"model_id": "gemini-a", "task": "context_digest"},
    }


def test_context_digest_cache_reuses_digest_across_contexts(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache

    calls = {"llm": 0}

    class FakeDigestRotator:
        def get_key(self, *_args, **_kwargs):
            return "fake-key"

    def fake_generate(*_args, **_kwargs):
        calls["llm"] += 1
        return type("Response", (), {"text": "{\"decision_relevant_facts\":[\"跨 run 摘要\"]}"})()

    def build_context():
        return {
            "pipeline_id": "v1",
            "analyses": {1: "商業模式", 2: "財務分析"},
            "structured_outputs": {},
            "agent_positions": {4: 4},
            "agent_total": 10,
        }

    try:
        cache_store.set_cache_backend(InMemoryCache())
        monkeypatch.setattr(context_digest_tasks, "_generate_context_digest_content", fake_generate)
        monkeypatch.setattr(context_digest_tasks, "response_text", lambda response: response.text)

        first_context = build_context()
        second_context = build_context()
        context_digest_tasks.ensure_context_digest(4, first_context, FakeDigestRotator())
        context_digest_tasks.ensure_context_digest(4, second_context, FakeDigestRotator())

        assert calls["llm"] == 1
        assert second_context["context_digests"][4] == first_context["context_digests"][4]
    finally:
        cache_store.reset_cache_store_for_tests()
