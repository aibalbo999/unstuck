"""Recent evidence is selected against its input cutoff, never fetch success."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def test_optional_merge_excludes_old_unknown_and_future_before_truncation(monkeypatch):
    import data_fetch.enrichment_merge as merge
    cutoff = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(merge.time_module, "time", lambda: cutoff.timestamp())
    data = {"ticker": "2305.TW", "recent_catalysts": [
        {"title": "old", "link": "https://old.example/story", "date": "2023-06-09"},
        {"title": "unknown", "link": "https://unknown.example/story"},
        {"title": "future", "link": "https://future.example/story", "date": "2026-09-23"},
    ]}
    merged = merge._merge_optional_http_bundle(data, {"free_news": [
        {"title": "recent", "link": "https://news.google.com/rss/articles/abc", "published_date": "2026-09-21T08:30:00+08:00", "source": "Example Daily"},
    ]}, refreshed_sources=("recent_catalysts",))
    assert [item["title"] for item in merged["recent_catalysts"]] == ["recent"]
    assert merged["recent_catalysts"][0]["date"] == "2026-09-21T00:30:00+00:00"
    assert [item["title"] for item in merged["historical_catalysts"]] == ["old"]
    assert {item["news_date_status"] for item in merged["unverified_catalysts"]} == {"unknown", "future"}
    assert merged["news_selection"]["recent_count"] == 1


def test_news_cutoff_has_no_boundary_tolerance_and_preserves_original_records():
    from news_freshness_policy import apply_news_freshness
    data = {"recent_catalysts": [
        {"title": "boundary", "link": "https://one.test/1", "date": "2026-08-23T12:00:00Z"},
        {"title": "older by second", "link": "https://two.test/2", "date": "2026-08-23T11:59:59Z"},
        {"title": "newer by second", "link": "https://three.test/3", "date": "2026-09-22T12:00:01Z"},
    ]}
    originals = deepcopy(data["recent_catalysts"])
    apply_news_freshness(data, cutoff="2026-09-22T12:00:00Z", lookback_days=30)
    assert [record["title"] for record in data["recent_catalysts"]] == ["boundary"]
    assert originals[0]["date"].endswith("Z")
    once = deepcopy(data)
    apply_news_freshness(data, cutoff="2026-09-22T12:00:00Z", lookback_days=30)
    assert data == once


def test_recent_search_excludes_unknown_future_and_timestamp_not_truncated_to_date():
    from external_search_quality import select_quality_results, search_quality_satisfied
    from external_search_types import SearchResult
    records = [SearchResult("Company news " + date, "Company", "https://source.test/" + str(i), "Source", date)
               for i, date in enumerate(("2026-09-22T15:00:00Z", "2025-09-22", "", "2026-09-22T11:00:00Z"))]
    selected = select_quality_results(records, limit=5, query="Company", require_recent=True,
                                      cutoff="2026-09-22T12:00:00Z")
    assert selected == [records[-1]]
    assert not search_quality_satisfied(records[:1], max_results=1, require_recent=True,
                                        cutoff="2026-09-22T12:00:00Z")


def test_google_wrapper_is_not_a_publisher_and_dedupe_precedes_selection():
    from news_freshness_policy import apply_news_freshness
    records = [
        {"title": "a", "link": "https://news.google.com/rss/articles/a", "source": "Google News", "date": "2026-09-22"},
        {"title": "b", "link": "https://news.google.com/rss/articles/b", "source": "Example Daily", "date": "2026-09-21"},
        {"title": "b", "link": "https://daily.test/story?utm_source=google", "source": "Example Daily", "date": "2026-09-21"},
        {"title": "c", "link": "https://news.google.com/rss/articles/c", "source": "Other Daily", "date": "2026-09-20"},
    ]
    data = {"recent_catalysts": records}
    apply_news_freshness(data, cutoff="2026-09-22T12:00:00Z", limit=3)
    assert len(data["recent_catalysts"]) == 3
    assert data["news_selection"]["publisher_count"] == 2
    wrapper = next(record for record in data["recent_catalysts"] if record["title"] == "a")
    assert wrapper["publisher"] == ""
    assert wrapper["publisher_status"] == "unknown"


def test_freeze_input_selects_at_original_cutoff_before_hash():
    from analysis_input_provenance import freeze_analysis_inputs
    data = {"ticker": "2305.TW", "recent_catalysts": [
        {"title": "known then", "date": "2026-08-31", "link": "https://one.test/news"},
        {"title": "not yet known", "date": "2026-09-02", "link": "https://two.test/news"},
    ]}
    receipt = freeze_analysis_inputs(data, cutoff="2026-09-01T12:00:00Z")
    assert [record["title"] for record in data["recent_catalysts"]] == ["known then"]
    assert receipt["analysis_input_cutoff"] == "2026-09-01T12:00:00Z"
    assert data["news_selection"]["cutoff"] == "2026-09-01T12:00:00+00:00"


def test_cache_read_reselects_news_without_modifying_saved_cache(monkeypatch):
    import data_fetch.workflow_cache as cache
    cached = {"ticker": "2305.TW", "recent_catalysts": [
        {"title": "old cached", "date": "2020-01-01", "link": "https://old.test/news"},
    ]}
    original = deepcopy(cached)
    monkeypatch.setattr(cache, "assess_cached_financial_data", lambda *args: (True, {}))
    monkeypatch.setattr(cache, "_append_cache_audit_entries", lambda *args: None)
    result = cache.fresh_cached_payload("2305.TW", cached)
    assert result["recent_catalysts"] == []
    assert result["news_selection"]["status"] == "no_recent_evidence"
    assert cached == original


def test_long_wrapper_urls_do_not_collapse_distinct_records_and_bad_urls_are_safe():
    from news_freshness_policy import apply_news_freshness
    prefix = "https://news.google.com/rss/articles/" + "x" * 240
    data = {"recent_catalysts": [
        {"title": "first", "link": prefix + "a", "date": "2026-09-21"},
        {"title": "second", "link": prefix + "b", "date": "2026-09-21"},
        {"title": "malformed", "link": "https://[broken", "date": "2026-09-21"},
    ]}
    apply_news_freshness(data, cutoff="2026-09-22T12:00:00Z")
    assert {item["title"] for item in data["recent_catalysts"]} == {"first", "second", "malformed"}
    assert data["news_selection"]["publisher_count"] == 0


def test_prompt_exposes_shortage_without_reintroducing_excluded_news():
    import json
    from news_freshness_policy import apply_news_freshness
    from prompt_builder import format_data_for_prompt
    data = {"ticker": "2305.TW", "recent_catalysts": [
        {"title": "ARCHIVED_OLD_NEWS", "summary": "private background " * 3000,
         "date": "2020-01-01", "link": "https://publisher.test/archive"},
    ]}
    apply_news_freshness(data, cutoff="2026-09-22T12:00:00Z")
    prompt = format_data_for_prompt(data)
    payload = json.loads(prompt.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0])
    assert payload["market_catalysts"]["selection_summary"]["status"] == "no_recent_evidence"
    assert payload["market_catalysts"]["selection_summary"]["historical_count"] == 1
    assert payload["market_catalysts"]["items"] == []
    assert "ARCHIVED_OLD_NEWS" not in prompt
    assert "private background" not in prompt


def test_snapshot_preserves_selection_and_marks_archive_size_omission():
    from news_freshness_policy import apply_news_freshness
    from data_trust_snapshot import build_data_snapshot
    data = {"ticker": "2305.TW", "recent_catalysts": [
        {"title": f"archive {i}", "summary": "x" * 3000, "date": "2020-01-01",
         "link": f"https://publisher.test/{i}"} for i in range(10)
    ]}
    apply_news_freshness(data, cutoff="2026-09-22T12:00:00Z")
    original = deepcopy(data)
    full = build_data_snapshot({"data": data}, max_bytes=200000)
    small = build_data_snapshot({"data": data}, max_bytes=12000)
    assert full["data"]["historical_catalysts"] == data["historical_catalysts"]
    assert small["data"]["news_selection"] == data["news_selection"]
    assert small["snapshot_truncated"] is True
    assert "data.historical_catalysts:7" in small["snapshot_omitted_sections"]
    assert data == original


def test_reselection_at_same_cutoff_keeps_overflow_and_is_idempotent():
    from news_freshness_policy import apply_news_freshness
    data = {"recent_catalysts": [
        {"title": f"news {i}", "date": "2026-09-21", "source": "One Publisher" if i < 3 else "Other Publisher",
         "link": f"https://news.google.com/rss/articles/{i}"} for i in range(5)
    ]}
    apply_news_freshness(data, cutoff="2026-09-22T12:00:00Z", limit=2)
    assert [item["title"] for item in data["recent_catalysts"]] == ["news 0", "news 3"]
    assert len(data["additional_recent_catalysts"]) == 3
    original = deepcopy(data)
    apply_news_freshness(data, cutoff="2026-09-22T12:00:00Z", limit=2)
    assert data == original
