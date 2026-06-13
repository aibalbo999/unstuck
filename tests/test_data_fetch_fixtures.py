import asyncio
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import data_fetch.cache_helpers as cache_helpers  # noqa: E402
import data_fetch.market_sources.global_context as global_context  # noqa: E402
import data_fetch.optional_enrichment as optional_enrichment  # noqa: E402
import data_fetch.yfinance_payload as yfinance_payload  # noqa: E402
import data_fetch.yfinance_sync_enrichment as sync_enrichment  # noqa: E402
import data_fetch.yfinance_core_fetch as financial_data  # noqa: E402
import external_data_gdelt  # noqa: E402
import external_data_parsers  # noqa: E402


class FakeStock:
    def __init__(self):
        cols = pd.to_datetime(["2025-12-31", "2024-12-31"])
        self.financials = pd.DataFrame(
            {
                cols[0]: {
                    "Total Revenue": 1_200_000_000,
                    "Net Income": 240_000_000,
                    "Gross Profit": 600_000_000,
                    "Operating Income": 360_000_000,
                },
                cols[1]: {
                    "Total Revenue": 1_000_000_000,
                    "Net Income": 200_000_000,
                    "Gross Profit": 500_000_000,
                    "Operating Income": 300_000_000,
                },
            }
        )
        self.cashflow = pd.DataFrame(
            {
                cols[0]: {"Operating Cash Flow": 300_000_000, "Capital Expenditure": -80_000_000},
                cols[1]: {"Operating Cash Flow": 260_000_000, "Capital Expenditure": -60_000_000},
            }
        )
        self.balance_sheet = pd.DataFrame(
            {
                cols[0]: {"Total Assets": 2_000_000_000, "Stockholders Equity": 1_000_000_000},
                cols[1]: {"Total Assets": 1_800_000_000, "Stockholders Equity": 900_000_000},
            }
        )

    def history(self, period="1y"):
        return pd.DataFrame(
            {"Close": [95.0, 100.0]},
            index=pd.to_datetime(["2025-01-31", "2025-02-28"]),
        )


class FakeProvider:
    name = "fake-yfinance"

    def __init__(self, resolved_ticker: str, country: str = "Taiwan"):
        self.resolved_ticker = resolved_ticker
        self.country = country

    def resolve_stock(self, ticker: str):
        info = {
            "longName": "Fixture Corp",
            "shortName": "Fixture",
            "sector": "Technology",
            "industry": "Semiconductors",
            "country": self.country,
            "currentPrice": 100.0,
            "marketCap": 10_000_000_000,
            "fiftyTwoWeekHigh": 120.0,
            "fiftyTwoWeekLow": 80.0,
            "averageVolume": 1_000_000,
            "trailingPE": 20.0,
            "forwardPE": 18.0,
            "priceToBook": 4.0,
            "priceToSalesTrailing12Months": 5.0,
            "enterpriseToEbitda": 12.0,
            "enterpriseValue": 11_000_000_000,
            "sharesOutstanding": 100_000_000,
            "forwardEps": 5.5,
            "trailingEps": 5.0,
            "totalRevenue": 1_250_000_000,
            "grossMargins": 0.5,
            "operatingMargins": 0.3,
            "profitMargins": 0.2,
            "ebitda": 400_000_000,
            "freeCashflow": 220_000_000,
            "operatingCashflow": 300_000_000,
            "totalDebt": 100_000_000,
            "totalCash": 200_000_000,
            "debtToEquity": 10.0,
            "currentRatio": 2.0,
            "returnOnEquity": 0.2,
            "returnOnAssets": 0.1,
            "dividendYield": 0.02,
            "dividendRate": 2.0,
            "payoutRatio": 0.4,
            "revenueGrowth": 0.1,
            "earningsGrowth": 0.12,
            "earningsQuarterlyGrowth": 0.11,
            "beta": 1.0,
            "targetMeanPrice": 115.0,
            "recommendationKey": "hold",
            "numberOfAnalystOpinions": 3,
        }
        return FakeStock(), info, True, self.resolved_ticker, [{"ticker": ticker, "valid": True}]


