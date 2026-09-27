"""Source presence measures observations, never diagnostic dictionary fields."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from data_trust_audit import source_record_count
from data_freshness import source_is_stale


def unavailable_payload():
    return {
        "status": "unavailable", "job_openings_104": {"status": "unavailable", "job_count": None, "reason_code": "client_rendered"},
        "job_openings_1111": {"status": "unavailable", "job_count": None, "reason_code": "access_denied"},
        "numeric_count_coverage": 0, "recruitment_news_count": 0,
        "component_statuses": {"104_1": {"status": "unavailable"}},
        "coverage_notes": ["失敗不代表零職缺"], "fetched_at_epoch": time.time(),
    }


def data(payload):
    return {"ticker": "5314.TWO", "company_name": "世紀* / Myson Century, Inc.", "_cache_hit": True,
            "source_freshness": {"alternative_data": {"fetched_at_epoch": time.time()}},
            "alternative_data": payload}


def count(payload):
    return source_record_count("alternative_data", data(payload))


def article(**updates):
    return {"title": "世紀招募工程師", "date": datetime.now(timezone.utc).isoformat(),
            "link": "https://example.com/recruitment", **updates}


def test_diagnostic_only_cache_is_missing_and_reaches_optional_refresh():
    from data_fetch.optional_provider_plan import collect_optional_providers
    from data_fetch.types import FetchRequest
    sample = data(unavailable_payload())
    original = deepcopy(sample)
    provider = object()
    class Registry:
        def for_request(self, request, source):
            assert source == "alternative_data"
            return [provider]
    assert source_record_count("alternative_data", sample) == 0
    assert source_is_stale(sample, "alternative_data", "5314.TWO", market_session=False)
    selected, refresh = collect_optional_providers(FetchRequest.from_ticker("5314.TWO"), Registry(), sample,
                                                 "5314.TWO", sources=["alternative_data"])
    assert selected == [provider]
    assert refresh == {"alternative_data": True}
    assert sample == original


@pytest.mark.parametrize("value", [0, 5])
def test_successful_numeric_observation_including_zero_is_present(value):
    payload = {"status": "valid_empty" if value == 0 else "success",
               "job_openings_104": {"status": "success", "job_count": value},
               "job_openings_1111": [{"status": "unavailable", "job_count": None}]}
    assert count(payload) == 1  # observation count, not number of jobs
    assert not source_is_stale(data(payload), "alternative_data", "5314.TWO", market_session=False)


@pytest.mark.parametrize("value", [None, True, False, -1, 1.5, float("nan"), float("inf"), "0", 10**1000])
def test_invalid_numeric_values_and_metadata_cannot_create_presence(value):
    assert count({"job_openings_104": {"status": "success", "job_count": value},
                  "numeric_count_coverage": 99, "recruitment_news_count": 99}) == 0


def test_failed_numeric_field_is_not_an_observation():
    assert count({"job_openings_104": {"status": "unavailable", "job_count": 8}}) == 0


def test_qualitative_news_is_unique_across_aggregate_and_components():
    first = article()
    duplicate = article(title="世紀擴編工程師", link="https://example.com/recruitment?utm_source=104")
    payload = {"status": "qualitative_only", "recent_recruitment_news": [first],
        "job_openings_104": {"status": "success", "job_count": None, "evidence_kind": "recruitment_news", "recent_recruitment_news": [first]},
        "job_openings_1111": [{"status": "success", "job_count": None, "evidence_kind": "recruitment_news", "recent_recruitment_news": [duplicate]}]}
    original = deepcopy(payload)
    assert count(payload) == 1
    assert payload == original


def test_legacy_component_only_qualitative_news_still_counts():
    assert count({"job_openings_104": {"status": "success", "job_count": None,
        "evidence_kind": "recruitment_news", "recent_recruitment_news": [article()]}}) == 1


def test_same_recruitment_headline_at_different_urls_is_one_observation():
    first = article()
    second = article(link="https://example.org/syndicated-recruitment")
    assert count({"recent_recruitment_news": [first, second]}) == 1


@pytest.mark.parametrize("updates", [
    {"date": None}, {"date": (datetime.now(timezone.utc)-timedelta(days=45)).isoformat()},
    {"date": (datetime.now(timezone.utc)+timedelta(days=2)).isoformat()},
    {"title": "台積電招募工程師"}, {"title": "世紀公布營收"}, {"link": ""},
])
def test_unqualified_news_does_not_hide_missing_source(updates):
    assert count({"status": "qualitative_only", "recent_recruitment_news": [article(**updates)]}) == 0


def test_mixed_numeric_and_qualitative_sources_count_observations_only():
    assert count({"status": "partial", "job_openings_104": [{"status": "success", "job_count": 0},
        {"status": "success", "job_count": 8}], "recent_recruitment_news": [article()],
        "component_statuses": {"extra": {"status": "success"}}, "coverage_notes": ["partial"]}) == 3
