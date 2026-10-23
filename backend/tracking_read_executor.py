"""Bounded, fresh tracking projections isolated from dashboard CPU threads."""
from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import socket
import hashlib
import json
import logging
import os
from pathlib import Path
from time import monotonic

import decision_tracking_service as service
from performance_read_executor import PerformanceReadExecutor, PerformanceReadUnavailable, _install_readonly_boundary
from report_index import query_report_metadata, sync_report_metadata
from report_index_rows import _row_file_path, _snapshot_path

LOGGER = logging.getLogger("uvicorn.error")
_BACKEND = Path(service.__file__).resolve().parent


def tracking_rules_revision():
    digest = hashlib.sha256()
    for directory, dirs, filenames in os.walk(_BACKEND):
        dirs[:] = sorted(name for name in dirs if name not in {"cache", "output", "__pycache__"} and not name.startswith("."))
        for name in sorted(filenames):
            if name.endswith(".py"):
                path = Path(directory) / name
                digest.update(str(path.relative_to(_BACKEND)).encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


_RULES_REVISION = tracking_rules_revision()


def _archive_proofs(value):
    if isinstance(value,dict):
        if value.get('raw_response_path') and value.get('raw_response_sha256'):yield value
        else:
            for item in value.values():yield from _archive_proofs(item)
    elif isinstance(value,list):
        for item in value:yield from _archive_proofs(item)


def tracking_read_revision(output_dir):
    digest = hashlib.sha256()
    items = service.decision_tracking_store.list_items()
    digest.update(json.dumps(items, sort_keys=True, ensure_ascii=False).encode())
    # Hash current candidate artifacts, including archived identity fallback
    # sources. No quality projection or result cache is involved here.
    seen = set()
    archive_seen=set()
    for item in items:
        ticker = str(item.get("ticker") or "").upper()
        page = 1
        while ticker:
            rows, total = query_report_metadata(page=page, limit=100, q=ticker.split(".", 1)[0], pipeline="all", include_versions=True, output_dir=output_dir, sync_metadata=False, row_mapper=dict)
            for row in rows:
                if not service._ticker_matches(row, ticker) or row["filename"] in seen:
                    continue
                seen.add(row["filename"])
                digest.update(json.dumps(row, sort_keys=True, ensure_ascii=False).encode())
                snapshot_path=_snapshot_path(row)
                if snapshot_path:
                    try:
                        snapshot=json.loads(Path(snapshot_path).read_text())
                        for proof in _archive_proofs(snapshot):
                            key=(proof.get("raw_response_path"),proof.get("raw_response_sha256"))
                            if key in archive_seen:continue
                            archive_seen.add(key)
                            from official_response_evidence import read_response
                            try:digest.update(read_response(proof))
                            except (OSError,ValueError,TypeError,EOFError):digest.update(b"raw_archive_unavailable")
                    except (OSError,ValueError,TypeError):pass
                for path in (snapshot_path, _row_file_path(row, kind="md"), _row_file_path(row, kind="html")):
                    digest.update(path.encode())
                    if path:
                        try:
                            with open(path, "rb") as handle:
                                while chunk := handle.read(1024 * 1024):
                                    digest.update(chunk)
                        except OSError:
                            digest.update(b"artifact_unavailable")
            if not rows or page * 100 >= total:
                break
            page += 1
    return digest.hexdigest()


def _quality_read_revision(output_dir):
    """Hash actual latest artifacts, raw proofs and review state in the child."""
    digest = hashlib.sha256()
    seen_archives = set()
    page = 1
    while True:
        rows, total = query_report_metadata(page=page, limit=100, pipeline="all", include_versions=False,
            output_dir=output_dir, sync_metadata=False, row_mapper=dict)
        for row in rows:
            digest.update(json.dumps(row, sort_keys=True, ensure_ascii=False).encode())
            snapshot_path = _snapshot_path(row)
            for path in (snapshot_path, _row_file_path(row, kind="md"), _row_file_path(row, kind="html")):
                digest.update(path.encode())
                try:
                    with open(path, "rb") as handle:
                        while chunk := handle.read(1024 * 1024): digest.update(chunk)
                except OSError: digest.update(b"artifact_unavailable")
            try:
                for proof in _archive_proofs(json.loads(Path(snapshot_path).read_text())):
                    key = (proof.get("raw_response_path"), proof.get("raw_response_sha256"))
                    if key in seen_archives: continue
                    seen_archives.add(key)
                    from official_response_evidence import read_response
                    try: digest.update(read_response(proof))
                    except (OSError, ValueError, TypeError, EOFError): digest.update(b"raw_archive_unavailable")
            except (OSError, ValueError, TypeError): pass
        if not rows or page * 100 >= total: break
        page += 1
    import report_quality_review_store
    with report_quality_review_store._connect() as conn:
        reviews = conn.execute("SELECT * FROM report_quality_review_events ORDER BY event_id").fetchall()
        digest.update(json.dumps([dict(row) for row in reviews], sort_keys=True, default=str).encode())
    return digest.hexdigest()


def _compute_readonly_quality(request):
    _install_readonly_boundary()
    _, output_dir, revision = request[:3]
    if len(request) == 4:
        if revision != _RULES_REVISION:
            raise PerformanceReadUnavailable("quality_rules_require_reload")
        revision = _quality_read_revision(output_dir)
    if tracking_rules_revision() != _RULES_REVISION:
        raise PerformanceReadUnavailable("quality_rules_require_reload")
    # Four-part requests establish their source fingerprint above in this
    # same child. Keep the post-computation byte check; an immediate second
    # pre-computation scan adds no additional boundary. Externally supplied
    # fingerprints still require their initial comparison.
    if len(request) != 4 and _quality_read_revision(output_dir) != revision:
        raise PerformanceReadUnavailable("quality_sources_changed")
    import report_quality_audit
    # Do not return prior completed projections from its legacy 15-second cache.
    report_quality_audit._REPORT_QUALITY_ROWS_CACHE.clear()
    result = report_quality_audit.build_indexed_report_quality_audit(output_dir, page_size=100)
    if tracking_rules_revision() != _RULES_REVISION:
        raise PerformanceReadUnavailable("quality_rules_require_reload")
    if _quality_read_revision(output_dir) != revision:
        raise PerformanceReadUnavailable("quality_sources_changed")
    return result


def _compute_readonly_tracking(request):
    _install_readonly_boundary()
    if len(request) == 3 and request[0] == "quality_audit":
        return _compute_readonly_quality(request)
    output_dir, revision = request
    if tracking_rules_revision() != _RULES_REVISION:
        raise PerformanceReadUnavailable("tracking_rules_require_reload")
    if tracking_read_revision(output_dir) != revision:
        raise PerformanceReadUnavailable("tracking_sources_changed")
    result = service.list_decision_tracking(output_dir, sync_metadata=False)
    if tracking_rules_revision() != _RULES_REVISION:
        raise PerformanceReadUnavailable("tracking_rules_require_reload")
    if tracking_read_revision(output_dir) != revision:
        raise PerformanceReadUnavailable("tracking_sources_changed")
    return result


# Process startup/imports share the first projection's deadline. The formal
# cold UI burst completed its valid projection in 21.887s, after the old 20s
# limit. Keep warm reads at 20s and allow a bounded 35s only for a new worker.
TRACKING_COLD_READ_TIMEOUT_SECONDS = 35.0
TRACKING_REQUEST_TIMEOUT_SECONDS = 60.0  # preparation <=20s + cold projection <=35s
tracking_reads = PerformanceReadExecutor(timeout_seconds=20.0, compute_fn=_compute_readonly_tracking,
    read_name="tracking", cold_start_timeout_seconds=TRACKING_COLD_READ_TIMEOUT_SECONDS)

# Keep tracking and performance availability independent of the full audit.
quality_reads = PerformanceReadExecutor(timeout_seconds=25.0, compute_fn=_compute_readonly_quality, read_name="quality")


def _prepare_tracking_read(output_dir):
    if tracking_rules_revision() != _RULES_REVISION:
        raise PerformanceReadUnavailable("tracking_rules_require_reload")
    sync_report_metadata(output_dir)
    return output_dir, tracking_read_revision(output_dir)


def _compute_tracking_preparation(request):
    # Only the preexisting report-index synchronization may write here.
    # Network is denied; artifact and evaluation-result writes are never called.
    def no_network(*args, **kwargs):
        raise OSError("tracking preparation does not permit network access")
    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    socket.create_connection = no_network
    socket.getaddrinfo = no_network
    output_dir, expected_rules = request[:2]
    if tracking_rules_revision() != expected_rules:
        raise PerformanceReadUnavailable("tracking_rules_require_reload")
    if len(request) == 3 and request[2] == "quality_audit":
        sync_report_metadata(output_dir)
        prepared = ("quality_audit", output_dir, _quality_read_revision(output_dir))
    else:
        prepared = _prepare_tracking_read(output_dir)
    if tracking_rules_revision() != expected_rules:
        raise PerformanceReadUnavailable("tracking_rules_require_reload")
    return prepared


# Preparation also leaves the API interpreter: file scanning has many short
# Python/I/O steps that stall behind dashboard CPU threads despite low CPU time.
tracking_preparations = PerformanceReadExecutor(
    lambda: ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn")),
    timeout_seconds=20.0, compute_fn=_compute_tracking_preparation, read_name="tracking_preparation")


async def read_tracking_items(output_dir):
    started = monotonic()
    deadline = asyncio.timeout(TRACKING_REQUEST_TIMEOUT_SECONDS)
    try:
        # Caller timeout does not terminate preparation threads or the worker.
        async with deadline:
            request = await tracking_preparations.read((output_dir, _RULES_REVISION))
            LOGGER.info("tracking_read_prepared seconds=%.3f", monotonic() - started)
            return await tracking_reads.read(request)
    except TimeoutError:
        reason = "tracking_read_timeout" if deadline.expired() else "tracking_read_failed"
    except PerformanceReadUnavailable as exc:
        reason = exc.reason
    except Exception:
        LOGGER.exception("Tracking read unavailable")
        reason = "tracking_read_failed"
    return {"status": "unavailable", "reason": reason, "message": "決策追蹤暫時無法查驗，請稍後重試。"}


async def read_quality_audit(output_dir):
    """Share preparation; project in one separate zero-queue read-only process."""
    deadline = asyncio.timeout(30.0)
    try:
        async with deadline:
            prepared = await tracking_preparations.read((output_dir, _RULES_REVISION))
            return await quality_reads.read(("quality_audit", output_dir, _RULES_REVISION, prepared[1]))
    except TimeoutError:
        reason = "quality_read_timeout" if deadline.expired() else "quality_read_failed"
    except PerformanceReadUnavailable as exc:
        reason = exc.reason
    except Exception:
        LOGGER.exception("Quality read unavailable")
        reason = "quality_read_failed"
    return {"status": "unavailable", "read_unavailable": True, "reason": reason,
            "message": "全報告品質查核尚未就緒，請稍後重試；沒有返回旧查核結果。"}
