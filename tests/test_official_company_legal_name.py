"""Official company profiles may identify an employer, not prove job availability."""

from datetime import date
import json


LISTED = {"出表日期": "1151003", "公司代號": "2882", "公司名稱": "國泰金融控股股份有限公司",
          "公司簡稱": "國泰金", "營利事業統一編號": "70827406"}
OTC = {"Date": "1151004", "SecuritiesCompanyCode": "5314",
       "CompanyName": "世紀民生科技股份有限公司", "CompanyAbbreviation": "世紀*",
       "UnifiedBusinessNo.": "22099815"}


def test_official_roster_matches_market_code_short_name_and_current_date():
    from data_fetch.market_sources.official_company_legal_name import parse_roster, select_legal_name

    twse = parse_roster(json.dumps([LISTED]).encode(), ".TW")
    tpex = parse_roster(json.dumps([OTC]).encode(), ".TWO")
    assert select_legal_name(twse, "2882.TW", "國泰金", today=date(2026, 10, 4))["legal_name"] == "國泰金融控股股份有限公司"
    assert select_legal_name(twse, "2882.TW", "國泰金", today=date(2026, 10, 4))["official_ubn"] == "70827406"
    assert select_legal_name(tpex, "5314.TWO", "世紀*", today=date(2026, 10, 4))["legal_name"] == "世紀民生科技股份有限公司"
    assert select_legal_name(tpex, "5314.TWO", "世紀*", today=date(2026, 10, 4))["official_ubn"] == "22099815"
    assert select_legal_name(twse, "2882.TW", "國泰證", today=date(2026, 10, 4)) is None
    assert select_legal_name(tpex, "5314.TW", "世紀*", today=date(2026, 10, 4)) is None
    assert select_legal_name(twse, "2882.TW", "國泰金", today=date(2026, 11, 4)) is None


def test_conflicting_code_or_nonlegal_name_is_rejected():
    import pytest
    from data_fetch.market_sources.official_company_legal_name import parse_roster, select_legal_name

    with pytest.raises(ValueError, match="duplicate"):
        parse_roster(json.dumps([LISTED, LISTED]).encode(), ".TW")
    bad = {**LISTED, "公司名稱": "國泰金"}
    assert select_legal_name(parse_roster(json.dumps([bad]).encode(), ".TW"),
                             "2882.TW", "國泰金", today=date(2026, 10, 4)) is None
    no_tax_id = {**LISTED, "營利事業統一編號": "not-reported"}
    selected = select_legal_name(parse_roster(json.dumps([no_tax_id]).encode(), ".TW"),
                                 "2882.TW", "國泰金", today=date(2026, 10, 4))
    assert selected["legal_name"] == "國泰金融控股股份有限公司"
    assert selected["official_ubn"] is None


def test_stale_roster_is_not_used_to_anchor_employer_search(monkeypatch):
    from data_fetch.market_sources import official_company_legal_name as names

    payload = names.parse_roster(json.dumps([LISTED]).encode(), ".TW")
    monkeypatch.setattr(names, "shared_fetch", lambda key, callback, **kwargs: (
        payload, {"cache_hit": True, "stale": True, "error_kind": "ReadError"}))
    assert names.get_official_legal_name("2882.TW", "國泰金") is None


