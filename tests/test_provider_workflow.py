import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_fetch import CallableProvider, FetchRequest, ProviderRegistry, ProviderResult, StockDataService  # noqa: E402
from data_fetch.constants import DATA_SCHEMA_VERSION  # noqa: E402
import data_fetch.workflow as workflow  # noqa: E402
import data_freshness  # noqa: E402
import provider_sla  # noqa: E402
from data_trust import build_source_audit_entry  # noqa: E402
from fixtures.data_payloads import FRESH_AT, FRESH_AT_EPOCH, financial_history, fresh_audited_payload  # noqa: E402


def test_stock_data_service_uses_provider_plan_for_optional_enrichment(monkeypatch):
    monkeypatch.setattr(workflow, "cache_financial_payload", lambda data, ticker: None)
    monkeypatch.setattr(workflow, "get_cache_json", lambda key: None)

    def core_provider(request, context):
        return ProviderResult(
            source="market_data",
            provider="fake-core",
            status="success",
            value={
                "ticker": request.ticker,
                "company_name": "Fixture",
                "company_identity": {},
                "sector": "Technology",
                "industry": "Semiconductors",
                "current_price": 100,
                "source_audit": [],
                "source_freshness": {
                    "recent_catalysts": {"fetched_at_epoch": 100.0},
                    "peer_discovery": {"fetched_at_epoch": 100.0},
                },
            },
        )

    def google_provider(request, context):
        return ProviderResult(
            source="recent_catalysts",
            provider="Google Search",
            status="success",
            value=[{"title": "Google catalyst"}],
            audit={"source": "recent_catalysts", "provider": "Google Search", "status": "success", "record_count": 1},
        )

    def fmp_provider(request, context):
        return ProviderResult(
            source="recent_catalysts",
            provider="FMP news",
            status="success",
            value=[{"title": "FMP catalyst"}],
            audit={"source": "recent_catalysts", "provider": "FMP news", "status": "success", "record_count": 1},
        )

    def peer_provider(request, context):
        return ProviderResult(
            source="peer_discovery",
            provider="Google Search",
            status="success",
            value=[{"title": "Peer discovery"}],
            audit={"source": "peer_discovery", "provider": "Google Search", "status": "success", "record_count": 1},
        )

    registry = ProviderRegistry([
        CallableProvider("market_data", "fake-core", core_provider),
        CallableProvider("recent_catalysts", "Google Search", google_provider),
        CallableProvider("recent_catalysts", "FMP news", fmp_provider),
        CallableProvider("peer_discovery", "Google Search", peer_provider),
    ])

    result = asyncio.run(StockDataService(registry=registry).fetch_async(FetchRequest.from_ticker("AAPL")))

    assert [item["title"] for item in result.data["recent_catalysts"]] == ["Google catalyst", "FMP catalyst"]
    assert result.data["peer_discovery_results"][0]["title"] == "Peer discovery"
    assert {entry["provider"] for entry in result.data["source_audit"]} >= {"Google Search", "FMP news"}


