"""Quality scoring and selection helpers for alternative search results."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from urllib.parse import urlparse

from config import SEARCH_MIN_UNIQUE_SOURCES, SEARCH_PROVIDER_EXPANSION_MIN_RESULTS
from external_search_payloads import dedupe_results
from external_search_types import SearchResult
from news_freshness_policy import news_cutoff, publisher_identity
from news_record_utils import canonical_link, parse_news_datetime


MIN_UNIQUE_SOURCES_BEFORE_STOP = SEARCH_MIN_UNIQUE_SOURCES
MIN_SEARCH_QUALITY_SCORE = 2

_GENERIC_SEARCH_TERMS = {
    "global",
    "competitors",
    "peers",
    "gross",
    "margin",
    "earnings",
    "outlook",
    "revenue",
    "catalyst",
    "investment",
    "supply",
    "chain",
    "法說會",
    "展望",
    "供應鏈",
    "營收",
    "投資",
    "同業",
    "競爭",
    "毛利率",
}


def search_quality_satisfied(
    records: list[SearchResult],
    *,
    max_results: int,
    query: str = "",
    lookback_days: int = 30,
    require_recent: bool = False,
    cutoff=None,
) -> bool:
    if require_recent:
        records = _recent_results(records, lookback_days=lookback_days, cutoff=cutoff)
    target_results = max(1, int(max_results))
    if len(records) < target_results:
        return False
    if target_results <= 1:
        return True
    source_count = len({result_source_key(record) for record in records if result_source_key(record)})
    if source_count < required_unique_sources(target_results):
        return False
    quality_count = sum(1 for record in records if is_quality_result(record, query, lookback_days=lookback_days, cutoff=cutoff))
    return quality_count >= required_quality_results(target_results)


def select_quality_results(
    records: list[SearchResult],
    *,
    limit: int,
    query: str = "",
    lookback_days: int = 30,
    require_recent: bool = False,
    cutoff=None,
) -> list[SearchResult]:
    if int(limit) <= 0:
        return []
    if require_recent:
        records = _recent_results(records, lookback_days=lookback_days, cutoff=cutoff)
    deduped = dedupe_results(records, limit=max(len(records), int(limit)))
    if len(deduped) <= 1:
        return deduped[:limit]

    ranked = sorted(
        enumerate(deduped),
        key=lambda item: (
            -result_quality_score(item[1], query, lookback_days=lookback_days, cutoff=cutoff),
            item[0],
        ),
    )
    quality_first = [record for _index, record in ranked]

    selected: list[SearchResult] = []
    selected_ids: set[tuple[str, str]] = set()
    seen_sources: set[str] = set()
    for record in quality_first:
        source_key = result_source_key(record)
        if source_key in seen_sources:
            continue
        selected.append(record)
        selected_ids.add((record.link.strip().lower(), record.title.strip().lower()))
        seen_sources.add(source_key)
        if len(selected) >= limit:
            return selected

    for record in quality_first:
        record_id = (record.link.strip().lower(), record.title.strip().lower())
        if record_id in selected_ids:
            continue
        selected.append(record)
        if len(selected) >= limit:
            break
    return selected


def _recent_results(records: list[SearchResult], *, lookback_days: int, cutoff=None) -> list[SearchResult]:
    from datetime import timedelta

    reference = news_cutoff(cutoff)
    lower = reference - timedelta(days=max(1, int(lookback_days)))
    return [record for record in records
            if (published := parse_result_date(record.published_at)) is not None and lower <= published <= reference]


def result_source_key(record: SearchResult) -> str:
    host = (urlparse(canonical_link(record.link)).hostname or "").lower().removeprefix("www.")
    if host and host not in {"news.google.com", "google.com", "search.yahoo.com"}:
        return host
    return publisher_identity({"link": record.link, "source": record.source})[1]


def provider_request_size(remaining: int, *, max_results: int) -> int:
    target_results = max(1, int(max_results))
    expansion_min = max(1, int(SEARCH_PROVIDER_EXPANSION_MIN_RESULTS))
    if remaining <= 0:
        return min(target_results, expansion_min)
    return min(target_results, max(max(1, int(remaining)), expansion_min))


def required_unique_sources(max_results: int) -> int:
    target_results = max(1, int(max_results))
    if target_results <= 1:
        return 1
    if target_results <= 4:
        return min(2, target_results)
    return min(max(2, int(MIN_UNIQUE_SOURCES_BEFORE_STOP)), target_results)


def required_quality_results(max_results: int) -> int:
    target_results = max(1, int(max_results))
    if target_results <= 2:
        return target_results
    return min(target_results, max(3, target_results - 2))


def is_quality_result(record: SearchResult, query: str, *, lookback_days: int, cutoff=None) -> bool:
    return result_quality_score(record, query, lookback_days=lookback_days, cutoff=cutoff) >= MIN_SEARCH_QUALITY_SCORE


def result_quality_score(record: SearchResult, query: str, *, lookback_days: int, cutoff=None) -> int:
    score = 0
    text = normalise_search_text(" ".join((record.title, record.snippet, record.source, record.link)))
    terms = query_terms(query)
    specific_terms = [term for term in terms if term not in _GENERIC_SEARCH_TERMS]
    matched_specific = [term for term in specific_terms if term in text]
    matched_terms = [term for term in terms if term in text]
    if matched_specific:
        score += 3
    elif matched_terms:
        score += 1

    if result_source_key(record) and record.link.strip():
        score += 1

    parsed_date = parse_result_date(record.published_at)
    if parsed_date is not None:
        now = news_cutoff(cutoff)
        age_days = max(0, int((now - parsed_date).total_seconds() // 86400))
        if age_days <= max(1, int(lookback_days)) + 1:
            score += 1
        elif age_days > max(1, int(lookback_days)) * 2:
            score -= 2

    return score


def query_terms(query: str) -> list[str]:
    terms: list[str] = []
    for raw in re.split(r"\s+", str(query or "")):
        term = normalise_search_text(raw).strip(" -_/|()[]{}:;,.，。")
        if len(term) >= 2 and term not in terms:
            terms.append(term)
    return terms


def normalise_search_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def parse_result_date(value: str) -> datetime | None:
    return parse_news_datetime(value)
