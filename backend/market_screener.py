"""Daily market screener for upstream watchlist discovery."""

from __future__ import annotations

from datetime import date, datetime

from cache_store import get_cache_json, set_cache_json
from config import FINMIND_API_TOKEN
from data_fetch.market_sources.taiwan import DataLoader
import market_screener_sources as _sources
from market_screener_candidates import (
    attach_quality_funnel,
    build_screener_candidates,
    filter_candidates,
    merge_candidates,
    paginate_candidates,
    sort_candidates,
)
from market_screener_sources import FinMindScreenerDataSource, TwseFreeScreenerDataSource, TwseOpenApiScreenerDataSource
from market_screener_utils import TAIPEI, date_text, provider_name, taipei_now, unique
from market_screener_query import (
    annotate_watchlist_status,
    last_updated_time,
    normalize_screener_filters,
    payload_last_updated,
    scan_cache_key,
    with_screener_item_metadata,
)
import watchlist_service
import watchlist_store


AUTO_SCREENER_TAG = "Auto-Screener"
DAILY_SCREENER_SOURCE = "daily_screener"
DAILY_SCREENER_PIPELINE = "v4"
SCREENER_META_KEY = "daily_market_screener:last_run_date"
DEFAULT_SCREENER_LIMIT = 20
DEFAULT_SCREENER_CACHE_TTL_SECONDS = 15 * 60


def run_daily_market_screener(
    *,
    now: datetime | None = None,
    force: bool = False,
    data_loader_cls=DataLoader,
    data_source=None,
    data_sources: list | None = None,
    top_n: int = 10,
) -> dict:
    now = taipei_now(now)
    run_date = now.date().isoformat()
    if not force and screener_already_ran(run_date):
        return {
            "success": True,
            "market": "TW",
            "screen_date": run_date,
            "candidates": [],
            "warnings": [],
            "imported": [],
            "imported_count": 0,
            "errors": [],
            "candidate_count": 0,
            "pagination": {"limit": 0, "offset": 0, "total": 0, "has_more": False},
            "last_updated_time": now.isoformat(timespec="seconds"),
            "skipped": [{"reason": "already_ran", "run_date": run_date}],
        }
    scan = scan_taiwan_market(
        scan_date=now.date(),
        data_loader_cls=data_loader_cls,
        data_source=data_source,
        data_sources=data_sources,
        top_n=top_n,
    )
    imported = import_candidates_to_watchlist(scan.get("candidates") or [])
    pruned = prune_stale_auto_screener_items(scan.get("candidates") or []) if scan.get("success") else {"pruned": [], "pruned_count": 0}
    return {
        **scan,
        **imported,
        **pruned,
        "success": bool(scan.get("success")) and not imported.get("errors"),
        "candidate_count": len(scan.get("candidates") or []),
    }


def scan_taiwan_market(
    *,
    scan_date: date | None = None,
    data_loader_cls=DataLoader,
    data_source=None,
    data_sources: list | None = None,
    top_n: int = 10,
    filters: dict | None = None,
    limit: int | None = None,
    offset: int = 0,
    sort_by: str = "score",
    sort_direction: str = "desc",
    use_cache: bool = False,
    cache_ttl_seconds: int = DEFAULT_SCREENER_CACHE_TTL_SECONDS,
) -> dict:
    scan_date = scan_date or datetime.now(TAIPEI).date()
    warnings = []
    sources = _resolve_data_sources(data_loader_cls=data_loader_cls, data_source=data_source, data_sources=data_sources)
    normalized_filters = normalize_screener_filters(filters)
    cache_key = scan_cache_key(scan_date, sources, top_n, normalized_filters, limit, offset, sort_by, sort_direction)
    if use_cache:
        cached = get_cache_json(cache_key)
        if isinstance(cached, dict):
            return {**cached, "cache": {"hit": True, "key": cache_key}}
    institutional, institutional_provider = _first_available_frame(
        sources,
        "institutional trades",
        lambda source: source.fetch_institutional_frame(scan_date),
        warnings,
    )
    daily, daily_provider = _first_available_frame(
        sources,
        "daily prices",
        lambda source: source.fetch_daily_frame(scan_date),
        warnings,
    )
    merged = build_screener_candidates(institutional, daily, scan_date=scan_date, top_n=top_n)
    merged = annotate_watchlist_status(merged)
    filtered = filter_candidates(merged, normalized_filters)
    ordered = sort_candidates(filtered, sort_by=sort_by, sort_direction=sort_direction)
    page, pagination = paginate_candidates(ordered, limit=limit, offset=offset)
    result = {
        "success": bool(merged) or not warnings,
        "market": "TW",
        "screen_date": scan_date.isoformat(),
        "candidates": page,
        "candidate_count": len(page),
        "total_candidate_count": len(filtered),
        "pagination": pagination,
        "filters": normalized_filters,
        "providers": unique([institutional_provider, daily_provider]),
        "data_sources": unique([provider_name(source) for source in sources]),
        "warnings": warnings,
        "last_updated_time": last_updated_time(ordered, scan_date),
        "cache": {"hit": False, "key": cache_key} if use_cache else {"hit": False},
    }
    if use_cache:
        set_cache_json(cache_key, result, ttl_seconds=max(1, int(cache_ttl_seconds or DEFAULT_SCREENER_CACHE_TTL_SECONDS)))
    return result


