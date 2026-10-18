"""Retained eligible news must be able to satisfy the unchanged search gate."""
from copy import deepcopy
from datetime import timedelta

import pytest

from data_fetch.enrichment_providers import FreeNewsWaterfallProvider
from data_fetch.types import FetchRequest
from test_catalyst_search_fallback_plan import NOW, feeds, run_plan


DATA = {"ticker": "2330.TW", "company_name": "台積電",
        "company_identity": {"official_name": "台積電", "allowed_aliases": ["台積電"]}}


def fetch(monkeypatch, rows, *, target=8):
    import config
    import external_data_client
    import news_freshness_policy
    calls = []

    class Client:
        last_news_audit = [{"source": "recent_catalysts", "provider": "Google News RSS",
                            "status": "success", "record_count": len(rows)}]

        def get_news(self, query, **kwargs):
            calls.append((query, kwargs))
            return deepcopy(rows[:kwargs["limit"]])

    monkeypatch.setattr(external_data_client, "ExternalDataClient", Client)
    monkeypatch.setattr(config, "SEARCH_CATALYST_MAX_RESULTS", target)
    monkeypatch.setattr(news_freshness_policy, "news_cutoff", lambda *a, **k: NOW)
    result = FreeNewsWaterfallProvider().fetch(FetchRequest.from_ticker("2330.TW"), {"data": deepcopy(DATA)})
    assert len(calls) == 1
    options = dict(calls[0][1])
    assert callable(options.pop('sufficient'))
    assert options == {"ticker": "2330.TW", "limit": 20}
    return result


def rows(count=20):
    return [{"title": f"台積電營運新聞{i}", "summary": "台積電公布營運資訊。",
             "date": (NOW-timedelta(hours=1)).isoformat(),
             "source": f"publisher{i % 3}", "link": f"https://news{i % 3}.example/article/{i}"}
            for i in range(count)]


def test_qualified_pool_retains_eight_and_keeps_the_remaining_evidence(monkeypatch):
    result = fetch(monkeypatch, rows())
    assert len(result.value) == 8 and result.status == "success"
    assert result.audit["record_count"] == result.audit["news_selection"]["recent_count"] == 8
    assert result.audit["news_selection"]["eligible_count"] == 20
    assert len(result.audit["additional_recent_catalysts"]) == 12
    assert {r["link"] for r in result.value}.isdisjoint(
        r["link"] for r in result.audit["additional_recent_catalysts"])
    assert result.audit["news_selection"]["publisher_count"] == 3


def test_public_workflow_does_not_refetch_when_existing_news_and_official_overlap_still_have_eight(monkeypatch):
    official = feeds()[1]
    # Three real official records are repeated in the RSS pool. Five more
    # articles already arrived in that same request; retaining only five
    # records makes the merged evidence insufficient after de-duplication.
    pool = [{"title": r["title"], "summary": r["summary"], "date": r["date"],
             "link": r["link"], "source": r["source"]} for r in official.value]
    pool += rows(5)
    result = fetch(monkeypatch, pool)
    data, calls, _ = run_plan(monkeypatch, results=[result, official], notice=True, yahoo=True)
    assert calls == ["Free news waterfall", "TWSE company announcement history"]
    for name in ("TWSE official trading notices", "Alternative Search", "Yahoo Finance news"):
        audit = next(a for a in data["source_audit"] if a.get("provider") == name)
        assert audit["event_kind"] == "local_block" and audit["http_request_sent"] is False
        assert audit["record_count"] == 0 and audit["existing_evidence"]["eligible_count"] == 8
        assert audit["existing_evidence"]["publisher_count"] >= 3
        assert audit["reason_code"] == "current_catalyst_evidence_sufficient"


@pytest.mark.parametrize("target", [3, 5, 8, 12, 20])
def test_configured_retained_capacity_does_not_increase_the_twenty_candidate_request(monkeypatch, target):
    result = fetch(monkeypatch, rows(), target=target)
    assert len(result.value) == target
    assert len(result.audit["additional_recent_catalysts"]) == 20-target


@pytest.mark.parametrize("count", [0, 2, 7])
def test_missing_candidates_are_not_padded_to_capacity(monkeypatch, count):
    result = fetch(monkeypatch, rows(count))
    assert len(result.value) == count
    assert result.audit["news_selection"]["eligible_count"] == count


def test_rejected_candidates_stay_excluded_but_do_not_degrade_sufficient_final_evidence(monkeypatch):
    good = rows(8)
    bad = deepcopy(rows(4))
    for i, item in enumerate(bad):
        item["link"] = f"https://rejected.example/article/{i}"
    bad[0]["date"] = (NOW-timedelta(days=40)).isoformat()
    bad[1]["date"] = (NOW+timedelta(days=1)).isoformat()
    bad[2]["date"] = ""
    bad[3].update(title="聯發科其他公司消息", summary="聯發科公司說明")
    result = fetch(monkeypatch, good+bad)
    assert len(result.value) == 8 and result.status == "success"
    assert result.audit["rejected_count"] == 4
    assert len(result.audit["source_record_archive"]) == 4
    assert not {r["link"] for r in result.value}.intersection(r["link"] for r in bad)
    assert result.audit["qualified_result_status"] == "sufficient_qualified_results"
    assert result.audit["retrieval_status"] == "records_received"


def test_final_evidence_below_existing_publisher_gate_stays_degraded(monkeypatch):
    rows_with_one_publisher = rows(8)
    for index, row in enumerate(rows_with_one_publisher):
        row["source"] = "one-publisher"
        row["link"] = f"https://one-publisher.example/article/{index}"
    result = fetch(monkeypatch, rows_with_one_publisher)
    assert len(result.value) == 8
    assert result.status == "degraded_enrichment"
    assert result.audit["rejected_count"] == 0
    assert result.audit["qualified_result_status"] == "insufficient_search_quality"
