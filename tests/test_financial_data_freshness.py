import asyncio
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import data_fetch.audit_helpers as audit_helpers  # noqa: E402
import data_fetch.cache_helpers as cache_helpers  # noqa: E402
import data_fetch.optional_enrichment as optional_enrichment  # noqa: E402
from data_fetch.constants import DATA_SCHEMA_VERSION  # noqa: E402
import data_fetch.yfinance_core_fetch as financial_data  # noqa: E402
import data_freshness  # noqa: E402
import data_freshness_market  # noqa: E402


def test_cached_financial_data_stales_quickly_during_market_session(monkeypatch):
    monkeypatch.setattr(data_freshness, "FINANCIAL_DATA_MARKET_CACHE_SECONDS", 60)
    monkeypatch.setattr(audit_helpers, "_is_likely_market_session", lambda ticker: True)

    cached = {
        "data_schema_version": DATA_SCHEMA_VERSION,
        "ticker": "2330.TW",
        "market_data_fetched_at_epoch": 100.0,
    }

    is_fresh, freshness = audit_helpers._assess_cached_financial_data(cached, "2330.TW", now_epoch=200.0)

    assert not is_fresh
    assert freshness["policy"] == "market_session"
    assert freshness["age_seconds"] == 100
    assert freshness["max_age_seconds"] == 60


def test_market_session_respects_us_holiday_and_early_close():
    holiday = datetime(2026, 7, 3, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    early_close_grace = datetime(2026, 11, 27, 13, 10, tzinfo=ZoneInfo("America/New_York"))
    after_grace = datetime(2026, 11, 27, 13, 30, tzinfo=ZoneInfo("America/New_York"))

    assert data_freshness_market.is_market_holiday("AAPL", holiday) is True
    assert data_freshness_market.is_likely_market_session("AAPL", holiday) is False
    assert data_freshness_market.is_likely_market_session("AAPL", early_close_grace, grace_minutes=15) is True
    assert data_freshness_market.is_likely_market_session("AAPL", after_grace, grace_minutes=15) is False


def test_market_session_respects_taiwan_holiday_calendar():
    holiday = datetime(2026, 6, 19, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    trading_time = datetime(2026, 6, 18, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))

    assert data_freshness_market.is_market_holiday("2330.TW", holiday) is True
    assert data_freshness_market.is_likely_market_session("2330.TW", holiday) is False
    assert data_freshness_market.is_likely_market_session("2330.TW", trading_time) is True


def test_cache_write_preserves_market_data_timestamp(monkeypatch):
    captured = {}

    def fake_set_cache_json(cache_key, value, ttl_seconds):
        captured[cache_key] = value

    monkeypatch.setattr(cache_helpers, "set_cache_json", fake_set_cache_json)
    monkeypatch.setattr(cache_helpers.time_module, "time", lambda: 500.0)
    monkeypatch.setattr(audit_helpers, "_is_likely_market_session", lambda ticker: False)

    cache_helpers._cache_financial_data(
        {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "market_data_fetched_at_epoch": 100.0,
            "_cache_hit": True,
        },
        "2330",
    )

    cached = captured["financial_data:2330"]
    assert cached["market_data_fetched_at_epoch"] == 100.0
    assert cached["cache_generated_at_epoch"] == 500.0
    assert cached["data_freshness"]["age_seconds"] == 400
    assert cached["source_freshness"]["market_data"]["age_seconds"] == 400


def test_fetch_stock_data_rebuilds_source_audit_on_cache_hit(monkeypatch):
    monkeypatch.setattr(financial_data.time_module, "time", lambda: 200.0)
    monkeypatch.setattr(audit_helpers, "_is_likely_market_session", lambda ticker: False)
    monkeypatch.setattr(data_freshness, "FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS", 1000)
    monkeypatch.setattr(
        financial_data,
        "get_cache_json",
        lambda key: {
            "data_schema_version": DATA_SCHEMA_VERSION,
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "years": ["2025"],
            "revenue_history": [10],
            "net_income_history": [2],
            "cache_generated_at_epoch": 100.0,
            "market_data_fetched_at_epoch": 100.0,
            "source_audit": [{"source": "old_run", "status": "success"}],
        },
    )

    data = financial_data.fetch_stock_data("2330.TW")

    assert data["_cache_hit"] is True
    assert data["source_audit"]
    assert all(entry["source"] != "old_run" for entry in data["source_audit"])
    assert data["source_audit"][0]["status"] == "skipped_fresh_cache"


def test_async_fetch_skips_fresh_optional_sources(monkeypatch):
    source_freshness = {
        "recent_catalysts": {"fetched_at_epoch": 190.0},
        "peer_discovery": {"fetched_at_epoch": 190.0},
    }

    def fake_fetch_stock_data(ticker, skip_optional_http=False):
        return {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "company_identity": {},
            "sector": "Technology",
            "industry": "Semiconductor",
            "recent_catalysts": [{"title": "Cached headline"}],
            "peer_discovery_results": [{"title": "Cached peer"}],
            "source_freshness": source_freshness,
            "_cache_hit": True,
        }

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("fresh optional source should not be refetched")

    cached_writes = []
    monkeypatch.setattr(financial_data.time_module, "time", lambda: 200.0)
    monkeypatch.setattr(financial_data, "fetch_stock_data", fake_fetch_stock_data)
    monkeypatch.setattr(optional_enrichment, "fetch_google_search_catalysts_async", fail_if_called)
    monkeypatch.setattr(optional_enrichment, "fetch_fmp_news_catalysts_async", fail_if_called)
    monkeypatch.setattr(optional_enrichment, "fetch_google_peer_discovery_results_async", fail_if_called)
    monkeypatch.setattr(cache_helpers, "set_cache_json", lambda *args: cached_writes.append(args))

    data = asyncio.run(financial_data.async_fetch_stock_data("2330"))

    assert data["recent_catalysts"][0]["title"] == "Cached headline"
    assert data["peer_discovery_results"][0]["title"] == "Cached peer"
    assert cached_writes
