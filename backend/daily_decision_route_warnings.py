"""Frontstage policy for model route warnings in the daily decision queue."""

from __future__ import annotations

from typing import Any

from mapping_fields import mapping_field as _field
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text


NON_ACTIONABLE_WARNING_IDS = frozenset({"slow_route"})


def route_warning_items(ops: dict[str, Any]) -> list[dict[str, Any]]:
    budget = safe_mapping_dict(_field(ops, "model_route_budget")) or {}
    return [
        _warning_payload(warning)
        for warning in safe_dict_list(_field(budget, "warnings"))
        if _warning_id(warning) not in NON_ACTIONABLE_WARNING_IDS
    ]


def _warning_payload(warning: dict[str, Any]) -> dict[str, Any]:
    warning_id = _warning_id(warning)
    priority = {"quality_gate_failures": 820, "retry_storm": 650, "slow_route": 610}.get(warning_id, 600)
    route = safe_text(_field(warning, "route")).strip() or "unknown"
    detail = safe_text(_field(warning, "message")).strip() or warning_id
    return {
        "source": "model_route_budget",
        "type": "model_route_warning",
        "priority_score": priority,
        "title": f"{route} 模型路由需檢查",
        "detail": detail,
        "route": route,
        "warning_id": warning_id,
    }


def _warning_id(warning: dict[str, Any]) -> str:
    return safe_text(_field(warning, "id")).strip() or "model_route_warning"


__all__ = ["NON_ACTIONABLE_WARNING_IDS", "route_warning_items"]
