"""Official annual workforce facts are separate from live job openings."""

from datetime import date
import json

from data_fetch.annual_workforce_provider import AnnualWorkforceProvider, parse_workforce_dataset
from data_fetch.types import FetchRequest


LISTED = {
    "出表日期": "1151004", "報告年度": "114", "公司代號": "2330", "公司名稱": "台積電",
    "員工薪資平均數(仟元/人) ": "4093",
    "非擔任主管之全時員工薪資中位數(仟元/人) ": "3162",
    "管理職女性主管佔比": "15.00%",
}


def test_parse_exact_issuer_year_and_units():
    payload = parse_workforce_dataset(json.dumps([LISTED]).encode(), "2330.TW", today=date(2026, 10, 4))
    assert payload["report_year"] == 2025
    assert payload["published_on"] == "2026-10-04"
    assert payload["metrics"]["employee_average_salary_thousand_twd"] == 4093
    assert payload["metrics"]["nonmanager_median_salary_thousand_twd"] == 3162
    assert payload["metrics"]["female_manager_percent"] == 15
    assert payload["job_openings_count"] is None
    assert payload["response_sha256"]


def test_missing_or_conflicting_issuer_cannot_be_promoted():
    assert parse_workforce_dataset(json.dumps([LISTED]).encode(), "5314.TWO", today=date(2026, 10, 4)) is None
    assert parse_workforce_dataset(json.dumps([LISTED, LISTED]).encode(), "2330.TW", today=date(2026, 10, 4)) is None
    stale = {**LISTED, "報告年度": "110"}
    assert parse_workforce_dataset(json.dumps([stale]).encode(), "2330.TW", today=date(2026, 10, 4)) is None
    bad = {**LISTED, "員工薪資平均數(仟元/人) ": "NaN"}
    assert parse_workforce_dataset(json.dumps([bad]).encode(), "2330.TW", today=date(2026, 10, 4)) is None


def test_provider_keeps_workforce_and_jobs_separate(monkeypatch):
    import data_fetch.annual_workforce_provider as workforce
    from data_fetch.provider_registry import ProviderRegistry
    from data_trust import source_record_count

    monkeypatch.setattr(workforce, "_fetch_dataset", lambda url: json.dumps([LISTED]))
    monkeypatch.setattr(workforce, "_today", lambda: date(2026, 10, 4))
    monkeypatch.setattr(workforce, "shared_fetch", lambda key, callback, **kwargs: (callback(), {"cache_hit": False, "stale": False, "fetched_at_epoch": 123.0}))
    result = AnnualWorkforceProvider().fetch(FetchRequest.from_ticker("2330.TW"))
    assert result.status == "success"
    assert result.audit["record_count"] == 1
    assert result.audit["event_kind"] == "fetch"
    assert result.audit["component_statuses"]["annual_disclosure"]["as_of"] == "2025-12-31"
    assert result.source == "annual_workforce"
    assert result.value["job_openings_count"] is None
    assert source_record_count("annual_workforce", {"ticker": "2330.TW", "annual_workforce": result.value}) == 1
    assert source_record_count("alternative_data", {"ticker": "2330.TW", "annual_workforce": result.value}) == 0
    assert any(isinstance(item, AnnualWorkforceProvider) for item in ProviderRegistry().for_request(FetchRequest.from_ticker("2330.TW"), source="annual_workforce"))


def test_workflow_plans_and_merges_workforce_without_changing_jobs(monkeypatch):
    import data_fetch.annual_workforce_provider as workforce
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.optional_provider_plan import collect_optional_providers
    from data_fetch.provider_registry import ProviderRegistry
    from data_trust import source_record_count

    monkeypatch.setattr(workforce, "_fetch_dataset", lambda url: json.dumps([LISTED]))
    monkeypatch.setattr(workforce, "_today", lambda: date(2026, 10, 4))
    monkeypatch.setattr(workforce, "shared_fetch", lambda key, callback, **kwargs: (callback(), {"cache_hit": False, "stale": False, "fetched_at_epoch": 123.0}))
    request = FetchRequest.from_ticker("2330.TW")
    data = {"ticker": "2330.TW", "company_name": "台積電", "quote_type": "EQUITY", "_cache_hit": False,
            "alternative_data": {"status": "unavailable", "job_openings_104": {"status": "unavailable", "job_count": None}},
            "source_audit": [], "source_freshness": {}}
    providers, refresh = collect_optional_providers(request, ProviderRegistry(), data, request.ticker,
                                                    sources=("annual_workforce",))
    assert refresh == {"annual_workforce": True}
    assert len(providers) == 1 and isinstance(providers[0], AnnualWorkforceProvider)
    result = providers[0].fetch(request, {"data": data})
    data["source_audit"].append(result.audit)
    merged = _merge_optional_http_bundle(data, {"annual_workforce": result.value},
                                         refreshed_sources=("annual_workforce",))
    assert merged["annual_workforce"]["report_year"] == 2025
    assert source_record_count("annual_workforce", merged) == 1
    assert source_record_count("alternative_data", merged) == 0
    assert merged["alternative_data"]["job_openings_104"]["job_count"] is None


def test_missing_optional_workforce_metric_remains_partial():
    row = {**LISTED, "管理職女性主管佔比": ""}
    payload = parse_workforce_dataset(json.dumps([row]).encode(), "2330.TW", today=date(2026, 10, 4))
    assert payload["coverage_status"] == "partial"
    assert payload["metrics"]["female_manager_percent"] is None


def test_report_force_refresh_reuses_current_official_annual_snapshot(monkeypatch):
    """Refreshing a report must not refetch the market-wide annual file per ticker."""
    import data_fetch.annual_workforce_provider as workforce

    seen = []

    def cached_snapshot(key, callback, **kwargs):
        seen.append(kwargs)
        return json.dumps([LISTED]), {"cache_hit": True, "stale": False, "fetched_at_epoch": 123.0}

    monkeypatch.setattr(workforce, "shared_fetch", cached_snapshot)
    monkeypatch.setattr(workforce, "_today", lambda: date(2026, 10, 4))
    result = AnnualWorkforceProvider().fetch(FetchRequest.from_ticker("2330.TW", force_refresh=True))

    assert result.status == "success"
    assert result.audit["cache_hit"] is True
    assert seen[0]["use_cache"] is True
    assert seen[0]["retention_seconds"] > seen[0]["freshness_seconds"]


def test_retained_workforce_after_transport_error_is_not_a_new_success(monkeypatch):
    import data_fetch.annual_workforce_provider as workforce

    monkeypatch.setattr(workforce, "_today", lambda: date(2026, 10, 4))
    monkeypatch.setattr(workforce, "shared_fetch", lambda key, callback, **kwargs: (
        json.dumps([LISTED]),
        {"cache_hit": True, "stale": True, "error_kind": "ReadError", "fetched_at_epoch": 123.0},
    ))

    result = AnnualWorkforceProvider().fetch(FetchRequest.from_ticker("2330.TW", force_refresh=True))

    assert result.status == "degraded_enrichment"
    assert result.value["status"] == "stale"
    assert result.audit["record_count"] == 1
    assert result.audit["stale"] is True
    assert result.audit["error_kind"] == "ReadError"
