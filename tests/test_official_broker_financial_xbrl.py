"""Broker filings use their own reported lines, never bank net-revenue labels."""

import pytest


BROKER_VALUES = {
    "ifrs-full:Revenue": "13,541,305",
    "ifrs-full:BrokerageFeeIncome": "4,757,564",
    "tifrs-bsci-bd:RevenuesFromUnderwritingBusiness": "167,352",
    "ifrs-full:ProfitLossAttributableToOwnersOfParent": "4,804,426",
    "ifrs-full:Assets": "100,000,000",
    "ifrs-full:EquityAttributableToOwnersOfParent": "20,000,000",
    "ifrs-full:CashFlowsFromUsedInOperatingActivities": "1,000,000",
    "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": "50,000",
    "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities": "10,000",
}


def broker_filing(year=2025, *, issuer="2855", missing=(), duplicate=False, positive_capex=False):
    instant = {"ifrs-full:Assets", "ifrs-full:EquityAttributableToOwnersOfParent"}
    outflows = {"ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"}
    facts = []
    for tag, value in BROKER_VALUES.items():
        if tag in missing:
            continue
        sign = ' sign="-"' if tag in outflows and not positive_capex else ""
        facts.append(f'<ix:nonFraction name="{tag}" contextRef="{("instant" if tag in instant else "duration")}"'
                     f'{sign} unitRef="TWD" scale="3" decimals="-3" format="ixt:numdotdecimal">'
                     f'{value}</ix:nonFraction>')
    if duplicate:
        facts.append(facts[0])
    return f'''<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
 xmlns:xbrli="http://www.xbrl.org/2003/instance">
 <xbrli:unit id="TWD"><xbrli:measure>iso4217:TWD</xbrli:measure></xbrli:unit>
 <xbrli:context id="duration"><xbrli:entity><xbrli:identifier scheme="http://www.twse.com.tw">{issuer}</xbrli:identifier></xbrli:entity>
 <xbrli:period><xbrli:startDate>{year}-01-01</xbrli:startDate><xbrli:endDate>{year}-12-31</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:context id="instant"><xbrli:entity><xbrli:identifier scheme="http://www.twse.com.tw">{issuer}</xbrli:identifier></xbrli:entity>
 <xbrli:period><xbrli:instant>{year}-12-31</xbrli:instant></xbrli:period></xbrli:context>
 {''.join(facts)}</html>'''.encode()


def test_broker_facts_have_distinct_sector_schema_and_prompt():
    from data_fetch.market_sources.broker_xbrl import parse_filing, assemble_histories
    from prompt_builder_helpers import _prompt_financial_institution_history

    facts = parse_filing(broker_filing(), "2855", 2025)
    result = assemble_histories({2025: facts}, expected_years=[2025])
    row = result["raw_twd_by_year"]["2025"]
    assert result["schema"] == "broker_consolidated.v1"
    assert row["reported_revenue"] == 13_541_305_000
    assert row["brokerage_fee_income"] == 4_757_564_000
    assert row["underwriting_revenue"] == 167_352_000
    assert row["free_cash_flow"] == 940_000_000
    assert "net_revenue" not in row and "revenue_history" not in result
    prompt = _prompt_financial_institution_history({"sector_specific_financials": result})
    assert prompt["schema"] == "broker_consolidated.v1"
    assert prompt["rows"][0]["reported_revenue_billion_twd"] == 13.5413
    assert "net_revenue_billion_twd" not in prompt["rows"][0]


@pytest.mark.parametrize("change", [
    {"issuer": "2851"}, {"missing": ("ifrs-full:Revenue",)},
    {"duplicate": True}, {"positive_capex": True},
])
def test_broker_rejects_wrong_identity_missing_or_ambiguous_facts(change):
    from data_fetch.market_sources.broker_xbrl import parse_filing
    from data_fetch.market_sources.official_xbrl_financial import FilingError

    with pytest.raises(FilingError):
        parse_filing(broker_filing(**change), "2855", 2025)


def test_financial_institution_fetch_routes_broker_taxonomy_without_bank_substitution(monkeypatch):
    import data_fetch.market_sources.financial_institution_xbrl as source

    urls = {year: f"https://mopsov.twse.com.tw/filing/{year}" for year in range(2021, 2026)}
    monkeypatch.setattr(source, "_filing_urls", lambda _index, _issuer: urls)
    monkeypatch.setattr(source, "_bounded_request", lambda _client, method, url, **_kwargs:
                        b"index" if method == "POST" else broker_filing(int(url.rsplit("/", 1)[1])))
    result = source.fetch_financial_institution_histories("2855.TW", client=object())
    assert result["schema"] == "broker_consolidated.v1"
    assert result["years"] == [str(year) for year in range(2021, 2026)]
    assert len(result["documents"]) == 5


def test_broker_history_reaches_sector_audit_without_general_industry_substitution(monkeypatch):
    from data_fetch import yfinance_extractors as extractors
    from data_fetch.market_sources.broker_xbrl import parse_filing, assemble_histories
    from test_financial_statement_observation import StatementStock

    rows = {year: parse_filing(broker_filing(year), "2855", year) for year in range(2021, 2026)}
    sector = assemble_histories(rows, expected_years=list(rows))
    sector.update(ticker="2855.TW", report_scope="consolidated",
                  source_url="https://mopsov.twse.com.tw/mops/web/ajax_t203sb01",
                  comparative_revisions=[],
                  documents=[{"year": year, "report_scope": "consolidated",
                              "url": f"https://mopsov.twse.com.tw/server-java/FileDownLoad?functionName=t164sb01&step=9&season=4&report_id=C&co_id=2855&year={year}",
                              "sha256": "a" * 64}
                             for year in rows])
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(extractors, "fetch_financial_institution_histories", lambda _ticker: sector)
    monkeypatch.setattr(extractors, "fetch_official_annual_histories",
                        lambda _ticker: (_ for _ in ()).throw(AssertionError("industrial parser cannot run")))
    notes = []
    result = extractors.extract_financial_histories(
        StatementStock(), "2855.TW", notes, data_loader_cls=None, industry_context="金融保險")
    assert result["sector_specific_financials"]["schema"] == "broker_consolidated.v1"
    assert result["sector_specific_financial_audit"]["status"] == "success"
    assert result["sector_specific_financial_audit"]["record_count"] == 5
    assert "證券商" in result["sector_specific_financial_audit"]["message"]
    assert any("證券商" in note for note in notes)
    assert result["official_financial_audit"] is None
