"""Free-mode notification planning without paid services or background sends."""

from __future__ import annotations

import os
from typing import Any, Mapping


SCHEMA_VERSION = "notification_plan.v1"

CHANNELS = (
    ("local", "本機 UI 通知", (), "free"),
    ("email_smtp", "SMTP Email", ("SMTP_HOST", "SMTP_TO"), "free_with_user_key"),
    ("telegram_webhook", "Telegram Bot", ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"), "free_with_user_key"),
    ("discord_webhook", "Discord Webhook", ("DISCORD_WEBHOOK_URL",), "free_with_user_key"),
    ("slack_webhook", "Slack Webhook", ("SLACK_WEBHOOK_URL",), "free_with_user_key"),
)


def build_daily_notification_plan(
    dashboard: dict[str, Any],
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = os.environ if env is None else env
    messages = _messages(dashboard)
    channels = [_channel_payload(channel_id, label, required, cost, env) for channel_id, label, required, cost in CHANNELS]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if messages else "quiet",
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
    missing = [name for name in required_env if not str(env.get(name) or "").strip()]
    return {
        "id": channel_id,
        "label": label,
        "enabled": not missing,
        "cost_tier": cost_tier,
        "requires_env": list(required_env),
        "missing_env": missing,
    }


def _messages(dashboard: dict[str, Any]) -> list[dict[str, str]]:
    actions = dashboard.get("actions") if isinstance(dashboard.get("actions"), list) else []
    return [
        {
            "type": str(action.get("type") or "daily_status"),
            "title": str(action.get("title") or "今日決策狀態"),
            "detail": str(action.get("detail") or ""),
        }
        for action in actions[:5]
        if isinstance(action, dict)
    ]


__all__ = ["SCHEMA_VERSION", "build_daily_notification_plan"]
