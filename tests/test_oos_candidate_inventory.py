from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from data_trust_snapshot_integrity import set_snapshot_integrity
from oos_candidate_inventory import finalize_inventory, planned_candidates, seal_ready
from oos_research.canonical import canonical_bytes, content_hash
from oos_research.manifest import build_manifest
from oos_research.policies import DEFAULT_POLICIES
from oos_research.store import StoreError
from report_paths import (
    report_markdown_filename_for_report,
    report_storage_key_for_filename,
)
from data_trust import data_snapshot_filename_for_report
from storage.report_storage import LocalFileStorage


TICKERS = ["1623.TW", "2308.TW", "2367.TW", "3017.TW", "3324.TWO", "3653.TW", "6282.TW"]
PIPELINES = ["v1", "v2", "v3", "v4"]


def _scope():
    jobs = []
    for ticker in TICKERS:
        for pipeline in PIPELINES:
            jobs.append({
                "ticker": ticker,
                "pipeline_id": pipeline,
                "source_filename": f"old-{ticker}-{pipeline}.html",
                "requires_rerun": True,
                "requires_rerun_reason": "stale",
                "status": "not_submitted",
            })
    return {
        "schema_version": "stock-agent.report-rebuild-prepare-indexed.v1",
        "prepare_only": True,
        "refresh_candidate_count": 28,
        "jobs": jobs,
    }


def _scope_rows(scope):
    return [{key: row[key] for key in (
        "ticker", "pipeline_id", "source_filename", "requires_rerun", "requires_rerun_reason"
    )} for row in scope["jobs"]]


def _manifest(scope):
    source_hash = hashlib.sha256(canonical_bytes(scope)).hexdigest()
    policies = dict(DEFAULT_POLICIES)
    policies.update({
        "cohort_source_manifest_sha256": source_hash,
        "cohort_candidate_count": 28,
    })
    return build_manifest(
        schema_version="oos.manifest.v1",
        study_id="four-mode-credibility-prospective-r1",
        study_kind="prospective",
        registered_at="2026-09-08T00:00:00Z",
        timezone="Asia/Taipei",
        selection_period={"start": "2026-09-09", "end": "2026-09-11"},
        ticker_universe=TICKERS,
        pipelines=PIPELINES,
        horizons={"v1": [3, 6, 12], "v2": [5], "v3": [5], "v4": [5, 10]},
        policies=policies,
        evaluator_version="oos.evaluator.v1",
        runtime_identity={
            "prompt_fingerprint": "a" * 64,
            "model_route_policy_sha256": "b" * 64,
        },
    )


def _submission(scope, *, job_id="job-1"):
    rows = _scope_rows(scope)
    scope_hash = hashlib.sha256(canonical_bytes(rows)).hexdigest()
    jobs = [dict(row) for row in scope["jobs"]]
    jobs[0].update({"job_id": job_id, "status": "completed", "submission_state": "accepted"})
    return {
        "schema_version": "stock-agent.report-rebuild-authorized.v1",
        "prepare_only": False,
        "authorization": {
            "source_manifest_sha256": hashlib.sha256(canonical_bytes(scope)).hexdigest(),
            "candidate_count": 28,
            "scope_sha256": scope_hash,
        },
        "jobs": jobs,
    }


def _write_report_bundle(report_root: Path, filename: str):
    quality = {"status": "sufficient", "score": 90}
    packet = {
        "prompt_fingerprint": "a" * 64,
        "code_commit": "c" * 40,
        "code_dirty": False,
        "model_id": "gemini-test",
        "model_executions": [{"agent_num": 16, "model_id": "gemini-test"}],
        "model_revision_unknown": True,
        "model_route_policy_sha256": "b" * 64,
        "analysis_input_cutoff": "2026-09-09T01:00:00Z",
        "analysis_input_hash": "d" * 64,
        "input_first_available_at": "",
        "source_publication_at": "",
        "source_provenance_coverage": "incomplete",
    }
    snapshot = {
        "ticker": TICKERS[0],
        "pipeline": "v1",
        "conclusion_generated_at": "2026-09-09T01:30:00Z",
        "reproducibility_packet": packet,
        "oos_evaluation_inputs": {
            "pipeline_id": "v1",
            "recommendation": {"建議": "買入", "短期目標（3個月）": "NT$100"},
        },
        "data_trust": quality,
        "report_lint": {},
        "evidence_exit_gate": {},
        "content_credibility": {},
        "report_conformance": {},
        "final_audit": {},
    }
    set_snapshot_integrity(snapshot)
    storage = LocalFileStorage(report_root)
    html_key = report_storage_key_for_filename(filename)
    prefix = html_key.rsplit("/", 1)[0]
    storage.save_report(html_key, b"<html>sealed</html>", content_type="text/html")
    storage.save_report(
        f"{prefix}/{report_markdown_filename_for_report(filename)}",
        b"# sealed",
        content_type="text/markdown",
    )
    storage.save_report(
        f"{prefix}/{data_snapshot_filename_for_report(filename)}",
        json.dumps(snapshot, ensure_ascii=False).encode(),
        content_type="application/json",
    )


