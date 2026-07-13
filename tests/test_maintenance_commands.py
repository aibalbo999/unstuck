import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import provider_sla  # noqa: E402
import provider_sla_maintenance  # noqa: E402
import report_index_maintenance  # noqa: E402
import database_maintenance  # noqa: E402
import job_store_maintenance  # noqa: E402
from data_trust_snapshot import build_data_snapshot, verify_data_snapshot_integrity  # noqa: E402
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


def test_verify_snapshots_write_repairs_mismatched_hash(tmp_path):
    snapshot = build_data_snapshot({"ticker": "TEST", "pipeline_id": "v1", "data": {"ticker": "TEST"}})
    snapshot["data"]["current_price"] = 123
    path = tmp_path / "TEST_v1_report_20260607_000000.data.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    before = verify_snapshots(output_dir=str(tmp_path), write=False)
    after = verify_snapshots(output_dir=str(tmp_path), write=True)
    stored = json.loads(path.read_text(encoding="utf-8"))

    assert before["mismatch"] == 1
    assert after["mismatch"] == 0
    assert after["repaired"] == 1
    assert verify_data_snapshot_integrity(stored)["valid"] is True


def test_verify_snapshots_treats_falsey_hash_metadata_as_mismatch(tmp_path):
    snapshot = build_data_snapshot({"ticker": "TEST", "pipeline_id": "v1", "data": {"ticker": "TEST"}})
    snapshot["snapshot_hash"] = 0
    snapshot.pop("content_hash", None)
    path = tmp_path / "TEST_v1_report_20260607_000000.data.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    before = verify_snapshots(output_dir=str(tmp_path), write=False)
    after = verify_snapshots(output_dir=str(tmp_path), write=True)
    stored = json.loads(path.read_text(encoding="utf-8"))

    assert before["missing_hash"] == 0
    assert before["mismatch"] == 1
    assert before["results"][0]["expected_hash"] == "0"
    assert after["repaired"] == 1
    assert after["results"][0]["previous_hash"] == "0"
    assert verify_data_snapshot_integrity(stored)["valid"] is True


def test_verify_snapshots_covers_partitioned_report_artifacts(tmp_path):
    snapshot = build_data_snapshot({"ticker": "TEST", "pipeline_id": "v1", "data": {"ticker": "TEST"}})
    snapshot.pop("snapshot_hash", None)
    snapshot.pop("content_hash", None)
    path = tmp_path / "2026-07" / "TEST" / "TEST_v1_report_20260711_000000.data.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    result = verify_snapshots(output_dir=str(tmp_path), write=False)

    assert result["checked"] == 1
    assert result["missing_hash"] == 1
    assert result["results"][0]["file"] == "2026-07/TEST/TEST_v1_report_20260711_000000.data.json"


def test_verify_snapshots_ignores_symlink_artifacts(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    external = tmp_path / "external.data.json"
    external.write_text("{}", encoding="utf-8")
    linked = output_dir / "2026-07" / "TEST" / "linked.data.json"
    linked.parent.mkdir(parents=True)
    linked.symlink_to(external)

    result = verify_snapshots(output_dir=str(output_dir), write=False)

    assert result["checked"] == 0


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


def test_runtime_sqlite_paths_deduplicates_same_canonical_path(tmp_path):
    shared = tmp_path / "shared.sqlite3"
    task = tmp_path / "task.sqlite3"

    result = database_maintenance.runtime_sqlite_paths(
        cache_db_path=str(shared),
        task_db_path=str(task),
        checkpoint_backend="sqlite",
        checkpoint_path=str(tmp_path / "nested" / ".." / "shared.sqlite3"),
    )

    assert result == {"cache_db": str(shared), "task_db": str(task)}


def test_sqlite_database_maintenance_dry_run_plans_backup_checkpoint_and_vacuum(tmp_path):
    db_path = tmp_path / "jobs.sqlite3"
    backup_dir = tmp_path / "backups"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE sample (value TEXT)")
        conn.execute("INSERT INTO sample (value) VALUES ('ok')")

    result = database_maintenance.maintain_sqlite_databases(
        {"task_db": str(db_path)},
        backup_dir=str(backup_dir),
        write=False,
        now=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )

    db_result = result["databases"][0]
    assert result["dry_run"] is True
    assert result["backup_pruning"]["retention_days"] == 1
    assert result["backup_pruning"]["cutoff"] == "2026-06-29"
    assert db_result["label"] == "task_db"
    assert db_result["exists"] is True
    assert db_result["backup"]["path"].endswith("task_db-20260629.sqlite3")
    assert db_result["backup"]["status"] == "planned"
    assert db_result["wal_checkpoint"]["status"] == "planned"
    assert db_result["vacuum"]["status"] == "planned"
    assert not backup_dir.exists()


def test_sqlite_database_maintenance_write_creates_daily_backup_and_is_idempotent(tmp_path):
    db_path = tmp_path / "jobs.sqlite3"
    backup_dir = tmp_path / "backups"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE sample (value TEXT)")
        conn.execute("INSERT INTO sample (value) VALUES ('ok')")

    result = database_maintenance.maintain_sqlite_databases(
        {"task_db": str(db_path)},
        backup_dir=str(backup_dir),
        write=True,
        now=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )
    second = database_maintenance.maintain_sqlite_databases(
        {"task_db": str(db_path)},
        backup_dir=str(backup_dir),
        write=True,
        now=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )

    backup_path = backup_dir / "task_db-20260629.sqlite3"
    with sqlite3.connect(backup_path) as conn:
        rows = conn.execute("SELECT value FROM sample").fetchall()

    db_result = result["databases"][0]
    assert result["dry_run"] is False
    assert db_result["backup"]["status"] == "created"
    assert db_result["wal_checkpoint"]["status"] == "ran"
    assert db_result["vacuum"]["status"] == "ran"
    assert rows == [("ok",)]
    second_db_result = second["databases"][0]
    assert second_db_result["backup"]["status"] == "skipped_interval"
    assert second_db_result["wal_checkpoint"]["status"] == "skipped_backup_interval"
    assert second_db_result["vacuum"]["status"] == "skipped_backup_interval"


def test_sqlite_backup_interval_skips_recent_backup_without_maintenance(tmp_path):
    db_path = tmp_path / "jobs.sqlite3"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "task_db-20260701.sqlite3").write_bytes(b"backup")
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE sample (value TEXT)")
        conn.execute("INSERT INTO sample (value) VALUES ('ok')")

    result = database_maintenance.maintain_sqlite_databases(
        {"task_db": str(db_path)},
        backup_dir=str(backup_dir),
        backup_interval_days=30,
        write=True,
        now=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )

    db_result = result["databases"][0]
    assert db_result["backup"]["status"] == "skipped_interval"
    assert db_result["backup"]["latest_backup"].endswith("task_db-20260701.sqlite3")
    assert db_result["backup"]["next_due_date"] == "2026-07-31"
    assert db_result["wal_checkpoint"]["status"] == "skipped_backup_interval"
    assert db_result["vacuum"]["status"] == "skipped_backup_interval"
    assert not (backup_dir / "task_db-20260710.sqlite3").exists()


