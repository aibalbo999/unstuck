from pathlib import Path
import sys

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _invalid_nested_snapshot(tmp_path: Path, filename: str) -> Path:
    from report_paths import report_storage_candidates_for_filename

    path = tmp_path / report_storage_candidates_for_filename(filename, kind="data")[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe not utf-8")
    return path


def test_report_metadata_treats_non_utf8_snapshot_as_unavailable(tmp_path):
    from report_index_metadata import build_report_metadata
    from report_paths import report_storage_key_for_filename

    filename = "2308_TW_v2_report_20260626_120000.html"
    html_path = tmp_path / report_storage_key_for_filename(filename)
    html_path.parent.mkdir(parents=True)
    html_path.write_text("<html></html>", encoding="utf-8")
    _invalid_nested_snapshot(tmp_path, filename)

    metadata = build_report_metadata(
        filename,
        output_dir=str(tmp_path),
        html_content="<html></html>",
        markdown_content="",
    )

    assert metadata["ticker"] == "2308.TW"
    assert metadata["data_trust_status"] == "unknown"
    assert metadata["decision_freshness"]["status"] == "unknown"


@pytest.mark.parametrize(
    ("module_name", "function_name"),
    [
        ("report_index_parsing", "_snapshot_generated_at"),
        ("report_index_metadata", "read_snapshot_report_flags"),
        ("report_index_metadata", "read_snapshot_ticker"),
        ("report_preview", "_read_snapshot"),
        ("report_compare_service", "_read_json"),
    ],
)
def test_report_readers_fail_closed_on_non_utf8_json(tmp_path, module_name, function_name):
    import importlib

    filename = "2308_TW_v2_report_20260626_120000.html"
    path = _invalid_nested_snapshot(tmp_path, filename)
    reader = getattr(importlib.import_module(module_name), function_name)

    if module_name == "report_index_metadata" and function_name == "read_snapshot_report_flags":
        result = reader(str(path))
        assert result["data_snapshot_hash"] == ""
    elif module_name == "report_index_metadata" and function_name == "read_snapshot_ticker":
        result = reader(str(path), "2308.TW")
        assert result == "2308.TW"
    else:
        result = reader(str(path))
        assert result in ({}, "")


def test_report_metadata_readers_fail_closed_on_non_object_json(tmp_path):
    from report_index_metadata import read_snapshot_report_flags, read_snapshot_ticker

    path = tmp_path / "snapshot.data.json"
    path.write_text("[]", encoding="utf-8")

    assert read_snapshot_report_flags(str(path)) == {
        "analysis_text_stale": False,
        "analysis_text_stale_message": "",
        "data_snapshot_hash": "",
    }
    assert read_snapshot_ticker(str(path), "2308.TW") == "2308.TW"


def test_rerun_snapshot_reports_non_utf8_storage_as_http_error():
    from report_paths import report_storage_candidates_for_filename
    from report_rerun_context import read_report_snapshot
    from storage.report_storage import InMemoryStorage

    filename = "2308_TW_v2_report_20260626_120000.html"
    storage = InMemoryStorage()
    storage.save_report(
        report_storage_candidates_for_filename(filename, kind="data")[0],
        b"\xff\xfe not utf-8",
        content_type="application/json",
    )

    with pytest.raises(HTTPException) as error:
        read_report_snapshot(filename, "/missing-output-dir", storage=storage)

    assert error.value.status_code == 400
    assert "資料快照無法讀取" in str(error.value.detail)


def test_rerun_snapshot_reports_non_object_json_as_http_error():
    from report_paths import report_storage_candidates_for_filename
    from report_rerun_context import read_report_snapshot
    from storage.report_storage import InMemoryStorage

    filename = "2308_TW_v2_report_20260626_120000.html"
    storage = InMemoryStorage()
    storage.save_report(
        report_storage_candidates_for_filename(filename, kind="data")[0],
        b"[]",
        content_type="application/json",
    )

    with pytest.raises(HTTPException) as error:
        read_report_snapshot(filename, "/missing-output-dir", storage=storage)

    assert error.value.status_code == 400
    assert "資料快照" in str(error.value.detail)


def test_report_download_returns_http_error_for_non_utf8_markdown():
    from report_history_service import download_report_file
    from report_paths import report_storage_candidates_for_filename
    from storage.report_storage import InMemoryStorage

    filename = "2308_TW_v2_report_20260626_120000.html"
    storage = InMemoryStorage()
    storage.save_report(
        report_storage_candidates_for_filename(filename, kind="md")[0],
        b"\xff\xfe not utf-8",
        content_type="text/markdown",
    )

    response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)

    assert response.status_code == 400
    assert "Markdown" in response.body.decode("utf-8")


def test_quality_audit_does_not_treat_non_utf8_markdown_as_missing_markers():
    from types import SimpleNamespace

    from report_quality_evidence import read_artifact_quality_summary

    def load_item(_storage, _filename, *, kind):
        assert kind == "md"
        return SimpleNamespace(content=b"\xff\xfe not utf-8")

    assert read_artifact_quality_summary(object(), "report.html", load_item=load_item) == {
        "status": "unavailable",
        "source": "markdown",
        "fields": [],
    }


def test_quality_audit_does_not_parse_replacement_text_as_rerun_context():
    from types import SimpleNamespace

    from report_quality_audit_rows import read_artifact_rerun_context_status

    def load_item(_storage, _filename, *, kind):
        assert kind == "md"
        return SimpleNamespace(
            content=(
                b"## 1. Agent (Agent 1)\nvalid\n"
                b"## 2. Agent (Agent 2)\nvalid\n"
                b"## 3. Agent (Agent 3)\nvalid\n"
                b"## 4. Agent (Agent 4)\nvalid\n"
                b"## 5. Agent (Agent 5)\nvalid\n"
                b"## 6. Agent (Agent 6)\n\xff\xfe not utf-8"
            )
        )

    assert read_artifact_rerun_context_status(
        object(),
        "report.html",
        "v1",
        load_item=load_item,
    ) == "unavailable"


def test_quality_audit_artifact_context_uses_filename_pipeline_when_pipeline_is_placeholder():
    from types import SimpleNamespace

    from report_quality_audit_rows import read_artifact_rerun_context_status

    def load_item(_storage, _filename, *, kind):
        assert kind == "md"
        sections = b"\n".join(
            f"## {index}. Agent {agent} (Agent {agent})\nvalid".encode("utf-8")
            for index, agent in enumerate((11, 12, 13, 14, 15), start=1)
        )
        return SimpleNamespace(content=sections)

    assert read_artifact_rerun_context_status(
        object(),
        "2449_v2_report_20260620_090000.html",
        "N/A",
        load_item=load_item,
    ) == "present"
