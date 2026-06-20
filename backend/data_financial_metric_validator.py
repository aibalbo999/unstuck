"""Payload-level financial metric validation helpers."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any

from data_validation_circuit_breaker import (
    CRITICAL_FINANCIAL_FIELDS,
    DIVERGENCE_THRESHOLD_PCT,
    PROVIDER_CONFLICT_CAUSE_PREFIX,
    CircuitBreakerOpen,
    load_provider_values_from_payload,
    relative_difference_pct,
    validate_state_provider_values,
)
from data_validation_values import relative_divergence as _relative_divergence
from data_validation_values import safe_float as _safe_float


logger = logging.getLogger(__name__)

HIGH_DISCREPANCY_FLAG = "High_Discrepancy"
DEFAULT_FINANCIAL_METRIC_FIELDS = (
    "eps",
    "monthly_revenue",
    "revenue",
    "net_income",
    "gross_margin",
    "operating_margin",
    "profit_margin",
)


def validate_financial_metrics(
    data_payload: MutableMapping[str, Any],
    source_a: Mapping[str, Any],
    source_b: Mapping[str, Any],
    *,
    source_a_name: str = "source_a",
    source_b_name: str = "source_b",
    fields: Iterable[str] | None = None,
    threshold_pct: float = DIVERGENCE_THRESHOLD_PCT,
    high_discrepancy_score: int = 50,
) -> MutableMapping[str, Any]:
    """Cross-validate same financial metrics from two sources and annotate trust."""
    payload = data_payload if isinstance(data_payload, MutableMapping) else {}
    source_a = source_a or {}
    source_b = source_b or {}
    selected = list(fields or sorted(set(DEFAULT_FINANCIAL_METRIC_FIELDS) | set(source_a) | set(source_b)))
    comparisons: dict[str, dict[str, Any]] = {}
    high_discrepancy_fields: list[str] = []

    for field in selected:
        value_a = _safe_float(_metric_value(source_a, field))
        value_b = _safe_float(_metric_value(source_b, field))
        if value_a is None or value_b is None:
            continue
        divergence_pct = _relative_divergence(value_a, value_b)
        entry = _field_entry(payload, field, value_a)
        comparison = _comparison(field, value_a, value_b, source_a_name, source_b_name, divergence_pct, threshold_pct)
        comparisons[field] = comparison
        if divergence_pct > threshold_pct:
            _mark_high_discrepancy(entry, comparison, field, value_a, value_b, source_a_name, source_b_name, high_discrepancy_score)
            high_discrepancy_fields.append(field)
        else:
            entry.setdefault("flags", [])
            entry["trust_score"] = _current_trust_score(entry)
            entry["discrepancy"] = comparison

    payload["financial_metric_validation"] = {
        "source_a": source_a_name,
        "source_b": source_b_name,
        "threshold_pct": float(threshold_pct),
        "comparisons": comparisons,
        "high_discrepancy_fields": high_discrepancy_fields,
    }
    return payload


def _metric_value(source: Mapping[str, Any], field: str) -> Any:
    value = source.get(field)
    if isinstance(value, Mapping):
        return value.get("value", value.get("raw", value.get("amount")))
    return value


def _field_entry(payload: MutableMapping[str, Any], field: str, fallback_value: Any) -> MutableMapping[str, Any]:
    metrics = payload.setdefault("financial_metrics", {})
    if not isinstance(metrics, MutableMapping):
        metrics = {}
        payload["financial_metrics"] = metrics
    entry = metrics.get(field)
    if not isinstance(entry, MutableMapping):
        entry = {"value": fallback_value}
        metrics[field] = entry
    else:
        entry.setdefault("value", fallback_value)
    return entry


def _current_trust_score(entry: Mapping[str, Any], default: int = 85) -> int:
    try:
        return max(0, min(int(round(float(entry.get("trust_score", default)))), 100))
    except (TypeError, ValueError):
        return default


def _comparison(
    field: str,
    value_a: float,
    value_b: float,
    source_a_name: str,
    source_b_name: str,
    divergence_pct: float,
    threshold_pct: float,
) -> dict[str, Any]:
    return {
        "field": field,
        "source_a": source_a_name,
        "source_b": source_b_name,
        "source_a_value": value_a,
        "source_b_value": value_b,
        "difference_pct": round(divergence_pct, 2),
        "threshold_pct": float(threshold_pct),
        "status": HIGH_DISCREPANCY_FLAG if divergence_pct > threshold_pct else "Aligned",
    }


def _mark_high_discrepancy(
    entry: MutableMapping[str, Any],
    comparison: dict[str, Any],
    field: str,
    value_a: float,
    value_b: float,
    source_a_name: str,
    source_b_name: str,
    high_discrepancy_score: int,
) -> None:
    flags = entry.get("flags")
    if isinstance(flags, str):
        flags = [flags]
    elif not isinstance(flags, list):
        flags = []
    if HIGH_DISCREPANCY_FLAG not in flags:
        flags.append(HIGH_DISCREPANCY_FLAG)
    entry["flags"] = flags
    entry["trust_score"] = min(_current_trust_score(entry), max(0, min(int(high_discrepancy_score), 100)))
    entry["discrepancy"] = comparison
    logger.warning(
        "High financial metric discrepancy for %s between %s=%s and %s=%s: %.2f%%",
        field,
        source_a_name,
        value_a,
        source_b_name,
        value_b,
        comparison["difference_pct"],
    )
