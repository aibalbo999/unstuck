import importlib.util
import json
from types import SimpleNamespace


def test_quality_audit_row_keeps_legacy_false_freshness_false():
    from report_quality_audit_rows import hydrate_report_from_index_row

    snapshot = {
        "snapshot_hash": "hash",
        "generated_at": "2026-06-09T00:00:00+00:00",
        "refreshed_without_analysis_rerun": "false",
    }

    def load_item(_storage, _filename, *, kind):
        assert kind == "data"
        return SimpleNamespace(content=json.dumps(snapshot))

    report = hydrate_report_from_index_row(
        {"ticker": "2449.TW", "filename": "2449_v2.html", "pipeline_id": "v2"},
        object(),
        load_item=load_item,
        verify_snapshot_integrity=lambda _snapshot: {"valid": True, "expected_hash": "hash", "errors": []},
    )

    assert report["refreshed_without_analysis_rerun"] is False
    assert report["decision_freshness"]["requires_rerun"] is False


def test_quality_audit_row_uses_filename_pipeline_when_index_pipeline_is_placeholder():
    from report_quality_audit_rows import hydrate_report_from_index_row

    snapshot = {
        "pipeline": "N/A",
        "data": {"ticker": "2330.TW"},
    }

    def load_item(_storage, _filename, *, kind):
        assert kind == "data"
        return SimpleNamespace(content=json.dumps(snapshot))

    report = hydrate_report_from_index_row(
        {
            "ticker": "2330.TW",
            "filename": "2330_TW_v4_report_20260620_090000.html",
            "pipeline_id": "N/A",
        },
        object(),
        load_item=load_item,
        verify_snapshot_integrity=lambda _snapshot: {"valid": True, "expected_hash": "hash", "errors": []},
        project_current_quality=False,
    )

    assert report["pipeline_id"] == "v4"


def test_report_quality_audit_output_resolves_placeholder_pipeline_from_filename():
    from report_quality_audit import build_report_quality_audit

    payload = build_report_quality_audit(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_TW_v4_report_20260620_090000.html",
                "pipeline_id": "N/A",
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
            }
        ],
        scope="all_indexed_reports",
    )

    assert payload["quality_metadata_by_pipeline"]["v4"]["audited_reports"] == 1
    assert payload["items"][0]["pipeline_id"] == "v4"


def test_report_freshness_item_resolves_placeholder_pipeline_from_filename():
    from report_freshness_summary import build_report_freshness_items

    payload = build_report_freshness_items(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_TW_v4_report_20260620_090000.html",
                "pipeline_id": "N/A",
                "decision_freshness": {
                    "requires_rerun": True,
                    "requires_rerun_reason": "資料快照與結論不同步。",
                },
            }
        ]
    )

    assert payload["items"][0]["pipeline_id"] == "v4"


def test_snapshot_integrity_fail_closes_legacy_false_valid_token():
    from report_quality_audit_rows import snapshot_integrity

    result = snapshot_integrity(
        {"snapshot_hash": "hash"},
        verify_snapshot_integrity=lambda _snapshot: {
            "valid": "false",
            "expected_hash": "hash",
            "errors": ["hash mismatch"],
        },
    )

    assert result == {
        "status": "invalid",
        "valid": False,
        "errors": ["hash mismatch"],
    }


def test_report_quality_audit_counts_verified_reports_with_missing_quality_metadata():
    assert importlib.util.find_spec("report_quality_audit") is not None
    from report_quality_audit import build_report_quality_audit

    payload = build_report_quality_audit(
        {
            "reports": [
                {
                    "ticker": "1623.TW",
                    "filename": "1623_v1.html",
                    "report_date": "",
                    "pipeline_id": "v1",
                    "snapshot_integrity": {"status": "verified"},
                    "report_conformance": {},
                    "evidence_exit_gate": {},
                    "content_credibility": {},
                },
                {
                    "ticker": "2330.TW",
                    "filename": "2330_v1.html",
                    "pipeline_id": "v1",
                    "snapshot_integrity": {"status": "verified"},
                    "report_conformance": {"status": "passed"},
                    "evidence_exit_gate": {"verdict": "approved"},
                    "content_credibility": {"status": "passed"},
                },
                {
                    "ticker": "2454.TW",
                    "filename": "2454_v1.html",
                    "pipeline_id": "v1",
                    "snapshot_integrity": {"status": "invalid"},
                    "report_conformance": {},
                    "evidence_exit_gate": {},
                    "content_credibility": {},
                },
            ]
        },
        scope="all_indexed_reports",
    )

    assert payload == {
        "schema_version": "report_quality_audit.v1",
        "scope": "all_indexed_reports",
        "selection_basis": "latest_per_ticker_pipeline",
        "audited_reports": 3,
        "verified_snapshot_reports": 2,
        "snapshot_invalid_reports": 1,
        "snapshot_unverified_reports": 0,
        "quality_metadata_complete_reports": 1,
        "quality_metadata_missing_reports": 1,
        "missing_quality_field_counts": {
            "report_conformance": 1,
            "evidence_exit_gate": 1,
            "content_credibility": 1,
        },
        "quality_metadata_missing_by_provenance": {
            "before_refresh": 0,
            "after_refresh": 0,
            "no_refresh_provenance": 1,
        },
        "quality_metadata_missing_by_rerun_execution": {
            "full_rerun_required": 0,
            "partial_rerun_available": 0,
            "partial_rerun_review_required": 0,
            "partial_rerun_unavailable": 0,
            "not_evaluated": 1,
        },
        "quality_metadata_missing_by_rerun_context": {
            "present": 0,
            "partial": 0,
            "artifact_fallback_available": 0,
            "missing": 0,
            "not_evaluated": 1,
        },
        "quality_metadata_missing_by_version_status": {
            "current": 0,
            "historical": 0,
            "unknown": 1,
        },
        "quality_review_by_status": {
            "pending": 1,
            "approved_with_gap": 0,
            "rejected": 0,
            "deferred": 0,
        },
        "artifact_quality_summary_by_status": {
            "present": 0,
            "not_found": 0,
            "unavailable": 0,
        },
        "artifact_quality_summary_by_field": {
            "report_conformance": 0,
            "evidence_exit_gate": 0,
            "content_credibility": 0,
        },
        "quality_metadata_by_pipeline": {
            "v1": {
                "audited_reports": 3,
                "verified_snapshot_reports": 2,
                "snapshot_invalid_reports": 1,
                "snapshot_unverified_reports": 0,
                "quality_metadata_complete_reports": 1,
                "quality_metadata_missing_reports": 1,
                "missing_quality_field_counts": {
                    "report_conformance": 1,
                    "evidence_exit_gate": 1,
                    "content_credibility": 1,
                },
                "quality_metadata_missing_by_provenance": {
                    "before_refresh": 0,
                    "after_refresh": 0,
                    "no_refresh_provenance": 1,
                },
                "quality_metadata_missing_by_rerun_execution": {
                    "full_rerun_required": 0,
                    "partial_rerun_available": 0,
                    "partial_rerun_review_required": 0,
                    "partial_rerun_unavailable": 0,
                    "not_evaluated": 1,
                },
                "quality_metadata_missing_by_rerun_context": {
                    "present": 0,
                    "partial": 0,
                    "artifact_fallback_available": 0,
                    "missing": 0,
                    "not_evaluated": 1,
                },
                "quality_review_by_status": {
                    "pending": 1,
                    "approved_with_gap": 0,
                    "rejected": 0,
                    "deferred": 0,
                },
                "quality_metadata_coverage_pct": 50.0,
                "quality_metadata_coverage_basis": "verified_snapshot_reports",
            }
        },
        "quality_metadata_coverage_pct": 50.0,
        "quality_metadata_coverage_basis": "verified_snapshot_reports",
        "items_offset": 0,
        "items_limit": 5,
        "items_total": 1,
        "items_returned": 1,
        "items_has_prev": False,
        "items_has_next": False,
        "items_truncated": False,
        "items": [
            {
                "ticker": "1623.TW",
                "filename": "1623_v1.html",
                "report_date": "",
                "pipeline_id": "v1",
                "title": "品質證據未記錄",
                "detail": "報告未記錄 report_conformance、evidence_exit_gate、content_credibility 品質證據，採用前需人工查看。",
                    "missing_quality_fields": ["report_conformance", "evidence_exit_gate", "content_credibility"],
                    "reason_codes": ["quality_metadata_missing"],
                    "quality_metadata_provenance": "no_refresh_provenance",
                    "report_version_status": "unknown",
                    "refreshed_from_report": "",
                    "snapshot_refreshed_at": "",
                    "recommended_action": "manual_review",
                    "severity": "blocked",
                    "action_label": "人工審核",
                    "priority_score": 820,
                    "blocks_auto_rerun": True,
                }
        ],
    }


