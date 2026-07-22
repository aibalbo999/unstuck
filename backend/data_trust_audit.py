"""Source audit entry helpers and source record counting."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Optional

from data_trust_constants import (
    AUDIT_STATUS_LABELS,
    AUDIT_STATUS_UNAVAILABLE,
    AUDIT_STATUSES,
    SOURCE_LABELS,
)
from data_trust_values import (
    has_value,
    list_count,
    safe_bool_value as _safe_bool,
    safe_int_value as _safe_int,
    safe_text_value as _safe_text,
    set_items as _set_items,
    string_list,
)
from mapping_fields import safe_mapping_dict, safe_sequence_items


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def iso_from_epoch(epoch: Optional[float]) -> Optional[str]:
    if isinstance(epoch, bool) or not isinstance(epoch, (int, float)) or epoch <= 0:
        return None
    try:
        epoch_value = float(epoch)
    except (OverflowError, TypeError, ValueError):
        return None
    if not math.isfinite(epoch_value):
        return None
    try:
        return datetime.fromtimestamp(epoch_value, timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def source_label(source: str) -> str:
    source_text = _safe_text(source).strip()
    return SOURCE_LABELS.get(source_text, source_text or "unknown")


def audit_status_label(status: str) -> str:
    status_text = _safe_text(status).strip()
    return AUDIT_STATUS_LABELS.get(status_text, status_text or "unknown")


def data_snapshot_filename_for_report(filename: str) -> str:
    return filename[:-5] + ".data.json" if filename.endswith(".html") else f"{filename}.data.json"


def duration_ms(started_at_epoch: Optional[float], finished_at_epoch: Optional[float], duration_ms_value: Optional[float]) -> Optional[int]:
    if isinstance(duration_ms_value, bool):
        pass
    elif isinstance(duration_ms_value, (int, float)):
        try:
            duration_value = float(duration_ms_value)
        except (OverflowError, TypeError, ValueError):
            pass
        else:
            if math.isfinite(duration_value):
                return max(0, int(round(duration_value)))
    if (
        isinstance(started_at_epoch, (int, float))
        and not isinstance(started_at_epoch, bool)
        and isinstance(finished_at_epoch, (int, float))
        and not isinstance(finished_at_epoch, bool)
    ):
        if iso_from_epoch(started_at_epoch) is None or iso_from_epoch(finished_at_epoch) is None:
            return None
        try:
            started_value = float(started_at_epoch)
            finished_value = float(finished_at_epoch)
        except (OverflowError, TypeError, ValueError):
            return None
        if math.isfinite(started_value) and math.isfinite(finished_value):
            return max(0, int(round((finished_value - started_value) * 1000)))
    return None


def build_source_audit_entry(
    source: str,
    provider: str,
    status: str,
    *,
    fetched_at_epoch: Optional[float] = None,
    fetched_at: Optional[str] = None,
    started_at_epoch: Optional[float] = None,
    finished_at_epoch: Optional[float] = None,
    duration_ms: Optional[float] = None,
    record_count: Optional[int] = None,
    cache_hit: bool = False,
    stale: bool = False,
    error_kind: str = "",
    message: str = "",
) -> dict:
    status_text = _safe_text(status).strip()
    normalized_status = status_text if status_text in AUDIT_STATUSES else AUDIT_STATUS_UNAVAILABLE
    raw_finished_at_epoch = finished_at_epoch
    fallback_finished_at_epoch = finished_at_epoch if iso_from_epoch(finished_at_epoch) is not None else time.time()
    duration_finished_at_epoch = fallback_finished_at_epoch if raw_finished_at_epoch is None else raw_finished_at_epoch
    fetched_at_value = _safe_text(fetched_at).strip() or iso_from_epoch(fetched_at_epoch) or iso_from_epoch(fallback_finished_at_epoch)
    return {
        "source": _safe_text(source).strip() or "unknown",
        "provider": _safe_text(provider).strip(),
        "status": normalized_status,
        "fetched_at": fetched_at_value,
        "duration_ms": duration_ms_fn(started_at_epoch, duration_finished_at_epoch, duration_ms),
        "record_count": _safe_int(record_count),
        "cache_hit": _safe_bool(cache_hit),
        "stale": _safe_bool(stale),
        "error_kind": _safe_text(error_kind).strip(),
        "message": _safe_text(message).strip(),
    }


def duration_ms_fn(started_at_epoch: Optional[float], finished_at_epoch: Optional[float], value: Optional[float]) -> Optional[int]:
    return duration_ms(started_at_epoch, finished_at_epoch, value)


def append_source_audit(data: dict, entry: dict) -> dict:
    if not isinstance(data, dict):
        return data
    entries = data.get("source_audit")
    if isinstance(entries, tuple):
        entries = safe_sequence_items(entries)
    elif not isinstance(entries, list):
        entries = []
    entries.append(entry)
    data["source_audit"] = entries
    return data


def source_record_count(source: str, data: Any) -> int:
    data_map = safe_mapping_dict(data)
    if data_map is None:
        return 0
    data = data_map
    source = _safe_text(source).strip()
    if source == "market_data":
        fields = ("current_price", "market_cap_raw", "pe_ratio_raw", "pb_ratio", "price_history")
        return sum(1 for field in fields if has_value(data.get(field)))
    if source == "financial_statements":
        return max(
            list_count(data.get("years")),
            list_count(data.get("revenue_history")),
            list_count(data.get("net_income_history")),
            list_count(data.get("fcf_history")),
            list_count(data.get("total_assets_history")),
            list_count(data.get("total_equity_history")),
        )
    if source == "monthly_revenue":
        return list_count(data.get("recent_monthly_revenue"))
    if source == "institutional_trading":
        value = safe_mapping_dict(data.get("institutional_trading"))
        if value is not None:
            daily = value.get("daily_total_net_buy_last_10")
            daily_count = list_count(daily)
            if daily_count:
                return daily_count
            fallback_values = [
                child
                for key, child in value.items()
                if key != "daily_total_net_buy_last_10"
            ]
            return 1 if any(has_value(child) for child in fallback_values) else 0
        return 0
    if source == "dynamic_peer_metrics":
        return list_count(data.get("dynamic_peer_metrics"))
    if source == "pe_river_chart":
        value = safe_mapping_dict(data.get("pe_river_chart"))
        if value is None:
            return 0
        bands = value.get("bands")
        bands_map = safe_mapping_dict(bands)
        if bands_map:
            band_count = max((list_count(series) for series in bands_map.values()), default=0)
            if band_count:
                return band_count
        return list_count(value.get("years")) or list_count(value.get("eps_twd"))
    if source == "recent_catalysts":
        return list_count(data.get("recent_catalysts"))
    if source == "global_market_context":
        value = safe_mapping_dict(data.get("global_market_context"))
        if value is not None:
            return list_count(value.get("items"))
        return 0
    if source == "international_news_context":
        value = safe_mapping_dict(data.get("international_news_context"))
        if value is not None:
            return list_count(value.get("topics"))
        return 0
    if source == "peer_discovery":
        return list_count(data.get("peer_discovery_results"))
    value = data.get(source)
    if isinstance(value, (list, tuple)):
        return list_count(value)
    if isinstance(value, (set, frozenset)):
        return sum(1 for item in _set_items(value) if has_value(item))
    if isinstance(value, Mapping):
        value_map = safe_mapping_dict(value)
        if value_map is None:
            return 0
        return sum(1 for child in value_map.values() if has_value(child))
    return 1 if has_value(value) else 0
