"""Official insurer individual filings stay distinct from consolidated bank facts."""

import pytest


VALUES = {
    "tifrs-bsci-ins:OperatingRevenue": "22,898,381",
    "tifrs-bsci-ins:NetOperatingIncomeLoss": "3,369,513",
    "ifrs-full:ProfitLoss": "2,932,619",
    "ifrs-full:Assets": "59,835,174",
    "ifrs-full:Equity": "21,706,032",
    "ifrs-full:CashFlowsFromUsedInOperatingActivities": "2,359,679",
    "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": "14,504",
    "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities": "24,999",
}


def insurer_filing(year=2025, *, issuer="2851", currency="iso4217:TWD", missing=(), duplicate=False,
                   positive_capex=False):
    instant = {"ifrs-full:Assets", "ifrs-full:Equity"}
    outflows = {"ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"}
    facts = []
    for tag, value in VALUES.items():
        if tag in missing:
            continue
        facts.append(f'<ix:nonFraction name="{tag}" contextRef="{("instant" if tag in instant else "duration")}"'
                     f'{" sign=\"-\"" if tag in outflows and not positive_capex else ""} unitRef="TWD" scale="3" decimals="-3"'
                     f' format="ixt:numdotdecimal">{value}</ix:nonFraction>')
    if duplicate:
        facts.append(facts[0])
    return f'''<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
 xmlns:xbrli="http://www.xbrl.org/2003/instance">
 <xbrli:unit id="TWD"><xbrli:measure>{currency}</xbrli:measure></xbrli:unit>
 <xbrli:context id="duration"><xbrli:entity><xbrli:identifier scheme="http://www.twse.com.tw">{issuer}</xbrli:identifier></xbrli:entity>
 <xbrli:period><xbrli:startDate>{year}-01-01</xbrli:startDate><xbrli:endDate>{year}-12-31</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:context id="instant"><xbrli:entity><xbrli:identifier scheme="http://www.twse.com.tw">{issuer}</xbrli:identifier></xbrli:entity>
 <xbrli:period><xbrli:instant>{year}-12-31</xbrli:instant></xbrli:period></xbrli:context>
 {''.join(facts)}</html>'''.encode()


def test_insurer_individual_facts_remain_scope_and_taxonomy_specific():
    from data_fetch.market_sources.insurer_xbrl import parse_filing, assemble_histories
    from prompt_builder_helpers import _prompt_financial_institution_history

    facts = parse_filing(insurer_filing(), "2851", 2025)
    result = assemble_histories({2025: facts}, expected_years=[2025])
    row = result["raw_twd_by_year"]["2025"]
    assert result["schema"] == "insurer_individual.v1"
    assert result["report_scope"] == "individual"
    assert row["insurance_operating_revenue"] == 22_898_381_000
    assert row["net_operating_income"] == 3_369_513_000
    assert row["profit_loss"] == 2_932_619_000
    assert row["free_cash_flow"] == 2_320_176_000
    assert "net_revenue" not in row and "revenue_history" not in result
    prompt = _prompt_financial_institution_history({"sector_specific_financials": result})
    assert prompt["schema"] == "insurer_individual.v1"
    assert "individual" in prompt["basis_note"]
    assert prompt["rows"][0]["insurance_operating_revenue_billion_twd"] == 22.8984
    assert "net_revenue_billion_twd" not in prompt["rows"][0]


@pytest.mark.parametrize("change", [
    {"issuer": "2855"}, {"currency": "iso4217:USD"}, {"year": 2024},
    {"missing": ("tifrs-bsci-ins:OperatingRevenue",)}, {"duplicate": True},
    {"positive_capex": True},
])
def test_insurer_rejects_wrong_identity_currency_missing_or_duplicate(change):
    from data_fetch.market_sources.insurer_xbrl import parse_filing
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    with pytest.raises(FilingError):
        parse_filing(insurer_filing(**change), "2851", 2025)


def test_financial_fetch_uses_individual_insurer_only_when_consolidated_unavailable(monkeypatch):
    import data_fetch.market_sources.financial_institution_xbrl as source
    from data_fetch.market_sources.official_xbrl_financial import FilingError

    years = range(2021, 2026)
    urls = {year: f"https://mopsov.twse.com.tw/filing/{year}" for year in years}
    requested = []

    def filing_urls(_index, _issuer, *, report_id="C"):
        requested.append(report_id)
        return {} if report_id == "C" else urls

    monkeypatch.setattr(source, "_filing_urls", filing_urls)
    monkeypatch.setattr(source, "_bounded_request", lambda _client, method, url, **_kwargs:
                        b"index" if method == "POST" else insurer_filing(int(url.rsplit("/", 1)[1])))
    result = source.fetch_financial_institution_histories("2851.TW", client=object())
    assert requested == ["C", "A"]
    assert result["schema"] == "insurer_individual.v1"
    assert result["report_scope"] == "individual"
    assert len(result["documents"]) == 5

    monkeypatch.setattr(source, "_bounded_request", lambda _client, method, url, **_kwargs:
                        b"index" if method == "POST" else b"<html>not insurer</html>")
    with pytest.raises(FilingError):
        source.fetch_financial_institution_histories("2851.TW", client=object())


def test_mops_index_separates_individual_from_consolidated_report_urls():
    from data_fetch.market_sources.official_xbrl_financial import _filing_urls

    def link(issuer, report_id):
        return ("/server-java/FileDownLoad?functionName=t164sb01&amp;step=9&amp;"
                f"co_id={issuer}&amp;year=2025&amp;season=4&amp;report_id={report_id}")

    index = f'<a href="{link("2851", "A")}">A</a><a href="{link("2851", "C")}">C</a>'
    index += f'<a href="{link("2855", "A")}">other issuer</a>'
    raw = index.encode()
    assert list(_filing_urls(raw, "2851")) == [2025]
    assert "report_id=C" in _filing_urls(raw, "2851")[2025]
    assert "report_id=A" in _filing_urls(raw, "2851", report_id="A")[2025]


def test_insurer_audit_says_individual_not_consolidated(monkeypatch):
    from data_fetch import yfinance_extractors as extractors
    from data_fetch.market_sources.insurer_xbrl import parse_filing, assemble_histories
    from test_financial_statement_observation import StatementStock

    years = range(2021, 2026)
    sector = assemble_histories({year: parse_filing(insurer_filing(year), "2851", year) for year in years},
                                expected_years=list(years))
    sector.update(source_url="https://mopsov.twse.com.tw/mops/web/ajax_t203sb01",
                  comparative_revisions=[],
                  documents=[{"year": year, "url": f"https://mopsov.twse.com.tw/{year}", "sha256": "d" * 64}
                             for year in years])
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(extractors, "fetch_financial_institution_histories", lambda _ticker: sector)
    notes = []
    result = extractors.extract_financial_histories(
        StatementStock(), "2851.TW", notes, data_loader_cls=None, industry_context="金融保險")
    audit = result["sector_specific_financial_audit"]
    assert audit["status"] == "success"
    assert audit["coverage_status"] == "sector_specific_individual_complete"
    assert audit["report_scope"] == "individual"
    assert "個體" in audit["message"] and "合併" not in audit["message"]
    assert any("個體" in note and "不代表合併集團" in note for note in notes)
