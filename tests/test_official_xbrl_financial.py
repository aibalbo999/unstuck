"""Official filing facts must keep their issuer, period and unit provenance."""
from pathlib import Path
from types import SimpleNamespace
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from data_fetch.market_sources.official_xbrl_financial import (
    parse_annual_filing, assemble_annual_histories, reconcile_comparative_rows, FilingError,
    FilingTransportError, FilingUnexpectedResponseError, PROVIDER, _bounded_request,
    _fetch_filing_document,
)


TAGS = {
    "Revenue": "1,000",
    "ProfitLossAttributableToOwnersOfParent": "100",
    "GrossProfit": "300",
    "ProfitLossFromOperatingActivities": "200",
    "Assets": "2,000",
    "EquityAttributableToOwnersOfParent": "1,500",
    "CashFlowsFromUsedInOperatingActivities": "400",
    "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": "50",
    "PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities": "0",
}


@pytest.fixture(autouse=True)
def restore_sector_provider_circuit_after_test():
    # The financial-sector routing checks intentionally run with fake-offline
    # upstreams. Their expected failures must not open the provider circuit
    # for the next test module in this isolated process.
    yield
    from data_fetch.market_sources.financial_institution_xbrl import PROVIDER as sector_provider
    from provider_resilience import clear_provider_circuits
    clear_provider_circuits(sector_provider)


