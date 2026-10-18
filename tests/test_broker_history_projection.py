"""Complete broker statements can replace incomplete SDK histories with typed facts."""
import json
import pytest
from pathlib import Path

from test_official_broker_financial_xbrl import broker_filing


def broker_statement(ticker="2855.TW"):
    from data_fetch.market_sources.broker_xbrl import parse_filing, assemble_histories
    years = list(range(2021, 2026))
    result = assemble_histories({y: parse_filing(broker_filing(y), "2855", y) for y in years},
                               expected_years=years)
    result.update(ticker=ticker, report_scope="consolidated",
                  source_url="https://mopsov.twse.com.tw/mops/web/ajax_t203sb01",
                  comparative_revisions=[],
                  documents=[{"year": y, "url": f"https://mopsov.twse.com.tw/server-java/FileDownLoad?functionName=t164sb01&step=9&season=4&report_id=C&year={y}&co_id=2855",
                              "report_scope": "consolidated", "sha256": "a" * 64} for y in years])
    return result


class NoStatementSdk:
    @property
    def financials(self):
        raise AssertionError("complete official broker history must avoid the SDK")

    cashflow = financials
    balance_sheet = financials


def test_complete_broker_history_skips_incomplete_sdk_and_keeps_statement_basis(monkeypatch):
    from data_fetch import yfinance_extractors as source
    from data_fetch.yfinance_derived import calculate_margin_histories
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(source, "fetch_financial_institution_histories", lambda _ticker: broker_statement())
    monkeypatch.setattr(source, "fetch_finmind_financial_statement_fallback",
                        lambda _ticker: (_ for _ in ()).throw(AssertionError("redundant fallback")))
    result = source.extract_financial_histories(NoStatementSdk(), "2855.TW", [],
                                              industry_context="證券 金融保險")
    assert result["years"] == [str(y) for y in range(2021, 2026)]
    assert result["revenue_history"] == [13.541305] * 5
    assert result["net_income_history"] == [4.804426] * 5
    assert result["fcf_history"] == [0.94] * 5
    assert result["total_assets_history"] == [100.0] * 5
    assert result["total_equity_history"] == [20.0] * 5
    assert result["gross_profit_history"] == result["operating_income_history"] == [None] * 5
    assert result["primary_financial_audit"] is result["finmind_financial_fallback_audit"] is None
    basis = result["financial_history_basis"]
    assert basis["statement_schema"] == "broker_consolidated.v1"
    assert basis["report_scope"] == "consolidated"
    assert basis["field_sources"]["revenue_history"]["fact"] == "ifrs-full:Revenue"
    assert basis["field_sources"]["net_income_history"]["fact"] == "ifrs-full:ProfitLossAttributableToOwnersOfParent"
    margins = calculate_margin_histories(result["revenue_history"], result["gross_profit_history"],
                                        result["operating_income_history"], result["net_income_history"],
                                        result["total_equity_history"])
    assert margins["gross_margin_history"] == margins["op_margin_history"] == [None] * 5
    assert margins["roe_history"] == [24.0] * 5


def test_broker_history_basis_reaches_prompt_and_money_claim_checks(monkeypatch):
    from data_fetch import yfinance_extractors as source
    from prompt_builder import format_data_for_prompt
    from financial_money_claims import financial_money_claim_issues
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(source, "fetch_financial_institution_histories", lambda _ticker: broker_statement())
    data = {"ticker": "2855.TW", "financial_currency": "TWD",
            **source.extract_financial_histories(NoStatementSdk(), "2855.TW", [],
                                                industry_context="證券 金融保險")}
    encoded = format_data_for_prompt(data)
    payload = json.loads(encoded.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0])
    assert payload["history"]["basis"]["statement_schema"] == "broker_consolidated.v1"
    assert payload["history"]["basis"]["field_sources"]["revenue_history"]["label"] == "證券商合併營業收入"
    assert payload["history"]["rows"][-1]["revenue_billion_twd"] == 13.5413
    assert payload["history"]["financial_institution"]["rows"][-1]["reported_revenue_billion_twd"] == 13.5413
    assert financial_money_claim_issues("2025 年營業收入為 13.54 億元。", data)
    assert financial_money_claim_issues("2025 年營業收入為 135.41 億元。", data) == []


