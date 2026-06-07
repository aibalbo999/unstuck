import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_financial_data_shim_warns_on_fetch(monkeypatch):
    import financial_data

    monkeypatch.setattr(
        financial_data.StockDataService,
        "fetch",
        lambda self, request: SimpleNamespace(data={"ticker": request.ticker}),
    )

    with pytest.warns(DeprecationWarning):
        data = financial_data.fetch_stock_data("aapl")

    assert data["ticker"] == "AAPL"


def test_financial_data_async_shim_warns_on_fetch(monkeypatch):
    import financial_data

    async def fake_fetch_async(self, request):
        return SimpleNamespace(data={"ticker": request.ticker})

    monkeypatch.setattr(financial_data.StockDataService, "fetch_async", fake_fetch_async)

    with pytest.warns(DeprecationWarning):
        data = asyncio.run(financial_data.async_fetch_stock_data("aapl"))

    assert data["ticker"] == "AAPL"


def test_data_fetch_orchestrator_shim_warns_on_fetch(monkeypatch):
    import data_fetch.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator._assembler, "fetch_stock_data", lambda ticker, skip_optional_http=False: {"ticker": ticker})

    with pytest.warns(DeprecationWarning):
        data = orchestrator.fetch_stock_data("AAPL", skip_optional_http=True)

    assert data["ticker"] == "AAPL"


def test_payload_assembler_shim_warns_on_fetch(monkeypatch):
    import data_fetch.payload_assembler as payload_assembler

    monkeypatch.setattr(
        payload_assembler.StockDataService,
        "fetch",
        lambda self, request: SimpleNamespace(data={"ticker": request.ticker}),
    )

    with pytest.warns(DeprecationWarning):
        data = payload_assembler.fetch_stock_data("aapl", skip_optional_http=True)

    assert data["ticker"] == "AAPL"


def test_report_gen_shim_warns_on_render(monkeypatch):
    import report_gen

    monkeypatch.setattr(report_gen, "_generate_markdown_report", lambda context: "# ok")

    with pytest.warns(DeprecationWarning):
        assert report_gen.generate_markdown_report({}) == "# ok"


def test_agent_runner_shim_warns_on_legacy_function():
    import agent_runner

    with pytest.warns(DeprecationWarning):
        models = agent_runner.get_agent_model_sequence(1)

    assert models


def test_core_builder_compatibility_aggregator_exports_legacy_helpers():
    import data_fetch.core_builder as core_builder

    assert core_builder.DATA_SCHEMA_VERSION == 4
    assert callable(core_builder.fetch_stock_data)
    assert callable(core_builder._append_source_fetch_audit)


def test_yfinance_legacy_fetch_shim_warns_on_fetch(monkeypatch):
    import data_fetch.yfinance_core_fetch as core_fetch
    import data_fetch.yfinance_legacy_fetch as legacy_fetch

    monkeypatch.setattr(core_fetch, "fetch_stock_data", lambda ticker, skip_optional_http=False, market_data_provider=None: {"ticker": ticker})

    with pytest.warns(DeprecationWarning):
        data = legacy_fetch.fetch_stock_data("AAPL", skip_optional_http=True)

    assert data["ticker"] == "AAPL"


def test_market_data_fetchers_shim_warns_on_helper_call():
    import market_data_fetchers

    with pytest.warns(DeprecationWarning):
        assert market_data_fetchers.is_taiwan_ticker("2330") is True


def test_rag_service_shim_warns_on_helper_call():
    import rag_service

    with pytest.warns(DeprecationWarning):
        assert rag_service.build_chunks({}) == []
