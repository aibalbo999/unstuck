"""Panel rates must describe nonempty observations, not tolerated outcomes."""

from fastapi.testclient import TestClient

import api
import provider_sla


def entry(source, provider, status, count=0, message=""):
    return dict(source=source, provider=provider, status=status, record_count=count, message=message)


def acquisition(window="last_24h"):
    response = TestClient(api.app).get("/api/observability/provider-sla", params={"window": window})
    assert response.status_code == 200
    return response.json()["acquisition"]


def test_empty_earnings_and_empty_cache_are_not_success(monkeypatch):
    provider_sla.record_source_audit_entries([
        entry("earnings_call", "MOPS investor conference", "degraded_enrichment"),
        entry("earnings_call", "MOPS investor conference", "degraded_enrichment", message="optional 外部來源本次無新增資料，已保留為可接受的補充資料空結果。"),
        entry("earnings_call", "cache", "skipped_fresh_cache"),
    ])
    result = acquisition()
    row = result["sources"][0]
    assert row["fetch_attempts"] == 1
    assert row["nonempty_rate"] == 0
    assert row["empty_count"] == 1
    assert row["empty_cache_count"] == 1
    assert row["aggregate_count"] == 1


def test_source_and_merge_are_not_counted_twice_and_retries_remain(monkeypatch):
    provider_sla.record_source_audit_entries([
        entry("global_market_context", "yfinance global context", "error"),
        entry("global_market_context", "yfinance global context", "success", 18),
        entry("global_market_context", "Global market context", "success", 18, "optional 外部來源已重新抓取並合併。"),
        entry("global_market_context", "cache", "skipped_fresh_cache", 18),
    ])
    row = acquisition()["sources"][0]
    assert row["fetch_attempts"] == 2
    assert row["nonempty_rate"] == .5
    assert row["fetched_count"] == 1
    assert row["failed_count"] == 1
    assert row["fresh_cache_count"] == 1
    assert len(row["providers"]) == 2


def test_zero_request_cooldown_is_local_block_but_real_request_remains_failure():
    from provider_acquisition import project_acquisition_events

    events = [
        {
            **entry("earnings_call", "Voltronic published conference presentation", "error"),
            "created_at": 100.0,
            "details_json": '{"error_kind":"cooldown","http_request_count":0}',
        },
        {
            **entry("earnings_call", "Voltronic published conference presentation", "error"),
            "created_at": 101.0,
            "details_json": '{"error_kind":"cooldown","event_kind":"http_attempt","http_request_sent":true,"http_request_count":1}',
        },
        {
            **entry("earnings_call", "Voltronic published conference presentation", "error"),
            "created_at": 102.0,
            "details_json": '{"error_kind":"cooldown"}',
        },
    ]

    source, = project_acquisition_events(events, window="last_24h", now=103.0)["sources"]

    assert source["local_block_count"] == 1
    assert source["failed_count"] == 2
    assert source["fetch_attempts"] == 2
    assert source["http_attempt_count"] == 1
    assert source["nonempty_rate"] == 0.0


def test_webpro_component_and_parent_result_are_not_double_counted():
    from provider_acquisition import project_acquisition_events

    events = [
        {
            **entry("earnings_call", "TWSE WebPro conference metadata", "success", 3),
            "created_at": 100.0,
            "details_json": '{"event_kind":"http_attempt","http_request_sent":true}',
        },
        {
            **entry("earnings_call", "TWSE WebPro conference metadata", "degraded_enrichment", 1,
                    "MOPS 未取得資料；WebPro 僅補回法說會日期與連結，未取得內容或逐字稿。"),
            "created_at": 101.0,
            "details_json": '{"event_kind":"aggregate","http_request_sent":true,"usable_count":3}',
        },
    ]

    source, = project_acquisition_events(events, window="last_24h", now=102.0)["sources"]
    provider, = source["providers"]

    assert source["fetch_attempts"] == provider["fetch_attempts"] == 1
    assert source["fetched_count"] == provider["fetched_count"] == 1
    assert source["aggregate_count"] == 1
    assert source["degraded_count"] == 0
    assert source["nonempty_rate"] == 1.0


