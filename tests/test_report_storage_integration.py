import asyncio
import json
import os
import time
from datetime import datetime, timezone
from types import MappingProxyType, SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_routes.reports import ReportRouteDeps, create_reports_router
from data_trust import data_snapshot_filename_for_report
from report_history_service import (
    cleanup_expired_reports,
    cleanup_orphan_markdown_reports,
    delete_report_files,
    download_report_file,
    get_report_file,
    list_reports,
)
from reporting import ReportBundle
from storage.report_storage import InMemoryStorage, StoredReport, StoredReportContent


class RecordingStorage:
    def __init__(self, *, fail_on_key: str | None = None):
        self.fail_on_key = fail_on_key
        self.saved: dict[str, StoredReportContent] = {}
        self.order: list[str] = []
        self.deleted: list[str] = []

    def save_report(self, key: str, content: bytes, *, content_type: str) -> StoredReport:
        label = _label_for_key(key)
        self.order.append(f"save:{label}")
        if key == self.fail_on_key:
            raise RuntimeError(f"boom: {key}")
        metadata = StoredReport(
            key=key,
            size=len(content),
            content_type=content_type,
            updated_at=datetime.now(timezone.utc),
        )
        self.saved[key] = StoredReportContent(metadata=metadata, content=bytes(content))
        return metadata

    def get_report(self, key: str) -> StoredReportContent | None:
        return self.saved.get(key)

    def delete_report(self, key: str) -> bool:
        self.deleted.append(key)
        return self.saved.pop(key, None) is not None

    def exists(self, key: str) -> bool:
        return key in self.saved

    def list_reports(self, *, prefix: str = "") -> list[StoredReport]:
        return [
            item.metadata
            for key, item in sorted(self.saved.items())
            if key.startswith(prefix)
        ]


class RecordingRepository:
    def __init__(self, order: list[str] | None = None, *, metadata_exists: bool = False):
        self.order = order if order is not None else []
        self.metadata_exists = metadata_exists
        self.upserts: list[dict] = []
        self.deleted: list[tuple[str, str | None]] = []

    def upsert(self, filename: str, **kwargs):
        self.order.append("index")
        self.upserts.append({"filename": filename, **kwargs})
        return {"filename": filename, "indexed": True}

    def delete(self, filename: str, output_dir: str | None = None) -> None:
        self.deleted.append((filename, output_dir))

    def exists(self, filename: str, output_dir: str | None = None) -> bool:
        return self.metadata_exists


class FailingUpsertRepository(RecordingRepository):
    def upsert(self, filename: str, **kwargs):
        self.order.append("index")
        raise RuntimeError("metadata upsert failed")


class FailingDeleteRepository(RecordingRepository):
    def delete(self, filename: str, output_dir: str | None = None) -> None:
        self.deleted.append((filename, output_dir))
        raise RuntimeError("metadata delete failed")


class RecordingLock:
    def __init__(self):
        self.entered = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _label_for_key(key: str) -> str:
    if key.endswith(".html"):
        return "html"
    if key.endswith(".md"):
        return "md"
    if key.endswith(".data.json"):
        return "data"
    return key


