"""The issuer's own open jobs must survive the alternative-data evidence gate."""

import hashlib
import json
from datetime import datetime, timezone


def _payload(rows):
    return {"MWHEADER": {"MSGID": "EZM-C-JOBLISTQ001", "RETURNCODE": "0000", "TXNSEQ": "test-sequence"},
            "TRANRS": {"JOB_LIST": rows}}


def _job(code="C0", number="I00026783", *, open="Y", submit="Y"):
    return {"APPL_FORM_NO": number, "JOB_TITLE": "雲端技術實習生", "JOB_DESCRIPTION": "後端開發",
            "COMPANY_NAME": "COMPANY_SIMPLE_" + code, "COMPANY_LIST": [code],
            "IS_OPEN": open, "CAN_SUBMIT": submit}


def test_official_career_parser_keeps_only_open_exact_holding_company_jobs():
    from data_fetch.market_sources.cathay_careers import parse_career_listing

    raw = json.dumps(_payload([_job(), _job("01", "I00026851"),
                               _job(number="I00026784", open="N"),
                               _job(number="I00026785", submit="N")])).encode()
    result = parse_career_listing(raw, "test-sequence", fetched_at_epoch=1791110000)
    assert result["status"] == "success"
    assert result["current_open_job_count"] == 1
    assert result["job_postings"][0]["url"] == "https://recruit.cathayholdings.com/iMatch/job/info/I00026783"
    assert result["response_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["rejected_count"] == 3


def test_official_career_parser_rejects_malformed_or_empty_as_success():
    import pytest
    from data_fetch.market_sources.cathay_careers import parse_career_listing

    with pytest.raises(ValueError):
        parse_career_listing(json.dumps(_payload([_job()])).encode(), "wrong", fetched_at_epoch=1791110000)
    empty = parse_career_listing(json.dumps(_payload([_job("01")])).encode(),
                                 "test-sequence", fetched_at_epoch=1791110000)
    assert empty["status"] == "unavailable"
    assert empty["current_open_job_count"] is None


def test_2882_provider_counts_verified_official_jobs_and_rejects_subsidiary(monkeypatch):
    import alternative_data_fetcher
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import cathay_careers
    from data_fetch.types import FetchRequest
    from data_trust import source_record_count

    raw = json.dumps(_payload([_job(), _job("01", "I00026851")])).encode()
    monkeypatch.setattr(cathay_careers, "_download", lambda request: raw)
    monkeypatch.setattr(cathay_careers, "_sequence", lambda: "test-sequence")
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_company_jobs", lambda name: {"status": "unavailable"})
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_job_openings_count", lambda *a, **k: {"status": "unavailable"})
    monkeypatch.setattr(alternative_data_fetcher, "fetch_1111_job_openings_count", lambda *a, **k: {"status": "unavailable"})
    data = {"ticker": "2882.TW", "company_name": "國泰金", "quote_type": "EQUITY",
            "company_identity": {"ticker": "2882.TW", "official_name": "國泰金", "stock_id": "2882",
                                 "instrument_type": "EQUITY", "legal_name": "國泰金融控股股份有限公司"}}
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker("2882.TW"), {"data": data})
    assert result.status == "success"
    assert result.value["job_openings_official"]["current_open_job_count"] == 1
    assert result.audit["record_count"] == 1
    assert source_record_count("alternative_data", {**data, "alternative_data": result.value}) == 1
    forged = {**result.value, "job_openings_official": {**result.value["job_openings_official"],
              "job_postings": [_job("01", "I00026851")]}}
    assert source_record_count("alternative_data", {**data, "alternative_data": forged}) == 0
    for altered in (
        {"company_identity": {**data["company_identity"], "ticker": "2881.TW"}},
        {"company_identity": {**data["company_identity"], "instrument_type": "FUND"}},
        {"quote_type": "FUND"},
    ):
        assert source_record_count("alternative_data", {**data, **altered, "alternative_data": result.value}) == 0


def test_non_2882_issuer_never_calls_official_cathay_source(monkeypatch):
    import alternative_data_fetcher
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import cathay_careers
    from data_fetch.types import FetchRequest

    monkeypatch.setattr(cathay_careers, "fetch_official_cathay_jobs", lambda ticker: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_company_jobs", lambda name: {"status": "unavailable"})
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_job_openings_count", lambda *a, **k: {"status": "unavailable"})
    monkeypatch.setattr(alternative_data_fetcher, "fetch_1111_job_openings_count", lambda *a, **k: {"status": "unavailable"})
    data = {"ticker": "2883.TW", "company_name": "開發金", "quote_type": "EQUITY",
            "company_identity": {"ticker": "2883.TW", "official_name": "開發金", "stock_id": "2883",
                                 "instrument_type": "EQUITY", "legal_name": "開發金融控股股份有限公司"}}
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker("2883.TW"), {"data": data})
    assert result.status == "degraded_enrichment"


def test_official_careers_with_exchange_legal_name_evidence(monkeypatch):
    import alternative_data_fetcher
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import cathay_careers, official_company_legal_name
    from data_fetch.types import FetchRequest
    from data_trust import source_record_count

    now = datetime.now(timezone.utc).timestamp()
    monkeypatch.setattr(cathay_careers, "_download", lambda request: json.dumps(_payload([_job()])).encode())
    monkeypatch.setattr(cathay_careers, "_sequence", lambda: "test-sequence")
    monkeypatch.setattr(official_company_legal_name, "get_official_legal_name", lambda ticker, short: {
        "ticker": ticker, "official_short_name": short, "legal_name": "國泰金融控股股份有限公司",
        "source_url": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "response_sha256": "a" * 64, "as_of": datetime.now(timezone.utc).date().isoformat(),
        "fetched_at_epoch": now, "stale": False,
    })
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_company_jobs", lambda name: {"status": "unavailable"})
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_job_openings_count", lambda *a, **k: {"status": "unavailable"})
    monkeypatch.setattr(alternative_data_fetcher, "fetch_1111_job_openings_count", lambda *a, **k: {"status": "unavailable"})
    data = {"ticker": "2882.TW", "company_name": "國泰金", "quote_type": "EQUITY",
            "company_identity": {"ticker": "2882.TW", "official_name": "國泰金", "stock_id": "2882",
                                 "instrument_type": "EQUITY", "legal_name": None}}
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker("2882.TW"), {"data": data})
    assert result.status == "success"
    assert source_record_count("alternative_data", {**data, "alternative_data": result.value}) == 1
    bad = {**result.value, "company_legal_name_evidence": {**result.value["company_legal_name_evidence"],
           "official_short_name": "國泰證"}}
    assert source_record_count("alternative_data", {**data, "alternative_data": bad}) == 0
