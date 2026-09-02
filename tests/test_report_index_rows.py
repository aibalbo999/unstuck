import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_report_index_row_snapshot_integrity_fail_closes_legacy_false_token(monkeypatch):
    import report_index_rows

    monkeypatch.setattr(
        report_index_rows,
        "verify_data_snapshot_integrity",
        lambda _snapshot: {
            "valid": "false",
            "hash": "actual-hash",
            "expected_hash": "expected-hash",
            "errors": ["snapshot_hash mismatch"],
        },
    )

    result = report_index_rows._snapshot_integrity({}, snapshot={"ticker": "2308.TW"})

    assert result == {
        "status": "invalid",
        "valid": False,
        "hash": "actual-hash",
        "expected_hash": "expected-hash",
        "errors": ["snapshot_hash mismatch"],
    }


def test_report_index_row_uses_filename_pipeline_when_index_pipeline_is_placeholder(tmp_path):
    import json

    import report_index_rows

    snapshot_path = tmp_path / "sample.data.json"
    snapshot_path.write_text(
        json.dumps({"pipeline": "N/A", "data": {"ticker": "2330.TW"}}),
        encoding="utf-8",
    )
    row = {
        "filename": "2330_TW_v4_report_20260620_090000.html",
        "ticker": "2330.TW",
        "company_name": "台積電",
        "report_date": "2026-06-20 09:00",
        "timestamp": 1781926800,
        "pipeline_id": "N/A",
        "recommendation_json": "{}",
        "data_trust_json": "{}",
        "data_snapshot_filename": snapshot_path.name,
        "output_dir": str(tmp_path),
        "analysis_text_stale": 0,
        "analysis_text_stale_message": "",
    }

    report = report_index_rows.row_to_report(row)

    assert report["pipeline_id"] == "v4"
    assert report["pipeline_label"] == "短線波段派"
    assert report["preview"]["kind"] == "swing_trade"
