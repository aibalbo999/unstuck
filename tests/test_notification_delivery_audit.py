from collections.abc import Mapping
import json
import sqlite3
from types import MappingProxyType

import notification_delivery_audit as audit
import pytest


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


def test_notification_delivery_audit_preserves_reason_codes_before_string_failures(tmp_path, monkeypatch):
    class BrokenReasonCode:
        def __str__(self):
            raise RuntimeError("delivery audit reason code string unavailable")

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    saved = audit.record_delivery_attempt(
        {
            "delivery_key": "notification_delivery.v1|telegram_webhook|repair-action",
            "channel_id": "telegram_webhook",
            "message_id": "repair-action",
            "dedupe_key": "notification_plan.v1|report_repair|manual_review|NVDA|nvda_invalid_snapshot.html|v2",
            "source": "report_repair",
            "type": "manual_review",
            "filename": "nvda_invalid_snapshot.html",
            "reason_codes": ["data_snapshot_integrity_invalid", BrokenReasonCode()],
        },
        status="failed",
        error="temporary webhook timeout",
        now=1_550.0,
    )

    assert saved["context"]["reason_codes"] == ["data_snapshot_integrity_invalid"]


def test_notification_delivery_audit_context_preserves_native_items_when_items_accessor_fails(tmp_path, monkeypatch):
    class BrokenItemsOutbox(dict):
        def items(self):
            raise RuntimeError("audit context items accessor unavailable")

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    outbox_entry = BrokenItemsOutbox({
        "delivery_key": "notification_delivery.v1|telegram_webhook|repair-action",
        "channel_id": "telegram_webhook",
        "message_id": "repair-action",
        "dedupe_key": "notification_plan.v1|report_repair|manual_review|NVDA|nvda_invalid_snapshot.html|v2",
        "source": "report_repair",
        "type": "manual_review",
        "ticker": "NVDA",
        "filename": "nvda_invalid_snapshot.html",
        "reason_codes": ["data_snapshot_integrity_invalid"],
        "queue_rank": 1,
    })

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="temporary webhook timeout",
        now=1_575.0,
    )

    assert saved["context"]["source"] == "report_repair"
    assert saved["context"]["ticker"] == "NVDA"
    assert saved["context"]["reason_codes"] == ["data_snapshot_integrity_invalid"]
    assert saved["context"]["queue_rank"] == 1


def test_notification_delivery_audit_context_ignores_non_string_metadata_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    outbox_entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|repair-action",
        "channel_id": "telegram_webhook",
        "message_id": "repair-action",
        "dedupe_key": "notification_plan.v1|report_repair|manual_review|NVDA|nvda_invalid_snapshot.html|v2",
        "source": "report_repair",
        "type": "manual_review",
        "ticker": "NVDA",
        "filename": "nvda_invalid_snapshot.html",
        "reason_codes": ["data_snapshot_integrity_invalid"],
        7: "numeric metadata key should not be persisted",
    }

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="temporary webhook timeout",
        now=1_585.0,
    )

    assert saved["context"]["source"] == "report_repair"
    assert saved["context"]["ticker"] == "NVDA"
    assert saved["context"]["reason_codes"] == ["data_snapshot_integrity_invalid"]
    assert 7 not in saved["context"]
    assert "7" not in saved["context"]


def test_notification_delivery_audit_context_preserves_mapping_metadata_values(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    saved = audit.record_delivery_attempt(
        {
            "delivery_key": "notification_delivery.v1|telegram_webhook|repair-action",
            "channel_id": "telegram_webhook",
            "message_id": "repair-action",
            "dedupe_key": "notification_plan.v1|report_repair|manual_review|NVDA|nvda_invalid_snapshot.html|v2",
            "source": "report_repair",
            "type": "manual_review",
            "ticker": "NVDA",
            "filename": "nvda_invalid_snapshot.html",
            "nested": MappingProxyType({"queue_rank": 1, "empty": ""}),
        },
        status="failed",
        error="temporary webhook timeout",
        now=1_590.0,
    )

    assert saved["context"]["nested"] == {"queue_rank": 1}


def test_notification_delivery_audit_context_ignores_unstringable_metadata_values(tmp_path, monkeypatch):
    class BrokenMetadataValue:
        def __str__(self):
            raise RuntimeError("audit context metadata value string unavailable")

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    outbox_entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|repair-action",
        "channel_id": "telegram_webhook",
        "message_id": "repair-action",
        "dedupe_key": "notification_plan.v1|report_repair|manual_review|NVDA|nvda_invalid_snapshot.html|v2",
        "source": "report_repair",
        "type": "manual_review",
        "ticker": "NVDA",
        "filename": "nvda_invalid_snapshot.html",
        "reason_codes": ["data_snapshot_integrity_invalid"],
        "operator_action_label": BrokenMetadataValue(),
    }

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="temporary webhook timeout",
        now=1_590.0,
    )

    assert saved["context"]["source"] == "report_repair"
    assert saved["context"]["ticker"] == "NVDA"
    assert saved["context"]["reason_codes"] == ["data_snapshot_integrity_invalid"]
    assert "operator_action_label" not in saved["context"]


def test_notification_delivery_audit_context_preserves_native_sequence_metadata_when_iterator_fails(
    tmp_path, monkeypatch
):
    class BrokenSequenceMetadata(list):
        def __iter__(self):
            raise RuntimeError("audit context metadata sequence iterator unavailable")

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    outbox_entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|repair-action",
        "channel_id": "telegram_webhook",
        "message_id": "repair-action",
        "dedupe_key": "notification_plan.v1|report_repair|manual_review|NVDA|nvda_invalid_snapshot.html|v2",
        "source": "report_repair",
        "type": "manual_review",
        "ticker": "NVDA",
        "filename": "nvda_invalid_snapshot.html",
        "reason_codes": ["data_snapshot_integrity_invalid"],
        "related_reports": BrokenSequenceMetadata(["nvda_invalid_snapshot.html"]),
    }

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="temporary webhook timeout",
        now=1_595.0,
    )

    assert saved["context"]["related_reports"] == ["nvda_invalid_snapshot.html"]
    assert saved["context"]["reason_codes"] == ["data_snapshot_integrity_invalid"]
    assert saved["context"]["ticker"] == "NVDA"


