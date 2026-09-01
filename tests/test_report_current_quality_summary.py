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
    assert payload["evidence_unverifiable_reason_counts_by_freshness"] == {
        "current": {},
        "needs_rerun": {"missing_semantic_path": 1},
        "unknown": {"no_matching_snapshot_path": 2},
    }
    assert payload["evidence_unverifiable_reports_by_freshness"] == {
        "current": 0,
        "needs_rerun": 1,
        "unknown": 1,
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
    assert payload["content_credibility_blocker_reports_by_freshness"] == {
        "current": 0,
        "needs_rerun": 1,
        "unknown": 0,
    }
    assert payload["items"][0]["content_credibility_blocker_ids"] == [
        "explicit_target_price_low_data_confidence",
    ]
    assert payload["items"][0]["content_credibility_freshness_status"] == "needs_rerun"
    assert payload["non_passed_reports"] == 2
    assert payload["items_returned"] == 1
    assert payload["items_truncated"] is True
    assert payload["items"][0]["filename"] == "2454.html"
    assert payload["items"][0]["reason"] == "證據矛盾"
    assert payload["items"][0]["evidence_failed_count"] == 1
    assert payload["items"][0]["evidence_unverifiable_reason_counts"] == {"missing_semantic_path": 1}
    assert payload["items"][0]["evidence_unverifiable_freshness_status"] == "needs_rerun"
    assert payload["items"][0]["evidence_mismatch_freshness_status"] == "needs_rerun"


def test_current_quality_summary_uses_canonical_unverifiable_count_when_reason_map_is_missing():
    payload = build_current_quality_summary(
        [{
            "ticker": "2330.TW",
            "pipeline_id": "v1",
            "filename": "2330.html",
            "decision_freshness": {"status": "current"},
            "report_conformance": {"status": "passed"},
            "content_credibility": {"status": "passed"},
            "evidence_exit_gate": {"verdict": "caution", "unverifiable_count": 2},
        }],
        scope="all_indexed_reports",
    )

    assert payload["evidence_unverifiable_claims_by_freshness"] == {
        "current": 2,
        "needs_rerun": 0,
        "unknown": 0,
    }
    assert payload["evidence_unverifiable_reports_by_freshness"] == {
        "current": 1,
        "needs_rerun": 0,
        "unknown": 0,
    }
    assert payload["items"][0]["evidence_unverifiable_count"] == 2
    assert payload["items"][0]["evidence_unverifiable_freshness_status"] == "current"


def test_current_quality_items_follow_action_priority_within_attention_level():
    payload = build_current_quality_summary(
        [
            {
                "ticker": "2330.TW",
                "filename": "z-content-manual.html",
                "pipeline_id": "v1",
                "report_conformance": {"status": "passed"},
                "content_credibility": {"status": "blocked", "summary": "目標價與建議矛盾。"},
                "evidence_exit_gate": {"verdict": "approved"},
            },
            {
                "ticker": "2367.TW",
                "filename": "a-agent-rerun.html",
                "pipeline_id": "v2",
                "report_conformance": {"status": "passed"},
                "content_credibility": {
                    "status": "blocked",
                    "blocking_issues": [{
                        "id": "final_audit_critical",
                        "details": {"critical": ["缺少 Agent 輸出：7"]},
                    }],
                },
                "evidence_exit_gate": {"verdict": "approved"},
            },
            {
                "ticker": "3017.TW",
                "filename": "b-conformance-manual.html",
                "pipeline_id": "v1",
                "report_conformance": {
                    "status": "blocked",
                    "blocking_issues": [{
                        "id": "final_audit",
                        "details": ["主力籌碼分析師：公司身分污染。"],
                    }],
                },
                "content_credibility": {"status": "passed"},
                "evidence_exit_gate": {"verdict": "approved"},
            },
        ],
        scope="all_indexed_reports",
        item_limit=3,
    )

    assert payload["items_sort_basis"] == "quality_attention_then_action_priority_then_filename"
    assert [item["filename"] for item in payload["items"]] == [
        "z-content-manual.html",
        "b-conformance-manual.html",
        "a-agent-rerun.html",
    ]


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


def test_current_quality_item_exposes_deduplicated_canonical_content_blocker_messages():
    payload = build_current_quality_summary(
        [{
            "ticker": "2330.TW",
            "filename": "2330.html",
            "report_conformance": {"status": "blocked", "blocking_issues": [{"message": "需要人工查看"}]},
            "content_credibility": {
                "status": "blocked",
                "blocking_issues": [
                    {
                        "id": "final_audit_critical",
                        "message": "最終稽核仍有重大問題。",
                        "details": {"critical": ["Agent 7 輸出失敗。", "Agent 7 輸出失敗。"]},
                    },
                    {
                        "id": "long_target_not_above_current_price",
                        "message": "偏多交易的目標價未高於目前股價。",
                    },
                ],
            },
            "evidence_exit_gate": {"verdict": "approved"},
        }],
        scope="all_indexed_reports",
    )

    assert payload["items"][0]["content_credibility_blocker_messages"] == [
        "Agent 7 輸出失敗。",
        "偏多交易的目標價未高於目前股價。",
    ]
    assert payload["items"][0]["quality_action"]["detail"] == "Agent 7 輸出失敗。"


def test_current_quality_summary_includes_content_attention_when_conformance_passes():
    payload = build_current_quality_summary(
        [{
            "ticker": "2330.TW",
            "filename": "2330.html",
            "report_conformance": {"status": "passed"},
            "content_credibility": {
                "status": "blocked",
                "blocking_issues": [{
                    "id": "final_audit_critical",
                    "message": "最終稽核仍有重大問題。",
                    "details": {"critical": ["Agent 7 輸出失敗。"]},
                }],
            },
            "evidence_exit_gate": {"verdict": "approved"},
        }],
        scope="all_indexed_reports",
    )

    assert payload["non_passed_reports"] == 1
    assert payload["items_total"] == 1
    assert payload["items"][0]["content_credibility_status"] == "blocked"


def test_current_quality_item_exposes_shared_quality_action_for_content_blocker():
    payload = build_current_quality_summary(
        [{
            "ticker": "2330.TW",
            "filename": "2330.html",
            "report_conformance": {"status": "passed"},
            "content_credibility": {
                "status": "blocked",
                "summary": "目標價與資料信心門檻互相矛盾。",
            },
            "evidence_exit_gate": {"verdict": "approved"},
        }],
        scope="all_indexed_reports",
    )

    assert payload["quality_gate_action_counts"] == {"manual_review": 1}
    assert payload["quality_gate_action_scope"] == {
        "scope": "all_indexed_reports",
        "selection_basis": "latest_per_ticker_pipeline",
        "basis": "quality_gate_repair_item_per_report",
        "is_daily_queue": False,
    }
    assert payload["items"][0]["quality_action"] == {
        "recommended_action": "manual_review",
        "action_label": "人工審核",
        "title": "內容可信度未通過",
        "detail": "目標價與資料信心門檻互相矛盾。",
        "reason_codes": ["content_credibility_blocked"],
        "blocks_auto_rerun": True,
    }


def test_current_quality_item_exposes_rerun_action_for_retryable_final_audit():
    payload = build_current_quality_summary(
        [{
            "ticker": "2330.TW",
            "filename": "2330.html",
            "report_conformance": {
                "status": "blocked",
                "blocking_issues": [{
                    "id": "final_audit",
                    "details": ["技術動能分析師 輸出為失敗訊息，不能產生正式報告。"],
                }],
            },
            "content_credibility": {"status": "passed"},
            "evidence_exit_gate": {"verdict": "approved"},
        }],
        scope="all_indexed_reports",
    )

    assert payload["items"][0]["quality_action"]["recommended_action"] == "rerun_analysis"
    assert payload["items"][0]["quality_action"]["action_label"] == "完整重跑"
    assert payload["items"][0]["quality_action"]["blocks_auto_rerun"] is False
    assert payload["items"][0]["quality_action"]["reason_codes"] == ["final_audit_agent_retry"]


def test_current_quality_item_exposes_rerun_action_for_content_final_audit_failure():
    payload = build_current_quality_summary(
        [{
            "ticker": "2367.TW",
            "filename": "2367_v2.html",
            "pipeline_id": "v2",
            "report_conformance": {"status": "passed"},
            "content_credibility": {
                "status": "blocked",
                "blocking_issues": [{
                    "id": "final_audit_critical",
                    "details": {"critical": ["缺少 Agent 輸出：7"]},
                }],
            },
            "evidence_exit_gate": {"verdict": "approved"},
        }],
        scope="all_indexed_reports",
    )

    assert payload["quality_gate_action_counts"] == {"rerun_analysis": 1}
    assert payload["items"][0]["quality_action"] == {
        "recommended_action": "rerun_analysis",
        "action_label": "完整重跑",
        "title": "Agent 輸出失敗，建議重跑",
        "detail": "缺少 Agent 輸出：7",
        "reason_codes": ["final_audit_agent_retry"],
        "blocks_auto_rerun": False,
    }


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
