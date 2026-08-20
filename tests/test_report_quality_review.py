import importlib


def test_report_quality_revision_ignores_index_write_and_filesystem_mtime_changes():
    from report_quality_review_workflow import report_quality_revision

    stable_row = {
        "output_dir": "/reports",
        "filename": "1623_TW_v1_report.html",
        "pipeline_id": "v1",
        "updated_at": 100.0,
        "file_mtime": 200.0,
        "data_snapshot_hash": "data-hash",
        "html_hash": "html-hash",
        "markdown_hash": "markdown-hash",
        "data_file_hash": "data-file-hash",
    }
    reindexed_row = {**stable_row, "updated_at": 300.0, "file_mtime": 400.0}
    changed_content_row = {**stable_row, "html_hash": "new-html-hash"}

    assert report_quality_revision(stable_row) == report_quality_revision(reindexed_row)
    assert report_quality_revision(stable_row) != report_quality_revision(changed_content_row)


def test_report_quality_review_store_keeps_append_only_revision_scoped_history(tmp_path, monkeypatch):
    review_store = importlib.import_module("report_quality_review_store")
    monkeypatch.setattr(review_store, "QUALITY_REVIEW_DB_PATH", str(tmp_path / "operational.sqlite3"))
    review_store.reset_report_quality_review_store_for_tests()

    first = review_store.record_review(
        output_dir=str(tmp_path / "reports"),
        filename="1623_TW_v1_report.html",
        ticker="1623.TW",
        pipeline_id="v1",
        report_quality_revision="rev-1",
        missing_quality_fields=["report_conformance", "content_credibility"],
        artifact_quality_summary={"status": "present", "source": "markdown", "fields": ["report_conformance"]},
        decision="deferred",
        note="先補看內容可信度證據。",
        reviewer_label="operator-a",
    )
    second = review_store.record_review(
        output_dir=str(tmp_path / "reports"),
        filename="1623_TW_v1_report.html",
        ticker="1623.TW",
        pipeline_id="v1",
        report_quality_revision="rev-1",
        missing_quality_fields=["report_conformance", "content_credibility"],
        artifact_quality_summary={"status": "present", "source": "markdown", "fields": ["report_conformance"]},
        decision="approved_with_gap",
        note="已核對 artifact；保留內容可信度缺口，不視為 gate 通過。",
        reviewer_label="operator-b",
    )

    latest = review_store.list_latest_reviews(
        str(tmp_path / "reports"),
        [("1623_TW_v1_report.html", "v1", "rev-1")],
    )

    assert first["decision"] == "deferred"
    assert second["decision"] == "approved_with_gap"
    assert latest[("1623_TW_v1_report.html", "v1", "rev-1")]["decision"] == "approved_with_gap"
    assert latest[("1623_TW_v1_report.html", "v1", "rev-1")]["event_count"] == 2

    history = review_store.list_review_history(
        str(tmp_path / "reports"),
        [("1623_TW_v1_report.html", "v1", "rev-1")],
    )
    events = history[("1623_TW_v1_report.html", "v1", "rev-1")]
    assert [event["event_id"] for event in events] == [second["event_id"], first["event_id"]]
    assert [event["reviewer_label"] for event in events] == ["operator-b", "operator-a"]
    assert events[0]["note"].startswith("已核對 artifact")

    old_revision = review_store.list_latest_reviews(
        str(tmp_path / "reports"),
        [("1623_TW_v1_report.html", "v1", "rev-2")],
    )
    assert old_revision == {}
    assert review_store.list_review_history(
        str(tmp_path / "reports"),
        [("1623_TW_v1_report.html", "v1", "rev-2")],
    ) == {}


def test_report_quality_review_store_rejects_missing_note_and_unknown_decision(tmp_path, monkeypatch):
    review_store = importlib.import_module("report_quality_review_store")
    monkeypatch.setattr(review_store, "QUALITY_REVIEW_DB_PATH", str(tmp_path / "operational.sqlite3"))
    review_store.reset_report_quality_review_store_for_tests()

    import pytest

    with pytest.raises(ValueError, match="unsupported review decision"):
        review_store.record_review(
            output_dir=str(tmp_path),
            filename="1623_TW_v1_report.html",
            ticker="1623.TW",
            pipeline_id="v1",
            report_quality_revision="rev-1",
            missing_quality_fields=["content_credibility"],
            artifact_quality_summary={},
            decision="approved",
            note="核對完成",
        )

    with pytest.raises(ValueError, match="review note is required"):
        review_store.record_review(
            output_dir=str(tmp_path),
            filename="1623_TW_v1_report.html",
            ticker="1623.TW",
            pipeline_id="v1",
            report_quality_revision="rev-1",
            missing_quality_fields=["content_credibility"],
            artifact_quality_summary={},
            decision="rejected",
            note="   ",
        )


def test_report_quality_audit_item_exposes_revision_and_review_state():
    from report_quality_audit import build_report_quality_audit
    from report_quality_review_store import pending_review

    payload = build_report_quality_audit(
        [
            {
                "ticker": "1623.TW",
                "filename": "1623_TW_v1_report.html",
                "pipeline_id": "v1",
                "snapshot_integrity": {"status": "verified"},
                "report_conformance": {},
                "evidence_exit_gate": {},
                "content_credibility": {},
                "report_quality_revision": "rev-1",
                "quality_review": pending_review(report_quality_revision="rev-1"),
            }
        ],
        scope="all_historical_indexed_reports",
        selection_basis="all_indexed_versions",
    )

    item = payload["items"][0]
    assert item["report_quality_revision"] == "rev-1"
    assert item["quality_review"] == {
        "status": "pending",
        "decision": "",
        "decision_label": "待人工核對",
        "reviewer_label": "",
        "note": "",
        "reviewed_at": None,
        "event_count": 0,
        "report_quality_revision": "rev-1",
    }