def test_notification_delivery_audit_context_preserves_partial_sequence_metadata_when_native_backing_is_empty(
    tmp_path, monkeypatch
):
    class PartialBrokenSequenceMetadataIterator:
        def __init__(self, first_item):
            self._first_item = first_item
            self._step = 0

        def __iter__(self):
            return self

        def __next__(self):
            self._step += 1
            if self._step == 1:
                return self._first_item
            raise RuntimeError("audit context metadata sequence stopped early")

    class PartialBrokenSequenceMetadata(list):
        def __init__(self, first_item):
            super().__init__()
            self._first_item = first_item

        def __iter__(self):
            return PartialBrokenSequenceMetadataIterator(self._first_item)

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    outbox_entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|repair-action",
        "channel_id": "telegram_webhook",
        "message_id": "repair-action",
        "dedupe_key": "notification_plan.v1|report_repair|manual_review|NVDA|nvda_invalid_snapshot.html|v2",
        "source": "report_repair",
        "type": "manual_review",
        "ticker": "NVDA",
        "filename": "nvda_invalid_snapshot.html",
        "reason_codes": ["data_snapshot_integrity_invalid"],
        "related_reports": PartialBrokenSequenceMetadata("nvda_invalid_snapshot.html"),
    }

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="temporary webhook timeout",
        now=1_596.0,
    )

    assert saved["context"]["related_reports"] == ["nvda_invalid_snapshot.html"]
    assert saved["context"]["reason_codes"] == ["data_snapshot_integrity_invalid"]
    assert saved["context"]["ticker"] == "NVDA"


def test_notification_delivery_audit_context_drops_non_finite_numeric_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    outbox_entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|repair-action",
        "channel_id": "telegram_webhook",
        "message_id": "repair-action",
        "dedupe_key": "notification_plan.v1|report_repair|manual_review|NVDA|nvda_invalid_snapshot.html|v2",
        "source": "report_repair",
        "type": "manual_review",
        "ticker": "NVDA",
        "filename": "nvda_invalid_snapshot.html",
        "reason_codes": ["data_snapshot_integrity_invalid"],
        "priority_score": float("nan"),
        "score_history": [float("inf"), 820.0],
        "numeric_context": {"route_score": float("-inf"), "queue_rank": 1},
    }

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="temporary webhook timeout",
        now=1_596.0,
    )

    assert "priority_score" not in saved["context"]
    assert saved["context"]["score_history"] == [820.0]
    assert saved["context"]["numeric_context"] == {"queue_rank": 1}
    assert saved["context"]["reason_codes"] == ["data_snapshot_integrity_invalid"]
    json.dumps(saved["context"], allow_nan=False)


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


def test_notification_delivery_audit_context_drops_whitespace_only_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    saved = audit.record_delivery_attempt(
        {
            "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
            "channel_id": "telegram_webhook",
            "message_id": "provider-action",
            "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
            "source": "provider_impact",
            "ticker": "   ",
            "filename": "\t",
            "related_reports": ["nvda_provider.html", "  "],
            "metadata": {"operator_action_label": "\n", "queue_rank": 1},
        },
        status="failed",
        error="temporary webhook timeout",
        now=1_925.0,
    )

    assert "ticker" not in saved["context"]
    assert "filename" not in saved["context"]
    assert saved["context"]["related_reports"] == ["nvda_provider.html"]
    assert saved["context"]["metadata"] == {"queue_rank": 1}
    assert saved["context"]["source_text"] == "資料來源 (provider_impact)"


def test_notification_delivery_audit_context_drops_empty_collections_after_normalization(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    saved = audit.record_delivery_attempt(
        {
            "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
            "channel_id": "telegram_webhook",
            "message_id": "provider-action",
            "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
            "source": "provider_impact",
            "related_reports": ["  "],
            "metadata": {"operator_action_label": "\t"},
            "nested_items": [{"cta": "\n"}],
        },
        status="failed",
        error="temporary webhook timeout",
        now=1_930.0,
    )

    assert "related_reports" not in saved["context"]
    assert "metadata" not in saved["context"]
    assert "nested_items" not in saved["context"]
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


def test_notification_delivery_audit_record_accepts_mapping_outbox_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    outbox_entry = MappingProxyType(
        {
            "delivery_key": "notification_delivery.v1|telegram_webhook|provider-action",
            "channel_id": "telegram_webhook",
            "message_id": "provider-action",
            "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
            "source": "provider_impact",
            "ticker": "NVDA",
            "report_filename": "nvda_provider.html",
        }
    )

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="temporary webhook timeout",
        now=1_985.0,
    )

    assert saved["delivery_key"] == outbox_entry["delivery_key"]
    assert saved["delivery_status"] == "failed"
    assert saved["context"]["source"] == "provider_impact"
    assert saved["context"]["ticker"] == "NVDA"


def test_notification_delivery_audit_record_rejects_malformed_mapping_outbox_entries_with_required_identity_error(tmp_path, monkeypatch):
    class BrokenMapping(Mapping):
        def __getitem__(self, key):
            raise RuntimeError("record outbox mapping item unavailable")

        def __iter__(self):
            raise RuntimeError("record outbox mapping iterator unavailable")

        def __len__(self):
            return 1

    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    with pytest.raises(ValueError, match="delivery_key is required"):
        audit.record_delivery_attempt(
            BrokenMapping(),
            status="failed",
            error="temporary webhook timeout",
            now=1_986.0,
        )


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


def test_notification_delivery_audit_list_limit_clamps_explicit_zero_to_one(tmp_path, monkeypatch):
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
            now=2_010.0 + index,
        )

    records = audit.list_delivery_records(limit=0)

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


def test_notification_delivery_audit_reconcile_treats_missing_outbox_entries_as_empty():
    assert audit.reconcile_outbox_with_audit(None) == []