def test_sqlite_backup_interval_creates_backup_after_due_and_maintains_once(tmp_path):
    db_path = tmp_path / "jobs.sqlite3"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "task_db-20260601.sqlite3").write_bytes(b"backup")
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE sample (value TEXT)")
        conn.execute("INSERT INTO sample (value) VALUES ('ok')")

    result = database_maintenance.maintain_sqlite_databases(
        {"task_db": str(db_path)},
        backup_dir=str(backup_dir),
        backup_interval_days=30,
        write=True,
        now=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )

    db_result = result["databases"][0]
    assert db_result["backup"]["status"] == "created"
    assert db_result["wal_checkpoint"]["status"] == "ran"
    assert db_result["vacuum"]["status"] == "ran"
    assert (backup_dir / "task_db-20260701.sqlite3").exists()


def test_sqlite_backup_skips_unsafe_backup_destination_symlink(tmp_path):
    db_path = tmp_path / "jobs.sqlite3"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    symlink_target = tmp_path / "outside.sqlite3"
    destination = backup_dir / "task_db-20260701.sqlite3"
    symlink_target.write_bytes(b"not a backup")
    destination.symlink_to(symlink_target)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE sample (value TEXT)")
        conn.execute("INSERT INTO sample (value) VALUES ('ok')")

    result = database_maintenance.maintain_sqlite_databases(
        {"task_db": str(db_path)},
        backup_dir=str(backup_dir),
        backup_interval_days=30,
        write=True,
        now=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )

    db_result = result["databases"][0]
    assert db_result["backup"]["status"] == "skipped_unsafe"
    assert db_result["backup"]["reason"] == "backup destination is not a regular file"
    assert db_result["wal_checkpoint"]["status"] == "skipped_backup_unsafe"
    assert db_result["vacuum"]["status"] == "skipped_backup_unsafe"
    assert destination.is_symlink()
    assert symlink_target.read_bytes() == b"not a backup"


