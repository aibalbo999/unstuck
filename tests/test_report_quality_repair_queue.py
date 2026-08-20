from __future__ import annotations

from collections.abc import Mapping
import importlib
import importlib.util
import sys
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class LookupItemsMapping(Mapping):
    def __init__(self, data):
        self._data = dict(data)

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def items(self):
        raise KeyError("repair queue mapping items lookup unavailable")


class LookupItemMapping(Mapping):
    def __init__(self, data):
        self._data = dict(data)

    def __getitem__(self, key):
        if key == "broken":
            raise KeyError("repair queue mapping item lookup unavailable")
        return self._data[key]

    def __iter__(self):
        return iter(("broken", *self._data.keys()))

    def __len__(self):
        return len(self._data) + 1


def test_report_quality_repair_items_project_blocked_content_credibility():
    assert importlib.util.find_spec("report_quality_repair_items") is not None
    helpers = importlib.import_module("report_quality_repair_items")

    item = helpers.content_credibility_repair_item(
        {
            "content_credibility": MappingProxyType(
                {
                    "status": "blocked",
                    "summary": "買入建議與目標價方向互相矛盾",
                }
            )
        }
    )

    assert item == {
        "severity": "blocked",
        "priority_score": 1000,
        "recommended_action": "manual_review",
        "action_label": "人工審核",
        "title": "內容可信度未通過",
        "detail": "買入建議與目標價方向互相矛盾",
        "reason_codes": ["content_credibility_blocked"],
        "blocks_auto_rerun": True,
    }


def test_report_quality_repair_items_project_warning_detail_from_content_warning():
    from report_quality_repair_items import content_credibility_repair_item

    item = content_credibility_repair_item(
        {
            "content_credibility": {
                "status": "warning",
                "summary": "報告關鍵結論未見阻斷矛盾，但仍有可信度警示。",
                "warnings": [
                    {
                        "id": "non_approved_evidence_gate",
                        "message": "證據抽查未完全通過，內容可信度需人工確認。",
                    }
                ],
            }
        }
    )

    assert item["detail"] == "證據抽查未完全通過，內容可信度需人工確認。"
    assert item["reason_codes"] == ["content_credibility_warning"]
    assert item["blocks_auto_rerun"] is False


def test_report_quality_repair_items_project_missing_quality_metadata():
    assert importlib.util.find_spec("report_quality_repair_items") is not None
    helpers = importlib.import_module("report_quality_repair_items")

    item = helpers.quality_metadata_repair_item(
        {
            "content_credibility": {},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "snapshot_integrity": {"status": "verified"},
        }
    )

    assert item == {
        "severity": "blocked",
        "priority_score": 820,
        "recommended_action": "manual_review",
        "action_label": "人工審核",
        "title": "品質證據未記錄",
        "detail": "報告未記錄 report_conformance、evidence_exit_gate、content_credibility 品質證據，採用前需人工查看。",
        "missing_quality_fields": ["report_conformance", "evidence_exit_gate", "content_credibility"],
        "reason_codes": ["quality_metadata_missing"],
        "blocks_auto_rerun": True,
    }


def test_quality_metadata_repair_accepts_mapping_safe_report_envelopes():
    from report_quality_metadata_repair import quality_metadata_repair_item

    report = MappingProxyType(
        {
            "snapshot_integrity": MappingProxyType({"status": "verified"}),
            "report_conformance": MappingProxyType({"status": "passed"}),
            "evidence_exit_gate": MappingProxyType({"verdict": "approved"}),
            "content_credibility": MappingProxyType({"status": "passed"}),
        }
    )

    assert quality_metadata_repair_item(report) is None


def test_quality_metadata_repair_rejects_placeholder_gate_states_as_missing():
    from report_quality_metadata_repair import quality_metadata_repair_item

    item = quality_metadata_repair_item(
        {
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {"status": "not_recorded"},
            "evidence_exit_gate": {"verdict": "unknown"},
            "content_credibility": {"status": "N/A"},
        }
    )

    assert item is not None
    assert item["missing_quality_fields"] == [
        "report_conformance",
        "evidence_exit_gate",
        "content_credibility",
    ]


def test_quality_metadata_repair_keeps_recorded_nonpassing_gate_states_complete():
    from report_quality_metadata_repair import quality_metadata_repair_item

    assert quality_metadata_repair_item(
        {
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {"status": "warning"},
            "evidence_exit_gate": {"verdict": "caution"},
            "content_credibility": {"status": "blocked"},
        }
    ) is None


