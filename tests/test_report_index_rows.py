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