class EmptyMonthlyRevenueLoader:
    def taiwan_stock_month_revenue(self, stock_id: str, start_date: str):
        return pd.DataFrame()


class ExplodingLoader:
    def __init__(self):
        raise AssertionError("US stocks should not request FinMind monthly revenue")


class FakeMarketProxy:
    def __init__(self, closes):
        self._closes = closes

    def history(self, period="5d"):
        return pd.DataFrame(
            {"Close": self._closes},
            index=pd.to_datetime(["2026-06-08", "2026-06-09", "2026-06-10"]),
        )


def test_global_market_context_summarizes_market_proxy_history(monkeypatch):
    monkeypatch.setattr(global_context.yf, "Ticker", lambda symbol: FakeMarketProxy([100.0, 104.0, 110.0]))

    context = global_context.fetch_global_market_context(
        "2330.TW",
        "Taiwan Semiconductor",
        "Technology",
        "Semiconductors",
        symbols=[("QQQ", "Nasdaq 100 ETF", "us_growth")],
    )

    assert context["lookback_days"] == 5
    assert context["items"][0]["symbol"] == "QQQ"
    assert context["items"][0]["latest"] == 110.0
    assert context["items"][0]["change_1d_pct"] == 5.7692
    assert context["items"][0]["change_5d_pct"] == 10.0
    assert context["items"][0]["source"] == "yfinance"


def test_global_market_context_includes_no_key_macro_commodity_and_regional_sources(monkeypatch):
    monkeypatch.setattr(global_context.yf, "Ticker", lambda symbol: FakeMarketProxy([100.0, 104.0, 110.0]))

    context = global_context.fetch_global_market_context(
        "2330.TW",
        "Taiwan Semiconductor",
        "Technology",
        "Semiconductors",
    )
    by_symbol = {item["symbol"]: item for item in context["items"]}

    assert {"^TNX", "DX-Y.NYB", "CL=F", "GC=F", "^TWII", "EWT", "EWJ", "EWY"}.issubset(by_symbol)
    assert by_symbol["^TNX"]["category"] == "rates"
    assert by_symbol["DX-Y.NYB"]["category"] == "fx"
    assert by_symbol["CL=F"]["category"] == "commodity_energy"
    assert by_symbol["GC=F"]["category"] == "commodity_safe_haven"
    assert by_symbol["^TWII"]["category"] == "regional_taiwan"


def test_gdelt_article_payload_parses_international_news_topics():
    payload = {
        "articles": [
            {
                "title": "US chip policy reshapes AI server supply chain",
                "seendate": "20260612T010203Z",
                "sourcecountry": "United States",
                "domain": "example.com",
                "url": "https://example.com/story",
                "socialimage": "https://example.com/image.jpg",
            },
            {"title": "", "url": "https://example.com/empty"},
        ]
    }

    records = external_data_parsers.parse_gdelt_article_payload(payload, tag="semiconductors_ai")

    assert records == [{
        "tag": "semiconductors_ai",
        "headline": "US chip policy reshapes AI server supply chain",
        "summary": "example.com · United States",
        "published_at": "20260612T010203Z",
        "source": "GDELT",
        "url": "https://example.com/story",
    }]


def test_google_news_rss_payload_parses_international_news_topics():
    payload = """<?xml version="1.0" encoding="UTF-8"?>
    <rss><channel>
      <item>
        <title>AI chip supply chain expands - Reuters</title>
        <link>https://news.google.com/rss/articles/example</link>
        <pubDate>Fri, 12 Jun 2026 01:02:03 GMT</pubDate>
        <source url="https://www.reuters.com">Reuters</source>
      </item>
      <item><title></title><link>https://example.com/empty</link></item>
    </channel></rss>
    """

    records = external_data_parsers.parse_google_news_rss_payload(payload, tag="semiconductors_ai")

    assert records == [{
        "tag": "semiconductors_ai",
        "headline": "AI chip supply chain expands - Reuters",
        "summary": "Reuters",
        "published_at": "Fri, 12 Jun 2026 01:02:03 GMT",
        "source": "Google News RSS",
        "url": "https://news.google.com/rss/articles/example",
    }]


