"""SQLite-backed metadata index for generated HTML/Markdown reports."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from config import CACHE_DB_PATH, OUTPUT_DIR
from data_trust import (
    data_snapshot_filename_for_report,
    normalize_data_trust,
    read_data_trust_from_snapshot,
    unknown_data_trust,
)
from pipeline_modes import get_pipeline_definition
from report_index_parsing import (
    clean_report_text,
    extract_company_name as _extract_company_name,
    extract_section,
    is_safe_report_filename,
    normalize_recommendation_label,
    output_dir_key,
    parse_recommendation_summary,
    parse_report_filename,
)
from storage.migrations import MigrationRunner, column_names


_REPORT_INDEX_LOCK = threading.Lock()
REPORT_INDEX_MIGRATION_KEY = "report_index"
REPORT_INDEX_SCHEMA_VERSION = 4


def _column_names(conn, table_name: str) -> set[str]:
    return column_names(conn, table_name)


def _set_schema_version(conn, version: int) -> None:
    conn.execute(
        """
        INSERT INTO schema_migrations (component, version, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(component) DO UPDATE SET
            version = excluded.version,
            updated_at = excluded.updated_at
        """,
        (REPORT_INDEX_MIGRATION_KEY, int(version), time.time()),
    )


def _run_report_index_migrations(conn) -> None:
    def migrate_v2(migration_conn):
        columns = _column_names(migration_conn, "reports")
        if "data_snapshot_filename" not in columns:
            migration_conn.execute("ALTER TABLE reports ADD COLUMN data_snapshot_filename TEXT NOT NULL DEFAULT ''")
        if "data_trust_json" not in columns:
            migration_conn.execute("ALTER TABLE reports ADD COLUMN data_trust_json TEXT NOT NULL DEFAULT '{}'")

    def migrate_v3(migration_conn):
        columns = _column_names(migration_conn, "reports")
        if "data_trust_status" not in columns:
            migration_conn.execute("ALTER TABLE reports ADD COLUMN data_trust_status TEXT NOT NULL DEFAULT 'unknown'")

    def migrate_v4(migration_conn):
        columns = _column_names(migration_conn, "reports")
        if "analysis_text_stale" not in columns:
            migration_conn.execute("ALTER TABLE reports ADD COLUMN analysis_text_stale INTEGER NOT NULL DEFAULT 0")
        if "analysis_text_stale_message" not in columns:
            migration_conn.execute("ALTER TABLE reports ADD COLUMN analysis_text_stale_message TEXT NOT NULL DEFAULT ''")

    MigrationRunner(conn, REPORT_INDEX_MIGRATION_KEY).run(
        REPORT_INDEX_SCHEMA_VERSION,
        {1: lambda _conn: None, 2: migrate_v2, 3: migrate_v3, 4: migrate_v4},
    )


def _connect():
    path = Path(CACHE_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
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
    _run_report_index_migrations(conn)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_reports_output_timestamp "
        "ON reports (output_dir, timestamp DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_reports_output_pipeline "
        "ON reports (output_dir, pipeline_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_reports_output_recommendation "
        "ON reports (output_dir, normalized_recommendation)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_reports_output_data_trust "
        "ON reports (output_dir, data_trust_status)"
    )
    return conn


def _safe_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _report_index_mtime(output_dir: str, filename: str) -> float:
    html_path = os.path.join(output_dir, filename)
    md_path = os.path.join(output_dir, filename[:-5] + ".md")
    data_path = os.path.join(output_dir, data_snapshot_filename_for_report(filename))
    return max(_safe_mtime(html_path), _safe_mtime(md_path), _safe_mtime(data_path))


def _read_snapshot_report_flags(data_snapshot_path: str) -> dict:
    if not os.path.exists(data_snapshot_path):
        return {"analysis_text_stale": False, "analysis_text_stale_message": ""}
    try:
        with open(data_snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"analysis_text_stale": False, "analysis_text_stale_message": ""}
    return {
        "analysis_text_stale": bool(snapshot.get("refreshed_without_analysis_rerun")),
        "analysis_text_stale_message": str(snapshot.get("analysis_text_stale_message") or "")[:240],
    }


def build_report_metadata(
    filename: str,
    output_dir: Optional[str] = None,
    html_content: Optional[str] = None,
    markdown_content: Optional[str] = None,
    data_trust: Optional[dict] = None,
) -> Optional[dict]:
    if not is_safe_report_filename(filename, ".html"):
        return None

    out_dir = output_dir_key(output_dir)
    html_path = os.path.join(out_dir, filename)
    if html_content is None and not os.path.exists(html_path):
        return None

    parsed = parse_report_filename(filename)
    html_mtime = _safe_mtime(html_path) or time.time()
    file_mtime = max(html_mtime, _report_index_mtime(out_dir, filename))

    company_name = _extract_company_name(filename, parsed["ticker"], out_dir, html_content)
    recommendation = parse_recommendation_summary(
        filename,
        output_dir=out_dir,
        markdown_text=markdown_content,
    )
    data_snapshot_filename = data_snapshot_filename_for_report(filename)
    data_snapshot_path = os.path.join(out_dir, data_snapshot_filename)
    data_trust_summary = (
        normalize_data_trust(data_trust)
        if data_trust is not None
        else read_data_trust_from_snapshot(data_snapshot_path)
    )
    snapshot_flags = _read_snapshot_report_flags(data_snapshot_path)
    normalized_recommendation = normalize_recommendation_label(recommendation.get("recommendation"))
    search_text = " ".join([
        filename,
        parsed["ticker"],
        company_name,
        str(recommendation.get("recommendation", "")),
    ]).lower()

    return {
        "output_dir": out_dir,
        "filename": filename,
        "md_filename": filename[:-5] + ".md",
        "ticker": parsed["ticker"],
        "company_name": company_name,
        "date": parsed["date"],
        "timestamp": html_mtime,
        "file_mtime": file_mtime,
        "pipeline_id": parsed["pipeline_id"],
        "recommendation": recommendation,
        "data_snapshot_filename": data_snapshot_filename if os.path.exists(data_snapshot_path) else "",
        "data_trust": data_trust_summary,
        "data_trust_status": data_trust_summary.get("status", "unknown"),
        "analysis_text_stale": snapshot_flags["analysis_text_stale"],
        "analysis_text_stale_message": snapshot_flags["analysis_text_stale_message"],
        "normalized_recommendation": normalized_recommendation,
        "search_text": search_text,
    }


def upsert_report_metadata(
    filename: str,
    output_dir: Optional[str] = None,
    html_content: Optional[str] = None,
    markdown_content: Optional[str] = None,
    data_trust: Optional[dict] = None,
) -> Optional[dict]:
    metadata = build_report_metadata(filename, output_dir, html_content, markdown_content, data_trust=data_trust)
    if not metadata:
        return None

    with _REPORT_INDEX_LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO reports (
                output_dir, filename, md_filename, ticker, company_name, report_date,
                timestamp, file_mtime, pipeline_id, recommendation_json,
                normalized_recommendation, search_text, data_snapshot_filename,
                data_trust_json, data_trust_status, analysis_text_stale,
                analysis_text_stale_message, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(output_dir, filename) DO UPDATE SET
                md_filename = excluded.md_filename,
                ticker = excluded.ticker,
                company_name = excluded.company_name,
                report_date = excluded.report_date,
                timestamp = excluded.timestamp,
                file_mtime = excluded.file_mtime,
                pipeline_id = excluded.pipeline_id,
                recommendation_json = excluded.recommendation_json,
                normalized_recommendation = excluded.normalized_recommendation,
                search_text = excluded.search_text,
                data_snapshot_filename = excluded.data_snapshot_filename,
                data_trust_json = excluded.data_trust_json,
                data_trust_status = excluded.data_trust_status,
                analysis_text_stale = excluded.analysis_text_stale,
                analysis_text_stale_message = excluded.analysis_text_stale_message,
                updated_at = excluded.updated_at
            """,
            (
                metadata["output_dir"],
                metadata["filename"],
                metadata["md_filename"],
                metadata["ticker"],
                metadata["company_name"],
                metadata["date"],
                metadata["timestamp"],
                metadata["file_mtime"],
                metadata["pipeline_id"],
                json.dumps(metadata["recommendation"], ensure_ascii=False),
                metadata["normalized_recommendation"],
                metadata["search_text"],
                metadata["data_snapshot_filename"],
                json.dumps(metadata["data_trust"], ensure_ascii=False),
                metadata["data_trust_status"],
                1 if metadata.get("analysis_text_stale") else 0,
                metadata.get("analysis_text_stale_message", ""),
                time.time(),
            ),
        )
    return metadata


