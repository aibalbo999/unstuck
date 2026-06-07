import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from agent_runtime import AgentExecutor, AgentRunRequest  # noqa: E402
from data_fetch import FetchRequest, StockDataService  # noqa: E402
from data_fetch.providers import (  # noqa: E402
    CallableProvider,
    FinMindProvider,
    FmpProvider,
    InstitutionalTradingProvider,
    MonthlyRevenueProvider,
    PeRiverChartProvider,
    ProviderRegistry,
    infer_market,
)
from reporting import ReportRenderer, ReportRequest  # noqa: E402


def test_stock_data_service_returns_typed_fetch_result_from_fake_provider():
    async def fake_fetcher(request):
        return {
            "ticker": request.ticker,
            "company_name": "Fixture",
            "source_audit": [
                {
                    "source": "market_data",
                    "provider": "fake",
                    "status": "success",
                    "duration_ms": 3,
                    "record_count": 1,
                }
            ],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        }

    result = asyncio.run(StockDataService(fetcher=fake_fetcher).fetch_async(FetchRequest.from_ticker("aapl")))

    assert result.request.ticker == "AAPL"
    assert result.data["ticker"] == "AAPL"
    assert result.provider_results[0].provider == "fake"
    assert result.provider_results[0].status == "success"


def test_provider_registry_routes_by_market():
    provider = CallableProvider(
        source="monthly_revenue",
        name="tw-only",
        markets={"tw"},
        callback=lambda request: None,
    )
    registry = ProviderRegistry([provider])

    assert infer_market("2330.TW") == "tw"
    assert registry.provider_names(FetchRequest.from_ticker("2330.TW")) == ["tw-only"]
    assert registry.provider_names(FetchRequest.from_ticker("AAPL")) == []


def test_default_core_provider_registry_exposes_expected_source_routes():
    registry = ProviderRegistry([
        FinMindProvider(),
        FmpProvider(),
        MonthlyRevenueProvider(),
        InstitutionalTradingProvider(),
        PeRiverChartProvider(),
    ])
    tw_request = FetchRequest.from_ticker("2330.TW")
    us_request = FetchRequest.from_ticker("AAPL")

    assert registry.provider_names(tw_request, source="financial_statements") == ["FinMind"]
    assert registry.provider_names(tw_request, source="monthly_revenue") == ["FinMind TaiwanStockMonthRevenue"]
    assert registry.provider_names(tw_request, source="institutional_trading") == ["FinMind"]
    assert registry.provider_names(tw_request, source="pe_river_chart") == ["FinMind/default multiples"]
    assert registry.provider_names(us_request, source="monthly_revenue") == []
    assert registry.provider_names(us_request, source="institutional_trading") == []
    assert registry.provider_names(us_request, source="market_data") == ["FMP stable quote"]
    assert registry.first_provider(us_request, source="market_data") is None


def test_agent_executor_uses_split_runtime(monkeypatch):
    import agent_runtime.executor as executor_module

    async def fake_run_single_agent_async(agent_num, data, context, rotator, max_retries=3):
        context.setdefault("structured_outputs", {})[agent_num] = {"ok": True}
        return "## Agent Output\n" + ("content " * 30)

    monkeypatch.setattr(executor_module, "run_single_agent_async", fake_run_single_agent_async)
    monkeypatch.setattr(executor_module, "get_runtime_model_sequence", lambda agent_num, context: ["fake-model"])

    context = {"structured_outputs": {}}
    result = asyncio.run(
        AgentExecutor().run_async(
            AgentRunRequest(
                agent_num=7,
                data={"ticker": "AAPL", "company_name": "Apple"},
                context=context,
                rotator=object(),
            )
        )
    )

    assert result.agent_num == 7
    assert result.model_id == "fake-model"
    assert result.structured_output == {"ok": True}
    assert result.duration_ms >= 0


def test_report_renderer_returns_bundle_with_snapshot(monkeypatch):
    import reporting.renderer as renderer_module

    async def fake_html(context):
        return "<html>ok</html>"

    monkeypatch.setattr(renderer_module, "generate_html_report_async", fake_html)
    monkeypatch.setattr(renderer_module, "generate_markdown_report", lambda context: "# ok")

    context = {
        "ticker": "AAPL",
        "company_name": "Apple",
        "pipeline_id": "v1",
        "data": {
            "ticker": "AAPL",
            "company_name": "Apple",
            "data_schema_version": 4,
            "source_audit": [],
            "data_trust": {"status": "unknown", "critical_failures": [], "stale_sources": [], "notes": []},
        },
    }
    bundle = asyncio.run(ReportRenderer().render_async(ReportRequest(context=context, pipeline_id="v1", filename="a.html")))

    assert bundle.html == "<html>ok</html>"
    assert bundle.markdown == "# ok"
    assert bundle.data_snapshot["ticker"] == "AAPL"
    assert bundle.metadata["filename"] == "a.html"