def test_report_quality_audit_item_exposes_revision_scoped_review_history():
    from report_quality_audit import build_report_quality_audit

    payload = build_report_quality_audit(
        [{
            "ticker": "1623.TW",
            "filename": "1623_TW_v1_report.html",
            "pipeline_id": "v1",
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "content_credibility": {},
            "report_quality_revision": "rev-2",
            "quality_review": {
                "status": "approved_with_gap",
                "decision": "approved_with_gap",
                "decision_label": "已核准保留缺口",
                "reviewer_label": "operator-b",
                "note": "保留缺口。",
                "reviewed_at": "2026-08-16T04:00:00+00:00",
                "event_count": 2,
                "event_id": 2,
                "report_quality_revision": "rev-2",
            },
            "quality_review_history": [{
                "status": "approved_with_gap",
                "decision": "approved_with_gap",
                "decision_label": "已核准保留缺口",
                "reviewer_label": "operator-b",
                "note": "保留缺口。",
                "reviewed_at": "2026-08-16T04:00:00+00:00",
                "event_count": 2,
                "event_id": 2,
                "report_quality_revision": "rev-2",
            }, {
                "status": "deferred",
                "decision": "deferred",
                "decision_label": "已暫緩",
                "reviewer_label": "operator-a",
                "note": "等待證據。",
                "reviewed_at": "2026-08-16T03:00:00+00:00",
                "event_count": 2,
                "event_id": 1,
                "report_quality_revision": "rev-2",
            }],
        }],
        scope="all_historical_indexed_reports",
        selection_basis="all_indexed_versions",
    )

    history = payload["items"][0]["quality_review_history"]
    assert [event["event_id"] for event in history] == [2, 1]
    assert history[1]["reviewer_label"] == "operator-a"
    assert history[1]["note"] == "等待證據。"


def test_report_quality_review_api_requires_current_revision_and_records_explicit_decision(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import api_routes.watchlist as watchlist_routes
    import report_quality_review_store as review_store
    from api_routes.watchlist import WatchlistRouteDeps, create_watchlist_router

    monkeypatch.setattr(review_store, "QUALITY_REVIEW_DB_PATH", str(tmp_path / "operational.sqlite3"))
    review_store.reset_report_quality_review_store_for_tests()
    target = {
        "ticker": "1623.TW",
        "filename": "1623_TW_v1_report.html",
        "pipeline_id": "v1",
        "report_quality_revision": "rev-current",
        "missing_quality_fields": ["content_credibility"],
        "artifact_quality_summary": {"status": "present", "source": "markdown", "fields": ["report_conformance"]},
        "quality_review": review_store.pending_review(report_quality_revision="rev-current"),
    }
    monkeypatch.setattr(watchlist_routes, "get_indexed_report_quality_review_target", lambda *args, **kwargs: target)
    app = FastAPI()
    app.include_router(create_watchlist_router(WatchlistRouteDeps(
        get_output_dir=lambda: str(tmp_path / "reports"),
        get_task_queue=lambda: None,
        run_stock_analysis_job=lambda *_args: "job",
        create_job=lambda *_args: "job",
        find_active_job=lambda *_args: {},
        require_mutation_authorized=lambda _request: None,
    )))

    client = TestClient(app)
    stale = client.post(
        "/api/watchlist/report-quality-audit/review",
        json={
            "filename": target["filename"],
            "pipeline_id": "v1",
            "report_quality_revision": "rev-old",
            "decision": "approved_with_gap",
            "note": "已核對",
        },
    )
    assert stale.status_code == 409

    response = client.post(
        "/api/watchlist/report-quality-audit/review",
        json={
            "filename": target["filename"],
            "pipeline_id": "v1",
            "report_quality_revision": "rev-current",
            "decision": "approved_with_gap",
            "note": "已核對 artifact；保留內容可信度缺口，不視為 gate 通過。",
            "reviewer_label": "operator-a",
        },
    )

    assert response.status_code == 200
    assert response.json()["review"]["decision"] == "approved_with_gap"
    assert response.json()["effects"] == {
        "artifact_written": False,
        "report_index_written": False,
        "rerun_enqueued": False,
    }


def test_cached_report_rows_reload_operational_review_state_after_a_new_event(tmp_path, monkeypatch):
    import report_quality_review_workflow as workflow
    import report_quality_review_store as review_store

    monkeypatch.setattr(review_store, "QUALITY_REVIEW_DB_PATH", str(tmp_path / "operational.sqlite3"))
    review_store.reset_report_quality_review_store_for_tests()
    report = {
        "ticker": "1623.TW",
        "filename": "1623_TW_v1_report.html",
        "pipeline_id": "v1",
        "snapshot_integrity": {"status": "verified"},
        "report_conformance": {},
        "evidence_exit_gate": {},
        "content_credibility": {},
        "report_quality_revision": "rev-1",
    }

    workflow.attach_quality_reviews([report], str(tmp_path / "reports"))
    assert report["quality_review"]["status"] == "pending"
    review_store.record_review(
        output_dir=str(tmp_path / "reports"),
        filename=report["filename"],
        ticker=report["ticker"],
        pipeline_id="v1",
        report_quality_revision="rev-1",
        missing_quality_fields=["content_credibility"],
        artifact_quality_summary={},
        decision="deferred",
        note="等待補充證據。",
    )
    workflow.attach_quality_reviews([report], str(tmp_path / "reports"))
    assert report["quality_review"]["status"] == "deferred"