def delete_report_metadata(filename: str, output_dir: Optional[str] = None) -> None:
    if not is_safe_report_filename(filename, ".html"):
        return
    with _REPORT_INDEX_LOCK, _connect() as conn:
        conn.execute(
            "DELETE FROM reports WHERE output_dir = ? AND filename = ?",
            (output_dir_key(output_dir), filename),
        )


def sync_report_metadata(output_dir: Optional[str] = None) -> None:
    out_dir = output_dir_key(output_dir)
    if not os.path.exists(out_dir):
        with _REPORT_INDEX_LOCK, _connect() as conn:
            conn.execute("DELETE FROM reports WHERE output_dir = ?", (out_dir,))
        return

    filenames = sorted(
        filename
        for filename in os.listdir(out_dir)
        if filename.endswith(".html") and is_safe_report_filename(filename, ".html")
    )
    filename_set = set(filenames)

    with _connect() as conn:
        existing_rows = conn.execute(
            "SELECT filename, file_mtime FROM reports WHERE output_dir = ?",
            (out_dir,),
        ).fetchall()
    existing_mtimes = {row["filename"]: float(row["file_mtime"]) for row in existing_rows}

    for filename in filenames:
        path = os.path.join(out_dir, filename)
        if not os.path.exists(path):
            continue
        file_mtime = _report_index_mtime(out_dir, filename)
        if filename not in existing_mtimes or abs(existing_mtimes[filename] - file_mtime) > 0.001:
            upsert_report_metadata(filename, output_dir=out_dir)

    stale = [filename for filename in existing_mtimes if filename not in filename_set]
    if stale:
        with _REPORT_INDEX_LOCK, _connect() as conn:
            conn.executemany(
                "DELETE FROM reports WHERE output_dir = ? AND filename = ?",
                [(out_dir, filename) for filename in stale],
            )


