from report_current_quality_summary import build_current_quality_summary


def test_current_quality_summary_keeps_gate_distributions_separate_and_bounds_targets():
    payload = build_current_quality_summary(
        [
            {
                "ticker": "2330.TW",
                "pipeline_id": "v1",
                "filename": "2330.html",
                "report_conformance": {"status": "warning", "warnings": [{"message": "需要人工注意"}]},
                "content_credibility": {"status": "warning"},
                "evidence_exit_gate": {
                    "verdict": "caution",
                    "unverifiable_reason_counts": {"no_matching_snapshot_path": 2},
                },
            },
            {
                "ticker": "2454.TW",
                "pipeline_id": "v2",
                "filename": "2454.html",
                "report_conformance": {
                    "status": "blocked",
                    "decision_tree": [
                        {"id": "final_audit", "status": "blocked"},
                        {"id": "report_lint", "status": "warning"},
                    ],
                    "blocking_issues": [
                        {"id": "final_audit", "message": "證據矛盾"},
                        {"id": "final_audit", "message": "重複的證據矛盾"},
                    ],
                },
                "content_credibility": {
                    "status": "blocked",
                    "blocking_issues": [
                        {"id": "explicit_target_price_low_data_confidence"},
                        {"id": "explicit_target_price_low_data_confidence"},
                    ],
                    "checks": [{"id": "trade_setup_alignment", "status": "warning"}],
                },
                "decision_freshness": {"status": "needs_rerun", "requires_rerun": True},
                "evidence_exit_gate": {
                    "verdict": "rejected",
                    "failed_count": 1,
                    "unverifiable_reason_counts": {"missing_semantic_path": 1},
                },
            },
            {
                "ticker": "2308.TW",
                "pipeline_id": "v1",
                "filename": "2308.html",
                "report_conformance": {"status": "passed"},
                "content_credibility": {"status": "passed"},
                "evidence_exit_gate": {"verdict": "approved"},
            },
        ],
        scope="all_indexed_reports",
        item_limit=1,
    )

    assert payload["schema_version"] == "report_current_quality_summary.v1"
    assert payload["selection_basis"] == "latest_per_ticker_pipeline"
    assert payload["audited_reports"] == 3
    assert payload["report_conformance_by_status"] == {"passed": 1, "warning": 1, "blocked": 1, "unknown": 0}
    assert payload["content_credibility_by_status"] == {"passed": 1, "warning": 1, "blocked": 1, "unknown": 0}
    assert payload["evidence_exit_gate_by_verdict"] == {"approved": 1, "caution": 1, "rejected": 1, "unknown": 0}
    assert payload["evidence_unverifiable_reason_counts"] == {
        "no_matching_snapshot_path": 2,
        "missing_semantic_path": 1,
    }
    assert payload["evidence_mismatch_claims_by_freshness"] == {
        "current": 0,
        "needs_rerun": 1,
        "unknown": 0,
    }
    assert payload["evidence_mismatch_reports_by_freshness"] == {
        "current": 0,
        "needs_rerun": 1,
        "unknown": 0,
    }
    assert payload["evidence_failed_count"] == 1
    assert payload["report_conformance_blocker_counts"] == {"final_audit": 1}
    assert payload["content_credibility_blocker_counts"] == {
        "explicit_target_price_low_data_confidence": 1,
    }
    assert payload["non_passed_reports"] == 2
    assert payload["items_returned"] == 1
    assert payload["items_truncated"] is True
    assert payload["items"][0]["filename"] == "2454.html"
    assert payload["items"][0]["reason"] == "證據矛盾"
    assert payload["items"][0]["evidence_failed_count"] == 1
    assert payload["items"][0]["evidence_unverifiable_reason_counts"] == {"missing_semantic_path": 1}
    assert payload["items"][0]["evidence_mismatch_freshness_status"] == "needs_rerun"


def test_current_quality_summary_treats_missing_gate_status_as_unknown():
    payload = build_current_quality_summary(
        [{"ticker": "2330.TW", "filename": "2330.html", "pipeline_id": "v1"}],
        scope="daily_report_sample",
    )

    assert payload["report_conformance_by_status"] == {"passed": 0, "warning": 0, "blocked": 0, "unknown": 1}
    assert payload["content_credibility_by_status"] == {"passed": 0, "warning": 0, "blocked": 0, "unknown": 1}
    assert payload["evidence_exit_gate_by_verdict"] == {"approved": 0, "caution": 0, "rejected": 0, "unknown": 1}
    assert payload["items_total"] == 1
    assert payload["items"][0]["report_conformance_status"] == "unknown"


def test_current_quality_summary_uses_blocked_check_when_content_issue_ids_are_missing():
    payload = build_current_quality_summary(
        [{
            "ticker": "2330.TW",
            "filename": "2330.html",
            "report_conformance": {"status": "passed"},
            "content_credibility": {
                "status": "blocked",
                "checks": [{"id": "blocked_check", "status": "blocked"}],
            },
            "evidence_exit_gate": {"verdict": "approved"},
        }],
        scope="all_indexed_reports",
    )

    assert payload["content_credibility_blocker_counts"] == {"blocked_check": 1}


def test_filtered_indexed_current_quality_summary_has_explicit_latest_scope(monkeypatch, tmp_path):
    import report_current_quality_summary as current_quality

    monkeypatch.setattr(
        current_quality,
        "collect_all_report_pages",
        lambda _list_reports, **kwargs: {
            "reports": [{
                "ticker": "2330.TW",
                "pipeline_id": "v2",
                "filename": "2330.html",
                "report_conformance": {"status": "warning"},
                "content_credibility": {"status": "warning"},
                "evidence_exit_gate": {"verdict": "caution"},
            }],
            "pagination": {"total": 1},
        },
    )

    payload = current_quality.build_filtered_indexed_current_quality_summary(
        str(tmp_path), q="2330.TW", pipeline="v2", item_limit=0
    )

    assert payload["schema_version"] == "report_current_quality_summary.v1"
    assert payload["scope"] == "historical_filter_current_latest"
    assert payload["selection_basis"] == "latest_per_ticker_pipeline"
    assert payload["filters"] == {"q": "2330.TW", "pipeline": "v2"}
    assert payload["audited_reports"] == 1
    assert payload["non_passed_reports"] == 1
    assert payload["items_returned"] == 0
