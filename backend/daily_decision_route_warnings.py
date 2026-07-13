"""Frontstage policy for model route warnings in the daily decision queue."""

from __future__ import annotations

from typing import Any

from mapping_fields import mapping_field as _field


NON_ACTIONABLE_WARNING_IDS = frozenset({"slow_route"})


def route_warning_items(ops: dict[str, Any]) -> list[dict[str, Any]]:
    raw_budget = _field(ops, "model_route_budget")
    budget = raw_budget if isinstance(raw_budget, dict) else {}
    return [
        _warning_payload(warning)
        for warning in _field(budget, "warnings") or []
        if isinstance(warning, dict)
        and str(_field(warning, "id") or "model_route_warning") not in NON_ACTIONABLE_WARNING_IDS
    ]


def _warning_payload(warning: dict[str, Any]) -> dict[str, Any]:
    warning_id = str(_field(warning, "id") or "model_route_warning")
    priority = {"quality_gate_failures": 820, "retry_storm": 650, "slow_route": 610}.get(warning_id, 600)
    route = str(_field(warning, "route") or "unknown")
    return {
        "source": "model_route_budget",
        "type": "model_route_warning",
        "priority_score": priority,
        "title": f"{route} 模型路由需檢查",
        "detail": str(_field(warning, "message") or warning_id),
        "route": route,
        "warning_id": warning_id,
    }


__all__ = ["NON_ACTIONABLE_WARNING_IDS", "route_warning_items"]
