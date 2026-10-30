from datetime import date
import json

from data_fetch.annual_occupational_safety import (
    PROVIDER, URLS, parse_occupational_safety_dataset,
    verified_occupational_safety_observation,
)
from data_fetch.annual_workforce_provider import AnnualWorkforceProvider
from data_fetch.types import FetchRequest


def _row(code="2330", **overrides):
    return {
        "出表日期": "1151016", "報告年度": "114", "公司代號": code, "公司名稱": "台積電",
        "職業災害人數及比率-人數": "0", "職業災害人數及比率-比率": "0.00%",
        "火災件數(件)": "2", "火災死傷人數(人)": "1",
        "火災死傷人數占員工總人數比率": "0.01%", **overrides,
    }


def test_parser_preserves_official_zeroes_and_normalizes_reported_rates():
    observation = parse_occupational_safety_dataset(
        json.dumps([_row()]).encode(), "2330.TW", today=date(2026, 10, 17))

    assert observation["report_year"] == 2025
    assert observation["published_on"] == "2026-10-16"
    assert observation["source_url"] == URLS[".TW"]
    assert observation["source"] == PROVIDER
    assert observation["metrics"] == {
        "occupational_injury_count": 0,
        "fire_incident_count": 2,
        "fire_casualty_count": 1,
        "occupational_injury_rate_percent": 0,
        "fire_casualty_rate_percent": 0.01,
    }
    observation["status"] = "success"
    assert verified_occupational_safety_observation(observation, "2330.TW", today=date(2026, 10, 17))


def test_parser_rejects_wrong_duplicate_stale_or_malformed_rows():
    today = date(2026, 10, 17)
    assert parse_occupational_safety_dataset(json.dumps([_row("2317")]).encode(), "2330.TW", today=today) is None
    assert parse_occupational_safety_dataset(json.dumps([_row(), _row()]).encode(), "2330.TW", today=today) is None
    old = _row(**{"報告年度": "110", "出表日期": "1110301"})
    assert parse_occupational_safety_dataset(json.dumps([old]).encode(), "2330.TW", today=today) is None
    invalid = _row(**{"火災件數(件)": "NaN"})
    assert parse_occupational_safety_dataset(json.dumps([invalid]).encode(), "2330.TW", today=today) is None
    unknown = _row(**{"職業災害人數及比率-人數": "", "職業災害人數及比率-比率": "",
                      "火災件數(件)": "", "火災死傷人數(人)": "",
                      "火災死傷人數占員工總人數比率": ""})
    assert parse_occupational_safety_dataset(json.dumps([unknown]).encode(), "2330.TW", today=today) is None


def test_provider_attaches_audited_occupational_safety_without_mixing_job_counts(monkeypatch):
    import data_fetch.annual_workforce_provider as workforce
    from data_trust import source_record_count
    from agent_runtime.prompting import data_for_agent_prompt

    workforce_row = {
        "出表日期": "1151016", "報告年度": "114", "公司代號": "2330", "公司名稱": "台積電",
        "員工薪資平均數(仟元/人) ": "4093",
        "非擔任主管之全時員工薪資中位數(仟元/人) ": "3162",
        "管理職女性主管佔比": "15.00%",
    }
    responses = {
        URLS[".TW"]: json.dumps([_row()]),
        "https://openapi.twse.com.tw/v1/opendata/t187ap46_L_5": json.dumps([workforce_row]),
    }
    import httpx
    monkeypatch.setattr(workforce, "sync_get", lambda url, **kw: httpx.Response(200,
        content=responses[url].encode(), request=httpx.Request("GET", url)))
    monkeypatch.setattr(workforce, "_today", lambda: date(2026, 10, 17))
    def cached(key, callback, **kwargs):
        return callback(), {"cache_hit": False, "stale": False, "fetched_at_epoch": 1_797_000_000,
                            "http_request_sent": True, "http_request_count": 1}

    monkeypatch.setattr(workforce, "shared_fetch", cached)
    result = AnnualWorkforceProvider().fetch(FetchRequest.from_ticker("2330.TW"))

    assert result.status == "success"
    assert result.audit["record_count"] == 1
    assert result.audit["http_request_count"] == 1
    assert result.audit["http_request_sent"] is True
    assert result.audit["component_statuses"]["occupational_safety_disclosure"]["status"] == "success"
    esg_audit, = result.audit["related_entries"]
    assert esg_audit["source"] == "esg_occupational_safety"
    assert esg_audit["record_count"] == 1
    assert esg_audit["http_request_sent"] is True and esg_audit["http_request_count"] == 1
    from data_fetch.workflow import _audit_entries_from_provider_results
    assert {entry["source"] for entry in _audit_entries_from_provider_results([result])} >= {
        "annual_workforce", "esg_occupational_safety"
    }
    safety = result.value["esg_occupational_safety"]
    assert safety["metrics"]["occupational_injury_count"] == 0
    assert source_record_count("annual_workforce", {"ticker": "2330.TW", "annual_workforce": result.value}) == 1
    assert source_record_count("esg_occupational_safety", {"ticker": "2330.TW", "annual_workforce": result.value}) == 1
    assert result.value["job_openings_count"] is None
    assert "annual_workforce" in data_for_agent_prompt(14, {"ticker": "2330.TW", "annual_workforce": result.value})
    assert "annual_workforce" not in data_for_agent_prompt(12, {"ticker": "2330.TW", "annual_workforce": result.value})
    from pathlib import Path
    sla_helpers = Path(__file__).resolve().parents[1] / "backend/static/provider_sla_helpers.js"
    assert "esg_occupational_safety: '職安衛／ESG 揭露'" in sla_helpers.read_text(encoding="utf-8")


