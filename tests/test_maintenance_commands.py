import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import provider_sla  # noqa: E402
import provider_sla_maintenance  # noqa: E402
import report_index_maintenance  # noqa: E402
import job_store_maintenance  # noqa: E402
from data_trust_snapshot import build_data_snapshot  # noqa: E402
from market_calendar_store import update_market_calendars  # noqa: E402
from snapshot_maintenance import verify_snapshots  # noqa: E402
from storage_inventory import build_storage_summary  # noqa: E402


def test_update_market_calendars_writes_seed_files(tmp_path):
    result = update_market_calendars(years=[2026], markets=["us", "tw"], calendar_dir=str(tmp_path))

    assert result["updated"] == 2
    us_calendar = json.loads((tmp_path / "us_2026.json").read_text(encoding="utf-8"))
    tw_calendar = json.loads((tmp_path / "tw_2026.json").read_text(encoding="utf-8"))
    assert "2026-07-03" in us_calendar["holidays"]
    assert "2026-06-19" in tw_calendar["holidays"]


def test_verify_snapshots_backfills_missing_hash(tmp_path):
    snapshot = build_data_snapshot({"ticker": "TEST", "pipeline_id": "v1", "data": {"ticker": "TEST"}})
    snapshot.pop("snapshot_hash", None)
    snapshot.pop("content_hash", None)
    path = tmp_path / "TEST_v1_report_20260607_000000.data.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    before = verify_snapshots(output_dir=str(tmp_path), write=False)
    after = verify_snapshots(output_dir=str(tmp_path), write=True)
    stored = json.loads(path.read_text(encoding="utf-8"))

    assert before["missing_hash"] == 1
    assert after["backfilled"] == 1
    assert stored["snapshot_hash"]


def test_cleanup_provider_sla_events_applies_retention_and_rebuilds_stats(monkeypatch, tmp_path):
    monkeypatch.setattr(provider_sla, "TASK_DB_PATH", str(tmp_path / "provider.sqlite3"))
    monkeypatch.setattr(provider_sla.time, "time", lambda: 100.0)
    provider_sla.record_source_audit_entries([
        {"source": "market_data", "provider": "old", "status": "error", "duration_ms": 1},
    ])
    monkeypatch.setattr(provider_sla.time, "time", lambda: 200_000.0)
    monkeypatch.setattr(provider_sla_maintenance.time, "time", lambda: 200_000.0)
    provider_sla.record_source_audit_entries([
        {"source": "market_data", "provider": "fresh", "status": "success", "duration_ms": 1},
    ])

    result = provider_sla_maintenance.cleanup_provider_sla_events(retention_days=1)
    summary = provider_sla.get_provider_sla_summary()

    assert result["deleted"] == 1
    assert [item["provider"] for item in summary] == ["fresh"]


def test_cleanup_report_index_orphans_requires_write(tmp_path):
    existing_output = tmp_path / "output"
    existing_output.mkdir()
    missing_output = tmp_path / "missing-output"
    cache_db = tmp_path / "cache.sqlite3"
    with sqlite3.connect(cache_db) as conn:
        conn.execute("CREATE TABLE reports (output_dir TEXT NOT NULL, filename TEXT NOT NULL)")
        conn.executemany(
            "INSERT INTO reports (output_dir, filename) VALUES (?, ?)",
            [
                (str(existing_output), "fresh.html"),
                (str(missing_output), "orphan.html"),
            ],
        )

    dry_run = report_index_maintenance.cleanup_report_index_orphans(cache_db_path=str(cache_db), write=False)
    storage = build_storage_summary(output_dir=str(existing_output), cache_db_path=str(cache_db))
    cleaned = report_index_maintenance.cleanup_report_index_orphans(cache_db_path=str(cache_db), write=True)

    assert dry_run["dry_run"] is True
    assert dry_run["deleted_rows"] == 0
    assert dry_run["orphan_rows"] == 1
    assert storage["cache_db"]["report_index_orphans"]["orphan_rows"] == 1
    assert cleaned["deleted_rows"] == 1
    assert cleaned["orphan_rows"] == 0


def test_cleanup_analysis_history_keeps_recent_and_active_jobs(monkeypatch, tmp_path):
    task_db = tmp_path / "jobs.sqlite3"
    now = 2_000_000.0
    old = now - 40 * 24 * 60 * 60
    with sqlite3.connect(task_db) as conn:
        conn.execute(
            """
            CREATE TABLE analysis_jobs (
                job_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                pipeline_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE analysis_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO analysis_jobs (job_id, ticker, pipeline_id, status, created_at, updated_at)
            VALUES (?, '6282', 'both', ?, ?, ?)
            """,
            [
                ("old-done", "done", old, old),
                ("recent-done", "done", now - 10, now - 10),
                ("running-old", "running", old, old),
            ],
        )
        conn.executemany(
            "INSERT INTO analysis_events (job_id, payload, created_at) VALUES (?, '{}', ?)",
            [
                ("old-done", old),
                ("recent-done", now - 10),
                ("running-old", old),
                ("orphan", old),
            ],
        )

    monkeypatch.setattr(job_store_maintenance.time, "time", lambda: now)
    dry_run = job_store_maintenance.cleanup_analysis_history(
        task_db_path=str(task_db),
        retention_days=30,
        keep_recent_jobs=1,
        write=False,
    )
    cleaned = job_store_maintenance.cleanup_analysis_history(
        task_db_path=str(task_db),
        retention_days=30,
        keep_recent_jobs=1,
        write=True,
    )

    with sqlite3.connect(task_db) as conn:
        remaining_jobs = [row[0] for row in conn.execute("SELECT job_id FROM analysis_jobs ORDER BY job_id")]
        remaining_events = [row[0] for row in conn.execute("SELECT job_id FROM analysis_events ORDER BY job_id")]

    assert dry_run["dry_run"] is True
    assert dry_run["stale_terminal_jobs"] == 1
    assert dry_run["orphan_events"] == 1
    assert cleaned["deleted_jobs"] == 1
    assert cleaned["deleted_events"] == 2
    assert remaining_jobs == ["recent-done", "running-old"]
    assert remaining_events == ["recent-done", "running-old"]


def test_maintenance_wrapper_sets_backend_pythonpath():
    script = ROOT / "scripts" / "maintenance.sh"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert script.exists()
    assert "PYTHONPATH=backend" in script.read_text(encoding="utf-8")
    assert "scripts/maintenance.sh storage-summary" in readme
    assert "cleanup-report-index --write" in readme
    assert "cleanup-analysis-history --write" in readme
