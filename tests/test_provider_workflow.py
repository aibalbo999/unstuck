import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_fetch import CallableProvider, FetchRequest, ProviderRegistry, ProviderResult, StockDataService  # noqa: E402
from data_fetch.constants import DATA_SCHEMA_VERSION  # noqa: E402
from data_fetch.enrichment_merge import _merge_optional_http_bundle  # noqa: E402
from data_fetch.market_sources.peers import CompanyProfile, rank_peer_candidates, select_peer_profiles  # noqa: E402
import data_fetch.market_sources.peers as peer_sources  # noqa: E402
from data_fetch.optional_provider_plan import OPTIONAL_WORKFLOW_SOURCES  # noqa: E402
import data_fetch.workflow as workflow  # noqa: E402
import data_freshness  # noqa: E402
import provider_sla  # noqa: E402
from data_trust import build_source_audit_entry  # noqa: E402
from fixtures.data_payloads import FRESH_AT, FRESH_AT_EPOCH, financial_history, fresh_audited_payload  # noqa: E402


def test_peer_selection_filters_market_cap_outliers_and_scores_business_overlap():
    target = CompanyProfile(
        ticker="2308.TW",
        name="台達電",
        gics_code="20104010",
        market="TW",
        market_cap_twd=5_000_000_000_000,
        revenue_twd=400_000_000_000,
        business_tags={"power", "thermal", "industrial_automation"},
        product_keywords={"power_supply", "cooling"},
        segment_revenue_tags={"datacenter_power"},
    )
    micro_cap = CompanyProfile(
        "2429.TW",
        "銘旺科",
        "20104010",
        "TW",
        4_000_000_000,
        2_000_000_000,
        {"electronics"},
        {"cable"},
        set(),
    )
    global_peer = CompanyProfile(
        "ETN",
        "Eaton",
        "20104010",
        "US",
        4_500_000_000_000,
        950_000_000_000,
        {"power", "industrial_automation"},
        {"power_supply"},
        {"datacenter_power"},
    )

    ranked = rank_peer_candidates(target, [micro_cap, global_peer])

    assert [row["ticker"] for row in ranked] == ["ETN"]
    assert ranked[0]["market_cap_ratio"] == 0.9
    assert ranked[0]["score"] > 0.55


def test_peer_selection_rejects_revenue_outliers_and_unrelated_businesses():
    target = CompanyProfile(
        "2308.TW",
        "台達電",
        "20104010",
        "TW",
        5_000_000_000_000,
        400_000_000_000,
        {"power"},
        {"power_supply"},
        {"datacenter_power"},
    )
    unrelated = CompanyProfile(
        "UNRELATED",
        "Unrelated",
        "20104010",
        "US",
        5_000_000_000_000,
        400_000_000_000,
        {"aerospace"},
        {"jet_engine"},
        {"defense"},
    )
    revenue_outlier = CompanyProfile(
        "TOO-LARGE",
        "Too Large",
        "20104010",
        "US",
        5_000_000_000_000,
        4_000_000_000_000,
        {"power"},
        {"power_supply"},
        {"datacenter_power"},
    )
    relevant = CompanyProfile(
        "ETN",
        "Eaton",
        "20104010",
        "US",
        4_500_000_000_000,
        950_000_000_000,
        {"power"},
        {"power_supply"},
        {"datacenter_power"},
    )

    ranked = rank_peer_candidates(target, [unrelated, revenue_outlier, relevant])

    assert [row["ticker"] for row in ranked] == ["ETN"]


def test_select_peer_profiles_expands_globally_when_local_peers_are_insufficient():
    target = CompanyProfile(
        "2308.TW",
        "台達電",
        "20104010",
        "TW",
        5_000_000_000_000,
        400_000_000_000,
        {"power"},
        {"power_supply"},
        set(),
    )
    local_bad = CompanyProfile(
        "9999.TW",
        "微型同業",
        "20104010",
        "TW",
        1_000_000_000,
        1_000_000_000,
        {"power"},
        {"power_supply"},
        set(),
    )
    global_good = CompanyProfile(
        "ETN",
        "Eaton",
        "20104010",
        "US",
        4_500_000_000_000,
        950_000_000_000,
        {"power"},
        {"power_supply"},
        set(),
    )

    result = select_peer_profiles(target, [local_bad, global_good], min_peers=1)

    assert result["expansion_used"] is True
    assert result["selected_peers"][0]["ticker"] == "ETN"


