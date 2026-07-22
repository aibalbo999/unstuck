"""DCF scenario policy helpers for deterministic financial tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


DcfCalculator = Callable[..., dict[str, Any]]


def dcf_scenario_assumptions(latest_revenue_growth_pct: float | None) -> tuple[str, dict[str, dict[str, float]]]:
    revenue_growth = latest_revenue_growth_pct or 0
    if revenue_growth > 30:
        base_growth = max(min(revenue_growth * 0.40, 25), 5)
        return "high_growth", {
            "bear": _assumptions(base_growth * 0.8, -20, -20, 1.5, 1.5),
            "base": _assumptions(base_growth, 0, 0, 0, 2.5),
            "bull": _assumptions(min(base_growth * 1.2, 35), 20, 20, -1.0, 3.0),
        }

    base_growth = max(min(revenue_growth * 0.25, 10), 0)
    return "stable", {
        "bear": _assumptions(base_growth * 0.8, -20, -20, 1.5, 1.0),
        "base": _assumptions(base_growth, 0, 0, 0, 2.0),
        "bull": _assumptions(max(min(base_growth * 1.2, 15), 2), 20, 20, -1.0, 2.5),
    }


def dcf_scenario_note(growth_phase: str) -> str:
    if growth_phase == "high_growth":
        return (
            "高成長期（年增>30%）：DCF 成長率上限已放寬至 bear=15% / base=25% / bull=35%，"
            "反映高科技供應鏈實際成長潛力；估值 agent 應優先以 Forward P/E 相對估值交叉驗證。"
        )
    return "穩定期（年增≤30%）：DCF 成長率採保守上限，bear=6% / base=10% / bull=15%。"


def build_dcf_scenarios(
    *,
    base_fcf_billion_twd: float,
    base_fcf_note: str,
    latest_revenue_growth_pct: float | None,
    wacc_pct: float,
    shares_outstanding: float,
    net_debt_billion_twd: float,
    dcf_calculator: DcfCalculator,
) -> dict[str, Any]:
    growth_phase, scenarios = dcf_scenario_assumptions(latest_revenue_growth_pct)
    dcf_results = {}
    for scenario, assumptions in scenarios.items():
        scenario_wacc = max(
            wacc_pct + assumptions["wacc_delta_pct"],
            assumptions["terminal_growth_pct"] + 0.5,
        )
        scenario_base_fcf = base_fcf_billion_twd * (1 + assumptions["margin_bias_pct"] / 100)
        dcf_results[scenario] = {
            **dcf_calculator(
                base_fcf_billion_twd=scenario_base_fcf,
                growth_rate_pct=assumptions["growth_rate_pct"],
                wacc_pct=scenario_wacc,
                terminal_growth_pct=assumptions["terminal_growth_pct"],
                shares_outstanding=shares_outstanding,
                net_debt_billion_twd=net_debt_billion_twd,
            ),
            "growth_bias_pct": assumptions["growth_bias_pct"],
            "margin_bias_pct": assumptions["margin_bias_pct"],
        }
    return {
        "base_fcf_billion_twd": round(base_fcf_billion_twd, 4),
        "base_fcf_note": base_fcf_note,
        "growth_phase": growth_phase,
        "growth_phase_note": dcf_scenario_note(growth_phase),
        "scenarios": dcf_results,
    }


def _assumptions(
    growth_rate_pct: float,
    growth_bias_pct: float,
    margin_bias_pct: float,
    wacc_delta_pct: float,
    terminal_growth_pct: float,
) -> dict[str, float]:
    return {
        "growth_rate_pct": growth_rate_pct,
        "growth_bias_pct": growth_bias_pct,
        "margin_bias_pct": margin_bias_pct,
        "wacc_delta_pct": wacc_delta_pct,
        "terminal_growth_pct": terminal_growth_pct,
    }