def filing(year=2025, *, issuer="5314", unit="TWD", missing=(), values=None):
    values = values or TAGS
    facts = []
    for tag, value in values.items():
        if tag in missing:
            continue
        context = "instant" if tag in {"Assets", "EquityAttributableToOwnersOfParent"} else "duration"
        sign = ' sign="-"' if tag == "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities" else ""
        facts.append(f'<ix:nonFraction name="ifrs-full:{tag}" contextRef="{context}"{sign} '
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


def test_exact_facts_and_fcf_keep_raw_twd():
    parsed = parse_annual_filing(filing(), "5314", 2025)
    output = assemble_annual_histories({2025: parsed}, expected_years=[2025])
    assert output["years"] == ["2025"]
    assert output["revenue_history"] == [0.001]
    assert output["fcf_history"] == [0.00035]
    assert output["raw_twd_by_year"]["2025"]["free_cash_flow"] == 350000


@pytest.mark.parametrize("change", [
    {"issuer": "2330"}, {"unit": "USD"}, {"year": 2024},
    {"missing": ("Revenue",)},
])
def test_wrong_identity_period_unit_or_missing_fact_fails_closed(change):
    with pytest.raises(FilingError):
        parse_annual_filing(filing(**change), "5314", 2025)


def test_explicit_zero_from_next_filing_comparative_not_missing_inference():
    missing = ("PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities",)
    prior = parse_annual_filing(filing(2023, missing=missing), "5314", 2023, allow_missing=True)
    comparative = '''<xbrli:context id="prior"><xbrli:entity><xbrli:identifier scheme="http://www.twse.com.tw">5314</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2023-01-01</xbrli:startDate><xbrli:endDate>2023-12-31</xbrli:endDate></xbrli:period></xbrli:context>
    <ix:nonFraction name="ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"
    contextRef="prior" unitRef="TWD" scale="3" decimals="-3" format="ixt:numdotdecimal">0</ix:nonFraction>'''.encode()
    next_filing = filing(2024).replace(b"</html>", comparative + b"</html>")
    next_year_prior = parse_annual_filing(next_filing, "5314", 2023, allow_missing=True)
    with pytest.raises(FilingError):
        assemble_annual_histories({2023: prior}, expected_years=[2023])
    # A verified explicit comparative cell is the only acceptable fill.
    resolved, provenance = reconcile_comparative_rows({2023: prior}, {2023: next_year_prior})
    assert provenance == [{"year": 2023, "fact": missing[0], "original_twd": None, "revised_twd": 0,
                           "original_filing_year": 2023, "comparative_filing_year": 2024,
                           "kind": "missing_fact_fill"}]
    assert assemble_annual_histories(resolved, expected_years=[2023])["raw_twd_by_year"]["2023"]["free_cash_flow"] == 350000


def test_doctype_and_duplicate_fact_rejected():
    with pytest.raises(FilingError):
        parse_annual_filing(b"<!DOCTYPE x>" + filing(), "5314", 2025)
    raw = filing().replace(b"</html>", b'<ix:nonFraction name="ifrs-full:Revenue" contextRef="duration" unitRef="TWD" scale="3">999</ix:nonFraction></html>')
    with pytest.raises(FilingError):
        parse_annual_filing(raw, "5314", 2025)


def test_http_200_security_page_is_retryable_without_opening_provider_circuit(monkeypatch):
    import provider_resilience

    class Response:
        status_code = 200

        def __init__(self, raw):
            self.raw = raw

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def iter_bytes(self):
            yield self.raw

    class Client:
        def __init__(self, bodies):
            self.bodies = iter(bodies)
            self.calls = 0

        def stream(self, method, url, **_kwargs):
            assert method == "GET"
            assert url.startswith("https://mopsov.twse.com.tw/server-java/FileDownLoad?")
            self.calls += 1
            return Response(next(self.bodies))

    url = "https://mopsov.twse.com.tw/server-java/FileDownLoad?co_id=5314"
    security_page = b"<!DOCTYPE html><html><title>Security check</title></html>"
    with pytest.raises(FilingUnexpectedResponseError):
        _bounded_request(Client([security_page]), "GET", url)

    provider = "MOPS unexpected-body fixture"
    client = Client([security_page, filing()])
    try:
        monkeypatch.setenv("PROVIDER_RETRY_ATTEMPTS", "2")
        monkeypatch.setenv("PROVIDER_RETRY_BACKOFF_SECONDS", "0")
        monkeypatch.setenv("PROVIDER_RETRY_BACKOFF_MAX_SECONDS", "0")
        monkeypatch.setenv("PROVIDER_RETRY_JITTER_SECONDS", "0")
        assert provider_resilience.call_provider_with_resilience(
            provider, lambda: _bounded_request(client, "GET", url)) == filing()
        assert client.calls == 2
        assert provider_resilience.provider_circuit_state(provider)["open"] is False
    finally:
        provider_resilience.clear_provider_circuits(provider)


def test_filing_retries_one_transient_502_without_repeating_other_documents(monkeypatch):
    class Response:
        def __init__(self, status, raw=b""):
            self.status_code, self.raw = status, raw

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def iter_bytes(self):
            yield self.raw

    class Client:
        def __init__(self, responses):
            self.responses, self.calls = iter(responses), 0

        def stream(self, *_args, **_kwargs):
            self.calls += 1
            return next(self.responses)

    monkeypatch.setattr("data_fetch.market_sources.official_xbrl_financial.time.sleep", lambda _s: None)
    url = "https://mopsov.twse.com.tw/server-java/FileDownLoad?co_id=5314"
    client = Client([Response(502), Response(200, filing())])
    assert _fetch_filing_document(client, url) == filing()
    assert client.calls == 2

    rate_limited = Client([Response(429), Response(200, filing())])
    with pytest.raises(FilingTransportError, match="MOPS HTTP 429"):
        _fetch_filing_document(rate_limited, url)
    assert rate_limited.calls == 1


def test_mops_index_retries_one_transient_connection_or_503(monkeypatch):
    import httpx
    from data_fetch.market_sources.official_xbrl_financial import _fetch_index_response

    monkeypatch.setattr("data_fetch.market_sources.official_xbrl_financial.time.sleep", lambda _s: None)
    calls = []

    def request(_client, method, url, *, data=None):
        calls.append((method, url, data))
        if len(calls) == 1:
            raise httpx.ConnectError("temporary")
        return b"valid index"

    assert _fetch_index_response(object(), {"co_id": "5314"}, request=request) == b"valid index"
    assert len(calls) == 2

    def rate_limited(_client, method, url, *, data=None):
        raise FilingTransportError("MOPS HTTP 429")

    with pytest.raises(FilingTransportError, match="429"):
        _fetch_index_response(object(), {"co_id": "5314"}, request=rate_limited)


def test_full_five_year_fetch_does_not_redownload_prior_year_after_one_502(monkeypatch):
    import collections
    import data_fetch.market_sources.official_xbrl_financial as source

    urls = {year: f"https://mopsov.twse.com.tw/filing/{year}" for year in range(2021, 2026)}
    calls = collections.Counter()

    def request(_client, method, url, *, data=None):
        if method == "POST":
            return b"index"
        year = int(url.rsplit("/", 1)[1])
        calls[year] += 1
        if year == 2023 and calls[year] == 1:
            raise source.FilingTransientResponseError("MOPS HTTP 502")
        return filing(year)

    monkeypatch.setattr(source, "_filing_urls", lambda _index, _issuer: urls)
    monkeypatch.setattr(source, "_bounded_request", request)
    monkeypatch.setattr(source.time, "sleep", lambda _seconds: None)
    result = source.fetch_official_annual_histories("5314.TW", client=object())
    assert result["years"] == ["2021", "2022", "2023", "2024", "2025"]
    assert calls == {2021: 1, 2022: 1, 2023: 2, 2024: 1, 2025: 1}


def test_request_observer_counts_index_filings_and_local_retry_exactly(monkeypatch):
    import data_fetch.market_sources.official_xbrl_financial as source
    urls={year:f"https://mopsov.twse.com.tw/filing/{year}"for year in range(2021,2026)}
    monkeypatch.setattr(source,"_filing_urls",lambda _index,_issuer:urls)
    monkeypatch.setattr(source.time,"sleep",lambda _seconds:None)
    calls={};observations=[]
    class Response:
        def __init__(self,status,raw):self.status_code=status;self.raw=raw
        def __enter__(self):return self
        def __exit__(self,*_args):return False
        def iter_bytes(self):yield self.raw
    class Client:
        def stream(self,method,url,**_kwargs):
            if method=="POST":return Response(200,b"index")
            year=int(url.rsplit("/",1)[1]);calls[year]=calls.get(year,0)+1
            if year==2023 and calls[year]==1:return Response(502,b"temporary")
            return Response(200,filing(year))
    result=source.fetch_official_annual_histories("5314.TW",client=Client(),request_observer=observations.append)
    assert result["years"]==["2021","2022","2023","2024","2025"]
    assert len(observations)==7
    assert [row.get("http_status")for row in observations]==[200,200,200,502,200,200,200]
    assert all(row["http_request_sent"]is True for row in observations)


def test_one_transient_filing_uses_comparison_year_but_later_xbrl_restates_it(monkeypatch):
    import data_fetch.market_sources.official_xbrl_financial as source

    urls = {year: f"https://mopsov.twse.com.tw/filing/{year}" for year in range(2021, 2026)}
    prior_contexts = '''<xbrli:context id="prior-duration"><xbrli:entity><xbrli:identifier
    scheme="http://www.twse.com.tw">5314</xbrli:identifier></xbrli:entity><xbrli:period>
    <xbrli:startDate>2022-01-01</xbrli:startDate><xbrli:endDate>2022-12-31</xbrli:endDate>
    </xbrli:period></xbrli:context><xbrli:context id="prior-instant"><xbrli:entity>
    <xbrli:identifier scheme="http://www.twse.com.tw">5314</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2022-12-31</xbrli:instant></xbrli:period></xbrli:context>'''
    prior_facts = []
    for tag, value in TAGS.items():
        period = "prior-instant" if tag in {"Assets", "EquityAttributableToOwnersOfParent"} else "prior-duration"
        value = "2,000" if tag == "Revenue" else value
        sign = ' sign="-"' if tag == "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities" else ""
        prior_facts.append(f'<ix:nonFraction name="ifrs-full:{tag}" contextRef="{period}"{sign} '
                           f'unitRef="TWD" scale="3" decimals="-3" format="ixt:numdotdecimal">'
                           f'{value}</ix:nonFraction>')
    restated_2023 = filing(2023).replace(b"</html>",
                                           (prior_contexts + "".join(prior_facts) + "</html>").encode())
    recovered = []

    def download(_client, url):
        year = int(url.rsplit("/", 1)[1])
        if year == 2022:
            raise FilingUnexpectedResponseError("MOPS returned non-XBRL content with HTTP 200")
        return restated_2023 if year == 2023 else filing(year)

    def comparison(issuer, year):
        recovered.append((issuer, year))
        return {"facts": parse_annual_filing(filing(year), issuer, year),
                "documents": [{"year": year, "statement": statement,
                               "url": "https://mopsfin.twse.com.tw/compare/report", "sha256": "b" * 64}
                              for statement in ("IncomeStatement", "BalanceSheet", "CashflowStatement")]}

    monkeypatch.setattr(source, "_fetch_index_response", lambda *_args, **_kwargs: b"index")
    monkeypatch.setattr(source, "_filing_urls", lambda *_args: urls)
    monkeypatch.setattr(source, "_fetch_filing_document", download)
    monkeypatch.setattr(source, "fetch_official_comparison_year", comparison, raising=False)
    result = source.fetch_official_annual_histories("5314.TW", client=object())
    assert recovered == [("5314", 2022)]
    assert result["raw_twd_by_year"]["2022"]["revenue_history"] == 2_000_000
    assert result["comparative_revisions"][0]["kind"] == "restatement"
    assert result["recovered_documents"][0]["year"] == 2022


def test_comparison_year_requires_next_xbrl_comparative_for_older_filing(monkeypatch):
    import data_fetch.market_sources.official_xbrl_financial as source

    urls = {year: f"https://mopsov.twse.com.tw/filing/{year}" for year in range(2021, 2026)}
    monkeypatch.setattr(source, "_fetch_index_response", lambda *_args, **_kwargs: b"index")
    monkeypatch.setattr(source, "_filing_urls", lambda *_args: urls)
    monkeypatch.setattr(source, "_fetch_filing_document", lambda _client, url: (
        (_ for _ in ()).throw(FilingUnexpectedResponseError("temporary interstitial"))
        if url.endswith("/2022") else filing(int(url.rsplit("/", 1)[1]))))
    monkeypatch.setattr(source, "fetch_official_comparison_year", lambda issuer, year: {
        "facts": parse_annual_filing(filing(year), issuer, year),
        "documents": [{"year": year, "statement": statement,
                       "url": "https://mopsfin.twse.com.tw/compare/report", "sha256": "b" * 64}
                      for statement in ("IncomeStatement", "BalanceSheet", "CashflowStatement")]}, raising=False)
    with pytest.raises(FilingError, match="comparative"):
        source.fetch_official_annual_histories("5314.TW", client=object())


@pytest.mark.parametrize("error", [FilingError("invalid issuer filing"), FilingTransportError("MOPS HTTP 429")])
def test_comparison_source_never_bypasses_structural_or_rate_limit_failure(monkeypatch, error):
    import data_fetch.market_sources.official_xbrl_financial as source

    urls = {year: f"https://mopsov.twse.com.tw/filing/{year}" for year in range(2021, 2026)}
    monkeypatch.setattr(source, "_fetch_index_response", lambda *_args, **_kwargs: b"index")
    monkeypatch.setattr(source, "_filing_urls", lambda *_args: urls)

    def download(_client, url):
        if url.endswith("/2022"):
            raise error
        return filing(int(url.rsplit("/", 1)[1]))

    monkeypatch.setattr(source, "_fetch_filing_document", download)
    monkeypatch.setattr(source, "fetch_official_comparison_year",
                        lambda *_args: (_ for _ in ()).throw(AssertionError("fallback must stay unused")))
    with pytest.raises(type(error), match=str(error)):
        source.fetch_official_annual_histories("5314.TW", client=object())


def test_failed_comparison_recovery_does_not_retry_all_prior_years(monkeypatch):
    import data_fetch.market_sources.official_xbrl_financial as source
    from data_fetch.market_sources.official_mopsfin_financial import MopsFinError
    from source_audit import audited_fetch

    urls = {year: f"https://mopsov.twse.com.tw/filing/{year}" for year in range(2021, 2026)}
    calls = []
    monkeypatch.setattr(source, "_fetch_index_response", lambda *_args, **_kwargs: b"index")
    monkeypatch.setattr(source, "_filing_urls", lambda *_args: urls)

    def download(_client, url):
        calls.append(url)
        if url.endswith("/2022"):
            raise FilingUnexpectedResponseError("temporary interstitial")
        return filing(int(url.rsplit("/", 1)[1]))

    monkeypatch.setattr(source, "_fetch_filing_document", download)
    monkeypatch.setattr(source, "fetch_official_comparison_year",
                        lambda *_args: (_ for _ in ()).throw(MopsFinError("取得無形資產 absent")))
    result = audited_fetch("financial_statements", PROVIDER,
                           lambda: source.fetch_official_annual_histories("5314.TW", client=object()), default=None)
    assert result["audit"]["status"] == "error"
    assert "取得無形資產" in result["audit"]["message"]
    assert len(calls) == 2


def test_transient_security_page_retries_only_the_current_filing():
    import httpx

    responses = iter((b"<html>Security check</html>", filing()))
    calls = []
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=next(responses))

    url = "https://mopsov.twse.com.tw/server-java/FileDownLoad?co_id=5314"
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert _fetch_filing_document(client, url) == filing()
    assert calls == [url, url]