@pytest.mark.parametrize("change", ["wrong_ticker", "individual", "wrong_document_issuer", "missing_value",
                                 "bool_value", "inconsistent_fcf", "non_contiguous", "missing_document", "malformed_url",
                                 "missing_document_hash", "missing_document_year", "missing_source_url",
                                 "missing_revisions", "wrong_source_url"])
def test_unverified_broker_projection_retains_sdk_fallback(monkeypatch, change):
    from data_fetch import yfinance_extractors as source
    from test_financial_statement_observation import StatementStock
    statement = broker_statement()
    if change == "wrong_ticker":
        statement["ticker"] = "6005.TW"
    elif change == "individual":
        statement["report_scope"] = "individual"
    elif change == "wrong_document_issuer":
        statement["documents"][0]["url"] = statement["documents"][0]["url"].replace("co_id=2855", "co_id=6005")
    elif change == "missing_value":
        statement["raw_twd_by_year"]["2021"].pop("reported_revenue")
    elif change == "bool_value":
        statement["raw_twd_by_year"]["2021"]["assets"] = True
    elif change == "inconsistent_fcf":
        statement["raw_twd_by_year"]["2021"]["free_cash_flow"] += 1
    elif change == "non_contiguous":
        statement["years"][0] = "2020"
    elif change == "missing_document":
        statement["documents"].pop()
    elif change == "malformed_url":
        statement["documents"][0]["url"] = "https://[invalid"
    elif change == "missing_document_hash":
        statement["documents"][0].pop("sha256")
    elif change == "missing_document_year":
        statement["documents"][0].pop("year")
    elif change == "missing_source_url":
        statement.pop("source_url")
    elif change == "missing_revisions":
        statement.pop("comparative_revisions")
    elif change == "wrong_source_url":
        statement["source_url"] = "https://example.com/filing"
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "1")
    baseline = source.extract_financial_histories(StatementStock(), "2855.TW", [],
                                                data_loader_cls=None, industry_context="證券 金融保險")
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(source, "fetch_financial_institution_histories", lambda _ticker: statement)
    result = source.extract_financial_histories(StatementStock(), "2855.TW", [],
                                              data_loader_cls=None, industry_context="證券 金融保險")
    assert "financial_history_basis" not in result
    assert result["sector_specific_financials"] is None
    assert result["sector_specific_financial_audit"]["status"] == "degraded_enrichment"
    for key in ("years", "revenue_history", "net_income_history", "fcf_history",
                "total_assets_history", "total_equity_history"):
        assert result[key] == baseline[key]


def test_prompt_basis_requires_matching_preserved_arrays():
    from data_fetch.financial_history_basis import project_broker_histories, prompt_history_basis
    statement = broker_statement()
    data = {"ticker": "2855.TW", "sector_specific_financials": statement,
            **project_broker_histories(statement, "2855.TW")}
    assert prompt_history_basis(data)["statement_schema"] == "broker_consolidated.v1"
    data["revenue_history"][0] += 1
    assert prompt_history_basis(data) == {}


def test_malformed_document_url_is_excluded_from_prompt_basis():
    from data_fetch.financial_history_basis import project_broker_histories, prompt_history_basis
    statement = broker_statement()
    data = {"ticker": "2855.TW", "sector_specific_financials": statement,
            **project_broker_histories(statement, "2855.TW")}
    statement["documents"][0]["url"] = "https://[invalid"
    assert prompt_history_basis(data) == {}


