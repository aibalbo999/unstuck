"""Notification suppression policy for free-mode notification planning."""

from __future__ import annotations

from typing import Any

from daily_decision_route_warnings import NON_ACTIONABLE_WARNING_IDS
from mapping_fields import mapping_field as _field, safe_text

SUPPRESSED_NOTIFICATION_TYPES = frozenset({"monitor", "fix_notification_delivery"})


def suppress_notification_action(action: dict[str, Any]) -> bool:
    action_type = _action_type(action)
    warning_id = safe_text(_field(action, "warning_id")).strip()
    return (
        explicit_bool(_field(action, "suppress_notification"))
        or action_type in SUPPRESSED_NOTIFICATION_TYPES
        or (action_type == "model_route_warning" and warning_id in NON_ACTIONABLE_WARNING_IDS)
    )


def explicit_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return False
    text = value.strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"", "0", "false", "no", "n", "off"}:
        return False
    return False


def _action_type(action: dict[str, Any]) -> str:
    return safe_text(_field(action, "type")).strip()


__all__ = ["explicit_bool", "suppress_notification_action"]