def test_persistent_security_page_still_fails_closed_after_bounded_retry():
    import httpx

    calls = []
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=b"<html>Security check</html>")

    url = "https://mopsov.twse.com.tw/server-java/FileDownLoad?co_id=5314"
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(FilingUnexpectedResponseError):
            _fetch_filing_document(client, url)
    assert calls == [url, url]


def test_xml_prolog_security_page_with_doctype_retries_current_document_only():
    import httpx

    security_page = b'<?xml version="1.0"?><!DOCTYPE html><html><title>Security check</title></html>'
    responses = iter((security_page, filing()))
    calls = []
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=next(responses))

    url = "https://mopsov.twse.com.tw/server-java/FileDownLoad?co_id=5314"
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert _fetch_filing_document(client, url) == filing()
    assert calls == [url, url]


def test_positive_purchase_cannot_inflate_free_cash_flow():
    raw = filing().replace(b'sign="-" ', b'')
    with pytest.raises(FilingError, match="cash outflow sign"):
        parse_annual_filing(raw, "5314", 2025)


def test_complete_later_comparative_supersedes_entire_prior_year_with_revision_record():
    old = parse_annual_filing(filing(2023), "5314", 2023)
    revised = dict(old, GrossProfit=old["GrossProfit"] + 1000)
    rows, revisions = reconcile_comparative_rows({2023: old}, {2023: revised})
    assert rows[2023] == revised
    assert revisions == [{"year": 2023, "fact": "GrossProfit", "original_twd": old["GrossProfit"],
                          "revised_twd": revised["GrossProfit"], "original_filing_year": 2023,
                          "comparative_filing_year": 2024, "kind": "restatement"}]
    with pytest.raises(FilingError, match="incomplete comparative"):
        reconcile_comparative_rows({2023: old}, {2023: {"GrossProfit": revised["GrossProfit"]}})