def test_market_roster_is_shared_across_issuers_even_for_report_refresh(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import official_company_legal_name as names

    second = {**LISTED, "公司代號": "2330", "公司名稱": "台灣積體電路製造股份有限公司",
              "公司簡稱": "台積電", "營利事業統一編號": "22099131"}
    payload = names.parse_roster(json.dumps([LISTED, second]).encode(), ".TW")
    calls = []
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(names, "_fetch_roster", lambda url, suffix: calls.append(url) or payload)
    monkeypatch.setattr(names, "_today", lambda: date(2026, 10, 4))
    try:
        a = names.get_official_legal_name("2882.TW", "國泰金")
        b = names.get_official_legal_name("2330.TW", "台積電")
        assert a["legal_name"] == "國泰金融控股股份有限公司"
        assert b["legal_name"] == "台灣積體電路製造股份有限公司"
        assert b["cache_hit"] is True
        assert len(calls) == 1
    finally:
        cache_store.reset_cache_store_for_tests()


def test_old_roster_cache_without_tax_id_does_not_mask_current_official_tax_id(monkeypatch):
    import hashlib
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import official_company_legal_name as names

    current = names.parse_roster(json.dumps([LISTED]).encode(), ".TW")
    legacy = names.parse_roster(json.dumps([{k: v for k, v in LISTED.items()
                                             if k != "營利事業統一編號"}]).encode(), ".TW")
    cache_store.set_cache_backend(InMemoryCache())
    old_key = "shared_provider:v1:" + hashlib.sha256(
        b"official-company-roster:v1:.TW").hexdigest()
    cache_store.set_cache_json(old_key, {
        "value": legacy, "fetched_at_epoch": 1,
        "fresh_until_epoch": 9999999999, "retained_until_epoch": 9999999999,
    }, ttl_seconds=3600)
    calls = []
    monkeypatch.setattr(names, "_fetch_roster", lambda url, suffix: calls.append(url) or current)
    monkeypatch.setattr(names, "_today", lambda: date(2026, 10, 4))
    try:
        selected = names.get_official_legal_name("2882.TW", "國泰金")
        assert selected["official_ubn"] == "70827406"
        assert calls == [names.URLS[".TW"]]
    finally:
        cache_store.reset_cache_store_for_tests()


def test_job_provider_uses_verified_official_legal_name_without_relaxing_posting_gate(monkeypatch):
    import alternative_data_fetcher
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import official_company_legal_name as names
    from data_fetch.types import FetchRequest

    legal = "國泰金融控股股份有限公司"
    calls = []
    monkeypatch.setattr(names, "get_official_legal_name", lambda ticker, short: {
        "legal_name": legal, "source_url": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "response_sha256": "a" * 64, "as_of": "2026-10-03", "cache_hit": False,
    })
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_company_jobs", lambda name: calls.append(name) or {
        "status": "unavailable", "job_count": None, "reason_code": "exact_employer_unverified"})
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_job_openings_count", lambda *a, **k: {
        "status": "unavailable", "job_count": None})
    monkeypatch.setattr(alternative_data_fetcher, "fetch_1111_job_openings_count", lambda *a, **k: {
        "status": "unavailable", "job_count": None})
    data = {"ticker": "2882.TW", "company_name": "國泰金", "quote_type": "EQUITY",
            "company_identity": {"ticker": "2882.TW", "official_name": "國泰金", "stock_id": "2882",
                                 "instrument_type": "EQUITY", "legal_name": None}}
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker("2882.TW"), {"data": data})

    assert calls == [legal]
    assert result.status == "degraded_enrichment"
    assert result.audit["record_count"] == 0
    assert result.audit["company_legal_name_basis"] == "official_company_profile"


def test_verified_posting_with_official_name_survives_data_trust_count(monkeypatch):
    from datetime import datetime, timezone
    import alternative_data_fetcher
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import official_company_legal_name as names
    from data_fetch.types import FetchRequest
    from data_trust import source_record_count

    legal = "國泰金融控股股份有限公司"
    stamp = datetime.now(timezone.utc)
    monkeypatch.setattr(names, "get_official_legal_name", lambda ticker, short: {
        "ticker": ticker, "official_short_name": short, "legal_name": legal,
        "source_url": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "response_sha256": "a" * 64, "as_of": stamp.date().isoformat(),
        "fetched_at_epoch": stamp.timestamp(), "cache_hit": False,
    })
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_company_jobs", lambda name: {
        "status": "success", "source": "104 Company Jobs API", "company_name": name,
        "evidence_kind": "company_job_postings", "query_scope": "exact_company_recent_postings",
        "source_url": "https://www.104.com.tw/jobs/search/api/jobs?kwop=2",
        "response_sha256": "b" * 64, "recent_company_job_count": 1, "job_count": None,
        "job_postings": [{"title": "財務分析師", "url": "https://www.104.com.tw/job/90fw6",
                          "employer": name, "employer_id": "12345678", "job_no": "15137142"}],
    })
    monkeypatch.setattr(alternative_data_fetcher, "fetch_1111_job_openings_count", lambda *a, **k: {
        "status": "unavailable", "job_count": None})
    data = {"ticker": "2882.TW", "company_name": "國泰金", "quote_type": "EQUITY",
            "company_identity": {"ticker": "2882.TW", "official_name": "國泰金", "stock_id": "2882",
                                 "instrument_type": "EQUITY", "legal_name": None}}
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker("2882.TW"), {"data": data})

    assert result.status == "success"
    assert result.audit["record_count"] == 1
    assert source_record_count("alternative_data", {**data, "alternative_data": result.value}) == 1
    for change in ({"ticker": "2881.TW"}, {"official_short_name": "國泰證"},
                   {"source_url": "https://example.invalid/company"},
                   {"response_sha256": "not-a-hash"}, {"stale": True}):
        tampered = {**result.value, "company_legal_name_evidence": {
            **result.value["company_legal_name_evidence"], **change,
        }}
        assert source_record_count("alternative_data", {**data, "alternative_data": tampered}) == 0


