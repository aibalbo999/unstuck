"""A fallback decision from current curated evidence, using the original search gate."""
from __future__ import annotations

import hashlib
import math

from config import CATALYST_LOOKBACK_DAYS, SEARCH_CATALYST_MAX_RESULTS
from external_search_quality import search_quality_satisfied, select_quality_results, result_source_key
from external_search_types import SearchResult
from news_freshness_policy import news_cutoff
from news_freshness_policy import publication_datetime
from report_freshness_summary import safe_bool
from source_content_selection import select_company_records
from .market_sources.twse_company_history import _detail_identity, _announcement_key, TAIPEI
from urllib.parse import parse_qs, urlsplit

CURATED_FEEDS = {"Free news waterfall", "TWSE company announcement history", "TPEx MOPS company announcement history"}
OFFICIAL_FEEDS = CURATED_FEEDS - {"Free news waterfall"}


def _current_official_cache(result, audit, cutoff):
    stamp = audit.get("fetched_at_epoch")
    if result.status != "skipped_fresh_cache" or not safe_bool(audit.get("cache_hit")) or type(stamp) not in (int,float):
        return False
    try:
        stamp = float(stamp)
        return math.isfinite(stamp) and 0 <= cutoff.timestamp()-stamp <= 1800
    except (ValueError, TypeError, OverflowError):
        return False


def _checked_official_record(record, ticker):
    if (record.get('source_type') == 'mops_issuer_announcement'
            or 'mops_json_receipt' in record):
        from .market_sources.mops_json_company_history import verified_json_record
        return bool(verified_json_record(record, {'ticker': ticker}))
    try:
        published = publication_datetime(record).astimezone(TAIPEI)
        link = str(record.get("link") or "")
        return (record.get("ticker") == ticker and record.get("source_type") == "official_disclosure"
                and record.get("content_coverage") == "text_available" and record.get("content_truncated") is False
                and isinstance(record.get("text"), str) and bool(record["text"])
                and isinstance(record.get("title"), str) and bool(record["title"])
                and record["text"].split("\n",1)[0].endswith(f"（{ticker.split('.')[0]}） {record['title']}")
                and record.get("content_sha256") == hashlib.sha256(record["text"].encode()).hexdigest()
                and _detail_identity(link, ticker.split(".")[0], published)
                and parse_qs(urlsplit(link).query)["SPOKE_TIME"][0].zfill(6) == published.strftime("%H%M%S"))
    except (ValueError, TypeError, AttributeError, KeyError, UnicodeError):
        return False


def current_catalyst_evidence(data, results):
    """Never count a skipped search as acquisition, or borrow stale/unchecked records."""
    cutoff = news_cutoff()
    ticker = str(data.get("ticker") or "").upper()
    candidates, provider_counts, verified_event_keys = [], {}, {}
    for result in results:
        if result.source != "recent_catalysts" or result.provider not in CURATED_FEEDS:
            continue
        audit = result.audit if isinstance(result.audit, dict) else {}
        if safe_bool(audit.get("stale")) or not isinstance(result.value, list):
            continue
        if result.provider in OFFICIAL_FEEDS:
            current_cache = _current_official_cache(result,audit,cutoff)
            if (result.status != "success" and not current_cache) or audit.get("coverage_status") != "window_complete":
                continue
            records, seen = [], set()
            for record in result.value:
                if not isinstance(record,dict) or not _checked_official_record(record,ticker):
                    continue
                if record.get('source_type') == 'mops_issuer_announcement':
                    from .market_sources.mops_json_company_history import announcement_link_identity
                    identity = announcement_link_identity(record)
                else:
                    identity = _announcement_key(record["link"])
                if identity not in seen:
                    seen.add(identity)
                    records.append(record)
        else:
            if (result.status not in {"success", "degraded_enrichment"}
                    or audit.get("selection_policy") != "company-time-v1"
                    or audit.get("quality_status") != "eligible_evidence"):
                continue
            records = result.value
        selected, _ = select_company_records(records, data, cutoff=cutoff, lookback_days=CATALYST_LOOKBACK_DAYS)
        if len(selected) < 3:
            continue
        provider_counts[result.provider] = len(selected)
        for record in selected:
            if (not isinstance(record.get('title'),str) or not isinstance(record.get('summary') or '',str)
                    or publication_datetime(record) is None):
                continue
            candidate = SearchResult(record['title'],record.get('summary') or '',record['link'],
                                     str(record.get('publisher') or record.get('source') or ''),
                                     publication_datetime(record).isoformat())
            if record.get('source_type') == 'mops_issuer_announcement':
                from .market_sources.mops_json_company_history import announcement_link_identity
                key = announcement_link_identity(record)
                if key:
                    # Only replay-verified originals supply this private key.
                    # Generic provider metadata never supplies an override.
                    verified_event_keys[id(candidate)] = key
            candidates.append(candidate)
    target = max(1, int(SEARCH_CATALYST_MAX_RESULTS))
    chosen = select_quality_results(candidates, limit=target, query=str(data.get("company_name") or ""),
                                    require_recent=True, lookback_days=CATALYST_LOOKBACK_DAYS, cutoff=cutoff,
                                    verified_event_identity=lambda record: verified_event_keys.get(id(record)))
    enough = len(provider_counts) >= 2 and search_quality_satisfied(
        chosen, max_results=target, query=str(data.get("company_name") or ""),
        require_recent=True, lookback_days=CATALYST_LOOKBACK_DAYS, cutoff=cutoff)
    return {"sufficient": bool(enough), "required_count": target, "eligible_count": len(chosen),
            "curated_feed_counts": provider_counts,
            "publisher_count": len({result_source_key(r) for r in chosen if result_source_key(r)}),
            "selection_cutoff": cutoff.isoformat(),
            "record_refs": [{"link":r.link,"published_at":r.published_at,"publisher":r.source} for r in chosen]}