def test_snapshot_size_governance_preserves_broker_statement_and_basis():
    from data_fetch.financial_history_basis import project_broker_histories, prompt_history_basis
    from data_trust import apply_snapshot_size_governance
    statement = broker_statement()
    data = {"ticker": "2855.TW", "sector_specific_financials": statement,
            **project_broker_histories(statement, "2855.TW"), "non_core_debug": "x" * 20_000}
    snapshot = apply_snapshot_size_governance({"data": data}, max_bytes=10_000)
    assert "non_core_debug" not in snapshot["data"]
    assert snapshot["data"]["sector_specific_financials"] == statement
    assert prompt_history_basis(snapshot["data"])["statement_schema"] == "broker_consolidated.v1"


def test_live_official_broker_receipt_replays_without_sdk(monkeypatch):
    from data_fetch import yfinance_extractors as source
    statement = json.loads((Path(__file__).parent / "fixtures/source_acquisition/broker_2855_20261009.json").read_text())
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(source, "fetch_financial_institution_histories", lambda _ticker: statement)
    result = source.extract_financial_histories(NoStatementSdk(), "2855.TW", [],
                                              data_loader_cls=None, industry_context="金融保險")
    assert result["years"] == ["2021", "2022", "2023", "2024", "2025"]
    assert result["revenue_history"] == [11.621619, 6.271336, 9.542583, 13.029981, 13.541305]
    assert result["fcf_history"][-1] == -10.230221
    assert result["financial_history_basis"]["field_sources"]["revenue_history"]["label"] == "證券商合併營業收入"


def test_role_state_view_keeps_scope_and_years_with_broker_annual_arrays():
    from data_fetch.financial_history_basis import project_broker_histories
    from state_memory import initialize_agent_state, state_view_for
    statement = broker_statement()
    data = {"ticker": "2855.TW", "sector_specific_financials": statement,
            **project_broker_histories(statement, "2855.TW")}
    view = state_view_for("valuation", initialize_agent_state(data))
    normalized = view["normalized_financials"]
    assert normalized["financial_history_basis"] == data["financial_history_basis"]
    assert normalized["financial_history_basis"]["years"] == data["years"]
    assert normalized["revenue_history"] == data["revenue_history"]


def test_broker_capital_notes_use_same_official_year_without_sdk_balance_read():
    from data_fetch.financial_history_basis import project_broker_histories
    from data_fetch.yfinance_capital_notes import build_capital_structure_notes
    statement = json.loads((Path(__file__).parent / "fixtures/source_acquisition/broker_2855_20261009.json").read_text())
    history = {"ticker": "2855.TW", "sector_specific_financials": statement,
               **project_broker_histories(statement, "2855.TW")}
    notes = build_capital_structure_notes(
        NoStatementSdk(), {"returnOnAssets": 0.9},
        **{key: history[key] for key in ("revenue_history", "net_income_history",
                                        "total_assets_history", "total_equity_history")},
        market_cap=10_000_000_000, total_debt=1_000_000_000,
        financial_history_data=history)
    assert notes["equity_multiplier"] == "6.355x"
    assert "2025" in notes["equity_multiplier_note"] and "母公司權益" in notes["equity_multiplier_note"]
    assert "期末母公司權益" in notes["dupont_identity_note"]
    assert "Yahoo ROA" not in notes["equity_multiplier_note"]


@pytest.mark.parametrize("field", ["financial_history_basis", "sector_specific_financials"])
def test_statement_scope_change_requires_analysis_rerun_even_with_equal_arrays(field):
    import copy
    from data_fetch.financial_history_basis import project_broker_histories
    from report_refresh_diff import refresh_data_diff, refresh_requires_analysis_rerun
    statement = broker_statement()
    data = {"ticker": "2855.TW", "sector_specific_financials": statement,
            **project_broker_histories(statement, "2855.TW")}
    before = {"data": data}
    after = copy.deepcopy(before)
    after["data"][field]["report_scope"] = "individual"
    assert refresh_requires_analysis_rerun(before, after, refresh_data_diff(before, after)) is True
