#!/usr/bin/env python3
"""Explicit maintenance steps for rebuilding the daily tracking report set."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from report_repository import DEFAULT_REPORT_REPOSITORY
from runtime_paths import current_runtime_paths
from storage.report_storage import LocalFileStorage
from storage._local_file_operations import atomic_write, exclusive_storage_lock, fsync_directory, metadata_path
from storage._report_keys import normalize_report_key


def save(path, manifest):
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))


def _requires_submission_confirmation(item):
    return not item.get("job_id") and (
        bool(item.get("submission_started_at")) or item.get("submission_state") in {"pending", "accepted"}
    )


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _authorized_scope_rows(jobs, *, require_unsubmitted=False):
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("Indexed authorization requires a non-empty jobs list")
    rows = []
    seen = set()
    for item in jobs:
        if not isinstance(item, dict):
            raise ValueError("Indexed authorization job must be an object")
        ticker = item.get("ticker")
        pipeline_id = item.get("pipeline_id")
        source_filename = item.get("source_filename")
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError("Indexed authorization job ticker is invalid")
        if pipeline_id not in {"v1", "v2", "v3", "v4"}:
            raise ValueError("Indexed authorization job pipeline is invalid")
        if not isinstance(source_filename, str) or not source_filename.strip():
            raise ValueError("Indexed authorization source filename is invalid")
        identity = (ticker, pipeline_id)
        if identity in seen:
            raise ValueError("Indexed authorization scope contains a duplicate ticker/pipeline")
        seen.add(identity)
        if item.get("requires_rerun") is not True:
            raise ValueError("Indexed authorization only accepts refresh candidates")
        if require_unsubmitted:
            if item.get("status") != "not_submitted":
                raise ValueError("Indexed authorization only accepts unsubmitted refresh candidates")
            if any(item.get(key) for key in ("job_id", "submission_state", "submission_started_at")):
                raise ValueError("Indexed authorization source already contains submission state")
        rows.append({
            "ticker": ticker,
            "pipeline_id": pipeline_id,
            "source_filename": source_filename,
            "requires_rerun": True,
            "requires_rerun_reason": item.get("requires_rerun_reason") or "",
        })
    return rows


def _scope_sha256(jobs):
    return hashlib.sha256(_canonical_json(_authorized_scope_rows(jobs))).hexdigest()


def _validate_authorized_submission_manifest(manifest):
    if manifest.get("schema_version") != "stock-agent.report-rebuild-authorized.v1":
        return
    authorization = manifest.get("authorization")
    jobs = manifest.get("jobs")
    if not isinstance(authorization, dict) or not isinstance(jobs, list):
        raise RuntimeError("Authorized scope metadata is missing or malformed")
    candidate_count = authorization.get("candidate_count")
    expected_hash = authorization.get("scope_sha256")
    source_hash = authorization.get("source_manifest_sha256")
    if (
        isinstance(candidate_count, bool)
        or not isinstance(candidate_count, int)
        or candidate_count != len(jobs)
        or not isinstance(expected_hash, str)
        or len(expected_hash) != 64
        or not isinstance(source_hash, str)
        or len(source_hash) != 64
    ):
        raise RuntimeError("Authorized scope metadata is inconsistent")
    try:
        actual_hash = _scope_sha256(jobs)
    except ValueError as exc:
        raise RuntimeError("Authorized scope no longer matches a valid indexed candidate set") from exc
    if actual_hash != expected_hash:
        raise RuntimeError("Authorized scope fingerprint changed; no jobs were submitted")


def _write_exclusive_manifest(path, manifest):
    if not path.is_absolute() or path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("Submission manifest must be a new absolute path in an existing directory")
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    encoded = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short submission manifest write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    fsync_directory(path.parent)


def _authorize_indexed_manifest(args):
    if args.submission_manifest is None or args.confirm_source_sha256 is None or args.confirm_candidate_count is None:
        raise ValueError(
            "authorize-indexed requires --submission-manifest, --confirm-source-sha256 and --confirm-candidate-count"
        )
    if args.manifest_was_symlink or args.manifest.is_symlink() or not args.manifest.is_file():
        raise ValueError("Indexed source manifest must be a regular non-symlink file")
    source_bytes = args.manifest.read_bytes()
    actual_hash = hashlib.sha256(source_bytes).hexdigest()
    if args.confirm_source_sha256.lower() != actual_hash:
        raise ValueError("Indexed source manifest SHA-256 does not match the explicit confirmation")
    source = json.loads(source_bytes)
    if source.get("schema_version") != "stock-agent.report-rebuild-prepare-indexed.v1" or source.get("prepare_only") is not True:
        raise ValueError("authorize-indexed requires a prepare-only indexed manifest")
    jobs = source.get("jobs")
    scope_rows = _authorized_scope_rows(jobs, require_unsubmitted=True)
    candidate_count = source.get("refresh_candidate_count")
    if isinstance(candidate_count, bool) or not isinstance(candidate_count, int) or candidate_count != len(scope_rows):
        raise ValueError("Indexed source candidate count is inconsistent")
    if args.confirm_candidate_count != candidate_count:
        raise ValueError("Indexed candidate count does not match the explicit confirmation")
    scope_hash = hashlib.sha256(_canonical_json(scope_rows)).hexdigest()
    authorized = {
        "schema_version": "stock-agent.report-rebuild-authorized.v1",
        "prepare_only": False,
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "source": source.get("source"),
        "authorization": {
            "source_manifest_sha256": actual_hash,
            "candidate_count": candidate_count,
            "scope_sha256": scope_hash,
        },
        "jobs": [dict(item) for item in jobs],
    }
    _write_exclusive_manifest(args.submission_manifest, authorized)
    print(json.dumps({"candidate_count": candidate_count, "scope_sha256": scope_hash}, ensure_ascii=False, indent=2))


def _indexed_prepare_manifest(reports, *, base_url, generated_at=None):
    """Build a read-only latest-per-ticker/mode inventory from /api/reports.

    The resulting manifest is deliberately marked ``prepare_only``.  It is an
    inventory for operator review, not a submission queue, because the API
    report index does not establish a user-approved refresh scope.
    """
    if not isinstance(reports, list):
        raise ValueError("indexed report payload must be a list")
    seen = set()
    groups = {}
    indexed = []
    for report in reports:
        if not isinstance(report, dict):
            raise ValueError("indexed report entry must be an object")
        filename = report.get("filename")
        ticker = report.get("ticker")
        pipeline_id = report.get("pipeline_id")
        if not all(isinstance(value, str) and value.strip() for value in (filename, ticker, pipeline_id)):
            raise ValueError("indexed report identity is incomplete")
        if filename in seen:
            raise ValueError("indexed report identity is duplicated")
        seen.add(filename)
        freshness = report.get("decision_freshness")
        freshness = freshness if isinstance(freshness, dict) else {}
        timestamp = report.get("timestamp")
        valid_timestamp = isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool) and math.isfinite(timestamp)
        entry = {
            "filename": filename,
            "ticker": ticker,
            "pipeline_id": pipeline_id,
            "timestamp": timestamp if valid_timestamp else None,
            "date": report.get("date"),
            "html_hash": report.get("html_hash"),
            "markdown_hash": report.get("markdown_hash"),
            "data_snapshot_hash": report.get("data_snapshot_hash"),
            "freshness_status": freshness.get("status"),
            "requires_rerun": freshness.get("requires_rerun"),
            "requires_rerun_reason": freshness.get("requires_rerun_reason"),
            "conclusion_generated_at": freshness.get("conclusion_generated_at"),
            "snapshot_refreshed_at": freshness.get("snapshot_refreshed_at"),
        }
        indexed.append(entry)
        groups.setdefault((ticker, pipeline_id), []).append(entry)

    latest_groups = []
    jobs = []
    for (ticker, pipeline_id), entries in sorted(groups.items()):
        if not all(entry["timestamp"] is not None for entry in entries):
            latest_groups.append({
                "ticker": ticker,
                "pipeline_id": pipeline_id,
                "status": "unverifiable",
                "reason": "missing_or_invalid_timestamp",
                "version_count": len(entries),
                "latest": None,
            })
            continue
        latest = max(entries, key=lambda entry: (entry["timestamp"], entry["filename"]))
        action = "refresh" if latest["requires_rerun"] is True else "no_action"
        group = {
            "ticker": ticker,
            "pipeline_id": pipeline_id,
            "status": latest["freshness_status"] or "unknown",
            "action": action,
            "reason": latest["requires_rerun_reason"] or "",
            "version_count": len(entries),
            "latest": latest,
        }
        latest_groups.append(group)
        if action == "refresh":
            jobs.append({
                "ticker": ticker,
                "pipeline_id": pipeline_id,
                "source_filename": latest["filename"],
                "status": "not_submitted",
                "requires_rerun": True,
                "requires_rerun_reason": latest["requires_rerun_reason"] or "",
            })

    return {
        "schema_version": "stock-agent.report-rebuild-prepare-indexed.v1",
        "prepare_only": True,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "source": {"kind": "indexed_reports", "base_url": base_url.rstrip("/")},
        "indexed_report_count": len(indexed),
        "latest_group_count": len(latest_groups),
        "refresh_candidate_count": len(jobs),
        "indexed_reports": indexed,
        "latest_groups": latest_groups,
        "jobs": jobs,
    }


def _source_path(root, key):
    if normalize_report_key(key) != key:
        raise ValueError("Purge requires an exact normalized report key")
    path = root
    for component in Path(key).parts:
        path /= component
        if path.is_symlink():
            raise ValueError("Purge target must not contain symlinks")
    if metadata_path(path).is_symlink():
        raise ValueError("Purge metadata must not be a symlink")
    return path


def purge_confirmed_targets(args, paths, manifest, get):
    if not args.confirm_purge or not args.report_key or args.backup_dir is None:
        raise ValueError("Purge requires --confirm-purge, exact --report-key values and --backup-dir")
    if manifest.get("purged_at"):
        raise RuntimeError("Legacy manifest was already purged; prepare a new inventory")
    root = paths.output_dir.resolve()
    if str(root) != manifest.get("source_output_dir"):
        raise RuntimeError("The report directory differs from the prepared deletion scope")
    keys = sorted(set(args.report_key))
    hashes = manifest.get("old_artifact_hashes") or {}
    if any(key not in manifest.get("old_artifact_keys", []) or key not in hashes for key in keys):
        raise ValueError("Every purge target requires a prepared content hash; prepare a new manifest")
    backup_path = args.backup_dir.resolve()
    if backup_path.exists() or backup_path.is_relative_to(root) or root.is_relative_to(backup_path):
        raise ValueError("Use a new backup directory outside the report directory")
    if get("/api/observability/active-jobs").get("active_count"):
        raise RuntimeError("Analysis jobs are active; no reports were removed")
    # Hold the same filesystem lock used by report writers throughout backup and
    # deletion. Do not nest LocalFileStorage operations against the source root.
    with exclusive_storage_lock(root):
        sources = {key: _source_path(root, key) for key in keys}
        contents = {key: path.read_bytes() for key, path in sources.items()}
        if any(hashlib.sha256(content).hexdigest() != hashes[key] for key, content in contents.items()):
            raise RuntimeError("Report content changed after prepare; no reports were removed")
        backup_path.mkdir(parents=True, exist_ok=False)
        backup = LocalFileStorage(backup_path)
        for key, content in contents.items():
            content_type = LocalFileStorage._read_content_type(key, sources[key], content_digest=hashes[key])
            backup.save_report(key, content, content_type=content_type)
            copied = backup.get_report(key)
            if copied is None or copied.content != content:
                raise RuntimeError("Backup verification failed; no reports were removed")
        record = {"backup_dir": str(backup_path), "keys": keys,
                  "sha256": {key: hashes[key] for key in keys}, "state": "backed_up"}
        manifest.setdefault("purge_backups", []).append(record)
        save(args.manifest, manifest)
        for path in sources.values():
            path.unlink()
            metadata_path(path).unlink(missing_ok=True)
            fsync_directory(path.parent)
        record["state"] = "purged"
        save(args.manifest, manifest)
    DEFAULT_REPORT_REPOSITORY.sync(str(root))
    print(json.dumps({"deleted_artifacts": len(keys), "backup_dir": str(backup_path), "keys": keys}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "prepare-indexed", "authorize-indexed", "purge", "submit", "status"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--confirm-purge", action="store_true", help="Confirm removal of only the explicitly named prepared keys")
    parser.add_argument("--report-key", action="append", default=[], help="Exact prepared artifact key to remove; repeat for each file")
    parser.add_argument("--backup-dir", type=Path, help="New recoverable backup directory outside report output")
    parser.add_argument("--submission-manifest", type=Path, help="New manifest created from an explicitly confirmed indexed scope")
    parser.add_argument("--confirm-source-sha256", help="Exact SHA-256 of the prepare-only indexed manifest")
    parser.add_argument("--confirm-candidate-count", type=int, help="Exact number of indexed candidates being authorized")
    parser.add_argument("--batch-size", type=int, help="Submit at most this many new jobs in one invocation")
    args = parser.parse_args()
    args.manifest_was_symlink = args.manifest.is_symlink()
    args.manifest = args.manifest.resolve()
    if args.submission_manifest is not None:
        if not args.submission_manifest.is_absolute():
            raise ValueError("Submission manifest path must be absolute")
        if args.submission_manifest.is_symlink():
            raise ValueError("Submission manifest path must not be a symlink")
        args.submission_manifest = args.submission_manifest.parent.resolve() / args.submission_manifest.name
    # Use a stable, dedicated directory rather than the manifest's parent: the
    # parent may also be report storage, whose operations acquire their own flock.
    # Never remove this directory after use; waiters must share the same inode.
    lock_dir = args.manifest.with_name(f".{args.manifest.name}.lock")
    lock_dir.mkdir(parents=True, exist_ok=True)
    if lock_dir.is_symlink():
        raise ValueError("Manifest lock directory must not be a symlink")
    with exclusive_storage_lock(lock_dir):
        _run_action(args)


def _run_action(args):
    # All manifest reads and writes, including status and purge, share the lock.
    paths = current_runtime_paths()
    storage = LocalFileStorage(paths.output_dir)
    session = requests.Session()

    def get(path):
        response = session.get(args.base_url + path, timeout=60)
        response.raise_for_status()
        return response.json()

    if args.action == "authorize-indexed":
        _authorize_indexed_manifest(args)
        return

    if args.action == "prepare-indexed":
        if args.manifest.exists():
            raise ValueError("Manifest already exists; use its existing inventory instead")
        reports = []
        page = 1
        total = None
        while True:
            payload = get(f"/api/reports?page={page}&limit=100&include_versions=true")
            if not isinstance(payload, dict) or not isinstance(payload.get("reports"), list):
                raise ValueError("report API returned malformed indexed inventory")
            pagination = payload.get("pagination")
            if not isinstance(pagination, dict) or not isinstance(pagination.get("total"), int):
                raise ValueError("report API returned malformed pagination")
            if total is None:
                total = pagination["total"]
            elif total != pagination["total"]:
                raise ValueError("report index changed during prepare")
            reports.extend(payload["reports"])
            if not pagination.get("has_next"):
                break
            page += 1
            if page > 1000:
                raise ValueError("report API pagination exceeded safety bound")
        if total != len(reports):
            raise ValueError("report API total does not match indexed inventory")
        manifest = _indexed_prepare_manifest(reports, base_url=args.base_url)
        save(args.manifest, manifest)
        print(json.dumps({key: manifest[key] for key in ("indexed_report_count", "latest_group_count", "refresh_candidate_count", "jobs")}, ensure_ascii=False, indent=2))
        return

    if args.action == "prepare":
        if args.manifest.exists():
            raise ValueError("Manifest already exists; use its existing jobs instead")
        active = get("/api/observability/active-jobs")
        if active.get("active_count"):
            raise RuntimeError("Analysis jobs are active; finish them before rebuilding")
        tracked = get("/api/decision-tracking")["items"]
        items = []
        for item in tracked:
            if not item.get("enabled"):
                continue
            reports = item.get("latest_reports") or []
            ticker = next((report["ticker"] for report in reports if report.get("ticker")), item["ticker"])
            modes = sorted({report["pipeline_id"] for report in reports} or {"v1", "v2", "v3", "v4"})
            items.extend({"ticker": ticker, "pipeline_id": mode, "tracking_ticker": item["ticker"]} for mode in modes)
        files = storage.list_reports()
        manifest = {
            "source_output_dir": str(paths.output_dir.resolve()),
            "old_artifact_keys": [item.key for item in files],
            "old_artifact_hashes": {item.key: hashlib.sha256(storage.get_report(item.key).content).hexdigest() for item in files},
            "old_report_count": sum(item.key.endswith(".html") for item in files),
            "tracking_count": sum(bool(item.get("enabled")) for item in tracked),
            "jobs": items,
        }
        save(args.manifest, manifest)
        print(json.dumps({key: manifest[key] for key in ("tracking_count", "old_report_count", "jobs")}, ensure_ascii=False, indent=2))
        return

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.action == "purge":
        purge_confirmed_targets(args, paths, manifest, get)
        return

    if args.action == "submit":
        if args.batch_size is not None and args.batch_size <= 0:
            raise ValueError("--batch-size must be a positive integer")
        if manifest.get("prepare_only"):
            raise RuntimeError("This manifest is prepare-only; confirm an explicit submission scope before submit")
        _validate_authorized_submission_manifest(manifest)
        if any(_requires_submission_confirmation(item) for item in manifest["jobs"]):
            raise RuntimeError(
                "Submission pending: verify existing jobs before retrying; manually attach the verified job_id "
                "to this manifest. Do not clear pending state or create another batch to resend it."
            )
        config = get("/api/client-config")
        session.headers[config["mutation_header"]] = config["mutation_token"]
        submitted_count = 0
        for item in manifest["jobs"]:
            if item.get("job_id"):
                continue
            if args.batch_size is not None and submitted_count >= args.batch_size:
                break
            # A timeout or a failed acceptance save cannot prove rejection. Keep
            # this durable marker until an operator verifies the existing job.
            item["submission_state"] = "pending"
            item["submission_started_at"] = datetime.now(timezone.utc).isoformat()
            item["status"] = "pending_confirmation"
            save(args.manifest, manifest)
            response = session.post(args.base_url + "/api/analysis-jobs", json={
                "ticker": item["ticker"], "pipeline_id": item["pipeline_id"], "force": False, "resume": True,
            }, timeout=60)
            response.raise_for_status()
            result = response.json()
            job_id = result.get("job_id")
            if not isinstance(job_id, str) or not job_id.strip():
                raise RuntimeError("Submission pending: verify existing jobs; response did not contain a usable job_id")
            item["job_id"] = job_id
            item["submission_state"] = "accepted"
            item["status"] = result.get("status", "queued")
            save(args.manifest, manifest)
            submitted_count += 1
            print(json.dumps({key: item[key] for key in ("ticker", "pipeline_id", "job_id", "status")}), flush=True)
        return

    for item in manifest["jobs"]:
        if not item.get("job_id"):
            item["status"] = "pending_confirmation" if _requires_submission_confirmation(item) else "not_submitted"
            continue
        result = get("/api/analysis-jobs/" + item["job_id"])
        item["status"] = result.get("status")
        item["report_path"] = result.get("report_path")
        item["error"] = result.get("error")
    save(args.manifest, manifest)
    print(json.dumps({"counts": dict(Counter(item.get("status") for item in manifest["jobs"])), "jobs": manifest["jobs"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