def test_official_success_is_audited_and_skips_partial_sdk(monkeypatch):
    import data_fetch.yfinance_extractors as extractors
    import data_fetch.official_financial_gap_cache as boundary
    legacy=boundary.fetch_official_financial_result
    monkeypatch.setattr(boundary,'fetch_official_financial_result',lambda ticker:legacy(ticker,fetcher=extractors.fetch_official_annual_histories))

    class UnusedStock:
        def __getattr__(self, name):
            raise AssertionError(f"unexpected SDK read: {name}")

    facts = {year: parse_annual_filing(filing(year), "5314", year) for year in range(2021, 2026)}
    value = assemble_annual_histories(facts, expected_years=list(facts))
    value.update(source_url="https://mopsov.twse.com.tw/mops/web/ajax_t203sb01",
                 comparative_revisions=[],
                 documents=[{"year": year, "url": f"https://mopsov.twse.com.tw/{year}", "sha256": "a" * 64}
                            for year in facts])
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(extractors, "fetch_official_annual_histories", lambda ticker: value)
    notes = []
    result = extractors.extract_financial_histories(UnusedStock(), "5314.TWO", notes)
    assert result["years"] == ["2021", "2022", "2023", "2024", "2025"]
    assert result["primary_financial_audit"] is None
    assert result["official_financial_audit"]["status"] == "success"
    assert result["official_financial_audit"]["record_count"] == 5
    assert result["official_financial_audit"]["raw_twd_by_year"]["2025"]["free_cash_flow"] == 350000
    from provider_observation_details import observation_details
    persisted = observation_details(result["official_financial_audit"])
    assert len(persisted["component_statuses"]) == 5
    assert persisted["component_statuses"]["filing_2025"]["response_sha256"] == "a" * 64
    assert notes and "XBRL" in notes[0]
    from data_fetch import yfinance_payload as payload
    monkeypatch.setattr(payload, "set_cache_json", lambda *_args: None)
    data = payload.finalize_and_cache_legacy_payload(
        data={"ticker": "5314.TWO", "current_price": 1, "data_source_notes": notes,
              **{key: result[key] for key in ("years", "revenue_history", "net_income_history", "gross_profit_history",
              "operating_income_history", "fcf_history", "total_assets_history", "total_equity_history")}},
        ticker="5314.TWO", original_cache_key="test:xbrl", provider=SimpleNamespace(name="fixture"),
        fetch_started_epoch=time.time(), skip_optional_http=True, enrichment_audit=[],
        fmp_quote_audit=None, monthly_revenue_audit=None, finmind_financial_fallback_audit=None,
        primary_financial_audit=None, official_financial_audit=result["official_financial_audit"],
    )
    assert data["source_audit"][-1]["provider"] == "TWSE MOPS official consolidated iXBRL"