def test_report_quality_repair_items_identify_quality_gap_after_snapshot_refresh():
    from report_quality_repair_items import quality_metadata_repair_item

    item = quality_metadata_repair_item(
        {
            "content_credibility": {},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "snapshot_integrity": {"status": "verified"},
            "refreshed_from_report": "1623_TW_v1_report_20260815_153238.html",
            "snapshot_refreshed_at": "2026-08-15T07:48:23+00:00",
        }
    )

    assert item["title"] == "刷新後品質證據缺口"
    assert "資料快照曾在報告後刷新" in item["detail"]
    assert "刷新歸因存在，但無法由目前 metadata 判定缺口是否由刷新造成" in item["detail"]
    assert item["reason_codes"] == ["quality_metadata_missing", "quality_metadata_after_refresh"]


def test_report_quality_repair_items_use_refresh_provenance_when_gap_predates_refresh():
    from report_quality_repair_items import quality_metadata_repair_item

    item = quality_metadata_repair_item(
        {
            "content_credibility": {},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "snapshot_integrity": {"status": "verified"},
            "refreshed_from_report": "1623_TW_v1_report_20260815_153238.html",
            "quality_metadata_refresh_provenance": {
                "schema_version": 1,
                "source": "previous_snapshot_before_refresh",
                "recorded_fields": {},
                "missing_fields": [
                    "report_conformance",
                    "evidence_exit_gate",
                    "content_credibility",
                ],
            },
        }
    )

    assert item["title"] == "刷新前已有品質證據缺口"
    assert "刷新前快照已確認缺少" in item["detail"]
    assert item["reason_codes"] == ["quality_metadata_missing", "quality_metadata_before_refresh"]


def test_report_quality_repair_items_explain_missing_rerun_context_after_refresh():
    from report_quality_repair_items import quality_metadata_repair_item

    item = quality_metadata_repair_item(
        {
            "content_credibility": {},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "snapshot_integrity": {"status": "verified"},
            "refreshed_from_report": "1623_TW_v1_report_20260815_153238.html",
            "refreshed_without_analysis_rerun": True,
            "decision_validity_status": "needs_rerun",
            "rerun_context": {},
        }
    )

    assert item["rerun_context_status"] == "missing"
    assert "沒有可供局部重跑的原始分析上下文" in item["detail"]
    assert "完整重跑" in item["detail"]
    assert item["reason_codes"][-1] == "rerun_context_missing"


def test_quality_metadata_repair_item_is_owned_by_dedicated_module():
    assert importlib.util.find_spec("report_quality_metadata_repair") is not None
    helpers = importlib.import_module("report_quality_repair_items")

    assert helpers.quality_metadata_repair_item.__module__ == "report_quality_metadata_repair"


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


def test_repair_queue_accepts_mapping_reports_envelope():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        MappingProxyType(
            {
                "reports": [
                    {
                        "ticker": "2308.TW",
                        "filename": "2308_stale.html",
                        "pipeline_id": "v1",
                        "data_trust": {"status": "stale", "stale_sources": ["market_price"]},
                    },
                ]
            }
        )
    )

    assert queue["summary"]["sampled_reports"] == 1
    assert queue["summary"]["action_required"] == 1
    assert queue["items"][0]["filename"] == "2308_stale.html"
    assert queue["items"][0]["recommended_action"] == "refresh_data_snapshot"


def test_repair_queue_blocks_invalid_snapshot_integrity_before_stale_snapshot():
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
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "snapshot_integrity": {
                    "status": "invalid",
                    "errors": ["snapshot_hash mismatch"],
                },
            },
        ]
    )

    assert [item["filename"] for item in queue["items"]] == [
        "2330_corrupt.html",
        "2308_stale.html",
    ]
    assert queue["items"][0]["recommended_action"] == "manual_review"
    assert queue["items"][0]["severity"] == "blocked"
    assert queue["items"][0]["blocks_auto_rerun"] is True
    assert queue["items"][0]["reason_codes"] == ["data_snapshot_integrity_invalid"]
    assert "snapshot_hash mismatch" in queue["items"][0]["detail"]


def test_repair_queue_blocks_invalid_mapping_snapshot_integrity_before_stale_snapshot():
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
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "snapshot_integrity": MappingProxyType(
                    {
                        "status": "invalid",
                        "errors": ("snapshot_hash mismatch",),
                    }
                ),
            },
        ]
    )

    assert [item["filename"] for item in queue["items"]] == [
        "2330_corrupt.html",
        "2308_stale.html",
    ]
    assert queue["items"][0]["recommended_action"] == "manual_review"
    assert queue["items"][0]["severity"] == "blocked"
    assert queue["items"][0]["blocks_auto_rerun"] is True
    assert queue["items"][0]["reason_codes"] == ["data_snapshot_integrity_invalid"]
    assert "snapshot_hash mismatch" in queue["items"][0]["detail"]


