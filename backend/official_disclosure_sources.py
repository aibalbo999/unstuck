"""TWSE/TPEx daily public disclosures with bounded, shared acquisition.

The exchange endpoints are daily snapshots, not historical searches. Publication
time, fact date and acquisition time remain distinct throughout normalization.
"""
from __future__ import annotations

from datetime import date, datetime, time as date_time
import hashlib
import json
import re
import time
from zoneinfo import ZoneInfo

from external_http_client import sync_get
from search_provider_runtime import (
    SourceResponseError, cooldown_state, observe_http_response, record_observation,
    remember_failure, scope_key,
)
from shared_provider_cache import shared_fetch

SOURCE = "official_disclosures"
PARSER_VERSION = "exchange-daily-disclosures-v1"
MAX_TEXT_CHARS = 12_000
FRESHNESS_SECONDS = 300
TAIPEI = ZoneInfo("Asia/Taipei")
MARKETS = {
    "twse": {"provider": "TWSE official disclosures", "suffix": ".TW",
             "url": "https://openapi.twse.com.tw/v1/opendata/t187ap04_L",
             "issuer": "公司代號", "company": "公司名稱"},
    "tpex": {"provider": "TPEx official disclosures", "suffix": ".TWO",
             "url": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O",
             "issuer": "SecuritiesCompanyCode", "company": "CompanyName"},
}
COVERAGE_NOTE = "交易所僅提供當日公告快照；本機索引自啟用後累積，不能據此判定查詢期間沒有其他公告，亦不計為獨立媒體來源。"


def _roc_date(value) -> date:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{7}", text):
        raise ValueError("Unknown exchange date")
    return date(int(text[:3]) + 1911, int(text[3:5]), int(text[5:]))


def parse_disclosure_rows(payload, market: str, *, observed_at_epoch: float) -> tuple[list[dict], int]:
    """Reject unidentifiable/future records without changing the raw explanation."""
    spec = MARKETS[market]
    if not isinstance(payload, list) or len(payload) > 20_000:
        raise ValueError("Unknown exchange disclosure envelope")
    documents, seen, rejected = [], set(), 0
    for raw in payload:
        if not isinstance(raw, dict):
            raise ValueError("Unknown exchange disclosure row")
        row = {str(key).strip(): value for key, value in raw.items()}
        if not {spec["issuer"], "發言日期", "主旨"}.issubset(row):
            raise ValueError("Unknown exchange disclosure columns")
        issuer = str(row.get(spec["issuer"]) or "").strip()
        title = str(row.get("主旨") or "").strip()
        try:
            if not re.fullmatch(r"\d{4,6}", issuer) or not title:
                raise ValueError("Missing disclosure issuer/title")
            published_date = _roc_date(row.get("發言日期"))
            raw_time = str(row.get("發言時間") or "").strip()
            if raw_time:
                if not re.fullmatch(r"\d{1,6}", raw_time):
                    raise ValueError("Unknown exchange publication time")
                clock = raw_time.zfill(6)
                published = datetime.combine(published_date, date_time(int(clock[:2]), int(clock[2:4]), int(clock[4:]), tzinfo=TAIPEI))
                if published.timestamp() > observed_at_epoch:
                    raise ValueError("Future disclosure publication")
                published_at = published.isoformat()
            else:
                if published_date > datetime.fromtimestamp(observed_at_epoch, TAIPEI).date():
                    raise ValueError("Future disclosure publication")
                published_at = published_date.isoformat()
        except (ValueError, TypeError, OverflowError):
            rejected += 1
            continue
        try:
            event_date = _roc_date(row.get("事實發生日")).isoformat()
        except (ValueError, TypeError, OverflowError):
            event_date = None
        raw_text = row.get("說明")
        if raw_text is not None and not isinstance(raw_text, str):
            rejected += 1
            continue
        raw_text = raw_text or ""
        content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        ticker = issuer + spec["suffix"]
        # These daily schemas expose no official sequence ID. Publication and
        # title identify the event; corrected fact dates/text become index
        # revisions, rather than separate conflicting announcements.
        identity = json.dumps([spec["provider"], ticker, published_at, title], ensure_ascii=False, separators=(",", ":"))
        document_id = "disclosure:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
        if document_id in seen:
            continue
        seen.add(document_id)
        documents.append({
            "document_id": document_id, "ticker": ticker, "company_name": str(row.get(spec["company"]) or "")[:120],
            "title": title[:500], "url": spec["url"], "published_at": published_at,
            "event_date": event_date, "source": spec["provider"], "source_type": "official_disclosure",
            "document_kind": "announcement", "summary": raw_text[:1800], "text": raw_text[:MAX_TEXT_CHARS],
            "content_truncated": len(raw_text) > MAX_TEXT_CHARS, "original_text_chars": len(raw_text),
            "content_sha256": hashlib.sha256(raw_text[:MAX_TEXT_CHARS].encode("utf-8")).hexdigest(),
            "raw_content_sha256": content_hash, "retrieved_at_epoch": observed_at_epoch,
            "coverage_status": "text_available" if raw_text.strip() else "metadata_only",
        })
    return documents, rejected


