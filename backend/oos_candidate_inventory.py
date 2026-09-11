"""Bridge formal job artifacts into an immutable prospective OOS inventory."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Sequence

from data_trust_snapshot_integrity import verify_data_snapshot_integrity
from oos_candidate_json import load_unique_json
from price_parser import extract_target_price_numbers
from recommendation_labels import normalize_recommendation_label
from oos_research.admission import evaluate_candidate
from oos_research.calendar import first_session_after_timestamp
from oos_research.canonical import canonical_bytes, content_hash
from oos_research.inventory import validate_inventory
from oos_research.manifest import validate_manifest
from oos_research.records import make_record
from oos_research.store import StoreError, StudyStore
from report_artifacts import ReportArtifactLocator
from storage.report_storage import LocalFileStorage


TERMINAL_STATUSES = {"done", "error", "cancelled", "completed", "failed"}
PIPELINES = ("v1", "v2", "v3", "v4")


def planned_candidates(scope: Mapping[str, Any], manifest: Mapping[str, Any]) -> list[dict[str, str]]:
    validate_manifest(manifest)
    jobs = scope.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("scope jobs must be a list")
    identities = [(row.get("ticker"), row.get("pipeline_id")) for row in jobs if isinstance(row, Mapping)]
    if any(not isinstance(ticker, str) or not isinstance(pipeline, str) for ticker, pipeline in identities):
        raise ValueError("scope candidate identity is invalid")
    expected = [(ticker, pipeline) for ticker in manifest["ticker_universe"] for pipeline in manifest["pipelines"]]
    if len(identities) != len(jobs) or len(identities) != 28 or set(identities) != set(expected):
        raise ValueError("scope must equal the attested 28-candidate universe")
    if len(set(identities)) != len(identities):
        raise ValueError("scope contains duplicate candidates")
    return [{"candidate_id": _candidate_id(index, ticker, pipeline), "ticker": ticker,
             "pipeline_id": pipeline} for index, (ticker, pipeline) in enumerate(expected, 1)]


def seal_ready(
    *, manifest: Mapping[str, Any], scope: Mapping[str, Any], submission: Mapping[str, Any],
    operational_db: str | Path, report_root: str | Path, sessions: Sequence[str],
    study_root: str | Path,
) -> dict[str, Any]:
    planned = planned_candidates(scope, manifest)
    submitted = _submission_rows(submission, planned, manifest)
    policies = manifest.get("policies")
    policies = policies if isinstance(policies, Mapping) else {}
    session_open = _text(policies.get("session_open_local_time")) or "09:00:00"
    store = StudyStore(study_root, study_id=manifest["study_id"])
    store.register_manifest(manifest)
    storage = LocalFileStorage(report_root)
    locator = ReportArtifactLocator(storage)
    sealed, pending, issues = 0, 0, {}
    with _read_only_db(operational_db) as connection:
        for row in planned:
            if _record_exists(store, row["candidate_id"]):
                sealed += 1
                continue
            submitted_row = submitted[(row["ticker"], row["pipeline_id"])]
            job_id = str(submitted_row.get("job_id") or "").strip()
            job = _job(connection, job_id) if job_id else None
            if not job or job["status"] != "done":
                pending += 1
                continue
            try:
                candidate = _seal_candidate(
                    connection, storage, locator, store, row, job, sessions,
                    timezone_name=manifest["timezone"], session_open=session_open,
                )
                store.put_record(make_record("candidate_seal", row["candidate_id"], candidate,
                                             created_at=candidate["sealed_at"]))
                sealed += 1
            except (OSError, ValueError, StoreError, sqlite3.Error) as exc:
                issues[row["candidate_id"]] = type(exc).__name__
    return {"planned": len(planned), "sealed": sealed, "pending": pending, "issues": issues}


def finalize_inventory(
    *, manifest: Mapping[str, Any], scope: Mapping[str, Any], submission: Mapping[str, Any],
    study_root: str | Path, registration_evidence: Mapping[str, Any] | None,
    selection_closed: bool,
) -> dict[str, Any]:
    planned = planned_candidates(scope, manifest)
    submitted = _submission_rows(submission, planned, manifest)
    store = StudyStore(study_root, study_id=manifest["study_id"], create=False)
    store.register_manifest(manifest)
    candidates = []
    all_resolved = True
    runtime = manifest.get("runtime_identity")
    runtime = runtime if isinstance(runtime, Mapping) else {}
    policies = manifest.get("policies")
    policies = policies if isinstance(policies, Mapping) else {}
    for row in planned:
        if _record_exists(store, row["candidate_id"]):
            candidate = _inflate_candidate(store, store.read_record(row["candidate_id"])["payload"])
        else:
            submitted_row = submitted[(row["ticker"], row["pipeline_id"])]
            status = str(submitted_row.get("status") or "not_submitted")
            all_resolved = all_resolved and status in TERMINAL_STATUSES
            candidate = {**row, "report": None, "artifacts": {}, "lifecycle": {
                "job_id": submitted_row.get("job_id"), "status": status,
                "error": submitted_row.get("error"),
            }}
        admission = evaluate_candidate(
            candidate, study_kind=manifest["study_kind"], registration_evidence=registration_evidence,
            manifest_sha256=manifest["manifest_sha256"], timezone_name=manifest["timezone"],
            expected_code_commit=_text(runtime.get("attested_source_commit")),
            expected_prompt_fingerprint=_text(runtime.get("prompt_fingerprint")),
            expected_model_route_policy_sha256=_text(runtime.get("model_route_policy_sha256")),
            selection_period=manifest["selection_period"], expected_horizons=manifest["horizons"],
            session_open_local_time=_text(policies.get("session_open_local_time")) or "09:00:00",
        )
        candidate["admission_status"] = admission["status"]
        candidate["admission_reasons"] = admission["reason_codes"]
        candidates.append(candidate)
    inventory = {"coverage_status": "closed" if all_resolved or selection_closed else "incomplete",
                 "candidates": candidates}
    inventory["inventory_sha256"] = content_hash(inventory)
    validate_inventory(inventory)
    return inventory


def _seal_candidate(
    connection, storage, locator, store, planned, job, sessions, *, timezone_name, session_open,
):
    if job.get("ticker") != planned["ticker"] or job.get("pipeline_id") != planned["pipeline_id"]:
        raise ValueError("job identity differs from planned candidate")
    events = _events(connection, job["job_id"])
    done = [row for row in events if row["payload"].get("type") == "report_done"
            and row["payload"].get("pipeline_id") == planned["pipeline_id"]]
    if len(done) != 1:
        raise ValueError("candidate requires exactly one pipeline report_done event")
    filename = str(done[0]["payload"].get("filename") or "")
    if not filename or filename != str(job.get("filename") or ""):
        raise ValueError("job/report filename mismatch")
    bundle = locator.require_bundle(filename)
    contents = {
        "html": _content(storage, bundle.html_key),
        "markdown": _content(storage, bundle.markdown_key),
        "snapshot": _content(storage, bundle.data_key),
    }
    snapshot = load_unique_json(contents["snapshot"])
    integrity = verify_data_snapshot_integrity(snapshot)
    if not integrity.get("valid") or not integrity.get("hash"):
        raise ValueError("snapshot integrity failed")
    evaluation_inputs = snapshot.get("oos_evaluation_inputs")
    if not isinstance(evaluation_inputs, Mapping):
        raise ValueError("OOS evaluation inputs are missing")
    contents["parsed_plan"] = canonical_bytes(dict(evaluation_inputs))
    artifact_refs = {name: {"sha256": store.put_blob(value), "size_bytes": len(value)}
                     for name, value in contents.items()}
    sealed_at = _utc_now()
    packet = snapshot.get("reproducibility_packet")
    packet = packet if isinstance(packet, Mapping) else {}
    created_at = done[0]["created_at"]
    if isinstance(created_at, bool) or not isinstance(created_at, (int, float)) or not math.isfinite(created_at):
        raise ValueError("report_done time is invalid")
    report_available_at = datetime.fromtimestamp(created_at, timezone.utc).isoformat()
    first_session = first_session_after_timestamp(
        sessions, report_available_at, timezone_name=timezone_name, session_open=session_open,
    )
    quality = {key: snapshot.get(key) for key in (
        "data_trust", "report_lint", "evidence_exit_gate", "content_credibility",
        "report_conformance", "final_audit",
    )}
    report = {key: packet.get(key) for key in (
        "prompt_fingerprint", "code_commit", "code_dirty", "model_id", "model_executions",
        "model_revision_unknown", "model_route_policy_sha256", "analysis_input_cutoff",
        "analysis_input_hash", "input_first_available_at", "source_publication_at",
        "source_provenance_coverage",
    )}
    report.update({"ticker": planned["ticker"], "pipeline_id": planned["pipeline_id"],
                   "data_snapshot_hash": integrity["hash"],
                   "conclusion_generated_at": snapshot.get("conclusion_generated_at"),
                   "report_available_at": report_available_at, "quality_metadata": quality,
                   "quality_metadata_hash": content_hash(quality), **_decision_projection(evaluation_inputs)})
    return {**planned, "job_id": job["job_id"], "sealed_at": sealed_at,
            "first_session_date": first_session.isoformat() if first_session else None,
            "report": report, "artifacts": artifact_refs,
            "event_ledger_sha256": content_hash(events)}


def _decision_projection(inputs: Mapping[str, Any]) -> dict[str, Any]:
    recommendation = inputs.get("recommendation")
    recommendation = recommendation if isinstance(recommendation, Mapping) else {}
    label = normalize_recommendation_label(
        recommendation.get("建議", recommendation.get("recommendation"))
    )
    pipeline = inputs.get("pipeline_id")
    field = {"v2": "position_plan", "v3": "short_setup", "v4": "trade_setup"}.get(pipeline)
    plan = inputs.get(field) if field else None
    targets = {
        "3": _single_target(recommendation.get("短期目標（3個月）")),
        "6": _single_target(recommendation.get("中期目標（6個月）")),
        "12": _single_target(recommendation.get("長期目標（12個月）")),
    }
    if pipeline == "v1":
        return {"recommendation": label, "targets_by_horizon": targets}
    plan = dict(plan) if isinstance(plan, Mapping) else None
    if pipeline == "v2" and plan is not None:
        action = plan.get("action")
        direction = "Neutral" if action == "等待" else (
            "Short" if action == "進場" and label == "放空" else
            "Long" if action == "進場" and label == "買入" else "Unknown"
        )
        if direction == "Neutral":
            plan["observation_reason"] = plan.get("invalidation_condition")
    elif pipeline == "v3" and plan is not None:
        direction = "Short" if label == "放空" else "Neutral" if label in {"避免", "持有", "買入"} else "Unknown"
        plan = {
            **plan,
            "entry_zone": plan.get("entry_trigger"),
            "target_price": plan.get("downside_target"),
            "stop_loss": plan.get("cover_stop"),
            "observation_reason": plan.get("thesis_invalidation") or plan.get("squeeze_risk"),
        }
    else:
        direction = plan.get("trade_direction") if plan is not None else None
        if direction == "Neutral" and plan is not None:
            plan["observation_reason"] = plan.get("core_catalyst")
    return {"recommendation": label, "targets_by_horizon": targets,
            "direction": direction, "plan": plan}


def _inflate_candidate(store: StudyStore, sealed: Mapping[str, Any]) -> dict[str, Any]:
    candidate = dict(sealed)
    artifacts = sealed.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise StoreError("candidate artifacts are malformed")
    inflated = {}
    for name, ref in artifacts.items():
        if not isinstance(name, str) or not isinstance(ref, Mapping):
            raise StoreError("candidate artifact reference is malformed")
        digest = ref.get("sha256")
        size = ref.get("size_bytes")
        if not isinstance(digest, str):
            raise StoreError("candidate artifact digest is missing")
        try:
            content = store.read_blob(digest, size_bytes=size).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StoreError("candidate artifact is not UTF-8") from exc
        inflated[name] = {**ref, "content": content}
    candidate["artifacts"] = inflated
    return candidate


def _submission_rows(submission, planned, manifest):
    if submission.get("schema_version") != "stock-agent.report-rebuild-authorized.v1" or submission.get("prepare_only") is not False:
        raise ValueError("submission is not an authorized indexed scope")
    jobs = submission.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("submission jobs must be a list")
    rows = {}
    for row in jobs:
        if not isinstance(row, Mapping):
            raise ValueError("submission job is malformed")
        ticker, pipeline = row.get("ticker"), row.get("pipeline_id")
        if not isinstance(ticker, str) or not isinstance(pipeline, str) or (ticker, pipeline) in rows:
            raise ValueError("submission job identity is invalid or duplicated")
        rows[(ticker, pipeline)] = row
    expected = {(row["ticker"], row["pipeline_id"]) for row in planned}
    if set(rows) != expected or len(rows) != len(jobs):
        raise ValueError("submission scope differs from attested candidates")
    authorization = submission.get("authorization")
    if not isinstance(authorization, Mapping) or authorization.get("candidate_count") != 28:
        raise ValueError("submission authorization count is invalid")
    if authorization.get("scope_sha256") != content_hash(_submission_scope_rows(jobs)):
        raise ValueError("submission authorization fingerprint changed")
    policies = manifest.get("policies")
    expected_source = policies.get("cohort_source_manifest_sha256") if isinstance(policies, Mapping) else None
    if not isinstance(expected_source, str) or authorization.get("source_manifest_sha256") != expected_source:
        raise ValueError("submission source is not the attested cohort manifest")
    return rows


def _submission_scope_rows(jobs):
    return [{
        "ticker": row.get("ticker"),
        "pipeline_id": row.get("pipeline_id"),
        "source_filename": row.get("source_filename"),
        "requires_rerun": row.get("requires_rerun"),
        "requires_rerun_reason": row.get("requires_rerun_reason") or "",
    } for row in jobs]


def _single_target(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    values = extract_target_price_numbers(str(value))
    return float(values[0]) if len(values) == 1 and values[0] > 0 else None


def _read_only_db(path):
    resolved = Path(path).resolve(strict=True)
    return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)


def _job(connection, job_id):
    connection.row_factory = sqlite3.Row
    row = connection.execute("SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def _events(connection, job_id):
    rows = connection.execute("SELECT payload, created_at FROM analysis_events WHERE job_id = ? ORDER BY id", (job_id,)).fetchall()
    events = []
    for row in rows:
        payload = load_unique_json(str(row["payload"]).encode("utf-8"))
        events.append({"payload": payload, "created_at": row["created_at"]})
    return events


def _content(storage, key):
    item = storage.get_report(key) if key else None
    if item is None:
        raise ValueError("report artifact is missing")
    return item.content


def _record_exists(store, record_id):
    try:
        store.read_record(record_id)
        return True
    except StoreError:
        return False


def _candidate_id(index, ticker, pipeline):
    slug = str(ticker).lower().replace(".", "-")
    return f"candidate-{index:02d}-{slug}-{pipeline}"


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value):
    return str(value or "").strip() or None
