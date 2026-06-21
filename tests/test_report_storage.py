import os
import sys
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