def test_persist_report_bundle_saves_content_before_indexing():
    from report_persistence import persist_report_bundle

    filename = "2308_TW_v2_report_20260626_120000.html"
    storage = RecordingStorage()
    repository = RecordingRepository(storage.order)

    result = persist_report_bundle(
        filename=filename,
        html_content="<html>台達電</html>",
        markdown_content="# 台達電\n",
        data_snapshot={"ticker": "2308.TW", "data_trust": {"status": "fresh"}},
        storage=storage,
        output_dir="/reports",
        repository=repository,
    )

    assert storage.order == ["save:html", "save:md", "save:data", "index"]
    assert result["filename"] == filename
    assert result["md_filename"] == "2308_TW_v2_report_20260626_120000.md"
    assert result["data_filename"] == data_snapshot_filename_for_report(filename)
    assert result["html_key"] == f"2026-06/2308.TW/{filename}"
    assert result["md_key"] == f"2026-06/2308.TW/{result['md_filename']}"
    assert result["data_key"] == f"2026-06/2308.TW/{result['data_filename']}"
    assert repository.upserts == [
        {
            "filename": filename,
            "output_dir": "/reports",
            "html_content": "<html>台達電</html>",
            "markdown_content": "# 台達電\n",
            "data_trust": {"status": "fresh"},
        }
    ]
    assert storage.saved[result["data_key"]].content == json.dumps(
        {"ticker": "2308.TW", "data_trust": {"status": "fresh"}},
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def test_persist_report_bundle_accepts_mapping_safe_data_snapshot():
    from report_persistence import persist_report_bundle

    filename = "2308_TW_v2_report_20260626_120000.html"
    storage = RecordingStorage()
    repository = RecordingRepository(storage.order)
    data_snapshot = MappingProxyType(
        {
            "ticker": "2308.TW",
            "data_trust": MappingProxyType(
                {
                    "status": "fresh",
                    "reason_codes": ("fresh_core_sources",),
                }
            ),
        }
    )

    result = persist_report_bundle(
        filename=filename,
        html_content="<html>台達電</html>",
        markdown_content="# 台達電\n",
        data_snapshot=data_snapshot,
        storage=storage,
        output_dir="/reports",
        repository=repository,
    )

    expected_snapshot = {
        "ticker": "2308.TW",
        "data_trust": {"status": "fresh", "reason_codes": ["fresh_core_sources"]},
    }
    assert repository.upserts[0]["data_trust"] == expected_snapshot["data_trust"]
    assert result["data_trust"] == expected_snapshot["data_trust"]
    assert json.loads(storage.saved[result["data_key"]].content.decode("utf-8")) == expected_snapshot


def test_persist_report_bundle_rolls_back_saved_content_when_data_save_fails():
    from report_persistence import persist_report_bundle

    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    data_filename = f"2026-06/2308.TW/{data_snapshot_filename_for_report(filename)}"
    storage = RecordingStorage(fail_on_key=data_filename)
    repository = RecordingRepository(storage.order)

    try:
        persist_report_bundle(
            filename=filename,
            html_content="<html></html>",
            markdown_content="# report\n",
            data_snapshot={"ticker": "2308.TW"},
            storage=storage,
            output_dir="/reports",
            repository=repository,
        )
    except RuntimeError as exc:
        assert str(exc) == f"boom: {data_filename}"
    else:
        raise AssertionError("expected data save failure")

    assert storage.deleted == [f"2026-06/2308.TW/{md_filename}", f"2026-06/2308.TW/{filename}"]
    assert filename not in storage.saved
    assert md_filename not in storage.saved
    assert repository.upserts == []
    assert "index" not in storage.order


def test_persist_report_bundle_rolls_back_saved_content_when_metadata_upsert_fails():
    from report_persistence import persist_report_bundle

    filename = "2308_TW_v2_report_20260626_120000.html"
    storage = RecordingStorage()
    repository = FailingUpsertRepository(storage.order)

    try:
        persist_report_bundle(
            filename=filename,
            html_content="<html></html>",
            markdown_content="# report\n",
            data_snapshot={"ticker": "2308.TW"},
            storage=storage,
            output_dir="/reports",
            repository=repository,
        )
    except RuntimeError as exc:
        assert str(exc) == "metadata upsert failed"
    else:
        raise AssertionError("expected metadata upsert failure")

    assert storage.deleted == [
        f"2026-06/2308.TW/{data_snapshot_filename_for_report(filename)}",
        "2026-06/2308.TW/2308_TW_v2_report_20260626_120000.md",
        f"2026-06/2308.TW/{filename}",
    ]
    assert storage.saved == {}


def test_report_bundle_keys_partition_by_report_month_and_ticker():
    from report_persistence import report_bundle_keys_for_filename

    filename = "2308_TW_v2_report_20260626_120000.html"

    keys = report_bundle_keys_for_filename(filename)

    assert keys.filename == filename
    assert keys.html_key == f"2026-06/2308.TW/{filename}"
    assert keys.md_key == "2026-06/2308.TW/2308_TW_v2_report_20260626_120000.md"
    assert keys.data_key == f"2026-06/2308.TW/{data_snapshot_filename_for_report(filename)}"


def test_list_reports_uses_metadata_without_syncing_nonlocal_storage(tmp_path):
    from report_persistence import persist_report_bundle

    storage = InMemoryStorage()
    missing_output_dir = tmp_path / "missing-output-dir"
    filename = "2308_TW_v2_report_20260626_120000.html"
    persist_report_bundle(
        filename=filename,
        html_content="<html><body>台達電</body></html>",
        markdown_content="# 投資建議\n\n買入\n",
        data_snapshot={"ticker": "2308.TW", "data_trust": {"status": "fresh"}},
        storage=storage,
        output_dir=str(missing_output_dir),
    )

    result = list_reports(
        page=1,
        limit=10,
        q="",
        pipeline="all",
        recommendation="all",
        data_trust="all",
        output_dir=str(missing_output_dir),
        report_cache={},
        storage=storage,
    )

    assert [report["filename"] for report in result["reports"]] == [filename]


def test_get_report_file_reads_storage_and_repairs_html():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(
        filename,
        '<p>台達電（<a href="http://2308.TW">2308.TW</a>）</p>'.encode("utf-8"),
        content_type="text/html",
    )

    response = get_report_file(filename, "/missing-output-dir", storage=storage)

    assert response.status_code == 200
    assert 'href="https://tw.stock.yahoo.com/quote/2308.TW"' in response.body.decode("utf-8")


def test_get_report_file_replaces_static_notice_when_snapshot_integrity_is_invalid():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(
        filename,
        """
        <html><body>
        <section class="report-reading-notice report-reading-notice-passed">
            <span class="report-reading-notice-status">已通過已知檢查</span>
        </section>
        <p>from storage</p>
        </body></html>
        """.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_hash": "expected-but-stale",
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = get_report_file(filename, "/missing-output-dir", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "from storage" in body
    assert "report-reading-notice-blocked" in body
    assert "品質 gate 未通過" in body
    assert "snapshot_hash mismatch" in body
    assert "report-reading-notice-passed" not in body


def test_get_report_file_replaces_static_notice_when_data_snapshot_is_malformed():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(
        filename,
        """
        <html><body>
        <section class="report-reading-notice report-reading-notice-passed">
            <span class="report-reading-notice-status">已通過已知檢查</span>
        </section>
        <p>malformed snapshot report</p>
        </body></html>
        """.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(data_snapshot_filename_for_report(filename), b"{", content_type="application/json")

    response = get_report_file(filename, "/missing-output-dir", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "malformed snapshot report" in body
    assert "report-reading-notice-blocked" in body
    assert "資料快照無法解析" in body
    assert "report-reading-notice-passed" not in body


def test_get_report_file_replaces_static_notice_when_snapshot_records_invalid_integrity_without_hash():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(
        filename,
        """
        <html><body>
        <section class="report-reading-notice report-reading-notice-passed">
            <span class="report-reading-notice-status">已通過已知檢查</span>
        </section>
        <p>recorded invalid snapshot report</p>
        </body></html>
        """.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {
                    "status": "verified",
                    "valid": False,
                    "errors": ["snapshot verifier rejected stale source bundle"],
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = get_report_file(filename, "/missing-output-dir", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "recorded invalid snapshot report" in body
    assert "report-reading-notice-blocked" in body
    assert "snapshot verifier rejected stale source bundle" in body
    assert "report-reading-notice-passed" not in body


def test_get_report_file_derives_hash_mismatch_detail_from_recorded_invalid_integrity_hashes():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(
        filename,
        """
        <html><body>
        <section class="report-reading-notice report-reading-notice-passed">
            <span class="report-reading-notice-status">已通過已知檢查</span>
        </section>
        <p>recorded hash mismatch report</p>
        </body></html>
        """.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {
                    "status": "invalid",
                    "hash": "actual-hash",
                    "expected_hash": "expected-hash",
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = get_report_file(filename, "/missing-output-dir", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "recorded hash mismatch report" in body
    assert "report-reading-notice-blocked" in body
    assert "snapshot_hash mismatch" in body
    assert "report-reading-notice-passed" not in body


def test_get_report_file_prefers_hash_mismatch_over_recorded_generic_integrity_error():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    generic_error = "資料快照完整性未通過，不能直接引用報告結論。"
    storage.save_report(
        filename,
        """
        <html><body>
        <section class="report-reading-notice report-reading-notice-passed">
            <span class="report-reading-notice-status">已通過已知檢查</span>
        </section>
        <p>recorded generic hash mismatch report</p>
        </body></html>
        """.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {
                    "status": "invalid",
                    "errors": [generic_error],
                    "hash": "actual-hash",
                    "expected_hash": "expected-hash",
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = get_report_file(filename, "/missing-output-dir", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "recorded generic hash mismatch report" in body
    assert "report-reading-notice-blocked" in body
    assert "snapshot_hash mismatch" in body
    assert generic_error not in body
    assert "report-reading-notice-passed" not in body


def test_get_report_file_removes_recorded_generic_integrity_error_when_specific_detail_exists():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    generic_error = "資料快照完整性未通過，不能直接引用報告結論。"
    specific_error = "provider audit source digest mismatch"
    storage.save_report(
        filename,
        """
        <html><body>
        <section class="report-reading-notice report-reading-notice-passed">
            <span class="report-reading-notice-status">已通過已知檢查</span>
        </section>
        <p>recorded mixed integrity errors report</p>
        </body></html>
        """.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {
                    "status": "invalid",
                    "errors": [generic_error, specific_error],
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = get_report_file(filename, "/missing-output-dir", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "recorded mixed integrity errors report" in body
    assert "report-reading-notice-blocked" in body
    assert specific_error in body
    assert generic_error not in body
    assert "report-reading-notice-passed" not in body


def test_get_report_file_deduplicates_recorded_integrity_error_details():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    specific_error = "provider audit source digest mismatch"
    storage.save_report(
        filename,
        """
        <html><body>
        <section class="report-reading-notice report-reading-notice-passed">
            <span class="report-reading-notice-status">已通過已知檢查</span>
        </section>
        <p>recorded duplicate integrity errors report</p>
        </body></html>
        """.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {
                    "status": "invalid",
                    "errors": [specific_error, specific_error],
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = get_report_file(filename, "/missing-output-dir", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "recorded duplicate integrity errors report" in body
    assert "report-reading-notice-blocked" in body
    assert body.count(specific_error) == 1
    assert "report-reading-notice-passed" not in body


def test_get_report_file_replaces_static_notice_when_nested_snapshot_integrity_is_invalid():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(
        filename,
        """
        <html><body>
        <section class="report-reading-notice report-reading-notice-passed">
            <span class="report-reading-notice-status">已通過已知檢查</span>
        </section>
        <p>nested invalid snapshot report</p>
        </body></html>
        """.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "data": {
                    "snapshot_integrity": {
                        "status": "invalid",
                        "errors": ["nested snapshot integrity rejected stale source bundle"],
                    },
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = get_report_file(filename, "/missing-output-dir", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "nested invalid snapshot report" in body
    assert "report-reading-notice-blocked" in body
    assert "nested snapshot integrity rejected stale source bundle" in body
    assert "report-reading-notice-passed" not in body


def test_get_report_file_uses_nested_invalid_integrity_even_when_top_level_is_verified():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(
        filename,
        """
        <html><body>
        <section class="report-reading-notice report-reading-notice-passed">
            <span class="report-reading-notice-status">已通過已知檢查</span>
        </section>
        <p>conflicting snapshot report</p>
        </body></html>
        """.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {"status": "verified", "valid": True},
                "data": {
                    "snapshot_integrity": {
                        "status": "invalid",
                        "errors": ["nested integrity must override top-level verified status"],
                    },
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = get_report_file(filename, "/missing-output-dir", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "conflicting snapshot report" in body
    assert "report-reading-notice-blocked" in body
    assert "nested integrity must override top-level verified status" in body
    assert "report-reading-notice-passed" not in body


def test_get_report_file_prefers_specific_nested_invalid_detail_over_generic_top_level_invalid():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(
        filename,
        """
        <html><body>
        <section class="report-reading-notice report-reading-notice-passed">
            <span class="report-reading-notice-status">已通過已知檢查</span>
        </section>
        <p>specific nested detail report</p>
        </body></html>
        """.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {"status": "invalid"},
                "data": {
                    "snapshot_integrity": {
                        "status": "invalid",
                        "errors": ["nested provider audit hash mismatch"],
                    },
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = get_report_file(filename, "/missing-output-dir", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "specific nested detail report" in body
    assert "report-reading-notice-blocked" in body
    assert "nested provider audit hash mismatch" in body
    assert "report-reading-notice-passed" not in body


def test_get_report_file_prefers_specific_nested_invalid_detail_over_generic_top_level_error_text():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(
        filename,
        """
        <html><body>
        <section class="report-reading-notice report-reading-notice-passed">
            <span class="report-reading-notice-status">已通過已知檢查</span>
        </section>
        <p>generic top-level detail report</p>
        </body></html>
        """.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {
                    "status": "invalid",
                    "errors": ["資料快照完整性未通過，不能直接引用報告結論。"],
                },
                "data": {
                    "snapshot_integrity": {
                        "status": "invalid",
                        "errors": ["nested provider audit hash mismatch"],
                    },
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = get_report_file(filename, "/missing-output-dir", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "generic top-level detail report" in body
    assert "report-reading-notice-blocked" in body
    assert "nested provider audit hash mismatch" in body
    assert "report-reading-notice-passed" not in body


def test_get_report_file_replaces_static_notice_when_data_snapshot_is_missing():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(
        filename,
        """
        <html><body>
        <section class="report-reading-notice report-reading-notice-passed">
            <span class="report-reading-notice-status">已通過已知檢查</span>
        </section>
        <p>missing snapshot report</p>
        </body></html>
        """.encode("utf-8"),
        content_type="text/html",
    )

    response = get_report_file(filename, "/missing-output-dir", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "missing snapshot report" in body
    assert "report-reading-notice-warning" in body
    assert "資料快照不存在" in body
    assert "report-reading-notice-passed" not in body


def test_download_report_file_reads_storage_for_html_markdown_and_data():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    data_filename = data_snapshot_filename_for_report(filename)
    storage.save_report(
        filename,
        '<a href="http://2308.TW">2308.TW</a>'.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(md_filename, "# 台達電\n".encode("utf-8"), content_type="text/markdown")
    storage.save_report(data_filename, b'{"ticker":"2308.TW"}', content_type="application/json")

    html_response = download_report_file(filename, "/missing-output-dir", "html", storage=storage)
    md_response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    data_response = download_report_file(filename, "/missing-output-dir", "data", storage=storage)

    assert html_response.status_code == 200
    assert html_response.headers["content-disposition"] == f"attachment; filename={filename}"
    assert 'href="https://tw.stock.yahoo.com/quote/2308.TW"' in html_response.body.decode("utf-8")
    assert md_response.status_code == 200
    assert md_response.body == "# 台達電\n".encode("utf-8")
    assert md_response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert md_response.headers["content-type"].startswith("text/markdown")
    assert data_response.status_code == 200
    assert data_response.body == b'{"ticker":"2308.TW"}'
    assert data_response.headers["content-disposition"] == f"attachment; filename={data_filename}"
    assert data_response.headers["content-type"].startswith("application/json")


def test_download_html_report_replaces_static_notice_when_snapshot_integrity_is_invalid():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(
        filename,
        """
        <html><body>
        <section class="report-reading-notice report-reading-notice-passed">
            <span class="report-reading-notice-status">已通過已知檢查</span>
        </section>
        <p>downloaded report</p>
        </body></html>
        """.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_hash": "expected-but-stale",
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = download_report_file(filename, "/missing-output-dir", "html", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={filename}"
    assert "downloaded report" in body
    assert "report-reading-notice-blocked" in body
    assert "snapshot_hash mismatch" in body
    assert "report-reading-notice-passed" not in body


def test_download_markdown_report_replaces_static_notice_when_snapshot_integrity_is_invalid():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    storage.save_report(
        md_filename,
        """
## 報告使用範圍與判讀限制

- **品質 gate 狀態:** 已通過已知檢查
> 綠燈只代表已知自動檢查通過

## 其他章節

downloaded markdown
        """.encode("utf-8"),
        content_type="text/markdown",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_hash": "expected-but-stale",
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert "品質 gate 未通過" in body
    assert "snapshot_hash mismatch" in body
    assert "已通過已知檢查" not in body
    assert "## 其他章節" in body
    assert "downloaded markdown" in body


def test_download_markdown_report_replaces_static_notice_when_data_snapshot_is_malformed():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    storage.save_report(
        md_filename,
        """
## 報告使用範圍與判讀限制

- **品質 gate 狀態:** 已通過已知檢查
> 綠燈只代表已知自動檢查通過

## 其他章節

malformed snapshot markdown
        """.encode("utf-8"),
        content_type="text/markdown",
    )
    storage.save_report(data_snapshot_filename_for_report(filename), b"{", content_type="application/json")

    response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert "品質 gate 未通過" in body
    assert "資料快照無法解析" in body
    assert "已通過已知檢查" not in body
    assert "## 其他章節" in body
    assert "malformed snapshot markdown" in body


def test_download_markdown_report_replaces_static_notice_when_snapshot_records_invalid_integrity_without_hash():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    storage.save_report(
        md_filename,
        """
## 報告使用範圍與判讀限制

- **品質 gate 狀態:** 已通過已知檢查
> 綠燈只代表已知自動檢查通過

## 其他章節

recorded invalid snapshot markdown
        """.encode("utf-8"),
        content_type="text/markdown",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {
                    "status": "verified",
                    "valid": False,
                    "errors": ["snapshot verifier rejected stale source bundle"],
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert "品質 gate 未通過" in body
    assert "snapshot verifier rejected stale source bundle" in body
    assert "已通過已知檢查" not in body
    assert "## 其他章節" in body
    assert "recorded invalid snapshot markdown" in body


def test_download_markdown_report_derives_hash_mismatch_detail_from_recorded_invalid_integrity_hashes():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    storage.save_report(
        md_filename,
        """
## 報告使用範圍與判讀限制

- **品質 gate 狀態:** 已通過已知檢查
> 綠燈只代表已知自動檢查通過

## 其他章節

recorded hash mismatch markdown
        """.encode("utf-8"),
        content_type="text/markdown",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {
                    "status": "invalid",
                    "hash": "actual-hash",
                    "expected_hash": "expected-hash",
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert "品質 gate 未通過" in body
    assert "snapshot_hash mismatch" in body
    assert "已通過已知檢查" not in body
    assert "## 其他章節" in body
    assert "recorded hash mismatch markdown" in body


def test_download_markdown_report_prefers_hash_mismatch_over_recorded_generic_integrity_error():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    generic_error = "資料快照完整性未通過，不能直接引用報告結論。"
    storage.save_report(
        md_filename,
        """
## 報告使用範圍與判讀限制

- **品質 gate 狀態:** 已通過已知檢查
> 綠燈只代表已知自動檢查通過

## 其他章節

recorded generic hash mismatch markdown
        """.encode("utf-8"),
        content_type="text/markdown",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {
                    "status": "invalid",
                    "errors": [generic_error],
                    "hash": "actual-hash",
                    "expected_hash": "expected-hash",
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert "品質 gate 未通過" in body
    assert "snapshot_hash mismatch" in body
    assert generic_error not in body
    assert "已通過已知檢查" not in body
    assert "## 其他章節" in body
    assert "recorded generic hash mismatch markdown" in body


def test_download_markdown_report_removes_recorded_generic_integrity_error_when_specific_detail_exists():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    generic_error = "資料快照完整性未通過，不能直接引用報告結論。"
    specific_error = "provider audit source digest mismatch"
    storage.save_report(
        md_filename,
        """
## 報告使用範圍與判讀限制

- **品質 gate 狀態:** 已通過已知檢查
> 綠燈只代表已知自動檢查通過

## 其他章節

recorded mixed integrity errors markdown
        """.encode("utf-8"),
        content_type="text/markdown",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {
                    "status": "invalid",
                    "errors": [generic_error, specific_error],
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert "品質 gate 未通過" in body
    assert specific_error in body
    assert generic_error not in body
    assert "已通過已知檢查" not in body
    assert "## 其他章節" in body
    assert "recorded mixed integrity errors markdown" in body


def test_download_markdown_report_deduplicates_recorded_integrity_error_details():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    specific_error = "provider audit source digest mismatch"
    storage.save_report(
        md_filename,
        """
## 報告使用範圍與判讀限制

- **品質 gate 狀態:** 已通過已知檢查
> 綠燈只代表已知自動檢查通過

## 其他章節

recorded duplicate integrity errors markdown
        """.encode("utf-8"),
        content_type="text/markdown",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {
                    "status": "invalid",
                    "errors": [specific_error, specific_error],
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert "品質 gate 未通過" in body
    assert body.count(specific_error) == 1
    assert "已通過已知檢查" not in body
    assert "## 其他章節" in body
    assert "recorded duplicate integrity errors markdown" in body


def test_download_markdown_report_replaces_static_notice_when_nested_snapshot_integrity_is_invalid():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    storage.save_report(
        md_filename,
        """
## 報告使用範圍與判讀限制

- **品質 gate 狀態:** 已通過已知檢查
> 綠燈只代表已知自動檢查通過

## 其他章節

nested invalid snapshot markdown
        """.encode("utf-8"),
        content_type="text/markdown",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "data": {
                    "snapshot_integrity": {
                        "status": "invalid",
                        "errors": ["nested snapshot integrity rejected stale source bundle"],
                    },
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert "品質 gate 未通過" in body
    assert "nested snapshot integrity rejected stale source bundle" in body
    assert "已通過已知檢查" not in body
    assert "## 其他章節" in body
    assert "nested invalid snapshot markdown" in body


def test_download_markdown_report_uses_nested_invalid_integrity_even_when_top_level_is_verified():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    storage.save_report(
        md_filename,
        """
## 報告使用範圍與判讀限制

- **品質 gate 狀態:** 已通過已知檢查
> 綠燈只代表已知自動檢查通過

## 其他章節

conflicting snapshot markdown
        """.encode("utf-8"),
        content_type="text/markdown",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {"status": "verified", "valid": True},
                "data": {
                    "snapshot_integrity": {
                        "status": "invalid",
                        "errors": ["nested integrity must override top-level verified status"],
                    },
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert "品質 gate 未通過" in body
    assert "nested integrity must override top-level verified status" in body
    assert "已通過已知檢查" not in body
    assert "## 其他章節" in body
    assert "conflicting snapshot markdown" in body


def test_download_markdown_report_prefers_specific_nested_invalid_detail_over_generic_top_level_invalid():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    storage.save_report(
        md_filename,
        """
## 報告使用範圍與判讀限制

- **品質 gate 狀態:** 已通過已知檢查
> 綠燈只代表已知自動檢查通過

## 其他章節

specific nested detail markdown
        """.encode("utf-8"),
        content_type="text/markdown",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {"status": "invalid"},
                "data": {
                    "snapshot_integrity": {
                        "status": "invalid",
                        "errors": ["nested provider audit hash mismatch"],
                    },
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert "品質 gate 未通過" in body
    assert "nested provider audit hash mismatch" in body
    assert "已通過已知檢查" not in body
    assert "## 其他章節" in body
    assert "specific nested detail markdown" in body


def test_download_markdown_report_prefers_specific_nested_invalid_detail_over_generic_top_level_error_text():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    storage.save_report(
        md_filename,
        """
## 報告使用範圍與判讀限制

- **品質 gate 狀態:** 已通過已知檢查
> 綠燈只代表已知自動檢查通過

## 其他章節

generic top-level detail markdown
        """.encode("utf-8"),
        content_type="text/markdown",
    )
    storage.save_report(
        data_snapshot_filename_for_report(filename),
        json.dumps(
            {
                "ticker": "2308.TW",
                "snapshot_integrity": {
                    "status": "invalid",
                    "errors": ["資料快照完整性未通過，不能直接引用報告結論。"],
                },
                "data": {
                    "snapshot_integrity": {
                        "status": "invalid",
                        "errors": ["nested provider audit hash mismatch"],
                    },
                },
                "data_trust": {"status": "fresh"},
                "evidence_exit_gate": {"verdict": "approved"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert "品質 gate 未通過" in body
    assert "nested provider audit hash mismatch" in body
    assert "已通過已知檢查" not in body
    assert "## 其他章節" in body
    assert "generic top-level detail markdown" in body


def test_download_markdown_report_replaces_static_notice_when_data_snapshot_is_missing():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    storage.save_report(
        md_filename,
        """
## 報告使用範圍與判讀限制

- **品質 gate 狀態:** 已通過已知檢查
> 綠燈只代表已知自動檢查通過

## 其他章節

missing snapshot markdown
        """.encode("utf-8"),
        content_type="text/markdown",
    )

    response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert "品質 gate 有警示" in body
    assert "資料快照不存在" in body
    assert "已通過已知檢查" not in body
    assert "## 其他章節" in body
    assert "missing snapshot markdown" in body


def test_refresh_data_snapshot_reads_and_updates_partitioned_storage(tmp_path, monkeypatch):
    import report_refresh_service
    from report_persistence import report_bundle_keys_for_filename

    monkeypatch.setattr(report_refresh_service, "upsert_report_metadata", lambda *args, **kwargs: {"filename": args[0]})
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    keys = report_bundle_keys_for_filename(filename)
    storage.save_report(keys.html_key, b"<html></html>", content_type="text/html")
    storage.save_report(
        keys.data_key,
        json.dumps(
            {
                "snapshot_schema_version": 3,
                "ticker": "2308.TW",
                "company_name": "台達電",
                "pipeline": "v2",
                "generated_at": "2026-06-26T12:00:00+00:00",
                "conclusion_generated_at": "2026-06-26T12:00:00+00:00",
                "data_schema_version": 4,
                "source_freshness": {
                    "market_data": {"stale": True, "fetched_at": "2026-06-20T00:00:00+00:00"},
                    "financial_statements": {"stale": False, "fetched_at": "2026-06-20T00:00:00+00:00"},
                },
                "source_audit": [],
                "data_trust": {"status": "stale", "critical_failures": [], "stale_sources": ["market_data"], "notes": []},
                "data": {"ticker": "2308.TW", "company_name": "台達電", "current_price": 100.0},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    class FakeRefreshService:
        async def fetch_async(self, request):
            return SimpleNamespace(
                data={
                    "data_schema_version": 4,
                    "ticker": request.ticker,
                    "company_name": "台達電",
                    "current_price": 110.0,
                    "source_freshness": {
                        "market_data": {"stale": False, "fetched_at": "2026-06-27T00:00:00+00:00"},
                        "financial_statements": {"stale": False, "fetched_at": "2026-06-27T00:00:00+00:00"},
                    },
                    "source_audit": [
                        {"source": "market_data", "provider": "fake", "status": "success", "record_count": 1},
                        {"source": "financial_statements", "provider": "fake", "status": "success", "record_count": 1},
                    ],
                    "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
                }
            )

    body = asyncio.run(
        report_refresh_service.refresh_report_data_snapshot(
            filename,
            output_dir=str(tmp_path),
            refresh_service=FakeRefreshService(),
            storage=storage,
        )
    )

    saved = json.loads(storage.get_report(keys.data_key).content.decode("utf-8"))
    assert body["success"] is True
    assert saved["data_trust"]["status"] == "fresh"
    assert saved["data"]["current_price"] == 110.0
    assert storage.exists(keys.data_key) is True


def test_delete_report_files_deletes_storage_cache_and_repository(tmp_path):
    storage = InMemoryStorage()
    repository = RecordingRepository()
    lock = RecordingLock()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    data_filename = data_snapshot_filename_for_report(filename)
    storage.save_report(filename, b"<html></html>", content_type="text/html")
    storage.save_report(md_filename, b"# report\n", content_type="text/markdown")
    storage.save_report(data_filename, b"{}", content_type="application/json")
    report_cache = {"2308.TW": filename, "2330.TW": "other.html"}

    result = delete_report_files(
        filename,
        str(tmp_path),
        report_cache,
        repository=repository,
        report_cache_lock=lock,
        storage=storage,
    )

    assert result == {"success": True, "deleted": [filename, md_filename, data_filename]}
    assert storage.exists(filename) is False
    assert storage.exists(md_filename) is False
    assert storage.exists(data_filename) is False
    assert report_cache == {"2330.TW": "other.html"}
    assert lock.entered == 1
    assert repository.deleted == [(filename, str(tmp_path))]


def test_delete_report_files_does_not_delete_content_when_metadata_delete_fails(tmp_path):
    storage = InMemoryStorage()
    repository = FailingDeleteRepository(metadata_exists=True)
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(filename, b"<html></html>", content_type="text/html")
    report_cache = {"2308.TW": filename}

    result = delete_report_files(
        filename,
        str(tmp_path),
        report_cache,
        repository=repository,
        storage=storage,
    )

    assert result["success"] is False
    assert "metadata delete failed" in result["error"]
    assert storage.exists(filename) is True
    assert report_cache == {"2308.TW": filename}


def test_delete_report_files_can_remove_stale_metadata_when_content_is_already_missing(tmp_path):
    storage = InMemoryStorage()
    repository = RecordingRepository(metadata_exists=True)
    filename = "2308_TW_v2_report_20260626_120000.html"
    report_cache = {"2308.TW": filename}

    result = delete_report_files(
        filename,
        str(tmp_path),
        report_cache,
        repository=repository,
        storage=storage,
    )

    assert result == {"success": True, "deleted": []}
    assert repository.deleted == [(filename, str(tmp_path))]
    assert report_cache == {}


def test_report_routes_use_injected_report_storage_for_read_and_delete(tmp_path):
    storage = InMemoryStorage()
    report_cache = {"2308.TW": "2308_TW_v2_report_20260626_120000.html"}
    filename = report_cache["2308.TW"]
    storage.save_report(filename, b"<html>from storage</html>", content_type="text/html")
    storage.save_report(filename.replace(".html", ".md"), b"# report\n", content_type="text/markdown")
    storage.save_report(data_snapshot_filename_for_report(filename), b"{}", content_type="application/json")
    app = FastAPI()
    app.include_router(
        create_reports_router(
            ReportRouteDeps(
                get_output_dir=lambda: str(tmp_path),
                get_report_storage=lambda: storage,
                get_refresh_service=lambda: None,
                get_pipeline_runner=lambda: None,
                get_report_renderer=lambda: None,
                get_task_queue=lambda: None,
                run_report_rerun_job=lambda *_: "",
                create_job=lambda *_: "job",
                get_job=lambda *_: {},
                get_events_since=lambda *_: [],
                update_job=lambda *_args, **_kwargs: None,
                append_event=lambda *_args, **_kwargs: None,
                request_job_cancel=lambda *_: False,
                print_streamed_event=lambda *_: None,
                require_mutation_authorized=lambda _request: None,
            )
        )
    )
    client = TestClient(app)

    view_response = client.get(f"/api/report/{filename}")
    delete_response = client.delete(f"/api/reports/{filename}")

    assert view_response.status_code == 200
    assert "from storage" in view_response.text
    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True
    assert storage.exists(filename) is False
    assert report_cache == {"2308.TW": filename}


def test_cleanup_expired_reports_removes_partitioned_report_bundle(tmp_path):
    from report_persistence import persist_report_bundle, report_bundle_keys_for_filename
    from storage.report_storage import LocalFileStorage

    filename = "2308_TW_v2_report_20260626_120000.html"
    storage = LocalFileStorage(tmp_path)
    persist_report_bundle(
        filename=filename,
        html_content="<html>old</html>",
        markdown_content="# old",
        data_snapshot={"ticker": "2308.TW", "data_trust": {"status": "fresh"}},
        storage=storage,
        output_dir=str(tmp_path),
    )
    keys = report_bundle_keys_for_filename(filename)
    old_mtime = time.time() - 3 * 24 * 60 * 60
    for key in (keys.html_key, keys.md_key, keys.data_key):
        os.utime(tmp_path / key, (old_mtime, old_mtime))

    deleted = cleanup_expired_reports(
        str(tmp_path),
        {"2308.TW": filename},
        retention_days=1,
    )

    assert keys.html_key in deleted
    assert storage.get_report(keys.html_key) is None
    assert storage.get_report(keys.md_key) is None
    assert storage.get_report(keys.data_key) is None


def test_cleanup_orphan_markdown_reports_removes_partitioned_snapshots(tmp_path):
    from report_persistence import report_bundle_keys_for_filename
    from storage.report_storage import LocalFileStorage

    filename = "2308_TW_v2_report_20260626_120000.html"
    storage = LocalFileStorage(tmp_path)
    keys = report_bundle_keys_for_filename(filename)
    storage.save_report(keys.md_key, b"# orphan", content_type="text/markdown")
    storage.save_report(keys.data_key, b'{"ticker":"2308.TW"}', content_type="application/json")

    deleted = cleanup_orphan_markdown_reports(str(tmp_path))

    assert keys.md_key in deleted
    assert keys.data_key in deleted
    assert storage.get_report(keys.md_key) is None
    assert storage.get_report(keys.data_key) is None


def test_report_rerun_route_queues_partitioned_storage_report(tmp_path):
    from report_persistence import report_bundle_keys_for_filename

    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    keys = report_bundle_keys_for_filename(filename)
    storage.save_report(keys.html_key, b"<html>from partitioned storage</html>", content_type="text/html")
    storage.save_report(keys.md_key, b"# report\n", content_type="text/markdown")
    storage.save_report(
        keys.data_key,
        json.dumps({"ticker": "2308.TW", "pipeline": "v2", "data": {"ticker": "2308.TW"}}).encode("utf-8"),
        content_type="application/json",
    )

    class FakeTaskQueue:
        def __init__(self):
            self.calls = []

        def enqueue(self, *args):
            self.calls.append(args)

    queue = FakeTaskQueue()
    app = FastAPI()
    app.include_router(
        create_reports_router(
            ReportRouteDeps(
                get_output_dir=lambda: str(tmp_path),
                get_report_storage=lambda: storage,
                get_refresh_service=lambda: None,
                get_pipeline_runner=lambda: None,
                get_report_renderer=lambda: None,
                get_task_queue=lambda: queue,
                run_report_rerun_job=lambda *_: "",
                create_job=lambda *_: "rerun-job",
                get_job=lambda *_: {},
                get_events_since=lambda *_: [],
                update_job=lambda *_args, **_kwargs: None,
                append_event=lambda *_args, **_kwargs: None,
                request_job_cancel=lambda *_: False,
                print_streamed_event=lambda *_: None,
                require_mutation_authorized=lambda _request: None,
            )
        )
    )
    client = TestClient(app)

    response = client.post(f"/api/report/{filename}/rerun", params={"scope": "mode_b"})

    assert response.status_code == 200
    assert response.json()["job_id"] == "rerun-job"
    assert queue.calls[0][2:] == ("rerun-job", filename, "mode_b")


def test_compare_reports_reads_partitioned_local_storage(tmp_path):
    from report_compare_service import compare_reports
    from report_persistence import persist_report_bundle
    from storage.report_storage import LocalFileStorage

    storage = LocalFileStorage(tmp_path)
    left = "2308_TW_v2_report_20260626_120000.html"
    right = "2308_TW_v2_report_20260627_120000.html"

    for filename, price, generated_at in (
        (left, 100, "2026-06-26T12:00:00+00:00"),
        (right, 110, "2026-06-27T12:00:00+00:00"),
    ):
        persist_report_bundle(
            filename=filename,
            html_content="<html><body>台達電</body></html>",
            markdown_content=f"""# 2308.TW 台達電

## 一頁式摘要
追蹤比較用報告。

## 🎯 最終投資建議
- **綜合建議:** 持有
- **股價:** NT${price}
""",
            data_snapshot={
                "ticker": "2308.TW",
                "pipeline": "v2",
                "generated_at": generated_at,
                "data_trust": {"status": "fresh"},
                "data": {"ticker": "2308.TW", "current_price": price},
            },
            storage=storage,
            output_dir=str(tmp_path),
        )

    result = compare_reports(left, right, output_dir=str(tmp_path))

    assert result["success"] is True
    assert result["compatibility"]["same_ticker"] is True
    assert result["left"]["filename"] == left
    assert result["right"]["generated_at"] == "2026-06-27T12:00:00+00:00"


def test_rerun_report_analysis_passes_storage_to_rerun_rendering(tmp_path, monkeypatch):
    import report_rerun_service

    filename = "2308_TW_v2_report_20260626_120000.html"
    source_snapshot = {
        "snapshot_schema_version": 3,
        "ticker": "2308.TW",
        "company_name": "台達電",
        "pipeline": "v2",
        "generated_at": "2026-06-26T12:00:00+00:00",
        "data_schema_version": 4,
        "source_freshness": {},
        "source_audit": [],
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        "data": {"ticker": "2308.TW", "company_name": "台達電"},
    }
    html_path = tmp_path / filename
    html_path.write_text("<html></html>", encoding="utf-8")
    (tmp_path / data_snapshot_filename_for_report(filename)).write_text(
        json.dumps(source_snapshot),
        encoding="utf-8",
    )

    class FakePipelineRunner:
        async def run_async(self, request):
            return SimpleNamespace(context={"ticker": "2308.TW", "data": request.data})

    class FakeReportRenderer:
        async def render_async(self, request):
            return ReportBundle(
                html="<html>rerun</html>",
                markdown="# rerun",
                data_snapshot={
                    "ticker": "2308.TW",
                    "pipeline": request.pipeline_id,
                    "data_trust": {"status": "fresh"},
                    "data": request.context["data"],
                },
            )

    monkeypatch.setattr(report_rerun_service, "time", SimpleNamespace(time=lambda: 1.0))
    storage = InMemoryStorage()

    result = asyncio_run(
        report_rerun_service.rerun_report_analysis(
            filename,
            scope="full_report",
            output_dir=str(tmp_path),
            pipeline_runner=FakePipelineRunner(),
            report_renderer=FakeReportRenderer(),
            storage=storage,
        )
    )

    from report_persistence import report_bundle_keys_for_filename

    keys = report_bundle_keys_for_filename(result["filename"])
    assert storage.get_report(keys.html_key) is not None
    assert storage.get_report(keys.md_key) is not None
    assert storage.get_report(keys.data_key) is not None


def test_rerun_report_analysis_reads_partitioned_source_storage(tmp_path, monkeypatch):
    import report_rerun_service
    from report_persistence import report_bundle_keys_for_filename

    filename = "2308_TW_v2_report_20260626_120000.html"
    source_snapshot = {
        "snapshot_schema_version": 3,
        "ticker": "2308.TW",
        "company_name": "台達電",
        "pipeline": "v2",
        "generated_at": "2026-06-26T12:00:00+00:00",
        "data_schema_version": 4,
        "source_freshness": {},
        "source_audit": [],
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        "data": {"ticker": "2308.TW", "company_name": "台達電"},
    }
    storage = InMemoryStorage()
    keys = report_bundle_keys_for_filename(filename)
    storage.save_report(keys.html_key, b"<html></html>", content_type="text/html")
    storage.save_report(keys.data_key, json.dumps(source_snapshot).encode("utf-8"), content_type="application/json")

    class FakePipelineRunner:
        async def run_async(self, request):
            return SimpleNamespace(context={"ticker": "2308.TW", "data": request.data})

    class FakeReportRenderer:
        async def render_async(self, request):
            return ReportBundle(
                html="<html>rerun</html>",
                markdown="# rerun",
                data_snapshot={
                    "ticker": "2308.TW",
                    "pipeline": request.pipeline_id,
                    "data_trust": {"status": "fresh"},
                    "data": request.context["data"],
                },
            )

    monkeypatch.setattr(report_rerun_service, "time", SimpleNamespace(time=lambda: 1.0))

    result = asyncio_run(
        report_rerun_service.rerun_report_analysis(
            filename,
            scope="full_report",
            output_dir=str(tmp_path),
            pipeline_runner=FakePipelineRunner(),
            report_renderer=FakeReportRenderer(),
            storage=storage,
        )
    )

    generated_keys = report_bundle_keys_for_filename(result["filename"])
    assert storage.get_report(generated_keys.html_key) is not None
    assert result["source_filename"] == filename


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
