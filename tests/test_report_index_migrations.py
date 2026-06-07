import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import report_index  # noqa: E402


def _columns(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {row[1] for row in conn.execute("PRAGMA table_info(reports)").fetchall()}


def _migration_version(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT version FROM schema_migrations WHERE component = ?",
            (report_index.REPORT_INDEX_MIGRATION_KEY,),
        ).fetchone()
    return int(row[0])


def _create_v1_reports_table(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE reports (
                output_dir TEXT NOT NULL,
                filename TEXT NOT NULL,
                md_filename TEXT NOT NULL,
                ticker TEXT NOT NULL,
                company_name TEXT NOT NULL,
                report_date TEXT NOT NULL,
                timestamp REAL NOT NULL,
                file_mtime REAL NOT NULL,
                pipeline_id TEXT NOT NULL,
                recommendation_json TEXT NOT NULL,
                normalized_recommendation TEXT NOT NULL,
                search_text TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (output_dir, filename)
            )
            """
        )


def test_report_index_migration_from_empty_db(monkeypatch, tmp_path):
    db_path = tmp_path / "cache.db"
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(db_path))

    with report_index._connect() as conn:
        version = conn.execute(
            "SELECT version FROM schema_migrations WHERE component = ?",
            (report_index.REPORT_INDEX_MIGRATION_KEY,),
        ).fetchone()["version"]

    assert version == report_index.REPORT_INDEX_SCHEMA_VERSION
    assert {"data_snapshot_filename", "data_trust_json", "data_trust_status", "data_snapshot_hash"}.issubset(_columns(db_path))


def test_report_index_migration_upgrades_v1_and_v2_idempotently(monkeypatch, tmp_path):
    db_path = tmp_path / "cache.db"
    _create_v1_reports_table(db_path)
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(db_path))

    with report_index._connect():
        pass
    with report_index._connect():
        pass

    assert {"data_snapshot_filename", "data_trust_json", "data_trust_status", "data_snapshot_hash"}.issubset(_columns(db_path))
    assert _migration_version(db_path) == report_index.REPORT_INDEX_SCHEMA_VERSION

    v2_path = tmp_path / "cache_v2.db"
    _create_v1_reports_table(v2_path)
    with sqlite3.connect(v2_path) as conn:
        conn.execute("ALTER TABLE reports ADD COLUMN data_snapshot_filename TEXT NOT NULL DEFAULT ''")
        conn.execute("ALTER TABLE reports ADD COLUMN data_trust_json TEXT NOT NULL DEFAULT '{}'")
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(v2_path))

    with report_index._connect():
        pass

    assert {"data_trust_status", "data_snapshot_hash"}.issubset(_columns(v2_path))
    assert _migration_version(v2_path) == report_index.REPORT_INDEX_SCHEMA_VERSION