def test_cold_official_dataset_requests_count_in_both_acquisition_categories(monkeypatch):
    import data_fetch.annual_workforce_provider as workforce
    from data_fetch.types import FetchRequest
    from provider_acquisition import observation_kind

    workforce_row = {
        "出表日期": "1151016", "報告年度": "114", "公司代號": "2330", "公司名稱": "台積電",
        "員工薪資平均數(仟元/人) ": "4093",
        "非擔任主管之全時員工薪資中位數(仟元/人) ": "3162",
        "管理職女性主管佔比": "15.00%",
    }
    responses = {
        URLS[".TW"]: json.dumps([_row()]).encode(),
        "https://openapi.twse.com.tw/v1/opendata/t187ap46_L_5": json.dumps([workforce_row]).encode(),
    }
    requested = []

    import httpx
    def fake_get(url, **kwargs):
        requested.append(url)
        return httpx.Response(200, content=responses[url], request=httpx.Request("GET", url))

    def cold_shared_fetch(key, callback, **kwargs):
        return callback(), {"cache_hit": False, "stale": False, "fetched_at_epoch": 1_797_000_000}

    monkeypatch.setattr(workforce, "sync_get", fake_get)
    monkeypatch.setattr(workforce, "shared_fetch", cold_shared_fetch)
    monkeypatch.setattr(workforce, "_today", lambda: date(2026, 10, 17))
    import data_fetch.annual_occupational_safety as safety
    monkeypatch.setattr(safety, "_today", lambda: date(2026, 10, 17))

    result = AnnualWorkforceProvider().fetch(FetchRequest.from_ticker("2330.TW"))

    assert requested == ["https://openapi.twse.com.tw/v1/opendata/t187ap46_L_5",
                         "https://openapi.twse.com.tw/v1/opendata/t187ap46_L_21"]
    esg_audit, = result.audit["related_entries"]
    for audit in (result.audit, esg_audit):
        assert audit["http_request_sent"] is True
        assert audit["http_request_count"] == 1
        assert observation_kind({
            "provider": audit["provider"], "status": audit["status"],
            "record_count": audit["record_count"], "message": audit["message"],
            "details": audit,
        }) == "fetched_count"


def test_safety_only_fetch_does_not_claim_workforce_success(monkeypatch):
    import data_fetch.annual_workforce_provider as workforce
    from data_fetch.types import FetchRequest
    from provider_acquisition import observation_kind

    responses = {
        "https://openapi.twse.com.tw/v1/opendata/t187ap46_L_5": b"[]",
        "https://openapi.twse.com.tw/v1/opendata/t187ap46_L_21": json.dumps([_row()]).encode(),
    }

    class Response:
        def __init__(self, content):
            self.content = content

    monkeypatch.setattr(workforce, "sync_get", lambda url, **kwargs: Response(responses[url]))
    monkeypatch.setattr(workforce, "shared_fetch", lambda key, callback, **kwargs: (
        callback(), {"cache_hit": False, "stale": False, "fetched_at_epoch": 1_797_000_000}))
    monkeypatch.setattr(workforce, "_today", lambda: date(2026, 10, 17))
    import data_fetch.annual_occupational_safety as safety
    monkeypatch.setattr(safety, "_today", lambda: date(2026, 10, 17))

    result = AnnualWorkforceProvider().fetch(FetchRequest.from_ticker("2330.TW"))

    workforce_audit = result.audit
    safety_audit, = result.audit["related_entries"]
    assert workforce_audit["status"] == "degraded_enrichment"
    assert workforce_audit["record_count"] == 0
    assert observation_kind({
        "provider": workforce_audit["provider"], "status": workforce_audit["status"],
        "record_count": workforce_audit["record_count"], "message": workforce_audit["message"],
        "details": workforce_audit,
    }) == "empty_count"
    assert safety_audit["status"] == "success" and safety_audit["record_count"] == 1
    assert observation_kind({
        "provider": safety_audit["provider"], "status": safety_audit["status"],
        "record_count": safety_audit["record_count"], "message": safety_audit["message"],
        "details": safety_audit,
    }) == "fetched_count"