def test_sqlite_backup_pruning_dry_run_preserves_files(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    old = backup_dir / "cache_db-20260625.sqlite3"
    recent = backup_dir / "cache_db-20260628.sqlite3"
    unknown = backup_dir / "manual-archive.sqlite3"
    unmanaged = backup_dir / "cache_db-20260625.sqlite3-wal"
    managed_name_directory = backup_dir / "task_db-20260625.sqlite3"
    for path in (old, recent, unknown, unmanaged):
        path.write_bytes(b"backup")
    managed_name_directory.mkdir()

    result = database_maintenance.maintain_sqlite_databases(
        {},
        backup_dir=str(backup_dir),
        retention_days=3,
        write=False,
        now=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )

    pruning = result["backup_pruning"]
    assert pruning["retention_days"] == 3
    assert pruning["cutoff"] == "2026-06-27"
    assert pruning["candidates"] == [str(old)]
    assert pruning["deleted"] == []
    assert pruning["dry_run"] is True
    assert all(
        path.exists() for path in (old, recent, unknown, unmanaged, managed_name_directory)
    )


def test_sqlite_backup_pruning_retention_one_uses_utc_date_cutoff(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    old = backup_dir / "cache_db-20260628.sqlite3"
    current = backup_dir / "cache_db-20260629.sqlite3"
    old.write_bytes(b"backup")
    current.write_bytes(b"backup")

    result = database_maintenance.maintain_sqlite_databases(
        {},
        backup_dir=str(backup_dir),
        retention_days=1,
        write=False,
        now=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )

    assert result["backup_pruning"]["cutoff"] == "2026-06-29"
    assert result["backup_pruning"]["candidates"] == [str(old)]
    assert result["backup_pruning"]["deleted"] == []


def test_sqlite_backup_pruning_retention_one_preserves_latest_active_label_backup(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    stale_cache = backup_dir / "cache_db-20260601.sqlite3"
    latest_cache = backup_dir / "cache_db-20260701.sqlite3"
    latest_task = backup_dir / "task_db-20260630.sqlite3"
    inactive_checkpoint = backup_dir / "checkpoint_db-20260710.sqlite3"
    for path in (stale_cache, latest_cache, latest_task, inactive_checkpoint):
        path.write_bytes(b"backup")

    result = database_maintenance.maintain_sqlite_databases(
        {
            "cache_db": str(tmp_path / "missing-cache.sqlite3"),
            "task_db": str(tmp_path / "missing-task.sqlite3"),
        },
        backup_dir=str(backup_dir),
        retention_days=1,
        write=True,
        now=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )

    pruning = result["backup_pruning"]
    assert pruning["candidates"] == [str(stale_cache), str(inactive_checkpoint)]
    assert pruning["deleted"] == [str(stale_cache), str(inactive_checkpoint)]
    assert not stale_cache.exists()
    assert not inactive_checkpoint.exists()
    assert latest_cache.exists()
    assert latest_task.exists()


def test_sqlite_backup_pruning_write_deletes_only_managed_expired_files(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    old = backup_dir / "cache_db-20260625.sqlite3"
    recent = backup_dir / "cache_db-20260628.sqlite3"
    unknown = backup_dir / "manual-archive.sqlite3"
    unmanaged = backup_dir / "cache_db-20260625.sqlite3-shm"
    managed_name_directory = backup_dir / "checkpoint_db-20260625.sqlite3"
    symlink_target = tmp_path / "symlink-target.sqlite3"
    managed_name_symlink = backup_dir / "task_db-20260625.sqlite3"
    for path in (old, recent, unknown, unmanaged):
        path.write_bytes(b"backup")
    managed_name_directory.mkdir()
    symlink_target.write_bytes(b"backup")
    managed_name_symlink.symlink_to(symlink_target)

    result = database_maintenance.maintain_sqlite_databases(
        {},
        backup_dir=str(backup_dir),
        retention_days=1,
        write=True,
        now=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )

    pruning = result["backup_pruning"]
    assert pruning["retention_days"] == 1
    assert pruning["cutoff"] == "2026-06-29"
    assert pruning["candidates"] == [str(old)]
    assert pruning["deleted"] == [str(old)]
    assert pruning["dry_run"] is False
    assert not old.exists()
    assert all(path.exists() for path in (recent, unknown, unmanaged, managed_name_directory))
    assert managed_name_symlink.is_symlink()
    assert symlink_target.exists()


@pytest.mark.parametrize("retention_days,backup_interval_days", [(0, 30), (-1, 30), (1, 0), (1, -1)])
def test_sqlite_backup_pruning_rejects_invalid_values_before_maintenance(
    tmp_path, retention_days, backup_interval_days
):
    db_path = tmp_path / "jobs.sqlite3"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    old = backup_dir / "task_db-20260625.sqlite3"
    old.write_bytes(b"backup")
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE sample (value TEXT)")

    expected_message = (
        "retention_days must be at least 1"
        if retention_days < 1
        else "backup_interval_days must be at least 1"
    )
    with pytest.raises(ValueError, match=expected_message):
        database_maintenance.maintain_sqlite_databases(
            {"task_db": str(db_path)},
            backup_dir=str(backup_dir),
            retention_days=retention_days,
            backup_interval_days=backup_interval_days,
            write=True,
            now=datetime(2026, 6, 29, tzinfo=timezone.utc),
        )

    assert old.exists()
    assert not (backup_dir / "task_db-20260629.sqlite3").exists()


def test_maintenance_wrapper_sets_backend_pythonpath():
    script = ROOT / "scripts" / "maintenance.sh"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert script.exists()
    assert "PYTHONPATH=backend" in script.read_text(encoding="utf-8")
    assert "scripts/maintenance.sh storage-summary" in readme
    assert "cleanup-report-index --write" in readme
    assert "cleanup-analysis-history --write" in readme
    assert "cleanup-terminal-checkpoints --write" in readme
