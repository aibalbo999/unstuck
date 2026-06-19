"""AgentState circuit breaker for critical cross-provider financial conflicts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import combinations
from typing import Any

from agent_state import AgentState, ProviderValue, RiskFlag, Severity, ValidationIssue
from data_validation_values import relative_divergence, safe_float


DIVERGENCE_THRESHOLD_PCT = 5.0
CRITICAL_FINANCIAL_FIELDS = ("revenue", "net_income", "total_debt", "free_cash_flow")
PROVIDER_CONFLICT_CAUSE_PREFIX = "provider_conflict:"


class CircuitBreakerOpen(RuntimeError):
    """Raised when critical cross-provider financial data conflicts block analysis."""

    def __init__(self, state: AgentState):
        self.state = state
        fields = ", ".join(state.circuit_breaker.blocking_fields)
        super().__init__(f"Financial data validation circuit breaker is open: {fields}")


def relative_difference_pct(a: Any, b: Any) -> float | None:
    """Return |a-b| / max(|a|, |b|, 1) as a percentage for numeric values."""
    value_a = safe_float(a)
    value_b = safe_float(b)
    if value_a is None or value_b is None:
        return None
    return relative_divergence(value_a, value_b)


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
        value_a = safe_float(comparison.get("source_a_value"))
        value_b = safe_float(comparison.get("source_b_value"))
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
    previous_blocking_fields = set(state.circuit_breaker.blocking_fields)

    state.validation_issues = [
        issue for issue in state.validation_issues
        if not _is_provider_conflict_validation_issue(issue, selected_fields)
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
        numeric_values = [value for value in values if safe_float(value.value) is not None]
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
                likely_cause=f"{PROVIDER_CONFLICT_CAUSE_PREFIX}{_infer_conflict_cause(left, right)}",
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
        state.circuit_breaker.blocking_fields = list(
            dict.fromkeys([*state.circuit_breaker.blocking_fields, *blocking_fields])
        )
        if (
            state.circuit_breaker.status != "open"
            or set(state.circuit_breaker.blocking_fields) != previous_blocking_fields
        ):
            state.circuit_breaker.attempts += 1
        state.circuit_breaker.status = "open"
        state.circuit_breaker.reason = "Critical financial provider values conflict above validation threshold."
        if raise_on_open:
            raise CircuitBreakerOpen(state)
    elif not state.circuit_breaker.blocking_fields:
        state.circuit_breaker.status = "closed"
        state.circuit_breaker.reason = None

    return state


def _is_provider_conflict_validation_issue(issue: ValidationIssue, fields: Iterable[str]) -> bool:
    return issue.field in fields and (issue.likely_cause or "").startswith(PROVIDER_CONFLICT_CAUSE_PREFIX)


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
