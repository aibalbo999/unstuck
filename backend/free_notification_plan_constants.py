"""Static context and channel tables for free notification planning."""

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
