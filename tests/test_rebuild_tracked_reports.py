"""Maintenance CLI safety using temporary report storage and fake HTTP only."""

import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import sys
from threading import Event, current_thread
from types import SimpleNamespace

import pytest
import requests


ROOT = Path(__file__).resolve().parents[1]
TARGET = "2026-01/TEST/TEST_v1_report_20260101_090000.html"
OTHER = "2026-01/OTHER/OTHER_v2_report_20260101_090000.html"


@pytest.fixture
def rebuild(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("rebuild_cli_test", ROOT / "scripts/rebuild_tracked_reports.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "external drive" / "output"
    storage = module.LocalFileStorage(output)
    storage.save_report(TARGET, b"valuable prior report", content_type="text/html")
    storage.save_report(OTHER, b"unrelated history", content_type="text/html")
    state = {"active_count": 0, "posts": [], "status_code": 200, "synced": []}

    class Response:
        def __init__(self, body, status=200):
            self.body, self.status = body, status

        def raise_for_status(self):
            if self.status >= 400:
                raise requests.HTTPError(f"HTTP {self.status}")

        def json(self):
            return self.body

    class Session:
        headers = {}

        def get(self, url, **kwargs):
            if url.endswith("/active-jobs"):
                return Response({"active_count": state["active_count"]})
            if url.endswith("/decision-tracking"):
                return Response({"items": [{"ticker": "TEST", "enabled": True, "latest_reports": [
                    {"ticker": "TEST", "pipeline_id": "v1", "filename": Path(TARGET).name},
                    {"ticker": "TEST", "pipeline_id": "v2", "filename": "TEST_v2_report_20260101_090000.html"},
                ]}]})
            if url.endswith("/client-config"):
                return Response({"mutation_header": "X-Test-Mutation", "mutation_token": "fixture-token"})
            if "/api/analysis-jobs/" in url:
                return Response({"status": "completed", "report_path": "fixture.html"})
            raise AssertionError(f"Unexpected HTTP GET: {url}")

        def post(self, url, *, json, **kwargs):
            state["posts"].append(json)
            if state.get("post_hook"):
                state["post_hook"](json)
            job_id = state.get("response_job_id", f"fixture-{len(state['posts'])}")
            return Response({"job_id": job_id, "status": "queued"}, state["status_code"])

    monkeypatch.setattr(module, "current_runtime_paths", lambda: SimpleNamespace(output_dir=output))
    monkeypatch.setattr(module.requests, "Session", Session)
    monkeypatch.setattr(module, "DEFAULT_REPORT_REPOSITORY", SimpleNamespace(sync=lambda directory: state["synced"].append(directory)))
    manifest = tmp_path / "manifest.json"

    def run(action, *args):
        monkeypatch.setattr(sys, "argv", ["rebuild_tracked_reports.py", action, "--manifest", str(manifest), *map(str, args)])
        module.main()

    run("prepare")
    return SimpleNamespace(module=module, storage=storage, state=state, manifest=manifest,
                           run=run, backup=tmp_path / "recoverable backup", output=output)


def test_rebuild_submission_preserves_history_and_batches_existing_modes(rebuild):
    rebuild.run("submit")
    assert {row["pipeline_id"] for row in rebuild.state["posts"]} == {"v1", "v2"}
    assert rebuild.storage.get_report(TARGET).content == b"valuable prior report"
    assert rebuild.storage.get_report(OTHER).content == b"unrelated history"
    rebuild.run("submit")
    assert len(rebuild.state["posts"]) == 2


def test_submit_uses_non_destructive_active_attach_contract(rebuild):
    rebuild.run("submit")
    assert all(row["force"] is False and row["resume"] is True for row in rebuild.state["posts"])


def test_accepted_request_timeout_stays_pending_and_cannot_be_resubmitted(rebuild):
    def accepted_but_response_lost(payload):
        # The request reached the server, but the CLI never learns its job ID.
        raise requests.Timeout("accepted server request; response lost")

    rebuild.state["post_hook"] = accepted_but_response_lost
    with pytest.raises(requests.Timeout):
        rebuild.run("submit")
    item = json.loads(rebuild.manifest.read_text())["jobs"][0]
    assert item["submission_state"] == "pending"
    assert datetime.fromisoformat(item["submission_started_at"]).utcoffset() is not None
    assert not item.get("job_id")
    with pytest.raises(RuntimeError, match="pending.*verify|待確認.*核對"):
        rebuild.run("submit")
    assert len(rebuild.state["posts"]) == 1


def test_pending_is_saved_before_any_request_leaves_the_cli(rebuild):
    def inspect_manifest_at_server(payload):
        items = json.loads(rebuild.manifest.read_text())["jobs"]
        item = next(item for item in items if item["pipeline_id"] == payload["pipeline_id"])
        assert item["submission_state"] == "pending"
        assert item["submission_started_at"]
        assert not item.get("job_id")

    rebuild.state["post_hook"] = inspect_manifest_at_server
    rebuild.run("submit")
    assert all(item["submission_state"] == "accepted" for item in json.loads(rebuild.manifest.read_text())["jobs"])


def test_accepted_job_with_manifest_save_failure_is_not_resent(rebuild, monkeypatch):
    original_save = rebuild.module.save

    def fail_acceptance_save(path, manifest):
        if any(item.get("job_id") for item in manifest["jobs"]):
            raise OSError("acceptance manifest write failed")
        original_save(path, manifest)

    monkeypatch.setattr(rebuild.module, "save", fail_acceptance_save)
    with pytest.raises(OSError, match="acceptance manifest"):
        rebuild.run("submit")
    saved = json.loads(rebuild.manifest.read_text())
    assert saved["jobs"][0]["submission_state"] == "pending"
    assert not saved["jobs"][0].get("job_id")
    with pytest.raises(RuntimeError, match="pending.*verify|待確認.*核對"):
        rebuild.run("submit")
    assert len(rebuild.state["posts"]) == 1


def test_pending_manifest_save_failure_prevents_post(rebuild, monkeypatch):
    def fail_save(*args, **kwargs):
        raise OSError("pending manifest write failed")

    monkeypatch.setattr(rebuild.module, "save", fail_save)
    with pytest.raises(OSError, match="pending manifest"):
        rebuild.run("submit")
    assert rebuild.state["posts"] == []


def test_any_pending_item_blocks_the_entire_batch_before_post(rebuild):
    manifest = json.loads(rebuild.manifest.read_text())
    manifest["jobs"][1].update(submission_state="pending", submission_started_at="2026-09-06T00:00:00+00:00")
    rebuild.module.save(rebuild.manifest, manifest)
    with pytest.raises(RuntimeError, match="pending.*verify|待確認.*核對"):
        rebuild.run("submit")
    assert rebuild.state["posts"] == []


def test_status_preserves_pending_confirmation_until_verified_job_id_is_attached(rebuild):
    manifest = json.loads(rebuild.manifest.read_text())
    manifest["jobs"][0].update(submission_state="pending", submission_started_at="2026-09-06T00:00:00+00:00")
    rebuild.module.save(rebuild.manifest, manifest)
    rebuild.run("status")
    manifest = json.loads(rebuild.manifest.read_text())
    assert manifest["jobs"][0]["status"] == "pending_confirmation"
    assert manifest["jobs"][1]["status"] == "not_submitted"
    # An operator first verifies this ID against the existing job listing.
    manifest["jobs"][0]["job_id"] = "manually-verified-job"
    rebuild.module.save(rebuild.manifest, manifest)
    rebuild.run("submit")
    assert [item["pipeline_id"] for item in rebuild.state["posts"]] == ["v2"]
    assert json.loads(rebuild.manifest.read_text())["jobs"][0]["job_id"] == "manually-verified-job"


def test_concurrent_submits_lock_then_reread_the_same_manifest(rebuild, monkeypatch):
    first_post = Event()
    release_first = Event()
    second_lock_requested = Event()
    original_lock = rebuild.module.exclusive_storage_lock

    @contextmanager
    def observe_real_lock(root):
        if current_thread().name.endswith("_1"):
            second_lock_requested.set()
        with original_lock(root):
            yield

    def hold_first_post(payload):
        if not first_post.is_set():
            first_post.set()
            assert release_first.wait(5), "test did not release the first request"

    monkeypatch.setattr(rebuild.module, "exclusive_storage_lock", observe_real_lock)
    rebuild.state["post_hook"] = hold_first_post
    monkeypatch.setattr(sys, "argv", ["rebuild_tracked_reports.py", "submit", "--manifest", str(rebuild.manifest)])
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="manifest-submit") as pool:
        first = pool.submit(rebuild.module.main)
        assert first_post.wait(5)
        second = pool.submit(rebuild.module.main)
        try:
            assert second_lock_requested.wait(2), "concurrent submit did not acquire a manifest lock"
            assert not second.done()
        finally:
            release_first.set()
        first.result(timeout=5)
        second.result(timeout=5)
    assert len(rebuild.state["posts"]) == 2
    assert [item["job_id"] for item in json.loads(rebuild.manifest.read_text())["jobs"]] == ["fixture-1", "fixture-2"]


@pytest.mark.parametrize("job_id", [None, "", "   ", 123])
def test_unusable_acceptance_job_id_keeps_manifest_pending(rebuild, job_id):
    rebuild.state["response_job_id"] = job_id
    with pytest.raises(RuntimeError, match="pending.*verify"):
        rebuild.run("submit")
    assert json.loads(rebuild.manifest.read_text())["jobs"][0]["submission_state"] == "pending"
    with pytest.raises(RuntimeError, match="pending.*verify"):
        rebuild.run("submit")
    assert len(rebuild.state["posts"]) == 1


def test_manifest_inside_output_does_not_nest_the_same_storage_lock(rebuild, monkeypatch):
    original_lock = rebuild.module.exclusive_storage_lock
    held_roots = set()

    @contextmanager
    def reject_nested_root_lock(root):
        resolved = root.resolve()
        assert resolved not in held_roots, "nested flock on the same directory can deadlock"
        held_roots.add(resolved)
        try:
            with original_lock(root):
                yield
        finally:
            held_roots.remove(resolved)

    monkeypatch.setattr(rebuild.module, "exclusive_storage_lock", reject_nested_root_lock)
    storage_module = sys.modules[rebuild.module.LocalFileStorage.__module__]
    monkeypatch.setattr(storage_module, "exclusive_storage_lock", reject_nested_root_lock)
    inside_manifest = rebuild.output / "maintenance manifest.json"
    rebuild.run("prepare", "--manifest", inside_manifest)
    rebuild.run("submit", "--manifest", inside_manifest)
    rebuild.run("status", "--manifest", inside_manifest)
    _purge(rebuild, "--manifest", inside_manifest)
    assert json.loads(inside_manifest.read_text())["purge_backups"][-1]["state"] == "purged"
    assert rebuild.storage.get_report(OTHER).content == b"unrelated history"


def test_purge_without_explicit_confirmation_does_not_delete_history(rebuild):
    with pytest.raises((ValueError, RuntimeError), match="confirm|確認"):
        rebuild.run("purge")
    assert rebuild.storage.exists(TARGET) and rebuild.storage.exists(OTHER)
    assert rebuild.state["synced"] == []


def _purge(rebuild, *extra, backup=None, key=TARGET):
    rebuild.run("purge", "--confirm-purge", "--backup-dir", backup or rebuild.backup,
                "--report-key", key, *extra)


def test_confirmed_purge_backs_up_only_explicit_targets_and_retains_other_history(rebuild):
    _purge(rebuild)
    assert not rebuild.storage.exists(TARGET)
    assert rebuild.storage.get_report(OTHER).content == b"unrelated history"
    backup = rebuild.module.LocalFileStorage(rebuild.backup)
    assert backup.get_report(TARGET).content == b"valuable prior report"
    assert not backup.exists(OTHER)
    saved = json.loads(rebuild.manifest.read_text())
    assert saved["purge_backups"][-1]["keys"] == [TARGET]
    assert saved["purge_backups"][-1]["backup_dir"] == str(rebuild.backup)


@pytest.mark.parametrize("key", ["../outside.html", "not-in-manifest.html"])
def test_purge_rejects_unprepared_or_escaping_target(rebuild, key):
    with pytest.raises((ValueError, RuntimeError)):
        _purge(rebuild, key=key)
    assert rebuild.storage.exists(TARGET) and rebuild.storage.exists(OTHER)


def test_purge_rejects_changed_content_since_prepare(rebuild):
    rebuild.storage.save_report(TARGET, b"new report at same key", content_type="text/html")
    with pytest.raises((ValueError, RuntimeError), match="changed|變更"):
        _purge(rebuild)
    assert rebuild.storage.get_report(TARGET).content == b"new report at same key"


def test_purge_rechecks_active_jobs_before_removing_anything(rebuild):
    rebuild.state["active_count"] = 1
    with pytest.raises(RuntimeError, match="active|執行"):
        _purge(rebuild)
    assert rebuild.storage.exists(TARGET)


def test_backup_cannot_live_inside_the_report_directory(rebuild):
    with pytest.raises((ValueError, RuntimeError), match="backup|備份"):
        _purge(rebuild, backup=rebuild.output / "backup")
    assert rebuild.storage.exists(TARGET)


def test_failed_backup_never_deletes_source(rebuild, monkeypatch):
    def fail_save(*args, **kwargs):
        raise OSError("backup disk unavailable")

    monkeypatch.setattr(rebuild.module.LocalFileStorage, "save_report", fail_save)
    with pytest.raises(OSError, match="backup disk"):
        _purge(rebuild)
    assert rebuild.storage.get_report(TARGET).content == b"valuable prior report"


def test_submission_stops_on_quota_rejection_and_never_retries_or_changes_routes(rebuild):
    rebuild.state["status_code"] = 429
    with pytest.raises(requests.HTTPError, match="429"):
        rebuild.run("submit")
    assert len(rebuild.state["posts"]) == 1
    assert rebuild.storage.exists(TARGET) and rebuild.storage.exists(OTHER)


def test_backup_directory_created_concurrently_is_not_reused_or_overwritten(rebuild, monkeypatch):
    original_mkdir = Path.mkdir
    raced = False

    def mkdir(path, *args, **kwargs):
        nonlocal raced
        if path == rebuild.backup and not raced:
            raced = True
            original_mkdir(path, parents=True)
            (path / "keep-existing-backup").write_bytes(b"valuable existing backup")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    with pytest.raises(FileExistsError):
        _purge(rebuild)
    assert rebuild.storage.exists(TARGET)
    assert (rebuild.backup / "keep-existing-backup").read_bytes() == b"valuable existing backup"


def test_backup_preserves_the_original_content_type(rebuild):
    rebuild.storage.save_report(TARGET, b"valuable prior report", content_type="application/xhtml+xml")
    _purge(rebuild)
    backup = rebuild.module.LocalFileStorage(rebuild.backup)
    assert backup.get_report(TARGET).metadata.content_type == "application/xhtml+xml"


def test_backup_verification_failure_preserves_all_source_content(rebuild, monkeypatch):
    original_get = rebuild.module.LocalFileStorage.get_report

    def get(storage, key):
        if storage._root == rebuild.backup:
            return SimpleNamespace(content=b"corrupt backup")
        return original_get(storage, key)

    monkeypatch.setattr(rebuild.module.LocalFileStorage, "get_report", get)
    with pytest.raises(RuntimeError, match="Backup verification"):
        _purge(rebuild)
    assert rebuild.storage.get_report(TARGET).content == b"valuable prior report"


def test_purge_rejects_a_target_replaced_by_a_symlink(rebuild, tmp_path):
    source = rebuild.output / TARGET
    outside = tmp_path / "external-valuables.html"
    outside.write_bytes(b"valuable prior report")
    source.unlink()
    source.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        _purge(rebuild)
    assert source.is_symlink()
    assert outside.read_bytes() == b"valuable prior report"
