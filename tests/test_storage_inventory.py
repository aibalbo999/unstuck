import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from storage_inventory import build_storage_summary  # noqa: E402


def test_storage_summary_counts_reports_databases_and_calendars(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "AAPL_v1_report_20260607_000000.html").write_text("<html></html>", encoding="utf-8")
    (output_dir / "AAPL_v1_report_20260607_000000.md").write_text("# report", encoding="utf-8")
    (output_dir / "AAPL_v1_report_20260607_000000.data.json").write_text("{}", encoding="utf-8")

    cache_db = tmp_path / "cache.sqlite3"
    with sqlite3.connect(cache_db) as conn:
        conn.execute("CREATE TABLE cache_entries (cache_key TEXT)")
        conn.execute("INSERT INTO cache_entries VALUES ('financial_data:AAPL')")
        conn.execute("CREATE TABLE reports (filename TEXT)")
        conn.execute("INSERT INTO reports VALUES ('AAPL_v1_report_20260607_000000.html')")

    task_db = tmp_path / "tasks.sqlite3"
    with sqlite3.connect(task_db) as conn:
        conn.execute("CREATE TABLE analysis_jobs (job_id TEXT)")
        conn.execute("CREATE TABLE provider_sla_events (id INTEGER)")
        conn.execute("INSERT INTO analysis_jobs VALUES ('job-1')")
        conn.execute("INSERT INTO provider_sla_events VALUES (1)")

    calendars = tmp_path / "market_calendars"
    calendars.mkdir()
    (calendars / "us_2026.json").write_text("{}", encoding="utf-8")

    summary = build_storage_summary(
        output_dir=str(output_dir),
        cache_dir=str(tmp_path),
        cache_db_path=str(cache_db),
        task_db_path=str(task_db),
        market_calendar_dir=str(calendars),
    )

    assert summary["reports"]["html"] == 1
    assert summary["reports"]["markdown"] == 1
    assert summary["reports"]["data_snapshots"] == 1
    assert summary["cache_db"]["tables"]["cache_entries"] == 1
    assert summary["cache_db"]["tables"]["reports"] == 1
    assert summary["task_db"]["tables"]["analysis_jobs"] == 1
    assert summary["task_db"]["tables"]["provider_sla_events"] == 1
    assert summary["market_calendars"]["json_files"] == 1
