"""Select recent news at a fixed input cutoff; preserve excluded evidence separately."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from copy import deepcopy
import re
import time
from urllib.parse import urlsplit

from config import CATALYST_LOOKBACK_DAYS, SEARCH_CATALYST_MAX_RESULTS
from news_record_utils import canonical_link, parse_news_datetime
from news_source_roles import is_finmind_forum_news_record, is_finmind_stock_overview_record

_DATE_KEYS = ("date", "published_date", "published_at", "publication_date", "pubDate")
_NEWS_BUCKETS = ("recent_catalysts", "additional_recent_catalysts", "historical_catalysts", "unverified_catalysts", "identity_rejected_catalysts")
_WRAPPER_HOSTS = {"news.google.com", "www.google.com", "google.com", "search.yahoo.com"}
_AGGREGATOR_NAMES = {"google", "google news", "google news rss", "yahoo", "yahoo finance", "yahoo news",
                     "gdelt", "finmind", "brave", "brave search", "bing", "tavily", "serpapi", "alternative"}


def news_cutoff(value: Any = None) -> datetime:
    if value is None:
        return datetime.fromtimestamp(time.time(), timezone.utc)
    parsed = parse_news_datetime(value)
    if parsed is None:
        raise ValueError("News cutoff must be a valid absolute timestamp")
    return parsed


def publication_datetime(record: dict) -> datetime | None:
    for key in _DATE_KEYS:
        parsed = parse_news_datetime(record.get(key))
        if parsed is not None:
            return parsed
    return None


def publisher_identity(record: dict) -> tuple[str, str, str]:
    """A search wrapper is delivery infrastructure, not a reported publisher."""
    source = str((record.get("publisher") if record.get("publisher_status") != "domain" else None) or record.get("source") or "").strip()
    link = canonical_link(record.get("link") or record.get("url"))
    host = (urlsplit(link).hostname or "").lower().removeprefix("www.")
    # An issuer-hosted reprint links to this original publisher. Keep its
    # reported brand and normal direct-domain observations in one publisher.
    if host == 'digitimes.com' and source.casefold() in {'', 'digitimes', 'digitimes.com', 'www.digitimes.com'}:
        return 'DigiTimes', 'digitimes.com', 'reported' if source else 'domain'
    if source and source.casefold() not in _AGGREGATOR_NAMES and source.lower() not in _WRAPPER_HOSTS:
        return source, source.casefold(), "reported"
    if host and host not in _WRAPPER_HOSTS:
        return host, host, "domain"
    return "", "", "unknown"


def _normalized(record: dict, cutoff: datetime, lower: datetime) -> dict:
    item = dict(record)
    original_dates = item.get("publication_date_original")
    item["publication_date_original"] = dict(original_dates) if isinstance(original_dates, dict) else {
        key: item[key] for key in _DATE_KEYS if item.get(key)
    }
    published = publication_datetime(item)
    item["date"] = item["published_date"] = published.isoformat() if published else ""
    item["news_date_status"] = (
        "unknown" if published is None else "future" if published > cutoff
        else "historical" if published < lower else "recent"
    )
    item["publisher"], item["publisher_key"], item["publisher_status"] = publisher_identity(item)
    # Keep the exact provider URL for traceability, even when it is a wrapper.
    if not item.get("link") and item.get("url"):
        item["link"] = item["url"]
    return item


def _dedupe(records: list[dict], *, ticker=None) -> list[dict]:
    kept, links, titles, ordinary_events = [], set(), set(), set()
    # A duplicate carrying a verified date can replace an undated wrapper.
    ranked = sorted(enumerate(records), key=lambda pair: (pair[1]["news_date_status"] == "unknown", pair[0]))
    for _index, record in ranked:
        link = canonical_link(record.get("link") or record.get("url"))
        json_identity = None
        from official_event_identity import ordinary_event_key
        ordinary_identity = ordinary_event_key(record, ticker)
        if record.get('source_type') == 'mops_issuer_announcement':
            from data_fetch.market_sources.mops_json_company_history import announcement_link_identity
            json_identity = announcement_link_identity(record)
            link = json_identity or link
        if record.get('source_type') == 'tdr_foreign_issuer_announcement':
            from data_fetch.market_sources.tdr_mops_history import announcement_link_identity
            # The official original is POST-only. Its exact filing parameters
            # identify the event; the general MOPS page remains the real link.
            link = announcement_link_identity(record) or link
        title = str(record.get("title") or "").strip().casefold()
        # Google RSS appends its reported publisher to the headline. The
        # matching original URL must not become an extra article merely
        # because it omits that suffix. Preserve the actual title and URL.
        if ((urlsplit(canonical_link(record.get('link') or record.get('url'))).hostname or '').lower() == 'news.google.com'
                and record.get('publisher_status') == 'reported' and record.get('publisher')):
            title = re.sub(r'\s+[-–—－]\s*' + re.escape(record['publisher'].casefold()) + r'$', '', title).strip()
        if ((link and link in links) or (ordinary_identity and ordinary_identity in ordinary_events)
                or (title and title in titles and not (json_identity or ordinary_identity)) or not (link or title)):
            continue
        kept.append(record)
        if link:
            links.add(link)
        if title:
            titles.add(title)
        if ordinary_identity:
            ordinary_events.add(ordinary_identity)
    return kept


def apply_news_freshness(
    data: dict, *, cutoff: Any = None, records: list[dict] | None = None,
    lookback_days: int = CATALYST_LOOKBACK_DAYS, limit: int = SEARCH_CATALYST_MAX_RESULTS,
) -> dict:
    """Normalize a working payload; callers must copy persisted snapshots before applying."""
    from source_content_selection import (
        issuer_match, company_aliases, reselect_social_context,
        _indexed_non_article_unverified,
    )
    reference = news_cutoff(cutoff)
    reselect_social_context(data, cutoff=reference)
    if records is None and not any(key in data for key in _NEWS_BUCKETS):
        return data
    window = max(1, int(lookback_days))
    lower = reference - timedelta(days=window)
    candidates = list(records) if records is not None else [
        record for key in _NEWS_BUCKETS for record in (data.get(key) or []) if isinstance(record, dict)
    ]
    normalized = _dedupe([_normalized(record, reference, lower) for record in candidates if isinstance(record, dict)], ticker=data.get('ticker'))
    identity_rejected = []
    if company_aliases(data) or str(data.get('ticker') or '').strip():
        identity_rejected = [item for item in normalized if not issuer_match(item, data)]
        normalized = [item for item in normalized if issuer_match(item, data)]
    # Replayed legacy buckets must retain the same source-role exclusions as
    # newly acquired records. An indexing date cannot turn a metric into news.
    role_unverified, eligible = [], []
    for item in normalized:
        link = canonical_link(item.get('link') or item.get('url'))
        reason = ('forum_post_is_not_news' if is_finmind_forum_news_record(item, link)
                  else 'stock_overview_is_not_news' if is_finmind_stock_overview_record(item, link)
                  else 'indexed_non_article_unverified' if _indexed_non_article_unverified(item, link)
                  else '')
        if reason:
            item['source_role_status'] = reason
            role_unverified.append(item)
        else:
            eligible.append(item)
    normalized = eligible
    recent = sorted((item for item in normalized if item["news_date_status"] == "recent"),
                    key=lambda item: item["date"], reverse=True)
    data['identity_rejected_catalysts'] = identity_rejected
    selected, remaining, publishers = [], [], set()
    bounded_limit = max(0, int(limit))
    for item in recent:
        publisher = item["publisher_key"]
        if publisher and publisher not in publishers and len(selected) < bounded_limit:
            selected.append(item)
            publishers.add(publisher)
        else:
            remaining.append(item)
    available_slots = bounded_limit - len(selected)
    selected.extend(remaining[:available_slots])
    data["recent_catalysts"] = selected
    data["additional_recent_catalysts"] = remaining[available_slots:]
    data["historical_catalysts"] = [item for item in normalized if item["news_date_status"] == "historical"]
    data["unverified_catalysts"] = [
        item for item in normalized if item["news_date_status"] in {"unknown", "future"}
    ] + role_unverified
    data["news_selection"] = {
        "policy_version": "recent-news-v1", "cutoff": reference.isoformat(),
        "window_start": lower.isoformat(), "lookback_days": window,
        "recent_count": len(selected), "eligible_count": len(recent),
        "identity_rejected_count": len(identity_rejected),
        "source_role_unverified_count": len(role_unverified),
        "historical_count": len(data["historical_catalysts"]),
        "unknown_date_count": sum(item["news_date_status"] == "unknown" for item in normalized),
        "future_date_count": sum(item["news_date_status"] == "future" for item in normalized),
        "publisher_count": len({item["publisher_key"] for item in selected if item["publisher_key"]}),
        "publisher_basis": "reported publisher or direct domain; independence not verified",
        "status": "no_recent_evidence" if not recent else "limited_recent_evidence" if len(selected) < 3 else "available",
        "coverage_note": "超過時間窗的舊聞保留為歷史背景；日期未知或晚於分析截止的新聞不作近期證據。",
    }
    return data


def apply_news_only_freshness(
    data: dict, *, cutoff: Any = None, records: list[dict] | None = None,
    lookback_days: int = CATALYST_LOOKBACK_DAYS, limit: int = SEARCH_CATALYST_MAX_RESULTS,
) -> dict:
    """Project news fields while preserving unrelated saved source contexts."""
    context = {key: deepcopy(data[key]) for key in (
        'ticker', 'company_name', 'company_identity', 'instrument_type', *_NEWS_BUCKETS,
    ) if key in data}
    apply_news_freshness(context, cutoff=cutoff, records=records,
                         lookback_days=lookback_days, limit=limit)
    for key in (*_NEWS_BUCKETS, 'news_selection'):
        if key in context:
            data[key] = deepcopy(context[key])
    return data
