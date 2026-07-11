from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_repair_queue_prioritizes_content_credibility_blocked_before_stale_snapshot():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        {
            "reports": [
                {
                    "ticker": "2308.TW",
                    "filename": "2308_stale.html",
                    "pipeline_id": "v1",
                    "data_trust": {"status": "stale", "stale_sources": ["market_price"]},
                },
                {
                    "ticker": "2330.TW",
                    "filename": "2330_blocked.html",
                    "pipeline_id": "v2",
                    "content_credibility": {
                        "status": "blocked",
                        "summary": "買入建議與目標價方向互相矛盾",
                    },
                },
            ]
        }
    )

    assert queue["schema_version"] == "report_quality_repair_queue.v1"
    assert [item["filename"] for item in queue["items"]] == [
        "2330_blocked.html",
        "2308_stale.html",
    ]
    assert queue["items"][0]["recommended_action"] == "manual_review"
    assert queue["items"][0]["severity"] == "blocked"
    assert queue["items"][1]["recommended_action"] == "refresh_data_snapshot"


def test_repair_queue_recommends_rerun_for_needs_rerun_instead_of_viewing_old_markdown():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "AAPL",
                "filename": "aapl_v1.html",
                "pipeline_id": "v1",
                "decision_freshness": {
                    "requires_rerun": True,
                    "requires_rerun_reason": "資料快照已刷新，但報告本文仍是舊結論。",
                },
                "data_trust": {"status": "fresh"},
            }
        ]
    )

    assert queue["items"][0]["recommended_action"] == "rerun_analysis"
    assert queue["items"][0]["action_label"] == "完整重跑"
    assert "舊結論" in queue["items"][0]["detail"]


def test_repair_queue_waits_for_core_provider_sla_recovery_before_blind_rerun():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "NVDA",
                "filename": "nvda_partial.html",
                "pipeline_id": "v2",
                "data_trust": {
                    "status": "partial",
                    "reason_codes": ["provider_sla_critical"],
                    "provider_sla_alerts": [
                        {
                            "source": "market_data",
                            "provider": "yfinance",
                            "alert_level": "critical",
                            "current_status": "unavailable",
                        }
                    ],
                },
                "decision_freshness": {"requires_rerun": True},
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "wait_provider_recovery"
    assert item["blocks_auto_rerun"] is True
    assert "provider_sla_critical" in item["reason_codes"]
    assert item["provider_impact"]["summary"]["max_severity"] == "critical"
    assert item["provider_impact"]["impacts"][0]["source_scope"] == "core"


def test_repair_queue_ignores_provider_sla_notice_when_current_fetch_is_healthy():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "MSFT",
                "filename": "msft_notice.html",
                "pipeline_id": "v1",
                "data_trust": {
                    "status": "partial",
                    "reason_codes": ["provider_sla_core_health_notice"],
                    "provider_sla_alerts": [
                        {
                            "source": "market_data",
                            "provider": "yfinance",
                            "alert_level": "critical",
                            "current_status": "success",
                            "current_record_count": 1,
                            "current_source_has_healthy_entry": True,
                        }
                    ],
                },
            }
        ]
    )

    assert queue["items"] == []
    assert queue["summary"]["action_required"] == 0


class BrokenRepairQueueEnvelopeGet(dict):
    def get(self, key, default=None):
        if key == "reports":
            raise AssertionError("repair queue must not use envelope.get()")
        return super().get(key, default)


class BrokenRepairQueueReportGet(dict):
    BROKEN_KEYS = {
        "ticker",
        "filename",
        "report_filename",
        "pipeline_id",
        "content_credibility",
        "report_conformance",
        "evidence_exit_gate",
        "data_trust",
        "decision_freshness",
        "requires_rerun",
        "analysis_text_stale",
        "analysis_text_stale_message",
        "requires_rerun_reason",
    }

    def get(self, key, default=None):
        if key in self.BROKEN_KEYS:
            raise AssertionError(f"repair queue must not use report.get({key!r})")
        return super().get(key, default)


