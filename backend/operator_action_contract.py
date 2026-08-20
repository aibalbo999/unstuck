"""Shared operator CTA and target metadata contract."""

from __future__ import annotations

from typing import Any, Mapping

from daily_decision_source_labels import source_key
from free_notification_plan_constants import (
    OPERATOR_ACTION_BY_SOURCE_AND_TYPE,
    OPERATOR_ACTION_BY_TYPE,
    TARGET_PANEL_BY_SOURCE_AND_TYPE,
    TARGET_PANEL_BY_TYPE,
)
from mapping_fields import mapping_field as _field
from mapping_fields import safe_text as _text


def operator_action_context(action: Mapping[str, Any]) -> dict[str, str]:
    action_type = _action_type(action)
    source = source_key(_field(action, "source"))
    default_action, default_label = _default_operator_action(action, source, action_type)
    explicit_operator_label = _first_text(action, "operator_action_label", "operatorActionLabel")
    if not explicit_operator_label and not _quality_audit_action_with_filename(source, action_type, action):
        explicit_operator_label = _first_text(action, "action_label")
    return {
        "operator_action": _first_text(action, "operator_action", "operatorAction") or default_action,
        "operator_action_label": explicit_operator_label or default_label,
    }


def target_context(action: Mapping[str, Any]) -> dict[str, str]:
    action_type = _action_type(action)
    source = source_key(_field(action, "source"))
    panel = _first_text(action, "target_panel", "targetPanel") or _default_target_panel(action, source, action_type)
    tab = _first_text(action, "target_tab", "targetTab") or target_tab_for_panel(panel)
    return {"target_panel": panel, "target_tab": tab}


def navigation_context(action: Mapping[str, Any]) -> dict[str, str]:
    return operator_action_context(action) | target_context(action)


def target_tab_for_panel(panel: str) -> str:
    return {
        "watchlist-panel": "tracking",
        "market-screener-panel": "screener",
        "history-quality-audit": "analysis",
    }.get(panel, "ops")


def _default_operator_action(action: Mapping[str, Any], source: str, action_type: str) -> tuple[str, str]:
    source_default = None
    if _source_type_default_allowed(action, source, action_type):
        source_default = OPERATOR_ACTION_BY_SOURCE_AND_TYPE.get((source, action_type))
    return source_default or OPERATOR_ACTION_BY_TYPE.get(action_type, ("open-ops", "查看狀態"))


def _default_target_panel(action: Mapping[str, Any], source: str, action_type: str) -> str:
    source_default = None
    if _source_type_default_allowed(action, source, action_type):
        source_default = TARGET_PANEL_BY_SOURCE_AND_TYPE.get((source, action_type))
    return source_default or TARGET_PANEL_BY_TYPE.get(action_type) or "active-jobs-panel"


def _source_type_default_allowed(action: Mapping[str, Any], source: str, action_type: str) -> bool:
    return not (
        source == "report_quality_audit"
        and action_type == "manual_review"
        and not _first_text(action, "filename", "report_filename")
    )


def _quality_audit_action_with_filename(source: str, action_type: str, action: Mapping[str, Any]) -> bool:
    return (
        source == "report_quality_audit"
        and action_type == "manual_review"
        and bool(_first_text(action, "filename", "report_filename"))
    )


def _first_text(action: Mapping[str, Any], *keys: str) -> str:
    return next((text for key in keys if (text := _text(_field(action, key)).strip()) != ""), "")


def _action_type(action: Mapping[str, Any]) -> str:
    return _text(_field(action, "type")).strip()


__all__ = ["navigation_context", "operator_action_context", "target_context", "target_tab_for_panel"]