def test_dynamic_peer_metrics_uses_ranked_profiles_and_exposes_selection_policy(monkeypatch):
    fetched_tickers = []

    class FakeTicker:
        def __init__(self, ticker):
            fetched_tickers.append(ticker)
            self.info = {
                "grossMargins": 0.38,
                "operatingMargins": 0.21,
                "profitMargins": 0.16,
                "trailingPE": 28.0,
                "priceToBook": 5.0,
            }

    monkeypatch.setattr(peer_sources.yf, "Ticker", FakeTicker)
    identity = {
        "company_profile": {
            "ticker": "2308.TW",
            "name": "台達電",
            "gics_code": "20104010",
            "market": "TW",
            "market_cap_twd": 5_000_000_000_000,
            "revenue_twd": 400_000_000_000,
            "business_tags": ["power", "thermal"],
            "product_keywords": ["power_supply"],
            "segment_revenue_tags": ["datacenter_power"],
        },
        "peer_profiles": [
            {
                "ticker": "2429.TW",
                "name": "銘旺科",
                "gics_code": "20104010",
                "market": "TW",
                "market_cap_twd": 4_000_000_000,
                "revenue_twd": 2_000_000_000,
                "business_tags": ["electronics"],
                "product_keywords": ["cable"],
                "segment_revenue_tags": [],
            },
            {
                "ticker": "ETN",
                "name": "Eaton",
                "gics_code": "20104010",
                "market": "US",
                "market_cap_twd": 4_500_000_000_000,
                "revenue_twd": 950_000_000_000,
                "business_tags": ["power", "industrial_automation"],
                "product_keywords": ["power_supply"],
                "segment_revenue_tags": ["datacenter_power"],
            },
        ],
    }

    records = peer_sources.fetch_dynamic_peer_metrics(
        "2308.TW",
        "台達電",
        "Industrials",
        "Electrical Equipment",
        identity,
    )

    assert fetched_tickers == ["ETN"]
    assert records[0]["ticker"] == "ETN"
    assert records[0]["selection_score"] > 0.55
    assert records[0]["selection_policy"]["market_cap_band"] == "0.2x-5.0x"
    assert records[0]["selection_policy"]["expansion_used"] is True


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
            value=[{"title": "Google duplicate", "link": "https://shared.example/a"}],
            audit={"source": "recent_catalysts", "provider": "Google Search", "status": "success", "record_count": 1},
        )

    def free_news_provider(request, context):
        return ProviderResult(
            source="recent_catalysts",
            provider="Free news waterfall",
            status="success",
            value=[{"title": "Free catalyst", "link": "https://shared.example/a"}],
            audit={
                "source": "recent_catalysts",
                "provider": "Free news waterfall",
                "status": "success",
                "record_count": 1,
                "related_entries": [
                    {"source": "recent_catalysts", "provider": "Google News RSS", "status": "success", "record_count": 1},
                ],
            },
        )

    def alternative_search_provider(request, context):
        return ProviderResult(
            source="recent_catalysts",
            provider="Alternative Search",
            status="success",
            value=[{"title": "Alternative catalyst"}],
            audit={"source": "recent_catalysts", "provider": "Alternative Search", "status": "success", "record_count": 1},
        )

    def fmp_provider(request, context):
        return ProviderResult(
            source="recent_catalysts",
            provider="FMP news",
            status="success",
            value=[{"title": "FMP catalyst"}],
            audit={"source": "recent_catalysts", "provider": "FMP news", "status": "success", "record_count": 1},
        )

    def yahoo_provider(request, context):
        return ProviderResult(
            source="recent_catalysts",
            provider="Yahoo Finance news",
            status="unavailable",
            value=[],
            audit={"source": "recent_catalysts", "provider": "Yahoo Finance news", "status": "unavailable", "record_count": 0},
        )

    def peer_provider(request, context):
        return ProviderResult(
            source="peer_discovery",
            provider="Google Search",
            status="success",
            value=[{"title": "Peer discovery"}],
            audit={"source": "peer_discovery", "provider": "Google Search", "status": "success", "record_count": 1},
        )

    def alternative_peer_provider(request, context):
        return ProviderResult(
            source="peer_discovery",
            provider="Alternative Search",
            status="success",
            value=[{"title": "Alternative peer"}],
            audit={"source": "peer_discovery", "provider": "Alternative Search", "status": "success", "record_count": 1},
        )

    registry = ProviderRegistry([
        CallableProvider("market_data", "fake-core", core_provider),
        CallableProvider("recent_catalysts", "Free news waterfall", free_news_provider),
        CallableProvider("recent_catalysts", "Alternative Search", alternative_search_provider),
        CallableProvider("recent_catalysts", "Google Search", google_provider),
        CallableProvider("recent_catalysts", "FMP news", fmp_provider),
        CallableProvider("recent_catalysts", "Yahoo Finance news", yahoo_provider),
        CallableProvider("peer_discovery", "Alternative Search", alternative_peer_provider),
        CallableProvider("peer_discovery", "Google Search", peer_provider),
    ])

    result = asyncio.run(StockDataService(registry=registry).fetch_async(FetchRequest.from_ticker("AAPL")))

    assert [item["title"] for item in result.data["recent_catalysts"]] == [
        "Free catalyst",
        "Alternative catalyst",
        "FMP catalyst",
    ]
    assert [item["title"] for item in result.data["peer_discovery_results"]] == [
        "Alternative peer",
        "Peer discovery",
    ]
    assert {entry["provider"] for entry in result.data["source_audit"]} >= {
        "Free news waterfall",
        "Alternative Search",
        "Google Search",
        "Google News RSS",
        "FMP news",
        "Yahoo Finance news",
    }
    latest_sources = {entry["source"]: entry for entry in result.data["source_audit"]}
    assert latest_sources["recent_catalysts"]["provider"] == "Recent catalysts providers"
    assert latest_sources["recent_catalysts"]["status"] == "success"
    assert latest_sources["recent_catalysts"]["record_count"] == 3


