"""Source status helpers for data trust scoring."""

from __future__ import annotations

from typing import Any

from data_trust_audit import _safe_bool as safe_bool, source_record_count
from data_trust_constants import (
    AUDIT_STATUS_SKIPPED_FRESH_CACHE,
    AUDIT_STATUS_SUCCESS,
    CORE_DATA_SOURCES,
)
from data_trust_values import has_value
from mapping_fields import safe_mapping_dict, safe_text
from numeric_safety import is_non_finite_number


CORE_SOURCE_SET = set(CORE_DATA_SOURCES)


def latest_audit_by_source(entries: list) -> dict:
    latest = {}
    for entry in entries:
        entry_map = safe_mapping_dict(entry)
        if entry_map is None:
            continue
        source = _safe_text(dict.get(entry_map, "source")).strip()
        if source:
            latest[source] = entry_map
    return latest


def stale_sources_from(source_freshness: dict, latest_audit: dict) -> list[str]:
    return _stale_sources_from(source_freshness, latest_audit, core_only=True)


def optional_stale_sources_from(source_freshness: dict, latest_audit: dict) -> list[str]:
    return _stale_sources_from(source_freshness, latest_audit, core_only=False)


def is_core_source(source: str) -> bool:
    return _safe_text(source).strip() in CORE_SOURCE_SET


def optional_sources_with_status(latest_audit: dict, status: str) -> list[str]:
    audit = safe_mapping_dict(latest_audit) or {}
    status_text = _safe_text(status).strip()
    return sorted(
        source_name
        for source, entry in audit.items()
        if (source_name := _safe_text(source).strip())
        and not is_core_source(source_name)
        and audit_status(entry) == status_text
    )


def last_market_data_at(data: dict, source_freshness: dict, latest_audit: dict) -> str | None:
    source_data = safe_mapping_dict(data) or {}
    freshness = safe_mapping_dict(source_freshness) or {}
    audit = safe_mapping_dict(latest_audit) or {}
    market = safe_mapping_dict(dict.get(freshness, "market_data")) or {}
    market_audit = safe_mapping_dict(dict.get(audit, "market_data")) or {}
    for candidate in (
        dict.get(market, "fetched_at"),
        dict.get(source_data, "market_data_fetched_at"),
        dict.get(market_audit, "fetched_at"),
    ):
        timestamp = _safe_text(candidate).strip()
        if timestamp:
            return timestamp
    return None


def audit_status(entry: Any) -> str:
    entry_map = safe_mapping_dict(entry)
    if entry_map is None:
        return ""
    return _safe_text(dict.get(entry_map, "status")).strip()


def has_usable_critical_data(data: dict, latest_audit: dict) -> bool:
    source_data = safe_mapping_dict(data) or {}
    audit = safe_mapping_dict(latest_audit) or {}
    market_status = audit_status(dict.get(audit, "market_data"))
    financial_status = audit_status(dict.get(audit, "financial_statements"))
    market_ok = (
        market_status in {AUDIT_STATUS_SUCCESS, AUDIT_STATUS_SKIPPED_FRESH_CACHE}
        or source_record_count("market_data", source_data) > 0
    )
    financial_ok = (
        financial_status in {AUDIT_STATUS_SUCCESS, AUDIT_STATUS_SKIPPED_FRESH_CACHE}
        or source_record_count("financial_statements", source_data) > 0
    )
    return market_ok and financial_ok


def _stale_sources_from(source_freshness: dict, latest_audit: dict, *, core_only: bool) -> list[str]:
    sources = set()
    for source, entry in source_freshness.items():
        source_name = _safe_text(source).strip()
        entry_map = safe_mapping_dict(entry)
        if (
            source_name
            and entry_map is not None
            and safe_bool(dict.get(entry_map, "stale"))
            and is_core_source(source_name) == core_only
        ):
            sources.add(source_name)
    for source, entry in latest_audit.items():
        source_name = _safe_text(source).strip()
        entry_map = safe_mapping_dict(entry)
        if (
            source_name
            and entry_map is not None
            and safe_bool(dict.get(entry_map, "stale"))
            and is_core_source(source_name) == core_only
        ):
            sources.add(source_name)
    return sorted(sources)


def _safe_text(value: Any) -> str:
    if is_non_finite_number(value):
        return ""
    if isinstance(value, str) and not has_value(value):
        return ""
    return safe_text(value)

__all__ = ["audit_status", "has_usable_critical_data", "is_core_source", "last_market_data_at", "latest_audit_by_source", "optional_sources_with_status", "optional_stale_sources_from", "stale_sources_from"]
