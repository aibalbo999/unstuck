import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_report_artifact_locator_finds_nested_report_bundle():
    from report_artifacts import ReportArtifactLocator
    from report_paths import report_markdown_filename_for_report, report_storage_key_for_filename
    from data_trust import data_snapshot_filename_for_report
    from storage.report_storage import InMemoryStorage

    filename = "2308_TW_v4_report_20260703_220941.html"
    storage = InMemoryStorage()
    html_key = report_storage_key_for_filename(filename)
    md_key = html_key.rsplit("/", 1)[0] + "/" + report_markdown_filename_for_report(filename)
    data_key = html_key.rsplit("/", 1)[0] + "/" + data_snapshot_filename_for_report(filename)
    snapshot = {"ticker": "2308.TW", "data": {"current_price": 1890.0}}
    storage.save_report(html_key, b"<html></html>", content_type="text/html")
    storage.save_report(md_key, b"# report", content_type="text/markdown")
    storage.save_report(data_key, json.dumps(snapshot).encode("utf-8"), content_type="application/json")

    bundle = ReportArtifactLocator(storage).require_bundle(filename)

    assert bundle.filename == filename
    assert bundle.html_key == html_key
    assert bundle.markdown_key == md_key
    assert bundle.data_key == data_key
    assert bundle.read_data_snapshot() == snapshot


def test_report_artifact_locator_falls_back_to_legacy_flat_bundle():
    from report_artifacts import ReportArtifactLocator
    from data_trust import data_snapshot_filename_for_report
    from storage.report_storage import InMemoryStorage

    filename = "2308_TW_v4_report_20260703_220941.html"
    data_filename = data_snapshot_filename_for_report(filename)
    storage = InMemoryStorage()
    storage.save_report(filename, b"<html></html>", content_type="text/html")
    storage.save_report(data_filename, b'{"ticker":"2308.TW"}', content_type="application/json")

    bundle = ReportArtifactLocator(storage).require_bundle(filename, require_markdown=False)

    assert bundle.html_key == filename
    assert bundle.markdown_key is None
    assert bundle.data_key == data_filename
    assert bundle.read_data_snapshot()["ticker"] == "2308.TW"
