from decimal import Decimal
from fractions import Fraction
from types import MappingProxyType

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


def test_notification_plan_preserves_decision_queue_context():
    plan = build_daily_notification_plan(
        {
            "actions": [
                {
                    "type": "wait_provider_recovery",
                    "title": "NVDA provider 影響需處理",
                    "detail": "market_data/yfinance critical",
                    "source": "provider_impact",
                    "priority_score": 900,
                    "ticker": "NVDA",
                    "filename": "nvda_provider.html",
                    "pipeline_id": "v2",
                }
            ]
        },
        env={},
    )

    message = plan["messages"][0]
    assert message["source"] == "provider_impact"
    assert message["priority_score"] == 900
    assert message["ticker"] == "NVDA"
    assert message["filename"] == "nvda_provider.html"
    assert message["pipeline_id"] == "v2"
    assert message["source_label"] == "資料來源"
    assert message["source_text"] == "資料來源 (provider_impact)"


def test_notification_plan_preserves_action_source_display_context():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "partner_feed",
                        "source_label": "合作來源",
                        "source_text": "合作來源 (partner_feed)",
                        "type": "manual_review",
                        "title": "外部來源事件需人工檢查",
                        "detail": "合作來源提供新事件，需確認是否影響報告。",
                    }
                ]
            }
        },
        env={},
    )

    message = plan["messages"][0]
    assert message["source_label"] == "合作來源"
    assert message["source_text"] == "合作來源 (partner_feed)"
    assert plan["delivery_outbox"][0]["source_label"] == "合作來源"
    assert plan["delivery_outbox"][0]["source_text"] == "合作來源 (partner_feed)"


def test_notification_plan_trims_action_source_display_context():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "partner_feed",
                        "source_label": " 合作來源 ",
                        "source_text": "\t合作來源 (partner_feed)\n",
                        "type": "manual_review",
                        "title": "外部來源事件需人工檢查",
                        "detail": "合作來源提供新事件，需確認是否影響報告。",
                    }
                ]
            }
        },
        env={},
    )

    message = plan["messages"][0]
    outbox = plan["delivery_outbox"][0]
    assert message["source_label"] == "合作來源"
    assert message["source_text"] == "合作來源 (partner_feed)"
    assert outbox["source_label"] == "合作來源"
    assert outbox["source_text"] == "合作來源 (partner_feed)"


def test_notification_plan_ignores_blank_action_source_display_context():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "provider_impact",
                        "source_label": "   ",
                        "source_text": "\t",
                        "type": "wait_provider_recovery",
                        "title": "Provider degraded",
                        "detail": "market data timeout",
                    }
                ]
            }
        },
        env={},
    )

    message = plan["messages"][0]
    outbox = plan["delivery_outbox"][0]
    assert message["source_label"] == "資料來源"
    assert message["source_text"] == "資料來源 (provider_impact)"
    assert outbox["source_label"] == "資料來源"
    assert outbox["source_text"] == "資料來源 (provider_impact)"


def test_notification_plan_ignores_non_string_action_source_display_context():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "provider_impact",
                        "source_label": 123,
                        "source_text": True,
                        "type": "wait_provider_recovery",
                        "title": "Provider degraded",
                        "detail": "market data timeout",
                    }
                ]
            }
        },
        env={},
    )

    message = plan["messages"][0]
    outbox = plan["delivery_outbox"][0]
    assert message["source_label"] == "資料來源"
    assert message["source_text"] == "資料來源 (provider_impact)"
    assert outbox["source_label"] == "資料來源"
    assert outbox["source_text"] == "資料來源 (provider_impact)"


def test_notification_plan_messages_trim_action_source_keys():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": " provider_impact ",
                        "type": "wait_provider_recovery",
                        "title": "Provider degraded",
                        "detail": "market data timeout",
                    }
                ]
            }
        },
        env={},
    )

    message = plan["messages"][0]
    outbox = plan["delivery_outbox"][0]
    assert message["source"] == "provider_impact"
    assert message["source_text"] == "資料來源 (provider_impact)"
    assert outbox["source"] == "provider_impact"
    assert outbox["source_text"] == "資料來源 (provider_impact)"


def test_notification_plan_messages_drop_blank_action_source_keys():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "   ",
                        "type": "manual_review",
                        "title": "Manual review",
                        "detail": "No source key available.",
                    }
                ]
            }
        },
        env={},
    )

    message = plan["messages"][0]
    outbox = plan["delivery_outbox"][0]
    assert "source" not in message
    assert "source_label" not in message
    assert "source_text" not in message
    assert "source" not in outbox
    assert "source_label" not in outbox
    assert "source_text" not in outbox


def test_notification_plan_messages_drop_orphan_source_display_context():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source_label": b"decoded label should not leak",
                        "source_text": True,
                        "type": "manual_review",
                        "title": "Manual review",
                        "detail": "No source key available.",
                    }
                ]
            }
        },
        env={},
    )

    message = plan["messages"][0]
    outbox = plan["delivery_outbox"][0]
    assert "source" not in message
    assert "source_label" not in message
    assert "source_text" not in message
    assert "source" not in outbox
    assert "source_label" not in outbox
    assert "source_text" not in outbox


def test_notification_plan_prefers_decision_queue_contract_over_legacy_actions():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {
                    "total_actionable": 4,
                    "displayed_count": 1,
                    "top_priority_score": 1000,
                    "sources": {"report_repair": 1, "watchlist": 3},
                    "source_labels": {"report_repair": "人工修復", "watchlist": "人工清單"},
                    "source_texts": {"report_repair": "人工修復 (report_repair)", "watchlist": "人工清單 (watchlist)"},
                },
                "items": [
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "priority_score": 1000,
                        "title": "2330.TW v2 內容可信度未通過",
                        "detail": "目標價與買入建議不一致。",
                        "ticker": "2330.TW",
                        "filename": "2330_blocked.html",
                        "pipeline_id": "v2",
                    }
                ],
                "secondary_count": 3,
            },
            "actions": [
                {
                    "type": "run_watchlist",
                    "title": "legacy action",
                    "detail": "legacy fallback should not win",
                }
            ],
        },
        env={},
    )

    assert plan["messages"][0]["type"] == "manual_review"
    assert plan["messages"][0]["source"] == "report_repair"
    assert plan["messages"][0]["title"] == "2330.TW v2 內容可信度未通過"
    assert plan["queue_context"] == {
        "source": "decision_queue",
        "total_actionable": 4,
        "displayed_count": 1,
        "secondary_count": 3,
        "top_priority_score": 1000,
        "sources": {"report_repair": 1, "watchlist": 3},
        "source_labels": {"report_repair": "人工修復", "watchlist": "人工清單"},
        "source_texts": {"report_repair": "人工修復 (report_repair)", "watchlist": "人工清單 (watchlist)"},
    }


