"""Structured backtest artifacts for report decisions."""

from __future__ import annotations

from typing import Any

from decision_backtest import evaluate_prediction
from factor_store import factor_snapshot_id


SCHEMA_VERSION = "backtest_artifact.v1"


def build_backtest_artifact(
    decision: dict[str, Any],
    *,
    price_path: list[dict[str, Any]],
    benchmark_path: list[dict[str, Any]] | None = None,
    factor_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic artifact linking a decision to realized prices."""
    prices = _clean_path(price_path)
    if len(prices) < 2:
        raise ValueError("price_path must contain at least two valid close prices")
    benchmark = _clean_path(benchmark_path or [])
    initial = prices[0]["close"]
    actual = prices[-1]["close"]
    evaluation = evaluate_prediction(
        recommendation=str(decision.get("recommendation") or ""),
        initial_price=initial,
        actual_price=actual,
        target_price=decision.get("target_price"),
    )
    benchmark_return = _path_return_pct(benchmark) if len(benchmark) >= 2 else None
    metrics = {
        **evaluation,
        "benchmark_return_pct": _round(benchmark_return),
        "excess_return_pct": _round(
            evaluation["strategy_roi_pct"] - benchmark_return
            if benchmark_return is not None
            else None
        ),
        "max_drawdown_pct": _round(_max_drawdown_pct([row["close"] for row in prices])),
    }
    factor_snapshot = dict(factor_snapshot or {})
    return {
        "schema_version": SCHEMA_VERSION,
        "decision_id": str(decision.get("decision_id") or ""),
        "ticker": str(decision.get("ticker") or "").strip().upper(),
        "alpha_model_id": str(decision.get("alpha_model_id") or ""),
        "generated_date": str(decision.get("generated_date") or ""),
        "evaluation_date": prices[-1]["date"],
        "factor_snapshot_id": factor_snapshot_id(factor_snapshot) if factor_snapshot else None,
        "price_path": {"start": prices[0], "end": prices[-1], "observations": len(prices)},
        "benchmark_path": {
            "start": benchmark[0],
            "end": benchmark[-1],
            "observations": len(benchmark),
        } if benchmark else None,
        "metrics": metrics,
    }


def _clean_path(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []
    for row in rows or []:
        try:
            close = float((row or {}).get("close"))
        except (TypeError, ValueError):
            continue
        if close <= 0:
            continue
        cleaned.append({"date": str((row or {}).get("date") or ""), "close": close})
    return sorted(cleaned, key=lambda item: item["date"])


def _path_return_pct(path: list[dict[str, Any]]) -> float:
    return (path[-1]["close"] / path[0]["close"] - 1) * 100


def _max_drawdown_pct(closes: list[float]) -> float:
    peak = closes[0]
    max_drawdown = 0.0
    for close in closes:
        peak = max(peak, close)
        max_drawdown = min(max_drawdown, close / peak - 1)
    return max_drawdown * 100


def _round(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


__all__ = ["SCHEMA_VERSION", "build_backtest_artifact"]
