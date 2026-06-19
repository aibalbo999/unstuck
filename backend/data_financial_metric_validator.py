"""Payload-level financial metric validation helpers."""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable, Mapping, MutableMapping
from itertools import combinations
from typing import Any

from agent_state import AgentState, ProviderValue, RiskFlag, Severity, ValidationIssue


logger = logging.getLogger(__name__)

DIVERGENCE_THRESHOLD_PCT = 5.0
HIGH_DISCREPANCY_FLAG = "High_Discrepancy"
CRITICAL_FINANCIAL_FIELDS = ("revenue", "net_income", "total_debt", "free_cash_flow")
DEFAULT_FINANCIAL_METRIC_FIELDS = (
    "eps",
    "monthly_revenue",
    "revenue",
    "net_income",
    "gross_margin",
    "operating_margin",
    "profit_margin",
)


class CircuitBreakerOpen(RuntimeError):
    """Raised when critical cross-provider financial data conflicts block analysis."""

    def __init__(self, state: AgentState):
        self.state = state
        fields = ", ".join(state.circuit_breaker.blocking_fields)
        super().__init__(f"Financial data validation circuit breaker is open: {fields}")


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


def relative_difference_pct(a: Any, b: Any) -> float | None:
    """Return |a-b| / max(|a|, |b|, 1) as a percentage for numeric values."""
    value_a = _safe_float(a)
    value_b = _safe_float(b)
    if value_a is None or value_b is None:
        return None
    return _relative_divergence(value_a, value_b)


def load_provider_values_from_payload(state: AgentState, data_payload: Mapping[str, Any]) -> AgentState:
    """Populate AgentState provider values from existing payload comparison metadata."""
    validation = data_payload.get("financial_metric_validation") if isinstance(data_payload, Mapping) else None
    if not isinstance(validation, Mapping):
        return state

    comparisons = validation.get("comparisons")
    if not isinstance(comparisons, Mapping):
        return state

    for field_key, comparison in comparisons.items():
        if not isinstance(comparison, Mapping):
            continue
        field = str(comparison.get("field") or field_key)
        source_a = str(comparison.get("source_a") or validation.get("source_a") or "source_a")
        source_b = str(comparison.get("source_b") or validation.get("source_b") or "source_b")
        value_a = _safe_float(comparison.get("source_a_value"))
        value_b = _safe_float(comparison.get("source_b_value"))
        if value_a is None or value_b is None:
            continue
        state.provider_values[field] = [
            ProviderValue(provider=source_a, field=field, value=value_a),
            ProviderValue(provider=source_b, field=field, value=value_b),
        ]

    return state


def validate_state_provider_values(
    state: AgentState,
    *,
    fields: Iterable[str] = CRITICAL_FINANCIAL_FIELDS,
    threshold_pct: float = DIVERGENCE_THRESHOLD_PCT,
    raise_on_open: bool = False,
) -> AgentState:
    """Open the AgentState circuit breaker when critical provider values conflict."""
    selected_fields = tuple(fields)
    blocking_fields: list[str] = []
    previous_blocking_fields = list(state.circuit_breaker.blocking_fields)

    state.validation_issues = [
        issue for issue in state.validation_issues
        if issue.field not in selected_fields
    ]
    state.risk_flags = [
        flag for flag in state.risk_flags
        if not _is_provider_conflict_risk_flag(flag, selected_fields)
    ]
    state.circuit_breaker.blocking_fields = [
        field for field in state.circuit_breaker.blocking_fields
        if field not in selected_fields
    ]

    for field in selected_fields:
        values = state.provider_values.get(field) or []
        numeric_values = [value for value in values if _safe_float(value.value) is not None]
        if len(numeric_values) < 2:
            continue

        conflict = _largest_provider_conflict(numeric_values)
        if conflict is None:
            continue
        left, right, diff_pct = conflict
        if diff_pct <= threshold_pct:
            continue

        rounded_diff = round(diff_pct, 2)
        blocking_fields.append(field)
        state.validation_issues.append(
            ValidationIssue(
                field=field,
                severity=Severity.critical,
                providers=[left.provider, right.provider],
                values=[left, right],
                diff_pct=rounded_diff,
                threshold_pct=float(threshold_pct),
                likely_cause=_infer_conflict_cause(left, right),
                resolution="Reconcile provider values before relying on critical financial metrics.",
            )
        )
        state.risk_flags.append(
            RiskFlag(
                id=f"data_quality:{field}:provider_conflict",
                severity=Severity.critical,
                category="data_quality",
                title=f"Critical provider conflict for {field}",
                evidence_refs=[f"provider_values.{field}"],
                source_agents=["data_validation"],
                impact=(
                    f"{left.provider} and {right.provider} differ by {rounded_diff:.2f}% "
                    f"for {field}, above the {float(threshold_pct):.2f}% threshold."
                ),
                confidence=0.95,
            )
        )

    if blocking_fields:
        state.circuit_breaker.blocking_fields = list(dict.fromkeys([*state.circuit_breaker.blocking_fields, *blocking_fields]))
        if state.circuit_breaker.status != "open" or state.circuit_breaker.blocking_fields != previous_blocking_fields:
            state.circuit_breaker.attempts += 1
        state.circuit_breaker.status = "open"
        state.circuit_breaker.reason = "Critical financial provider values conflict above validation threshold."
        if raise_on_open:
            raise CircuitBreakerOpen(state)
    elif not state.circuit_breaker.blocking_fields:
        state.circuit_breaker.status = "closed"
        state.circuit_breaker.reason = None

    return state


def _is_provider_conflict_risk_flag(flag: RiskFlag, fields: Iterable[str]) -> bool:
    return (
        flag.category == "data_quality"
        and "data_validation" in flag.source_agents
        and any(flag.id == f"data_quality:{field}:provider_conflict" for field in fields)
    )


def _largest_provider_conflict(values: list[ProviderValue]) -> tuple[ProviderValue, ProviderValue, float] | None:
    largest: tuple[ProviderValue, ProviderValue, float] | None = None
    for left, right in combinations(values, 2):
        diff_pct = relative_difference_pct(left.value, right.value)
        if diff_pct is None:
            continue
        if largest is None or diff_pct > largest[2]:
            largest = (left, right, diff_pct)
    return largest


def _infer_conflict_cause(left: ProviderValue, right: ProviderValue) -> str:
    if left.period and right.period and left.period != right.period:
        return "period_mismatch"
    if left.unit and right.unit and left.unit != right.unit:
        return "unit_mismatch"
    if left.statement_type != right.statement_type and "unknown" not in {left.statement_type, right.statement_type}:
        return "statement_type_mismatch"
    return "provider_value_conflict"


def _safe_float(value: Any) -> float | None:
    if value is None or value == "N/A":
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("NT$", "").replace("$", "").replace("%", "").strip()
            if not value:
                return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _relative_divergence(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1.0) * 100


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
