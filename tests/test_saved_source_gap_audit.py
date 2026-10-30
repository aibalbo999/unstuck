"""Audit reports are descriptive and must not repair or write their inputs."""
from datetime import date
import importlib.util
from pathlib import Path
import sqlite3

import pytest


spec = importlib.util.spec_from_file_location("saved_source_audit", Path(__file__).resolve().parents[1] / "scripts/audit_saved_source_gaps.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_drift_and_rebound_are_distinct_from_expiry():
    from test_saved_trade_source_identity import record
    prefix = "short_term_market_context.institutional_evidence.records"
    frozen = {"short_term_market_context": {"institutional_evidence": {"records": [record("2026-10-14", 50), record()]}}}
    current = {"short_term_market_context": {"institutional_evidence": {"records": [record()]}}}
    value = audit.classify_reference(prefix + "[1]", current, frozen, True, date(2026, 10, 27))
    assert value["reason_codes"] == ["catalog_index_drift_original_record_still_present"]
    assert value["same_original_record_current_paths"] == [prefix + "[0]"]
    current["short_term_market_context"]["institutional_evidence"]["records"].append(record("2026-10-21", -99))
    assert audit.classify_reference(prefix + "[1]", current, frozen, True, date(2026, 10, 27))["reason_codes"] == ["same_index_rebound_to_different_record"]


def test_audit_never_substitutes_current_record_for_missing_original():
    from test_saved_trade_source_identity import record
    ref = "short_term_market_context.institutional_evidence.records[0]"
    current = {"short_term_market_context": {"institutional_evidence": {"records": [record()]}}}
    detail = audit.classify_reference(ref, {}, {}, False, date(2026, 10, 27))
    assert detail["reason_codes"] == ["original_catalog_unavailable_or_unbound"]
    assert detail["original_usable"] is False
    assert detail["original_value"] is None


def test_latest_selection_is_per_ticker_pipeline_and_does_not_modify_index(tmp_path):
    database = tmp_path / "index.sqlite3"
    output = tmp_path / "artifacts"
    with sqlite3.connect(database) as con:
        con.execute("CREATE TABLE reports(output_dir,filename,ticker,pipeline_id,report_date,timestamp)")
        con.executemany("INSERT INTO reports VALUES(?,?,?,?,?,?)", [
            (str(output), "2356_TW_v4_report_20261020_100000.html", "2356.TW", "v4", "2026-10-20", 1),
            (str(output), "2356_TW_v4_report_20261027_100000.html", "2356.TW", "v4", "2026-10-27", 2),
            (str(output), "2356_TW_v1_report_20261020_100000.html", "2356.TW", "v1", "2026-10-20", 1)])
    before = database.read_bytes()
    rows = audit.latest_rows(database, output)
    assert len(rows) == 2
    assert {row["pipeline_id"] for row in rows} == {"v1", "v4"}
    assert next(row for row in rows if row["pipeline_id"] == "v4")["report_date"] == "2026-10-27"
    assert database.read_bytes() == before


def test_artifact_adapter_is_read_only_and_rejects_escape(tmp_path):
    root = tmp_path / "reports"
    root.mkdir()
    (root / "one.txt").write_text("evidence")
    storage = audit.ReadOnlyArtifacts(root)
    assert storage.get_report("one.txt").content == b"evidence"
    assert not hasattr(storage, "save_report")
    with pytest.raises(ValueError):
        storage.get_report("../outside")