class BrokenRepairQueueGateGet(dict):
    BROKEN_KEYS = {
        "status",
        "summary",
        "message",
        "verdict",
        "reason_codes",
        "stale_sources",
        "provider_sla_alerts",
        "requires_rerun",
        "requires_rerun_reason",
    }

    def get(self, key, default=None):
        if key in self.BROKEN_KEYS:
            raise AssertionError(f"repair queue must not use gate.get({key!r})")
        return super().get(key, default)


class BrokenRepairQueueTruthText:
    def __init__(self, text: str):
        self.text = text

    def __bool__(self):
        raise RuntimeError("repair queue text truthiness unavailable")

    def __str__(self):
        return self.text


class BrokenRepairQueueTruthBool:
    def __bool__(self):
        raise RuntimeError("repair queue bool truthiness unavailable")


class BrokenRepairQueueLimit:
    def __bool__(self):
        raise RuntimeError("repair queue limit truthiness unavailable")

    def __int__(self):
        return 1


class BrokenRepairQueueString:
    def __str__(self):
        raise RuntimeError("repair queue reason code string unavailable")


class BrokenRepairQueueNativeTextList(list):
    def __iter__(self):
        raise RuntimeError("repair queue text list iterator accessor unavailable")


class BrokenRepairQueueFirstNextTextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("repair queue text list first item unavailable")


class BrokenRepairQueueFirstNextTextList(list):
    def __iter__(self):
        return BrokenRepairQueueFirstNextTextIterator()


class BrokenRepairQueueAlertIterator(list):
    def __iter__(self):
        yield {
            "source": "market_data",
            "provider": "yfinance",
            "alert_level": "critical",
            "current_status": "unavailable",
            "current_record_count": 0,
        }
        raise RuntimeError("repair queue provider alert iterator unavailable")


class BrokenRepairQueueFirstNextAlertIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("repair queue provider alert first item unavailable")


class BrokenRepairQueueFirstNextAlertList(list):
    def __iter__(self):
        return BrokenRepairQueueFirstNextAlertIterator()


class BrokenRepairQueueReportIterator(list):
    def __iter__(self):
        yield {
            "ticker": "2330.TW",
            "filename": "2330_quality.html",
            "pipeline_id": "v2",
            "content_credibility": {
                "status": "blocked",
                "summary": "買入建議、目標價與資料限制互相矛盾。",
            },
        }
        raise RuntimeError("repair queue report iterator unavailable")


def test_repair_queue_keeps_quality_gate_mappings_when_accessor_fails():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        BrokenRepairQueueEnvelopeGet(
            {
                "reports": [
                    BrokenRepairQueueReportGet(
                        {
                            "ticker": "2330.TW",
                            "filename": "2330_quality.html",
                            "pipeline_id": "v2",
                            "content_credibility": BrokenRepairQueueGateGet(
                                {
                                    "status": "blocked",
                                    "summary": "買入建議、目標價與資料限制互相矛盾。",
                                }
                            ),
                            "report_conformance": BrokenRepairQueueGateGet(
                                {
                                    "status": "warning",
                                    "summary": "報告缺少部分可讀風險說明。",
                                }
                            ),
                            "evidence_exit_gate": BrokenRepairQueueGateGet({"verdict": "accepted"}),
                            "data_trust": BrokenRepairQueueGateGet(
                                {
                                    "status": "fresh",
                                    "reason_codes": [],
                                    "provider_sla_alerts": [],
                                }
                            ),
                            "decision_freshness": BrokenRepairQueueGateGet({"requires_rerun": False}),
                        }
                    )
                ]
            }
        )
    )

    assert queue["summary"]["action_required"] == 1
    item = queue["items"][0]
    assert item["ticker"] == "2330.TW"
    assert item["filename"] == "2330_quality.html"
    assert item["pipeline_id"] == "v2"
    assert item["recommended_action"] == "manual_review"
    assert item["reason_codes"] == ["content_credibility_blocked"]
    assert item["blocks_auto_rerun"] is True
    assert "互相矛盾" in item["detail"]