def test_same_provider_result_projection_is_counted_once_per_operation():
    from provider_acquisition import project_acquisition_events

    detailed = {
        **entry("earnings_call", "Auras official conference presentation", "error"),
        "created_at": 100.0,
        "duration_ms": 10999,
        "details_json": '{"event_kind":"aggregate","fetch_id":"fetch-1",'
                        '"operation_id":"operation-1","ticker":"3324.TWO",'
                        '"http_request_sent":true,"http_request_count":3,"error_kind":"timeout"}',
    }
    repeated_projection = {
        **detailed,
        "created_at": 100.0,
        "duration_ms": 0,
        "details_json": '{"event_kind":"aggregate","fetch_id":"fetch-1",'
                        '"operation_id":"operation-1","ticker":"3324.TWO",'
                        '"http_request_count":3,"error_kind":"timeout"}',
    }
    separate_retry = {
        **detailed,
        "created_at": 101.0,
        "details_json": '{"event_kind":"aggregate","fetch_id":"fetch-1",'
                        '"operation_id":"operation-2","ticker":"3324.TWO",'
                        '"http_request_sent":true,"http_request_count":3,"error_kind":"timeout"}',
    }

    source, = project_acquisition_events(
        [detailed, repeated_projection, separate_retry], window="last_24h", now=102.0
    )["sources"]

    assert source["failed_count"] == 2
    assert source["aggregate_count"] == 1
    assert source["fetch_attempts"] == 2
    assert source["http_attempt_count"] == 2
    assert source["nonempty_rate"] == 0.0


def test_failed_provider_cannot_be_covered_by_healthy_provider():
    provider_sla.record_source_audit_entries([
        entry("recent_catalysts", "PTT Stock", "unavailable"),
        entry("recent_catalysts", "DuckDuckGo News", "success", 5),
        entry("recent_catalysts", "Free news waterfall", "success", 5),
        entry("recent_catalysts", "Recent catalysts providers", "success", 5, "optional 外部來源已重新抓取並合併。"),
    ])
    row = acquisition()["sources"][0]
    assert row["fetch_attempts"] == 2
    assert row["failed_count"] == 1
    assert row["nonempty_rate"] == .5
    assert row["providers"][0]["provider"] == "PTT Stock"


def test_window_uses_its_own_last_observation_and_no_samples_is_null(monkeypatch):
    monkeypatch.setattr(provider_sla.time, "time", lambda: 100_000.)
    provider_sla.record_source_audit_entries([entry("market_data", "yfinance", "error")])
    monkeypatch.setattr(provider_sla.time, "time", lambda: 200_000.)
    result = acquisition("last_1h")
    assert result["sources"] == []
    provider_sla.record_source_audit_entries([entry("market_data", "cache", "skipped_fresh_cache", 5)])
    row = acquisition("last_1h")["sources"][0]
    assert row["fetch_attempts"] == 0
    assert row["nonempty_rate"] is None
    assert row["failed_count"] == 0
    assert row["fresh_cache_count"] == 1


def test_stale_cache_and_unknown_evidence_never_become_fresh_success():
    provider_sla.record_source_audit_entries([
        entry("recent_catalysts", "cache", "degraded_enrichment", 8),
        entry("recent_catalysts", "new-provider", "future_status", 8),
        entry("recent_catalysts", "optional-provider", "not_configured"),
        entry("recent_catalysts", "partial-provider", "degraded_enrichment", 2),
    ])
    row = acquisition()["sources"][0]
    assert row["stale_cache_count"] == 1
    assert row["unknown_count"] == 1
    assert row["not_configured_count"] == 1
    assert row["degraded_count"] == 1
    assert row["fetched_count"] == 0
    assert row["nonempty_rate"] == 0


def test_missing_database_is_unavailable_not_healthy(monkeypatch, tmp_path):
    # Read-only projection must neither create missing databases nor claim success.
    from provider_acquisition import get_provider_acquisition_summary
    missing = tmp_path / "missing.sqlite3"
    monkeypatch.setattr(provider_sla, "TASK_DB_PATH", str(missing))
    result = get_provider_acquisition_summary("last_24h")
    assert result["available"] is False
    assert not missing.exists()


def test_unknown_provider_observations_cannot_inflate_success_rate():
    provider_sla.record_source_audit_entries([
        entry("market_data", "primary", "success", 5),
        entry("market_data", "unconfirmed", "future_status", 5),
        entry("market_data", "cache", "future_status", 5),
    ])
    row = acquisition()["sources"][0]
    assert row["unknown_count"] == 2
    assert row["fetch_attempts"] == 2
    assert row["nonempty_rate"] == .5


def test_projection_preserves_raw_history_and_legacy_compatibility():
    import sqlite3
    provider_sla.record_source_audit_entries([
        entry("earnings_call", "MOPS investor conference", "degraded_enrichment"),
    ])
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as conn:
        before = conn.execute("SELECT * FROM provider_sla_events").fetchall()
    response = TestClient(api.app).get("/api/observability/provider-sla?window=last_24h")
    payload = response.json()
    assert payload["providers"][0]["success_rate"] == 1.0
    assert payload["acquisition"]["sources"][0]["nonempty_rate"] == 0.0
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as conn:
        assert conn.execute("SELECT * FROM provider_sla_events").fetchall() == before