def test_report_quality_audit_marks_sample_scope_when_full_index_is_not_available():
    from report_quality_audit import build_report_quality_audit

    payload = build_report_quality_audit([], scope="daily_report_sample")

    assert payload["scope"] == "daily_report_sample"
    assert payload["audited_reports"] == 0
    assert payload["quality_metadata_coverage_pct"] is None
    assert payload["items"] == []


def test_report_freshness_summary_keeps_full_scope_separate_from_quality_metadata():
    from report_freshness_summary import build_report_freshness_summary

    payload = build_report_freshness_summary(
        [
            {"decision_freshness": {"status": "current", "requires_rerun": False}},
            {"decision_freshness": {"status": "needs_rerun", "requires_rerun": True}},
            {"decision_freshness": {"status": "unknown", "requires_rerun": False}},
        ],
        scope="all_indexed_reports",
        selection_basis="latest_per_ticker_pipeline",
    )

    assert payload == {
        "schema_version": "report_freshness_summary.v1",
        "scope": "all_indexed_reports",
        "selection_basis": "latest_per_ticker_pipeline",
        "audited_reports": 3,
        "current_reports": 1,
        "needs_rerun_reports": 1,
        "unknown_reports": 1,
    }


def test_report_freshness_items_keep_full_count_separate_from_bounded_navigation_sample():
    from report_freshness_summary import build_report_freshness_items

    payload = build_report_freshness_items([
        {"ticker": f"{index}.TW", "pipeline_id": "v1", "filename": f"{index}.html", "decision_freshness": {"status": "needs_rerun", "requires_rerun": True}}
        for index in range(7)
    ])

    assert payload["schema_version"] == "report_freshness_items.v1"
    assert payload["scope"] == "all_indexed_reports"
    assert payload["selection_basis"] == "latest_per_ticker_pipeline"
    assert payload["audited_reports"] == 7
    assert payload["needs_rerun_reports"] == 7
    assert payload["items_limit"] == 5
    assert payload["items_total"] == 7
    assert payload["items_returned"] == 5
    assert payload["items_truncated"] is True
    assert [item["filename"] for item in payload["items"]] == [f"{index}.html" for index in range(5)]


def test_report_quality_audit_exposes_item_truncation_metadata():
    from report_quality_audit import build_report_quality_audit

    reports = [
        {
            "ticker": ticker,
            "filename": f"{ticker}_v1.html",
            "pipeline_id": "v1",
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "content_credibility": {},
        }
        for ticker in ("1623.TW", "2330.TW", "2454.TW")
    ]

    payload = build_report_quality_audit(reports, scope="all_indexed_reports", item_limit=2)

    assert payload["quality_metadata_missing_reports"] == 3
    assert payload["items_returned"] == 2
    assert payload["items_truncated"] is True
    assert len(payload["items"]) == 2


def test_report_quality_audit_paginates_manual_review_items_without_changing_totals():
    from report_quality_audit import build_report_quality_audit

    reports = [
        {
            "ticker": ticker,
            "filename": f"{ticker}_v1.html",
            "pipeline_id": "v1",
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "content_credibility": {},
        }
        for ticker in ("1623.TW", "2330.TW", "2454.TW")
    ]

    payload = build_report_quality_audit(reports, scope="all_historical_indexed_reports", item_limit=2, item_offset=2)

    assert payload["quality_metadata_missing_reports"] == 3
    assert payload["items_offset"] == 2
    assert payload["items_limit"] == 2
    assert payload["items_total"] == 3
    assert payload["items_returned"] == 1
    assert payload["items_has_prev"] is True
    assert payload["items_has_next"] is False
    assert payload["items"][0]["filename"] == "2454.TW_v1.html"


def test_report_quality_audit_counts_missing_gates_independently():
    from report_quality_audit import build_report_quality_audit

    payload = build_report_quality_audit(
        [
            {
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
            },
            {
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {"status": "warning"},
                "evidence_exit_gate": {},
                "content_credibility": {"status": "passed"},
            },
            {
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {"status": "passed"},
                "evidence_exit_gate": {"verdict": "caution"},
                "content_credibility": {},
            },
        ],
        scope="all_historical_indexed_reports",
        selection_basis="all_indexed_versions",
    )

    assert payload["quality_metadata_missing_reports"] == 3
    assert payload["missing_quality_field_counts"] == {
        "report_conformance": 1,
        "evidence_exit_gate": 1,
        "content_credibility": 1,
    }