def test_notification_plan_queue_context_fills_partial_source_display_maps():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {
                    "total_actionable": 3,
                    "displayed_count": 2,
                    "sources": {"report_repair": 1, "watchlist": 2},
                    "source_labels": {"report_repair": "人工修復"},
                    "source_texts": {"report_repair": "人工修復 (report_repair)"},
                },
                "items": [
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "報告需人工修復",
                        "detail": "內容可信度未通過。",
                    }
                ],
            }
        },
        env={},
    )

    assert plan["queue_context"]["source_labels"] == {
        "report_repair": "人工修復",
        "watchlist": "追蹤清單",
    }
    assert plan["queue_context"]["source_texts"] == {
        "report_repair": "人工修復 (report_repair)",
        "watchlist": "追蹤清單 (watchlist)",
    }


def test_notification_plan_queue_context_ignores_blank_source_display_overrides():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {
                    "sources": {"watchlist": 2},
                    "source_labels": {"watchlist": ""},
                    "source_texts": {"watchlist": None},
                },
                "items": [
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "title": "追蹤清單待分析",
                        "detail": "2 檔待更新。",
                    }
                ],
            }
        },
        env={},
    )

    assert plan["queue_context"]["source_labels"] == {"watchlist": "追蹤清單"}
    assert plan["queue_context"]["source_texts"] == {"watchlist": "追蹤清單 (watchlist)"}


def test_notification_plan_queue_context_drops_inactive_source_display_overrides():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {
                    "sources": {"watchlist": 2},
                    "source_labels": {"watchlist": "人工清單", "ghost_source": "幽靈來源"},
                    "source_texts": {
                        "watchlist": "人工清單 (watchlist)",
                        "ghost_source": "幽靈來源 (ghost_source)",
                    },
                },
                "items": [
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "title": "追蹤清單待分析",
                        "detail": "2 檔待更新。",
                    }
                ],
            }
        },
        env={},
    )

    assert plan["queue_context"]["source_labels"] == {"watchlist": "人工清單"}
    assert plan["queue_context"]["source_texts"] == {"watchlist": "人工清單 (watchlist)"}


def test_notification_plan_queue_context_trims_source_distribution_keys():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {
                    "sources": {" watchlist ": 2, "\tprovider_impact\n": 1},
                    "source_labels": {" watchlist ": " 人工清單 "},
                    "source_texts": {" watchlist ": "\t人工清單 (watchlist)\n"},
                },
                "items": [
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "title": "追蹤清單待分析",
                        "detail": "2 檔待更新。",
                    }
                ],
            }
        },
        env={},
    )

    assert plan["queue_context"]["sources"] == {"watchlist": 2, "provider_impact": 1}
    assert plan["queue_context"]["source_labels"] == {"watchlist": "人工清單", "provider_impact": "資料來源"}
    assert plan["queue_context"]["source_texts"] == {
        "watchlist": "人工清單 (watchlist)",
        "provider_impact": "資料來源 (provider_impact)",
    }


def test_notification_plan_legacy_actions_context_trims_source_distribution_keys():
    plan = build_daily_notification_plan(
        {
            "actions": [
                {
                    "source": " watchlist ",
                    "type": "run_watchlist",
                    "title": "追蹤清單待分析",
                    "detail": "2 檔待更新。",
                }
            ]
        },
        env={},
    )

    assert plan["queue_context"]["sources"] == {"watchlist": 1}
    assert plan["queue_context"]["source_labels"] == {"watchlist": "追蹤清單"}
    assert plan["queue_context"]["source_texts"] == {"watchlist": "追蹤清單 (watchlist)"}


def test_notification_plan_legacy_actions_context_maps_non_string_sources_to_unknown():
    plan = build_daily_notification_plan(
        {
            "actions": [
                {
                    "source": 123,
                    "type": "rerun_report",
                    "title": "Numeric source",
                    "detail": "Legacy action source is malformed.",
                },
                {
                    "source": True,
                    "type": "run_watchlist",
                    "title": "Boolean source",
                    "detail": "Legacy action source is malformed.",
                },
                {
                    "source": " watchlist ",
                    "type": "run_watchlist",
                    "title": "追蹤清單待分析",
                    "detail": "1 檔待更新。",
                },
            ]
        },
        env={},
    )

    assert plan["queue_context"]["sources"] == {"unknown": 2, "watchlist": 1}
    assert plan["queue_context"]["source_labels"] == {"unknown": "unknown", "watchlist": "追蹤清單"}
    assert plan["queue_context"]["source_texts"] == {"unknown": "unknown", "watchlist": "追蹤清單 (watchlist)"}


def test_notification_plan_legacy_actions_context_uses_string_safe_type_filter():
    class BrokenTruthType:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("legacy action type truthiness unavailable")

        def __str__(self):
            return self.value

    plan = build_daily_notification_plan(
        {
            "actions": [
                {
                    "source": "monitor",
                    "type": BrokenTruthType("monitor"),
                    "title": "目前沒有急件",
                    "detail": "保持每日追蹤。",
                },
                {
                    "source": "report_repair",
                    "type": BrokenTruthType("manual_review"),
                    "title": "TSM 報告需人工審核",
                    "detail": "內容可信度未通過。",
                },
            ]
        },
        env={},
    )

    assert plan["queue_context"]["total_actionable"] == 1
    assert plan["queue_context"]["sources"] == {"report_repair": 1}
    assert [message["type"] for message in plan["messages"]] == ["manual_review"]


def test_notification_plan_queue_context_ignores_numeric_conversion_failures():
    class BrokenTruthNumber:
        def __bool__(self):
            raise RuntimeError("queue number truthiness unavailable")

    class BrokenIntNumber:
        def __bool__(self):
            return True

        def __int__(self):
            raise ArithmeticError("queue number int unavailable")

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {
                    "total_actionable": BrokenTruthNumber(),
                    "displayed_count": BrokenIntNumber(),
                    "top_priority_score": float("inf"),
                    "sources": {"watchlist": 1},
                },
                "secondary_count": BrokenIntNumber(),
                "items": [
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "title": "追蹤清單待分析",
                        "detail": "1 檔待更新。",
                    }
                ],
            }
        },
        env={},
    )

    assert plan["queue_context"]["total_actionable"] == 0
    assert plan["queue_context"]["displayed_count"] == 0
    assert plan["queue_context"]["secondary_count"] == 0
    assert plan["queue_context"]["top_priority_score"] == 0
    assert plan["queue_context"]["sources"] == {"watchlist": 1}


def test_notification_plan_queue_context_rejects_binary_and_boolean_counts():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {
                    "total_actionable": b"4",
                    "displayed_count": True,
                    "top_priority_score": memoryview(b"980"),
                    "sources": {"watchlist": 1},
                },
                "secondary_count": bytearray(b"3"),
                "items": [
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "title": "追蹤清單待分析",
                        "detail": "1 檔待更新。",
                    }
                ],
            }
        },
        env={},
    )

    assert plan["queue_context"]["total_actionable"] == 0
    assert plan["queue_context"]["displayed_count"] == 0
    assert plan["queue_context"]["secondary_count"] == 0
    assert plan["queue_context"]["top_priority_score"] == 0
    assert plan["queue_context"]["sources"] == {"watchlist": 1}
    assert plan["messages"][0]["type"] == "run_watchlist"