def test_repair_queue_treats_mapping_content_credibility_gate_as_recorded():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_content_blocked.html",
                "pipeline_id": "v2",
                "content_credibility": MappingProxyType(
                    {
                        "status": "blocked",
                        "summary": "買入建議與目標價方向互相矛盾",
                    }
                ),
            },
        ]
    )

    assert queue["summary"]["action_required"] == 1
    assert queue["items"][0]["recommended_action"] == "manual_review"
    assert queue["items"][0]["severity"] == "blocked"
    assert queue["items"][0]["blocks_auto_rerun"] is True
    assert queue["items"][0]["reason_codes"] == ["content_credibility_blocked"]
    assert "目標價方向互相矛盾" in queue["items"][0]["detail"]


def test_repair_queue_treats_lookup_items_mapping_content_credibility_gate_as_recorded():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_content_blocked.html",
                "pipeline_id": "v2",
                "content_credibility": LookupItemsMapping(
                    {
                        "status": "blocked",
                        "summary": "買入建議與目標價方向互相矛盾",
                    }
                ),
            },
        ]
    )

    assert queue["summary"]["action_required"] == 1
    assert queue["items"][0]["recommended_action"] == "manual_review"
    assert queue["items"][0]["severity"] == "blocked"
    assert queue["items"][0]["blocks_auto_rerun"] is True
    assert queue["items"][0]["reason_codes"] == ["content_credibility_blocked"]
    assert "目標價方向互相矛盾" in queue["items"][0]["detail"]


def test_repair_queue_treats_lookup_item_mapping_content_credibility_gate_as_recorded():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_content_blocked.html",
                "pipeline_id": "v2",
                "content_credibility": LookupItemMapping(
                    {
                        "status": "blocked",
                        "summary": "買入建議與目標價方向互相矛盾",
                    }
                ),
            },
        ]
    )

    assert queue["summary"]["action_required"] == 1
    assert queue["items"][0]["recommended_action"] == "manual_review"
    assert queue["items"][0]["severity"] == "blocked"
    assert queue["items"][0]["blocks_auto_rerun"] is True
    assert queue["items"][0]["reason_codes"] == ["content_credibility_blocked"]
    assert "目標價方向互相矛盾" in queue["items"][0]["detail"]


def test_report_conformance_agent_failure_recommends_rerun_without_blocking_auto_rerun():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2367.TW",
                "filename": "2367_v2.html",
                "pipeline_id": "v2",
                "report_conformance": {
                    "status": "blocked",
                    "blocking_issues": [
                        {
                            "id": "final_audit",
                            "details": ["技術動能分析師 輸出為失敗訊息，不能產生正式報告。"],
                        }
                    ],
                },
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "rerun_analysis"
    assert item["action_label"] == "完整重跑"
    assert item["severity"] == "blocked"
    assert item["priority_score"] == 840
    assert item["reason_codes"] == ["final_audit_agent_retry"]
    assert item["blocks_auto_rerun"] is False
    assert "輸出為失敗訊息" in item["detail"]


def test_report_conformance_non_retryable_final_audit_stays_manual_review():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "3017.TW",
                "filename": "3017_v1.html",
                "pipeline_id": "v1",
                "report_conformance": {
                    "status": "blocked",
                    "blocking_issues": [
                        {
                            "id": "final_audit",
                            "details": ["主力籌碼分析師：公司身分污染。"],
                        }
                    ],
                },
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "manual_review"
    assert item["blocks_auto_rerun"] is True
    assert item["reason_codes"] == ["report_conformance_blocked"]


def test_report_conformance_manual_review_exposes_blocking_issue_detail():
    from report_quality_repair_queue import build_report_quality_repair_queue

    detail = "建議/報酬矛盾：建議為「持有」但 12 個月目標價 NT$4500 相對現價 NT$3235 隱含 39.1% 報酬。"
    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "3017.TW",
                "filename": "3017_v1.html",
                "pipeline_id": "v1",
                "report_conformance": {
                    "status": "blocked",
                    "summary": "報告未符合輸出契約，需修正後再採用。",
                    "blocking_issues": [{"id": "final_audit", "details": [detail]}],
                },
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "manual_review"
    assert item["blocks_auto_rerun"] is True
    assert item["detail"] == detail


