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
