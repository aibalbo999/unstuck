"""Free-mode notification planning without paid services or background sends."""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
import os
from typing import Any, Mapping

from daily_decision_source_labels import normalize_source_counts, source_display_overrides, source_key, source_label, source_labels, source_text, source_texts
from free_notification_identity import dedupe_context, delivery_key, message_delivery_identity
from mapping_fields import mapping_field as _field, safe_dict_list, safe_int, safe_mapping_dict, safe_text, safe_text_list
SCHEMA_VERSION = "notification_plan.v1"
SUPPRESSED_NOTIFICATION_TYPES = {"monitor", "fix_notification_delivery"}
CHANNELS = (
    ("local", "本機 UI 通知", (), "free"),
    ("email_smtp", "SMTP Email", ("SMTP_HOST", "SMTP_TO"), "free_with_user_key"),
    ("telegram_webhook", "Telegram Bot", ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"), "free_with_user_key"),
    ("discord_webhook", "Discord Webhook", ("DISCORD_WEBHOOK_URL",), "free_with_user_key"),
    ("slack_webhook", "Slack Webhook", ("SLACK_WEBHOOK_URL",), "free_with_user_key"),
)

MESSAGE_CONTEXT_KEYS = (
    "source", "source_label", "source_text",
    "priority_score",
    "ticker",
    "filename",
    "report_filename",
    "pipeline_id",
    "route",
    "warning_id",
    "horizon_months",
    "recommended_action",
    "blocks_auto_rerun",
    "reason_codes",
    "severity",
    "action_label",
    "target_panel",
    "target_tab",
    "operator_action",
    "operator_action_label",
    "dedupe_key",
    "message_id",
)
NUMERIC_MESSAGE_CONTEXT_KEYS = ("priority_score", "horizon_months")
BOOLEAN_MESSAGE_CONTEXT_KEYS = ("blocks_auto_rerun",)
TEXT_MESSAGE_CONTEXT_KEYS = (
    "ticker",
    "filename",
    "report_filename",
    "pipeline_id",
    "route",
    "warning_id",
    "recommended_action",
    "severity",
    "action_label",
)
DELIVERY_CONTEXT_KEYS = ("type", "detail", *MESSAGE_CONTEXT_KEYS, "source_label", "source_text", "queue_rank", "queue_displayed_count", "is_top_priority")

OPERATOR_ACTION_BY_TYPE = {
    "rerun_report": ("rerun-report", "完整重跑"),
    "run_watchlist": ("run-watchlist", "建立/更新報告"),
    "refresh_data_snapshot": ("refresh-report", "刷新資料"),
    "manual_review": ("view-report", "查看報告"),
    "wait_provider_recovery": ("open-ops", "查看來源"),
    "backtest_due": ("open-ops", "查看回測"),
    "model_route_warning": ("open-ops", "查看路由"),
    "monitor_provider": ("open-ops", "查看來源"),
    "fix_free_mode": ("open-ops", "修免費模式"),
    "review_candidate": ("open-ops", "查看候選"),
    "monitor": ("monitor", "查看狀態"),
}

TARGET_PANEL_BY_TYPE = {
    "wait_provider_recovery": "provider-sla-panel",
    "monitor_provider": "provider-sla-panel",
    "fix_free_mode": "provider-sla-panel",
    "backtest_due": "performance-panel",
    "model_route_warning": "api-quota-panel",
    "review_candidate": "market-screener-panel",
    "run_watchlist": "watchlist-panel",
}


def build_daily_notification_plan(
    dashboard: dict[str, Any],
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = os.environ if env is None else safe_mapping_dict(env) or {}
    actions, queue_context = _notification_actions(dashboard)
    messages = _messages(actions)
    channels = [_channel_payload(channel_id, label, required, cost, env) for channel_id, label, required, cost in CHANNELS]
    delivery_outbox = _delivery_outbox(messages, channels)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if messages else "quiet",
        "queue_context": queue_context,
        "delivery_summary": _delivery_summary(messages, channels, delivery_outbox),
        "delivery_outbox": delivery_outbox,
        "free_mode": {
            "requires_paid_service": False,
            "policy": "local notifications always work; external channels are user-supplied free integrations",
        },
        "channels": channels,
        "messages": messages,
    }


def _channel_payload(
    channel_id: str,
    label: str,
    required_env: tuple[str, ...],
    cost_tier: str,
    env: Mapping[str, str],
) -> dict[str, Any]:
    missing = [name for name in required_env if not _env_value_present(env, name)]
    return {
        "id": channel_id,
        "label": label,
        "enabled": not missing,
        "cost_tier": cost_tier,
        "requires_env": list(required_env),
        "missing_env": missing,
    }


def _env_value_present(env: Mapping[str, str], name: str) -> bool:
    value = env.get(name)
    return isinstance(value, str) and value.strip() != ""


def _delivery_summary(
    messages: list[dict[str, Any]],
    channels: list[dict[str, Any]],
    delivery_outbox: list[dict[str, Any]],
) -> dict[str, int]:
    return {
        "enabled_channel_count": sum(1 for channel in channels if _field(channel, "enabled") is True),
        "message_count": len(messages),
        "pending_count": len(delivery_outbox),
    }


def _delivery_outbox(messages: list[dict[str, Any]], channels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enabled_channels = [channel for channel in channels if _field(channel, "enabled") is True]
    entries: list[dict[str, Any]] = []
    for message in messages:
        message_id, dedupe_key = message_delivery_identity(message)
        context = {key: _field(message, key) for key in DELIVERY_CONTEXT_KEYS if _present(_field(message, key))}
        for channel in enabled_channels:
            channel_id = str(_field(channel, "id") or "unknown")
            entries.append(
                {
                    "schema_version": "notification_delivery.v1",
                    "channel_id": channel_id,
                    "message_id": message_id,
                    "dedupe_key": dedupe_key,
                    "delivery_key": delivery_key(channel_id, message_id),
                    "delivery_status": "pending",
                    "attempt_count": 0,
                    **context,
                }
            )
    return entries


def _notification_actions(dashboard: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    dashboard = safe_mapping_dict(dashboard) or {}
    raw_queue = _field(dashboard, "decision_queue")
    queue = safe_mapping_dict(raw_queue) or {}
    raw_queue_items = _field(queue, "items")
    queue_items = safe_dict_list(raw_queue_items) if isinstance(raw_queue_items, (list, tuple)) else None
    if queue_items is not None:
        return queue_items, _decision_queue_context(queue)

    raw_actions = _field(dashboard, "actions")
    actions = safe_dict_list(raw_actions) if isinstance(raw_actions, (list, tuple)) else []
    return actions, _legacy_actions_context(actions)


def _decision_queue_context(queue: dict[str, Any]) -> dict[str, Any]:
    raw_summary = _field(queue, "summary")
    summary = safe_mapping_dict(raw_summary) or {}
    raw_sources = _field(summary, "sources")
    sources = safe_mapping_dict(raw_sources) or {}
    source_counts = normalize_source_counts(sources)
    return {
        "source": "decision_queue",
        "total_actionable": _int(_field(summary, "total_actionable")),
        "displayed_count": _int(_field(summary, "displayed_count")),
        "secondary_count": _int(_field(queue, "secondary_count")),
        "top_priority_score": _int(_field(summary, "top_priority_score")),
        "sources": source_counts,
        "source_labels": source_labels(source_counts) | source_display_overrides(source_counts, _field(summary, "source_labels")),
        "source_texts": source_texts(source_counts) | source_display_overrides(source_counts, _field(summary, "source_texts")),
    }


def _legacy_actions_context(actions: list[Any]) -> dict[str, Any]:
    actionable = [action for action in actions if isinstance(action, dict) and _action_type(action) != "monitor"]
    source_counts = _source_counts(actionable)
    return {
        "source": "actions",
        "total_actionable": len(actionable),
        "displayed_count": min(5, len(actionable)),
        "secondary_count": max(0, len(actionable) - 5),
        "top_priority_score": max((_int(_field(action, "priority_score")) for action in actionable), default=0),
        "sources": source_counts,
        "source_labels": source_labels(source_counts),
        "source_texts": source_texts(source_counts),
    }


def _messages(actions: list[Any]) -> list[dict[str, Any]]:
    actionable = [
        action
        for action in actions
        if isinstance(action, dict) and not _suppress_notification(action)
    ][:5]
    displayed_count = len(actionable)
    return [
        _message_context(action) | _rank_context(index, displayed_count) | {
            "type": _action_type(action) or "daily_status",
            "title": _text(_field(action, "title")).strip() or "今日決策狀態",
            "detail": _text(_field(action, "detail")).strip(),
        }
        for index, action in enumerate(actionable, start=1)
    ]


def _rank_context(index: int, displayed_count: int) -> dict[str, Any]:
    return {
        "queue_rank": index,
        "queue_displayed_count": displayed_count,
        "is_top_priority": index == 1,
    }


def _message_context(action: dict[str, Any]) -> dict[str, Any]:
    context = {key: _field(action, key) for key in MESSAGE_CONTEXT_KEYS if _present(_field(action, key))}
    for key in NUMERIC_MESSAGE_CONTEXT_KEYS:
        if key in context:
            context[key] = _int(context[key])
    for key in BOOLEAN_MESSAGE_CONTEXT_KEYS:
        if key in context:
            context[key] = _explicit_bool(context[key])
    for key in TEXT_MESSAGE_CONTEXT_KEYS:
        if key in context:
            text = _text(context[key]).strip()
            if text:
                context[key] = text
            else:
                context.pop(key, None)
    reason_codes = safe_text_list(_field(action, "reason_codes"))
    if reason_codes:
        context["reason_codes"] = reason_codes
    else:
        context.pop("reason_codes", None)
    source = source_key(context.get("source"))
    if source:
        context["source"] = source
        for key, fallback in (("source_label", source_label(source)), ("source_text", source_text(source))):
            context[key] = (value.strip() if isinstance(value := context.get(key), str) else "") or fallback
    else:
        context.pop("source", None)
        context.pop("source_label", None)
        context.pop("source_text", None)
    filename = _first_text(action, "filename", "report_filename")
    if filename != "":
        for key in ("filename", "report_filename"):
            if not isinstance(context.get(key), str) or not context.get(key):
                context[key] = filename
    dedupe = dedupe_context(action)
    context["dedupe_key"] = dedupe["dedupe_key"]
    context["message_id"] = dedupe["message_id"]
    cta = _operator_cta_context(action)
    context["operator_action"] = cta["operator_action"]
    context["operator_action_label"] = cta["operator_action_label"]
    target = _target_context(action)
    context["target_panel"] = target["target_panel"]
    context["target_tab"] = target["target_tab"]
    return context


def _suppress_notification(action: dict[str, Any]) -> bool:
    suppressed = _explicit_bool(_field(action, "suppress_notification"))
    return suppressed or _action_type(action) in SUPPRESSED_NOTIFICATION_TYPES


def _explicit_bool(value: Any) -> bool:
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


def _operator_cta_context(action: dict[str, Any]) -> dict[str, str]:
    default_action, default_label = OPERATOR_ACTION_BY_TYPE.get(_action_type(action), ("open-ops", "查看狀態"))
    return {
        "operator_action": _first_text(action, "operator_action", "operatorAction") or default_action,
        "operator_action_label": _first_text(action, "operator_action_label", "operatorActionLabel", "action_label") or default_label,
    }


def _target_context(action: dict[str, Any]) -> dict[str, str]:
    panel = _first_text(action, "target_panel", "targetPanel") or TARGET_PANEL_BY_TYPE.get(_action_type(action)) or "active-jobs-panel"
    tab = _first_text(action, "target_tab", "targetTab") or _target_tab_for_panel(panel)
    return {"target_panel": panel, "target_tab": tab}


def _target_tab_for_panel(panel: str) -> str:
    return {"watchlist-panel": "tracking", "market-screener-panel": "screener"}.get(panel, "ops")


def _source_counts(actions: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for action in actions:
        source = source_key(_field(action, "source")) or "unknown"
        counts[source] = counts.get(source, 0) + 1
    return counts


def _first_text(action: dict[str, Any], *keys: str) -> str:
    return next((text for key in keys if (text := _text(_field(action, key)).strip()) != ""), "")


def _action_type(action: dict[str, Any]) -> str:
    return _text(_field(action, "type")).strip()


def _text(value: Any) -> str:
    return safe_text(value)
def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value != ""
    return True
def _int(value: Any) -> int:
    if isinstance(value, (bool, bytes, bytearray, memoryview)):
        return 0
    if not isinstance(value, (int, float, str, Decimal, Fraction)):
        return 0
    return max(0, safe_int(value))

__all__ = ["SCHEMA_VERSION", "build_daily_notification_plan"]
