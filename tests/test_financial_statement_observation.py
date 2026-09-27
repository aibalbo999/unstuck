"""Observe existing SDK reads without changing financial extraction behavior."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import sqlite3
import sys
import time

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from data_fetch.yfinance_extractors import extract_financial_histories


def statement_frames():
    columns = pd.to_datetime(["2025-12-31", "2024-12-31"])
    return {
        "financials": pd.DataFrame(
            [[2e9, 1e9], [4e8, 2e8], [8e8, 4e8], [6e8, 3e8]], columns=columns,
            index=["Total Revenue", "Net Income", "Gross Profit", "Operating Income"],
        ),
        "cashflow": pd.DataFrame(
            [[5e8, 3e8], [-1e8, -1e8]], columns=columns,
            index=["Operating Cash Flow", "Capital Expenditure"],
        ),
        "balance_sheet": pd.DataFrame(
            [[6e9, 5e9], [3e9, 2e9]], columns=columns,
            index=["Total Assets", "Stockholders Equity"],
        ),
    }


class StatementStock:
    def __init__(self, frames=None):
        self.frames = frames if frames is not None else statement_frames()
        self.calls = Counter()

    def __getattr__(self, name):
        if name not in self.frames:
            raise AttributeError(name)
        self.calls[name] += 1
        value = self.frames[name]
        if isinstance(value, Exception):
            raise value
        return value


def test_primary_three_table_read_has_one_observation_and_preserves_values():
    stock = StatementStock()
    result = extract_financial_histories(stock, "AAPL", [], data_loader_cls=None)

    assert result["years"] == ["2024", "2025"]
    assert result["revenue_history"] == [1.0, 2.0]
    assert result["net_income_history"] == [0.2, 0.4]
    assert result["fcf_history"] == [0.2, 0.4]
    assert result["total_assets_history"] == [5.0, 6.0]
    assert result["total_equity_history"] == [2.0, 3.0]
    assert stock.calls == {"financials": 1, "cashflow": 1, "balance_sheet": 1}
    audit = result["primary_financial_audit"]
    assert audit["source"] == "financial_statements"
    assert audit["provider"] == "Yahoo annual financial statements"
    assert audit["status"] == "success"
    assert audit["record_count"] == 2
    assert audit["event_kind"] == "sdk_operation"
    assert len(audit["operation_id"]) == 32
    assert set(audit["component_statuses"]) == {"financials", "cashflow", "balance_sheet"}
    assert all(row["status"] == "complete" for row in audit["component_statuses"].values())
    assert "http_request_sent" not in audit
    assert "response_sha256" not in audit


@pytest.mark.parametrize("case", ["missing_field", "zero", "nan", "missing_capex", "missing_period",
                                  "balance_order", "invalid_period", "duplicate_year", "year_gap", "future_period"])
def test_incomplete_primary_stays_partial_without_repairing_output(case):
    frames = statement_frames()
    if case == "missing_field":
        frames["financials"] = frames["financials"].drop("Gross Profit")
    elif case in {"zero", "nan"}:
        frames["financials"].iloc[0, 0] = 0 if case == "zero" else float("nan")
    elif case == "missing_capex":
        frames["cashflow"] = frames["cashflow"].drop("Capital Expenditure")
    elif case == "missing_period":
        frames["cashflow"] = frames["cashflow"].iloc[:, :1]
    elif case == "balance_order":
        frames["balance_sheet"] = frames["balance_sheet"].iloc[:, ::-1]
    elif case == "invalid_period":
        frames["financials"].columns = ["invalid", "2024"]
    elif case == "duplicate_year":
        frames["cashflow"].columns = pd.to_datetime(["2025-12-31", "2025-06-30"])
    elif case == "year_gap":
        for frame in frames.values():
            frame.columns = pd.to_datetime(["2025-12-31", "2023-12-31"])
    elif case == "future_period":
        for frame in frames.values():
            frame.columns = pd.to_datetime(["2099-12-31", "2024-12-31"])
    stock = StatementStock(frames)
    result = extract_financial_histories(stock, "AAPL", [], data_loader_cls=None)
    audit = result["primary_financial_audit"]
    assert audit["status"] == "degraded_enrichment"
    assert audit["coverage_status"] == "partial"
    assert audit["record_count"] > 0
    assert stock.calls == {"financials": 1, "cashflow": 1, "balance_sheet": 1}
    if case == "zero":
        assert result["revenue_history"] == [1.0, None]  # Legacy zero loss is not repaired here.
    if case == "missing_capex":
        assert result["fcf_history"] == [0.3, 0.5]  # Existing CapEx default remains visible.
    if case == "balance_order":
        assert result["total_assets_history"] == [6.0, 5.0]  # Existing position alignment.


@pytest.mark.parametrize("name", ["financials", "cashflow", "balance_sheet"])
def test_one_table_exception_preserves_other_reads_and_diagnostics(name):
    frames = statement_frames()
    frames[name] = RuntimeError("synthetic getter failure")
    stock = StatementStock(frames)
    result = extract_financial_histories(stock, "AAPL", [], data_loader_cls=None)
    audit = result["primary_financial_audit"]
    assert audit["status"] == "degraded_enrichment"
    assert audit["component_statuses"][name]["status"] == "error"
    assert audit["component_statuses"][name]["error_kind"] == "RuntimeError"
    assert stock.calls == {"financials": 1, "cashflow": 1, "balance_sheet": 1}


@pytest.mark.parametrize("kind,status,outcome", [("empty", "degraded_enrichment", "empty"),
                                                ("null", "degraded_enrichment", "empty"),
                                                ("error", "error", "error")])
def test_no_usable_primary_values_never_report_success(kind, status, outcome):
    frames = statement_frames()
    for name in frames:
        frames[name] = pd.DataFrame() if kind == "empty" else (
            frames[name] * float("nan") if kind == "null" else ValueError("synthetic"))
    result = extract_financial_histories(StatementStock(frames), "AAPL", [], data_loader_cls=None)
    audit = result["primary_financial_audit"]
    assert (audit["status"], audit["record_count"], audit["outcome"]) == (status, 0, outcome)


@pytest.mark.parametrize("quote_type", ["ETF", "MUTUALFUND"])
def test_fund_skip_has_no_getters_or_operation(quote_type):
    stock = StatementStock()
    result = extract_financial_histories(stock, "AAPL", [], quote_type=quote_type)
    assert stock.calls == {}
    assert result["primary_financial_audit"] is None


def test_fallback_success_cannot_promote_failed_primary(monkeypatch):
    import data_fetch.yfinance_extractors as extractors
    calls = []
    fallback_audit = {"source": "financial_statements", "provider": "FinMind financial statement fallback",
                      "status": "success", "record_count": 1, "operation_id": "fallback-operation"}

    def fallback(*args, **kwargs):
        calls.append(args)
        return {"audit": fallback_audit, "value": {
            "years": ["2025"], "rows_by_year": {"2025": {"revenue": 1, "net_income": 0.2,
            "gross_profit": 0.4, "operating_income": 0.3, "free_cash_flow": 0.2,
            "total_assets": 5, "total_equity": 2}}}}

    monkeypatch.setattr(extractors, "audited_fetch", fallback)
    stock = StatementStock({name: RuntimeError("synthetic") for name in statement_frames()})
    result = extract_financial_histories(stock, "5314.TWO", [], data_loader_cls=object)
    assert len(calls) == 1
    assert result["revenue_history"] == [1]
    assert result["primary_financial_audit"]["status"] == "error"
    assert result["primary_financial_audit"]["record_count"] == 0
    assert result["finmind_financial_fallback_audit"] == fallback_audit
    assert result["primary_financial_audit"]["operation_id"] != fallback_audit["operation_id"]


def finalize(histories, monkeypatch, fallback=None):
    import data_fetch.yfinance_payload as payload
    monkeypatch.setattr(payload, "set_cache_json", lambda *_args: None)
    data = {"ticker": "AAPL", "current_price": 123, "data_source_notes": [],
            **{key: value for key, value in histories.items() if not key.endswith("audit")}}
    return payload.finalize_and_cache_legacy_payload(
        data=data, ticker="AAPL", original_cache_key="test:financial", provider=SimpleNamespace(name="fixture"),
        fetch_started_epoch=time.time(), skip_optional_http=True, enrichment_audit=[],
        fmp_quote_audit=None, monthly_revenue_audit=None, finmind_financial_fallback_audit=fallback,
        primary_financial_audit=histories["primary_financial_audit"],
    )


@pytest.mark.parametrize("with_fallback", [False, True])
def test_finalizer_keeps_primary_before_existing_latest_semantics(monkeypatch, with_fallback):
    from data_trust_source_status import latest_audit_by_source
    histories = extract_financial_histories(StatementStock(), "AAPL", [], data_loader_cls=None)
    fallback = ({"source": "financial_statements", "provider": "FinMind financial statement fallback",
                 "status": "success", "record_count": 2, "operation_id": "fallback-operation"}
                if with_fallback else None)
    data = finalize(histories, monkeypatch, fallback)
    audits = [entry for entry in data["source_audit"] if entry["source"] == "financial_statements"]
    assert audits[0] == histories["primary_financial_audit"]
    assert audits[1]["message"] == "本次重新抓取完成。"
    assert len(audits) == (3 if with_fallback else 2)
    assert latest_audit_by_source(audits)["financial_statements"] == (fallback or audits[1])


@pytest.mark.parametrize("record", [False, True])
def test_service_persists_one_sdk_operation_and_excludes_aggregate_from_projection(monkeypatch, record):
    import asyncio
    import provider_sla
    from data_fetch import FetchRequest, StockDataService
    from provider_acquisition import project_acquisition_events

    async def fetcher(request):
        return finalize(extract_financial_histories(StatementStock(), request.ticker, [], data_loader_cls=None), monkeypatch)

    result = asyncio.run(StockDataService(fetcher=fetcher).fetch_async(
        FetchRequest.from_ticker("AAPL", record_provider_sla=record)))
    primary = next(entry for entry in result.source_audit if entry["provider"] == "Yahoo annual financial statements")
    assert primary["fetch_id"]
    if not record:
        # Existing trust/SLA reads may initialize the isolated schema.
        if Path(provider_sla.TASK_DB_PATH).exists():
            with sqlite3.connect(provider_sla.TASK_DB_PATH) as conn:
                assert conn.execute("SELECT COUNT(*) FROM provider_sla_events").fetchone()[0] == 0
        return
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(conn.execute("SELECT * FROM provider_sla_events WHERE source='financial_statements'"))
    assert len(rows) == 2  # One SDK operation plus the unchanged excluded summary.
    details = json.loads(rows[0]["details_json"])
    assert details["operation_id"] == primary["operation_id"]
    assert details["event_kind"] == "sdk_operation"
    assert details["component_statuses"] == primary["component_statuses"]
    assert "http_request_sent" not in details
    projection = project_acquisition_events(rows, window="last_24h", now=time.time())
    group = projection["sources"][0]
    assert (group["fetch_attempts"], group["fetched_count"], group["aggregate_count"]) == (1, 1, 1)
    assert group["http_attempt_count"] == 0


@pytest.mark.parametrize("path", ["core_fresh", "workflow_fresh", "workflow_fallback"])
def test_cache_rebuilding_never_replays_sdk_operation(monkeypatch, path):
    from data_fetch import workflow_cache
    from data_fetch.constants import DATA_SCHEMA_VERSION, REQUIRED_DATA_SCHEMA_FIELDS
    from data_fetch.types import ProviderResult
    from data_fetch.yfinance_cache_gate import build_fresh_cache_payload
    from data_fetch.audit_helpers import _append_cache_audit_entries
    histories = extract_financial_histories(StatementStock(), "AAPL", [], data_loader_cls=None)
    cached = finalize(histories, monkeypatch)
    cached.update({field: cached.get(field) for field in REQUIRED_DATA_SCHEMA_FIELDS})
    cached["data_schema_version"] = DATA_SCHEMA_VERSION
    saved = deepcopy(cached)
    assess = lambda *_args: (path != "workflow_fallback", {"source_freshness": {}})
    monkeypatch.setattr(workflow_cache, "assess_cached_financial_data", assess)
    if path == "core_fresh":
        result, _, _ = build_fresh_cache_payload("AAPL", cached, assess_cached=assess,
                                                 append_cache_audit=_append_cache_audit_entries, now_epoch=time.time())
    elif path == "workflow_fresh":
        result = workflow_cache.fresh_cached_payload("AAPL", cached)
    else:
        result = workflow_cache.fallback_cached_payload("AAPL", cached, ProviderResult("market_data", "fixture", "error"))
    assert result["_cache_hit"] is True
    assert not any(entry.get("event_kind") == "sdk_operation" for entry in result["source_audit"])
    assert cached == saved


def core_fetch_fixture(monkeypatch, stock):
    """Keep real financial extraction/derived/finalization; isolate other sources."""
    import data_fetch.yfinance_core_fetch as core
    import data_fetch.yfinance_payload as payload
    monkeypatch.setattr(payload, "set_cache_json", lambda *_args: None)
    monkeypatch.setattr(core, "extract_price_history", lambda *_args: {})
    monkeypatch.setattr(core, "extract_market_history_bundle", lambda *_args: {
        "price_history_ranges": {}, "daily_market_data": {}, "technical_indicators": {}})
    monkeypatch.setattr(core, "extract_dividend_history", lambda *_args: {})
    monkeypatch.setattr(core, "extract_event_calendar", lambda *_args: {})
    monkeypatch.setattr(core, "fetch_monthly_revenue_records", lambda *_args: ([], None))
    monkeypatch.setattr(core, "fetch_sync_enrichment_bundle", lambda **_kwargs: {})
    financial_fields = ("years", "revenue_history", "net_income_history", "gross_profit_history",
                        "operating_income_history", "fcf_history", "total_assets_history", "total_equity_history")
    monkeypatch.setattr(core, "build_yfinance_payload_vars", lambda values: (
        {"ticker": values["ticker"], "current_price": values["current_price"],
         **{key: values[key] for key in financial_fields}}, {"fmp_quote_audit": None}))
    monkeypatch.setattr(core, "build_legacy_payload", lambda values: dict(values))

    class Provider:
        name = "synthetic-market-provider"

        def resolve_stock(self, ticker):
            return stock, {"currentPrice": 123, "longName": "Synthetic"}, True, ticker, []

    return core, Provider()


@pytest.mark.parametrize("kind, expected", [("complete", "fetched_count"), ("partial", "degraded_count"),
                                            ("empty", "empty_count"), ("error", "failed_count")])
def test_core_to_service_sqlite_projection_preserves_financial_classification(monkeypatch, kind, expected):
    import asyncio
    import provider_sla
    from data_fetch import FetchRequest, StockDataService
    from provider_acquisition import project_acquisition_events
    frames = statement_frames()
    if kind == "partial":
        frames["cashflow"] = frames["cashflow"].drop("Capital Expenditure")
    elif kind != "complete":
        frames = {name: pd.DataFrame() if kind == "empty" else RuntimeError("synthetic") for name in frames}
    stock = StatementStock(frames)
    core, provider = core_fetch_fixture(monkeypatch, stock)

    async def fetcher(request):
        return core.fetch_stock_data(request.ticker, skip_optional_http=True,
                                     market_data_provider=provider, force_refresh=True)

    result = asyncio.run(StockDataService(fetcher=fetcher).fetch_async(FetchRequest.from_ticker("AAPL")))
    assert not result.data.get("error")
    primary = [entry for entry in result.source_audit if entry.get("event_kind") == "sdk_operation"]
    assert len(primary) == 1
    # Capital-structure notes already read balance_sheet again outside the
    # observed extractor; this slice neither removes nor adds that existing read.
    assert stock.calls == {"financials": 1, "cashflow": 1, "balance_sheet": 2}
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(conn.execute("SELECT * FROM provider_sla_events WHERE source='financial_statements'"))
    group = project_acquisition_events(rows, window="last_24h", now=time.time())["sources"][0]
    assert group[expected] == 1
    assert group["fetch_attempts"] == 1
    assert group["aggregate_count"] == 1
    assert group["http_attempt_count"] == 0
    assert group["fetched_count"] == int(kind == "complete")


def test_later_core_error_keeps_existing_error_return_without_second_observation_sink(monkeypatch):
    from data_fetch import FetchRequest, StockDataService
    import asyncio
    import provider_sla
    stock = StatementStock()
    core, provider = core_fetch_fixture(monkeypatch, stock)

    def fail_after_extraction(*_args):
        raise RuntimeError("synthetic post-extraction failure")

    monkeypatch.setattr(core, "calculate_margin_histories", fail_after_extraction)

    async def fetcher(request):
        return core.fetch_stock_data(request.ticker, skip_optional_http=True,
                                     market_data_provider=provider, force_refresh=True)

    result = asyncio.run(StockDataService(fetcher=fetcher).fetch_async(FetchRequest.from_ticker("AAPL")))
    assert result.data["error"] == "synthetic post-extraction failure"
    assert stock.calls == {"financials": 1, "cashflow": 1, "balance_sheet": 1}
    assert not any(entry.get("event_kind") == "sdk_operation" for entry in result.source_audit)
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as conn:
        assert conn.execute("SELECT COUNT(*) FROM provider_sla_events WHERE source='financial_statements'").fetchone()[0] == 0


def test_malformed_index_observation_cannot_interrupt_usable_extraction():
    frames = statement_frames()
    frames["financials"].loc[pd.NA] = [0, 0]
    result = extract_financial_histories(StatementStock(frames), "AAPL", [], data_loader_cls=None)
    assert result["revenue_history"] == [1.0, 2.0]
    assert result["primary_financial_audit"]["status"] == "degraded_enrichment"
    component = result["primary_financial_audit"]["component_statuses"]["financials"]
    assert "observation_error" in component["reason_code"]
    assert component["error_kind"] == "TypeError"
    assert component["retrieval_status"] == "observation_error"


def test_duplicate_columns_keep_original_swallowed_error_and_other_tables():
    frames = statement_frames()
    frames["financials"].columns = pd.to_datetime(["2025-12-31", "2025-12-31"])
    result = extract_financial_histories(StatementStock(frames), "AAPL", [], data_loader_cls=None)
    assert result["total_assets_history"] == [5.0, 6.0]
    assert result["primary_financial_audit"]["status"] == "degraded_enrichment"
    assert result["primary_financial_audit"]["component_statuses"]["financials"]["error_kind"] == "ValueError"


def test_duplicate_fiscal_periods_do_not_inflate_usable_year_count():
    frames = statement_frames()
    frames["cashflow"].columns = pd.to_datetime(["2025-12-31", "2025-06-30"])
    audit = extract_financial_histories(StatementStock(frames), "AAPL", [], data_loader_cls=None)["primary_financial_audit"]
    assert audit["record_count"] == 2