def test_notification_delivery_audit_reconcile_accepts_tuple_outbox_entries():
    outbox_entry = {
        "delivery_key": "notification_delivery.v1|local|route-warning",
        "channel_id": "local",
        "message_id": "route-warning",
        "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
        "delivery_status": "pending",
    }

    reconciled = audit.reconcile_outbox_with_audit((outbox_entry,))

    assert reconciled[0]["delivery_key"] == outbox_entry["delivery_key"]
    assert reconciled[0]["audit_status"] == "not_seen"
    assert reconciled[0]["should_send"] is True


def test_notification_delivery_audit_reconcile_accepts_mapping_outbox_entries():
    outbox_entry = MappingProxyType(
        {
            "delivery_key": "notification_delivery.v1|local|route-warning",
            "channel_id": "local",
            "message_id": "route-warning",
            "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
            "delivery_status": "pending",
        }
    )

    reconciled = audit.reconcile_outbox_with_audit([outbox_entry])

    assert reconciled[0]["delivery_key"] == outbox_entry["delivery_key"]
    assert reconciled[0]["audit_status"] == "not_seen"
    assert reconciled[0]["should_send"] is True


def test_notification_delivery_audit_reconcile_skips_malformed_mapping_outbox_entries():
    class BrokenMapping(Mapping):
        def __getitem__(self, key):
            raise RuntimeError("outbox mapping item unavailable")

        def __iter__(self):
            raise RuntimeError("outbox mapping iterator unavailable")

        def __len__(self):
            return 1

    valid_entry = {
        "delivery_key": "notification_delivery.v1|local|route-warning",
        "channel_id": "local",
        "message_id": "route-warning",
        "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
        "delivery_status": "pending",
    }

    reconciled = audit.reconcile_outbox_with_audit([BrokenMapping(), valid_entry])

    assert [entry["delivery_key"] for entry in reconciled] == [valid_entry["delivery_key"]]
    assert reconciled[0]["audit_status"] == "not_seen"
    assert reconciled[0]["should_send"] is True


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


def test_notification_delivery_audit_reconcile_matches_blob_stored_delivery_key(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    sent_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    audit.record_delivery_attempt(
        sent_entry,
        status="sent",
        response_id="telegram:123",
        now=2_200.0,
    )
    with audit._connect() as conn:
        conn.execute(
            """
            UPDATE notification_delivery_audit
            SET delivery_key = ?
            WHERE delivery_key = ?
            """,
            (sqlite3.Binary(delivery_key.encode("utf-8")), delivery_key),
        )

    reconciled = audit.reconcile_outbox_with_audit([sent_entry])[0]

    assert reconciled["audit_status"] == "sent"
    assert reconciled["already_sent"] is True
    assert reconciled["should_send"] is False
    assert reconciled["last_response_id"] == "telegram:123"


def test_notification_delivery_audit_reconcile_matches_trimmed_stored_delivery_key(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    sent_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    audit.record_delivery_attempt(
        sent_entry,
        status="sent",
        response_id="telegram:123",
        now=2_205.0,
    )
    with audit._connect() as conn:
        conn.execute(
            """
            UPDATE notification_delivery_audit
            SET delivery_key = ?
            WHERE delivery_key = ?
            """,
            (f" {delivery_key} ", delivery_key),
        )

    reconciled = audit.reconcile_outbox_with_audit([sent_entry])[0]

    assert reconciled["audit_status"] == "sent"
    assert reconciled["already_sent"] is True
    assert reconciled["should_send"] is False
    assert reconciled["last_response_id"] == "telegram:123"


def test_notification_delivery_audit_reconcile_matches_control_whitespace_stored_delivery_key(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    sent_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    audit.record_delivery_attempt(
        sent_entry,
        status="sent",
        response_id="telegram:123",
        now=2_206.0,
    )
    with audit._connect() as conn:
        conn.execute(
            """
            UPDATE notification_delivery_audit
            SET delivery_key = ?
            WHERE delivery_key = ?
            """,
            (f"\t{delivery_key}\n", delivery_key),
        )

    reconciled = audit.reconcile_outbox_with_audit([sent_entry])[0]

    assert reconciled["audit_status"] == "sent"
    assert reconciled["already_sent"] is True
    assert reconciled["should_send"] is False
    assert reconciled["last_response_id"] == "telegram:123"


def test_notification_delivery_audit_record_updates_blob_stored_delivery_key(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    outbox_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="temporary webhook timeout",
        now=2_250.0,
    )
    with audit._connect() as conn:
        conn.execute(
            """
            UPDATE notification_delivery_audit
            SET delivery_key = ?
            WHERE delivery_key = ?
            """,
            (sqlite3.Binary(delivery_key.encode("utf-8")), delivery_key),
        )

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="sent",
        response_id="telegram:123",
        now=2_260.0,
    )
    records = audit.list_delivery_records()

    assert len(records) == 1
    assert saved["delivery_status"] == "sent"
    assert saved["attempt_count"] == 2
    assert saved["last_response_id"] == "telegram:123"
    assert records[0]["delivery_key"] == delivery_key


def test_notification_delivery_audit_record_updates_trimmed_stored_delivery_key(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    outbox_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="temporary webhook timeout",
        now=2_265.0,
    )
    with audit._connect() as conn:
        conn.execute(
            """
            UPDATE notification_delivery_audit
            SET delivery_key = ?
            WHERE delivery_key = ?
            """,
            (f" {delivery_key} ", delivery_key),
        )

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="sent",
        response_id="telegram:123",
        now=2_270.0,
    )
    records = audit.list_delivery_records()

    assert len(records) == 1
    assert saved["delivery_status"] == "sent"
    assert saved["attempt_count"] == 2
    assert saved["last_response_id"] == "telegram:123"
    assert records[0]["delivery_key"].strip() == delivery_key


def test_notification_delivery_audit_record_updates_control_whitespace_stored_delivery_key(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    outbox_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="temporary webhook timeout",
        now=2_275.0,
    )
    with audit._connect() as conn:
        conn.execute(
            """
            UPDATE notification_delivery_audit
            SET delivery_key = ?
            WHERE delivery_key = ?
            """,
            (f"\t{delivery_key}\n", delivery_key),
        )

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="sent",
        response_id="telegram:123",
        now=2_280.0,
    )
    records = audit.list_delivery_records()

    assert len(records) == 1
    assert saved["delivery_status"] == "sent"
    assert saved["attempt_count"] == 2
    assert saved["last_response_id"] == "telegram:123"
    assert records[0]["delivery_key"].strip() == delivery_key