def test_report_quality_audit_counts_review_status_only_for_missing_metadata():
    from report_quality_audit import build_report_quality_audit

    payload = build_report_quality_audit(
        [
            {
                "pipeline_id": "v1",
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
                "quality_review": {"status": "approved_with_gap"},
            },
            {
                "pipeline_id": "v1",
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
                "quality_review": {"status": "deferred"},
            },
            {
                "pipeline_id": "v2",
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {"status": "passed"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "quality_review": {"status": "rejected"},
            },
        ],
        scope="all_historical_indexed_reports",
        selection_basis="all_indexed_versions",
    )

    assert payload["quality_review_by_status"] == {
        "pending": 0,
        "approved_with_gap": 1,
        "rejected": 0,
        "deferred": 1,
    }
    assert payload["quality_metadata_by_pipeline"]["v1"]["quality_review_by_status"] == {
        "pending": 0,
        "approved_with_gap": 1,
        "rejected": 0,
        "deferred": 1,
    }


def test_report_quality_audit_groups_coverage_by_pipeline():
    from report_quality_audit import build_report_quality_audit

    payload = build_report_quality_audit(
        [
            {
                "pipeline_id": "v1",
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
            },
            {
                "pipeline_id": "v2",
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {"status": "passed"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
            },
        ],
        scope="all_historical_indexed_reports",
        selection_basis="all_indexed_versions",
    )

    assert payload["quality_metadata_by_pipeline"] == {
        "v1": {
            "audited_reports": 1,
            "verified_snapshot_reports": 1,
            "snapshot_invalid_reports": 0,
            "snapshot_unverified_reports": 0,
            "quality_metadata_complete_reports": 0,
            "quality_metadata_missing_reports": 1,
                "missing_quality_field_counts": {
                    "report_conformance": 1,
                    "evidence_exit_gate": 1,
                    "content_credibility": 1,
                },
                "quality_metadata_missing_by_provenance": {
                    "before_refresh": 0,
                    "after_refresh": 0,
                    "no_refresh_provenance": 1,
                },
            "quality_metadata_missing_by_rerun_execution": {
                "full_rerun_required": 0,
                "partial_rerun_available": 0,
                "partial_rerun_review_required": 0,
                "partial_rerun_unavailable": 0,
                "not_evaluated": 1,
            },
            "quality_metadata_missing_by_rerun_context": {
                "present": 0,
                "partial": 0,
                "artifact_fallback_available": 0,
                "missing": 0,
                "not_evaluated": 1,
            },
                "quality_review_by_status": {
                    "pending": 1,
                    "approved_with_gap": 0,
                    "rejected": 0,
                    "deferred": 0,
                },
                "quality_metadata_coverage_pct": 0.0,
            "quality_metadata_coverage_basis": "verified_snapshot_reports",
        },
        "v2": {
            "audited_reports": 1,
            "verified_snapshot_reports": 1,
            "snapshot_invalid_reports": 0,
            "snapshot_unverified_reports": 0,
            "quality_metadata_complete_reports": 1,
            "quality_metadata_missing_reports": 0,
                "missing_quality_field_counts": {
                    "report_conformance": 0,
                    "evidence_exit_gate": 0,
                    "content_credibility": 0,
                },
                "quality_metadata_missing_by_provenance": {
                    "before_refresh": 0,
                    "after_refresh": 0,
                    "no_refresh_provenance": 0,
                },
                "quality_metadata_missing_by_rerun_execution": {
                    "full_rerun_required": 0,
                    "partial_rerun_available": 0,
                    "partial_rerun_review_required": 0,
                    "partial_rerun_unavailable": 0,
                    "not_evaluated": 0,
                },
                "quality_metadata_missing_by_rerun_context": {
                    "present": 0,
                    "partial": 0,
                    "artifact_fallback_available": 0,
                    "missing": 0,
                    "not_evaluated": 0,
                },
                "quality_review_by_status": {
                    "pending": 0,
                    "approved_with_gap": 0,
                    "rejected": 0,
                    "deferred": 0,
                },
                "quality_metadata_coverage_pct": 100.0,
            "quality_metadata_coverage_basis": "verified_snapshot_reports",
        },
    }


def test_report_quality_audit_surfaces_current_and_historical_version_status():
    from report_quality_audit import build_report_quality_audit

    payload = build_report_quality_audit(
        [
            {
                "ticker": "1623.TW",
                "filename": "1623_current.html",
                "pipeline_id": "v2",
                "report_version_status": "current",
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
            },
            {
                "ticker": "1623.TW",
                "filename": "1623_old.html",
                "pipeline_id": "v2",
                "report_version_status": "historical",
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
            },
        ],
        scope="all_historical_indexed_reports",
        selection_basis="all_indexed_versions",
    )

    assert payload["quality_metadata_missing_by_version_status"] == {
        "current": 1,
        "historical": 1,
        "unknown": 0,
    }
    assert [item["report_version_status"] for item in payload["items"]] == ["current", "historical"]


def test_indexed_quality_annotation_uses_ticker_pipeline_latest_filename():
    from report_quality_audit import _annotate_report_version_status

    reports = [
        {"ticker": "1623.TW", "pipeline_id": "v2", "filename": "old.html"},
        {"ticker": "1623", "pipeline_id": "v2", "filename": "new.html"},
        {"ticker": "1623.TW", "pipeline_id": "v1", "filename": "v1.html"},
    ]

    _annotate_report_version_status(
        reports,
        {("1623", "v2"): "new.html", ("1623", "v1"): "v1.html"},
    )

    assert [report["report_version_status"] for report in reports] == ["historical", "current", "current"]


def test_report_quality_audit_groups_missing_metadata_by_refresh_provenance():
    from report_quality_audit import build_report_quality_audit

    payload = build_report_quality_audit(
        [
            {
                "ticker": "1623.TW",
                "filename": "1623_v1.html",
                "pipeline_id": "v1",
                "snapshot_integrity": {"status": "verified"},
                "refreshed_from_report": "1623_v1.html",
                "snapshot_refreshed_at": "2026-08-15T07:48:23+00:00",
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
            },
            {
                "ticker": "2330.TW",
                "filename": "2330_v2.html",
                "pipeline_id": "v2",
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
            },
        ],
        scope="all_historical_indexed_reports",
        selection_basis="all_indexed_versions",
        item_limit=0,
    )

    assert payload["quality_metadata_missing_by_provenance"] == {
        "before_refresh": 0,
        "after_refresh": 1,
        "no_refresh_provenance": 1,
    }
    assert payload["quality_metadata_by_pipeline"]["v1"]["quality_metadata_missing_by_provenance"] == {
        "before_refresh": 0,
        "after_refresh": 1,
        "no_refresh_provenance": 0,
    }
    assert payload["items"] == []

    payload = build_report_quality_audit(
        [
            {
                "ticker": "1623.TW",
                "filename": "1623_v1.html",
                "pipeline_id": "v1",
                "snapshot_integrity": {"status": "verified"},
                "refreshed_from_report": "1623_v1.html",
                "snapshot_refreshed_at": "2026-08-15T07:48:23+00:00",
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
            }
        ],
        scope="all_historical_indexed_reports",
        selection_basis="all_indexed_versions",
    )
    assert payload["items"][0]["quality_metadata_provenance"] == "after_refresh"
    assert payload["items"][0]["rerun_context_status"] == "missing"
    assert payload["items"][0]["refreshed_from_report"] == "1623_v1.html"
    assert payload["items"][0]["snapshot_refreshed_at"] == "2026-08-15T07:48:23+00:00"


def test_report_quality_audit_classifies_pre_refresh_quality_gaps_separately():
    from report_quality_audit import build_report_quality_audit

    payload = build_report_quality_audit(
        [
            {
                "ticker": "1623.TW",
                "filename": "1623_v1.html",
                "pipeline_id": "v1",
                "snapshot_integrity": {"status": "verified"},
                "refreshed_from_report": "1623_v1.html",
                "quality_metadata_refresh_provenance": {
                    "schema_version": 1,
                    "source": "previous_snapshot_before_refresh",
                    "recorded_fields": {},
                    "missing_fields": ["report_conformance", "evidence_exit_gate"],
                },
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {"status": "passed"},
            }
        ],
        scope="all_historical_indexed_reports",
        selection_basis="all_indexed_versions",
    )

    assert payload["quality_metadata_missing_by_provenance"] == {
        "before_refresh": 1,
        "after_refresh": 0,
        "no_refresh_provenance": 0,
    }
    assert payload["items"][0]["quality_metadata_provenance"] == "before_refresh"
    assert payload["items"][0]["reason_codes"] == [
        "quality_metadata_missing",
        "quality_metadata_before_refresh",
    ]


def test_report_quality_audit_groups_missing_metadata_by_rerun_execution_strategy():
    from report_quality_audit import build_report_quality_audit

    base = {
        "snapshot_integrity": {"status": "verified"},
        "report_conformance": {},
        "evidence_exit_gate": {},
        "content_credibility": {},
        "refreshed_from_report": "report.html",
    }
    payload = build_report_quality_audit(
        [
            {**base, "ticker": "1000.TW", "filename": "full.html", "decision_validity_status": "needs_rerun"},
            {
                **base,
                "ticker": "1001.TW",
                "filename": "partial.html",
                "rerun_context": {"analyses": {"agent": "ok"}, "structured_outputs": {"agent": "ok"}, "parsed": {"recommendation": {}}},
            },
            {
                **base,
                "ticker": "1002.TW",
                "filename": "review.html",
                "rerun_context": {"analyses": {"agent": "ok"}},
            },
        ],
        scope="all_historical_indexed_reports",
        selection_basis="all_indexed_versions",
        item_limit=0,
    )

    assert payload["quality_metadata_missing_by_rerun_execution"] == {
        "full_rerun_required": 1,
        "partial_rerun_available": 1,
        "partial_rerun_review_required": 1,
        "partial_rerun_unavailable": 0,
        "not_evaluated": 0,
    }
    assert payload["quality_metadata_missing_by_rerun_context"] == {
        "present": 1,
        "partial": 1,
        "artifact_fallback_available": 0,
        "missing": 1,
        "not_evaluated": 0,
    }


def test_report_quality_audit_does_not_count_placeholder_gate_states_as_complete():
    from report_quality_audit import build_report_quality_audit

    payload = build_report_quality_audit(
        [
            {
                "ticker": "2330.TW",
                "filename": "2330_v1.html",
                "pipeline_id": "v1",
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {"status": "not_recorded"},
                "evidence_exit_gate": {"verdict": "unknown"},
                "content_credibility": {"status": "N/A"},
            }
        ],
        scope="all_indexed_reports",
    )

    assert payload["quality_metadata_complete_reports"] == 0
    assert payload["quality_metadata_missing_reports"] == 1
    assert payload["selection_basis"] == "latest_per_ticker_pipeline"
    assert payload["items"][0]["missing_quality_fields"] == [
        "report_conformance",
        "evidence_exit_gate",
        "content_credibility",
    ]


def test_report_quality_audit_keeps_unverified_snapshots_out_of_coverage_denominator():
    from report_quality_audit import build_report_quality_audit

    payload = build_report_quality_audit(
        [
            {
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {"status": "passed"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
            },
            {"snapshot_integrity": {"status": "unverified"}},
        ],
        scope="all_indexed_reports",
    )

    assert payload["verified_snapshot_reports"] == 1
    assert payload["snapshot_invalid_reports"] == 0
    assert payload["snapshot_unverified_reports"] == 1
    assert payload["quality_metadata_coverage_pct"] == 100.0
    assert payload["quality_metadata_coverage_basis"] == "verified_snapshot_reports"


def test_indexed_report_quality_audit_isolates_one_snapshot_load_failure(monkeypatch, tmp_path):
    import report_quality_audit as audit

    monkeypatch.setattr(
        audit,
        "collect_all_report_pages",
        lambda *_args, **_kwargs: {
            "reports": [
                {"ticker": "BAD", "filename": "bad.html", "pipeline_id": "v1"},
                {"ticker": "GOOD", "filename": "good.html", "pipeline_id": "v1"},
            ]
        },
    )
    monkeypatch.setattr(audit, "storage_for_existing_output_dir", lambda *_args: object())

    def load_item(_storage, filename, *, kind):
        assert kind == "data"
        if filename == "bad.html":
            raise OSError("simulated artifact read failure")
        return SimpleNamespace(content=json.dumps({
            "snapshot_hash": "hash",
            "report_conformance": {"status": "passed"},
            "evidence_exit_gate": {"verdict": "approved"},
            "content_credibility": {"status": "passed"},
        }))

    monkeypatch.setattr(audit, "load_storage_item", load_item)
    monkeypatch.setattr(
        audit,
        "verify_data_snapshot_integrity",
        lambda _snapshot: {"valid": True, "expected_hash": "hash", "errors": []},
    )

    payload = audit.build_indexed_report_quality_audit(str(tmp_path))

    assert payload["audited_reports"] == 2
    assert payload["verified_snapshot_reports"] == 1
    assert payload["snapshot_unverified_reports"] == 1
    assert payload["quality_metadata_complete_reports"] == 1


def test_indexed_quality_projection_does_not_keep_passed_credibility_when_final_audit_is_blocked(monkeypatch):
    import report_quality_audit as audit

    snapshot = {
        "snapshot_hash": "hash",
        "pipeline": "v1",
        "report_conformance": {
            "decision_tree": [
                {
                    "id": "final_audit",
                    "status": "blocked",
                    "message": "最終稽核存在 critical 問題。",
                    "details": ["缺少 Agent 輸出：7"],
                }
            ]
        },
        "content_credibility": {"status": "passed", "blocking_issues": [], "warnings": [], "checks": []},
    }
    monkeypatch.setattr(
        audit,
        "load_storage_item",
        lambda *_args, **_kwargs: SimpleNamespace(content=json.dumps(snapshot)),
    )

    report = audit._report_from_index_row(
        {"filename": "stale.html", "ticker": "2330.TW", "pipeline_id": "v1"},
        object(),
    )

    assert report["content_credibility"]["status"] == "blocked"
    assert any(
        issue["id"] == "final_audit_critical"
        for issue in report["content_credibility"]["blocking_issues"]
    )


def test_indexed_quality_projection_rechecks_saved_parsed_context_without_filling_missing_gate(monkeypatch):
    import report_quality_audit as audit

    snapshot = {
        "snapshot_hash": "hash",
        "pipeline": "v1",
        "data": {
            "current_price": 100.0,
            "data_trust": {"status": "fresh", "score": 90, "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "evidence_exit_gate": {"verdict": "approved", "failed_count": 0},
        "evidence_matrix": [
            {"claim": "估值結論", "basis": "熊市 80；基本 120；牛市 140", "status": "success"},
            {"claim": "最終投資建議", "basis": "建議 買入；12 個月 90", "status": "success"},
        ],
        "rerun_context": {
            "pipeline_id": "v1",
            "parsed": {
                "recommendation": {"建議": "買入", "12個月": "NT$90", "信心": "7/10"},
                "price_targets": {"熊市情境": 80, "基本情境": 120, "牛市情境": 140},
            },
        },
        "content_credibility": {"status": "passed", "blocking_issues": [], "warnings": [], "checks": []},
    }
    monkeypatch.setattr(
        audit,
        "load_storage_item",
        lambda *_args, **_kwargs: SimpleNamespace(content=json.dumps(snapshot)),
    )

    report = audit._report_from_index_row(
        {"filename": "current.html", "ticker": "2330.TW", "pipeline_id": "v1"},
        object(),
    )

    assert report["content_credibility"]["status"] == "blocked"
    assert report["content_credibility_projection"] == {
        "status": "projected",
        "source": "snapshot.rerun_context",
        "persisted_status": "passed",
    }

    snapshot["content_credibility"] = {}
    monkeypatch.setattr(
        audit,
        "load_storage_item",
        lambda *_args, **_kwargs: SimpleNamespace(content=json.dumps(snapshot)),
    )
    report = audit._report_from_index_row(
        {"filename": "missing.html", "ticker": "2330.TW", "pipeline_id": "v1"},
        object(),
    )

    assert report["content_credibility"] == {}
    assert report["content_credibility_projection"]["status"] == "available"


def test_indexed_quality_projection_rechecks_saved_evidence_gate_without_mutating_snapshot(monkeypatch):
    import report_quality_audit as audit

    snapshot = {
        "snapshot_hash": "hash",
        "pipeline": "v1",
        "data": {"current_price": 100.0},
        "evidence_exit_gate": {"verdict": "approved", "failed_count": 0},
        "content_credibility": {"status": "passed"},
    }
    original_snapshot = json.loads(json.dumps(snapshot))
    markdown = "- 股價: NT$90.0"

    def load_item(_storage, _filename, *, kind):
        if kind == "data":
            return SimpleNamespace(content=json.dumps(snapshot))
        assert kind == "md"
        return SimpleNamespace(content=markdown)

    monkeypatch.setattr(audit, "load_storage_item", load_item)

    report = audit._report_from_index_row(
        {"filename": "stale.html", "ticker": "2330.TW", "pipeline_id": "v1"},
        object(),
    )

    assert report["evidence_exit_gate"]["verdict"] == "rejected"
    assert report["evidence_exit_gate_projection"] == {
        "status": "projected",
        "source": "markdown+snapshot.current_rules",
        "persisted_verdict": "approved",
    }
    assert snapshot == original_snapshot


def test_indexed_quality_audit_skips_projection_without_persisted_content_gate(monkeypatch):
    import report_quality_audit as audit
    import report_quality_audit_rows as audit_rows

    snapshot = {
        "snapshot_hash": "hash",
        "pipeline": "v1",
        "data": {"current_price": 100.0},
        "rerun_context": {
            "pipeline_id": "v1",
            "parsed": {"recommendation": {"建議": "買入"}},
        },
        "content_credibility": {},
    }
    monkeypatch.setattr(
        audit,
        "load_storage_item",
        lambda *_args, **_kwargs: SimpleNamespace(content=json.dumps(snapshot)),
    )

    def fail_projection(_snapshot):
        raise AssertionError("missing persisted content gate must not trigger projection")

    monkeypatch.setattr(audit_rows, "project_content_credibility", fail_projection)

    report = audit._report_from_index_row(
        {"filename": "missing-content-gate.html", "ticker": "2330.TW", "pipeline_id": "v1"},
        object(),
    )

    assert report["content_credibility"] == {}
    assert report["content_credibility_projection"]["status"] == "available"


def test_indexed_quality_audit_skips_evidence_projection_without_persisted_gate(monkeypatch):
    import report_quality_audit as audit
    import report_quality_audit_rows as audit_rows

    snapshot = {
        "snapshot_hash": "hash",
        "pipeline": "v1",
        "data": {"current_price": 100.0},
        "content_credibility": {"status": "passed"},
    }
    monkeypatch.setattr(
        audit,
        "load_storage_item",
        lambda *_args, **_kwargs: SimpleNamespace(content=json.dumps(snapshot)),
    )

    def fail_projection(*_args):
        raise AssertionError("missing persisted evidence gate must not trigger projection")

    monkeypatch.setattr(audit_rows, "project_evidence_exit_gate", fail_projection)

    report = audit._report_from_index_row(
        {"filename": "missing-evidence-gate.html", "ticker": "2330.TW", "pipeline_id": "v1"},
        object(),
    )

    assert report["evidence_exit_gate"] == {}
    assert "evidence_exit_gate_projection" not in report


def test_indexed_quality_audit_does_not_project_current_content_credibility(monkeypatch):
    import report_quality_audit as audit
    import report_quality_audit_rows as audit_rows

    snapshot = {
        "snapshot_hash": "hash",
        "pipeline": "v1",
        "evidence_exit_gate": {"verdict": "approved"},
        "content_credibility": {"status": "passed"},
    }
    monkeypatch.setattr(
        audit,
        "load_storage_item",
        lambda *_args, **_kwargs: SimpleNamespace(content=json.dumps(snapshot)),
    )

    def fail_projection(_snapshot):
        raise AssertionError("quality audit does not consume current content projection")

    monkeypatch.setattr(audit_rows, "project_content_credibility", fail_projection)

    def fail_evidence_projection(*_args):
        raise AssertionError("quality audit does not consume current evidence projection")

    monkeypatch.setattr(audit_rows, "project_evidence_exit_gate", fail_evidence_projection)

    reports = audit._indexed_quality_reports(
        [{"filename": "current.html", "ticker": "2330.TW", "pipeline_id": "v1"}],
        object(),
    )

    assert reports[0]["content_credibility"] == {"status": "passed"}
    assert reports[0]["evidence_exit_gate"] == {"verdict": "approved"}


def test_indexed_report_quality_audit_exposes_snapshot_refresh_provenance(monkeypatch, tmp_path):
    import report_quality_audit as audit

    monkeypatch.setattr(
        audit,
        "collect_all_report_pages",
        lambda *_args, **_kwargs: {
            "reports": [{"ticker": "1623.TW", "filename": "1623_v1.html", "pipeline_id": "v1"}]
        },
    )
    monkeypatch.setattr(audit, "storage_for_existing_output_dir", lambda *_args: object())
    monkeypatch.setattr(
        audit,
        "load_storage_item",
        lambda *_args, **_kwargs: SimpleNamespace(
            content=json.dumps(
                {
                    "snapshot_hash": "hash",
                    "refreshed_from_report": "1623_v1.html",
                    "snapshot_refreshed_at": "2026-08-15T07:48:23+00:00",
                    "refreshed_without_analysis_rerun": True,
                    "decision_validity_status": "needs_rerun",
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
                    "rerun_context": {},
                    "report_conformance": {},
                    "evidence_exit_gate": {},
                    "content_credibility": {},
                }
            )
        ),
    )
    monkeypatch.setattr(
        audit,
        "verify_data_snapshot_integrity",
        lambda _snapshot: {"valid": True, "expected_hash": "hash", "errors": []},
    )

    payload = audit.build_indexed_report_quality_audit(str(tmp_path))

    assert payload["decision_freshness_summary"] == {
        "schema_version": "report_freshness_summary.v1",
        "scope": "all_indexed_reports",
        "selection_basis": "latest_per_ticker_pipeline",
        "audited_reports": 1,
        "current_reports": 0,
        "needs_rerun_reports": 1,
        "unknown_reports": 0,
    }
    freshness_items = payload["decision_freshness_items"]
    assert freshness_items["schema_version"] == "report_freshness_items.v1"
    assert freshness_items["scope"] == "all_indexed_reports"
    assert freshness_items["selection_basis"] == "latest_per_ticker_pipeline"
    assert freshness_items["audited_reports"] == 1
    assert freshness_items["needs_rerun_reports"] == 1
    assert freshness_items["items_returned"] == 1
    assert freshness_items["items_truncated"] is False
    assert freshness_items["items"][0]["filename"] == "1623_v1.html"
    assert freshness_items["items"][0]["ticker"] == "1623.TW"
    assert freshness_items["items"][0]["pipeline_id"] == "v1"
    assert payload["items"][0]["title"] == "刷新前已有品質證據缺口"
    assert payload["items"][0]["rerun_context_status"] == "missing"
    assert payload["items"][0]["reason_codes"] == [
        "quality_metadata_missing",
        "quality_metadata_before_refresh",
        "rerun_context_missing",
    ]
    assert payload["items"][0]["quality_metadata_refresh_provenance"]["missing_fields"] == [
        "report_conformance",
        "evidence_exit_gate",
        "content_credibility",
    ]


def test_indexed_report_quality_audit_exposes_markdown_rerun_fallback(monkeypatch, tmp_path):
    import report_quality_audit as audit
    from pipeline_modes import get_pipeline_definition, get_structured_agent_num

    pipeline_id = "v2"
    final_agent = get_structured_agent_num("recommendation", pipeline_id)
    required_agents = [agent for agent in get_pipeline_definition(pipeline_id)["agents"] if agent < final_agent]
    markdown = "\n\n".join(
        f"## {agent}. 前序段落 (Agent {agent})\n既有分析內容。"
        for agent in required_agents
    )

    monkeypatch.setattr(
        audit,
        "collect_all_report_pages",
        lambda *_args, **_kwargs: {
            "reports": [{"ticker": "1623.TW", "filename": "1623_v2.html", "pipeline_id": pipeline_id}]
        },
    )
    monkeypatch.setattr(audit, "storage_for_existing_output_dir", lambda *_args: object())

    def load_item(_storage, _filename, *, kind):
        if kind == "data":
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "snapshot_hash": "hash",
                        "pipeline": pipeline_id,
                        "refreshed_from_report": "1623_v2.html",
                        "refreshed_without_analysis_rerun": True,
                        "decision_validity_status": "needs_rerun",
                        "rerun_context": {},
                        "report_conformance": {},
                        "evidence_exit_gate": {},
                        "content_credibility": {},
                    }
                )
            )
        assert kind == "md"
        return SimpleNamespace(content=markdown.encode("utf-8"))

    monkeypatch.setattr(audit, "load_storage_item", load_item)
    monkeypatch.setattr(
        audit,
        "verify_data_snapshot_integrity",
        lambda _snapshot: {"valid": True, "expected_hash": "hash", "errors": []},
    )

    payload = audit.build_indexed_report_quality_audit(str(tmp_path))
    item = payload["items"][0]

    assert item["rerun_context_status"] == "artifact_fallback_available"
    assert item["artifact_rerun_context_status"] == "present"
    assert item["rerun_execution_status"] == "full_rerun_required"
    assert "目前資料 freshness 仍要求完整重跑" in item["detail"]
    assert "可嘗試只重跑最終建議" not in item["detail"]
    assert "rerun_context_missing" not in item["reason_codes"]


def test_indexed_report_quality_audit_exposes_artifact_quality_summary_without_reconstructing_gates(monkeypatch, tmp_path):
    import report_quality_audit as audit

    monkeypatch.setattr(
        audit,
        "collect_all_report_pages",
        lambda *_args, **_kwargs: {
            "reports": [{"ticker": "1623.TW", "filename": "1623_v1.html", "pipeline_id": "v1"}]
        },
    )
    monkeypatch.setattr(audit, "storage_for_existing_output_dir", lambda *_args: object())

    def load_item(_storage, _filename, *, kind):
        if kind == "data":
            return SimpleNamespace(content=json.dumps({
                "snapshot_hash": "hash",
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
            }))
        assert kind == "md"
        return SimpleNamespace(content=(
            "- **Evidence gate:** approved\n"
            "- **Report conformance:** blocked\n"
        ).encode("utf-8"))

    monkeypatch.setattr(audit, "load_storage_item", load_item)
    monkeypatch.setattr(
        audit,
        "verify_data_snapshot_integrity",
        lambda _snapshot: {"valid": True, "expected_hash": "hash", "errors": []},
    )

    payload = audit.build_indexed_report_quality_audit(str(tmp_path))

    assert payload["items"][0]["artifact_quality_summary"] == {
        "status": "present",
        "source": "markdown",
        "fields": ["report_conformance", "evidence_exit_gate"],
    }
    assert payload["artifact_quality_summary_by_status"] == {
        "present": 1,
        "not_found": 0,
        "unavailable": 0,
    }
    assert payload["artifact_quality_summary_by_field"] == {
        "report_conformance": 1,
        "evidence_exit_gate": 1,
        "content_credibility": 0,
    }


def test_report_quality_audit_artifact_field_summary_counts_all_missing_rows_before_item_pagination():
    from report_quality_audit import build_report_quality_audit

    payload = build_report_quality_audit(
        [
            {
                "ticker": "1623.TW",
                "filename": "1623_v1.html",
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
                "artifact_quality_summary": {"status": "present", "fields": ["report_conformance"]},
            },
            {
                "ticker": "2330.TW",
                "filename": "2330_v1.html",
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
                "artifact_quality_summary": {"status": "not_found", "fields": []},
            },
        ],
        scope="all_historical_indexed_reports",
        selection_basis="all_indexed_versions",
        item_limit=1,
    )

    assert payload["items_returned"] == 1
    assert payload["items_total"] == 2
    assert payload["artifact_quality_summary_by_status"] == {
        "present": 1,
        "not_found": 1,
        "unavailable": 0,
    }
    assert payload["artifact_quality_summary_by_field"] == {
        "report_conformance": 1,
        "evidence_exit_gate": 0,
        "content_credibility": 0,
    }


def test_indexed_report_quality_audit_reuses_unchanged_rows_but_refreshes_when_index_fingerprint_changes(monkeypatch, tmp_path):
    import report_quality_audit as audit

    rows = [{"ticker": "1623.TW", "filename": "1623_v1.html", "pipeline_id": "v1", "updated_at": 1}]
    calls = {"data": 0, "md": 0}
    monkeypatch.setattr(audit, "collect_all_report_pages", lambda *_args, **_kwargs: {"reports": rows})
    monkeypatch.setattr(audit, "storage_for_existing_output_dir", lambda *_args: object())

    def load_item(_storage, _filename, *, kind):
        calls[kind] += 1
        if kind == "data":
            return SimpleNamespace(content=json.dumps({
                "snapshot_hash": "hash",
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
            }))
        return SimpleNamespace(content="- **Report conformance:** blocked\n".encode("utf-8"))

    monkeypatch.setattr(audit, "load_storage_item", load_item)
    monkeypatch.setattr(
        audit,
        "verify_data_snapshot_integrity",
        lambda _snapshot: {"valid": True, "expected_hash": "hash", "errors": []},
    )

    audit.build_indexed_report_quality_audit(str(tmp_path))
    audit.build_indexed_report_quality_audit(str(tmp_path))
    assert calls == {"data": 1, "md": 1}

    rows[0]["updated_at"] = 2
    audit.build_indexed_report_quality_audit(str(tmp_path))
    assert calls == {"data": 2, "md": 2}


def test_historical_indexed_report_quality_audit_includes_every_indexed_version(monkeypatch, tmp_path):
    import report_quality_audit as audit

    calls = []
    monkeypatch.setattr(
        audit,
        "collect_all_report_pages",
        lambda list_reports, **kwargs: calls.append((list_reports, kwargs)) or {
            "reports": [{"ticker": "1623.TW", "filename": "1623_v1.html", "pipeline_id": "v1"}]
        },
    )
    monkeypatch.setattr(audit, "storage_for_existing_output_dir", lambda *_args: object())
    monkeypatch.setattr(
        audit,
        "load_storage_item",
        lambda *_args, **_kwargs: SimpleNamespace(
            content=json.dumps(
                {
                    "snapshot_hash": "hash",
                    "report_conformance": {"status": "passed"},
                    "evidence_exit_gate": {"verdict": "approved"},
                    "content_credibility": {"status": "passed"},
                }
            )
        ),
    )
    monkeypatch.setattr(
        audit,
        "verify_data_snapshot_integrity",
        lambda _snapshot: {"valid": True, "expected_hash": "hash", "errors": []},
    )
    monkeypatch.setattr(
        audit,
        "build_filtered_indexed_current_quality_summary",
        lambda *_args, **_kwargs: {
            "schema_version": "report_current_quality_summary.v1",
            "scope": "historical_filter_current_latest",
            "selection_basis": "latest_per_ticker_pipeline",
            "audited_reports": 1,
        },
    )

    payload = audit.build_historical_indexed_report_quality_audit(
        str(tmp_path),
        item_limit=0,
        q="1623.TW",
        pipeline="v2",
    )

    assert calls[0][1]["include_versions"] is True
    assert calls[0][1]["q"] == "1623.TW"
    assert calls[0][1]["pipeline"] == "v2"
    assert payload["scope"] == "all_historical_indexed_reports"
    assert payload["selection_basis"] == "all_indexed_versions"
    assert payload["audited_reports"] == 1
    assert payload["quality_metadata_coverage_pct"] == 100.0
    assert payload["current_quality_summary"]["scope"] == "historical_filter_current_latest"
    assert payload["items"] == []


def test_historical_indexed_report_quality_audit_filters_revision_review_status(monkeypatch, tmp_path):
    import report_quality_audit as audit
    import report_quality_review_workflow as review_workflow

    rows = [
        {"ticker": "1623.TW", "filename": "1623_v1.html", "pipeline_id": "v1"},
        {"ticker": "2330.TW", "filename": "2330_v1.html", "pipeline_id": "v1"},
        {"ticker": "2454.TW", "filename": "2454_v1.html", "pipeline_id": "v1"},
    ]
    reports = [
        {
            "ticker": row["ticker"],
            "filename": row["filename"],
            "pipeline_id": row["pipeline_id"],
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "content_credibility": {},
            "report_quality_revision": f"rev-{row['filename']}",
        }
        for row in rows
    ]
    reports[2].update(
        {
            "report_conformance": {"status": "passed"},
            "evidence_exit_gate": {"verdict": "approved"},
            "content_credibility": {"status": "passed"},
        }
    )
    monkeypatch.setattr(audit, "collect_all_report_pages", lambda *_args, **_kwargs: {"reports": rows})
    monkeypatch.setattr(audit, "storage_for_existing_output_dir", lambda *_args: None)
    monkeypatch.setattr(audit, "_cached_indexed_quality_reports", lambda *_args, **_kwargs: reports)

    def attach_quality_reviews(loaded, _output_dir):
        loaded[0]["quality_review"] = {"status": "approved_with_gap"}
        loaded[1]["quality_review"] = {"status": "pending"}

    monkeypatch.setattr(review_workflow, "attach_quality_reviews", attach_quality_reviews)

    payload = audit.build_historical_indexed_report_quality_audit(str(tmp_path), item_limit=5, review_status="pending")

    assert payload["review_status_filter"] == "pending"
    assert payload["audited_reports"] == 1
    assert payload["quality_review_by_status"] == {
        "pending": 1,
        "approved_with_gap": 0,
        "rejected": 0,
        "deferred": 0,
    }
    assert [item["filename"] for item in payload["items"]] == ["2330_v1.html"]


def test_historical_indexed_report_quality_audit_filters_missing_quality_field(monkeypatch, tmp_path):
    import report_quality_audit as audit

    reports = [
        {
            "ticker": "1623.TW",
            "filename": "1623_v1.html",
            "pipeline_id": "v1",
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "content_credibility": {},
        },
        {
            "ticker": "2330.TW",
            "filename": "2330_v1.html",
            "pipeline_id": "v1",
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {"status": "passed"},
            "evidence_exit_gate": {"verdict": "approved"},
            "content_credibility": {},
        },
        {
            "ticker": "2454.TW",
            "filename": "2454_v1.html",
            "pipeline_id": "v1",
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {"status": "passed"},
            "evidence_exit_gate": {"verdict": "approved"},
            "content_credibility": {"status": "passed"},
        },
    ]
    monkeypatch.setattr(audit, "collect_all_report_pages", lambda *_args, **_kwargs: {"reports": reports})
    monkeypatch.setattr(audit, "storage_for_existing_output_dir", lambda *_args: None)
    monkeypatch.setattr(audit, "_cached_indexed_quality_reports", lambda *_args, **_kwargs: reports)

    payload = audit.build_historical_indexed_report_quality_audit(
        str(tmp_path), item_limit=5, missing_field="content_credibility"
    )

    assert payload["missing_quality_field_filter"] == "content_credibility"
    assert payload["audited_reports"] == 2
    assert payload["quality_metadata_missing_reports"] == 2
    assert [item["filename"] for item in payload["items"]] == ["1623_v1.html", "2330_v1.html"]


def test_historical_indexed_report_quality_audit_combines_review_and_missing_field_filters(monkeypatch, tmp_path):
    import report_quality_audit as audit
    import report_quality_review_workflow as review_workflow

    reports = [
        {
            "ticker": "1623.TW",
            "filename": "1623_v1.html",
            "pipeline_id": "v1",
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "content_credibility": {},
        },
        {
            "ticker": "2330.TW",
            "filename": "2330_v1.html",
            "pipeline_id": "v1",
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "content_credibility": {},
        },
        {
            "ticker": "2454.TW",
            "filename": "2454_v1.html",
            "pipeline_id": "v1",
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "content_credibility": {"status": "passed"},
        },
    ]
    monkeypatch.setattr(audit, "collect_all_report_pages", lambda *_args, **_kwargs: {"reports": reports})
    monkeypatch.setattr(audit, "storage_for_existing_output_dir", lambda *_args: None)
    monkeypatch.setattr(audit, "_cached_indexed_quality_reports", lambda *_args, **_kwargs: reports)

    def attach_quality_reviews(loaded, _output_dir):
        loaded[0]["quality_review"] = {"status": "pending"}
        loaded[1]["quality_review"] = {"status": "approved_with_gap"}
        loaded[2]["quality_review"] = {"status": "pending"}

    monkeypatch.setattr(review_workflow, "attach_quality_reviews", attach_quality_reviews)

    payload = audit.build_historical_indexed_report_quality_audit(
        str(tmp_path), item_limit=5, review_status="pending", missing_field="content_credibility"
    )

    assert payload["review_status_filter"] == "pending"
    assert payload["missing_quality_field_filter"] == "content_credibility"
    assert payload["audited_reports"] == 1
    assert [item["filename"] for item in payload["items"]] == ["1623_v1.html"]


def test_historical_indexed_report_quality_audit_filters_report_version_status(monkeypatch, tmp_path):
    import report_quality_audit as audit

    historical_rows = [
        {"ticker": "1623.TW", "filename": "1623_current.html", "pipeline_id": "v2"},
        {"ticker": "1623.TW", "filename": "1623_old.html", "pipeline_id": "v2"},
        {"ticker": "1623.TW", "filename": "1623_current_complete.html", "pipeline_id": "v1"},
    ]
    latest_rows = [
        {"ticker": "1623.TW", "filename": "1623_current.html", "pipeline_id": "v2"},
        {"ticker": "1623.TW", "filename": "1623_current_complete.html", "pipeline_id": "v1"},
    ]
    reports = [
        {
            **row,
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "content_credibility": {},
        }
        for row in historical_rows
    ]
    reports[2].update(
        {
            "report_conformance": {"status": "passed"},
            "evidence_exit_gate": {"verdict": "approved"},
            "content_credibility": {"status": "passed"},
        }
    )
    loaded_rows = []

    def collect(_list_reports, **kwargs):
        return {"reports": historical_rows if kwargs["include_versions"] else latest_rows}

    monkeypatch.setattr(audit, "collect_all_report_pages", collect)
    monkeypatch.setattr(audit, "storage_for_existing_output_dir", lambda *_args: None)

    def cached(rows, *_args, **_kwargs):
        loaded_rows.append([row["filename"] for row in rows])
        filenames = {row["filename"] for row in rows}
        return [report for report in reports if report["filename"] in filenames]

    monkeypatch.setattr(audit, "_cached_indexed_quality_reports", cached)

    payload = audit.build_historical_indexed_report_quality_audit(
        str(tmp_path), item_limit=5, version_status="current"
    )

    assert payload["report_version_status_filter"] == "current"
    assert payload["audited_reports"] == 2
    assert payload["quality_metadata_missing_by_version_status"] == {"current": 1, "historical": 0, "unknown": 0}
    assert [item["filename"] for item in payload["items"]] == ["1623_current.html"]
    assert loaded_rows == [["1623_current.html", "1623_current_complete.html"]]


def test_collect_all_report_pages_follows_index_pagination():
    from report_history_pagination import collect_all_report_pages

    calls = []

    def fake_list_reports(*, page, limit, **_kwargs):
        calls.append((page, limit))
        if page == 1:
            return {"reports": [{"filename": "one.html"}, {"filename": "two.html"}], "pagination": {"total": 3}}
        return {"reports": [{"filename": "three.html"}], "pagination": {"total": 3}}

    payload = collect_all_report_pages(fake_list_reports, page_size=2, q="")

    assert calls == [(1, 2), (2, 2)]
    assert [row["filename"] for row in payload["reports"]] == ["one.html", "two.html", "three.html"]
    assert payload["pagination"]["has_next"] is False
    assert payload["pagination"]["complete"] is True

def test_collection_is_complete_accepts_legacy_true_token():
    from report_history_pagination import collection_is_complete

    assert collection_is_complete({"pagination": {"complete": "true"}}) is True
    assert collection_is_complete({"pagination": {"complete": "false"}}) is False
    assert collection_is_complete({"pagination": {}}) is True


def test_collect_all_report_pages_marks_missing_page_incomplete():
    from report_history_pagination import collect_all_report_pages

    calls = []

    def fake_list_reports(*, page, limit, **_kwargs):
        calls.append((page, limit))
        if page == 1:
            return {"reports": [{"filename": "one.html"}, {"filename": "two.html"}], "pagination": {"total": 3}}
        return {"reports": [], "pagination": {"total": 3}}

    payload = collect_all_report_pages(fake_list_reports, page_size=2, q="")

    assert calls == [(1, 2), (2, 2)]
    assert [row["filename"] for row in payload["reports"]] == ["one.html", "two.html"]
    assert payload["pagination"]["total"] == 3
    assert payload["pagination"]["complete"] is False


def test_collect_all_report_pages_marks_short_nonfinal_page_incomplete():
    from report_history_pagination import collect_all_report_pages

    def fake_list_reports(*, page, limit, **_kwargs):
        if page == 1:
            return {"reports": [{"filename": "one.html"}, {"filename": "two.html"}], "pagination": {"total": 5}}
        if page == 2:
            return {"reports": [{"filename": "three.html"}], "pagination": {"total": 5}}
        return {"reports": [{"filename": "four.html"}, {"filename": "five.html"}], "pagination": {"total": 5}}

    payload = collect_all_report_pages(fake_list_reports, page_size=2, q="")

    assert payload["pagination"]["complete"] is False


def test_indexed_report_quality_audit_rejects_incomplete_page_collection(monkeypatch, tmp_path):
    import report_quality_audit as audit

    monkeypatch.setattr(
        audit,
        "collect_all_report_pages",
        lambda *_args, **_kwargs: {
            "reports": [{"ticker": "2330.TW", "pipeline_id": "v1", "filename": "2330.html"}],
            "pagination": {"total": 2, "complete": False},
        },
    )

    payload = audit.build_indexed_report_quality_audit(str(tmp_path))

    assert payload["status"] == "unavailable"
    assert payload["error_code"] == "quality_audit_unavailable"


def test_historical_report_quality_audit_rejects_incomplete_latest_page_collection(monkeypatch, tmp_path):
    import report_quality_audit as audit

    def collect(_list_reports, **kwargs):
        if kwargs["include_versions"]:
            return {
                "reports": [{"ticker": "2330.TW", "pipeline_id": "v1", "filename": "2330.html"}],
                "pagination": {"total": 1, "complete": True},
            }
        return {
            "reports": [{"ticker": "2330.TW", "pipeline_id": "v1", "filename": "2330.html"}],
            "pagination": {"total": 2, "complete": False},
        }

    monkeypatch.setattr(audit, "collect_all_report_pages", collect)

    payload = audit.build_historical_indexed_report_quality_audit(str(tmp_path))

    assert payload["status"] == "unavailable"
    assert payload["error_code"] == "quality_audit_unavailable"


def test_report_quality_audit_item_normalizes_legacy_false_action_block_flag():
    from report_quality_audit_payload import _audit_item

    payload = _audit_item(
        {"ticker": "2330.TW", "filename": "2330.html", "report_version_status": "current"},
        {
            "title": "品質狀態需要處理",
            "detail": "請先查看品質證據。",
            "recommended_action": "manual_review",
            "severity": "warning",
            "action_label": "人工審核",
            "priority_score": 700,
            "reason_codes": [],
            "blocks_auto_rerun": "false",
        },
    )

    assert payload["blocks_auto_rerun"] is False