def test_official_short_name_and_tax_id_admit_104_alias_only_with_matching_receipt(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import alternative_data_fetcher
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import official_company_legal_name as names
    from data_fetch.types import FetchRequest
    from data_trust import source_record_count

    ticker, short, legal, ubn = "2330.TW", "台積電", "台灣積體電路製造股份有限公司", "22099131"
    now = datetime.now(ZoneInfo("Asia/Taipei"))
    receipt = {
        "ticker": ticker, "official_short_name": short, "legal_name": legal, "official_ubn": ubn,
        "source_url": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "response_sha256": "a" * 64, "as_of": now.date().isoformat(),
        "fetched_at_epoch": now.timestamp(), "cache_hit": False,
    }
    monkeypatch.setattr(names, "get_official_legal_name", lambda *args: receipt)
    calls = []

    def fake_company_jobs(name, **kwargs):
        calls.append((name, kwargs))
        return {"status": "success", "company_name": name, "job_count": None,
                "source": "104 Company Jobs API", "evidence_kind": "company_job_postings",
                "query_scope": "exact_company_recent_postings",
                "source_url": "https://www.104.com.tw/jobs/search/api/jobs?kwop=2",
                "response_sha256": "b" * 64, "recent_company_job_count": 1,
                "job_postings": [{"title": "製程工程師", "url": "https://www.104.com.tw/job/abc123",
                                  "employer": legal, "source_employer": legal + "(" + short + ")",
                                  "employer_match_basis": "official_name_ubn_alias",
                                  "employer_id": ubn + "000", "job_no": "12345678"}]}

    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_company_jobs", fake_company_jobs)
    monkeypatch.setattr(alternative_data_fetcher, "fetch_1111_job_openings_count", lambda *a, **k: {
        "status": "unavailable", "job_count": None})
    data = {"ticker": ticker, "company_name": short, "quote_type": "EQUITY",
            "company_identity": {"ticker": ticker, "official_name": short,
                                 "instrument_type": "EQUITY", "legal_name": None}}
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker(ticker), {"data": data})

    assert calls == [(legal, {"official_short_name": short, "official_ubn": ubn})]
    assert result.audit["record_count"] == 1
    prefix = {**result.value, "job_openings_104": {**result.value["job_openings_104"],
        "job_postings": [{**result.value["job_openings_104"]["job_postings"][0],
                          "source_employer": f"({short}){legal}",
                          "employer_match_basis": "official_name_ubn_prefix_alias"}]}}
    assert source_record_count("alternative_data", {**data, "alternative_data": prefix}) == 1
    prefix_bad_id = {**prefix, "job_openings_104": {**prefix["job_openings_104"],
        "job_postings": [{**prefix["job_openings_104"]["job_postings"][0],
                          "employer_id": ubn + "001"}]}}
    assert source_record_count("alternative_data", {**data, "alternative_data": prefix_bad_id}) == 0
    latin = {**result.value, "job_openings_104": {**result.value["job_openings_104"],
        "job_postings": [{**result.value["job_openings_104"]["job_postings"][0],
                          "source_employer": legal + " _TSMC INC.",
                          "employer_match_basis": "official_name_ubn_latin_suffix"}]}}
    assert source_record_count("alternative_data", {**data, "alternative_data": latin}) == 1
    latin_bad = {**latin, "job_openings_104": {**latin["job_openings_104"],
        "job_postings": [{**latin["job_openings_104"]["job_postings"][0],
                          "source_employer": legal + " _台積子公司"}]}}
    assert source_record_count("alternative_data", {**data, "alternative_data": latin_bad}) == 0
    for evidence_change, job_change in (({"official_ubn": "12345678"}, {}),
                                         ({}, {"source_employer": legal + "(別家公司)"}),
                                         ({}, {"employer_id": ubn + "001"})):
        tampered = {**result.value,
                    "company_legal_name_evidence": {**receipt, **evidence_change},
                    "job_openings_104": {**result.value["job_openings_104"],
                                         "job_postings": [{**result.value["job_openings_104"]["job_postings"][0],
                                                           **job_change}]}}
        assert source_record_count("alternative_data", {**data, "alternative_data": tampered}) == 0