def fetch_disclosure_snapshot(market: str) -> tuple[dict, dict]:
    """One whole-market observation per five minutes, including valid-empty days."""
    spec = MARKETS[market]
    key = scope_key(spec["provider"], endpoint="daily_disclosures")
    captured = {}
    def fetch():
        try:
            return _fetch_snapshot(market, key)
        except SourceResponseError as exc:
            captured.update(exc.diagnostic)
            raise
    snapshot, meta = shared_fetch(f"{PARSER_VERSION}:{market}", fetch, freshness_seconds=FRESHNESS_SECONDS)
    if meta.get("error_kind"):
        details = {**meta, **cooldown_state(key), **captured}
        if not captured:
            details.update(http_request_sent=False, event_kind="local_block")
        error = SourceResponseError(details.get("error_kind") or "provider_error", status_code=details.get("http_status"), parser_version=PARSER_VERSION)
        error.diagnostic.update(details, actual_provider=spec["provider"])
        raise error
    details = {**snapshot["diagnostic"], **meta, "actual_provider": spec["provider"]}
    # shared_fetch finishes just after parsing; the snapshot's timestamp is the
    # acquisition used by its documents and must not move on subsequent reads.
    details["fetched_at_epoch"] = snapshot["retrieved_at_epoch"]
    if meta.get("cache_hit"):
        details.update(http_request_sent=False, event_kind="cache_hit")
    return snapshot, details


def _fetch_snapshot(market: str, cooldown_key: str) -> dict:
    spec = MARKETS[market]
    started = time.monotonic()
    blocked = cooldown_state(cooldown_key)
    if blocked:
        record_observation(spec["provider"], started, outcome="cooldown", source=SOURCE, details=blocked, sent=False)
        error = SourceResponseError(blocked.get("error_kind", "cooldown"), status_code=blocked.get("http_status"), parser_version=PARSER_VERSION)
        error.diagnostic.update(blocked, http_request_sent=False, event_kind="local_block")
        raise error
    response = None
    observe_http_response(None)
    try:
        response = sync_get(spec["url"], timeout=(5, 15), provider=spec["provider"])
        observe_http_response(response)
        response.raise_for_status()
        if len(response.content) > 10 * 1024 * 1024:
            raise ValueError("Oversized exchange snapshot")
        payload = response.json()
        acquired_at = time.time()
        documents, rejected = parse_disclosure_rows(payload, market, observed_at_epoch=acquired_at)
        if payload and not documents and rejected:
            raise ValueError("No valid exchange disclosure rows")
    except Exception as original:
        if isinstance(original, (ValueError, TypeError, KeyError)):
            original = SourceResponseError("parse_error", status_code=getattr(response, "status_code", None), parser_version=PARSER_VERSION)
        details = remember_failure(cooldown_key, original)
        details.update(parser_version=PARSER_VERSION, actual_provider=spec["provider"], http_request_sent=True, event_kind="http_attempt")
        record_observation(spec["provider"], started, outcome="failure", source=SOURCE, details=details)
        error = SourceResponseError(details["error_kind"], status_code=details.get("http_status"), parser_version=PARSER_VERSION)
        error.diagnostic.update(details)
        raise error from original
    details = {"http_status": response.status_code, "parser_version": PARSER_VERSION,
               "outcome": "results" if documents else "valid_empty", "http_request_sent": True,
               "event_kind": "http_attempt", "coverage_status": "partial", "rejected_record_count": rejected}
    record_observation(spec["provider"], started, outcome=details["outcome"], count=len(documents), source=SOURCE, details=details)
    return {"documents": documents, "retrieved_at_epoch": acquired_at, "diagnostic": details}
