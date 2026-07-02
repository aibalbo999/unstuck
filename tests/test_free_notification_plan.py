from free_notification_plan import build_daily_notification_plan


def test_notification_plan_keeps_local_channel_free_and_webhooks_optional():
    dashboard = {
        "status": "action_required",
        "actions": [
            {"type": "rerun_report", "title": "2330.TW 結論需重跑", "detail": "資料不同步"},
            {"type": "run_watchlist", "title": "2 檔 watchlist 待分析", "detail": "2308.TW、2454.TW"},
        ],
    }

    plan = build_daily_notification_plan(dashboard, env={})

    assert plan["schema_version"] == "notification_plan.v1"
    assert plan["free_mode"]["requires_paid_service"] is False
    assert [channel["id"] for channel in plan["channels"] if channel["enabled"]] == ["local"]
    assert plan["channels"][0]["cost_tier"] == "free"
    assert plan["messages"][0]["title"] == "2330.TW 結論需重跑"


def test_notification_plan_enables_user_supplied_free_integrations():
    plan = build_daily_notification_plan(
        {"actions": [{"type": "monitor", "title": "目前沒有急件", "detail": "保持每日追蹤。"}]},
        env={
            "SMTP_HOST": "smtp.example.test",
            "SMTP_TO": "me@example.test",
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_CHAT_ID": "chat",
            "DISCORD_WEBHOOK_URL": "https://discord.example/webhook",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.example/webhook",
        },
    )

    enabled = {channel["id"] for channel in plan["channels"] if channel["enabled"]}

    assert {"local", "email_smtp", "telegram_webhook", "discord_webhook", "slack_webhook"} <= enabled
    assert all(channel["cost_tier"] in {"free", "free_with_user_key"} for channel in plan["channels"])