def test_verified_company_endpoint_fallback_counts_only_checked_job_identity(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import alternative_data_fetcher
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import official_company_legal_name as names
    from data_fetch.types import FetchRequest
    from data_trust import source_record_count

    ticker, short, legal, ubn = "2002.TW", "中鋼", "中國鋼鐵股份有限公司", "30414175"
    now = datetime.now(ZoneInfo("Asia/Taipei"))
    receipt = {"ticker": ticker, "official_short_name": short, "legal_name": legal,
               "official_ubn": ubn,
               "source_url": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
               "response_sha256": "a" * 64, "as_of": now.date().isoformat(),
               "fetched_at_epoch": now.timestamp()}
    monkeypatch.setattr(names, "get_official_legal_name", lambda *args: receipt)
    calls = []
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_company_jobs",
                        lambda *a, **k: calls.append("search") or {"status": "unavailable"})
    posting = {"title": "研發替代役", "url": "https://www.104.com.tw/job/965f7",
               "published_date": now.date().isoformat(), "employer": legal,
               "source_employer": legal, "employer_match_basis": "official_name_ubn_company_api",
               "employer_id": "30414175000", "source_employer_id": "dyztbmg",
               "job_no": "15403507", "source_job_no": "965f7"}
    def company_api(name, tax_id, **kwargs):
        calls.append((name, tax_id, kwargs))
        return {"status": "success", "source": "104 Company Jobs API",
                "company_name": name, "evidence_kind": "company_job_postings",
                "query_scope": "exact_company_recent_postings",
                "source_url": "https://www.104.com.tw/api/companies/dyztbmg/jobs",
                "response_sha256": "b" * 64, "recent_company_job_count": 1,
                "job_count": None, "job_postings": [posting]}
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_company_jobs_by_ubn", company_api, raising=False)
    monkeypatch.setattr(alternative_data_fetcher, "fetch_1111_job_openings_count",
                        lambda *a, **k: {"status": "unavailable", "job_count": None})
    data = {"ticker": ticker, "company_name": short, "quote_type": "EQUITY",
            "company_identity": {"ticker": ticker, "official_name": short,
                                 "instrument_type": "EQUITY", "legal_name": None}}
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker(ticker), {"data": data})
    assert calls == ["search", (legal, ubn, {"official_short_name": short})]
    assert result.status == "success"
    assert source_record_count("alternative_data", {**data, "alternative_data": result.value}) == 1
    for change in ({"source_employer_id": "dyztbmh"}, {"source_job_no": "965f8"},
                   {"source_employer": "中國鋼鐵結構股份有限公司"},
                   {"published_date": "2020-01-01"}):
        tampered = {**result.value, "job_openings_104": {**result.value["job_openings_104"],
            "job_postings": [{**posting, **change}]}}
        assert source_record_count("alternative_data", {**data, "alternative_data": tampered}) == 0