def test_provider_critical_still_precedes_agent_retry_recommendation():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "1623.TW",
                "filename": "1623_v3.html",
                "pipeline_id": "v3",
                "report_conformance": {
                    "status": "blocked",
                    "blocking_issues": [
                        {
                            "id": "final_audit",
                            "details": ["主力籌碼分析師 輸出為失敗訊息，不能產生正式報告。"],
                        }
                    ],
                },
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
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "wait_provider_recovery"
    assert item["blocks_auto_rerun"] is True


def test_repair_queue_blocks_false_valid_snapshot_integrity_before_stale_snapshot():
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
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "snapshot_integrity": {
                    "valid": False,
                    "errors": ["snapshot_hash mismatch"],
                },
            },
        ]
    )

    assert [item["filename"] for item in queue["items"]] == [
        "2330_corrupt.html",
        "2308_stale.html",
    ]
    assert queue["items"][0]["recommended_action"] == "manual_review"
    assert queue["items"][0]["severity"] == "blocked"
    assert queue["items"][0]["blocks_auto_rerun"] is True
    assert queue["items"][0]["reason_codes"] == ["data_snapshot_integrity_invalid"]
    assert "snapshot_hash mismatch" in queue["items"][0]["detail"]


def test_repair_queue_blocks_false_valid_snapshot_integrity_even_with_verified_status():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "snapshot_integrity": {
                    "status": "verified",
                    "valid": False,
                    "errors": ["snapshot_hash mismatch"],
                },
            },
        ]
    )

    assert queue["summary"]["action_required"] == 1
    assert queue["items"][0]["recommended_action"] == "manual_review"
    assert queue["items"][0]["severity"] == "blocked"
    assert queue["items"][0]["blocks_auto_rerun"] is True
    assert queue["items"][0]["reason_codes"] == ["data_snapshot_integrity_invalid"]
    assert "snapshot_hash mismatch" in queue["items"][0]["detail"]


def test_repair_queue_preserves_scalar_snapshot_integrity_error_detail():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "snapshot_integrity": {
                    "status": "invalid",
                    "errors": "snapshot_hash mismatch",
                },
            },
        ]
    )

    assert queue["items"][0]["recommended_action"] == "manual_review"
    assert queue["items"][0]["severity"] == "blocked"
    assert queue["items"][0]["reason_codes"] == ["data_snapshot_integrity_invalid"]
    assert queue["items"][0]["detail"] == "snapshot_hash mismatch"


def test_repair_queue_derives_snapshot_hash_mismatch_detail_from_hashes():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "snapshot_integrity": {
                    "status": "invalid",
                    "hash": "actual-hash",
                    "expected_hash": "expected-hash",
                },
            },
        ]
    )

    assert queue["items"][0]["recommended_action"] == "manual_review"
    assert queue["items"][0]["severity"] == "blocked"
    assert queue["items"][0]["reason_codes"] == ["data_snapshot_integrity_invalid"]
    assert queue["items"][0]["detail"] == "snapshot_hash mismatch"


def test_repair_queue_prefers_hash_mismatch_over_generic_snapshot_integrity_error():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "snapshot_integrity": {
                    "status": "invalid",
                    "hash": "actual-hash",
                    "expected_hash": "expected-hash",
                    "errors": ["資料快照完整性未通過，不能直接引用報告結論。"],
                },
            },
        ]
    )

    assert queue["items"][0]["recommended_action"] == "manual_review"
    assert queue["items"][0]["severity"] == "blocked"
    assert queue["items"][0]["reason_codes"] == ["data_snapshot_integrity_invalid"]
    assert queue["items"][0]["detail"] == "snapshot_hash mismatch"


def test_repair_queue_removes_generic_snapshot_integrity_error_when_specific_detail_exists():
    from report_quality_repair_queue import build_report_quality_repair_queue

    generic_error = "資料快照完整性未通過，不能直接引用報告結論。"
    specific_error = "provider audit mismatch: stale market price"

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "snapshot_integrity": {
                    "status": "invalid",
                    "errors": [generic_error, specific_error],
                },
            },
        ]
    )

    assert queue["items"][0]["recommended_action"] == "manual_review"
    assert queue["items"][0]["severity"] == "blocked"
    assert queue["items"][0]["detail"] == specific_error
    assert generic_error not in queue["items"][0]["detail"]


def test_repair_queue_deduplicates_snapshot_integrity_error_details():
    from report_quality_repair_queue import build_report_quality_repair_queue

    detail = "provider audit mismatch: stale market price"

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_corrupt.html",
                "pipeline_id": "v2",
                "snapshot_integrity": {
                    "status": "invalid",
                    "errors": [detail, detail],
                },
            },
        ]
    )

    assert queue["items"][0]["recommended_action"] == "manual_review"
    assert queue["items"][0]["severity"] == "blocked"
    assert queue["items"][0]["detail"] == detail