def _operational_db(path: Path, filename: str, *, duplicate_done=False):
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE analysis_jobs (job_id TEXT, ticker TEXT, pipeline_id TEXT, status TEXT, filename TEXT)"
        )
        connection.execute("CREATE TABLE analysis_events (id INTEGER PRIMARY KEY, job_id TEXT, payload TEXT, created_at REAL)")
        connection.execute(
            "INSERT INTO analysis_jobs VALUES (?, ?, ?, ?, ?)",
            ("job-1", TICKERS[0], "v1", "done", filename),
        )
        event = json.dumps({"type": "report_done", "pipeline_id": "v1", "filename": filename})
        connection.execute("INSERT INTO analysis_events VALUES (1, ?, ?, ?)", ("job-1", event, 1788915600.0))
        if duplicate_done:
            connection.execute("INSERT INTO analysis_events VALUES (2, ?, ?, ?)", ("job-1", event, 1788915601.0))


def test_planned_candidates_requires_exact_attested_28_cross_product():
    scope = _scope()
    manifest = _manifest(scope)
    assert len(planned_candidates(scope, manifest)) == 28
    scope["jobs"].pop()
    with pytest.raises(ValueError, match="28-candidate"):
        planned_candidates(scope, manifest)


def test_first_session_after_report_respects_twse_open_time():
    from oos_research.calendar import first_session_after_timestamp

    sessions = ["2026-09-09", "2026-09-10"]
    assert first_session_after_timestamp(
        sessions, "2026-09-09T08:59:59+08:00", timezone_name="Asia/Taipei"
    ).isoformat() == "2026-09-09"
    assert first_session_after_timestamp(
        sessions, "2026-09-09T09:00:00+08:00", timezone_name="Asia/Taipei"
    ).isoformat() == "2026-09-10"


def test_seal_ready_copies_one_completed_bundle_to_immutable_store_and_keeps_denominator(tmp_path):
    scope = _scope()
    manifest = _manifest(scope)
    submission = _submission(scope)
    filename = f"{TICKERS[0]}_v1_report_20260909_093000.html"
    report_root = tmp_path / "formal-output"
    _write_report_bundle(report_root, filename)
    db = tmp_path / "operational.sqlite3"
    _operational_db(db, filename)

    status = seal_ready(
        manifest=manifest,
        scope=scope,
        submission=submission,
        operational_db=db,
        report_root=report_root,
        sessions=["2026-09-09", "2026-09-10", "2026-09-11"],
        study_root=tmp_path / "prospective-study",
    )

    assert status == {"planned": 28, "sealed": 1, "pending": 27, "issues": {}}
    inventory = finalize_inventory(
        manifest=manifest,
        scope=scope,
        submission=submission,
        study_root=tmp_path / "prospective-study",
        registration_evidence=None,
        selection_closed=False,
    )
    assert len(inventory["candidates"]) == 28
    assert inventory["coverage_status"] == "incomplete"
    sealed = inventory["candidates"][0]
    assert sealed["report"]["targets_by_horizon"]["3"] == 100.0
    assert sealed["admission_status"] == "insufficient_provenance"
    assert "source_provenance_incomplete" in sealed["admission_reasons"]
    assert inventory["candidates"][1]["admission_status"] == "missing_report"


def test_seal_rejects_duplicate_report_done_and_job_identity_mismatch(tmp_path):
    scope = _scope()
    manifest = _manifest(scope)
    submission = _submission(scope)
    filename = f"{TICKERS[0]}_v1_report_20260909_093000.html"
    report_root = tmp_path / "formal-output"
    _write_report_bundle(report_root, filename)
    db = tmp_path / "operational.sqlite3"
    _operational_db(db, filename, duplicate_done=True)
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE analysis_jobs SET ticker = 'WRONG.TW'")

    status = seal_ready(
        manifest=manifest,
        scope=scope,
        submission=submission,
        operational_db=db,
        report_root=report_root,
        sessions=["2026-09-09", "2026-09-10"],
        study_root=tmp_path / "study",
    )
    assert status["sealed"] == 0
    assert status["issues"] == {"candidate-01-1623-tw-v1": "ValueError"}


def test_finalize_rejects_tampered_content_addressed_blob(tmp_path):
    scope = _scope()
    manifest = _manifest(scope)
    submission = _submission(scope)
    filename = f"{TICKERS[0]}_v1_report_20260909_093000.html"
    report_root = tmp_path / "formal-output"
    _write_report_bundle(report_root, filename)
    db = tmp_path / "operational.sqlite3"
    _operational_db(db, filename)
    study = tmp_path / "study"
    seal_ready(
        manifest=manifest,
        scope=scope,
        submission=submission,
        operational_db=db,
        report_root=report_root,
        sessions=["2026-09-09", "2026-09-10"],
        study_root=study,
    )
    record = json.loads((study / "records/candidate-01-1623-tw-v1.json").read_text())
    digest = record["payload"]["artifacts"]["html"]["sha256"]
    (study / "blobs" / digest).write_bytes(b"tampered")

    with pytest.raises(StoreError, match="blob"):
        finalize_inventory(
            manifest=manifest,
            scope=scope,
            submission=submission,
            study_root=study,
            registration_evidence=None,
            selection_closed=False,
        )
