"""Financial-institution XBRL facts must not be cast as industrial revenue."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


FIELDS = {
    "ifrs-full:RevenueFromInterest": "1,000",
    "tifrs-bsci-fh:NetInterestIncomeExpense": "800",
    "tifrs-bsci-fh:NetServiceFeeChargeAndCommissionsIncomeLoss": "200",
    "tifrs-bsci-fh:NetIncomeLoss": "1,400",
    "ifrs-full:ProfitLossAttributableToOwnersOfParent": "100",
    "ifrs-full:Assets": "2,000",
    "ifrs-full:EquityAttributableToOwnersOfParent": "1,500",
    "ifrs-full:CashFlowsFromUsedInOperatingActivities": "400",
    "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": "50",
    "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities": "10",
}


def complete_receipt(sector, ticker="2882.TW"):
    sector.update(ticker=ticker, report_scope="consolidated",
                  source_url="https://mopsov.twse.com.tw/mops/web/ajax_t203sb01", comparative_revisions=[],
                  documents=[{"year": int(year), "report_scope": "consolidated", "sha256": "b" * 64,
                    "url": f"https://mopsov.twse.com.tw/server-java/FileDownLoad?functionName=t164sb01&step=9&season=4&report_id=C&year={year}&co_id={ticker.split('.')[0]}"}
                    for year in sector["years"]])
    return sector


def filing(year=2025, *, issuer="2882", unit="TWD", missing=(), values=None):
    facts = []
    for tag, value in (values or FIELDS).items():
        if tag in missing:
            continue
        period = "instant" if tag in {"ifrs-full:Assets", "ifrs-full:EquityAttributableToOwnersOfParent"} else "duration"
        sign = ' sign="-"' if ":PurchaseOf" in tag else ""
        facts.append(f'<ix:nonFraction name="{tag}" contextRef="{period}"{sign} '
                     f'unitRef="{unit}" scale="3" decimals="-3" format="ixt:numdotdecimal">'
                     f'{value}</ix:nonFraction>')
    return f'''<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
 xmlns:xbrli="http://www.xbrl.org/2003/instance">
 <xbrli:unit id="TWD"><xbrli:measure>iso4217:TWD</xbrli:measure></xbrli:unit>
 <xbrli:context id="duration"><xbrli:entity><xbrli:identifier scheme="http://www.twse.com.tw">{issuer}</xbrli:identifier></xbrli:entity>
 <xbrli:period><xbrli:startDate>{year}-01-01</xbrli:startDate><xbrli:endDate>{year}-12-31</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:context id="instant"><xbrli:entity><xbrli:identifier scheme="http://www.twse.com.tw">{issuer}</xbrli:identifier></xbrli:entity>
 <xbrli:period><xbrli:instant>{year}-12-31</xbrli:instant></xbrli:period></xbrli:context>
 {''.join(facts)}</html>'''.encode()


def test_financial_institution_facts_remain_sector_specific():
    from data_fetch.market_sources.financial_institution_xbrl import parse_filing, assemble_histories
    facts = parse_filing(filing(), "2882", 2025)
    histories = assemble_histories({2025: facts}, expected_years=[2025])
    row = histories["raw_twd_by_year"]["2025"]
    assert row["net_revenue"] == 1_400_000
    assert row["interest_income"] == 1_000_000
    assert row["net_income_attributable"] == 100_000
    assert row["free_cash_flow"] == 340_000
    assert "revenue_history" not in histories
    assert "gross_profit_history" not in histories


def test_bank_partial_restatement_keeps_verified_facts_and_unknown_fcf_explicit():
    from data_fetch.market_sources.financial_institution_xbrl import (
        BANK_FIELDS, assemble_histories, reconcile_comparatives,
    )

    intangible = "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"
    interest = "ifrs-full:RevenueFromInterest"
    operating_cash_flow = "ifrs-full:CashFlowsFromUsedInOperatingActivities"
    ppe = "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"

    def annual_row(year):
        row = {tag: 100_000 + offset for offset, tag in enumerate(BANK_FIELDS) if tag != intangible}
        row[operating_cash_flow] = 10_000_000 + year
        row[ppe] = -100_000
        return row

    rows = {year: annual_row(year) for year in range(2021, 2026)}
    partial_comparative = dict(rows[2021])
    partial_comparative[interest] += 500_000

    resolved, revisions = reconcile_comparatives(rows, {2021: partial_comparative})
    history = assemble_histories(resolved, expected_years=list(range(2021, 2026)))

    assert resolved[2021][interest] == partial_comparative[interest]
    assert intangible not in resolved[2021]
    assert any(
        item["year"] == 2021 and item["fact"] == interest and item["kind"] == "restatement"
        for item in revisions
    )
    for year in history["years"]:
        row = history["raw_twd_by_year"][year]
        assert row["intangible_purchase"] is None
        assert row["free_cash_flow"] is None


@pytest.mark.parametrize("change", [
    {"issuer": "2881"}, {"unit": "USD"}, {"year": 2024},
    {"missing": ("tifrs-bsci-fh:NetIncomeLoss",)},
])
def test_financial_institution_rejects_wrong_identity_currency_period_or_missing_fact(change):
    from data_fetch.market_sources.financial_institution_xbrl import parse_filing
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    with pytest.raises(FilingError):
        parse_filing(filing(**change), "2882", 2025)


def test_financial_institution_rejects_duplicate_and_positive_capex():
    from data_fetch.market_sources.financial_institution_xbrl import parse_filing
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    raw = filing()
    duplicate = raw.replace(b"</html>",
                            b'<ix:nonFraction name="tifrs-bsci-fh:NetIncomeLoss" contextRef="duration" '
                            b'unitRef="TWD" scale="3" decimals="-3" format="ixt:numdotdecimal">2</ix:nonFraction></html>')
    with pytest.raises(FilingError):
        parse_filing(duplicate, "2882", 2025)
    with pytest.raises(FilingError, match="cash outflow sign"):
        parse_filing(raw.replace(b'sign="-" ', b''), "2882", 2025)


def test_sector_facts_are_acquired_without_filling_general_industry_fields(monkeypatch):
    from data_fetch import yfinance_extractors as extractors
    from data_fetch.market_sources.financial_institution_xbrl import parse_filing, assemble_histories
    from test_financial_statement_observation import StatementStock
    from data_trust import source_record_count

    rows = {year: parse_filing(filing(year), "2882", year) for year in range(2021, 2026)}
    sector = complete_receipt(assemble_histories(rows, expected_years=list(rows)))
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "1")
    baseline = extractors.extract_financial_histories(
        StatementStock(), "2882.TW", [], data_loader_cls=None, industry_context="金融保險")
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(extractors, "fetch_financial_institution_histories", lambda _ticker: sector)
    monkeypatch.setattr(extractors, "fetch_official_annual_histories",
                        lambda _ticker: (_ for _ in ()).throw(AssertionError("industrial taxonomy must not run")))
    result = extractors.extract_financial_histories(
        StatementStock(), "2882.TW", [], data_loader_cls=None, industry_context="金融保險")
    assert result["sector_specific_financials"] is not None, result["sector_specific_financial_audit"]
    assert result["sector_specific_financials"]["raw_twd_by_year"]["2025"]["net_revenue"] == 1_400_000
    assert result["sector_specific_financial_audit"]["status"] == "success"
    assert result["sector_specific_financial_audit"]["record_count"] == 5
    assert result["official_financial_audit"] is None
    for key in ("revenue_history", "gross_profit_history", "operating_income_history"):
        assert result[key] == [None] * 5
    assert result["net_revenue_history"] == [0.0014] * 5
    assert source_record_count("financial_statements", {"sector_specific_financials": sector}) == 0


def test_prompt_keeps_financial_institution_values_separate_from_general_history():
    from data_fetch.market_sources.financial_institution_xbrl import parse_filing, assemble_histories
    from prompt_builder_helpers import _prompt_financial_institution_history

    sector = assemble_histories({2025: parse_filing(filing(), "2882", 2025)}, expected_years=[2025])
    projected = _prompt_financial_institution_history({"sector_specific_financials": sector})
    assert projected["rows"][0]["net_revenue_billion_twd"] == 0.0014
    assert projected["rows"][0]["free_cash_flow_billion_twd"] == 0.0003
    assert "gross_profit_billion_twd" not in projected["rows"][0]
    assert "not_general_industry_revenue" in projected["basis_note"]

    import json
    from prompt_builder import format_data_for_prompt
    encoded = format_data_for_prompt({"sector_specific_financials": sector})
    payload = json.loads(encoded.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0])
    assert payload["history"]["financial_institution"] == projected
    assert payload["history"]["rows"] == []


def test_radar_cache_does_not_repeat_official_financial_institution_download(monkeypatch):
    import cache_store
    import hashlib
    import time
    from datetime import datetime
    from cache_backends import InMemoryCache
    from data_fetch import yfinance_extractors as extractors
    from data_fetch.market_sources.financial_institution_xbrl import parse_filing, assemble_histories
    from test_financial_statement_observation import StatementStock

    rows = {year: parse_filing(filing(year), "2882", year) for year in range(2021, 2026)}
    sector = complete_receipt(assemble_histories(rows, expected_years=list(rows)))
    calls = []
    cache_store.set_cache_backend(InMemoryCache())
    old_key = f"radar_annual_histories:v3:2882.TW:{datetime.now():%Y-%m-%d}"
    cache_store.set_cache_json("shared_provider:v1:" + hashlib.sha256(old_key.encode()).hexdigest(), {
        "value": {"histories": {"years": []}, "notes": []},
        "fetched_at_epoch": time.time(), "fresh_until_epoch": time.time() + 3600,
        "retained_until_epoch": time.time() + 3600,
    }, 3600)
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(extractors, "fetch_financial_institution_histories",
                        lambda ticker: calls.append(ticker) or sector)
    try:
        first = extractors.extract_financial_histories(
            StatementStock(), "2882.TW", [], data_loader_cls=None,
            finmind_use_cache=True, industry_context="金融保險")
        second = extractors.extract_financial_histories(
            StatementStock(), "2882.TW", [], data_loader_cls=None,
            finmind_use_cache=True, industry_context="金融保險")
        assert calls == ["2882.TW"]
        assert first["sector_specific_financial_audit"]["status"] == "success"
        assert second["sector_specific_financial_audit"]["status"] == "skipped_fresh_cache"
        assert second["sector_specific_financial_audit"]["cache_hit"] is True
    finally:
        cache_store.reset_cache_store_for_tests()