def test_repair_queue_uses_shared_text_safety_for_report_identity_fields():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": True,
                "filename": b"corrupt.html",
                "report_filename": "2330_corrupt.html",
                "pipeline_id": memoryview(b"v2"),
                "snapshot_integrity": {
                    "status": "invalid",
                    "errors": ["snapshot_hash mismatch"],
                },
            },
        ]
    )

    item = queue["items"][0]
    assert item["ticker"] == ""
    assert item["filename"] == "2330_corrupt.html"
    assert item["report_filename"] == "2330_corrupt.html"
    assert item["pipeline_id"] == "v1"


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


class BrokenRepairQueueLookupBool:
    def __bool__(self):
        raise KeyError("repair queue bool lookup unavailable")


class BrokenRepairQueueLimit:
    def __bool__(self):
        raise RuntimeError("repair queue limit truthiness unavailable")

    def __int__(self):
        return 1


class BrokenRepairQueueLookupLimit:
    def __int__(self):
        raise KeyError("repair queue limit lookup unavailable")


class BrokenRepairQueueString:
    def __str__(self):
        raise RuntimeError("repair queue reason code string unavailable")


class BrokenRepairQueueLookupString:
    def __str__(self):
        raise KeyError("repair queue text lookup unavailable")


class BrokenRepairQueueNativeTextList(list):
    def __iter__(self):
        raise RuntimeError("repair queue text list iterator accessor unavailable")


class BrokenRepairQueueFirstNextTextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("repair queue text list first item unavailable")


class BrokenRepairQueueLookupTextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise KeyError("repair queue text list lookup unavailable")


class BrokenRepairQueueFirstNextTextList(list):
    def __iter__(self):
        return BrokenRepairQueueFirstNextTextIterator()


class BrokenRepairQueueLookupTextList(list):
    def __iter__(self):
        return BrokenRepairQueueLookupTextIterator()


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


class BrokenRepairQueueLookupAlertIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise KeyError("repair queue provider alert lookup unavailable")


class BrokenRepairQueueLookupAlertList(list):
    def __iter__(self):
        return BrokenRepairQueueLookupAlertIterator()


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


def test_repair_queue_reason_code_native_lists_survive_lookup_iterator_failures():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_data_trust.html",
                "pipeline_id": "v2",
                "data_trust": {
                    "status": "error",
                    "reason_codes": BrokenRepairQueueLookupTextList(["source_error:market_data"]),
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


def test_repair_queue_provider_alerts_survive_lookup_iterator_failures():
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
                    "provider_sla_alerts": BrokenRepairQueueLookupAlertList(
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


def test_repair_queue_limit_uses_default_for_lookup_integer_failures():
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
        limit=BrokenRepairQueueLookupLimit(),
    )

    assert queue["summary"]["action_required"] == 2
    assert [item["filename"] for item in queue["items"]] == [
        "2330_blocked.html",
        "2308_stale.html",
    ]
    assert queue["items"][0]["recommended_action"] == "manual_review"


def test_repair_queue_decision_freshness_flags_ignore_lookup_truthiness_failures():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "AAPL",
                "filename": "aapl_v1.html",
                "pipeline_id": "v1",
                "decision_freshness": {
                    "requires_rerun": BrokenRepairQueueLookupBool(),
                    "requires_rerun_reason": "資料快照已刷新，但報告本文仍是舊結論。",
                },
                "analysis_text_stale": True,
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "rerun_analysis"
    assert item["action_label"] == "完整重跑"
    assert "舊結論" in item["detail"]


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


def test_repair_queue_quality_gate_text_fields_ignore_lookup_string_failures():
    from report_quality_repair_queue import build_report_quality_repair_queue

    queue = build_report_quality_repair_queue(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_quality.html",
                "pipeline_id": "v2",
                "content_credibility": {
                    "status": "blocked",
                    "summary": BrokenRepairQueueLookupString(),
                    "message": "買入建議、目標價與資料限制互相矛盾。",
                },
            }
        ]
    )

    item = queue["items"][0]
    assert item["recommended_action"] == "manual_review"
    assert item["severity"] == "blocked"
    assert item["reason_codes"] == ["content_credibility_blocked"]
    assert item["blocks_auto_rerun"] is True
    assert item["detail"] == "買入建議、目標價與資料限制互相矛盾。"
