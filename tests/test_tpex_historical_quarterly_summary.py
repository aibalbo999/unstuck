"""Offline contracts for TPEx's explicitly summary-only quarterly source."""
from __future__ import annotations

from datetime import date
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import time

from official_response_evidence import archive_response

from data_fetch.market_sources import tpex_historical_quarterly_summary as tpex


TODAY = date(2026, 10, 17)
FIXTURE = Path(__file__).parent / "fixtures" / "source_acquisition" / "tpex_quarterly_summary_2026Q2.xls"
FIXTURE_SHA256 = "86ff1112a0eb6da1a0e4fc8d7be562b0848bfb95bcffacfce7742537c7316f43"


def _index(year=2026, quarters=(1, 2)):
    return json.dumps({
        "stat": "ok",
        "tables": [
            {"title": "Mainboard Companies", "date": str(year),
             "fields": ["Quarter/Year", "XLS Download", "ODS Download"],
             "data": [[f"Q{q} {year}", f"/storage/statistic/financial/en-us/O_{year}Q{q}.xls",
                       f"/en-us/api/convertToOds?f=/statistic/financial/en-us/O_{year}Q{q}.xls"]
                      for q in quarters], "totalCount": len(quarters)},
            {"title": "Emerging Stock Board Companies", "date": str(year),
             "fields": ["Quarter/Year", "XLS Download", "ODS Download"], "data": [], "totalCount": 0},
        ],
    }, ensure_ascii=False).encode("utf-8")


def _value_with_receipts():
    raw = FIXTURE.read_bytes()
    index_raw = _index()
    now = time.time()
    index_receipt = archive_response(index_raw, source_url=tpex.INDEX_URL, retrieved_at=now,
                                     http_status=200, max_bytes=tpex.INDEX_MAX_BYTES)
    file_url = tpex.quarter_file_url(2026, 2)
    file_receipt = archive_response(raw, source_url=file_url, retrieved_at=now,
                                    http_status=200, max_bytes=tpex.FILE_MAX_BYTES)
    value = tpex.parse_quarterly_summary(raw, ticker="3324.TWO", year=2026, quarter=2, today=TODAY)
    value.update(source_url=file_url, response_sha256=sha256(raw).hexdigest(), response_bytes=len(raw),
                 fetched_at_epoch=now, fetched_at=tpex.iso_from_epoch(now), original_receipt=file_receipt,
                 index_year=2026, index_fetched_at_epoch=now, index_original_receipt=index_receipt)
    return value


def test_current_official_file_produces_a_typed_same_period_summary():
    raw = FIXTURE.read_bytes()
    assert sha256(raw).hexdigest() == FIXTURE_SHA256

    value = tpex.parse_quarterly_summary(
        raw, ticker="3324.TWO", year=2026, quarter=2, today=TODAY,
    )

    assert value["schema"] == tpex.SCHEMA
    assert value["coverage_status"] == "period_comparison_summary_only"
    assert value["ticker"] == "3324.TWO" and value["issuer_name"] == "AURAS"
    assert value["period"] == {
        "year": 2026, "quarter": 2,
        "period_start": "2026-01-01", "period_end": "2026-06-30",
        "comparison_period_start": "2025-01-01", "comparison_period_end": "2025-06-30",
        "income_period_basis": "year_to_date_cumulative",
        "comparison_basis": "same_period_previous_year",
    }
    assert value["metrics"]["operating_revenue_ytd_thousands"] == 17_251_778
    assert value["comparison"]["operating_revenue_ytd_thousands"] == 9_721_388
    assert value["metrics"]["net_income_after_tax_ytd_thousands"] == 2_132_961
    assert value["metrics"]["eps_ytd_twd_per_share"] == 23.01
    assert value["comparison"]["eps_ytd_twd_per_share"] == 7.41
    assert value["currency"] == "TWD" and value["amount_unit"] == "thousands"
    assert value["cash_flow_statement_available"] is False
    assert value["scope"] == "tpex_mainboard_summary_not_complete_financial_statements"


def test_index_selects_only_a_recent_mainboard_xls_with_exact_period_identity():
    reports = tpex.parse_report_index(_index(), requested_year=2026)
    selected = tpex.select_latest_report([reports], today=TODAY)

    assert selected == {
        "year": 2026, "quarter": 2,
        "url": "https://www.tpex.org.tw/storage/statistic/financial/en-us/O_2026Q2.xls",
    }