def test_comparison_recovery_is_visible_in_financial_audit(monkeypatch):
    import data_fetch.yfinance_extractors as extractors
    import data_fetch.official_financial_gap_cache as boundary
    legacy=boundary.fetch_official_financial_result
    monkeypatch.setattr(boundary,'fetch_official_financial_result',lambda ticker:legacy(ticker,fetcher=extractors.fetch_official_annual_histories))
    from data_fetch.market_sources.official_mopsfin_financial import PROVIDER as comparison_provider

    facts = {year: parse_annual_filing(filing(year), "5314", year) for year in range(2021, 2026)}
    value = assemble_annual_histories(facts, expected_years=list(facts))
    value.update(
        source_url="https://mopsov.twse.com.tw/mops/web/ajax_t203sb01",
        comparative_revisions=[],
        recovered_documents=[{"year": 2022, "error_kind": "FilingUnexpectedResponseError",
                              "documents": [{"year": 2022, "sha256": "b" * 64}]}],
        documents=[{"year": year, "url": f"https://mopsov.twse.com.tw/{year}",
                    "sha256": "a" * 64, **({"provider": comparison_provider} if year == 2022 else {})}
                   for year in facts],
    )
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(extractors, "fetch_official_annual_histories", lambda _ticker: value)
    notes = []
    result = extractors.extract_financial_histories(object(), "5314.TWO", notes)
    audit = result["official_financial_audit"]
    assert audit["status"] == "success"
    assert audit["component_statuses"]["filing_2022"]["provider"] == comparison_provider
    assert audit["component_statuses"]["filing_2023"]["provider"] == PROVIDER
    assert audit["recovered_documents"][0]["year"] == 2022
    assert audit["source_mix"] == "xbrl_with_official_comparison_recovery"
    assert "財務比較站" in audit["message"]
    assert "2022" in notes[0] and "比較列" in notes[0]