def test_stock_data_service_fake_registry_e2e_cache_audit_and_trust(monkeypatch, tmp_path):
    calls = []
    cached_payloads = {}
    monkeypatch.setattr(data_freshness.time_module, "time", lambda: FRESH_AT_EPOCH + 60)
    monkeypatch.setattr(provider_sla, "TASK_DB_PATH", str(tmp_path / "tasks.sqlite3"))
    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    monkeypatch.setattr(workflow, "get_cache_json", lambda key: cached_payloads.get(key))

    def fake_cache_financial_payload(data, ticker):
        cached = dict(data)
        cached["cache_generated_at_epoch"] = FRESH_AT_EPOCH
        cached["market_data_fetched_at_epoch"] = FRESH_AT_EPOCH
        source_freshness = dict(cached.get("source_freshness", {}) or {})
        for source in data_freshness.CORE_CACHE_SOURCES:
            source_freshness.setdefault(source, {"fetched_at_epoch": FRESH_AT_EPOCH, "stale": False})
        cached["source_freshness"] = source_freshness
        cached_payloads[f"financial_data:{ticker}"] = cached

    monkeypatch.setattr(workflow, "cache_financial_payload", fake_cache_financial_payload)

    def market_provider(request, context):
        calls.append("market")
        payload = fresh_audited_payload(ticker=request.ticker, provider="fake-market", include_financials=False)
        return ProviderResult(
            source="market_data",
            provider="fake-market",
            status="success",
            value=payload,
            audit=payload["source_audit"][0],
        )

    def financial_provider(request, context):
        calls.append("financial")
        return ProviderResult(
            source="financial_statements",
            provider="fake-financials",
            status="success",
            value=financial_history(),
            audit=build_source_audit_entry(
                "financial_statements",
                "fake-financials",
                "success",
                fetched_at=FRESH_AT,
                record_count=2,
            ),
        )

    def catalysts_provider(request, context):
        calls.append("catalysts")
        return ProviderResult(
            source="recent_catalysts",
            provider="Google Search",
            status="success",
            value=[{"title": "Fake provider catalyst"}],
            audit=build_source_audit_entry("recent_catalysts", "Google Search", "success", fetched_at=FRESH_AT, record_count=1),
        )

    def peers_provider(request, context):
        calls.append("peers")
        return ProviderResult(
            source="peer_discovery",
            provider="Google Search",
            status="success",
            value=[{"title": "Fake peer"}],
            audit=build_source_audit_entry("peer_discovery", "Google Search", "success", fetched_at=FRESH_AT, record_count=1),
        )

    registry = ProviderRegistry([
        CallableProvider("market_data", "fake-market", market_provider),
        CallableProvider("financial_statements", "fake-financials", financial_provider),
        CallableProvider("recent_catalysts", "Google Search", catalysts_provider),
        CallableProvider("peer_discovery", "Google Search", peers_provider),
    ])
    service = StockDataService(registry=registry)

    first = asyncio.run(service.fetch_async(FetchRequest.from_ticker("FAKE")))
    second = asyncio.run(service.fetch_async(FetchRequest.from_ticker("FAKE")))

    assert first.data["data_trust"]["status"] == "fresh"
    assert {"fake-market", "fake-financials", "Google Search"} <= {entry["provider"] for entry in first.source_audit}
    assert cached_payloads["financial_data:FAKE"]["data_trust"]["status"] == "fresh"
    assert second.cache_hit is True
    assert calls == ["market", "financial", "catalysts", "peers"]
    assert {entry["status"] for entry in second.source_audit} <= {"skipped_fresh_cache"}


def test_provider_workflow_skips_fresh_optional_sources(monkeypatch):
    monkeypatch.setattr(workflow, "cache_financial_payload", lambda data, ticker: None)
    monkeypatch.setattr(workflow, "get_cache_json", lambda key: None)
    monkeypatch.setattr(data_freshness.time_module, "time", lambda: 200.0)

    def core_provider(request, context):
        return ProviderResult(
            source="market_data",
            provider="fake-core",
            status="success",
            value={
                "ticker": request.ticker,
                "company_name": "Fixture",
                "company_identity": {},
                "sector": "Technology",
                "industry": "Semiconductors",
                "recent_catalysts": [{"title": "Cached headline"}],
                "peer_discovery_results": [{"title": "Cached peer"}],
                "source_audit": [],
                "source_freshness": {
                    "recent_catalysts": {"fetched_at_epoch": 190.0},
                    "peer_discovery": {"fetched_at_epoch": 190.0},
                },
                "_cache_hit": True,
            },
        )

    def should_not_run(request, context):
        raise AssertionError("fresh optional source should not be fetched")

    registry = ProviderRegistry([
        CallableProvider("market_data", "fake-core", core_provider),
        CallableProvider("recent_catalysts", "Google Search", should_not_run),
        CallableProvider("peer_discovery", "Google Search", should_not_run),
    ])

    result = asyncio.run(StockDataService(registry=registry).fetch_async(FetchRequest.from_ticker("AAPL")))

    assert result.data["recent_catalysts"][0]["title"] == "Cached headline"
    assert result.data["peer_discovery_results"][0]["title"] == "Cached peer"
    statuses = {(entry["source"], entry["status"]) for entry in result.data["source_audit"]}
    assert ("recent_catalysts", "skipped_fresh_cache") in statuses
    assert ("peer_discovery", "skipped_fresh_cache") in statuses


