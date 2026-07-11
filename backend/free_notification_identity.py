"""Stable notification delivery identity helpers."""

from __future__ import annotations

from typing import Any

from mapping_fields import mapping_field as _field

IDENTITY_ERRORS = (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError)


def message_delivery_identity(message: dict[str, Any]) -> tuple[str, str]:
    dedupe_key = next((text for key in ("dedupe_key", "message_id") if (text := identity_part(_field(message, key), ""))), "message")
    message_id = next((text for key in ("message_id",) if (text := identity_part(_field(message, key), ""))), dedupe_key)
    return message_id, dedupe_key


def delivery_key(channel_id: str, message_id: str) -> str:
    return "|".join(
        [
            "notification_delivery.v1",
            identity_part(channel_id, "channel"),
            identity_part(message_id, "message"),
        ]
    )


def dedupe_context(action: dict[str, Any]) -> dict[str, str]:
    existing = next((text for key in ("dedupe_key", "dedupeKey", "message_id") if (text := identity_part(_field(action, key), ""))), "")
    key = existing or _dedupe_key(action)
    message_id = next((text for key in ("message_id", "messageId") if (text := identity_part(_field(action, key), ""))), key)
    return {"dedupe_key": key, "message_id": message_id or key}


def _dedupe_key(action: dict[str, Any]) -> str:
    source = identity_part(_field(action, "source"), "unknown")
    action_type = identity_part(_field(action, "type"), "daily_status")
    return "|".join(["notification_plan.v1", source, action_type, *_identity_parts_for_action(action)])


def _identity_parts_for_action(action: dict[str, Any]) -> list[str]:
    action_type = identity_part(_field(action, "type"), "")
    if action_type == "model_route_warning":
        return [
            identity_part(_field(action, "route"), "unknown-route"),
            identity_part(_field(action, "warning_id"), "model_route_warning"),
        ]
    if action_type == "backtest_due":
        return [
            _first_identity(action, identity_part(_field(action, "ticker"), "report"), "filename", "report_filename"),
            identity_part(_field(action, "horizon_months"), "unknown-horizon"),
            identity_part(_field(action, "pipeline_id"), "v1"),
        ]
    if _has_identity(action, "filename", "report_filename", "ticker", "pipeline_id"):
        return [
            identity_part(_field(action, "ticker"), "ticker"),
            _first_identity(action, "report", "filename", "report_filename"),
            identity_part(_field(action, "pipeline_id"), "v1"),
        ]
    if _has_identity(action, "route", "warning_id"):
        return [
            identity_part(_field(action, "route"), "unknown-route"),
            identity_part(_field(action, "warning_id"), "event"),
        ]
    return [identity_part(_field(action, "title"), "untitled")]


def _has_identity(action: dict[str, Any], *keys: str) -> bool:
    return any(identity_part(_field(action, key), "") for key in keys)


def _first_identity(action: dict[str, Any], fallback: Any, *keys: str) -> str:
    return next((text for key in keys if (text := identity_part(_field(action, key), ""))), str(fallback))


def identity_part(value: Any, fallback: Any) -> str:
    try:
        text = str(value if value not in (None, "") else fallback)
    except IDENTITY_ERRORS:
        text = str(fallback)
    return text.replace("|", "/").strip() or str(fallback)


__all__ = ["dedupe_context", "delivery_key", "identity_part", "message_delivery_identity"]
