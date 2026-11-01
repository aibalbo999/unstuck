"""Private SQLite/filesystem publication tests; no qualified live samples."""

import hashlib
import json
from pathlib import Path
import sys
import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import report_index
from report_persistence import persist_report_bundle, report_bundle_keys_for_filename
from report_repository import ReportRepository
from storage.report_storage import LocalFileStorage


NAME = "2330_TW_v4_report_20260915_120000.html"


@pytest.fixture
def publication(tmp_path, monkeypatch):
    root = tmp_path / "reports"
    storage = LocalFileStorage(root)
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "index.sqlite3"))
    return dict(filename=NAME, html_content="<html>Original fixture</html>",
                markdown_content="# Original fixture", data_snapshot={
                    "ticker": "2330.TW", "pipeline": "v4", "final_audit": {"status": "passed"}},
                storage=storage, output_dir=str(root), repository=ReportRepository())


def fingerprint(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def rows():
    with report_index._connect() as conn:
        return [tuple(r) for r in conn.execute("SELECT * FROM reports ORDER BY filename")]


def publish(values):
    # On the old implementation exercise the actual overwriting path so RED
    # demonstrates the behavior defect, not an unexpected-keyword setup error.
    import inspect
    options = {"create_only": True} if "create_only" in inspect.signature(persist_report_bundle).parameters else {}
    return persist_report_bundle(**values, **options)


def test_create_only_keeps_existing_bundle_and_index_unchanged(publication):
    publish(publication)
    root = Path(publication["output_dir"])
    original_files, original_rows = fingerprint(root), rows()
    with pytest.raises(FileExistsError):
        publish({**publication, "html_content": "replacement must not be written"})
    assert fingerprint(root) == original_files
    assert rows() == original_rows


@pytest.mark.parametrize("kind", ["nested_html", "flat_html", "nested_md", "flat_data", "sidecar", "review"])
def test_create_only_preflights_all_existing_artifacts_before_any_write(publication, kind):
    root = Path(publication["output_dir"])
    keys = report_bundle_keys_for_filename(NAME)
    choices = {"nested_html": keys.html_key, "flat_html": NAME,
               "nested_md": keys.md_key, "flat_data": keys.data_filename,
               "sidecar": str(Path(keys.data_key).with_name(f".{keys.data_filename}.onstock-metadata.json")),
               "review": keys.html_key.replace(".html", ".review.json")}
    existing = root / choices[kind]
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"preserve original evidence")
    before = fingerprint(root)
    with pytest.raises(FileExistsError):
        publish(publication)
    assert fingerprint(root) == before
    assert rows() == []


def test_create_only_keeps_index_only_collision_without_creating_artifacts(publication):
    root = Path(publication["output_dir"])
    publish(publication)
    original_rows = rows()
    for artifact in root.rglob("*"):
        if artifact.is_file():
            artifact.unlink()
    with pytest.raises(FileExistsError):
        publish(publication)
    assert fingerprint(root) == {}
    assert rows() == original_rows


def test_create_only_success_has_real_index_and_matching_bytes(publication):
    result = publish(publication)
    root = Path(publication["output_dir"])
    assert (root / result["html_key"]).read_text() == publication["html_content"]
    assert (root / result["md_key"]).read_text() == publication["markdown_content"]
    assert json.loads((root / result["data_key"]).read_text())["pipeline"] == "v4"
    assert len(rows()) == 1
    assert result["metadata"]["html_hash"] == hashlib.sha256(publication["html_content"].encode()).hexdigest()


def test_two_create_only_publishers_have_one_winner(publication):
    def attempt(number):
        try:
            publish({**publication, "html_content": str(number), "markdown_content": str(number)})
            return number
        except FileExistsError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, (1, 2)))
    winner, = [n for n in outcomes if n is not None]
    keys = report_bundle_keys_for_filename(NAME)
    root = Path(publication["output_dir"])
    assert (root / keys.html_key).read_text() == (root / keys.md_key).read_text() == str(winner)
    assert len(rows()) == 1


@pytest.mark.parametrize("committed", [False, True])
def test_uncertain_index_result_retains_artifacts_and_never_retries(publication, monkeypatch, committed):
    insert = publication["repository"].insert

    def uncertain(*args, **kwargs):
        if committed:
            insert(*args, **kwargs)
        raise OSError("index outcome not returned")

    monkeypatch.setattr(publication["repository"], "insert", uncertain)
    with pytest.raises(OSError, match="not returned"):
        publish(publication)
    root = Path(publication["output_dir"])
    retained = fingerprint(root)
    assert len(retained) == 7  # Three artifacts, three sidecars, pending attempt.
    before_rows = rows()
    assert len(before_rows) == int(committed)
    with pytest.raises(FileExistsError):
        publish(publication)
    assert fingerprint(root) == retained and rows() == before_rows


