import importlib.util


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
        "audited_reports": 3,
        "verified_snapshot_reports": 2,
        "quality_metadata_complete_reports": 1,
        "quality_metadata_missing_reports": 1,
        "quality_metadata_coverage_pct": 50.0,
        "items": [
            {
                "ticker": "1623.TW",
                "filename": "1623_v1.html",
                "pipeline_id": "v1",
                "title": "品質證據未記錄",
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
