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
        "quality_metadata_coverage_pct": 50.0,
        "quality_metadata_coverage_basis": "verified_snapshot_reports",
        "items_returned": 1,
        "items_truncated": False,
        "items": [
            {
                "ticker": "1623.TW",
                "filename": "1623_v1.html",
                "pipeline_id": "v1",
                "title": "品質證據未記錄",
                "detail": "報告未記錄 report_conformance、evidence_exit_gate、content_credibility 品質證據，採用前需人工查看。",
                "missing_quality_fields": ["report_conformance", "evidence_exit_gate", "content_credibility"],
                "reason_codes": ["quality_metadata_missing"],
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
    assert payload["items"][0]["reason_codes"] == ["quality_metadata_missing", "quality_metadata_after_refresh"]


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