def test_stock_data_service_merges_global_market_and_international_news_context(monkeypatch):
    monkeypatch.setattr(workflow, "cache_financial_payload", lambda data, ticker: None)
    monkeypatch.setattr(workflow, "get_cache_json", lambda key: None)

    def core_provider(request, context):
        payload = fresh_audited_payload(ticker=request.ticker, provider="fake-core")
        payload["sector"] = "Technology"
        payload["industry"] = "Semiconductors"
        return ProviderResult(
            source="market_data",
            provider="fake-core",
            status="success",
            value=payload,
            audit=payload["source_audit"][0],
        )

    def global_market_provider(request, context):
        return ProviderResult(
            source="global_market_context",
            provider="yfinance global context",
            status="success",
            value={
                "as_of": FRESH_AT,
                "lookback_days": 5,
                "items": [
                    {
                        "symbol": "QQQ",
                        "label": "Nasdaq 100 ETF",
                        "category": "us_growth",
                        "latest": 500.0,
                        "change_1d_pct": 1.2,
                        "change_5d_pct": 3.4,
                        "source": "yfinance",
                        "fetched_at": FRESH_AT,
                    }
                ],
                "coverage_notes": [],
            },
            audit=build_source_audit_entry(
                "global_market_context",
                "yfinance global context",
                "success",
                fetched_at=FRESH_AT,
                record_count=1,
            ),
        )

    def international_news_provider(request, context):
        return ProviderResult(
            source="international_news_context",
            provider="GDELT",
            status="success",
            value={
                "lookback_days": 7,
                "topics": [
                    {
                        "tag": "semiconductors_ai",
                        "headline": "AI chip demand lifts global semiconductor supply chain",
                        "summary": "Global AI chip demand remains a cross-market driver.",
                        "published_at": FRESH_AT,
                        "source": "GDELT",
                        "url": "https://example.com/ai-chip",
                    }
                ],
                "coverage_notes": [],
            },
            audit=build_source_audit_entry(
                "international_news_context",
                "GDELT",
                "success",
                fetched_at=FRESH_AT,
                record_count=1,
            ),
        )

    registry = ProviderRegistry([
        CallableProvider("market_data", "fake-core", core_provider),
        CallableProvider("global_market_context", "yfinance global context", global_market_provider),
        CallableProvider("international_news_context", "GDELT", international_news_provider),
    ])

    result = asyncio.run(StockDataService(registry=registry).fetch_async(FetchRequest.from_ticker("2330.TW")))

    assert result.data["global_market_context"]["items"][0]["symbol"] == "QQQ"
    assert result.data["international_news_context"]["topics"][0]["tag"] == "semiconductors_ai"
    latest_sources = {entry["source"]: entry for entry in result.data["source_audit"]}
    assert latest_sources["global_market_context"]["status"] == "success"
    assert latest_sources["international_news_context"]["status"] == "success"
    assert "global_market_context" not in result.data["data_trust"]["stale_sources"]
    assert "international_news_context" not in result.data["data_trust"]["stale_sources"]
    assert not any(
        code in {
            "source_stale:global_market_context",
            "source_stale:international_news_context",
        }
        for code in result.data["data_trust"].get("reason_codes", [])
    )