def test_repair_queue_preserves_valid_reports_before_iterator_failures():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(BrokenRepairQueueReportIterator())

    assert queue["summary"]["sampled_reports"] == 1
    assert queue["summary"]["action_required"] == 1
    item = queue["items"][0]
    assert item["ticker"] == "2330.TW"
    assert item["filename"] == "2330_quality.html"
    assert item["recommended_action"] == "manual_review"
    assert item["reason_codes"] == ["content_credibility_blocked"]


def test_repair_queue_reason_codes_preserve_valid_items_before_string_failures():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_data_trust.html",
                "pipeline_id": "v2",
                "data_trust": {
                    "status": "error",
                    "reason_codes": ["source_error:market_data", BrokenRepairQueueString()],
                },
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "manual_review"
    assert item["severity"] == "blocked"
    assert item["reason_codes"] == ["source_error:market_data"]
    assert item["blocks_auto_rerun"] is True


def test_repair_queue_reason_code_tuple_sequences_preserve_repair_reasons():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_data_trust.html",
                "pipeline_id": "v2",
                "data_trust": {
                    "status": "error",
                    "reason_codes": ("source_error:market_data",),
                },
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "manual_review"
    assert item["severity"] == "blocked"
    assert item["reason_codes"] == ["source_error:market_data"]
    assert item["blocks_auto_rerun"] is True


def test_repair_queue_reason_code_native_lists_survive_iterator_accessor_failures():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_data_trust.html",
                "pipeline_id": "v2",
                "data_trust": {
                    "status": "error",
                    "reason_codes": BrokenRepairQueueNativeTextList(["source_error:market_data"]),
                },
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "manual_review"
    assert item["severity"] == "blocked"
    assert item["reason_codes"] == ["source_error:market_data"]
    assert item["blocks_auto_rerun"] is True


def test_repair_queue_stale_sources_preserve_valid_items_before_string_failures():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2308.TW",
                "filename": "2308_stale.html",
                "pipeline_id": "v1",
                "data_trust": {
                    "status": "fresh",
                    "stale_sources": [BrokenRepairQueueString(), "market_price"],
                },
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "refresh_data_snapshot"
    assert item["severity"] == "warning"
    assert item["reason_codes"] == ["data_trust_stale"]


def test_repair_queue_stale_source_tuple_sequences_trigger_refresh_data():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2308.TW",
                "filename": "2308_stale.html",
                "pipeline_id": "v1",
                "data_trust": {
                    "status": "fresh",
                    "stale_sources": ("market_price",),
                },
            }
        ]
    )

    assert queue["summary"]["action_required"] == 1
    item = queue["items"][0]
    assert item["recommended_action"] == "refresh_data_snapshot"
    assert item["severity"] == "warning"
    assert item["reason_codes"] == ["data_trust_stale"]


def test_repair_queue_stale_sources_survive_first_next_iterator_failures():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2308.TW",
                "filename": "2308_stale.html",
                "pipeline_id": "v1",
                "data_trust": {
                    "status": "fresh",
                    "stale_sources": BrokenRepairQueueFirstNextTextList(["market_price"]),
                },
            }
        ]
    )

    assert queue["summary"]["action_required"] == 1
    item = queue["items"][0]
    assert item["recommended_action"] == "refresh_data_snapshot"
    assert item["severity"] == "warning"
    assert item["reason_codes"] == ["data_trust_stale"]


def test_repair_queue_provider_alerts_preserve_valid_items_before_iterator_failures():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "NVDA",
                "filename": "nvda_partial.html",
                "pipeline_id": "v2",
                "data_trust": {
                    "status": "partial",
                    "reason_codes": ["provider_sla_critical"],
                    "provider_sla_alerts": BrokenRepairQueueAlertIterator(),
                },
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "wait_provider_recovery"
    assert item["blocks_auto_rerun"] is True
    assert item["provider_impact"]["summary"]["max_severity"] == "critical"
    assert item["provider_impact"]["impacts"][0]["source"] == "market_data"


