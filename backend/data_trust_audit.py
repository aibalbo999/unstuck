"""Source audit entry helpers and source record counting."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from data_trust_constants import (
    AUDIT_STATUS_LABELS,
    AUDIT_STATUS_UNAVAILABLE,
    AUDIT_STATUSES,
    SOURCE_LABELS,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def iso_from_epoch(epoch: Optional[float]) -> Optional[str]:
    if not isinstance(epoch, (int, float)) or epoch <= 0:
        return None
    return datetime.fromtimestamp(float(epoch), timezone.utc).isoformat()


def source_label(source: str) -> str:
    source_text = _safe_text(source).strip()
    return SOURCE_LABELS.get(source_text, source_text or "unknown")


def audit_status_label(status: str) -> str:
    status_text = _safe_text(status).strip()
    return AUDIT_STATUS_LABELS.get(status_text, status_text or "unknown")


def data_snapshot_filename_for_report(filename: str) -> str:
    return filename[:-5] + ".data.json" if filename.endswith(".html") else f"{filename}.data.json"


def duration_ms(started_at_epoch: Optional[float], finished_at_epoch: Optional[float], duration_ms_value: Optional[float]) -> Optional[int]:
    if isinstance(duration_ms_value, (int, float)):
        return max(0, int(round(float(duration_ms_value))))
    if isinstance(started_at_epoch, (int, float)) and isinstance(finished_at_epoch, (int, float)):
        return max(0, int(round((float(finished_at_epoch) - float(started_at_epoch)) * 1000)))
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
    finished_at_epoch = finished_at_epoch if isinstance(finished_at_epoch, (int, float)) else time.time()
    fetched_at_value = fetched_at or iso_from_epoch(fetched_at_epoch or finished_at_epoch)
    return {
        "source": _safe_text(source).strip() or "unknown",
        "provider": _safe_text(provider).strip(),
        "status": normalized_status,
        "fetched_at": fetched_at_value,
        "duration_ms": duration_ms_fn(started_at_epoch, finished_at_epoch, duration_ms),
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
    if not isinstance(entries, list):
        entries = []
    entries.append(entry)
    data["source_audit"] = entries
    return data


def source_record_count(source: str, data: dict) -> int:
    if not isinstance(data, dict):
        return 0
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
        value = data.get("institutional_trading")
        if isinstance(value, dict):
            daily = value.get("daily_total_net_buy_last_10")
            return list_count(daily) or (1 if value else 0)
        return 0
    if source == "dynamic_peer_metrics":
        return list_count(data.get("dynamic_peer_metrics"))
    if source == "pe_river_chart":
        value = data.get("pe_river_chart")
        if not isinstance(value, dict):
            return 0
        bands = value.get("bands")
        if isinstance(bands, dict) and bands:
            return max((list_count(series) for series in bands.values()), default=0)
        return list_count(value.get("years")) or list_count(value.get("eps_twd"))
    if source == "recent_catalysts":
        return list_count(data.get("recent_catalysts"))
    if source == "global_market_context":
        value = data.get("global_market_context")
        if isinstance(value, dict):
            return list_count(value.get("items"))
        return 0
    if source == "international_news_context":
        value = data.get("international_news_context")
        if isinstance(value, dict):
            return list_count(value.get("topics"))
        return 0
    if source == "peer_discovery":
        return list_count(data.get("peer_discovery_results"))
    value = data.get(source)
    if isinstance(value, list):
        return list_count(value)
    if isinstance(value, dict):
        return len(value)
    return 1 if has_value(value) else 0


def list_count(value: Any) -> int:
    if isinstance(value, list):
        return len([item for item in value if has_value(item)])
    return 0


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().upper() != "N/A"
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return True


def string_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [
            text
            for item in value
            if (text := _safe_text(item).strip())
        ]
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (bool, int, float)) and not value:
        return []
    text = _safe_text(value).strip()
    return [text] if text else []


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return ""


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return 0


def _safe_bool(value: Any) -> bool:
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return False