def test_optional_merge_does_not_mark_empty_source_as_fresh():
    data = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "source_audit": [],
        "source_freshness": {},
    }

    result = _merge_optional_http_bundle(
        data,
        {"taiwan_open_data": {}},
        refreshed_sources=("taiwan_open_data",),
    )

    assert "taiwan_open_data" not in result.get("source_freshness", {})
    latest = {entry["source"]: entry for entry in result["source_audit"]}
    assert latest["taiwan_open_data"]["status"] == "unavailable"
    assert latest["taiwan_open_data"]["record_count"] == 0
    assert latest["taiwan_open_data"]["stale"] is True


def test_stock_data_service_auto_merges_free_context_sources(monkeypatch):
    monkeypatch.setattr(workflow, "cache_financial_payload", lambda data, ticker: None)
    monkeypatch.setattr(workflow, "get_cache_json", lambda key: None)

    def core_provider(request, context):
        payload = fresh_audited_payload(ticker=request.ticker, provider="fake-core")
        payload["sector"] = "Technology"
        payload["industry"] = "Semiconductors"
        return ProviderResult(
            source="market_data",
            provider="fake-core",
            status="success",
            value=payload,
            audit=payload["source_audit"][0],
        )

    def social_provider(request, context):
        return ProviderResult(
            source="social_sentiment",
            provider="Social Forum Sentiment (Dcard/Mobile01/PTT)",
            status="success",
            value={
                "dcard": [{"title": "Dcard 討論熱度升溫", "link": "https://example.test/dcard"}],
                "mobile01": [],
                "pttweb": [{"title": "PTT 討論供應鏈", "link": "https://example.test/ptt"}],
            },
            audit=build_source_audit_entry(
                "social_sentiment",
                "Social Forum Sentiment (Dcard/Mobile01/PTT)",
                "success",
                fetched_at=FRESH_AT,
                record_count=2,
            ),
        )

    def sec_provider(request, context):
        return ProviderResult(
            source="sec_edgar",
            provider="SEC EDGAR Filings",
            status="success",
            value={
                "cik": "0000320193",
                "company_name": "Apple Inc.",
                "recent_filings": [{"form": "10-Q", "filingDate": "2026-05-01"}],
            },
            audit=build_source_audit_entry(
                "sec_edgar",
                "SEC EDGAR Filings",
                "success",
                fetched_at=FRESH_AT,
                record_count=1,
            ),
        )

    def taiwan_open_data_provider(request, context):
        return ProviderResult(
            source="taiwan_open_data",
            provider="Taiwan Open Data (Exchange Rates)",
            status="success",
            value={
                "dataset": "Bank of Taiwan Exchange Rates (牌告匯率)",
                "rates": {"USD": {"buy": "31.00", "sell": "31.50"}},
            },
            audit=build_source_audit_entry(
                "taiwan_open_data",
                "Taiwan Open Data (Exchange Rates)",
                "success",
                fetched_at=FRESH_AT,
                record_count=1,
            ),
        )

    registry = ProviderRegistry([
        CallableProvider("market_data", "fake-core", core_provider),
        CallableProvider("social_sentiment", "Social Forum Sentiment (Dcard/Mobile01/PTT)", social_provider),
        CallableProvider("sec_edgar", "SEC EDGAR Filings", sec_provider, markets={"us"}),
        CallableProvider("taiwan_open_data", "Taiwan Open Data (Exchange Rates)", taiwan_open_data_provider),
    ])

    result = asyncio.run(StockDataService(registry=registry).fetch_async(FetchRequest.from_ticker("AAPL")))

    assert result.data["social_sentiment"]["dcard"][0]["title"] == "Dcard 討論熱度升溫"
    assert result.data["sentiment_context"]["social_sentiment"]["pttweb"][0]["title"] == "PTT 討論供應鏈"
    assert result.data["sec_edgar"]["recent_filings"][0]["form"] == "10-Q"
    assert result.data["taiwan_open_data"]["rates"]["USD"]["sell"] == "31.50"
    latest_sources = {entry["source"]: entry for entry in result.data["source_audit"]}
    assert latest_sources["social_sentiment"]["status"] == "success"
    assert latest_sources["sec_edgar"]["status"] == "success"
    assert latest_sources["taiwan_open_data"]["status"] == "success"
    assert "social_sentiment" in result.data["source_freshness"]
    assert "sec_edgar" in result.data["source_freshness"]
    assert "taiwan_open_data" in result.data["source_freshness"]


