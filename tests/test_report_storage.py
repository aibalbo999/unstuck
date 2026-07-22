import os
import stat
import sys
import threading
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from storage.report_storage import (  # noqa: E402
    InMemoryStorage,
    LocalFileStorage,
    ReportStorage,
    StoredReport,
    StoredReportContent,
    normalize_report_key,
)
from storage.memory_report_storage import InMemoryStorage as DirectInMemoryStorage  # noqa: E402
import storage.report_storage as report_storage_module  # noqa: E402


def test_local_storage_round_trip_and_lists_sorted_metadata(tmp_path):
    storage_root = tmp_path / "reports"
    storage = LocalFileStorage(storage_root)

    assert storage_root.is_dir()
    assert isinstance(storage, ReportStorage)

    html = storage.save_report(
        "nested/report.html",
        b"<html>report</html>",
        content_type="text/html",
    )
    markdown = storage.save_report(
        "report.md",
        b"# Report",
        content_type="text/markdown",
    )
    snapshot = storage.save_report(
        "nested/report.data.json",
        b'{"ok": true}',
        content_type="application/json",
    )

    assert html.key == "nested/report.html"
    assert html.size == len(b"<html>report</html>")
    assert html.content_type == "text/html"
    assert html.updated_at.utcoffset().total_seconds() == 0
    assert markdown.content_type == "text/markdown"
    assert snapshot.content_type == "application/json"

    loaded = storage.get_report("nested/report.html")
    assert loaded == StoredReportContent(metadata=html, content=b"<html>report</html>")
    assert storage.exists("nested/report.html") is True
    assert storage.exists("missing.html") is False

    listed = storage.list_reports()
    assert [item.key for item in listed] == [
        "nested/report.data.json",
        "nested/report.html",
        "report.md",
    ]
    assert listed == [snapshot, html, markdown]
    assert storage.list_reports(prefix="nested/report.") == [snapshot, html]
    assert not list(storage_root.rglob("*.tmp"))


def test_local_storage_failed_replace_preserves_old_content_and_cleans_temp(tmp_path, monkeypatch):
    storage = LocalFileStorage(tmp_path)
    storage.save_report("report.html", b"old", content_type="text/html")

    def fail_replace(source, target):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        storage.save_report("report.html", b"new", content_type="text/html")

    assert storage.get_report("report.html").content == b"old"
    assert not list(tmp_path.rglob("*.tmp"))


def test_local_storage_preserves_custom_content_type_across_restart_and_delete(tmp_path):
    custom_type = "application/vnd.onstock.report"
    storage = LocalFileStorage(tmp_path)

    saved = storage.save_report("report.custom", b"report", content_type=custom_type)

    reopened = LocalFileStorage(tmp_path)
    assert saved.content_type == custom_type
    assert reopened.get_report("report.custom").metadata.content_type == custom_type
    assert reopened.list_reports() == [saved]

    assert reopened.delete_report("report.custom") is True
    assert not list(tmp_path.iterdir())


def test_local_storage_falls_back_to_suffix_for_missing_or_corrupt_metadata(tmp_path):
    storage = LocalFileStorage(tmp_path)
    storage.save_report(
        "report.html",
        b"report",
        content_type="application/vnd.onstock.report",
    )
    sidecar = next(path for path in tmp_path.iterdir() if "onstock-metadata" in path.name)

    sidecar.write_text("not-json", encoding="utf-8")
    assert storage.get_report("report.html").metadata.content_type == "text/html"
    assert storage.list_reports()[0].content_type == "text/html"

    sidecar.write_text(
        '{"content_type":"application/x-custom","sha256":"é"}',
        encoding="utf-8",
    )
    assert storage.get_report("report.html").metadata.content_type == "text/html"
    assert storage.list_reports()[0].content_type == "text/html"

    sidecar.unlink()
    assert storage.get_report("report.html").metadata.content_type == "text/html"
    assert storage.list_reports()[0].content_type == "text/html"


def test_local_storage_rejects_symlink_root(tmp_path):
    real_root = tmp_path / "real"
    real_root.mkdir()
    symlink_root = tmp_path / "alias"
    symlink_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        LocalFileStorage(symlink_root)


def test_local_storage_rejects_in_root_file_symlink_for_save_and_delete(tmp_path):
    storage = LocalFileStorage(tmp_path)
    storage.save_report("original.html", b"original", content_type="text/html")
    alias = tmp_path / "alias.html"
    alias.symlink_to(tmp_path / "original.html")

    with pytest.raises(ValueError, match="symlink"):
        storage.save_report("alias.html", b"replacement", content_type="text/html")
    with pytest.raises(ValueError, match="symlink"):
        storage.delete_report("alias.html")

    assert storage.get_report("original.html").content == b"original"
    assert alias.is_symlink()


