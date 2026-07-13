import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import pytest

from storage_inventory import build_storage_summary, clear_runtime_storage, ensure_runtime_storage  # noqa: E402


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


def test_storage_summary_counts_partitioned_report_artifacts(tmp_path):
    output_dir = tmp_path / "output"
    report_dir = output_dir / "2026-07" / "AAPL"
    report_dir.mkdir(parents=True)
    (report_dir / "AAPL_v1_report_20260711_000000.html").write_text("<html></html>", encoding="utf-8")
    (report_dir / "AAPL_v1_report_20260711_000000.md").write_text("# report", encoding="utf-8")
    (report_dir / "AAPL_v1_report_20260711_000000.data.json").write_text("{}", encoding="utf-8")

    summary = build_storage_summary(output_dir=str(output_dir), cache_db_path=str(tmp_path / "cache.sqlite3"))

    assert summary["reports"]["html"] == 1
    assert summary["reports"]["markdown"] == 1
    assert summary["reports"]["data_snapshots"] == 1


def test_storage_summary_ignores_symlink_report_artifacts(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    external = tmp_path / "external.html"
    external.write_text("<html></html>", encoding="utf-8")
    (output_dir / "linked.html").symlink_to(external)

    summary = build_storage_summary(output_dir=str(output_dir), cache_db_path=str(tmp_path / "cache.sqlite3"))

    assert summary["reports"]["html"] == 0


def test_clear_runtime_storage_requires_confirmation_and_removes_contents(tmp_path):
    output_dir = tmp_path / "output"
    cache_dir = tmp_path / "cache"
    calendars = cache_dir / "market_calendars"
    output_dir.mkdir()
    calendars.mkdir(parents=True)
    cache_db = cache_dir / "cache.sqlite3"
    task_db = cache_dir / "tasks.sqlite3"
    for path in [
        output_dir / "report.html",
        output_dir / "report.md",
        cache_db,
        Path(f"{cache_db}-wal"),
        task_db,
        calendars / "us_2026.json",
    ]:
        path.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError):
        clear_runtime_storage(
            output_dir=str(output_dir),
            cache_dir=str(cache_dir),
            cache_db_path=str(cache_db),
            task_db_path=str(task_db),
            market_calendar_dir=str(calendars),
        )

    result = clear_runtime_storage(
        output_dir=str(output_dir),
        cache_dir=str(cache_dir),
        cache_db_path=str(cache_db),
        task_db_path=str(task_db),
        market_calendar_dir=str(calendars),
        confirm_delete=True,
    )

    assert output_dir.exists()
    assert cache_dir.exists()
    assert not any(output_dir.iterdir())
    assert not any(cache_dir.iterdir())
    assert result["removed_count"] >= 5
    assert result["summary"]["reports"]["html"] == 0
    assert result["summary"]["cache_db"]["exists"] is False


def test_ensure_runtime_storage_creates_openable_sqlite_paths(tmp_path):
    output_dir = tmp_path / "output"
    cache_dir = tmp_path / "cache"
    cache_db = cache_dir / "stock_agent_cache.sqlite3"
    task_db = cache_dir / "analysis_jobs.sqlite3"
    checkpoint_db = cache_dir / "langgraph_checkpoints.sqlite3"
    tracking_db = cache_dir / "decision_tracking.sqlite3"
    watchlist_db = cache_dir / "watchlist.sqlite3"
    yfinance_cache = cache_dir / "yfinance"
    calendars = cache_dir / "market_calendars"

    result = ensure_runtime_storage(
        output_dir=str(output_dir),
        cache_dir=str(cache_dir),
        cache_db_path=str(cache_db),
        task_db_path=str(task_db),
        checkpoint_path=str(checkpoint_db),
        decision_tracking_db_path=str(tracking_db),
        watchlist_db_path=str(watchlist_db),
        yfinance_cache_dir=str(yfinance_cache),
        market_calendar_dir=str(calendars),
    )

    assert result["success"] is True
    assert output_dir.is_dir()
    assert cache_dir.is_dir()
    assert calendars.is_dir()
    assert yfinance_cache.is_dir()
    assert result["directories"]["yfinance_cache_dir"] == str(yfinance_cache)
    import yfinance.cache as yf_cache

    assert yf_cache._TzDBManager.get_location() == str(yfinance_cache)
    for db_path in (cache_db, task_db, checkpoint_db, tracking_db, watchlist_db):
        with sqlite3.connect(db_path) as conn:
            assert conn.execute("PRAGMA user_version").fetchone() is not None


def test_ensure_runtime_storage_defaults_operational_consumers_to_task_db(tmp_path, monkeypatch):
    monkeypatch.delenv("DECISION_TRACKING_DB_PATH", raising=False)
    monkeypatch.delenv("WATCHLIST_DB_PATH", raising=False)
    monkeypatch.delenv("WATCHLIST_PATH", raising=False)
    cache_dir = tmp_path / "cache"
    cache_db = cache_dir / "stock_agent_cache.sqlite3"
    task_db = cache_dir / "operational.sqlite3"

    result = ensure_runtime_storage(
        output_dir=str(tmp_path / "output"),
        cache_dir=str(cache_dir),
        cache_db_path=str(cache_db),
        task_db_path=str(task_db),
        checkpoint_path=str(cache_db),
        market_calendar_dir=str(cache_dir / "market_calendars"),
    )

    assert result["sqlite_paths"]["decision_tracking_db"] == str(task_db.resolve(strict=False))
    assert result["sqlite_paths"]["watchlist_db"] == str(task_db.resolve(strict=False))
    assert not (cache_dir / "decision_tracking.sqlite3").exists()
    assert not (cache_dir / "watchlist.sqlite3").exists()


def test_ensure_runtime_storage_skips_checkpoint_sqlite_for_postgres_backend(tmp_path):
    cache_dir = tmp_path / "cache"
    checkpoint_db = cache_dir / "langgraph_checkpoints.sqlite3"

    result = ensure_runtime_storage(
        output_dir=str(tmp_path / "output"),
        cache_dir=str(cache_dir),
        cache_db_path=str(cache_dir / "stock_agent_cache.sqlite3"),
        task_db_path=str(cache_dir / "operational.sqlite3"),
        checkpoint_backend="postgres",
        checkpoint_path=str(checkpoint_db),
        market_calendar_dir=str(cache_dir / "market_calendars"),
    )

    assert "checkpoint_db" not in result["sqlite_paths"]
    assert not checkpoint_db.exists()


def test_ensure_runtime_storage_rejects_directory_used_as_database(tmp_path):
    bad_cache_db = tmp_path / "cache-as-db"
    bad_cache_db.mkdir()

    with pytest.raises(RuntimeError, match="cache_db.*directory"):
        ensure_runtime_storage(
            output_dir=str(tmp_path / "output"),
            cache_dir=str(tmp_path / "cache"),
            cache_db_path=str(bad_cache_db),
            task_db_path=str(tmp_path / "cache" / "tasks.sqlite3"),
            checkpoint_path=str(tmp_path / "cache" / "checkpoints.sqlite3"),
            decision_tracking_db_path=str(tmp_path / "cache" / "tracking.sqlite3"),
            watchlist_db_path=str(tmp_path / "cache" / "watchlist.sqlite3"),
            market_calendar_dir=str(tmp_path / "cache" / "market_calendars"),
        )