def test_official_failure_keeps_failure_audit_and_sdk_values(monkeypatch):
    import data_fetch.yfinance_extractors as extractors
    import data_fetch.official_financial_gap_cache as boundary
    legacy=boundary.fetch_official_financial_result
    monkeypatch.setattr(boundary,'fetch_official_financial_result',lambda ticker:legacy(ticker,fetcher=extractors.fetch_official_annual_histories))
    from test_financial_statement_observation import StatementStock

    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    def broken(_ticker):
        raise FilingError("synthetic unavailable")
    monkeypatch.setattr(extractors, "fetch_official_annual_histories", broken)
    result = extractors.extract_financial_histories(StatementStock(), "5314.TWO", [], data_loader_cls=None)
    assert result["official_financial_audit"]["status"] == "error"
    assert result["primary_financial_audit"]["status"] == "success"
    assert result["revenue_history"] == [1.0, 2.0]


def test_issuer_filing_error_does_not_block_other_issuers(monkeypatch):
    import provider_resilience
    from source_audit import audited_fetch

    provider_resilience.clear_provider_circuits(PROVIDER)
    monkeypatch.setenv("PROVIDER_CIRCUIT_BREAKER_THRESHOLD", "1")
    monkeypatch.setenv("PROVIDER_RETRY_ATTEMPTS", "1")
    try:
        def invalid_issuer():
            raise FilingError("issuer-specific incomplete annual facts")

        failed = audited_fetch("financial_statements", PROVIDER, invalid_issuer, default=None)
        assert failed["audit"]["status"] == "error"
        assert provider_resilience.provider_circuit_state(PROVIDER)["open"] is False
        next_issuer = audited_fetch("financial_statements", PROVIDER, lambda: {"years": ["2025"]})
        assert next_issuer["audit"]["status"] == "success"

        def service_failure():
            raise FilingTransportError("MOPS HTTP 503")

        audited_fetch("financial_statements", PROVIDER, service_failure, default=None)
        assert provider_resilience.provider_circuit_state(PROVIDER)["open"] is True
    finally:
        provider_resilience.clear_provider_circuits(PROVIDER)