@pytest.mark.parametrize("error", [OSError("disk failed"), KeyboardInterrupt()])
def test_partial_file_attempt_is_retained_without_index(publication, monkeypatch, error):
    import storage.create_only_reports as create_only
    create = create_only._create_file

    def fail_after_first_content(path, payload):
        create(path, payload)
        if path.suffix == ".html":
            raise error

    monkeypatch.setattr(create_only, "_create_file", fail_after_first_content)
    with pytest.raises(type(error)) as caught:
        publish(publication)
    assert caught.value is error
    root = Path(publication["output_dir"])
    retained = fingerprint(root)
    assert len(retained) == 3 and rows() == []  # HTML, sidecar, pending attempt.
    with pytest.raises(FileExistsError):
        publish(publication)
    assert fingerprint(root) == retained


def test_index_insert_collision_cannot_replace_existing_row(publication, monkeypatch):
    import sqlite3
    repository = publication["repository"]
    collided = []

    def racing_exists(*args, **kwargs):
        # A writer outside our filesystem lock wins after the preflight query.
        repository.insert(NAME, output_dir=publication["output_dir"], html_content="other index",
                          markdown_content="other index", data_trust={})
        collided.extend(rows())
        return False

    monkeypatch.setattr(repository, "exists", racing_exists)
    with pytest.raises(sqlite3.IntegrityError):
        publish(publication)
    assert rows() == collided
    assert len(fingerprint(Path(publication["output_dir"]))) == 7


def render_arguments(publication, renderer, cancel_check=lambda: None):
    from pipeline_modes import get_pipeline_definition
    return dict(job_id="render-test", ticker_upper="2330.TW", current_pipeline_id="v4",
                pipeline_def=get_pipeline_definition("v4"), sequence_index=1, sequence_total=1,
                context={"ticker": "2330.TW"}, audit_notice={}, renderer=renderer,
                cancel_check=cancel_check, append_event_func=lambda *args: None,
                output_dir=publication["output_dir"], storage=publication["storage"], filename=NAME)


def test_cancellation_during_renderer_never_publishes(publication):
    from analysis_job_reports import render_and_persist_report
    from reporting import ReportBundle
    cancelled = False

    async def render(request):
        nonlocal cancelled
        cancelled = True
        return ReportBundle(html="fixture", markdown="fixture", data_snapshot={"ticker": "2330.TW"})

    def check():
        if cancelled:
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(render_and_persist_report(**render_arguments(
            publication, SimpleNamespace(render_async=render), check)))
    assert fingerprint(Path(publication["output_dir"])) == {} and rows() == []


@pytest.mark.parametrize("kind", ["html_symlink", "sidecar_symlink", "directory", "hardlink"])
def test_existing_special_artifact_is_not_followed_or_replaced(publication, tmp_path, kind):
    import os
    root = Path(publication["output_dir"])
    key = report_bundle_keys_for_filename(NAME).html_key
    target = root / key
    target.parent.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"must stay unchanged")
    if kind == "sidecar_symlink":
        target = target.with_name(f".{target.name}.onstock-metadata.json")
    if kind in ("html_symlink", "sidecar_symlink"):
        target.symlink_to(outside)
    elif kind == "directory":
        target.mkdir()
    else:
        os.link(outside, target)
    original = target.lstat()
    with pytest.raises((FileExistsError, ValueError)):
        publish(publication)
    assert target.lstat() == original
    assert outside.read_bytes() == b"must stay unchanged"
    assert rows() == []


def test_create_only_rejects_other_storage_root_without_writes(publication, tmp_path):
    other = tmp_path / "other-root"
    other.mkdir()
    with pytest.raises(ValueError, match="match storage"):
        publish({**publication, "output_dir": str(other)})
    assert fingerprint(Path(publication["output_dir"])) == fingerprint(other) == {}
    assert rows() == []


def test_fsync_failure_keeps_incomplete_attempt_and_no_index(publication, monkeypatch):
    import storage.create_only_reports as create_only
    import stat
    real_fsync = create_only.os.fsync
    def fail_file_sync(fd):
        if stat.S_ISREG(create_only.os.fstat(fd).st_mode):
            raise OSError("fixture failed file fsync")
        return real_fsync(fd)
    with monkeypatch.context() as patched:
        patched.setattr(create_only.os, "fsync", fail_file_sync)
        with pytest.raises(OSError, match="file fsync"):
            publish(publication)
    retained = fingerprint(Path(publication["output_dir"]))
    assert len(retained) == 1 and rows() == []
    with pytest.raises(FileExistsError):
        publish(publication)
    assert fingerprint(Path(publication["output_dir"])) == retained


