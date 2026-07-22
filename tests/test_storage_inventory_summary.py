import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from storage_inventory_summary import report_file_counts, sqlite_table_counts  # noqa: E402


def test_report_file_counts_recurses_and_ignores_symlinks(tmp_path):
    output_dir = tmp_path / "output"
    report_dir = output_dir / "2026-07" / "AAPL"
    report_dir.mkdir(parents=True)
    (report_dir / "AAPL_v1_report_20260711_000000.html").write_text("<html></html>", encoding="utf-8")
    (report_dir / "AAPL_v1_report_20260711_000000.md").write_text("# report", encoding="utf-8")
    (report_dir / "AAPL_v1_report_20260711_000000.data.json").write_text("{}", encoding="utf-8")
    external = tmp_path / "external.html"
    external.write_text("<html></html>", encoding="utf-8")
    (output_dir / "linked.html").symlink_to(external)

    counts = report_file_counts(output_dir)

    assert counts == {"exists": True, "html": 1, "markdown": 1, "data_snapshots": 1}


def test_report_file_counts_marks_missing_output_dir(tmp_path):
    assert report_file_counts(tmp_path / "missing-output") == {
        "exists": False,
        "html": 0,
        "markdown": 0,
        "data_snapshots": 0,
    }


def test_sqlite_table_counts_distinguishes_missing_tables_from_empty_tables(tmp_path):
    db_path = tmp_path / "cache.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE cache_entries (cache_key TEXT)")
        conn.execute("CREATE TABLE reports (filename TEXT)")
        conn.execute("INSERT INTO reports VALUES ('AAPL.html')")

    counts = sqlite_table_counts(db_path, ("cache_entries", "reports", "schema_migrations"))

    assert counts == {"cache_entries": 0, "reports": 1, "schema_migrations": None}


def test_sqlite_table_counts_returns_none_values_when_database_is_absent(tmp_path):
    counts = sqlite_table_counts(tmp_path / "missing.sqlite3", ("cache_entries", "reports"))

    assert counts == {"cache_entries": None, "reports": None}
