import notification_delivery_audit as audit


def test_notification_delivery_audit_upserts_delivery_results(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    outbox_entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }

    failed = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="timeout",
        now=1_000.0,
    )
    sent = audit.record_delivery_attempt(
        outbox_entry,
        status="sent",
        response_id="telegram:123",
        now=1_010.0,
    )

    records = audit.list_delivery_records()

    assert failed["delivery_status"] == "failed"
    assert failed["attempt_count"] == 1
    assert sent["delivery_status"] == "sent"
    assert sent["attempt_count"] == 2
    assert len(records) == 1
    assert records[0] == {
        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
        "delivery_status": "sent",
        "attempt_count": 2,
        "first_seen_at": 1_000.0,
        "last_attempt_at": 1_010.0,
        "last_success_at": 1_010.0,
        "last_error": "",
        "last_response_id": "telegram:123",
        "context": {},
    }

    assert audit.get_delivery_audit_summary() == {
        "total_count": 1,
        "sent_count": 1,
        "failed_count": 0,
        "pending_count": 0,
        "retry_exhausted_count": 0,
        "channel_counts": {"telegram_webhook": 1},
        "failure_reason_counts": {},
        "attention_contexts": [],
    }


def test_notification_delivery_audit_preserves_outbox_context_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    outbox_entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
        "source": "provider_impact",
        "source_label": "資料來源",
        "source_text": "資料來源 (provider_impact)",
        "type": "wait_provider_recovery",
        "priority_score": 900,
        "ticker": "NVDA",
        "filename": "nvda_provider.html",
        "report_filename": "nvda_provider.html",
        "pipeline_id": "v2",
        "target_panel": "provider-sla-panel",
        "target_tab": "ops",
        "operator_action": "open-ops",
        "operator_action_label": "查看來源",
        "queue_rank": 1,
        "is_top_priority": True,
    }

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="temporary webhook timeout",
        now=1_500.0,
    )
    records = audit.list_delivery_records()

    assert saved["context"] == {
        "source": "provider_impact",
        "source_label": "資料來源",
        "source_text": "資料來源 (provider_impact)",
        "type": "wait_provider_recovery",
        "priority_score": 900,
        "ticker": "NVDA",
        "filename": "nvda_provider.html",
        "report_filename": "nvda_provider.html",
        "pipeline_id": "v2",
        "target_panel": "provider-sla-panel",
        "target_tab": "ops",
        "operator_action": "open-ops",
        "operator_action_label": "查看來源",
        "queue_rank": 1,
        "is_top_priority": True,
    }
    assert records[0]["context"] == saved["context"]


def test_notification_delivery_audit_reads_outbox_context_without_mapping_get_accessors(tmp_path, monkeypatch):
    class BrokenGetDict(dict):
        def get(self, *args, **kwargs):
            raise RuntimeError("audit context get accessor unavailable")

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    outbox_entry = BrokenGetDict({
        "delivery_key": "notification_delivery.v1|telegram_webhook|backtest-action",
        "channel_id": "telegram_webhook",
        "message_id": "backtest-action",
        "dedupe_key": "notification_plan.v1|backtest_due|backtest_due|nvda_due_alias.html|6|v2",
        "source": "backtest_due",
        "type": "backtest_due",
        "ticker": "NVDA",
        "filename": "nvda_due_alias.html",
        "report_filename": "nvda_due_alias.html",
        "pipeline_id": "v2",
        "target_panel": "performance-panel",
        "operator_action_label": "查看回測",
        "queue_rank": 1,
    })

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="temporary webhook timeout",
        now=1_600.0,
    )
    reconciled = audit.reconcile_outbox_with_audit(
        [outbox_entry],
        now=1_601.0,
        retry_backoff_seconds=0,
    )[0]

    expected_context = {
        "source": "backtest_due",
        "source_label": "決策回測",
        "source_text": "決策回測 (backtest_due)",
        "type": "backtest_due",
        "ticker": "NVDA",
        "filename": "nvda_due_alias.html",
        "report_filename": "nvda_due_alias.html",
        "pipeline_id": "v2",
        "target_panel": "performance-panel",
        "operator_action_label": "查看回測",
        "queue_rank": 1,
    }
    assert saved["context"] == expected_context
    assert reconciled["audit_status"] == "failed"
    assert reconciled["should_send"] is True
    assert reconciled["audit_context"] == expected_context


