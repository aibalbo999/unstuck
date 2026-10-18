"""Independent public-boundary checks for the captured FinMind overview role."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from data_fetch.types import FetchRequest
from test_finmind_news_daily_recovery import isolated, install_http, ROW
from test_finmind_overview_recovery import observed, api_row

CUTOFF = "2026-10-13T00:00:00+00:00"
SUBJECT = {"ticker": "1623.TW", "company_name": "大東電"}


@pytest.mark.parametrize("link,is_overview", [
    ("https://CMONEY.TW/finance/1623/f00025/?utm_source=test#news", True),
    ("https://www.cmoney.tw/finance/1623/f00025?source=FinMind", True),
    ("https://cmoney.tw.example/finance/1623/f00025", False),
    ("https://publisher.example/news?url=https://cmoney.tw/finance/1623/f00025", False),
    ("https://www.cmoney.tw/notes/note-detail.aspx?nid=1623", False),
    ("https://www.cmoney.tw/finance/1623/f000250", False),
    ("https://www.cmoney.tw/finance/1623/f00025/article", False),
])
def test_public_selector_matches_exact_known_route_only(link, is_overview):
    from source_content_selection import select_company_records
    original = {**observed(), "link": link, "title": "大東電(1623)營運資料"}
    before = deepcopy(original)
    selected, audit = select_company_records([original], SUBJECT, cutoff=CUTOFF)
    assert bool(selected) is not is_overview
    assert audit["rejected_reason_counts"] == ({"stock_overview_is_not_news": 1} if is_overview else {})
    if is_overview:
        assert audit["source_record_archive"][0]["record"] == before
    assert original == before


def test_overview_then_native_429_stops_and_warm_cannot_retry(monkeypatch, isolated):
    from data_fetch.market_sources import finmind_news as news, finmind_news_transport as transport
    from official_response_evidence import read_response
    isolated[0] = datetime(2026, 10, 13, tzinfo=timezone.utc).timestamp()
    overview = api_row("2026-10-12")
    calls = install_http(monkeypatch, {"2026-10-12": [overview]})
    original_collect = transport.collect_capped_process

    def native_response(*args, **kwargs):
        parts, rc, error = original_collect(*args, **kwargs)
        if calls[-1]["query"]["start_date"] == ["2026-10-11"]:
            parts["headers"] = b"HTTP/1.1 429 Too Many Requests\r\nContent-Type: application/json\r\n\r\n"
            meta = json.loads(parts["metadata"])
            meta["http_code"] = 429
            parts["metadata"] = json.dumps(meta).encode()
            parts["body"] = b'{"status":429,"msg":"rate limit","data":[]}'
        return parts, rc, error

    monkeypatch.setattr(transport, "collect_capped_process", native_response)
    first = news.fetch_finmind_news_result(FetchRequest.from_ticker("1623.TW"))
    assert first.value == [] and first.status == "error"
    assert first.audit["error_kind"] == "rate_limited"
    assert first.audit["rejected_reason_counts"] == {"stock_overview_is_not_news": 1}
    assert first.audit["http_request_count"] == len(calls) == 2
    assert [call["query"]["start_date"][0] for call in calls] == ["2026-10-12", "2026-10-11"]
    assert json.loads(read_response(first.audit["components"][0]["raw_http_receipt"]))["data"] == [overview]
    second = news.fetch_finmind_news_result(FetchRequest.from_ticker("1623.TW"))
    assert second.value == [] and second.status == "error"
    assert second.audit["error_kind"] == "rate_limited"
    assert second.audit["http_request_count"] == 0 and len(calls) == 2


@pytest.mark.parametrize("bucket", ["recent_catalysts", "additional_recent_catalysts", "historical_catalysts", "unverified_catalysts", "identity_rejected_catalysts"])
def test_all_saved_buckets_retire_overview_with_receipt_and_idempotency(bucket):
    from news_freshness_policy import apply_news_only_freshness
    data = {**SUBJECT, bucket: [observed()], "social_sentiment": {"original": [1]},
            "current_price": 42, "source_audit": [{"unchanged": True}]}
    original = deepcopy(data)
    apply_news_only_freshness(data, cutoff=CUTOFF)
    assert data["news_selection"]["eligible_count"] == 0
    assert data["news_selection"]["source_role_unverified_count"] == 1
    row = data["unverified_catalysts"][0]
    for key in ("link", "title", "summary", "source", "publication_date_original", "finmind_news_receipt"):
        assert row[key] == observed()[key]
    assert row["source_role_status"] == "stock_overview_is_not_news"
    assert all(data[key] == original[key] for key in ("current_price", "source_audit", "social_sentiment"))
    once = deepcopy(data)
    apply_news_only_freshness(data, cutoff=CUTOFF)
    assert data == once


def test_source_only_merge_preserves_overview_archive_without_promoting(monkeypatch):
    import recent_catalyst_source_refresh as refresh
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    monkeypatch.setattr(refresh.time, "time", lambda: now.timestamp())
    original = {**SUBJECT, "quote_type": "EQUITY", "recent_catalysts": [observed()],
                "current_price": 42, "revenue_ttm_raw": 23, "social_sentiment": {"original": True}, "source_audit": []}
    before = deepcopy(original)
    records = [{"title": f"大東電(1623)營運新聞 {i}", "date": "2026-10-11T00:00:00+00:00",
                "source": f"publisher{i % 3}", "link": f"https://publisher{i % 3}.example/news/{i}"} for i in range(8)]
    audit = {"source": "recent_catalysts", "provider": "Alternative Search", "status": "success",
             "record_count": 8, "quality_status": "sufficient_candidates", "selection_policy": "company-time-v1",
             "fetched_at_epoch": now.timestamp(), "fetched_at": now.isoformat(), "selection_cutoff": now.isoformat(),
             "cache_hit": False, "stale": False, "fetch_id": "independent-overview-review"}
    assert refresh.valid_recent_receipt(records, audit, original)
    merged = refresh.merge_recent_source(original, [], records, [audit], original["ticker"])
    assert merged["news_selection"]["eligible_count"] == 8
    assert len(merged["unverified_catalysts"]) == 1
    assert merged["unverified_catalysts"][0]["finmind_news_receipt"] == observed()["finmind_news_receipt"]
    assert all(r["link"] != observed()["link"] for key in ("recent_catalysts", "additional_recent_catalysts") for r in merged[key])
    assert original == before
    assert all(merged[key] == before[key] for key in ("current_price", "revenue_ttm_raw", "social_sentiment"))


def test_overview_rejection_does_not_restart_ten_second_deadline(monkeypatch, isolated):
    from data_fetch.market_sources import finmind_news as news, finmind_news_transport as transport
    isolated[0] = datetime(2026, 10, 13, tzinfo=timezone.utc).timestamp()
    calls = install_http(monkeypatch, {"2026-10-12": [api_row("2026-10-12")]})
    mono = [100.]
    monkeypatch.setattr(news.time, "monotonic", lambda: mono[0])
    original_collect = transport.collect_capped_process

    def consume_whole_budget(*args, **kwargs):
        result = original_collect(*args, **kwargs)
        mono[0] += 10.01
        return result

    monkeypatch.setattr(transport, "collect_capped_process", consume_whole_budget)
    result = news.fetch_finmind_news_result(FetchRequest.from_ticker("1623.TW"))
    assert result.status == "error" and result.audit["error_kind"] == "timeout"
    assert result.value == [] and result.audit["http_request_count"] == len(calls) == 1
