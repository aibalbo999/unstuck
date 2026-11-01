"""Deterministic financial cross-checks shared by prompts and snapshots."""

from __future__ import annotations

from financial_tool_utils import raw_twd_to_billion_twd, safe_float


def build_financial_cross_checks(data: dict) -> dict:
    """Build deterministic financial cross-checks from canonical raw fields."""
    shares = safe_float(dict.get(data, "shares_raw"))
    forward_eps = safe_float(dict.get(data, "forward_eps"))
    profit_margin_raw = safe_float(dict.get(data, "profit_margin_raw"))
    revenue_ttm_raw = safe_float(dict.get(data, "revenue_ttm_raw"))

    implied_forward_net_income_b = None
    implied_forward_revenue_b = None
    implied_forward_revenue_growth_pct = None
    if shares and forward_eps:
        implied_forward_net_income_twd = shares * forward_eps
        implied_forward_net_income_b = raw_twd_to_billion_twd(implied_forward_net_income_twd)
        if profit_margin_raw and profit_margin_raw > 0:
            implied_forward_revenue_twd = implied_forward_net_income_twd / profit_margin_raw
            implied_forward_revenue_b = raw_twd_to_billion_twd(implied_forward_revenue_twd)
            if revenue_ttm_raw and revenue_ttm_raw > 0:
                implied_forward_revenue_growth_pct = round(
                    (implied_forward_revenue_twd / revenue_ttm_raw - 1) * 100,
                    4,
                )

    dupont_note = dict.get(data, "dupont_identity_note") or dict.get(data, "equity_multiplier_note")
    qualified_note = (
        "原始序列算術參考（此註記之原件期間與申報範圍未核實；不得當官方結論）："
        + dupont_note if isinstance(dupont_note, str) and dupont_note.strip() else dupont_note
    )
    return {
        "forward_eps_implied_net_income_billion_twd": implied_forward_net_income_b,
        "forward_eps_implied_revenue_billion_twd": implied_forward_revenue_b,
        "forward_eps_implied_revenue_growth_pct": implied_forward_revenue_growth_pct,
        "dupont_identity_note": dupont_note,
        "dupont_identity_note_qualified": qualified_note,
        "dupont_source_qualification": {
            "verification_scope": "snapshot_arithmetic_consistency_only",
            "independent_primary_source_verified": False,
            "may_support_official_source_claim": False,
            "source_period_status": "not_established_by_this_note",
            "source_report_scope_status": "not_established_by_this_note",
        },
        "wacc_capital_structure_note": dict.get(data, "wacc_capital_structure_note"),
    }