def test_notification_delivery_audit_ignores_blank_source_display_context(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    saved = audit.record_delivery_attempt(
        {
            "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
            "channel_id": "telegram_webhook",
            "message_id": "provider-action",
            "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
            "source": "provider_impact",
            "source_label": "   ",
            "source_text": "\t",
        },
        status="failed",
        error="temporary webhook timeout",
        now=1_750.0,
    )

    assert saved["context"]["source_label"] == "資料來源"
    assert saved["context"]["source_text"] == "資料來源 (provider_impact)"


def test_notification_delivery_audit_source_display_ignores_truthiness_failures(tmp_path, monkeypatch):
    class BrokenTruthDisplay:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("source display truthiness unavailable")

        def __str__(self):
            return self.value

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    saved = audit.record_delivery_attempt(
        {
            "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
            "channel_id": "telegram_webhook",
            "message_id": "provider-action",
            "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
            "source": "provider_impact",
            "source_label": BrokenTruthDisplay("外部來源"),
            "source_text": BrokenTruthDisplay("   "),
        },
        status="failed",
        error="temporary webhook timeout",
        now=1_800.0,
    )

    assert saved["context"]["source_label"] == "外部來源"
    assert saved["context"]["source_text"] == "資料來源 (provider_impact)"


def test_notification_delivery_audit_source_key_ignores_truthiness_failures(tmp_path, monkeypatch):
    class BrokenTruthSource:
        def __bool__(self):
            raise RuntimeError("source key truthiness unavailable")

        def __str__(self):
            return " provider_impact "

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    saved = audit.record_delivery_attempt(
        {
            "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
            "channel_id": "telegram_webhook",
            "message_id": "provider-action",
            "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
            "source": BrokenTruthSource(),
        },
        status="failed",
        error="temporary webhook timeout",
        now=1_850.0,
    )

    assert saved["context"]["source"] == "provider_impact"
    assert saved["context"]["source_label"] == "資料來源"
    assert saved["context"]["source_text"] == "資料來源 (provider_impact)"


def test_notification_delivery_audit_context_values_ignore_equality_failures(tmp_path, monkeypatch):
    class BrokenEqualityValue:
        def __init__(self, value):
            self.value = value

        def __eq__(self, other):
            raise RuntimeError("context value equality unavailable")

        def __str__(self):
            return self.value

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    saved = audit.record_delivery_attempt(
        {
            "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
            "channel_id": "telegram_webhook",
            "message_id": "provider-action",
            "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
            "source": "provider_impact",
            "ticker": BrokenEqualityValue("NVDA"),
        },
        status="failed",
        error="temporary webhook timeout",
        now=1_900.0,
    )

    assert saved["context"]["ticker"] == "NVDA"
    assert saved["context"]["source_text"] == "資料來源 (provider_impact)"


def test_notification_delivery_audit_attempt_result_ignores_truthiness_failures(tmp_path, monkeypatch):
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("attempt result truthiness unavailable")

        def __str__(self):
            return self.value

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    failed = audit.record_delivery_attempt(
        {
            "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
            "channel_id": "telegram_webhook",
            "message_id": "provider-action",
            "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
        },
        status=BrokenTruthText("failed"),
        error=BrokenTruthText("temporary webhook timeout"),
        response_id=BrokenTruthText("telegram:error-123"),
        now=1_950.0,
    )

    assert failed["delivery_status"] == "failed"
    assert failed["last_error"] == "temporary webhook timeout"
    assert failed["last_response_id"] == "telegram:error-123"


def test_notification_delivery_audit_outbox_identity_ignores_truthiness_failures(tmp_path, monkeypatch):
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("outbox identity truthiness unavailable")

        def __str__(self):
            return self.value

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    saved = audit.record_delivery_attempt(
        {
            "delivery_key": BrokenTruthText(" notification_delivery.v1|telegram_webhook|provider-action "),
            "channel_id": BrokenTruthText(" telegram_webhook "),
            "message_id": BrokenTruthText(" provider-action "),
            "dedupe_key": BrokenTruthText(" notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2 "),
        },
        status="failed",
        error="temporary webhook timeout",
        now=1_975.0,
    )

    assert saved["delivery_key"] == "notification_delivery.v1|telegram_webhook|provider-action"
    assert saved["channel_id"] == "telegram_webhook"
    assert saved["message_id"] == "provider-action"
    assert saved["dedupe_key"] == "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2"


def test_notification_delivery_audit_list_limit_ignores_truthiness_failures(tmp_path, monkeypatch):
    class BrokenTruthLimit:
        def __bool__(self):
            raise RuntimeError("list limit truthiness unavailable")

        def __int__(self):
            return 1

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    for index in range(2):
        audit.record_delivery_attempt(
            {
                "delivery_key": f"notification_delivery.v1|telegram_webhook|provider-action-{index}",
                "channel_id": "telegram_webhook",
                "message_id": f"provider-action-{index}",
                "dedupe_key": f"dedupe-{index}",
            },
            status="failed",
            error="temporary webhook timeout",
            now=2_000.0 + index,
        )

    records = audit.list_delivery_records(limit=BrokenTruthLimit())

    assert len(records) == 1
    assert records[0]["message_id"] == "provider-action-1"


def test_notification_delivery_audit_reconciles_outbox_before_send(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    sent_entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
        "delivery_status": "pending",
    }
    new_entry = {
        "delivery_key": "notification_delivery.v1|local|route-warning",
        "channel_id": "local",
        "message_id": "route-warning",
        "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
        "delivery_status": "pending",
    }
    audit.record_delivery_attempt(
        sent_entry,
        status="sent",
        response_id="telegram:123",
        now=2_000.0,
    )

    reconciled = audit.reconcile_outbox_with_audit([sent_entry, new_entry])

    assert reconciled[0]["delivery_key"] == sent_entry["delivery_key"]
    assert reconciled[0]["audit_status"] == "sent"
    assert reconciled[0]["audit_attempt_count"] == 1
    assert reconciled[0]["already_sent"] is True
    assert reconciled[0]["should_send"] is False
    assert reconciled[0]["last_response_id"] == "telegram:123"
    assert reconciled[1]["delivery_key"] == new_entry["delivery_key"]
    assert reconciled[1]["audit_status"] == "not_seen"
    assert reconciled[1]["audit_attempt_count"] == 0
    assert reconciled[1]["already_sent"] is False
    assert reconciled[1]["should_send"] is True


def test_notification_delivery_audit_reconcile_delivery_key_ignores_truthiness_failures(tmp_path, monkeypatch):
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("reconcile delivery key truthiness unavailable")

        def __str__(self):
            return self.value

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    audit.record_delivery_attempt(
        {
            "delivery_key": delivery_key,
            "channel_id": "telegram_webhook",
            "message_id": "provider-action",
            "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
        },
        status="sent",
        response_id="telegram:123",
        now=2_100.0,
    )

    reconciled = audit.reconcile_outbox_with_audit(
        [
            {
                "delivery_key": BrokenTruthText(f" {delivery_key} "),
                "channel_id": "telegram_webhook",
                "message_id": "provider-action",
                "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
            }
        ]
    )

    assert reconciled[0]["audit_status"] == "sent"
    assert reconciled[0]["already_sent"] is True
    assert reconciled[0]["should_send"] is False
    assert reconciled[0]["last_response_id"] == "telegram:123"


def test_notification_delivery_audit_reconcile_attempt_count_ignores_truthiness_failures(monkeypatch):
    class BrokenTruthNumber:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("reconcile attempt count truthiness unavailable")

        def __int__(self):
            return self.value

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    monkeypatch.setattr(
        audit,
        "_records_by_delivery_key",
        lambda _keys: {
            delivery_key: {
                "delivery_key": delivery_key,
                "channel_id": "telegram_webhook",
                "message_id": "provider-action",
                "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
                "delivery_status": "failed",
                "attempt_count": BrokenTruthNumber(2),
                "last_attempt_at": 2_100.0,
                "last_success_at": None,
                "last_error": "temporary webhook timeout",
                "last_response_id": "",
                "context": {},
            }
        },
    )

    reconciled = audit.reconcile_outbox_with_audit(
        [
            {
                "delivery_key": delivery_key,
                "channel_id": "telegram_webhook",
                "message_id": "provider-action",
                "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
            }
        ],
        max_attempts=3,
        now=2_101.0,
        retry_backoff_seconds=0,
    )[0]

    assert reconciled["audit_status"] == "failed"
    assert reconciled["audit_attempt_count"] == 2
    assert reconciled["retry_exhausted"] is False
    assert reconciled["should_send"] is True
    assert reconciled["next_attempt_count"] == 3


def test_notification_delivery_audit_reconcile_status_ignores_truthiness_failures(monkeypatch):
    class BrokenTruthStatus:
        def __bool__(self):
            raise RuntimeError("reconcile status truthiness unavailable")

        def __str__(self):
            return "failed"

    delivery_key = "notification_delivery.v1|telegram_webhook|route-warning"
    monkeypatch.setattr(
        audit,
        "_records_by_delivery_key",
        lambda _keys: {
            delivery_key: {
                "delivery_key": delivery_key,
                "channel_id": "telegram_webhook",
                "message_id": "route-warning",
                "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
                "delivery_status": BrokenTruthStatus(),
                "attempt_count": 1,
                "last_attempt_at": 5_000.0,
                "last_success_at": None,
                "last_error": "temporary webhook timeout",
                "last_response_id": "",
                "context": {},
            }
        },
    )

    reconciled = audit.reconcile_outbox_with_audit(
        [
            {
                "delivery_key": delivery_key,
                "channel_id": "telegram_webhook",
                "message_id": "route-warning",
                "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
            }
        ],
        now=5_100.0,
        retry_backoff_seconds=300,
    )[0]

    assert reconciled["audit_status"] == "failed"
    assert reconciled["retry_wait_seconds"] == 200
    assert reconciled["skip_reason"] == "retry_wait"
    assert reconciled["should_send"] is False


def test_notification_delivery_audit_reconcile_text_metadata_ignores_truthiness_failures(monkeypatch):
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("reconcile text metadata truthiness unavailable")

        def __str__(self):
            return self.value

    delivery_key = "notification_delivery.v1|telegram_webhook|route-warning"
    monkeypatch.setattr(
        audit,
        "_records_by_delivery_key",
        lambda _keys: {
            delivery_key: {
                "delivery_key": delivery_key,
                "channel_id": "telegram_webhook",
                "message_id": "route-warning",
                "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
                "delivery_status": "failed",
                "attempt_count": 1,
                "last_attempt_at": 5_000.0,
                "last_success_at": None,
                "last_error": BrokenTruthText("temporary webhook timeout"),
                "last_response_id": BrokenTruthText("telegram:error-123"),
                "context": {},
            }
        },
    )

    reconciled = audit.reconcile_outbox_with_audit(
        [
            {
                "delivery_key": delivery_key,
                "channel_id": "telegram_webhook",
                "message_id": "route-warning",
                "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
            }
        ],
        now=5_100.0,
        retry_backoff_seconds=0,
    )[0]

    assert reconciled["last_error"] == "temporary webhook timeout"
    assert reconciled["last_response_id"] == "telegram:error-123"


def test_notification_delivery_audit_reconcile_context_ignores_truthiness_failures(monkeypatch):
    class BrokenTruthContext(dict):
        def __bool__(self):
            raise RuntimeError("reconcile context truthiness unavailable")

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    monkeypatch.setattr(
        audit,
        "_records_by_delivery_key",
        lambda _keys: {
            delivery_key: {
                "delivery_key": delivery_key,
                "channel_id": "telegram_webhook",
                "message_id": "provider-action",
                "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
                "delivery_status": "failed",
                "attempt_count": 1,
                "last_attempt_at": 2_500.0,
                "last_success_at": None,
                "last_error": "timeout",
                "last_response_id": "",
                "context": BrokenTruthContext({"source": "provider_impact", "ticker": "NVDA"}),
            }
        },
    )

    reconciled = audit.reconcile_outbox_with_audit(
        [
            {
                "delivery_key": delivery_key,
                "channel_id": "telegram_webhook",
                "message_id": "provider-action",
                "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
            }
        ],
        now=2_501.0,
        retry_backoff_seconds=0,
    )[0]

    assert reconciled["audit_context"] == {"source": "provider_impact", "ticker": "NVDA"}


def test_notification_delivery_audit_reconcile_exposes_context_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    rich_entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
        "source": "provider_impact",
        "type": "wait_provider_recovery",
        "ticker": "NVDA",
        "filename": "nvda_provider.html",
        "target_panel": "provider-sla-panel",
        "operator_action": "open-ops",
        "queue_rank": 1,
    }
    minimal_entry = {
        "delivery_key": rich_entry["delivery_key"],
        "channel_id": rich_entry["channel_id"],
        "message_id": rich_entry["message_id"],
        "dedupe_key": rich_entry["dedupe_key"],
        "delivery_status": "pending",
    }
    audit.record_delivery_attempt(rich_entry, status="failed", error="timeout", now=2_500.0)

    reconciled = audit.reconcile_outbox_with_audit(
        [minimal_entry],
        now=2_501.0,
        retry_backoff_seconds=0,
    )[0]

    assert reconciled["audit_status"] == "failed"
    assert reconciled["should_send"] is True
    assert reconciled["audit_context"] == {
        "source": "provider_impact",
        "source_label": "資料來源",
        "source_text": "資料來源 (provider_impact)",
        "type": "wait_provider_recovery",
        "ticker": "NVDA",
        "filename": "nvda_provider.html",
        "target_panel": "provider-sla-panel",
        "operator_action": "open-ops",
        "queue_rank": 1,
    }