def test_notification_plan_rejects_fractional_numeric_counts_and_metadata():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {
                    "total_actionable": 1.5,
                    "displayed_count": Decimal("2.5"),
                    "top_priority_score": Fraction(7, 2),
                    "sources": {"watchlist": 1},
                },
                "secondary_count": Fraction(3, 2),
                "items": [
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "priority_score": 1.7,
                        "horizon_months": Decimal("3.5"),
                        "title": "追蹤清單待分析",
                        "detail": "1 檔待更新。",
                    }
                ],
            }
        },
        env={},
    )

    assert plan["queue_context"]["total_actionable"] == 0
    assert plan["queue_context"]["displayed_count"] == 0
    assert plan["queue_context"]["secondary_count"] == 0
    assert plan["queue_context"]["top_priority_score"] == 0
    assert plan["messages"][0]["priority_score"] == 0
    assert plan["messages"][0]["horizon_months"] == 0
    assert plan["delivery_outbox"][0]["priority_score"] == 0
    assert plan["delivery_outbox"][0]["horizon_months"] == 0


def test_notification_plan_rejects_negative_numeric_counts_and_metadata():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {
                    "total_actionable": -1,
                    "displayed_count": "-2",
                    "top_priority_score": Decimal("-3"),
                    "sources": {"watchlist": 1},
                },
                "secondary_count": Fraction(-4, 1),
                "items": [
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "priority_score": -5,
                        "horizon_months": "-6",
                        "title": "追蹤清單待分析",
                        "detail": "1 檔待更新。",
                    }
                ],
            }
        },
        env={},
    )

    assert plan["queue_context"]["total_actionable"] == 0
    assert plan["queue_context"]["displayed_count"] == 0
    assert plan["queue_context"]["secondary_count"] == 0
    assert plan["queue_context"]["top_priority_score"] == 0
    assert plan["messages"][0]["priority_score"] == 0
    assert plan["messages"][0]["horizon_months"] == 0
    assert plan["delivery_outbox"][0]["priority_score"] == 0
    assert plan["delivery_outbox"][0]["horizon_months"] == 0


def test_notification_plan_rejects_arbitrary_numeric_counts_and_metadata():
    class SyntheticCount:
        def __init__(self, value):
            self.value = value

        def __int__(self):
            return self.value

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {
                    "total_actionable": SyntheticCount(4),
                    "displayed_count": SyntheticCount(3),
                    "top_priority_score": SyntheticCount(980),
                    "sources": {"watchlist": 1},
                },
                "secondary_count": SyntheticCount(2),
                "items": [
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "priority_score": SyntheticCount(760),
                        "horizon_months": SyntheticCount(12),
                        "title": "追蹤清單待分析",
                        "detail": "1 檔待更新。",
                    }
                ],
            }
        },
        env={},
    )

    assert plan["queue_context"]["total_actionable"] == 0
    assert plan["queue_context"]["displayed_count"] == 0
    assert plan["queue_context"]["secondary_count"] == 0
    assert plan["queue_context"]["top_priority_score"] == 0
    assert plan["messages"][0]["priority_score"] == 0
    assert plan["messages"][0]["horizon_months"] == 0
    assert plan["delivery_outbox"][0]["priority_score"] == 0
    assert plan["delivery_outbox"][0]["horizon_months"] == 0


def test_notification_plan_preserves_action_specific_metadata():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {"total_actionable": 3, "displayed_count": 3},
                "items": [
                    {
                        "source": "model_route_budget",
                        "type": "model_route_warning",
                        "priority_score": 650,
                        "title": "v2/gemini-2.5-pro 模型路由需檢查",
                        "detail": "retry_count=7",
                        "route": "v2/gemini-2.5-pro",
                        "warning_id": "retry_storm",
                    },
                    {
                        "source": "backtest_due",
                        "type": "backtest_due",
                        "priority_score": 763,
                        "title": "2308.TW 3M 回測到期",
                        "detail": "先完成到期回測。",
                        "ticker": "2308.TW",
                        "filename": "2308_due.html",
                        "pipeline_id": "v1",
                        "horizon_months": 3,
                    },
                    {
                        "source": "provider_impact",
                        "type": "wait_provider_recovery",
                        "priority_score": 900,
                        "title": "NVDA provider 影響需處理",
                        "detail": "market_data/yfinance critical",
                        "ticker": "NVDA",
                        "filename": "nvda_provider.html",
                        "pipeline_id": "v2",
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                    },
                ],
            }
        },
        env={},
    )

    route_message, backtest_message, provider_message = plan["messages"]
    assert route_message["route"] == "v2/gemini-2.5-pro"
    assert route_message["warning_id"] == "retry_storm"
    assert backtest_message["horizon_months"] == 3
    assert provider_message["recommended_action"] == "wait_provider_recovery"
    assert provider_message["blocks_auto_rerun"] is True


def test_notification_plan_numeric_message_metadata_uses_strict_count_conversion():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "backtest_due",
                        "type": "backtest_due",
                        "priority_score": b"763",
                        "title": "NVDA 回測到期",
                        "detail": "先完成到期回測。",
                        "ticker": "NVDA",
                        "filename": "nvda_due.html",
                        "pipeline_id": "v2",
                        "horizon_months": memoryview(b"3"),
                    },
                    {
                        "source": "provider_impact",
                        "type": "wait_provider_recovery",
                        "priority_score": True,
                        "title": "Provider degraded",
                        "detail": "需要查看來源。",
                    },
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    backtest_message, provider_message = plan["messages"]
    assert backtest_message["priority_score"] == 0
    assert backtest_message["horizon_months"] == 0
    assert "unknown-horizon" in backtest_message["dedupe_key"]
    assert "memory" not in backtest_message["dedupe_key"]
    assert provider_message["priority_score"] == 0
    assert all(entry["priority_score"] == 0 for entry in plan["delivery_outbox"])
    assert all(entry.get("horizon_months", 0) == 0 for entry in plan["delivery_outbox"])


def test_notification_plan_text_message_metadata_uses_shared_text_conversion():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "報告需審核",
                        "detail": "資料可信度不足。",
                        "ticker": b"NVDA",
                        "filename": bytearray(b"bad.html"),
                        "report_filename": memoryview(b"worse.html"),
                        "pipeline_id": True,
                        "route": b"v2/gemini",
                        "warning_id": memoryview(b"retry_storm"),
                        "recommended_action": True,
                        "blocks_auto_rerun": True,
                        "severity": bytearray(b"critical"),
                        "action_label": memoryview(b"manual review"),
                    }
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    message = plan["messages"][0]
    outbox = plan["delivery_outbox"]
    malformed_keys = {
        "ticker",
        "filename",
        "report_filename",
        "pipeline_id",
        "route",
        "warning_id",
        "recommended_action",
        "severity",
        "action_label",
    }
    assert malformed_keys.isdisjoint(message)
    assert message["blocks_auto_rerun"] is True
    assert message["operator_action"] == "view-report"
    assert message["operator_action_label"] == "查看報告"
    assert all(malformed_keys.isdisjoint(entry) for entry in outbox)
    assert all(entry["blocks_auto_rerun"] is True for entry in outbox)


