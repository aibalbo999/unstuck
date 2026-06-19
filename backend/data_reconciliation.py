"""Fallback planning for financial data conflicts."""

from __future__ import annotations

from typing import Any

from agent_state import AgentState


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
