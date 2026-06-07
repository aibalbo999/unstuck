import asyncio
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import data_fetch.yfinance_snapshot as yfinance_builder  # noqa: E402
import data_fetch.yfinance_core_fetch as core_fetch  # noqa: E402
import data_fetch.market_sources.http_enrichment as http_sources  # noqa: E402
import data_fetch.market_sources.taiwan as taiwan_sources  # noqa: E402
from data_fetch import FetchRequest  # noqa: E402
from data_fetch.enrichment_providers import YahooProvider  # noqa: E402
from data_fetch.provider_registry import ProviderRegistry  # noqa: E402
from data_fetch.quote_providers import FmpProvider, YFinanceProvider  # noqa: E402
from data_fetch.taiwan_providers import FinMindProvider, MonthlyRevenueProvider  # noqa: E402


class FakeMarketProvider:
    name = "fake-yfinance"

    def resolve_stock(self, ticker):
        return object(), {"currentPrice": 10, "longName": "Fixture"}, True, "2330.TW", [{"ticker": ticker, "valid": True}]


def test_yfinance_provider_returns_raw_snapshot(monkeypatch):
    monkeypatch.setattr(yfinance_builder, "get_market_data_provider", lambda ticker: FakeMarketProvider())

    result = asyncio.run(YFinanceProvider().fetch_async(FetchRequest.from_ticker("2330")))

    assert result.status == "success"
    assert result.value["kind"] == "yfinance_snapshot"
    assert result.value["ticker"] == "2330.TW"
    assert result.value["provider_name"] == "fake-yfinance"


def test_snapshot_payload_adapter_does_not_mutate_provider_factory(monkeypatch):
    original_factory = yfinance_builder.get_market_data_provider
    calls = {}

    def fake_fetch_stock_data(ticker, skip_optional_http=False, market_data_provider=None):
        calls["ticker"] = ticker
        calls["resolved"] = market_data_provider.resolve_stock(ticker)
        raise RuntimeError("stop after adapter")

    monkeypatch.setattr(core_fetch, "fetch_stock_data", fake_fetch_stock_data)
    snapshot = {
        "original_ticker": "2330",
        "ticker": "2330.TW",
        "resolved_ticker": "2330.TW",
        "stock": object(),
        "info": {"longName": "台積電"},
        "is_valid": True,
        "attempts": [{"ticker": "2330", "valid": True}],
        "provider_name": "fake-yfinance",
    }

    with pytest.raises(RuntimeError):
        yfinance_builder.fetch_stock_data_from_snapshot(snapshot, skip_optional_http=True)

    assert yfinance_builder.get_market_data_provider is original_factory
    assert calls["ticker"] == "2330"
    assert calls["resolved"][3] == "2330.TW"


def test_fmp_provider_fetches_quote_when_market_fields_missing(monkeypatch):
    monkeypatch.setattr(http_sources, "fetch_fmp_quote_fallback", lambda ticker: {"price": 123, "marketCap": 456})

    result = FmpProvider().fetch(
        FetchRequest.from_ticker("AAPL"),
        {"data": {"ticker": "AAPL", "current_price": "N/A", "market_cap_raw": "N/A"}},
    )

    assert result.status == "success"
    assert result.value["price"] == 123


def test_finmind_provider_fetches_financial_statement_fallback(monkeypatch):
    monkeypatch.setattr(taiwan_sources, "fetch_finmind_financial_statement_fallback", lambda ticker: {"years": ["2025"]})

    result = FinMindProvider().fetch(FetchRequest.from_ticker("2330.TW"))

    assert result.status == "success"
    assert result.value["years"] == ["2025"]


class EmptyMonthlyRevenueLoader:
    def taiwan_stock_month_revenue(self, stock_id, start_date):
        return pd.DataFrame()


def test_monthly_revenue_provider_records_unavailable_for_empty_finmind(monkeypatch):
    monkeypatch.setattr(taiwan_sources, "DataLoader", EmptyMonthlyRevenueLoader)

    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker("2330.TW"))

    assert result.status == "unavailable"
    assert result.value == []


def test_tw_only_providers_are_not_routed_for_us_tickers():
    registry = ProviderRegistry([FinMindProvider(), MonthlyRevenueProvider()])

    assert registry.provider_names(FetchRequest.from_ticker("AAPL"), source="financial_statements") == []
    assert registry.provider_names(FetchRequest.from_ticker("AAPL"), source="monthly_revenue") == []


def test_yahoo_provider_records_fetch_error(monkeypatch):
    def fail_news(stock):
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(http_sources, "fetch_yfinance_news_catalysts", fail_news)

    result = YahooProvider().fetch(FetchRequest.from_ticker("AAPL"), {"stock": object()})

    assert result.status == "error"
    assert result.audit["error_kind"] == "RuntimeError"