def test_notification_plan_boolean_message_metadata_uses_explicit_bool_text_conversion():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "明確不阻擋",
                        "detail": "這筆可以自動處理。",
                        "blocks_auto_rerun": "false",
                    },
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "明確阻擋",
                        "detail": "這筆需要人工處理。",
                        "blocks_auto_rerun": "true",
                    },
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "binary 不可信",
                        "detail": "binary flag 不應外洩。",
                        "blocks_auto_rerun": b"true",
                    },
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "memoryview 不可信",
                        "detail": "memoryview flag 不應外洩。",
                        "blocks_auto_rerun": memoryview(b"true"),
                    },
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    assert [message["blocks_auto_rerun"] for message in plan["messages"]] == [
        False,
        True,
        False,
        False,
    ]
    assert [entry["blocks_auto_rerun"] for entry in plan["delivery_outbox"]] == [
        False,
        False,
        True,
        True,
        False,
        False,
        False,
        False,
    ]


def test_notification_plan_preserves_report_repair_reason_codes():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {"total_actionable": 1, "displayed_count": 1},
                "items": [
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "priority_score": 980,
                        "title": "2330.TW v2 資料快照完整性未通過",
                        "detail": "snapshot_hash mismatch",
                        "ticker": "2330.TW",
                        "filename": "2330_corrupt.html",
                        "pipeline_id": "v2",
                        "recommended_action": "manual_review",
                        "blocks_auto_rerun": True,
                        "reason_codes": ["data_snapshot_integrity_invalid"],
                    }
                ],
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    message = plan["messages"][0]
    assert message["blocks_auto_rerun"] is True
    assert message["detail"] == "snapshot_hash mismatch"
    assert message["reason_codes"] == ["data_snapshot_integrity_invalid"]
    assert all(entry["detail"] == "snapshot_hash mismatch" for entry in plan["delivery_outbox"])
    assert all(entry["reason_codes"] == ["data_snapshot_integrity_invalid"] for entry in plan["delivery_outbox"])


def test_notification_plan_reads_decision_queue_action_fields_without_mapping_get_accessors():
    class BrokenGetDict(dict):
        def get(self, *args, **kwargs):
            raise RuntimeError("notification action get accessor unavailable")

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    BrokenGetDict({
                        "source": "backtest_due",
                        "type": "backtest_due",
                        "priority_score": 766,
                        "title": "NVDA 6M 回測到期",
                        "detail": "先完成到期回測。",
                        "ticker": "NVDA",
                        "report_filename": "nvda_due_alias.html",
                        "pipeline_id": "v2",
                        "horizon_months": 6,
                        "target_panel": "performance-panel",
                        "operator_action": "open-ops",
                        "operator_action_label": "查看回測",
                    })
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    message = plan["messages"][0]
    assert message["source"] == "backtest_due"
    assert message["source_text"] == "決策回測 (backtest_due)"
    assert message["type"] == "backtest_due"
    assert message["title"] == "NVDA 6M 回測到期"
    assert message["filename"] == "nvda_due_alias.html"
    assert message["report_filename"] == "nvda_due_alias.html"
    assert message["horizon_months"] == 6
    assert message["target_panel"] == "performance-panel"
    assert message["operator_action_label"] == "查看回測"
    assert message["queue_rank"] == 1
    assert message["dedupe_key"] == "notification_plan.v1|backtest_due|backtest_due|nvda_due_alias.html|6|v2"
    assert [entry["channel_id"] for entry in plan["delivery_outbox"]] == ["local", "telegram_webhook"]
    assert all(entry["filename"] == "nvda_due_alias.html" for entry in plan["delivery_outbox"])
    assert all(entry["source_text"] == "決策回測 (backtest_due)" for entry in plan["delivery_outbox"])


def test_notification_plan_decision_queue_items_iterator_failure_uses_native_actions():
    class BrokenActionList(list):
        def __iter__(self):
            raise RuntimeError("notification action iterator unavailable")

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": BrokenActionList(
                    [
                        {
                            "source": "watchlist",
                            "type": "run_watchlist",
                            "title": "追蹤清單待分析",
                            "detail": "1 檔待更新。",
                        },
                        "malformed action should be ignored",
                    ]
                )
            }
        },
        env={},
    )

    assert plan["messages"][0]["type"] == "run_watchlist"
    assert plan["messages"][0]["source"] == "watchlist"
    assert plan["delivery_outbox"][0]["source"] == "watchlist"


def test_notification_plan_legacy_actions_iterator_failure_uses_native_actions():
    class BrokenActionList(list):
        def __iter__(self):
            raise RuntimeError("legacy notification action iterator unavailable")

    plan = build_daily_notification_plan(
        {
            "actions": BrokenActionList(
                [
                    {
                        "source": "provider_impact",
                        "type": "wait_provider_recovery",
                        "title": "Provider degraded",
                        "detail": "需要查看資料來源。",
                    },
                    object(),
                ]
            )
        },
        env={},
    )

    assert plan["queue_context"]["sources"] == {"provider_impact": 1}
    assert plan["messages"][0]["type"] == "wait_provider_recovery"
    assert plan["messages"][0]["source"] == "provider_impact"


def test_notification_plan_decision_queue_accepts_tuple_actions():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": (
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "title": "追蹤清單待分析",
                        "detail": "1 檔待更新。",
                    },
                    "malformed action should be ignored",
                )
            }
        },
        env={},
    )

    assert plan["queue_context"]["source"] == "decision_queue"
    assert plan["messages"][0]["type"] == "run_watchlist"
    assert plan["messages"][0]["source"] == "watchlist"
    assert plan["delivery_outbox"][0]["source"] == "watchlist"


def test_notification_plan_legacy_actions_accepts_tuple_actions():
    plan = build_daily_notification_plan(
        {
            "actions": (
                {
                    "source": "provider_impact",
                    "type": "wait_provider_recovery",
                    "title": "Provider degraded",
                    "detail": "需要查看資料來源。",
                },
                object(),
            )
        },
        env={},
    )

    assert plan["queue_context"]["sources"] == {"provider_impact": 1}
    assert plan["messages"][0]["type"] == "wait_provider_recovery"
    assert plan["messages"][0]["source"] == "provider_impact"


def test_notification_plan_accepts_mapping_decision_queue_payloads():
    plan = build_daily_notification_plan(
        {
            "decision_queue": MappingProxyType(
                {
                    "summary": {"sources": {"watchlist": 1}},
                    "items": [
                        {
                            "source": "watchlist",
                            "type": "run_watchlist",
                            "title": "追蹤清單待分析",
                            "detail": "1 檔待更新。",
                        }
                    ],
                }
            )
        },
        env={},
    )

    assert plan["queue_context"]["source"] == "decision_queue"
    assert plan["queue_context"]["sources"] == {"watchlist": 1}
    assert plan["messages"][0]["type"] == "run_watchlist"
    assert plan["messages"][0]["source"] == "watchlist"