def test_summary_is_restricted_to_tpex_mainboard_and_current_report_window():
    assert tpex.supports_ticker("3324.TWO") is True
    assert tpex.supports_ticker("3324.TW") is False
    assert tpex.supports_ticker("3324") is False

    raw = FIXTURE.read_bytes()
    for ticker, today in (("2449.TWO", TODAY), ("3324.TWO", date(2027, 3, 1))):
        try:
            tpex.parse_quarterly_summary(raw, ticker=ticker, year=2026, quarter=2, today=today)
        except ValueError:
            pass
        else:
            raise AssertionError("wrong issuer or expired quarter must be rejected")


def test_index_rejects_foreign_or_ambiguous_download_routes():
    payload = json.loads(_index())
    payload["tables"][0]["data"][1][1] = "https://other.example/O_2026Q2.xls"
    try:
        tpex.parse_report_index(json.dumps(payload).encode(), requested_year=2026)
    except ValueError:
        pass
    else:
        raise AssertionError("foreign download URL must be rejected")

    payload = json.loads(_index())
    payload["tables"][0]["data"].append(payload["tables"][0]["data"][1])
    try:
        tpex.parse_report_index(json.dumps(payload).encode(), requested_year=2026)
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate quarter entry must be rejected")


def test_fetch_replays_original_index_and_workbook_before_returning_success(monkeypatch):
    raw = FIXTURE.read_bytes()
    index_raw = _index()
    now = time.time()
    index_receipt = archive_response(index_raw, source_url=tpex.INDEX_URL, retrieved_at=now,
                                     http_status=200, max_bytes=tpex.INDEX_MAX_BYTES)
    file_url = tpex.quarter_file_url(2026, 2)
    file_receipt = archive_response(raw, source_url=file_url, retrieved_at=now,
                                    http_status=200, max_bytes=tpex.FILE_MAX_BYTES)

    class FakeHttp:
        def __init__(self, deadline):
            self.deadline = deadline
            self.http_request_count = 2
            self.components = []

        def post_index(self, year):
            assert year == 2026
            self.components.append({"url": tpex.INDEX_URL, "http_request_sent": True,
                                    "cache_hit": False, "http_status": 200,
                                    "original_receipt": index_receipt})
            return index_raw, index_receipt

        def get_file(self, url):
            assert url == file_url
            self.components.append({"url": url, "http_request_sent": True,
                                    "cache_hit": False, "http_status": 200,
                                    "original_receipt": file_receipt})
            return raw, file_receipt

    monkeypatch.setattr(tpex, "TpexFinancialSummaryHttp", FakeHttp)
    monkeypatch.setattr(tpex, "_today", lambda: TODAY)

    result = tpex.fetch_quarterly_summary_result("3324.TWO")

    assert result["audit"]["status"] == "success", result["audit"]
    assert result["audit"]["provider"] == tpex.PROVIDER
    assert result["audit"]["coverage_status"] == "period_comparison_summary_only"
    assert result["audit"]["http_request_count"] == 2
    assert result["value"]["source_url"] == file_url
    assert tpex.project_summary(result["value"], "3324.TWO", today=TODAY) is not None


def test_annual_source_uses_tpex_only_after_annual_and_mops_quarter_fail(monkeypatch):
    from types import SimpleNamespace
    from data_fetch import annual_financial_source_provider as annual
    from data_fetch import official_financial_gap_cache
    from data_fetch.market_sources import official_quarterly_financials

    ticker = "3324.TWO"
    fetch_id = "tpex-fallback-test"
    annual_failure = {"source": "financial_statements", "provider": "TWSE MOPS public annual JSON",
                      "status": "error", "record_count": 0, "message": "annual unavailable", "fetch_id": fetch_id}
    quarterly_failure = {"source": "financial_statements", "provider": official_quarterly_financials.PROVIDER,
                         "status": "error", "record_count": 0, "message": "latest quarter unavailable", "fetch_id": fetch_id}
    value = _value_with_receipts()
    summary_audit = {"source": "financial_statements", "provider": tpex.PROVIDER,
                     "status": "success", "record_count": 1,
                     "coverage_status": "period_comparison_summary_only", "fetch_id": fetch_id,
                     "related_entries": [deepcopy(annual_failure), deepcopy(quarterly_failure)]}

    monkeypatch.setattr(annual, "validate_context", lambda data, symbol: None)
    monkeypatch.setattr(official_financial_gap_cache, "fetch_official_financial_result",
                        lambda symbol: {"value": None, "audit": deepcopy(annual_failure)})
    monkeypatch.setattr(official_quarterly_financials, "fetch_latest_quarter_result",
                        lambda symbol, data: {"value": None, "audit": deepcopy(quarterly_failure)})
    monkeypatch.setattr(tpex, "fetch_quarterly_summary_result",
                        lambda symbol: {"value": value, "audit": deepcopy(summary_audit)})
    monkeypatch.setattr(tpex, "project_summary", lambda candidate, symbol: candidate if candidate is value else None)

    result = annual.AnnualFinancialSourceProvider().fetch(
        SimpleNamespace(ticker=ticker), {"data": {"ticker": ticker, "industry": "Technology"}},
    )

    assert result.status == "success" and result.value is value
    assert result.provider == tpex.PROVIDER
    assert [row["provider"] for row in result.audit["related_entries"]] == [
        annual_failure["provider"], quarterly_failure["provider"],
    ]