def test_gdelt_context_limits_topic_requests_and_spaces_calls(monkeypatch):
    class FakeAsyncClient:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    calls = []
    sleeps = []

    async def fake_json_get(_client, _url, params):
        calls.append(params["query"])
        return {
            "articles": [{
                "title": f"Story for {params['query']}",
                "seendate": "20260612T010203Z",
                "sourcecountry": "United States",
                "domain": "example.com",
                "url": f"https://example.com/{len(calls)}",
            }]
        }

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(external_data_gdelt, "async_client", lambda: FakeAsyncClient())
    monkeypatch.setattr(external_data_gdelt, "async_json_get", fake_json_get)
    monkeypatch.setattr(external_data_gdelt.asyncio, "sleep", fake_sleep)

    context = asyncio.run(external_data_gdelt.fetch_gdelt_international_news_context(
        "Technology",
        "Semiconductors",
        max_topics=2,
        request_spacing_seconds=5.0,
    ))

    assert len(calls) == 2
    assert sleeps == [5.0]
    assert len(context["topics"]) == 2


def test_gdelt_context_falls_back_to_google_news_rss(monkeypatch):
    rss_payload = """<?xml version="1.0" encoding="UTF-8"?>
    <rss><channel><item>
      <title>AI chip policy reshapes supply chain - Reuters</title>
      <link>https://news.google.com/rss/articles/fallback</link>
      <pubDate>Fri, 12 Jun 2026 01:02:03 GMT</pubDate>
      <source>Reuters</source>
    </item></channel></rss>
    """

    class FakeResponse:
        text = rss_payload

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, _url, params):
            assert params["q"]
            return FakeResponse()

    async def failing_json_get(_client, _url, _params):
        raise RuntimeError("gdelt unavailable")

    monkeypatch.setattr(external_data_gdelt, "async_client", lambda: FakeAsyncClient())
    monkeypatch.setattr(external_data_gdelt, "async_json_get", failing_json_get)

    context = asyncio.run(external_data_gdelt.fetch_gdelt_international_news_context(
        "Technology",
        "Semiconductors",
        max_topics=1,
        request_spacing_seconds=0,
    ))

    assert context["topics"][0]["source"] == "Google News RSS"
    assert context["topics"][0]["headline"] == "AI chip policy reshapes supply chain - Reuters"


def _patch_common_fetch_dependencies(monkeypatch, resolved_ticker="2330.TW", country="Taiwan"):
    monkeypatch.setattr(financial_data, "get_cache_json", lambda key: None)
    monkeypatch.setattr(financial_data, "set_cache_json", lambda *args: None)
    monkeypatch.setattr(yfinance_payload, "set_cache_json", lambda *args: None)
    monkeypatch.setattr(cache_helpers, "set_cache_json", lambda *args: None)
    monkeypatch.setattr(financial_data, "_is_likely_market_session", lambda ticker: False)
    monkeypatch.setattr(financial_data.time_module, "time", lambda: 1_780_800_000.0)
    monkeypatch.setattr(
        financial_data,
        "get_market_data_provider",
        lambda ticker: FakeProvider(resolved_ticker=resolved_ticker, country=country),
    )
    monkeypatch.setattr(financial_data, "fetch_recent_catalysts", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync_enrichment, "fetch_finmind_news_catalysts", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync_enrichment, "fetch_yfinance_news_catalysts", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync_enrichment, "fetch_google_search_catalysts", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync_enrichment, "fetch_fmp_news_catalysts", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync_enrichment, "fetch_institutional_trading_trend", lambda *args, **kwargs: {})
    monkeypatch.setattr(sync_enrichment, "fetch_dynamic_peer_metrics", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync_enrichment, "fetch_google_peer_discovery_results", lambda *args, **kwargs: [])
    monkeypatch.setattr(financial_data, "fetch_fmp_quote_fallback", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        financial_data,
        "fetch_finmind_financial_statement_fallback",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        sync_enrichment,
        "build_pe_river_chart_data",
        lambda *args, **kwargs: {"years": ["2024", "2025"], "eps_twd": [2, 3], "bands": {"15": [30, 45]}},
    )