def import_candidates_to_watchlist(candidates: list[dict]) -> dict:
    imported = []
    errors = []
    for candidate in attach_quality_funnel(merge_candidates(candidates)):
        ticker = str(candidate.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        categories = candidate.get("categories") if isinstance(candidate.get("categories"), list) else [candidate.get("category")]
        categories = [str(category) for category in categories if category]
        quality_funnel = candidate.get("quality_funnel") if isinstance(candidate.get("quality_funnel"), dict) else {}
        quality_outcome = str(quality_funnel.get("outcome") or "").strip()
        tags = list(dict.fromkeys([AUTO_SCREENER_TAG, *categories, *([f"quality:{quality_outcome}"] if quality_outcome else [])]))
        trigger = {
            "key": "daily_screener",
            "type": DAILY_SCREENER_SOURCE,
            "company_name": str(candidate.get("company_name") or ""),
            "category": candidate.get("category") or "",
            "categories": categories,
            "screen_date": str(candidate.get("screen_date") or ""),
            "reason": str(candidate.get("reason") or ""),
            "score": candidate.get("score"),
            "metrics": candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {},
            "quality_funnel": quality_funnel,
        }
        try:
            watchlist_service.upsert_watchlist_item({
                "ticker": ticker,
                "pipeline": DAILY_SCREENER_PIPELINE,
                "enabled": True,
                "schedule_slots": ["post_market"],
                "tags": tags,
                "trigger_source": DAILY_SCREENER_SOURCE,
                "triggers": [trigger],
            })
            imported.append({"ticker": ticker, "pipeline": DAILY_SCREENER_PIPELINE, "trigger": trigger})
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)[:240]})
    return {"imported": imported, "imported_count": len(imported), "errors": errors}


def prune_stale_auto_screener_items(candidates: list[dict]) -> dict:
    keep = {str(candidate.get("ticker") or "").strip().upper() for candidate in candidates if candidate.get("ticker")}
    if not keep:
        return {"pruned": [], "pruned_count": 0}
    pruned = []
    for item in watchlist_service.list_watchlist().get("items", []):
        ticker = str(item.get("ticker") or "").strip().upper()
        pipeline = str(item.get("pipeline") or "").strip().lower()
        is_auto = item.get("trigger_source") == DAILY_SCREENER_SOURCE or AUTO_SCREENER_TAG in (item.get("tags") or [])
        if not is_auto or pipeline != DAILY_SCREENER_PIPELINE or ticker in keep:
            continue
        result = watchlist_service.delete_watchlist_item(ticker, pipeline)
        if result.get("deleted"):
            pruned.append({"ticker": ticker, "pipeline": pipeline})
    return {"pruned": pruned, "pruned_count": len(pruned)}


def list_auto_screener_watchlist(
    output_dir: str | None = None,
    *,
    filters: dict | None = None,
    limit: int = DEFAULT_SCREENER_LIMIT,
    offset: int = 0,
    sort_by: str = "score",
    sort_direction: str = "desc",
) -> dict:
    payload = watchlist_service.list_watchlist_with_report_alerts(output_dir or "")
    all_items = [
        with_screener_item_metadata(item) for item in payload.get("items", [])
        if item.get("trigger_source") == DAILY_SCREENER_SOURCE or AUTO_SCREENER_TAG in (item.get("tags") or [])
    ]
    normalized_filters = normalize_screener_filters(filters)
    filtered_items = filter_candidates(all_items, normalized_filters)
    ordered_items = sort_candidates(filtered_items, sort_by=sort_by, sort_direction=sort_direction)
    items, pagination = paginate_candidates(ordered_items, limit=limit, offset=offset)
    category_counts: dict[str, int] = {}
    for item in filtered_items:
        for tag in item.get("tags") or []:
            if tag != AUTO_SCREENER_TAG:
                category_counts[tag] = category_counts.get(tag, 0) + 1
    return {
        **payload,
        "items": items,
        "category_counts": category_counts,
        "auto_screener_count": len(filtered_items),
        "pagination": pagination,
        "filters": normalized_filters,
        "sort": {"by": sort_by, "direction": sort_direction},
        "last_updated_time": payload_last_updated(payload, filtered_items),
    }


def screener_already_ran(run_date: str | date) -> bool:
    run_date_text = date_text(run_date)
    with watchlist_store._connect() as conn:
        return watchlist_store._meta_value(conn, SCREENER_META_KEY) == run_date_text


def mark_screener_ran(run_date: str | date) -> None:
    run_date_text = date_text(run_date)
    with watchlist_store._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        watchlist_store._set_meta(conn, SCREENER_META_KEY, run_date_text)
        watchlist_store._touch_store(conn)


def _sync_sources_token() -> None:
    _sources.FINMIND_API_TOKEN = FINMIND_API_TOKEN


def _resolve_data_sources(*, data_loader_cls=DataLoader, data_source=None, data_sources: list | None = None) -> list:
    _sync_sources_token()
    return _sources.resolve_data_sources(data_loader_cls=data_loader_cls, data_source=data_source, data_sources=data_sources)


def _first_available_frame(sources: list, operation: str, fetcher, warnings: list[dict]):
    return _sources.first_available_frame(sources, operation, fetcher, warnings)
