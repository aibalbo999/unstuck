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
from data_fetch.enrichment_providers import EarningsCallProvider, YahooProvider  # noqa: E402
from data_fetch.provider_registry import ProviderRegistry  # noqa: E402
from data_fetch.quote_providers import FmpProvider, YFinanceProvider  # noqa: E402
from data_fetch.taiwan_providers import FinMindProvider, MonthlyRevenueProvider, TwseOfficialProvider  # noqa: E402


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


def test_twse_official_provider_fetches_cross_validation_payload(monkeypatch):
    import external_data_twse

    payload = {
        "revenue_ttm_raw": 4_600.0,
        "net_income_ttm_raw": 460.0,
        "free_cash_flow_raw": 400.0,
        "gross_margin_raw": 0.4,
        "operating_margin_raw": 0.2,
        "profit_margin_raw": 0.1,
        "total_debt_raw": 700.0,
        "source": "FinMind_TWSE",
        "fetch_date": "2026-06-19",
    }
    monkeypatch.setattr(external_data_twse, "fetch_twse_official_data", lambda ticker: payload)

    result = TwseOfficialProvider().fetch(FetchRequest.from_ticker("2330.TW"))

    assert result.status == "success"
    assert result.source == "twse_official"
    assert result.value["source"] == "FinMind_TWSE"


class EmptyMonthlyRevenueLoader:
    def taiwan_stock_month_revenue(self, stock_id, start_date):
        return pd.DataFrame()


def test_monthly_revenue_provider_records_unavailable_for_empty_finmind(monkeypatch):
    monkeypatch.setattr(taiwan_sources, "DataLoader", EmptyMonthlyRevenueLoader)

    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker("2330.TW"))

    assert result.status == "unavailable"
    assert result.value == []


def test_tw_only_providers_are_not_routed_for_us_tickers():
    registry = ProviderRegistry([FinMindProvider(), MonthlyRevenueProvider(), TwseOfficialProvider()])

    assert registry.provider_names(FetchRequest.from_ticker("AAPL"), source="financial_statements") == []
    assert registry.provider_names(FetchRequest.from_ticker("AAPL"), source="monthly_revenue") == []
    assert registry.provider_names(FetchRequest.from_ticker("AAPL"), source="twse_official") == []


def test_yahoo_provider_records_fetch_error(monkeypatch):
    def fail_news(stock):
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(http_sources, "fetch_yfinance_news_catalysts", fail_news)

    result = YahooProvider().fetch(FetchRequest.from_ticker("AAPL"), {"stock": object()})

    assert result.status == "error"
    assert result.audit["error_kind"] == "RuntimeError"


def test_earnings_call_provider_uses_free_mops_source_without_fmp_key(monkeypatch):
    import data_fetch.enrichment_providers as providers

    def fake_mops(ticker):
        assert ticker == "2330.TW"
        return {
            "ticker": "2330",
            "date": "2026-06-20",
            "period": "2026-06-20",
            "title": "台積電 法人說明會",
            "summary": "第一季營運成果",
            "transcript_excerpt": "",
            "transcript_available": False,
            "materials": [{"label": "簡報檔案", "url": "https://example.test/2330.pdf"}],
            "source": "MOPS investor conference",
        }

    monkeypatch.setattr(providers, "fetch_free_earnings_call_context", fake_mops, raising=False)

    result = EarningsCallProvider().fetch(FetchRequest.from_ticker("2330.TW"))

    assert result.status == "success"
    assert result.provider == "MOPS investor conference"
    assert result.value["transcript_available"] is False
    assert result.value["materials"][0]["label"] == "簡報檔案"