def test_default_provider_registry_includes_global_context_sources():
    sources = {provider.source for provider in ProviderRegistry().providers}

    assert "global_market_context" in sources
    assert "international_news_context" in sources


def test_mops_earnings_call_provider_only_runs_for_taiwan_tickers():
    registry = ProviderRegistry()

    us_names = registry.provider_names(FetchRequest.from_ticker("AAPL"), source="earnings_call")
    tw_names = registry.provider_names(FetchRequest.from_ticker("2330.TW"), source="earnings_call")

    assert "MOPS investor conference" not in us_names
    assert "MOPS investor conference" in tw_names


def test_default_provider_registry_sources_are_covered_by_automatic_workflow():
    registry_sources = {provider.source for provider in ProviderRegistry().providers}
    core_workflow_sources = {
        "market_data",
        "financial_statements",
        "twse_official",
        "monthly_revenue",
        "institutional_trading",
        "dynamic_peer_metrics",
        "pe_river_chart",
    }
    automated_sources = core_workflow_sources | set(OPTIONAL_WORKFLOW_SOURCES)

    assert registry_sources - automated_sources == set()


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
    latest_cache_audit = {entry["source"]: entry for entry in second.source_audit}
    assert latest_cache_audit["market_data"]["status"] == "skipped_fresh_cache"
    assert latest_cache_audit["financial_statements"]["status"] == "skipped_fresh_cache"
    assert latest_cache_audit["recent_catalysts"]["status"] == "skipped_fresh_cache"
    assert latest_cache_audit["peer_discovery"]["status"] == "skipped_fresh_cache"
    assert latest_cache_audit["earnings_call"]["status"] == "unavailable"
    assert latest_cache_audit["earnings_call"]["record_count"] == 0


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


def test_workflow_falls_back_from_yfinance_to_fmp_after_blocking(monkeypatch):
    monkeypatch.setattr(workflow, "cache_financial_payload", lambda data, ticker: None)
    monkeypatch.setattr(workflow, "get_cache_json", lambda key: None)
    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])

    def yfinance_provider(request, context):
        return ProviderResult(
            source="market_data",
            provider="yfinance",
            status="error",
            value={"ticker": request.ticker, "error": "timeout"},
            audit=build_source_audit_entry(
                "market_data",
                "yfinance",
                "error",
                record_count=0,
                error_kind="TimeoutError",
                message="yfinance timeout and HTTP 403 blocked",
            ),
        )

    def fmp_provider(request, context):
        audit = build_source_audit_entry(
            "market_data",
            "FMP stable quote",
            "success",
            record_count=3,
        )
        return ProviderResult(
            source="market_data",
            provider="FMP stable quote",
            status="success",
            value={
                "ticker": request.ticker,
                "company_name": "Fallback Fixture",
                "current_price": 123.0,
                "market_cap_raw": 1000,
                "pe_ratio_raw": 12.5,
                "source_audit": [audit],
            },
            audit=audit,
        )

    fmp = CallableProvider("market_data", "FMP stable quote", fmp_provider)
    fmp.primary_source_provider = False
    registry = ProviderRegistry([
        CallableProvider("market_data", "yfinance", yfinance_provider),
        fmp,
    ])

    result = asyncio.run(
        StockDataService(registry=registry).fetch_async(FetchRequest.from_ticker("AAPL", skip_optional_http=True))
    )

    assert result.data["company_name"] == "Fallback Fixture"
    assert result.data["current_price"] == 123.0
    statuses = {(entry["provider"], entry["status"]) for entry in result.data["source_audit"]}
    assert ("yfinance", "error") in statuses
    assert ("FMP stable quote", "success") in statuses