def test_notification_plan_accepts_mapping_decision_queue_summary_payloads():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": MappingProxyType(
                    {
                        "total_actionable": 1,
                        "displayed_count": 1,
                        "top_priority_score": 710,
                        "sources": MappingProxyType({"provider_impact": 1}),
                        "source_labels": MappingProxyType({"provider_impact": "資料來源修復"}),
                    }
                ),
                "items": [
                    {
                        "source": "provider_impact",
                        "type": "wait_provider_recovery",
                        "title": "Provider degraded",
                        "detail": "需要查看資料來源。",
                    }
                ],
            }
        },
        env={},
    )

    assert plan["queue_context"]["total_actionable"] == 1
    assert plan["queue_context"]["displayed_count"] == 1
    assert plan["queue_context"]["top_priority_score"] == 710
    assert plan["queue_context"]["sources"] == {"provider_impact": 1}
    assert plan["queue_context"]["source_labels"] == {"provider_impact": "資料來源修復"}
    assert plan["messages"][0]["source"] == "provider_impact"


def test_notification_plan_accepts_mapping_dashboard_payloads():
    plan = build_daily_notification_plan(
        MappingProxyType(
            {
                "decision_queue": {
                    "summary": {"sources": {"watchlist": 1}},
                    "items": [
                        {
                            "source": "watchlist",
                            "type": "run_watchlist",
                            "title": "追蹤清單待分析",
                            "detail": "1 檔待更新。",
                        }
                    ],
                }
            }
        ),
        env={},
    )

    assert plan["queue_context"]["source"] == "decision_queue"
    assert plan["queue_context"]["sources"] == {"watchlist": 1}
    assert plan["messages"][0]["type"] == "run_watchlist"
    assert plan["messages"][0]["source"] == "watchlist"


def test_notification_plan_preserves_report_filename_alias_context():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {"total_actionable": 1, "displayed_count": 1},
                "items": [
                    {
                        "source": "backtest_due",
                        "type": "backtest_due",
                        "priority_score": 763,
                        "title": "NVDA 3M 回測到期",
                        "detail": "先完成到期回測。",
                        "ticker": "NVDA",
                        "report_filename": "nvda_due_alias.html",
                        "pipeline_id": "v2",
                        "horizon_months": 3,
                    }
                ],
            }
        },
        env={},
    )

    message = plan["messages"][0]
    assert message["report_filename"] == "nvda_due_alias.html"
    assert message["dedupe_key"] == "notification_plan.v1|backtest_due|backtest_due|nvda_due_alias.html|3|v2"


def test_notification_plan_normalizes_report_filename_aliases():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {"total_actionable": 2, "displayed_count": 2},
                "items": [
                    {
                        "source": "backtest_due",
                        "type": "backtest_due",
                        "title": "NVDA 3M 回測到期",
                        "detail": "先完成到期回測。",
                        "report_filename": "nvda_due_alias.html",
                        "horizon_months": 3,
                    },
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "TSM 報告需人工審核",
                        "detail": "內容可信度未通過。",
                        "filename": "tsm_repair.html",
                    },
                ],
            }
        },
        env={},
    )

    alias_only_message, filename_only_message = plan["messages"]
    assert alias_only_message["filename"] == "nvda_due_alias.html"
    assert alias_only_message["report_filename"] == "nvda_due_alias.html"
    assert filename_only_message["filename"] == "tsm_repair.html"
    assert filename_only_message["report_filename"] == "tsm_repair.html"


def test_notification_plan_normalizes_report_filename_when_truthiness_fails():
    class BrokenTruthFilename:
        def __bool__(self):
            raise RuntimeError("filename truthiness unavailable")

        def __str__(self):
            return "broken_report.html"

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "TSM 報告需人工審核",
                        "detail": "內容可信度未通過。",
                        "filename": BrokenTruthFilename(),
                    }
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    message = plan["messages"][0]
    expected = "notification_plan.v1|report_repair|manual_review|ticker|broken_report.html|v1"
    assert message["filename"] == "broken_report.html"
    assert message["report_filename"] == "broken_report.html"
    assert message["dedupe_key"] == expected
    assert all(entry["filename"] == "broken_report.html" for entry in plan["delivery_outbox"])
    assert all(entry["report_filename"] == "broken_report.html" for entry in plan["delivery_outbox"])


def test_notification_plan_preserves_context_when_value_comparison_fails():
    class BrokenComparisonMetadata:
        def __eq__(self, other):
            raise RuntimeError("context equality unavailable")

        def __str__(self):
            return "manual_review"

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "TSM 報告需人工審核",
                        "detail": "內容可信度未通過。",
                        "filename": "tsm_repair.html",
                        "recommended_action": BrokenComparisonMetadata(),
                    }
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    message = plan["messages"][0]
    assert str(message["recommended_action"]) == "manual_review"
    assert all(str(entry["recommended_action"]) == "manual_review" for entry in plan["delivery_outbox"])


def test_notification_plan_preserves_context_when_value_compares_equal_to_blank():
    class BlankComparableMetadata:
        def __eq__(self, other):
            return other == ""

        def __str__(self):
            return "manual_review"

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "TSM 報告需人工審核",
                        "detail": "內容可信度未通過。",
                        "filename": "tsm_repair.html",
                        "recommended_action": BlankComparableMetadata(),
                    }
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    message = plan["messages"][0]
    assert message["recommended_action"] == "manual_review"
    assert all(entry["recommended_action"] == "manual_review" for entry in plan["delivery_outbox"])


def test_notification_plan_ignores_malformed_suppress_notification_flag():
    class BrokenSuppressFlag:
        def __bool__(self):
            raise RuntimeError("suppress flag truthiness unavailable")

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "TSM 報告需人工審核",
                        "detail": "內容可信度未通過。",
                        "filename": "tsm_repair.html",
                        "suppress_notification": BrokenSuppressFlag(),
                    }
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    assert plan["messages"][0]["title"] == "TSM 報告需人工審核"
    assert len(plan["delivery_outbox"]) == 2


def test_notification_plan_suppression_flag_uses_explicit_bool_text_conversion():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "title": "追蹤清單待分析",
                        "detail": "1 檔待更新。",
                        "suppress_notification": "false",
                    },
                    {
                        "source": "provider_impact",
                        "type": "wait_provider_recovery",
                        "title": "Provider degraded",
                        "detail": "需要查看來源。",
                        "suppress_notification": b"false",
                    },
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "報告需審核",
                        "detail": "資料可信度不足。",
                        "suppress_notification": memoryview(b"true"),
                    },
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "明確壓掉通知",
                        "detail": "這筆只留在 queue。",
                        "suppress_notification": "true",
                    },
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "布林壓掉通知",
                        "detail": "這筆只留在 queue。",
                        "suppress_notification": True,
                    },
                ]
            }
        },
        env={},
    )

    assert [message["type"] for message in plan["messages"]] == [
        "run_watchlist",
        "wait_provider_recovery",
        "manual_review",
    ]
    assert [message["title"] for message in plan["messages"]] == [
        "追蹤清單待分析",
        "Provider degraded",
        "報告需審核",
    ]


def test_notification_plan_boolean_fields_reject_arbitrary_stringlike_tokens():
    class SyntheticBoolToken:
        def __str__(self):
            return "true"

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "未知 bool metadata",
                        "detail": "不可偽裝成阻擋。",
                        "blocks_auto_rerun": SyntheticBoolToken(),
                    },
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "title": "未知 suppress token",
                        "detail": "不可偽裝成壓制通知。",
                        "suppress_notification": SyntheticBoolToken(),
                    },
                ]
            }
        },
        env={},
    )

    assert [message["title"] for message in plan["messages"]] == [
        "未知 bool metadata",
        "未知 suppress token",
    ]
    assert plan["messages"][0]["blocks_auto_rerun"] is False
    assert plan["delivery_outbox"][0]["blocks_auto_rerun"] is False