def test_notification_delivery_audit_record_output_strips_control_whitespace_delivery_key(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    outbox_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="temporary webhook timeout",
        now=2_285.0,
    )
    with audit._connect() as conn:
        conn.execute(
            """
            UPDATE notification_delivery_audit
            SET delivery_key = ?
            WHERE delivery_key = ?
            """,
            (f"\t{delivery_key}\n", delivery_key),
        )

    records = audit.list_delivery_records()

    assert records[0]["delivery_key"] == delivery_key


def test_notification_delivery_audit_reconcile_prefers_sent_duplicate_decoded_delivery_key(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    outbox_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    with audit._connect() as conn:
        conn.execute(
            """
            INSERT INTO notification_delivery_audit (
                delivery_key, channel_id, message_id, dedupe_key, delivery_status,
                attempt_count, first_seen_at, last_attempt_at, last_success_at,
                last_error, last_response_id, context_json
            )
            VALUES (?, ?, ?, ?, 'sent', 1, 2300.0, 2300.0, 2300.0, '', 'telegram:sent', '{}')
            """,
            (delivery_key, "telegram_webhook", "provider-action", outbox_entry["dedupe_key"]),
        )
        conn.execute(
            """
            INSERT INTO notification_delivery_audit (
                delivery_key, channel_id, message_id, dedupe_key, delivery_status,
                attempt_count, first_seen_at, last_attempt_at, last_success_at,
                last_error, last_response_id, context_json
            )
            VALUES (?, ?, ?, ?, 'failed', 2, 2310.0, 2310.0, NULL, 'temporary webhook timeout', '', '{}')
            """,
            (
                sqlite3.Binary(delivery_key.encode("utf-8")),
                "telegram_webhook",
                "provider-action",
                outbox_entry["dedupe_key"],
            ),
        )

    reconciled = audit.reconcile_outbox_with_audit(
        [outbox_entry],
        now=2_320.0,
        retry_backoff_seconds=0,
    )[0]

    assert reconciled["audit_status"] == "sent"
    assert reconciled["already_sent"] is True
    assert reconciled["should_send"] is False
    assert reconciled["last_response_id"] == "telegram:sent"


def test_notification_delivery_audit_reconcile_prefers_blob_sent_status_duplicate_key(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    outbox_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    with audit._connect() as conn:
        conn.execute(
            """
            INSERT INTO notification_delivery_audit (
                delivery_key, channel_id, message_id, dedupe_key, delivery_status,
                attempt_count, first_seen_at, last_attempt_at, last_success_at,
                last_error, last_response_id, context_json
            )
            VALUES (?, ?, ?, ?, 'failed', 2, 2400.0, 2400.0, NULL, 'temporary webhook timeout', '', '{}')
            """,
            (delivery_key, "telegram_webhook", "provider-action", outbox_entry["dedupe_key"]),
        )
        conn.execute(
            """
            INSERT INTO notification_delivery_audit (
                delivery_key, channel_id, message_id, dedupe_key, delivery_status,
                attempt_count, first_seen_at, last_attempt_at, last_success_at,
                last_error, last_response_id, context_json
            )
            VALUES (?, ?, ?, ?, ?, 1, 2390.0, 2390.0, 2390.0, '', 'telegram:sent', '{}')
            """,
            (
                sqlite3.Binary(delivery_key.encode("utf-8")),
                "telegram_webhook",
                "provider-action",
                outbox_entry["dedupe_key"],
                sqlite3.Binary(b"sent"),
            ),
        )

    reconciled = audit.reconcile_outbox_with_audit(
        [outbox_entry],
        now=2_410.0,
        retry_backoff_seconds=0,
    )[0]

    assert reconciled["audit_status"] == "sent"
    assert reconciled["already_sent"] is True
    assert reconciled["should_send"] is False
    assert reconciled["last_response_id"] == "telegram:sent"


def test_notification_delivery_audit_reconcile_prefers_normalized_sent_status_duplicate_key(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    outbox_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    with audit._connect() as conn:
        conn.execute(
            """
            INSERT INTO notification_delivery_audit (
                delivery_key, channel_id, message_id, dedupe_key, delivery_status,
                attempt_count, first_seen_at, last_attempt_at, last_success_at,
                last_error, last_response_id, context_json
            )
            VALUES (?, ?, ?, ?, 'failed', 2, 2420.0, 2420.0, NULL, 'temporary webhook timeout', '', '{}')
            """,
            (delivery_key, "telegram_webhook", "provider-action", outbox_entry["dedupe_key"]),
        )
        conn.execute(
            """
            INSERT INTO notification_delivery_audit (
                delivery_key, channel_id, message_id, dedupe_key, delivery_status,
                attempt_count, first_seen_at, last_attempt_at, last_success_at,
                last_error, last_response_id, context_json
            )
            VALUES (?, ?, ?, ?, ?, 1, 2410.0, 2410.0, 2410.0, '', 'telegram:sent', '{}')
            """,
            (
                sqlite3.Binary(delivery_key.encode("utf-8")),
                "telegram_webhook",
                "provider-action",
                outbox_entry["dedupe_key"],
                "\tSENT\n",
            ),
        )

    reconciled = audit.reconcile_outbox_with_audit(
        [outbox_entry],
        now=2_430.0,
        retry_backoff_seconds=0,
    )[0]

    assert reconciled["audit_status"] == "sent"
    assert reconciled["already_sent"] is True
    assert reconciled["should_send"] is False
    assert reconciled["last_response_id"] == "telegram:sent"


def test_notification_delivery_audit_record_preserves_sent_duplicate_key_status(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    outbox_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    with audit._connect() as conn:
        conn.execute(
            """
            INSERT INTO notification_delivery_audit (
                delivery_key, channel_id, message_id, dedupe_key, delivery_status,
                attempt_count, first_seen_at, last_attempt_at, last_success_at,
                last_error, last_response_id, context_json
            )
            VALUES (?, ?, ?, ?, 'sent', 1, 2500.0, 2500.0, 2500.0, '', 'telegram:sent', '{}')
            """,
            (delivery_key, "telegram_webhook", "provider-action", outbox_entry["dedupe_key"]),
        )
        conn.execute(
            """
            INSERT INTO notification_delivery_audit (
                delivery_key, channel_id, message_id, dedupe_key, delivery_status,
                attempt_count, first_seen_at, last_attempt_at, last_success_at,
                last_error, last_response_id, context_json
            )
            VALUES (?, ?, ?, ?, 'failed', 2, 2510.0, 2510.0, NULL, 'temporary webhook timeout', '', '{}')
            """,
            (
                sqlite3.Binary(delivery_key.encode("utf-8")),
                "telegram_webhook",
                "provider-action",
                outbox_entry["dedupe_key"],
            ),
        )

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="late duplicate failure",
        now=2_520.0,
    )
    reconciled = audit.reconcile_outbox_with_audit(
        [outbox_entry],
        now=2_530.0,
        retry_backoff_seconds=0,
    )[0]

    assert saved["delivery_status"] == "sent"
    assert saved["last_response_id"] == "telegram:sent"
    assert reconciled["audit_status"] == "sent"
    assert reconciled["already_sent"] is True
    assert reconciled["should_send"] is False


def test_notification_delivery_audit_record_preserves_normalized_sent_duplicate_key_status(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    outbox_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    audit.record_delivery_attempt(
        outbox_entry,
        status="sent",
        response_id="telegram:sent",
        now=2_540.0,
    )
    with audit._connect() as conn:
        conn.execute(
            """
            UPDATE notification_delivery_audit
            SET delivery_status = ?
            WHERE delivery_key = ?
            """,
            ("\tSENT\n", delivery_key),
        )

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="late duplicate failure",
        response_id="telegram:error",
        now=2_550.0,
    )
    records = audit.list_delivery_records()

    assert saved["delivery_status"] == "sent"
    assert saved["last_error"] == ""
    assert saved["last_response_id"] == "telegram:sent"
    assert records[0]["delivery_status"] == "sent"
    assert records[0]["last_error"] == ""
    assert records[0]["last_response_id"] == "telegram:sent"


def test_notification_delivery_audit_record_preserves_sent_duplicate_key_last_error(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    outbox_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    audit.record_delivery_attempt(
        outbox_entry,
        status="sent",
        response_id="telegram:sent",
        now=2_600.0,
    )

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="late duplicate failure",
        now=2_610.0,
    )
    records = audit.list_delivery_records()

    assert saved["delivery_status"] == "sent"
    assert saved["last_error"] == ""
    assert saved["last_response_id"] == "telegram:sent"
    assert records[0]["delivery_status"] == "sent"
    assert records[0]["last_error"] == ""


def test_notification_delivery_audit_record_preserves_sent_duplicate_key_response_id(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    outbox_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    audit.record_delivery_attempt(
        outbox_entry,
        status="sent",
        response_id="telegram:sent",
        now=2_700.0,
    )

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="failed",
        error="late duplicate failure",
        response_id="telegram:error-123",
        now=2_710.0,
    )
    records = audit.list_delivery_records()

    assert saved["delivery_status"] == "sent"
    assert saved["last_response_id"] == "telegram:sent"
    assert records[0]["delivery_status"] == "sent"
    assert records[0]["last_response_id"] == "telegram:sent"


def test_notification_delivery_audit_record_preserves_sent_duplicate_key_context(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    sent_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
        "source": "provider_impact",
        "ticker": "NVDA",
        "filename": "nvda_provider.html",
        "operator_action_label": "查看來源",
    }
    failed_entry = {
        **sent_entry,
        "source": "report_repair",
        "ticker": "TSMC",
        "filename": "tsmc_repair.html",
        "operator_action_label": "人工複檢",
    }
    audit.record_delivery_attempt(
        sent_entry,
        status="sent",
        response_id="telegram:sent",
        now=2_800.0,
    )

    saved = audit.record_delivery_attempt(
        failed_entry,
        status="failed",
        error="late duplicate failure",
        response_id="telegram:error-123",
        now=2_810.0,
    )
    records = audit.list_delivery_records()

    assert saved["delivery_status"] == "sent"
    assert saved["context"]["source"] == "provider_impact"
    assert saved["context"]["ticker"] == "NVDA"
    assert saved["context"]["filename"] == "nvda_provider.html"
    assert saved["context"]["operator_action_label"] == "查看來源"
    assert records[0]["delivery_status"] == "sent"
    assert records[0]["context"]["source"] == "provider_impact"
    assert records[0]["context"]["ticker"] == "NVDA"
    assert records[0]["context"]["filename"] == "nvda_provider.html"
    assert records[0]["context"]["operator_action_label"] == "查看來源"


def test_notification_delivery_audit_record_preserves_sent_duplicate_key_identity_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    delivery_key = "notification_delivery.v1|telegram_webhook|provider-action"
    sent_entry = {
        "delivery_key": delivery_key,
        "channel_id": "telegram_webhook",
        "message_id": "provider-action",
        "dedupe_key": "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2",
    }
    failed_entry = {
        **sent_entry,
        "channel_id": "local",
        "message_id": "repair-action",
        "dedupe_key": "notification_plan.v1|report_repair|repair_report|TSMC|tsmc_repair.html|v2",
    }
    audit.record_delivery_attempt(
        sent_entry,
        status="sent",
        response_id="telegram:sent",
        now=2_900.0,
    )

    saved = audit.record_delivery_attempt(
        failed_entry,
        status="failed",
        error="late duplicate failure",
        response_id="telegram:error-123",
        now=2_910.0,
    )
    records = audit.list_delivery_records()

    assert saved["delivery_status"] == "sent"
    assert saved["channel_id"] == "telegram_webhook"
    assert saved["message_id"] == "provider-action"
    assert saved["dedupe_key"] == "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2"
    assert records[0]["delivery_status"] == "sent"
    assert records[0]["channel_id"] == "telegram_webhook"
    assert records[0]["message_id"] == "provider-action"
    assert records[0]["dedupe_key"] == "notification_plan.v1|provider_impact|wait_provider_recovery|NVDA|nvda_provider.html|v2"


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


def test_notification_delivery_audit_reconcile_normalizes_statuses_before_decisions(monkeypatch):
    sent_key = "notification_delivery.v1|telegram_webhook|sent-action"
    failed_key = "notification_delivery.v1|telegram_webhook|failed-action"
    monkeypatch.setattr(
        audit,
        "_records_by_delivery_key",
        lambda _keys: {
            sent_key: {
                "delivery_key": sent_key,
                "channel_id": "telegram_webhook",
                "message_id": "sent-action",
                "dedupe_key": "dedupe-sent",
                "delivery_status": "\tSENT\n",
                "attempt_count": 1,
                "last_attempt_at": 4_900.0,
                "last_success_at": 4_900.0,
                "last_error": "",
                "last_response_id": "telegram:sent",
                "context": {},
            },
            failed_key: {
                "delivery_key": failed_key,
                "channel_id": "telegram_webhook",
                "message_id": "failed-action",
                "dedupe_key": "dedupe-failed",
                "delivery_status": "\rFAILED\n",
                "attempt_count": 1,
                "last_attempt_at": 5_000.0,
                "last_success_at": None,
                "last_error": "temporary webhook timeout",
                "last_response_id": "",
                "context": {},
            },
        },
    )

    sent, failed = audit.reconcile_outbox_with_audit(
        [
            {
                "delivery_key": sent_key,
                "channel_id": "telegram_webhook",
                "message_id": "sent-action",
                "dedupe_key": "dedupe-sent",
            },
            {
                "delivery_key": failed_key,
                "channel_id": "telegram_webhook",
                "message_id": "failed-action",
                "dedupe_key": "dedupe-failed",
            },
        ],
        now=5_100.0,
        retry_backoff_seconds=300,
    )

    assert sent["audit_status"] == "sent"
    assert sent["already_sent"] is True
    assert sent["should_send"] is False
    assert sent["skip_reason"] == "already_sent"
    assert failed["audit_status"] == "failed"
    assert failed["retry_wait_seconds"] == 200
    assert failed["skip_reason"] == "retry_wait"
    assert failed["should_send"] is False


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


def test_notification_delivery_audit_strips_response_ids_before_output(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    outbox_entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|sent-action",
        "channel_id": "telegram_webhook",
        "message_id": "sent-action",
        "dedupe_key": "dedupe-sent",
    }

    saved = audit.record_delivery_attempt(
        outbox_entry,
        status="sent",
        response_id="\ttelegram:sent\n",
        now=5_000.0,
    )
    records = audit.list_delivery_records()
    reconciled = audit.reconcile_outbox_with_audit([outbox_entry], now=5_100.0)[0]

    assert saved["last_response_id"] == "telegram:sent"
    assert records[0]["last_response_id"] == "telegram:sent"
    assert reconciled["last_response_id"] == "telegram:sent"


def test_notification_delivery_audit_reconcile_normalizes_non_finite_last_success_at(monkeypatch):
    delivery_key = "notification_delivery.v1|telegram_webhook|sent-action"
    monkeypatch.setattr(
        audit,
        "_records_by_delivery_key",
        lambda _keys: {
            delivery_key: {
                "delivery_key": delivery_key,
                "channel_id": "telegram_webhook",
                "message_id": "sent-action",
                "dedupe_key": "dedupe-sent",
                "delivery_status": "sent",
                "attempt_count": 1,
                "last_attempt_at": 5_000.0,
                "last_success_at": float("inf"),
                "last_error": "",
                "last_response_id": "telegram:sent",
                "context": {},
            }
        },
    )

    reconciled = audit.reconcile_outbox_with_audit(
        [
            {
                "delivery_key": delivery_key,
                "channel_id": "telegram_webhook",
                "message_id": "sent-action",
                "dedupe_key": "dedupe-sent",
            }
        ],
        now=5_100.0,
        retry_backoff_seconds=300,
    )[0]

    assert reconciled["last_success_at"] == 0.0
    json.dumps(reconciled, allow_nan=False)


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


def test_notification_delivery_audit_reconcile_context_drops_non_finite_values(monkeypatch):
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
                "context": {
                    "source": "provider_impact",
                    "ticker": "NVDA",
                    "bad_score": float("inf"),
                    "nested": {"queue_rank": 1, "bad_wait": float("nan")},
                },
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

    assert reconciled["audit_context"] == {
        "source": "provider_impact",
        "ticker": "NVDA",
        "nested": {"queue_rank": 1},
    }
    json.dumps(reconciled, allow_nan=False)


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


def test_notification_delivery_audit_reconcile_uses_default_retry_budget_when_max_attempts_is_none(
    tmp_path, monkeypatch
):
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

    reconciled = audit.reconcile_outbox_with_audit(
        [failed_entry],
        max_attempts=None,
        now=5_301.0,
        retry_backoff_seconds=300,
    )[0]

    assert reconciled["audit_status"] == "failed"
    assert reconciled["audit_attempt_count"] == 1
    assert reconciled["retry_exhausted"] is False
    assert reconciled["should_send"] is True
    assert reconciled["skip_reason"] == ""
    assert reconciled["next_attempt_count"] == 2


def test_notification_delivery_audit_reconcile_uses_default_backoff_when_backoff_is_none(tmp_path, monkeypatch):
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

    reconciled = audit.reconcile_outbox_with_audit(
        [failed_entry],
        now=5_100.0,
        retry_backoff_seconds=None,
    )[0]

    assert reconciled["audit_status"] == "failed"
    assert reconciled["retry_exhausted"] is False
    assert reconciled["should_send"] is False
    assert reconciled["skip_reason"] == "retry_wait"
    assert reconciled["retry_wait_seconds"] == 800
    assert reconciled["next_retry_at"] == 5_900.0


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


def test_notification_delivery_audit_reconcile_treats_non_finite_retry_backoff_as_zero(tmp_path, monkeypatch):
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

    reconciled = audit.reconcile_outbox_with_audit(
        [failed_entry],
        now=5_100.0,
        retry_backoff_seconds=float("inf"),
    )[0]

    assert reconciled["audit_status"] == "failed"
    assert reconciled["should_send"] is True
    assert reconciled["skip_reason"] == ""
    assert reconciled["retry_wait_seconds"] == 0
    assert reconciled["next_retry_at"] == 5_000.0


def test_notification_delivery_audit_reconcile_uses_current_time_when_now_is_non_finite(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    monkeypatch.setattr(audit.time, "time", lambda: 5_100.0)
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

    reconciled = audit.reconcile_outbox_with_audit(
        [failed_entry],
        now=float("inf"),
        retry_backoff_seconds=300,
    )[0]

    assert reconciled["audit_status"] == "failed"
    assert reconciled["should_send"] is False
    assert reconciled["skip_reason"] == "retry_wait"
    assert reconciled["retry_wait_seconds"] == 200
    assert reconciled["next_retry_at"] == 5_300.0


def test_notification_delivery_audit_records_normalize_non_finite_stored_timestamps(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|route-warning",
        "channel_id": "telegram_webhook",
        "message_id": "route-warning",
        "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
        "delivery_status": "pending",
    }
    audit.record_delivery_attempt(
        entry,
        status="sent",
        response_id="telegram:sent-1",
        now=5_000.0,
    )
    with audit._connect() as conn:
        conn.execute(
            """
            UPDATE notification_delivery_audit
            SET first_seen_at = ?,
                last_attempt_at = ?,
                last_success_at = ?
            WHERE delivery_key = ?
            """,
            (float("inf"), float("-inf"), float("inf"), entry["delivery_key"]),
        )

    record = audit.list_delivery_records()[0]

    assert record["first_seen_at"] == 0.0
    assert record["last_attempt_at"] == 0.0
    assert record["last_success_at"] == 0.0


def test_notification_delivery_audit_records_normalize_blob_text_fields_before_output(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|route-warning",
        "channel_id": "telegram_webhook",
        "message_id": "route-warning",
        "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
        "delivery_status": "pending",
    }
    audit.record_delivery_attempt(
        entry,
        status="failed",
        error="temporary webhook timeout",
        now=5_000.0,
    )
    with audit._connect() as conn:
        conn.execute(
            """
            UPDATE notification_delivery_audit
            SET channel_id = ?,
                message_id = ?,
                dedupe_key = ?,
                delivery_status = ?,
                last_error = ?,
                last_response_id = ?
            WHERE delivery_key = ?
            """,
            (
                sqlite3.Binary(b"telegram_webhook"),
                sqlite3.Binary(b"route-warning"),
                sqlite3.Binary(b"dedupe-key"),
                sqlite3.Binary(b"failed"),
                sqlite3.Binary(b"temporary webhook timeout"),
                sqlite3.Binary(b"telegram:error-1"),
                entry["delivery_key"],
            ),
        )

    record = audit.list_delivery_records()[0]

    assert record["channel_id"] == "telegram_webhook"
    assert record["message_id"] == "route-warning"
    assert record["dedupe_key"] == "dedupe-key"
    assert record["delivery_status"] == "failed"
    assert record["last_error"] == "temporary webhook timeout"
    assert record["last_response_id"] == "telegram:error-1"


def test_notification_delivery_audit_records_normalize_status_before_output(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|route-warning",
        "channel_id": "telegram_webhook",
        "message_id": "route-warning",
        "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
        "delivery_status": "pending",
    }
    audit.record_delivery_attempt(
        entry,
        status="failed",
        error="temporary webhook timeout",
        now=5_005.0,
    )
    with audit._connect() as conn:
        conn.execute(
            """
            UPDATE notification_delivery_audit
            SET delivery_status = ?
            WHERE delivery_key = ?
            """,
            ("\tFAILED\n", entry["delivery_key"]),
        )

    record = audit.list_delivery_records()[0]

    assert record["delivery_status"] == "failed"


def test_notification_delivery_audit_records_strip_identity_fields_before_output(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|route-warning",
        "channel_id": "telegram_webhook",
        "message_id": "route-warning",
        "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
        "delivery_status": "pending",
    }
    audit.record_delivery_attempt(
        entry,
        status="failed",
        error="temporary webhook timeout",
        now=5_010.0,
    )
    with audit._connect() as conn:
        conn.execute(
            """
            UPDATE notification_delivery_audit
            SET channel_id = ?,
                message_id = ?,
                dedupe_key = ?
            WHERE delivery_key = ?
            """,
            (
                "\ttelegram_webhook\n",
                " route-warning ",
                "\tnotification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm\n",
                entry["delivery_key"],
            ),
        )

    record = audit.list_delivery_records()[0]

    assert record["channel_id"] == "telegram_webhook"
    assert record["message_id"] == "route-warning"
    assert record["dedupe_key"] == "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm"


def test_notification_delivery_audit_records_normalize_bad_attempt_count_before_output(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TASK_DB_PATH", str(tmp_path / "operational.sqlite3"))
    audit.reset_notification_delivery_audit_for_tests()

    entry = {
        "delivery_key": "notification_delivery.v1|telegram_webhook|route-warning",
        "channel_id": "telegram_webhook",
        "message_id": "route-warning",
        "dedupe_key": "notification_plan.v1|model_route_budget|model_route_warning|v2/gemini-2.5-pro|retry_storm",
        "delivery_status": "pending",
    }
    audit.record_delivery_attempt(
        entry,
        status="failed",
        error="temporary webhook timeout",
        now=5_000.0,
    )
    with audit._connect() as conn:
        conn.execute(
            """
            UPDATE notification_delivery_audit
            SET attempt_count = ?
            WHERE delivery_key = ?
            """,
            (sqlite3.Binary(b"not-an-integer"), entry["delivery_key"]),
        )

    record = audit.list_delivery_records()[0]

    assert record["attempt_count"] == 0


def test_notification_delivery_audit_context_json_parsing_ignores_payload_truthiness_failures():
    class BrokenTruthJson(str):
        def __bool__(self):
            raise RuntimeError("context payload truthiness unavailable")

    context = audit.context_from_json(BrokenTruthJson('{"source":"provider_impact"}'))

    assert context == {"source": "provider_impact"}


def test_notification_delivery_audit_context_json_parsing_uses_string_safe_payloads():
    class StringableJson:
        def __str__(self):
            return '{"source":"provider_impact","ticker":"NVDA"}'

    context = audit.context_from_json(StringableJson())

    assert context == {"source": "provider_impact", "ticker": "NVDA"}


def test_notification_delivery_audit_context_json_parsing_drops_non_finite_numbers():
    context = audit.context_from_json(
        '{"source":"provider_impact","queue_rank":1,"bad_score":NaN,"bad_wait":Infinity}'
    )

    assert context == {"source": "provider_impact", "queue_rank": 1}


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


def test_notification_delivery_audit_failure_reason_rejects_binary_errors(monkeypatch):
    monkeypatch.setattr(
        audit,
        "list_delivery_records",
        lambda limit=1000: [
            {
                "delivery_key": "notification_delivery.v1|telegram_webhook|valid-timeout",
                "channel_id": "telegram_webhook",
                "message_id": "valid-timeout",
                "dedupe_key": "dedupe-valid-timeout",
                "delivery_status": "failed",
                "attempt_count": 1,
                "last_error": "temporary webhook timeout",
                "context": {},
            },
            {
                "delivery_key": "notification_delivery.v1|telegram_webhook|binary-timeout",
                "channel_id": "telegram_webhook",
                "message_id": "binary-timeout",
                "dedupe_key": "dedupe-binary-timeout",
                "delivery_status": "failed",
                "attempt_count": 1,
                "last_error": b"temporary webhook timeout",
                "context": {},
            },
            {
                "delivery_key": "notification_delivery.v1|telegram_webhook|buffer-auth",
                "channel_id": "telegram_webhook",
                "message_id": "buffer-auth",
                "dedupe_key": "dedupe-buffer-auth",
                "delivery_status": "failed",
                "attempt_count": 1,
                "last_error": memoryview(b"HTTP 403 invalid token"),
                "context": {},
            },
        ],
    )

    summary = audit.get_delivery_audit_summary()

    assert summary["failure_reason_counts"] == {"timeout": 1, "unknown": 2}


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


def test_notification_delivery_audit_summary_normalizes_statuses_before_counting_contexts(monkeypatch):
    monkeypatch.setattr(
        audit,
        "list_delivery_records",
        lambda limit=1000: [
            {
                "delivery_key": "notification_delivery.v1|telegram_webhook|failed-action",
                "channel_id": "telegram_webhook",
                "message_id": "failed-action",
                "dedupe_key": "dedupe-failed",
                "delivery_status": "\tFAILED\n",
                "attempt_count": 3,
                "last_error": "temporary webhook timeout",
                "context": {"source": "provider_impact", "ticker": "NVDA"},
            },
            {
                "delivery_key": "notification_delivery.v1|local|sent-action",
                "channel_id": "local",
                "message_id": "sent-action",
                "dedupe_key": "dedupe-sent",
                "delivery_status": " SENT ",
                "attempt_count": 1,
                "last_error": "",
                "context": {},
            },
            {
                "delivery_key": "notification_delivery.v1|local|pending-action",
                "channel_id": "local",
                "message_id": "pending-action",
                "dedupe_key": "dedupe-pending",
                "delivery_status": "\rPENDING\n",
                "attempt_count": 0,
                "last_error": "",
                "context": {},
            },
        ],
    )

    summary = audit.get_delivery_audit_summary()

    assert summary["sent_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["pending_count"] == 1
    assert summary["retry_exhausted_count"] == 1
    assert summary["failure_reason_counts"] == {"timeout": 1}
    assert summary["attention_contexts"] == [
        {
            "delivery_key": "notification_delivery.v1|telegram_webhook|failed-action",
            "channel_id": "telegram_webhook",
            "delivery_status": "failed",
            "attempt_count": 3,
            "last_error": "temporary webhook timeout",
            "context": {"source": "provider_impact", "ticker": "NVDA"},
        }
    ]


def test_notification_delivery_audit_summary_strips_attention_context_identity_fields(monkeypatch):
    monkeypatch.setattr(
        audit,
        "list_delivery_records",
        lambda limit=1000: [
            {
                "delivery_key": "\tnotification_delivery.v1|telegram_webhook|failed-action\n",
                "channel_id": " telegram_webhook ",
                "message_id": "failed-action",
                "dedupe_key": "dedupe-failed",
                "delivery_status": "failed",
                "attempt_count": 1,
                "last_error": "temporary webhook timeout",
                "context": {"source": "provider_impact", "ticker": "NVDA"},
            }
        ],
    )

    summary = audit.get_delivery_audit_summary()

    assert summary["attention_contexts"][0]["delivery_key"] == "notification_delivery.v1|telegram_webhook|failed-action"
    assert summary["attention_contexts"][0]["channel_id"] == "telegram_webhook"


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


def test_notification_delivery_audit_attention_contexts_default_limit_when_limit_is_none():
    records = [
        {
            "delivery_key": "delivery-1",
            "channel_id": "telegram_webhook",
            "delivery_status": "failed",
            "attempt_count": 2,
            "last_error": "temporary webhook timeout",
            "context": {"source": "provider_impact", "ticker": "NVDA"},
        }
    ]

    assert audit.attention_contexts_from_records(records, limit=None) == [
        {
            "delivery_key": "delivery-1",
            "channel_id": "telegram_webhook",
            "delivery_status": "failed",
            "attempt_count": 2,
            "last_error": "temporary webhook timeout",
            "context": {"source": "provider_impact", "ticker": "NVDA"},
        }
    ]