def test_repair_queue_provider_alerts_survive_first_next_iterator_failures():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "NVDA",
                "filename": "nvda_partial.html",
                "pipeline_id": "v2",
                "data_trust": {
                    "status": "partial",
                    "reason_codes": ["provider_sla_critical"],
                    "provider_sla_alerts": BrokenRepairQueueFirstNextAlertList(
                        [
                            {
                                "source": "market_data",
                                "provider": "yfinance",
                                "alert_level": "critical",
                                "current_status": "unavailable",
                                "current_record_count": 0,
                            }
                        ]
                    ),
                },
                "decision_freshness": {"requires_rerun": True},
            }
        ]
    )

    assert queue["summary"]["action_required"] == 1
    item = queue["items"][0]
    assert item["recommended_action"] == "wait_provider_recovery"
    assert item["severity"] == "blocked"
    assert item["blocks_auto_rerun"] is True
    assert item["provider_impact"]["summary"]["max_severity"] == "critical"


def test_repair_queue_decision_freshness_detail_does_not_depend_on_truthiness():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "AAPL",
                "filename": "aapl_v1.html",
                "pipeline_id": "v1",
                "decision_freshness": {
                    "requires_rerun": True,
                    "requires_rerun_reason": BrokenRepairQueueTruthText("資料快照已刷新，但報告本文仍是舊結論。"),
                },
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "rerun_analysis"
    assert item["action_label"] == "完整重跑"
    assert "舊結論" in item["detail"]


def test_repair_queue_decision_freshness_flags_do_not_depend_on_truthiness():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "AAPL",
                "filename": "aapl_v1.html",
                "pipeline_id": "v1",
                "decision_freshness": {
                    "requires_rerun": BrokenRepairQueueTruthBool(),
                    "requires_rerun_reason": "資料快照已刷新，但報告本文仍是舊結論。",
                },
                "requires_rerun": True,
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "rerun_analysis"
    assert item["action_label"] == "完整重跑"
    assert "舊結論" in item["detail"]


def test_repair_queue_limit_does_not_depend_on_truthiness():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2308.TW",
                "filename": "2308_stale.html",
                "pipeline_id": "v1",
                "data_trust": {"status": "stale", "stale_sources": ["market_price"]},
            },
            {
                "ticker": "2330.TW",
                "filename": "2330_blocked.html",
                "pipeline_id": "v2",
                "content_credibility": {
                    "status": "blocked",
                    "summary": "買入建議與目標價方向互相矛盾",
                },
            },
        ],
        limit=BrokenRepairQueueLimit(),
    )

    assert queue["summary"]["action_required"] == 2
    assert [item["filename"] for item in queue["items"]] == ["2330_blocked.html"]
    assert queue["items"][0]["recommended_action"] == "manual_review"


def test_repair_queue_report_identity_fields_do_not_depend_on_truthiness():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": BrokenRepairQueueTruthText("2330.TW"),
                "filename": BrokenRepairQueueTruthText("2330_quality.html"),
                "pipeline_id": BrokenRepairQueueTruthText("v2"),
                "content_credibility": {
                    "status": "blocked",
                    "summary": "買入建議、目標價與資料限制互相矛盾。",
                },
            }
        ]
    )

    item = queue["items"][0]
    assert item["ticker"] == "2330.TW"
    assert item["filename"] == "2330_quality.html"
    assert item["report_filename"] == "2330_quality.html"
    assert item["pipeline_id"] == "v2"
    assert item["recommended_action"] == "manual_review"
    assert item["blocks_auto_rerun"] is True


def test_repair_queue_quality_gate_text_fields_do_not_depend_on_truthiness():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_quality.html",
                "pipeline_id": "v2",
                "content_credibility": {
                    "status": BrokenRepairQueueTruthText("blocked"),
                    "summary": BrokenRepairQueueTruthText("買入建議、目標價與資料限制互相矛盾。"),
                },
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "manual_review"
    assert item["severity"] == "blocked"
    assert item["reason_codes"] == ["content_credibility_blocked"]
    assert item["blocks_auto_rerun"] is True
    assert "互相矛盾" in item["detail"]