def test_notification_plan_adds_operator_target_metadata():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {"total_actionable": 3, "displayed_count": 3},
                "items": [
                    {
                        "source": "provider_impact",
                        "type": "wait_provider_recovery",
                        "priority_score": 900,
                        "title": "NVDA provider 影響需處理",
                        "detail": "market_data/yfinance critical",
                    },
                    {
                        "source": "model_route_budget",
                        "type": "model_route_warning",
                        "priority_score": 650,
                        "title": "v2/gemini-2.5-pro 模型路由需檢查",
                        "detail": "retry_count=7",
                    },
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "priority_score": 560,
                        "title": "2 檔 watchlist 待分析",
                        "detail": "2308.TW、2454.TW",
                    },
                ],
            }
        },
        env={},
    )

    provider_message, route_message, watchlist_message = plan["messages"]
    assert provider_message["target_panel"] == "provider-sla-panel"
    assert provider_message["target_tab"] == "ops"
    assert route_message["target_panel"] == "api-quota-panel"
    assert route_message["target_tab"] == "ops"
    assert watchlist_message["target_panel"] == "watchlist-panel"
    assert watchlist_message["target_tab"] == "tracking"


def test_notification_plan_preserves_target_metadata_when_truthiness_fails():
    class BrokenTruthTarget:
        def __bool__(self):
            raise RuntimeError("target panel truthiness unavailable")

        def __str__(self):
            return "custom-panel"

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "TSM 報告需人工審核",
                        "detail": "內容可信度未通過。",
                        "target_panel": BrokenTruthTarget(),
                        "target_tab": "custom-tab",
                    }
                ]
            }
        },
        env={},
    )

    message = plan["messages"][0]
    assert message["target_panel"] == "custom-panel"
    assert message["target_tab"] == "custom-tab"


def test_notification_plan_trims_action_type_before_default_cta_target_lookup():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "provider_impact",
                        "type": " \t wait_provider_recovery \n",
                        "title": "Provider degraded",
                        "detail": "需要查看資料來源。",
                    }
                ]
            }
        },
        env={},
    )

    message = plan["messages"][0]
    assert message["type"] == "wait_provider_recovery"
    assert message["operator_action"] == "open-ops"
    assert message["operator_action_label"] == "查看來源"
    assert message["target_panel"] == "provider-sla-panel"
    assert message["target_tab"] == "ops"
    assert plan["delivery_outbox"][0]["target_panel"] == "provider-sla-panel"


def test_notification_plan_preserves_message_envelope_when_truthiness_fails():
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("message envelope truthiness unavailable")

        def __str__(self):
            return self.value

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "report_repair",
                        "type": BrokenTruthText("manual_review"),
                        "title": BrokenTruthText("TSM 報告需人工審核"),
                        "detail": BrokenTruthText("內容可信度未通過。"),
                        "filename": "2330_manual_review.html",
                    }
                ]
            }
        },
        env={},
    )

    message = plan["messages"][0]
    assert message["type"] == "manual_review"
    assert message["title"] == "TSM 報告需人工審核"
    assert message["detail"] == "內容可信度未通過。"


def test_notification_plan_message_envelope_rejects_binary_and_boolean_text():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "watchlist",
                        "type": True,
                        "title": b"decoded title should not leak",
                        "detail": memoryview(b"decoded detail should not leak"),
                    }
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    message = plan["messages"][0]
    assert message["type"] == "daily_status"
    assert message["title"] == "今日決策狀態"
    assert message["detail"] == ""
    assert plan["delivery_outbox"][0]["type"] == "daily_status"
    assert "detail" not in plan["delivery_outbox"][0]


def test_notification_plan_message_envelope_trims_blank_fields_before_fallbacks():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "watchlist",
                        "type": " \t ",
                        "title": "\n  ",
                        "detail": "  ",
                    }
                ]
            }
        },
        env={},
    )

    message = plan["messages"][0]
    assert message["type"] == "daily_status"
    assert message["title"] == "今日決策狀態"
    assert message["detail"] == ""
    assert plan["delivery_outbox"][0]["type"] == "daily_status"
    assert "detail" not in plan["delivery_outbox"][0]


def test_notification_plan_adds_operator_cta_metadata():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {"total_actionable": 3, "displayed_count": 3},
                "items": [
                    {
                        "source": "provider_impact",
                        "type": "wait_provider_recovery",
                        "priority_score": 900,
                        "title": "NVDA provider 影響需處理",
                        "detail": "market_data/yfinance critical",
                    },
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "priority_score": 560,
                        "title": "2 檔 watchlist 待分析",
                        "detail": "2308.TW、2454.TW",
                    },
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "priority_score": 1000,
                        "title": "2330.TW v2 內容可信度未通過",
                        "detail": "目標價與買入建議不一致。",
                        "filename": "2330_blocked.html",
                    },
                ],
            }
        },
        env={},
    )

    provider_message, watchlist_message, repair_message = plan["messages"]
    assert provider_message["operator_action"] == "open-ops"
    assert provider_message["operator_action_label"] == "查看來源"
    assert watchlist_message["operator_action"] == "run-watchlist"
    assert watchlist_message["operator_action_label"] == "建立/更新報告"
    assert repair_message["operator_action"] == "view-report"
    assert repair_message["operator_action_label"] == "查看報告"


def test_notification_plan_preserves_operator_cta_when_truthiness_fails():
    class BrokenTruthCta:
        def __bool__(self):
            raise RuntimeError("operator cta truthiness unavailable")

        def __str__(self):
            return "custom-action"

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "TSM 報告需人工審核",
                        "detail": "內容可信度未通過。",
                        "operator_action": BrokenTruthCta(),
                        "operator_action_label": "自訂處理",
                    }
                ]
            }
        },
        env={},
    )

    message = plan["messages"][0]
    assert message["operator_action"] == "custom-action"
    assert message["operator_action_label"] == "自訂處理"


def test_notification_plan_ignores_blank_custom_cta_and_target_metadata():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "report_repair",
                        "type": "manual_review",
                        "title": "TSM 報告需人工審核",
                        "detail": "內容可信度未通過。",
                        "operator_action": " \n ",
                        "operator_action_label": "\t ",
                        "target_panel": "  ",
                        "target_tab": "\r\n",
                    }
                ]
            }
        },
        env={},
    )

    message = plan["messages"][0]
    assert message["operator_action"] == "view-report"
    assert message["operator_action_label"] == "查看報告"
    assert message["target_panel"] == "active-jobs-panel"
    assert message["target_tab"] == "ops"
    assert plan["delivery_outbox"][0]["operator_action"] == "view-report"
    assert plan["delivery_outbox"][0]["operator_action_label"] == "查看報告"
    assert plan["delivery_outbox"][0]["target_panel"] == "active-jobs-panel"
    assert plan["delivery_outbox"][0]["target_tab"] == "ops"


