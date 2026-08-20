import importlib.util
import json
from types import SimpleNamespace


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
            "after_refresh": 0,
            "no_refresh_provenance": 1,
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
                    "after_refresh": 0,
                    "no_refresh_provenance": 1,
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
                    "after_refresh": 0,
                    "no_refresh_provenance": 1,
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
                    "after_refresh": 0,
                    "no_refresh_provenance": 0,
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
        "after_refresh": 1,
        "no_refresh_provenance": 1,
    }
    assert payload["quality_metadata_by_pipeline"]["v1"]["quality_metadata_missing_by_provenance"] == {
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

    assert payload["items"][0]["title"] == "刷新後品質證據缺口"
    assert payload["items"][0]["rerun_context_status"] == "missing"
    assert payload["items"][0]["reason_codes"] == [
        "quality_metadata_missing",
        "quality_metadata_after_refresh",
        "rerun_context_missing",
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
