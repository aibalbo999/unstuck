import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_data_snapshot_keeps_refresh_quality_provenance_as_optional_evidence():
    from data_trust_snapshot import build_data_snapshot

    provenance = {
        "schema_version": 1,
        "source": "previous_snapshot_before_refresh",
        "recorded_fields": {"report_conformance": "warning"},
        "missing_fields": ["evidence_exit_gate", "content_credibility"],
    }

    snapshot = build_data_snapshot(
        {
            "ticker": "2308.TW",
            "pipeline_id": "v2",
            "data": {"ticker": "2308.TW", "data_trust": {"status": "fresh", "score": 90}},
            "quality_metadata_refresh_provenance": provenance,
        },
        pipeline_id="v2",
        generated_at="2026-08-20T00:00:00+00:00",
    )

    assert snapshot["quality_metadata_refresh_provenance"] == provenance


def test_index_row_quality_evidence_classifies_pre_refresh_gap(monkeypatch):
    import report_index_rows

    monkeypatch.setattr(report_index_rows, "storage_for_existing_output_dir", lambda *_args: object())
    monkeypatch.setattr(report_index_rows, "read_artifact_quality_summary", lambda *_args: {})

    evidence = report_index_rows._quality_evidence(
        {"output_dir": "/tmp/output"},
        {
            "snapshot_integrity": {"status": "verified"},
            "report_conformance": {},
            "evidence_exit_gate": {},
            "content_credibility": {"status": "passed"},
            "refreshed_from_report": "1623_v1.html",
            "quality_metadata_refresh_provenance": {
                "schema_version": 1,
                "source": "previous_snapshot_before_refresh",
                "recorded_fields": {"content_credibility": "passed"},
                "missing_fields": ["report_conformance", "evidence_exit_gate"],
            },
            "snapshot_refreshed_at": "2026-08-20T00:00:00+00:00",
        },
    )

    assert evidence["quality_metadata_provenance"] == "before_refresh"