def test_taiwan_fixture_records_unavailable_finmind_monthly_revenue(monkeypatch):
    _patch_common_fetch_dependencies(monkeypatch, resolved_ticker="2330.TW", country="Taiwan")
    monkeypatch.setattr(financial_data, "DataLoader", EmptyMonthlyRevenueLoader)

    data = financial_data.fetch_stock_data("2330.TW", skip_optional_http=True)

    monthly_entries = [
        entry for entry in data["source_audit"]
        if entry["source"] == "monthly_revenue" and entry["provider"] == "FinMind TaiwanStockMonthRevenue"
    ]
    assert monthly_entries
    assert monthly_entries[-1]["status"] == "unavailable"
    assert data["recent_monthly_revenue"] == []


def test_us_fixture_has_no_monthly_revenue_without_finmind_call(monkeypatch):
    _patch_common_fetch_dependencies(monkeypatch, resolved_ticker="AAPL", country="United States")
    monkeypatch.setattr(financial_data, "DataLoader", ExplodingLoader)

    data = financial_data.fetch_stock_data("AAPL", skip_optional_http=True)

    monthly_entries = [entry for entry in data["source_audit"] if entry["source"] == "monthly_revenue"]
    assert data["recent_monthly_revenue"] == []
    assert monthly_entries
    assert monthly_entries[-1]["status"] == "unavailable"


def test_async_fixture_records_google_and_fmp_failures(monkeypatch):
    def fake_fetch_stock_data(ticker, skip_optional_http=False):
        return {
            "data_schema_version": financial_data.DATA_SCHEMA_VERSION,
            "ticker": "2330.TW",
            "company_name": "Fixture Corp",
            "company_identity": {},
            "sector": "Technology",
            "industry": "Semiconductors",
            "current_price": 100,
            "years": ["2025"],
            "revenue_history": [10],
            "net_income_history": [2],
            "source_audit": [],
            "source_freshness": {
                "recent_catalysts": {"fetched_at_epoch": 1_780_700_000.0, "stale": True},
                "peer_discovery": {"fetched_at_epoch": 1_780_700_000.0, "stale": True},
            },
        }

    async def fail_google(*args, **kwargs):
        raise RuntimeError("google down")

    async def fail_fmp(*args, **kwargs):
        raise RuntimeError("fmp down")

    monkeypatch.setattr(financial_data, "fetch_stock_data", fake_fetch_stock_data)
    monkeypatch.setattr(optional_enrichment, "fetch_google_search_catalysts_async", fail_google)
    monkeypatch.setattr(optional_enrichment, "fetch_fmp_news_catalysts_async", fail_fmp)
    monkeypatch.setattr(optional_enrichment, "fetch_google_peer_discovery_results_async", fail_google)
    monkeypatch.setattr(cache_helpers, "set_cache_json", lambda *args: None)
    monkeypatch.setattr(financial_data.time_module, "time", lambda: 1_780_800_200.0)

    data = asyncio.run(financial_data.async_fetch_stock_data("2330"))

    errors = [
        entry for entry in data["source_audit"]
        if entry["status"] == "error" and entry["provider"] in {"Google Search", "FMP news"}
    ]
    assert {entry["provider"] for entry in errors} == {"Google Search", "FMP news"}
    assert data["data_trust"]["status"] == "partial"