@pytest.mark.parametrize("industry", ["Financial Services Banks - Regional",
                                      "Financial Services Capital Markets", "金融保險業"])
def test_financial_sector_does_not_attempt_inapplicable_industrial_taxonomy(monkeypatch, industry):
    import data_fetch.yfinance_extractors as extractors
    from test_financial_statement_observation import StatementStock

    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(extractors, "fetch_official_annual_histories",
                        lambda _ticker: (_ for _ in ()).throw(AssertionError("bank should skip industrial taxonomy")))
    result = extractors.extract_financial_histories(
        StatementStock(), "2882.TW", [], data_loader_cls=None,
        industry_context=industry)
    assert result["official_financial_audit"] is None
    assert result["primary_financial_audit"]["status"] == "success"


def test_current_master_classification_supplies_missing_yahoo_financial_sector(monkeypatch):
    from datetime import date
    from data_fetch.market_sources.peer_recovery import current_master_industry_categories
    from data_fetch import yfinance_extractors as extractors
    from test_financial_statement_observation import StatementStock

    today = date(2026, 10, 4)
    rows = [{"stock_id": "2882", "stock_name": "國泰金", "type": "twse",
             "industry_category": "金融保險", "date": "2026-10-03"}]
    categories = current_master_industry_categories("2882.TW", rows, today=today)
    assert categories == ["金融保險"]
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(extractors, "fetch_official_annual_histories",
                        lambda _ticker: (_ for _ in ()).throw(AssertionError("bank should skip industrial taxonomy")))
    result = extractors.extract_financial_histories(
        StatementStock(), "2882.TW", [], data_loader_cls=None,
        industry_context=" ".join(["", "", *categories]))
    assert result["official_financial_audit"] is None
    assert result["primary_financial_audit"]["status"] == "success"


def test_master_financial_classification_rejects_stale_or_wrong_market():
    from datetime import date
    from data_fetch.market_sources.peer_recovery import current_master_industry_categories

    today = date(2026, 10, 4)
    recent = {"stock_id": "2882", "stock_name": "國泰金", "type": "twse",
              "industry_category": "金融保險業", "date": "2026-10-03"}
    assert current_master_industry_categories("2882.TW", [{**recent, "date": "2026-09-01"}], today=today) == []
    assert current_master_industry_categories("2882.TWO", [recent], today=today) == []
    assert current_master_industry_categories("2881.TW", [recent], today=today) == []
