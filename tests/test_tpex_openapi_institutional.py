"""The current TPEx OpenAPI row is an exact dated alternative to dailyTrade."""

import json

import pytest


ROW = {
    "Date": "1151008", "SecuritiesCompanyCode": "5314", "CompanyName": "世紀*",
    "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Total Buy": "2937290",
    " Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Total Sell": "5445607",
    "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Difference": "-2508317",
    "Foreign Dealers-Total Buy": "0", "Foreign Dealers-TotalSell": "0", "ForeignDealers-Difference": "0",
    "ForeignInvestorsIncludeMainlandAreaInvestors-TotalBuy": "2937290",
    "ForeignInvestorsIncludeMainlandAreaInvestors-TotalSell": "5445607",
    "ForeignInvestorsInclude MainlandAreaInvestors-Difference": "-2508317",
    "SecuritiesInvestmentTrustCompanies-TotalBuy": "0",
    "SecuritiesInvestmentTrustCompanies-TotalSell": "0",
    "SecuritiesInvestmentTrustCompanies-Difference": "0",
    "Dealers-TotalBuy": "9000", "Dealers-TotalSell": "70862", "Dealers-Difference": "-61862",
    "Dealers -TotalSell": "70862", "TotalDifference": "-2570179",
}


def test_exact_openapi_fields_and_shares_produce_dated_report():
    from tpex_openapi_institutional import parse_latest_report

    report = parse_latest_report(json.dumps([ROW]).encode(), "2026-10-08")
    assert report["date"] == "2026-10-08"
    assert report["rows"]["5314"] == {
        "company_name": "世紀*", "foreign": -2508317,
        "investment_trust": 0, "dealer": -61862,
    }


@pytest.mark.parametrize("mutation", [
    {"Date": "1151007"},
    {"TotalDifference": "-2570178"},
    {"Dealers-TotalSell": "70863"},
    {"ForeignInvestorsInclude MainlandAreaInvestors-Difference": "-2508316"},
    {"CompanyName": ""},
    {"CompanyName": 5314},
    {"SecuritiesCompanyCode": 5314},
    {"Dealers -TotalSell": "-1"},
])
def test_openapi_rejects_mismatched_date_totals_or_identity(mutation):
    from tpex_openapi_institutional import parse_latest_report

    with pytest.raises(ValueError):
        parse_latest_report(json.dumps([{**ROW, **mutation}]).encode(), "2026-10-08")


def test_openapi_rejects_duplicate_code_or_changed_schema():
    from tpex_openapi_institutional import parse_latest_report

    with pytest.raises(ValueError):
        parse_latest_report(json.dumps([ROW, ROW]).encode(), "2026-10-08")
    with pytest.raises(ValueError):
        parse_latest_report(json.dumps([{k: v for k, v in ROW.items() if k != "TotalDifference"}]).encode(),
                            "2026-10-08")


def test_latest_tpex_session_prefers_openapi_and_falls_back_to_dated_report(monkeypatch):
    import official_institutional_source as source

    monkeypatch.setattr(source, "expected_sessions", lambda *_args: ["2026-10-08"])
    calls = []

    def fetch(market, day, timeout, *, openapi=False):
        calls.append((market, day, openapi))
        if openapi:
            raise TimeoutError("new endpoint temporarily unavailable")
        return {"date": day, "rows": {"5314": {"company_name": "世紀*", "foreign": -2508317,
                                                  "investment_trust": 0, "dealer": -61862}},
                "report_status": "available", "market": "TPEX", "source": source.TPEX_SOURCE}

    monkeypatch.setattr(source, "_fetch_report", fetch)
    value, audit = source.recover_institutional_observations(
        "5314.TWO", {}, now_epoch=1791475200.0, limit=1, force_refresh=True)
    assert calls == [("TPEX", "2026-10-08", True), ("TPEX", "2026-10-08", False)]
    assert value["latest_date"] == "2026-10-08"
    assert audit["reports"][0]["status"] == "available"
    assert value["net_buy_shares_by_category"]["foreign"] == -2508317


def test_latest_tpex_session_uses_openapi_row_without_dated_request(monkeypatch):
    import official_institutional_source as source
    from tpex_openapi_institutional import SOURCE, URL, parse_latest_report

    monkeypatch.setattr(source, "expected_sessions", lambda *_args: ["2026-10-08"])
    calls = []

    def fetch(market, day, timeout, *, openapi=False):
        calls.append((market, day, openapi))
        assert openapi is True
        return {**parse_latest_report(json.dumps([ROW]).encode(), day), "source_url": URL}

    monkeypatch.setattr(source, "_fetch_report", fetch)
    value, audit = source.recover_institutional_observations(
        "5314.TWO", {}, now_epoch=1791475200.0, limit=1, force_refresh=True)
    assert calls == [("TPEX", "2026-10-08", True)]
    assert audit["reports"][0]["source"] == SOURCE
    assert audit["reports"][0]["source_url"] == URL
    assert value["daily_category_observations"][0]["source"] == SOURCE
    assert value["latest_official_observation"]["source_url"] == URL


def test_provisional_tpex_session_does_not_probe_latest_only_openapi(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import official_institutional_source as source

    monkeypatch.setattr(source, "expected_sessions", lambda *_args: ["2026-10-08"])
    calls = []

    def fetch(market, day, timeout, *, openapi=False):
        calls.append(openapi)
        return {"date": day, "rows": {}, "report_status": "valid_empty", "market": market}

    monkeypatch.setattr(source, "_fetch_report", fetch)
    source.recover_institutional_observations(
        "5314.TWO", {}, now_epoch=datetime(2026, 10, 8, 14, tzinfo=ZoneInfo("Asia/Taipei")).timestamp(),
        limit=1, force_refresh=True)
    assert calls == [False]


def test_archived_openapi_row_passes_latest_session_admission_only_with_matching_bytes(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import runtime_paths
    from official_response_evidence import archive_response
    from report_source_admission import institutional_admission
    from tpex_openapi_institutional import URL

    monkeypatch.setattr(runtime_paths, "current_runtime_paths", lambda: SimpleNamespace(cache_dir=tmp_path))
    body = json.dumps([ROW]).encode()
    proof = archive_response(body, source_url=URL, retrieved_at="2026-10-08T16:03:00+00:00")
    value = {
        "latest_date": "2026-10-08",
        "daily_category_observations": [
            {"date": "2026-10-08", "category": category, "net_buy_shares": shares, "unit": "shares"}
            for category, shares in (("foreign", -2508317), ("investment_trust", 0), ("dealer", -61862))
        ],
        "latest_official_observation": {
            "date": "2026-10-08", "market": "TPEX", "ticker": "5314.TWO", "raw_evidence": proof,
        },
    }
    assert institutional_admission(value, "2026-10-08")["eligible"] is True
    value["daily_category_observations"][0]["net_buy_shares"] += 1
    assert institutional_admission(value, "2026-10-08")["reason"] == "primary_official_latest_categories_mismatch"