def test_notification_delivery_audit_stops_retry_after_budget_exhausted(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    failed_entry = {
        "delivery_key": "notification_delivery.v1|discord_webhook|provider-action",
        "channel_id": "discord_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
        "delivery_status": "pending",
    }
    retryable_entry = {
        "delivery_key": "notification_delivery.v1|slack_webhook|route-warning",
        "channel_id": "slack_webhook",
        "message_id": "route-warning",
        "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
        "delivery_status": "pending",
    }
    for attempt in range(3):
        audit.record_delivery_attempt(
            failed_entry,
            status="failed",
            error=f"timeout-{attempt}",
            now=3_000.0 + attempt,
        )
    audit.record_delivery_attempt(
        retryable_entry,
        status="failed",
        error="temporary",
        now=4_000.0,
    )

    exhausted, retryable = audit.reconcile_outbox_with_audit([failed_entry, retryable_entry])

    assert exhausted["audit_status"] == "failed"
    assert exhausted["audit_attempt_count"] == 3
    assert exhausted["retry_exhausted"] is True
    assert exhausted["should_send"] is False
    assert exhausted["skip_reason"] == "retry_exhausted"
    assert exhausted["next_attempt_count"] == 4
    assert retryable["retry_exhausted"] is False
    assert retryable["should_send"] is True
    assert retryable["next_attempt_count"] == 2
    assert audit.get_delivery_audit_summary()["retry_exhausted_count"] == 1


def test_notification_delivery_audit_waits_for_retry_backoff_before_resend(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    failed_entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|route-warning",
        "channel_id": "telegram_webhook",
        "message_id": "route-warning",
        "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
        "delivery_status": "pending",
    }
    audit.record_delivery_attempt(
        failed_entry,
        status="failed",
        error="temporary webhook timeout",
        now=5_000.0,
    )

    waiting = audit.reconcile_outbox_with_audit(
        [failed_entry],
        now=5_100.0,
        retry_backoff_seconds=300,
    )[0]
    ready = audit.reconcile_outbox_with_audit(
        [failed_entry],
        now=5_301.0,
        retry_backoff_seconds=300,
    )[0]

    assert waiting["audit_status"] == "failed"
    assert waiting["audit_attempt_count"] == 1
    assert waiting["retry_exhausted"] is False
    assert waiting["should_send"] is False
    assert waiting["skip_reason"] == "retry_wait"
    assert waiting["retry_wait_seconds"] == 200
    assert waiting["next_retry_at"] == 5_300.0
    assert ready["should_send"] is True
    assert ready["skip_reason"] == ""
    assert ready["retry_wait_seconds"] == 0
    assert ready["next_retry_at"] == 5_300.0
    assert ready["next_attempt_count"] == 2


def test_notification_delivery_audit_reconcile_last_attempt_at_ignores_truthiness_failures(monkeypatch):
    class BrokenTruthFloat:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("reconcile last attempt truthiness unavailable")

        def __float__(self):
            return self.value

    delivery_key = "notification_delivery.v1|telegram_webhook|route-warning"
    monkeypatch.setattr(
        audit,
        "_records_by_delivery_key",
        lambda _keys: {
            delivery_key: {
                "delivery_key": delivery_key,
                "channel_id": "telegram_webhook",
                "message_id": "route-warning",
                "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
                "delivery_status": "failed",
                "attempt_count": 1,
                "last_attempt_at": BrokenTruthFloat(5_000.0),
                "last_success_at": None,
                "last_error": "temporary webhook timeout",
                "last_response_id": "",
                "context": {},
            }
        },
    )

    reconciled = audit.reconcile_outbox_with_audit(
        [
            {
                "delivery_key": delivery_key,
                "channel_id": "telegram_webhook",
                "message_id": "route-warning",
                "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
            }
        ],
        now=5_100.0,
        retry_backoff_seconds=300,
    )[0]

    assert reconciled["audit_status"] == "failed"
    assert reconciled["next_retry_at"] == 5_300.0
    assert reconciled["retry_wait_seconds"] == 200
    assert reconciled["skip_reason"] == "retry_wait"
    assert reconciled["should_send"] is False


def test_notification_delivery_audit_summarizes_failure_reason_buckets(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    failures = [
        ("timeout", "telegram_webhook", "temporary webhook timeout"),
        ("auth", "slack_webhook", "HTTP 403 invalid token"),
        ("rate_limited", "discord_webhook", "429 rate limit exceeded"),
        ("configuration", "smtp", "missing SMTP env configuration"),
        ("network", "telegram_webhook", "DNS connection refused"),
        ("other", "local", "unexpected sender crash"),
    ]
    for index, (_reason, channel, error) in enumerate(failures):
        audit.record_delivery_attempt(
            {
                "delivery_key": f"notification_delivery.v1|{channel}|msg-{index}",
                "channel_id": channel,
                "message_id": f"msg-{index}",
                "dedupe_key": f"dedupe-{index}",
            },
            status="failed",
            error=error,
            now=6_000.0 + index,
        )

    summary = audit.get_delivery_audit_summary()

    assert summary["failure_reason_counts"] == {
        "auth": 1,
        "configuration": 1,
        "network": 1,
        "other": 1,
        "rate_limited": 1,
        "timeout": 1,
    }


def test_notification_delivery_audit_failure_reason_ignores_error_truthiness_failures(monkeypatch):
    class BrokenTruthError:
        def __bool__(self):
            raise RuntimeError("failure reason truthiness unavailable")

        def __str__(self):
            return "temporary webhook timeout"

    monkeypatch.setattr(
        audit,
        "list_delivery_records",
        lambda limit=1000: [
            {
                "delivery_key": "notification_delivery.v1|telegram_webhook|timeout-action",
                "channel_id": "telegram_webhook",
                "message_id": "timeout-action",
                "dedupe_key": "dedupe-timeout",
                "delivery_status": "failed",
                "attempt_count": 1,
                "last_error": BrokenTruthError(),
                "context": {},
            }
        ],
    )

    summary = audit.get_delivery_audit_summary()

    assert summary["failure_reason_counts"] == {"timeout": 1}


def test_notification_delivery_audit_summary_channel_counts_ignore_channel_truthiness_failures(monkeypatch):
    class BrokenTruthChannel:
        def __bool__(self):
            raise RuntimeError("summary channel truthiness unavailable")

        def __str__(self):
            return "telegram_webhook"

    monkeypatch.setattr(
        audit,
        "list_delivery_records",
        lambda limit=1000: [
            {
                "delivery_key": "notification_delivery.v1|telegram_webhook|sent-action",
                "channel_id": BrokenTruthChannel(),
                "message_id": "sent-action",
                "dedupe_key": "dedupe-sent",
                "delivery_status": "sent",
                "attempt_count": 1,
                "last_error": "",
                "context": {},
            }
        ],
    )

    summary = audit.get_delivery_audit_summary()

    assert summary["channel_counts"] == {"telegram_webhook": 1}


def test_notification_delivery_audit_summary_status_counts_ignore_status_equality_failures(monkeypatch):
    class BrokenEqualityStatus:
        def __eq__(self, _other):
            raise RuntimeError("summary status equality unavailable")

        def __str__(self):
            return "failed"

    monkeypatch.setattr(
        audit,
        "list_delivery_records",
        lambda limit=1000: [
            {
                "delivery_key": "notification_delivery.v1|telegram_webhook|failed-action",
                "channel_id": "telegram_webhook",
                "message_id": "failed-action",
                "dedupe_key": "dedupe-failed",
                "delivery_status": BrokenEqualityStatus(),
                "attempt_count": 1,
                "last_error": "temporary webhook timeout",
                "context": {},
            }
        ],
    )

    summary = audit.get_delivery_audit_summary()

    assert summary["failed_count"] == 1
    assert summary["failure_reason_counts"] == {"timeout": 1}


def test_notification_delivery_audit_summary_includes_attention_contexts(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    audit.record_delivery_attempt(
        {
            "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
            "channel_id": "telegram_webhook",
            "message_id": "provider-action",
            "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
            "source": "provider_impact",
            "type": "wait_provider_recovery",
            "ticker": "NVDA",
            "filename": "nvda_provider.html",
            "target_panel": "provider-sla-panel",
            "operator_action_label": "查看來源",
            "queue_rank": 1,
        },
        status="failed",
        error="temporary webhook timeout",
        now=7_000.0,
    )
    audit.record_delivery_attempt(
        {
            "delivery_key": "notification_delivery.v1|local|sent-action",
            "channel_id": "local",
            "message_id": "sent-action",
            "dedupe_key": "sent-action",
            "source": "watchlist",
            "ticker": "TSM",
        },
        status="sent",
        now=7_001.0,
    )

    summary = audit.get_delivery_audit_summary()

    assert summary["attention_contexts"] == [
        {
            "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
            "channel_id": "telegram_webhook",
            "delivery_status": "failed",
            "attempt_count": 1,
            "last_error": "temporary webhook timeout",
            "context": {
                "source": "provider_impact",
                "source_label": "資料來源",
                "source_text": "資料來源 (provider_impact)",
                "type": "wait_provider_recovery",
                "ticker": "NVDA",
                "filename": "nvda_provider.html",
                "target_panel": "provider-sla-panel",
                "operator_action_label": "查看來源",
                "queue_rank": 1,
            },
        }
    ]


def test_notification_delivery_audit_attention_contexts_ignore_record_truthiness_failures():
    class BrokenTruthText:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("attention context truthiness unavailable")

        def __str__(self):
            return self.value

    class BrokenTruthNumber:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            raise RuntimeError("attention count truthiness unavailable")

        def __int__(self):
            return self.value

    class BrokenTruthContext(dict):
        def __bool__(self):
            raise RuntimeError("attention context snapshot truthiness unavailable")

    records = [
        {
            "delivery_key": BrokenTruthText("delivery-1"),
            "channel_id": BrokenTruthText("telegram_webhook"),
            "delivery_status": BrokenTruthText("failed"),
            "attempt_count": BrokenTruthNumber(2),
            "last_error": BrokenTruthText("temporary webhook timeout"),
            "context": BrokenTruthContext({"source": "provider_impact"}),
        }
    ]

    assert audit.attention_contexts_from_records(records, limit=BrokenTruthNumber(2)) == [
        {
            "delivery_key": "delivery-1",
            "channel_id": "telegram_webhook",
            "delivery_status": "failed",
            "attempt_count": 2,
            "last_error": "temporary webhook timeout",
            "context": {"source": "provider_impact"},
        }
    ]