def _row_to_report(row) -> dict:
    try:
        recommendation = json.loads(row["recommendation_json"])
    except (TypeError, json.JSONDecodeError):
        recommendation = parse_recommendation_summary(row["filename"], output_dir=row["output_dir"])
    try:
        data_trust = normalize_data_trust(json.loads(row["data_trust_json"]))
    except (KeyError, TypeError, json.JSONDecodeError):
        data_trust = unknown_data_trust()

    pipeline_id = row["pipeline_id"] or "v1"
    return {
        "filename": row["filename"],
        "ticker": row["ticker"],
        "company_name": row["company_name"],
        "date": row["report_date"],
        "timestamp": row["timestamp"],
        "pipeline_id": pipeline_id,
        "pipeline_label": get_pipeline_definition(pipeline_id)["short_label"],
        "recommendation": recommendation,
        "data_snapshot_filename": row["data_snapshot_filename"] if "data_snapshot_filename" in row.keys() else "",
        "data_trust": data_trust,
        "data_trust_status": row["data_trust_status"] if "data_trust_status" in row.keys() else data_trust.get("status", "unknown"),
        "analysis_text_stale": bool(row["analysis_text_stale"]) if "analysis_text_stale" in row.keys() else False,
        "analysis_text_stale_message": row["analysis_text_stale_message"] if "analysis_text_stale_message" in row.keys() else "",
    }


def query_report_metadata(
    page: int,
    limit: int,
    q: str = "",
    pipeline: str = "all",
    recommendation: str = "all",
    data_trust: str = "all",
    output_dir: Optional[str] = None,
) -> tuple[list[dict], int]:
    out_dir = output_dir_key(output_dir)
    sync_report_metadata(out_dir)

    clauses = ["output_dir = ?"]
    params: list[object] = [out_dir]
    if pipeline != "all":
        clauses.append("pipeline_id = ?")
        params.append(pipeline)
    if recommendation != "all":
        clauses.append("normalized_recommendation = ?")
        params.append(recommendation)
    if data_trust != "all":
        clauses.append("data_trust_status = ?")
        params.append(data_trust)
    query = str(q or "").strip().lower()
    if query:
        clauses.append("search_text LIKE ?")
        params.append(f"%{query}%")

    where_sql = " AND ".join(clauses)
    offset = max(page - 1, 0) * limit
    with _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM reports WHERE {where_sql}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT * FROM reports
            WHERE {where_sql}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    return [_row_to_report(row) for row in rows], int(total)