def test_local_storage_rejects_outside_symlink_directory(tmp_path):
    storage_root = tmp_path / "reports"
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    original = outside_root / "original.html"
    original.write_bytes(b"outside")
    storage = LocalFileStorage(storage_root)
    (storage_root / "linked").symlink_to(outside_root, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        storage.save_report("linked/original.html", b"replacement", content_type="text/html")
    with pytest.raises(ValueError, match="symlink"):
        storage.delete_report("linked/original.html")

    assert original.read_bytes() == b"outside"


def test_local_storage_fsyncs_report_files_and_containing_directories(tmp_path, monkeypatch):
    fsync_target_types = []
    real_fsync = os.fsync

    def recording_fsync(file_descriptor):
        fsync_target_types.append(stat.S_ISDIR(os.fstat(file_descriptor).st_mode))
        return real_fsync(file_descriptor)

    monkeypatch.setattr(os, "fsync", recording_fsync)

    LocalFileStorage(tmp_path).save_report(
        "nested/report.html",
        b"report",
        content_type="text/html",
    )

    assert False in fsync_target_types
    assert True in fsync_target_types


def test_local_storage_lists_legitimate_dotfile_with_tmp_suffix(tmp_path):
    storage = LocalFileStorage(tmp_path)
    saved = storage.save_report(
        ".draft.tmp",
        b"draft",
        content_type="application/x-onstock-draft",
    )

    assert storage.list_reports() == [saved]


@pytest.mark.parametrize(
    "key",
    [
        ".report.html.onstock-metadata.json",
        ".onstock-storage-user.tmp",
        "nested/.report.html.onstock-metadata.json/child.html",
    ],
)
def test_local_storage_rejects_keys_reserved_for_internal_files(tmp_path, key):
    storage = LocalFileStorage(tmp_path)

    with pytest.raises(ValueError, match="reserved"):
        storage.save_report(key, b"report", content_type="text/html")


def test_local_storage_rolls_back_metadata_when_report_replace_fails(tmp_path, monkeypatch):
    storage = LocalFileStorage(tmp_path)
    storage.save_report(
        "report.html",
        b"old",
        content_type="application/vnd.onstock.old",
    )
    real_replace = os.replace
    replace_count = 0

    def fail_second_replace(source, target):
        nonlocal replace_count
        replace_count += 1
        if replace_count == 2:
            raise OSError("report replace failed")
        return real_replace(source, target)

    monkeypatch.setattr(os, "replace", fail_second_replace)

    with pytest.raises(OSError, match="report replace failed"):
        storage.save_report(
            "report.html",
            b"new",
            content_type="application/vnd.onstock.new",
        )

    loaded = storage.get_report("report.html")
    assert loaded.content == b"old"
    assert loaded.metadata.content_type == "application/vnd.onstock.old"


def test_local_storage_serializes_two_writers_for_the_same_key(tmp_path, monkeypatch):
    storage_a = LocalFileStorage(tmp_path)
    storage_b = LocalFileStorage(tmp_path)
    real_atomic_write = report_storage_module.atomic_write
    writer_a_first_write = threading.Event()
    writer_a_calls = 0

    def slow_first_writer(target, payload):
        nonlocal writer_a_calls
        real_atomic_write(target, payload)
        if threading.current_thread().name == "writer-a":
            writer_a_calls += 1
            if writer_a_calls == 1:
                writer_a_first_write.set()
                time.sleep(0.2)

    monkeypatch.setattr(report_storage_module, "atomic_write", slow_first_writer)

    writer_a = threading.Thread(
        name="writer-a",
        target=storage_a.save_report,
        args=("report.bin", b"a"),
        kwargs={"content_type": "application/x-writer-a"},
    )
    writer_b = threading.Thread(
        name="writer-b",
        target=storage_b.save_report,
        args=("report.bin", b"b"),
        kwargs={"content_type": "application/x-writer-b"},
    )

    writer_a.start()
    assert writer_a_first_write.wait(timeout=1)
    writer_b.start()
    writer_a.join(timeout=2)
    writer_b.join(timeout=2)

    assert not writer_a.is_alive()
    assert not writer_b.is_alive()
    loaded = storage_a.get_report("report.bin")
    expected_type = {
        b"a": "application/x-writer-a",
        b"b": "application/x-writer-b",
    }
    assert loaded.metadata.content_type == expected_type[loaded.content]


@pytest.mark.parametrize(
    "key",
    ["", "../secret", "/tmp/secret", "a/../../secret", r"a\..\secret"],
)
def test_normalize_report_key_rejects_unsafe_paths(key):
    with pytest.raises(ValueError):
        normalize_report_key(key)


def test_in_memory_storage_defensively_copies_mutable_content_and_deletes():
    storage = InMemoryStorage()
    source = bytearray(b"original")

    saved = storage.save_report("report.md", source, content_type="text/markdown")
    source[:] = b"mutated!"

    first = storage.get_report("report.md")
    second = storage.get_report("report.md")
    assert first.content == b"original"
    assert first.metadata == saved
    assert first is not second
    assert first.metadata is not second.metadata
    assert storage.exists("report.md") is True

    assert storage.delete_report("report.md") is True
    assert storage.delete_report("report.md") is False
    assert storage.exists("report.md") is False
    assert storage.get_report("report.md") is None


def test_in_memory_storage_keeps_report_storage_reexport_identity():
    assert InMemoryStorage is DirectInMemoryStorage


def test_in_memory_prefix_listing_is_deterministic_and_returns_value_copies():
    storage = InMemoryStorage()
    storage.save_report("z/report.html", b"z", content_type="text/html")
    storage.save_report("a/two.json", b"2", content_type="application/json")
    storage.save_report("a/one.md", b"1", content_type="text/markdown")

    first = storage.list_reports(prefix="a/")
    second = storage.list_reports(prefix="a/")

    assert [item.key for item in first] == ["a/one.md", "a/two.json"]
    assert first == second
    assert all(left is not right for left, right in zip(first, second))