def test_refresh_keeps_tpex_summary_separate_and_preserves_failed_sources(monkeypatch):
    import annual_financial_source_refresh as refresh
    from data_fetch.market_sources import official_quarterly_financials as quarterly

    ticker = "3324.TWO"
    value = _value_with_receipts()
    fetch_id = "tpex-refresh-test"
    annual_failure = {"source": "financial_statements", "provider": "TWSE MOPS public annual JSON",
                      "status": "error", "record_count": 0, "message": "annual unavailable", "fetch_id": fetch_id}
    quarter_failure = {"source": "financial_statements", "provider": quarterly.PROVIDER,
                       "status": "error", "record_count": 0, "message": "latest quarter unavailable", "fetch_id": fetch_id}
    audit = {"source": "financial_statements", "provider": tpex.PROVIDER,
             "status": "success", "record_count": 1,
             "coverage_status": "period_comparison_summary_only", "fetch_id": fetch_id,
             "fetched_at_epoch": value["fetched_at_epoch"],
             "related_entries": [deepcopy(annual_failure), deepcopy(quarter_failure)]}
    monkeypatch.setattr(refresh, "validate_annual_refresh_context", lambda *_args: None)
    old = {"ticker": ticker, "latest_quarter_financials": {"preserve": True},
           "data_source_notes": ["existing note"], "source_freshness": {"financial_statements": {"age": 4}}}

    merged = refresh.merge_latest_quarter_financial_source(
        old, [], value, [audit, annual_failure, quarter_failure], ticker,
    )

    assert merged["latest_quarter_financial_summary"]["schema"] == tpex.SCHEMA
    assert merged["latest_quarter_financials"] == {"preserve": True}
    assert merged["source_freshness"] == old["source_freshness"]
    assert [row["provider"] for row in merged["source_audit"]] == [
        tpex.PROVIDER, annual_failure["provider"], quarter_failure["provider"],
    ]
    assert any("同期摘要" in note and "不是完整三表" in note for note in merged["data_source_notes"])


def test_refresh_rejects_tpex_summary_when_both_prior_failure_receipts_are_not_preserved(monkeypatch):
    from fastapi import HTTPException
    import annual_financial_source_refresh as refresh
    from data_fetch.market_sources import official_quarterly_financials as quarterly

    ticker = "3324.TWO"
    value = _value_with_receipts()
    fetch_id = "tpex-incomplete-chain-test"
    annual_failure = {"source": "financial_statements", "provider": "TWSE MOPS public annual JSON",
                      "status": "error", "record_count": 0, "message": "annual unavailable", "fetch_id": fetch_id}
    audit = {"source": "financial_statements", "provider": tpex.PROVIDER,
             "status": "success", "record_count": 1,
             "coverage_status": "period_comparison_summary_only", "fetch_id": fetch_id,
             "fetched_at_epoch": value["fetched_at_epoch"],
             "related_entries": [deepcopy(annual_failure)]}
    monkeypatch.setattr(refresh, "validate_annual_refresh_context", lambda *_args: None)

    try:
        refresh.merge_latest_quarter_financial_source(
            {"ticker": ticker}, [], value, [audit, annual_failure], ticker,
        )
    except HTTPException as exc:
        assert exc.status_code == 502
    else:
        raise AssertionError("TPEx fallback must retain both prior provider failures")


def test_prompt_and_refresh_diff_keep_the_summary_scoped_and_decision_relevant():
    from prompt_builder import format_data_for_prompt
    import report_refresh_diff

    value = _value_with_receipts()
    prompt = format_data_for_prompt({"ticker": "3324.TWO", "latest_quarter_financial_summary": value}, compact=True)
    assert '"latest_quarter_financial_summary"' in prompt
    assert '"year_to_date_cumulative"' in prompt
    assert '"amount_unit": "thousands"' in prompt
    assert "不是完整三表、年度序列或 TTM" in prompt
    assert "raw_response_path" not in prompt and "original_receipt" not in prompt
    assert "latest_quarter_financial_summary" in report_refresh_diff.DECISION_RELEVANT_DATA_KEYS
