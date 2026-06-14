"""Merge optional HTTP enrichment into legacy-compatible payloads."""

from __future__ import annotations

import time as time_module
from typing import Optional, Sequence

from data_trust import (
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_UNAVAILABLE,
    finalize_data_trust,
    source_record_count,
)
from .market_sources.common import _dedupe_records, first_number, is_missing_value

from .audit_helpers import _append_source_fetch_audit, _mark_market_data_fetched, _mark_sources_fetched
from .formatting import format_number


def _merge_optional_http_bundle(
    data: dict,
    http_bundle: dict,
    refreshed_sources: Optional[Sequence[str]] = None,
    source_errors: Optional[dict] = None,
) -> dict:
    """Merge async HTTP-backed enrichment into a base yfinance/FinMind payload."""
    if not data or "error" in data or not http_bundle:
        return data
    refreshed_sources = tuple(refreshed_sources or ())
    source_errors = source_errors or {}
    refresh_epoch = time_module.time()
    ticker = str(data.get("ticker") or "").strip().upper()

    combined_catalysts = list(data.get("recent_catalysts", []) or [])
    combined_catalysts.extend(http_bundle.get("google_catalysts", []) or [])
    combined_catalysts.extend(http_bundle.get("fmp_news", []) or [])
    if combined_catalysts:
        data["recent_catalysts"] = _dedupe_records(combined_catalysts, limit=5)[:5]

    peer_discovery = http_bundle.get("google_peer_discovery", []) or []
    if peer_discovery:
        data["peer_discovery_results"] = _dedupe_records(peer_discovery, limit=5)

    global_context = http_bundle.get("global_market_context", {}) or {}
    if isinstance(global_context, dict) and global_context:
        data["global_market_context"] = global_context

    news_context = http_bundle.get("international_news_context", {}) or {}
    if isinstance(news_context, dict) and news_context:
        data["international_news_context"] = news_context

    fmp_quote = http_bundle.get("fmp_quote", {}) or {}
    if isinstance(fmp_quote, dict) and fmp_quote:
        updated_fields = []
        if is_missing_value(data.get("current_price")):
            current_price = first_number(fmp_quote.get("price"), fmp_quote.get("previousClose"))
            if current_price is not None:
                data["current_price"] = current_price
                data["current_price_fmt"] = f"NT${current_price:.2f}"
                updated_fields.append("current_price")
        if is_missing_value(data.get("market_cap_raw")):
            market_cap = first_number(fmp_quote.get("marketCap"))
            if market_cap is not None:
                data["market_cap_raw"] = market_cap
                data["market_cap_fmt"] = format_number(market_cap, "億")
                updated_fields.append("market_cap")
        if is_missing_value(data.get("pe_ratio_raw")):
            pe_ratio = first_number(fmp_quote.get("pe"), fmp_quote.get("peRatio"))
            if pe_ratio is not None:
                data["pe_ratio_raw"] = pe_ratio
                data["pe_ratio"] = f"{pe_ratio:.1f}x"
                updated_fields.append("pe_ratio")
        if is_missing_value(data.get("week_52_high")):
            week_52_high = first_number(fmp_quote.get("yearHigh"), fmp_quote.get("priceAvg200"))
            if week_52_high is not None:
                data["week_52_high"] = week_52_high
                data["week_52_high_fmt"] = f"NT${week_52_high:.2f}"
                updated_fields.append("week_52_high")
        if is_missing_value(data.get("week_52_low")):
            week_52_low = first_number(fmp_quote.get("yearLow"))
            if week_52_low is not None:
                data["week_52_low"] = week_52_low
                data["week_52_low_fmt"] = f"NT${week_52_low:.2f}"
                updated_fields.append("week_52_low")

        if updated_fields:
            _mark_market_data_fetched(
                data,
                ticker,
                fetched_at_epoch=refresh_epoch,
                cache_hit=bool(data.get("_cache_hit")),
            )
            _append_source_fetch_audit(
                data,
                "market_data",
                "FMP stable quote",
                AUDIT_STATUS_SUCCESS,
                fetched_at_epoch=refresh_epoch,
                finished_at_epoch=refresh_epoch,
                record_count=len(updated_fields),
                cache_hit=bool(data.get("_cache_hit")),
                stale=False,
                message="async FMP quote bundle 補齊缺漏市場欄位：" + ", ".join(updated_fields),
            )
            data.setdefault("data_source_notes", []).append(
                "部分市場欄位由 async FMP quote bundle 補值：" + ", ".join(updated_fields)
            )

    if refreshed_sources:
        _mark_sources_fetched(
            data,
            ticker,
            refreshed_sources,
            fetched_at_epoch=refresh_epoch,
            cache_hit=bool(data.get("_cache_hit")),
        )
        for source in refreshed_sources:
            count = source_record_count(source, data)
            error_message = str(source_errors.get(source) or "")
            if count > 0:
                status = AUDIT_STATUS_SUCCESS
                error_kind = ""
                message = "optional 外部來源已重新抓取並合併。"
            elif error_message:
                status = AUDIT_STATUS_ERROR
                error_kind = "async_fetch_error"
                message = error_message[:240]
            else:
                status = AUDIT_STATUS_UNAVAILABLE
                error_kind = ""
                message = "optional 外部來源本次未回傳可用資料。"
            _append_source_fetch_audit(
                data,
                source,
                _optional_provider_label(source),
                status,
                fetched_at_epoch=refresh_epoch,
                finished_at_epoch=refresh_epoch,
                record_count=count,
                cache_hit=bool(data.get("_cache_hit")),
                stale=False,
                error_kind=error_kind,
                message=message,
            )

    finalize_data_trust(data)
    return data


def _optional_provider_label(source: str) -> str:
    if source == "recent_catalysts":
        return "Google Search/FMP"
    if source == "global_market_context":
        return "Global market context"
    if source == "international_news_context":
        return "International news context"
    return "Google Search"
