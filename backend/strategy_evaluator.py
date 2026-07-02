"""Compare alpha models, quality gates, and watchlist triggers from backtests."""

from __future__ import annotations

from statistics import mean
from typing import Any

from alpha_model_registry import model_for_pipeline


SCHEMA_VERSION = "strategy_evaluation.v1"


def evaluate_strategy_artifacts(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [_normalize_artifact(item) for item in artifacts if isinstance(item, dict)]
    rows = [row for row in rows if row["model_id"]]
    models = _group_stats(rows, "model_id")
    triggers = _group_stats([row for row in rows if row.get("trigger_source")], "trigger_source")
    quality = _group_stats([row for row in rows if row.get("quality_outcome")], "quality_outcome")
    best_model_id = _best_key(models, "average_excess_return_pct") or _best_key(models, "hit_rate_pct")
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "total_artifacts": len(rows),
            "model_count": len(models),
            "best_model_id": best_model_id,
        },
        "models": models,
        "watchlist_triggers": triggers,
        "quality_funnel": quality,
    }


def _normalize_artifact(item: dict[str, Any]) -> dict[str, Any]:
    metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else item
    model_id = str(item.get("alpha_model_id") or "").strip()
    if not model_id and item.get("pipeline_id"):
        model_id = model_for_pipeline(str(item.get("pipeline_id")))["id"]
    quality = item.get("quality_funnel") if isinstance(item.get("quality_funnel"), dict) else {}
    return {
        "model_id": model_id,
        "trigger_source": str(item.get("trigger_source") or "").strip(),
        "quality_outcome": str(quality.get("outcome") or item.get("quality_outcome") or "").strip().lower(),
        "hit": _is_hit(metrics),
        "strategy_roi_pct": _number(metrics.get("strategy_roi_pct")),
        "excess_return_pct": _number(metrics.get("excess_return_pct")),
        "max_drawdown_pct": _number(metrics.get("max_drawdown_pct")),
    }


def _group_stats(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        group_key = str(row.get(key) or "").strip()
        if group_key:
            grouped.setdefault(group_key, []).append(row)
    return {group_key: _stats(group_rows) for group_key, group_rows in sorted(grouped.items())}


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    hits = sum(1 for row in rows if row.get("hit"))
    return {
        "count": len(rows),
        "hit_rate_pct": _round(hits / len(rows) * 100 if rows else 0),
        "average_strategy_roi_pct": _average(rows, "strategy_roi_pct"),
        "average_excess_return_pct": _average(rows, "excess_return_pct"),
        "worst_max_drawdown_pct": _round(min(_values(rows, "max_drawdown_pct"), default=0)),
    }


def _is_hit(metrics: dict[str, Any]) -> bool:
    if "hit" in metrics:
        return bool(metrics.get("hit"))
    return str(metrics.get("outcome") or "").strip().lower() == "hit"


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [float(row[key]) for row in rows if row.get(key) is not None]


def _average(rows: list[dict[str, Any]], key: str) -> float:
    values = _values(rows, key)
    return _round(mean(values)) if values else 0.0


def _best_key(groups: dict[str, dict[str, Any]], metric: str) -> str | None:
    if not groups:
        return None
    return max(groups, key=lambda group_key: float(groups[group_key].get(metric) or 0))


def _round(value: float) -> float:
    return round(float(value), 4)


__all__ = ["SCHEMA_VERSION", "evaluate_strategy_artifacts"]