@pytest.mark.parametrize("failure", ["partial_html", "index_before_commit", "index_after_commit"])
def test_incomplete_publication_cannot_be_resurrected_by_normal_readers(publication, monkeypatch, failure):
    import storage.create_only_reports as create_only
    from report_history_service import get_report_file, download_report_file
    from report_repository import ReportListQuery
    create, insert = create_only._create_file, publication["repository"].insert
    def partial(path, payload):
        create(path, payload)
        if path.suffix == ".html":
            raise OSError("fixture partial HTML")
    def uncertain(*args, **kwargs):
        if failure == "index_after_commit":
            insert(*args, **kwargs)
        raise OSError("fixture uncertain index result")
    with monkeypatch.context() as patched:
        if failure == "partial_html":
            patched.setattr(create_only, "_create_file", partial)
        else:
            patched.setattr(publication["repository"], "insert", uncertain)
        with pytest.raises(OSError):
            publish(publication)
    before = fingerprint(Path(publication["output_dir"]))
    before_rows = rows()
    assert len(before_rows) == int(failure == "index_after_commit")
    for sync in (False, True):
        result, count = publication["repository"].query(ReportListQuery(
            page=1, limit=10, output_dir=publication["output_dir"], sync_metadata=sync))
        assert result == [] and count == 0
    assert get_report_file(NAME, publication["output_dir"], publication["storage"]).status_code == 404
    for kind in ("html", "md", "data"):
        assert download_report_file(NAME, publication["output_dir"], kind, publication["storage"]).status_code == 404
    from dataclasses import fields, MISSING
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_routes.reports import ReportRouteDeps, create_reports_router
    def forbidden(*args, **kwargs):
        raise AssertionError("read request invoked a mutation dependency")
    deps = {field.name: forbidden for field in fields(ReportRouteDeps) if field.default is MISSING}
    deps.update(get_output_dir=lambda: publication["output_dir"], get_report_storage=lambda: publication["storage"])
    app = FastAPI()
    app.include_router(create_reports_router(ReportRouteDeps(**deps)))
    with TestClient(app) as client:
        response = client.get("/api/reports")
        assert response.status_code == 200 and response.json()["reports"] == []
        for suffix in ("", "/download/html", "/download/md", "/download/data"):
            assert client.get(f"/api/report/{NAME}{suffix}").status_code == 404
    assert fingerprint(Path(publication["output_dir"])) == before
    assert rows() == before_rows


def test_completion_marker_failure_hides_confirmed_index_without_deleting_it(publication, monkeypatch):
    import storage.create_only_reports as create_only
    from report_repository import ReportListQuery
    def fail_rename(*args, **kwargs):
        raise OSError("fixture marker rename failed")
    with monkeypatch.context() as patched:
        patched.setattr(create_only.os, "rename", fail_rename)
        with pytest.raises(OSError, match="marker rename"):
            publish(publication)
    before_rows, before = rows(), fingerprint(Path(publication["output_dir"]))
    assert len(before_rows) == 1
    result, count = publication["repository"].query(ReportListQuery(
        page=1, limit=10, output_dir=publication["output_dir"]))
    assert result == [] and count == 0
    assert rows() == before_rows and fingerprint(Path(publication["output_dir"])) == before


@pytest.mark.parametrize("kind", ["empty", "directory", "symlink", "fifo"])
def test_invalid_completion_marker_is_not_a_publication_receipt(publication, kind, tmp_path):
    import os
    import storage.create_only_reports as create_only
    from report_repository import ReportListQuery
    publish(publication)
    root = Path(publication["output_dir"])
    _, _, complete = create_only._receipt_paths(root, NAME)
    complete.unlink()
    if kind == "empty":
        complete.touch()
    elif kind == "directory":
        complete.mkdir()
    elif kind == "fifo":
        os.mkfifo(complete)
    else:
        other = tmp_path / "other-completion"
        other.write_bytes(b"complete\n")
        complete.symlink_to(other)
    before_rows = rows()
    result, count = publication["repository"].query(ReportListQuery(
        page=1, limit=10, output_dir=str(root)))
    assert result == [] and count == 0 and rows() == before_rows


def test_complete_bundle_receipts_stay_internal_to_storage(publication):
    publish(publication)
    listed = publication["storage"].list_reports()
    assert len(listed) == 3
    assert all(".onstock-storage-publications.tmp" not in item.key for item in listed)


@pytest.mark.parametrize("reader", ["load", "exists"])
def test_reader_rechecks_pending_after_waiting_for_writer(publication, monkeypatch, reader):
    import report_history_storage as history
    import storage.create_only_reports as create_only
    check, create = history.publication_is_pending, create_only._create_file
    calls = 0
    def partial(path, payload):
        create(path, payload)
        if path.suffix == ".html":
            raise OSError("fixture writer partial")
    def concurrent_writer(root, filename):
        nonlocal calls
        calls += 1
        result = check(root, filename)
        if calls == 1:
            assert result is False
            with pytest.raises(OSError, match="writer partial"):
                publish(publication)
        return result
    monkeypatch.setattr(create_only, "_create_file", partial)
    monkeypatch.setattr(history, "publication_is_pending", concurrent_writer)
    read = history.load_storage_item if reader == "load" else history.existing_storage_key
    assert read(publication["storage"], NAME, kind="html") is None
    assert calls >= 2
    assert (Path(publication["output_dir"]) / report_bundle_keys_for_filename(NAME).html_key).exists()
    assert rows() == []