def test_workflow_falls_back_from_invalid_yfinance_snapshot_to_fmp(monkeypatch):
    monkeypatch.setattr(workflow, "cache_financial_payload", lambda data, ticker: None)
    monkeypatch.setattr(workflow, "get_cache_json", lambda key: None)
    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    fmp_calls = []

    def yfinance_provider(request, context):
        return ProviderResult(
            source="market_data",
            provider="yfinance",
            status="success",
            value={
                "kind": "yfinance_snapshot",
                "original_ticker": request.ticker,
                "ticker": request.ticker,
                "resolved_ticker": request.ticker,
                "is_valid": False,
                "info": {},
                "stock": None,
                "attempts": [{"ticker": request.ticker, "valid": False}],
                "provider_name": "yfinance",
            },
            audit=build_source_audit_entry(
                "market_data",
                "yfinance",
                "success",
                record_count=0,
                message="yfinance snapshot returned no valid ticker.",
            ),
        )

    def fmp_provider(request, context):
        fmp_calls.append(request.ticker)
        audit = build_source_audit_entry(
            "market_data",
            "FMP stable quote",
            "success",
            record_count=3,
        )
        return ProviderResult(
            source="market_data",
            provider="FMP stable quote",
            status="success",
            value={
                "ticker": request.ticker,
                "company_name": "Fallback Fixture",
                "current_price": 123.0,
                "market_cap_raw": 1000,
                "pe_ratio_raw": 12.5,
                "source_audit": [audit],
            },
            audit=audit,
        )

    fmp = CallableProvider("market_data", "FMP stable quote", fmp_provider)
    fmp.primary_source_provider = False
    registry = ProviderRegistry([
        CallableProvider("market_data", "yfinance", yfinance_provider),
        fmp,
    ])

    result = asyncio.run(
        StockDataService(registry=registry).fetch_async(FetchRequest.from_ticker("9999.TW", skip_optional_http=True))
    )

    assert fmp_calls == ["9999.TW"]
    assert result.data["company_name"] == "Fallback Fixture"
    statuses = {(entry["provider"], entry["status"]) for entry in result.data["source_audit"]}
    assert ("yfinance", "success") in statuses
    assert ("FMP stable quote", "success") in statuses


def test_fetch_stock_data_from_invalid_yfinance_snapshot_returns_clean_error():
    from data_fetch.yfinance_snapshot import fetch_stock_data_from_snapshot

    payload = fetch_stock_data_from_snapshot(
        {
            "kind": "yfinance_snapshot",
            "original_ticker": "9999.TW",
            "ticker": "9999.TW",
            "resolved_ticker": "9999.TW",
            "is_valid": False,
            "info": {},
            "stock": None,
            "attempts": [{"ticker": "9999.TW", "valid": False}, {"ticker": "9999.TWO", "valid": False}],
            "provider_name": "taiwan_yfinance_finmind",
        },
        skip_optional_http=True,
    )

    assert payload["error"] == "yfinance 無法驗證股票代號：9999.TW"
    assert payload["data_trust"]["status"] == "error"
    audit = payload["source_audit"][0]
    assert audit["source"] == "market_data"
    assert audit["status"] == "error"
    assert audit["error_kind"] == "InvalidTickerError"


def test_yfinance_timeout_403_audits_surface_provider_sla_alert(monkeypatch, tmp_path):
    monkeypatch.setattr(provider_sla, "TASK_DB_PATH", str(tmp_path / "provider-sla.sqlite3"))

    provider_sla.record_source_audit_entries([
        {
            "source": "market_data",
            "provider": "yfinance",
            "status": "error",
            "duration_ms": 1000,
            "record_count": 0,
            "message": "TimeoutError: HTTP 403 blocked",
        }
        for _ in range(3)
    ])

    alerts = provider_sla.get_provider_sla_alerts()
    yfinance = next(item for item in alerts if item["provider"] == "yfinance")

    assert yfinance["alert_level"] == "critical"
    assert yfinance["attempts"] == 3
    assert yfinance["success_rate"] == 0.0
