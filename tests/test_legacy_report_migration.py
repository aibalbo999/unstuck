import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_trust import DATA_SNAPSHOT_SCHEMA_VERSION, data_snapshot_filename_for_report  # noqa: E402
from storage.legacy_reports import migrate_legacy_reports  # noqa: E402


def write_legacy_report(output_dir: Path, filename: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / filename).write_text(
        '<div class="sidebar-name">Legacy Corp</div>',
        encoding="utf-8",
    )
    (output_dir / filename.replace(".html", ".md")).write_text(
        """# Legacy Report

## 🎯 最終投資建議
- **綜合建議:** 持有
- **3個月目標:** NT$100
- **6個月目標:** NT$110
- **12個月目標:** NT$120
- **信心指數:** 6/10
""",
        encoding="utf-8",
    )


def test_migrate_legacy_reports_creates_placeholder_snapshot(tmp_path, monkeypatch):
    import report_index

    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "2330_v2_report_20260606_010000.html"
    write_legacy_report(tmp_path, filename)

    dry_run = migrate_legacy_reports(str(tmp_path), dry_run=True)
    data_filename = data_snapshot_filename_for_report(filename)
    assert dry_run["created"] == 1
    assert not (tmp_path / data_filename).exists()

    result = migrate_legacy_reports(str(tmp_path), dry_run=False)
    assert result["created"] == 1
    assert result["indexed"] == 1

    snapshot = json.loads((tmp_path / data_filename).read_text(encoding="utf-8"))
    assert snapshot["snapshot_schema_version"] == DATA_SNAPSHOT_SCHEMA_VERSION
    assert snapshot["snapshot_migrated_from_legacy"] is True
    assert snapshot["data_trust"]["status"] == "unknown"
    assert snapshot["source_audit"] == []

    second = migrate_legacy_reports(str(tmp_path), dry_run=False)
    assert second["created"] == 0
    assert second["skipped"] == 1


def test_migrate_legacy_reports_does_not_overwrite_existing_snapshot(tmp_path):
    filename = "AAPL_v1_report_20260606_020000.html"
    write_legacy_report(tmp_path, filename)
    data_path = tmp_path / data_snapshot_filename_for_report(filename)
    data_path.write_text(
        json.dumps({"snapshot_schema_version": 1, "ticker": "AAPL", "sentinel": True}),
        encoding="utf-8",
    )

    migrate_legacy_reports(str(tmp_path), dry_run=False)

    assert json.loads(data_path.read_text(encoding="utf-8"))["sentinel"] is True
