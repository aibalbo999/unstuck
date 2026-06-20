"""Fallback planning for financial data conflicts."""

from __future__ import annotations

from typing import Any

from agent_state import AgentState, ProviderValue
from data_financial_metric_validator import relative_difference_pct, validate_state_provider_values
from official_financials import fetch_mops_balance_sheet


def build_reconciliation_plan(state: AgentState) -> dict[str, Any]:
    """Return the deterministic retry and official-filing plan for an open breaker."""
    blocking_fields = list(state.circuit_breaker.blocking_fields or [])
    if state.circuit_breaker.status != "open" or not blocking_fields:
        return {
            "status": "not_required",
            "blocking_fields": [],
            "steps": [],
            "resume_condition": {
                "max_diff_pct": 2.0,
                "preferred_source": "official_filing",
            },
        }

    return {
        "status": "required",
        "reason": state.circuit_breaker.reason or "critical_provider_conflict",
        "ticker": state.ticker,
        "company_name": state.company_name,
        "blocking_fields": blocking_fields,
        "steps": [
            {
                "action": "fresh_provider_retry",
                "providers": ["yfinance", "FinMind"],
                "fields": blocking_fields,
                "description": (
                    "Bypass cache and refetch conflicting provider fields with unit, "
                    "period, and statement-scope checks."
                ),
            },
            {
                "action": "mops_statement_lookup",
                "provider": "MOPS",
                "fields": blocking_fields,
                "description": (
                    "Search 公開資訊觀測站 for the latest quarterly or annual filing "
                    "and extract matching consolidated statement values."
                ),
            },
            {
                "action": "source_ranking",
                "description": (
                    "Prefer official filings, matching period, matching currency/unit, "
                    "and consolidated statements over stale third-party API values."
                ),
            },
        ],
        "resume_condition": {
            "max_diff_pct": 2.0,
            "preferred_source": "official_filing",
            "required_resolution": (
                "At least one provider aligns with MOPS or official filing within tolerance."
            ),
        },
        "fail_closed_action": "Render Data Conflict Report and skip valuation/final target prices.",
    }


def reconcile_with_official_filing(
    state: AgentState,
    *,
    year: int,
    season: int,
    tolerance_pct: float = 2.0,
) -> dict[str, Any]:
    """Fetch MOPS official filing values and retry breaker validation."""
    blocking_fields = list(state.circuit_breaker.blocking_fields or [])
    if state.circuit_breaker.status != "open" or not blocking_fields:
        return {"status": "not_required", "blocking_fields": []}
    if set(blocking_fields) != {"total_debt"}:
        return {"status": "unsupported", "blocking_fields": blocking_fields}

    filing = fetch_mops_balance_sheet(state.ticker, year, season)
    if not _mops_filing_is_usable(filing):
        return {"status": "unresolved", "blocking_fields": blocking_fields, "reason": "mops_unavailable_or_unusable"}

    appended_fields = []
    period = f"{int(filing.get('year') or year)}Q{int(filing.get('season') or season)}"
    if "total_debt" in blocking_fields and filing.get("total_liabilities") is not None:
        official_value = ProviderValue(
            provider="MOPS",
            field="total_debt",
            value=filing["total_liabilities"],
            unit=str(filing.get("unit") or ""),
            period=period,
            statement_type=str(filing.get("statement_scope") or "unknown"),
            source_url="https://mops.twse.com.tw/mops/web/t164sb03",
            confidence=0.98,
        )
        reconciled_values = _values_aligned_with_official(
            state.provider_values.get("total_debt", []),
            official_value,
            tolerance_pct,
        )
        if len(reconciled_values) < 2:
            return {
                "status": "unresolved",
                "blocking_fields": blocking_fields,
                "reason": "no_provider_aligned_with_official",
            }
        state.provider_values["total_debt"] = reconciled_values
        appended_fields.append("total_debt")

    if not appended_fields:
        return {"status": "unresolved", "blocking_fields": blocking_fields, "reason": "no_matching_official_fields"}

    state.raw_financial_data.setdefault("official_filings", []).append(filing)
    validate_state_provider_values(state, fields=tuple(blocking_fields), threshold_pct=tolerance_pct)
    return {
        "status": "resolved" if state.circuit_breaker.status == "closed" else "unresolved",
        "blocking_fields": list(state.circuit_breaker.blocking_fields),
        "appended_fields": appended_fields,
        "source": "MOPS",
    }


def _mops_filing_is_usable(filing: Any) -> bool:
    if not isinstance(filing, dict):
        return False
    return (
        filing.get("source") == "MOPS"
        and filing.get("unit") == "thousand_twd"
        and filing.get("statement_scope") == "consolidated"
    )


def _values_aligned_with_official(
    values: list[ProviderValue],
    official_value: ProviderValue,
    tolerance_pct: float,
) -> list[ProviderValue]:
    aligned: list[tuple[float, ProviderValue]] = []
    for value in values:
        if not _metadata_matches_official(value, official_value):
            continue
        diff_pct = relative_difference_pct(value.value, official_value.value)
        if diff_pct is not None and diff_pct <= tolerance_pct:
            aligned.append((diff_pct, value))
    aligned.sort(key=lambda item: item[0])
    return [*(value for _, value in aligned[:1]), official_value]


def _metadata_matches_official(value: ProviderValue, official_value: ProviderValue) -> bool:
    if value.unit and value.unit != official_value.unit:
        return False
    if value.period and value.period != official_value.period:
        return False
    if (
        value.statement_type != "unknown"
        and official_value.statement_type != "unknown"
        and value.statement_type != official_value.statement_type
    ):
        return False
    return True
