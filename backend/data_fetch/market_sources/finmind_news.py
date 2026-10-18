"""Bounded recent-day sampling for FinMind's one-day-only news dataset."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from hashlib import sha256
import ipaddress
import json
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from config import CATALYST_LOOKBACK_DAYS
from data_trust import build_source_audit_entry
from news_source_roles import is_cmoney_forum_post_url, is_cmoney_stock_overview_url
from provider_correlation import source_operation
from search_provider_runtime import SourceResponseError
from ..types import FetchRequest, ProviderResult
from .finmind_news_transport import FinMindNewsHttp, PROVIDER, decode_payload
from .identity import _stock_id_from_ticker, is_taiwan_ticker

SOURCE = "recent_catalysts"
DEADLINE_SECONDS = 10.
NON_NEWS_ROLE_REJECTIONS = frozenset({"forum_post_is_not_news", "stock_overview_is_not_news"})


def sample_dates(today):
    # Recent completed calendar days and a one-week-back sample: at most three
    # requests, never an exhaustive 30-day fetch or a claim of window coverage.
    return [(today - timedelta(days=offset)).isoformat() for offset in (1, 2, 8)
            if offset <= CATALYST_LOOKBACK_DAYS]


def _record(row, stock_id, day, receipt, index):
    if not isinstance(row, dict) or row.get("stock_id") != stock_id:
        return None, "stock_identity_mismatch"
    raw_date = row.get("date")
    try:
        if not isinstance(raw_date, str) or datetime.fromisoformat(raw_date).date().isoformat() != day:
            raise ValueError
    except ValueError:
        return None, "query_date_mismatch"
    title, link, publisher = row.get("title"), row.get("link"), row.get("source")
    if (not isinstance(title, str) or not title.strip() or len(title) > 1000
            or not isinstance(link, str) or len(link) > 4000
            or not isinstance(publisher, str) or not publisher.strip()):
        return None, "missing_headline_fields"
    try:
        parsed = urlsplit(link)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
                or parsed.hostname in {"localhost", "localhost.localdomain"} or "." not in parsed.hostname):
            raise ValueError
        try:
            ipaddress.ip_address(parsed.hostname)
        except ValueError:
            pass
        else:
            raise ValueError
    except ValueError:
        return None, "invalid_news_link"
    if is_cmoney_forum_post_url(link):
        return None, "forum_post_is_not_news"
    if is_cmoney_stock_overview_url(link):
        return None, "stock_overview_is_not_news"
    summary = row.get("description")
    return {"date": day, "title": title.strip(), "summary": summary[:280] if isinstance(summary, str) else "",
            "source": publisher.strip(), "link": link, "source_type": "finmind_news",
            "content_coverage": "headline_or_snippet", "publication_date_precision": "day",
            "publication_date_original": {"finmind_date": raw_date, "timezone": "not_reported"},
            "finmind_news_receipt": {"stock_id": stock_id, "query_date": day, "row_index": index,
                                     "row_sha256": sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                                     "raw_http_receipt": receipt}}, ""


def fetch_finmind_news_result(request: FetchRequest) -> ProviderResult:
    started = time.time()
    today = datetime.fromtimestamp(started, ZoneInfo("Asia/Taipei")).date()
    planned = sample_dates(today)
    client = FinMindNewsHttp(time.monotonic() + DEADLINE_SECONDS)
    records, rejected, raw_count, duplicates, error_kind = [], Counter(), 0, 0, ""
    new_record_count, cached_record_count = 0, 0
    seen = set()
    with source_operation(SOURCE, PROVIDER):
        if is_taiwan_ticker(request.ticker):
            stock_id = _stock_id_from_ticker(request.ticker)
            for day in planned:
                try:
                    raw, receipt = client.get(stock_id, day)
                    rows = decode_payload(raw)
                    if time.monotonic() >= client.deadline:
                        raise SourceResponseError("timeout")
                    raw_count += len(rows)
                    before_count = len(records)
                    for original_index, original_row in sorted(
                            enumerate(rows), key=lambda pair: str(pair[1].get("date", "")) if isinstance(pair[1], dict) else "", reverse=True):
                        record, reason = _record(original_row, stock_id, day, receipt, original_index)
                        if time.monotonic() >= client.deadline:
                            raise SourceResponseError("timeout")
                        if reason:
                            rejected[reason] += 1
                            continue
                        marker = record["link"]
                        if marker in seen:
                            duplicates += 1
                            continue
                        seen.add(marker)
                        if len(records) < 20:
                            records.append(record)
                    selected_count = len(records) - before_count
                    if client.components[-1].get("http_request_sent") and not client.components[-1].get("cache_hit"):
                        new_record_count += selected_count
                    else:
                        cached_record_count += selected_count
                    if records:
                        break
                except SourceResponseError as exc:
                    error_kind = exc.error_kind
                    break
        else:
            error_kind = "not_applicable"
        if time.monotonic() >= client.deadline and not error_kind:
            error_kind = "timeout"
        components = client.components
        sent = client.http_request_count > 0
        # A retained cache value may accompany a real HTTP refusal. Only an
        # operation without any sent request is a cache-only observation.
        cached = bool(components) and not sent and all(c.get("cache_hit") for c in components)
        mixed_cached_only = bool(records) and sent and not new_record_count
        stamps = [c["fetched_at_epoch"] for c in components if c.get("fetched_at_epoch") is not None]
        role_only_rejections = bool(rejected) and set(rejected).issubset(NON_NEWS_ROLE_REJECTIONS)
        fresh_valid_records = bool(records) and new_record_count > 0
        degraded = mixed_cached_only or bool(rejected) and not (role_only_rejections and fresh_valid_records)
        status = ("error" if error_kind else "degraded_enrichment" if degraded else "success" if records else "unavailable")
        if error_kind in {"not_applicable", "cooldown", "single_flight_busy", "ProviderCircuitOpenError", "ProviderRateLimitOpenError"}:
            status = "unavailable"
        if cached and status == "success":
            status = "skipped_fresh_cache"
        stamp = min(stamps) if stamps and not error_kind else None
        audit = build_source_audit_entry(
            SOURCE, PROVIDER, status, started_at_epoch=started, finished_at_epoch=time.time(),
            fetched_at_epoch=stamp, record_count=len(records), cache_hit=cached, stale=False,
            error_kind=error_kind, message=("FinMind 單日入口取得近期新聞；有限日期取樣，不代表完整時間窗。" if records else
                                         "FinMind 指定日期未取得可用新聞；不代表時間窗內沒有事件。" if not error_kind else
                                         "FinMind 新聞取得失敗；保留來源錯誤並停止後續查詢。"))
        audit.update(http_request_sent=sent, http_request_count=client.http_request_count,
                     event_kind="aggregate", fetched_at_epoch=stamp, sampled_dates=[c["query_date"] for c in components],
                     planned_dates=planned, coverage_status="bounded_daily_samples", lookback_days=CATALYST_LOOKBACK_DAYS,
                     raw_count=raw_count, usable_count=len(records), rejected_count=sum(rejected.values()),
                     rejected_reason_counts=dict(rejected), duplicate_count=duplicates, components=components,
                     new_record_count=new_record_count, cached_record_count=cached_record_count,
                     quality_status="partial" if rejected or error_kind else "headline_metadata_only")
        if mixed_cached_only and not error_kind:
            audit.update(quality_status="partial_acquisition_with_cached_records",
                         message="本次指定日期未取得新增新聞；保留仍有效的快取原件，不當作新的有資料抓取。")
        if time.monotonic() >= client.deadline:
            audit["deadline_exhausted"] = True
            if not error_kind:
                status = "error"
                audit.update(status=status, error_kind="timeout", quality_status="partial", fetched_at_epoch=None,
                             message="FinMind 新聞處理超過總期限；保留限制，不當作成功取得。")
                stamp = None
        if stamp is None:
            audit["fetched_at"] = None
        return ProviderResult(source=SOURCE, provider=PROVIDER, status=status, value=records, audit=audit,
                              duration_ms=audit.get("duration_ms") or 0)