def test_workflow_returns_fresh_cache_before_provider_plan(monkeypatch):
    monkeypatch.setattr(data_freshness.time_module, "time", lambda: 200.0)
    monkeypatch.setattr(
        workflow,
        "get_cache_json",
        lambda key: {
            "data_schema_version": DATA_SCHEMA_VERSION,
            "ticker": "AAPL",
            "company_name": "Fixture",
            "current_price": 100,
            "market_cap_raw": 10_000,
            "pe_ratio_raw": 20,
            "years": ["2025"],
            "revenue_history": [10],
            "net_income_history": [2],
            "cache_generated_at_epoch": 190.0,
            "market_data_fetched_at_epoch": 190.0,
        },
    )

    def should_not_run(request, context):
        raise AssertionError("fresh cache should skip provider plan")

    registry = ProviderRegistry([CallableProvider("market_data", "fake-core", should_not_run)])
    result = asyncio.run(StockDataService(registry=registry).fetch_async(FetchRequest.from_ticker("AAPL")))

    assert result.cache_hit is True
    assert result.data["ticker"] == "AAPL"
    assert result.data["source_audit"]
    assert {entry["status"] for entry in result.data["source_audit"]} <= {"skipped_fresh_cache"}


def test_workflow_refetches_when_cached_schema_is_old(monkeypatch):
    monkeypatch.setattr(workflow, "get_cache_json", lambda key: {"data_schema_version": 3, "ticker": "AAPL"})

    def core_provider(request, context):
        return ProviderResult(
            source="market_data",
            provider="fake-core",
            status="success",
            value={
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": request.ticker,
                "company_name": "Fixture",
                "source_audit": [],
            },
        )

    registry = ProviderRegistry([CallableProvider("market_data", "fake-core", core_provider)])
    result = asyncio.run(
        StockDataService(registry=registry).fetch_async(FetchRequest.from_ticker("AAPL", skip_optional_http=True))
    )

    assert result.cache_hit is False
    assert result.data["data_schema_version"] == DATA_SCHEMA_VERSION


def test_workflow_falls_back_to_stale_cache_when_core_provider_fails(monkeypatch):
    monkeypatch.setattr(data_freshness.time_module, "time", lambda: 200_000.0)
    stale_cached = {
        "data_schema_version": DATA_SCHEMA_VERSION,
        "ticker": "AAPL",
        "company_name": "Fixture",
        "current_price": 100,
        "market_cap_raw": 10_000,
        "pe_ratio_raw": 20,
        "years": ["2025"],
        "revenue_history": [10],
        "net_income_history": [2],
        "cache_generated_at_epoch": 1.0,
        "market_data_fetched_at_epoch": 1.0,
    }
    monkeypatch.setattr(workflow, "get_cache_json", lambda key: stale_cached)

    def core_provider(request, context):
        return ProviderResult(
            source="market_data",
            provider="fake-core",
            status="error",
            value={"ticker": request.ticker, "error": "provider down"},
            audit={
                "source": "market_data",
                "provider": "fake-core",
                "status": "error",
                "record_count": 0,
                "message": "provider down",
            },
        )

    registry = ProviderRegistry([CallableProvider("market_data", "fake-core", core_provider)])
    result = asyncio.run(
        StockDataService(registry=registry).fetch_async(FetchRequest.from_ticker("AAPL", skip_optional_http=True))
    )

    assert result.cache_hit is True
    assert result.data["ticker"] == "AAPL"
    assert result.data["data_trust"]["status"] == "partial"
    assert result.data["source_audit"][-1]["provider"] == "fake-core"
    assert result.data["source_audit"][-1]["status"] == "error"