def test_notification_plan_adds_queue_rank_metadata():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {"total_actionable": 3, "displayed_count": 3},
                "items": [
                    {
                        "source": "monitor",
                        "type": "monitor",
                        "priority_score": 0,
                        "title": "目前沒有急件",
                        "detail": "相容 fallback 不應進通知。",
                    },
                    {
                        "source": "provider_impact",
                        "type": "wait_provider_recovery",
                        "priority_score": 900,
                        "title": "NVDA provider 影響需處理",
                        "detail": "market_data/yfinance critical",
                    },
                    {
                        "source": "backtest_due",
                        "type": "backtest_due",
                        "priority_score": 763,
                        "title": "2308.TW 3M 回測到期",
                        "detail": "先完成到期回測。",
                    },
                ],
            }
        },
        env={},
    )

    assert [message["queue_rank"] for message in plan["messages"]] == [1, 2]
    assert [message["queue_displayed_count"] for message in plan["messages"]] == [2, 2]
    assert [message["is_top_priority"] for message in plan["messages"]] == [True, False]


def test_notification_plan_adds_stable_dedupe_keys():
    base_action = {
        "source": "provider_impact",
        "type": "wait_provider_recovery",
        "priority_score": 900,
        "title": "NVDA provider 影響需處理",
        "detail": "market_data/yfinance critical",
        "ticker": "NVDA",
        "filename": "nvda_provider.html",
        "pipeline_id": "v2",
    }
    changed_copy = {
        **base_action,
        "priority_score": 850,
        "title": "NVDA provider 還是需要處理",
        "detail": "文字可變，但識別應穩定。",
    }

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {"total_actionable": 3, "displayed_count": 3},
                "items": [
                    base_action,
                    {
                        "source": "model_route_budget",
                        "type": "model_route_warning",
                        "priority_score": 650,
                        "title": "v2/gemini-2.5-pro 模型路由需檢查",
                        "detail": "retry_count=7",
                        "route": "v2/gemini-2.5-pro",
                        "warning_id": "retry_storm",
                    },
                    {
                        "source": "backtest_due",
                        "type": "backtest_due",
                        "priority_score": 763,
                        "title": "2308.TW 3M 回測到期",
                        "detail": "先完成到期回測。",
                        "filename": "2308_due.html",
                        "pipeline_id": "v1",
                        "horizon_months": 3,
                    },
                ],
            }
        },
        env={},
    )
    changed_plan = build_daily_notification_plan(
        {"decision_queue": {"items": [changed_copy]}},
        env={},
    )

    provider_message, route_message, backtest_message = plan["messages"]
    assert provider_message["dedupe_key"] == "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2"
    assert provider_message["message_id"] == provider_message["dedupe_key"]
    assert changed_plan["messages"][0]["dedupe_key"] == provider_message["dedupe_key"]
    assert route_message["dedupe_key"] == "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm"
    assert backtest_message["dedupe_key"] == "notification_plan.v1|backtest_due|backtest_due|2308_due.html|3|v1"


def test_notification_plan_dedupe_identity_uses_fallback_for_malformed_values():
    class BrokenComparisonIdentity:
        def __bool__(self):
            return True

        def __eq__(self, other):
            raise RuntimeError("identity comparison unavailable")

        def __str__(self):
            return "Malformed title"

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "title": BrokenComparisonIdentity(),
                        "detail": "需要建立報告。",
                    }
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    assert plan["messages"][0]["title"] == "Malformed title"
    assert plan["messages"][0]["dedupe_key"] == "notification_plan.v1|watchlist|run_watchlist|untitled"
    assert plan["messages"][0]["message_id"] == plan["messages"][0]["dedupe_key"]
    assert all(entry["message_id"] == plan["messages"][0]["message_id"] for entry in plan["delivery_outbox"])


def test_notification_plan_ignores_malformed_dedupe_overrides():
    class BrokenStringOverride:
        def __bool__(self):
            return True

        def __str__(self):
            raise RuntimeError("dedupe override unavailable")

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "title": "追蹤清單待分析",
                        "detail": "需要建立報告。",
                        "dedupe_key": BrokenStringOverride(),
                        "message_id": BrokenStringOverride(),
                    }
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    expected = "notification_plan.v1|watchlist|run_watchlist|追蹤清單待分析"
    assert plan["messages"][0]["dedupe_key"] == expected
    assert plan["messages"][0]["message_id"] == expected
    assert all(entry["dedupe_key"] == expected for entry in plan["delivery_outbox"])
    assert all(entry["message_id"] == expected for entry in plan["delivery_outbox"])


def test_notification_plan_preserves_dedupe_override_when_value_compares_equal_to_blank():
    class BlankComparableIdentity:
        def __init__(self, value):
            self.value = value

        def __eq__(self, other):
            return other == ""

        def __str__(self):
            return self.value

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "watchlist",
                        "type": "run_watchlist",
                        "title": "追蹤清單待分析",
                        "detail": "需要建立報告。",
                        "dedupe_key": BlankComparableIdentity("custom-dedupe"),
                        "message_id": BlankComparableIdentity("custom-message"),
                    }
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    message = plan["messages"][0]
    assert message["dedupe_key"] == "custom-dedupe"
    assert message["message_id"] == "custom-message"
    assert all(entry["dedupe_key"] == "custom-dedupe" for entry in plan["delivery_outbox"])
    assert all(entry["message_id"] == "custom-message" for entry in plan["delivery_outbox"])
    assert all("custom-message" in entry["delivery_key"] for entry in plan["delivery_outbox"])


def test_notification_plan_builds_delivery_outbox_for_enabled_channels():
    action = {
        "source": "provider_impact",
        "type": "wait_provider_recovery",
        "priority_score": 900,
        "title": "NVDA provider 影響需處理",
        "detail": "market_data/yfinance critical",
        "ticker": "NVDA",
        "filename": "nvda_provider.html",
        "pipeline_id": "v2",
    }
    changed_action = {
        **action,
        "title": "NVDA provider 仍需處理",
        "detail": "文案改變不應改變 delivery identity。",
    }

    plan = build_daily_notification_plan(
        {"decision_queue": {"items": [action]}},
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )
    changed_plan = build_daily_notification_plan(
        {"decision_queue": {"items": [changed_action]}},
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    assert plan["delivery_summary"] == {
        "enabled_channel_count": 2,
        "message_count": 1,
        "pending_count": 2,
    }
    assert [entry["channel_id"] for entry in plan["delivery_outbox"]] == ["local", "telegram_webhook"]
    assert {entry["delivery_status"] for entry in plan["delivery_outbox"]} == {"pending"}
    assert {entry["attempt_count"] for entry in plan["delivery_outbox"]} == {0}
    assert all(entry["message_id"] == plan["messages"][0]["message_id"] for entry in plan["delivery_outbox"])
    assert all(entry["dedupe_key"] == plan["messages"][0]["dedupe_key"] for entry in plan["delivery_outbox"])
    assert all("email_smtp" not in entry["delivery_key"] for entry in plan["delivery_outbox"])
    assert changed_plan["delivery_outbox"][0]["delivery_key"] == plan["delivery_outbox"][0]["delivery_key"]


def test_notification_plan_delivery_outbox_preserves_report_context():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "backtest_due",
                        "type": "backtest_due",
                        "title": "NVDA 3M 回測到期",
                        "detail": "先完成到期回測。",
                        "ticker": "NVDA",
                        "report_filename": "nvda_due_alias.html",
                        "pipeline_id": "v2",
                        "horizon_months": 3,
                    }
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    for entry in plan["delivery_outbox"]:
        assert entry["source"] == "backtest_due"
        assert entry["type"] == "backtest_due"
        assert entry["ticker"] == "NVDA"
        assert entry["filename"] == "nvda_due_alias.html"
        assert entry["report_filename"] == "nvda_due_alias.html"
        assert entry["pipeline_id"] == "v2"


