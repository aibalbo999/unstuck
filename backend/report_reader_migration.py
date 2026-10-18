"""Guarded HTML-only migration; no analysis or quality metadata is rebuilt."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3

from report_artifacts import ReportArtifactLocator
from report_reader_assets import inject_reader, remove_reader
from storage._local_file_operations import atomic_write, exclusive_storage_lock, metadata_path
from storage.report_storage import LocalFileStorage


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _reader_snapshot(storage: LocalFileStorage, filename: str):
    locator = ReportArtifactLocator(storage)
    data_key = locator.existing_key(filename, kind='data')
    snapshot = None
    content_hash = None
    if data_key is not None:
        content = storage.get_report(data_key).content
        content_hash = sha256(content)
        snapshot = json.loads(content.decode('utf-8'))
        if not isinstance(snapshot, dict):
            raise ValueError('Saved report snapshot must be a JSON object')
        from report_evidence_review import load_review
        review, reference = load_review(storage, filename, content)
        if reference is not None:
            snapshot['_reader_institutional_reports'] = review['institutional_reports']
            snapshot['_reader_volume_observation'] = review.get('volume_observation')
            snapshot['_reader_cash_flow_review'] = review.get('cash_flow_period_review')
            snapshot['_reader_review_reference'] = reference
    return snapshot, data_key, content_hash


def prepared_reader_html(storage: LocalFileStorage, filename: str, html: str) -> str:
    snapshot, _, _ = _reader_snapshot(storage, filename)
    return inject_reader(html, snapshot=snapshot)


def migrate_report(
    index_path: Path,
    storage: LocalFileStorage,
    filename: str,
    *,
    expected_sha256: str | None = None,
    expected_after_sha256: str | None = None,
    apply: bool = False,
) -> dict:
    key = ReportArtifactLocator(storage).require_key(filename, kind="html")
    # Resolve through storage validation, including symlink and reserved-key checks.
    _, path = storage._target(key)
    # Storage reads acquire the same filesystem lock; preload and recheck the
    # snapshot under the write lock instead of recursively acquiring flock.
    snapshot, data_key, data_hash = _reader_snapshot(storage, filename)
    sidecar = metadata_path(path)
    mode = "rw" if apply else "ro"
    conn = sqlite3.connect(f"{Path(index_path).resolve().as_uri()}?mode={mode}", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        if apply:
            conn.execute("BEGIN IMMEDIATE")
        with exclusive_storage_lock(storage._root):
            if data_key is not None:
                _, data_path = storage._target(data_key)
                if sha256(data_path.read_bytes()) != data_hash:
                    raise ValueError('Saved report snapshot changed during preparation')
            review = snapshot.get('_reader_review_reference') if isinstance(snapshot, dict) else None
            if review:
                _, review_path = storage._target(review['key'])
                if sha256(review_path.read_bytes()) != review['sha256']:
                    raise ValueError('Supplemental evidence review changed during preparation')
            row = conn.execute(
                "SELECT * FROM reports WHERE output_dir=? AND filename=?",
                (str(storage._root), filename),
            ).fetchone()
            if row is None:
                raise ValueError("Report is not indexed for this output directory")
            original = path.read_bytes()
            before_hash = sha256(original)
            if expected_sha256 is not None and before_hash != expected_sha256:
                raise ValueError("HTML changed since the prepared inventory")
            if row["html_hash"] and row["html_hash"] != before_hash:
                raise ValueError("Index HTML checksum does not match saved content")
            if sidecar.is_symlink():
                raise ValueError("Report checksum must not be a symlink")
            old_metadata = sidecar.read_bytes() if sidecar.exists() else None
            metadata = json.loads(old_metadata) if old_metadata is not None else {}
            if old_metadata is not None and (not isinstance(metadata, dict) or metadata.get("sha256") != before_hash):
                raise ValueError("Report sidecar checksum does not match saved content")
            decoded = original.decode("utf-8")
            updated = inject_reader(decoded, snapshot=snapshot).encode("utf-8")
            if remove_reader(updated.decode("utf-8")) != remove_reader(decoded):
                raise ValueError("Reader injection changed original report content")
            after_hash = sha256(updated)
            if expected_after_sha256 is not None and after_hash != expected_after_sha256:
                raise ValueError("Reader assets changed since the prepared inventory")
            result = {
                "filename": filename, "key": key, "pipeline_id": row["pipeline_id"],
                "before_sha256": before_hash, "after_sha256": after_hash,
                "original_sha256": sha256(remove_reader(decoded).encode("utf-8")),
                "status": "unchanged" if updated == original else "ready",
            }
            if not apply or updated == original:
                if apply:
                    conn.commit()
                return result
            stat = path.stat()
            metadata.update(content_type=metadata.get("content_type", "text/html"), sha256=after_hash)
            try:
                atomic_write(sidecar, json.dumps(metadata, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                atomic_write(path, updated)
                # A layout refresh must not masquerade as a new analysis date.
                os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                conn.execute(
                    "UPDATE reports SET html_hash=? WHERE output_dir=? AND filename=?",
                    (after_hash, str(storage._root), filename),
                )
                conn.commit()
            except Exception as migration_error:
                conn.rollback()
                errors = []
                try:
                    atomic_write(path, original)
                    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                    if old_metadata is None:
                        sidecar.unlink(missing_ok=True)
                    else:
                        atomic_write(sidecar, old_metadata)
                except Exception as recovery_error:
                    errors.append(recovery_error)
                if errors:
                    raise ExceptionGroup("HTML migration recovery failed", [migration_error, *errors]) from migration_error
                raise
            result["status"] = "updated"
            return result
    finally:
        conn.close()
