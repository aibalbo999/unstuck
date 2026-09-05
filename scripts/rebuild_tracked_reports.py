#!/usr/bin/env python3
"""Explicit maintenance steps for rebuilding the daily tracking report set."""

from __future__ import annotations

import argparse
import hashlib
import json
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
    parser.add_argument("action", choices=("prepare", "purge", "submit", "status"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--confirm-purge", action="store_true", help="Confirm removal of only the explicitly named prepared keys")
    parser.add_argument("--report-key", action="append", default=[], help="Exact prepared artifact key to remove; repeat for each file")
    parser.add_argument("--backup-dir", type=Path, help="New recoverable backup directory outside report output")
    args = parser.parse_args()
    args.manifest = args.manifest.resolve()
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
        if any(_requires_submission_confirmation(item) for item in manifest["jobs"]):
            raise RuntimeError(
                "Submission pending: verify existing jobs before retrying; manually attach the verified job_id "
                "to this manifest. Do not clear pending state or create another batch to resend it."
            )
        config = get("/api/client-config")
        session.headers[config["mutation_header"]] = config["mutation_token"]
        for item in manifest["jobs"]:
            if item.get("job_id"):
                continue
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