def test_notification_plan_delivery_outbox_preserves_operator_context():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "provider_impact",
                        "type": "wait_provider_recovery",
                        "priority_score": 900,
                        "title": "NVDA provider 影響需處理",
                        "detail": "market_data/yfinance critical",
                        "ticker": "NVDA",
                        "filename": "nvda_provider.html",
                        "pipeline_id": "v2",
                    }
                ]
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    for entry in plan["delivery_outbox"]:
        assert entry["priority_score"] == 900
        assert entry["target_panel"] == "provider-sla-panel"
        assert entry["target_tab"] == "ops"
        assert entry["operator_action"] == "open-ops"
        assert entry["operator_action_label"] == "查看來源"
        assert entry["source_label"] == "資料來源"
        assert entry["source_text"] == "資料來源 (provider_impact)"
        assert entry["queue_rank"] == 1
        assert entry["queue_displayed_count"] == 1
        assert entry["is_top_priority"] is True


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


def test_notification_plan_external_channels_reject_binary_and_boolean_env_values():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "provider_impact",
                        "type": "wait_provider_recovery",
                        "title": "Provider degraded",
                        "detail": "需要查看資料來源。",
                    }
                ]
            }
        },
        env={
            "SMTP_HOST": "smtp.example.test",
            "SMTP_TO": b"me@example.test",
            "TELEGRAM_BOT_TOKEN": True,
            "TELEGRAM_CHAT_ID": "chat",
            "DISCORD_WEBHOOK_URL": memoryview(b"https://discord.example/webhook"),
            "SLACK_WEBHOOK_URL": bytearray(b"https://hooks.slack.example/webhook"),
        },
    )

    channels = {channel["id"]: channel for channel in plan["channels"]}
    assert [channel["id"] for channel in plan["channels"] if channel["enabled"]] == ["local"]
    assert channels["email_smtp"]["missing_env"] == ["SMTP_TO"]
    assert channels["telegram_webhook"]["missing_env"] == ["TELEGRAM_BOT_TOKEN"]
    assert channels["discord_webhook"]["missing_env"] == ["DISCORD_WEBHOOK_URL"]
    assert channels["slack_webhook"]["missing_env"] == ["SLACK_WEBHOOK_URL"]
    assert plan["delivery_summary"]["enabled_channel_count"] == 1
    assert [entry["channel_id"] for entry in plan["delivery_outbox"]] == ["local"]


def test_notification_plan_external_channels_reject_arbitrary_stringlike_env_values():
    class SyntheticEnvValue:
        def __str__(self):
            return "token"

    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "provider_impact",
                        "type": "wait_provider_recovery",
                        "title": "Provider degraded",
                        "detail": "需要查看資料來源。",
                    }
                ]
            }
        },
        env={
            "SMTP_HOST": "smtp.example.test",
            "SMTP_TO": SyntheticEnvValue(),
            "TELEGRAM_BOT_TOKEN": SyntheticEnvValue(),
            "TELEGRAM_CHAT_ID": "chat",
            "DISCORD_WEBHOOK_URL": SyntheticEnvValue(),
            "SLACK_WEBHOOK_URL": SyntheticEnvValue(),
        },
    )

    channels = {channel["id"]: channel for channel in plan["channels"]}
    assert [channel["id"] for channel in plan["channels"] if channel["enabled"]] == ["local"]
    assert channels["email_smtp"]["missing_env"] == ["SMTP_TO"]
    assert channels["telegram_webhook"]["missing_env"] == ["TELEGRAM_BOT_TOKEN"]
    assert channels["discord_webhook"]["missing_env"] == ["DISCORD_WEBHOOK_URL"]
    assert channels["slack_webhook"]["missing_env"] == ["SLACK_WEBHOOK_URL"]
    assert plan["delivery_summary"]["enabled_channel_count"] == 1
    assert [entry["channel_id"] for entry in plan["delivery_outbox"]] == ["local"]


def test_notification_plan_external_channels_treat_malformed_env_as_missing():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "items": [
                    {
                        "source": "provider_impact",
                        "type": "wait_provider_recovery",
                        "title": "Provider degraded",
                        "detail": "需要查看資料來源。",
                    }
                ]
            }
        },
        env=object(),
    )

    channels = {channel["id"]: channel for channel in plan["channels"]}
    assert [channel["id"] for channel in plan["channels"] if channel["enabled"]] == ["local"]
    assert channels["email_smtp"]["missing_env"] == ["SMTP_HOST", "SMTP_TO"]
    assert channels["telegram_webhook"]["missing_env"] == ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    assert channels["discord_webhook"]["missing_env"] == ["DISCORD_WEBHOOK_URL"]
    assert channels["slack_webhook"]["missing_env"] == ["SLACK_WEBHOOK_URL"]
    assert plan["delivery_summary"]["enabled_channel_count"] == 1
    assert [entry["channel_id"] for entry in plan["delivery_outbox"]] == ["local"]


def test_notification_plan_keeps_monitor_only_dashboard_quiet():
    plan = build_daily_notification_plan(
        {"actions": [{"type": "monitor", "title": "目前沒有急件", "detail": "保持每日追蹤。"}]},
        env={},
    )

    assert plan["status"] == "quiet"
    assert plan["messages"] == []


def test_notification_plan_suppresses_padded_monitor_type_before_message_filtering():
    plan = build_daily_notification_plan(
        {"actions": [{"type": " \t monitor \n", "title": "目前沒有急件", "detail": "保持每日追蹤。"}]},
        env={},
    )

    assert plan["status"] == "quiet"
    assert plan["messages"] == []
    assert plan["delivery_outbox"] == []
    assert plan["queue_context"]["total_actionable"] == 0


def test_notification_plan_suppresses_notification_delivery_repair_actions():
    plan = build_daily_notification_plan(
        {
            "decision_queue": {
                "summary": {
                    "total_actionable": 1,
                    "displayed_count": 1,
                    "sources": {"notification_delivery": 1},
                },
                "items": [
                    {
                        "source": "notification_delivery",
                        "type": "fix_notification_delivery",
                        "priority_score": 840,
                        "title": "外部通知通道需檢查",
                        "detail": "failed=2, exhausted=1",
                        "suppress_notification": True,
                    }
                ],
            }
        },
        env={"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
    )

    assert plan["status"] == "quiet"
    assert plan["messages"] == []
    assert plan["delivery_outbox"] == []
    assert plan["delivery_summary"]["message_count"] == 0
    assert plan["queue_context"]["sources"]["notification_delivery"] == 1
