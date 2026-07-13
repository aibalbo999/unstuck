"""Source audit entry helpers and source record counting."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from numbers import Real
from typing import Any, Optional

from data_trust_constants import (
    AUDIT_STATUS_LABELS,
    AUDIT_STATUS_UNAVAILABLE,
    AUDIT_STATUSES,
    SOURCE_LABELS,
)
from mapping_fields import safe_int, safe_mapping_dict, safe_sequence_items, safe_text


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


def list_count(value: Any) -> int:
    return len([item for item in safe_sequence_items(value) if has_value(item)])


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return False
    if isinstance(value, (bytes, bytearray, memoryview)):
        return False
    if isinstance(value, complex):
        return False
    if isinstance(value, Decimal):
        return value.is_finite()
    if isinstance(value, Real):
        try:
            numeric_value = float(value)
        except (OverflowError, TypeError, ValueError):
            return False
        return math.isfinite(numeric_value)
    if isinstance(value, str):
        text = value.strip()
        return bool(text) and text.upper() not in {
            "N/A",
            "NA",
            "NONE",
            "NULL",
            "NIL",
            "MISSING",
            "-",
            "--",
            "NAN",
            "INF",
            "+INF",
            "-INF",
            "INFINITY",
            "+INFINITY",
            "-INFINITY",
        }
    if isinstance(value, (set, frozenset)):
        return any(has_value(item) for item in _set_items(value))
    if isinstance(value, (list, tuple)):
        return any(has_value(item) for item in safe_sequence_items(value))
    if isinstance(value, Mapping):
        value_map = safe_mapping_dict(value)
        if value_map is None:
            return False
        return any(has_value(child) for child in value_map.values())
    return True


def string_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [
            text
            for item in safe_sequence_items(value)
            if (text := _safe_list_text(item))
        ]
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (bool, int, float)) and not value:
        return []
    text = _safe_list_text(value)
    return [text] if text else []


def _safe_list_text(value: Any) -> str:
    if isinstance(value, Decimal) and not value.is_finite():
        return ""
    if isinstance(value, Real) and not isinstance(value, bool):
        try:
            numeric_value = float(value)
        except (OverflowError, TypeError, ValueError):
            return ""
        if not math.isfinite(numeric_value):
            return ""
    return _safe_text(value).strip()


def _set_items(value: Any) -> list[Any]:
    if not isinstance(value, (set, frozenset)):
        return []
    try:
        iterator = iter(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        iterator = _native_set_iterator(value)
        if iterator is None:
            return []
    items = []
    while True:
        try:
            items.append(next(iterator))
        except StopIteration:
            return items
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            native_iterator = _native_set_iterator(value)
            if native_iterator is None or native_iterator is iterator:
                return items
            native_items = []
            while True:
                try:
                    native_items.append(next(native_iterator))
                except StopIteration:
                    return native_items
                except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
                    return native_items


def _native_set_iterator(value: Any):
    try:
        if isinstance(value, frozenset):
            return frozenset.__iter__(value)
        if isinstance(value, set):
            return set.__iter__(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return None
    return None


def _safe_text(value: Any) -> str:
    return safe_text(value)


def _safe_int(value: Any) -> int:
    return safe_int(value)


def _safe_bool(value: Any) -> bool:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return False
    if isinstance(value, Mapping) or isinstance(value, (list, tuple, set, frozenset)):
        return False
    if isinstance(value, complex):
        return False
    if isinstance(value, Decimal):
        if not value.is_finite():
            return False
        if value == 0:
            return False
        if value == 1:
            return True
        return False
    if isinstance(value, Real) and not isinstance(value, bool):
        try:
            numeric_value = float(value)
        except (OverflowError, TypeError, ValueError):
            return False
        if not math.isfinite(numeric_value):
            return False
        if value == 0:
            return False
        if value == 1:
            return True
        return False
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"", "0", "false", "no", "off", "none", "null"}:
            return False
        if text in {"1", "true", "yes", "on"}:
            return True
        try:
            numeric_text = Decimal(text)
        except (ArithmeticError, ValueError):
            return False
        else:
            if not numeric_text.is_finite():
                return False
            if numeric_text == 0:
                return False
            if numeric_text == 1:
                return True
            return False
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return False
