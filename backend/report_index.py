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
from report_index_connection import connect_report_index_sqlite
from report_index_parsing import is_safe_report_filename, normalize_recommendation_label, output_dir_key, parse_recommendation_summary
from report_index_metadata import build_report_metadata, report_index_mtime
from report_index_migrations import REPORT_INDEX_MIGRATION_KEY, REPORT_INDEX_SCHEMA_VERSION, run_report_index_migrations
from report_index_repair import stored_recommendation_needs_rebuild
from report_index_rows import row_to_report


_REPORT_INDEX_LOCK = threading.Lock()


def _connect():
    conn = connect_report_index_sqlite(CACHE_DB_PATH, sqlite3.connect)
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
    run_report_index_migrations(conn)
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
            analysis_text_stale_message, data_snapshot_hash, html_hash,
            markdown_hash, data_file_hash, decision_tracking_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                data_snapshot_hash = excluded.data_snapshot_hash,
                html_hash = excluded.html_hash,
                markdown_hash = excluded.markdown_hash,
                data_file_hash = excluded.data_file_hash,
                decision_tracking_json = excluded.decision_tracking_json,
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
                metadata.get("data_snapshot_hash", ""),
                metadata.get("html_hash", ""),
                metadata.get("markdown_hash", ""),
                metadata.get("data_file_hash", ""),
                json.dumps(metadata.get("decision_tracking", {}), ensure_ascii=False),
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
        path.name
        for path in Path(out_dir).rglob("*.html")
        if path.is_file() and is_safe_report_filename(path.name, ".html")
    )
    filename_set = set(filenames)

    with _connect() as conn:
        existing_rows = conn.execute(
            "SELECT filename, file_mtime, recommendation_json FROM reports WHERE output_dir = ?",
            (out_dir,),
        ).fetchall()
    existing = {row["filename"]: row for row in existing_rows}
    existing_mtimes = {filename: float(row["file_mtime"]) for filename, row in existing.items()}

    for filename in filenames:
        file_mtime = report_index_mtime(out_dir, filename)
        if file_mtime <= 0:
            continue
        if (
            filename not in existing_mtimes or abs(existing_mtimes[filename] - file_mtime) > 0.001
            or stored_recommendation_needs_rebuild(existing[filename], out_dir)
        ):
            upsert_report_metadata(filename, output_dir=out_dir)

    stale = [filename for filename in existing_mtimes if filename not in filename_set]
    if stale:
        with _REPORT_INDEX_LOCK, _connect() as conn:
            conn.executemany(
                "DELETE FROM reports WHERE output_dir = ? AND filename = ?",
                [(out_dir, filename) for filename in stale],
            )


def query_report_metadata(
    page: int,
    limit: int,
    q: str = "",
    pipeline: str = "all",
    recommendation: str = "all",
    data_trust: str = "all",
    include_versions: bool = False,
    output_dir: Optional[str] = None,
    sync_metadata: bool = True,
) -> tuple[list[dict], int]:
    out_dir = output_dir_key(output_dir)
    if sync_metadata: sync_report_metadata(out_dir)

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
    order_sql = "report_date DESC, filename DESC, timestamp DESC"
    with _connect() as conn:
        if include_versions:
            total = conn.execute(
                f"SELECT COUNT(*) FROM reports WHERE {where_sql}",
                params,
            ).fetchone()[0]
            rows_sql = f"""
                SELECT * FROM reports WHERE {where_sql}
                ORDER BY {order_sql} LIMIT ? OFFSET ?
            """
        else:
            latest_sql = f"""
                FROM (
                    SELECT reports.*, ROW_NUMBER() OVER (
                        PARTITION BY
                            lower(CASE WHEN instr(ticker, '.') > 0 THEN substr(ticker, 1, instr(ticker, '.') - 1) ELSE ticker END),
                            pipeline_id ORDER BY {order_sql}
                    ) AS version_rank
                    FROM reports WHERE {where_sql}
                )
                WHERE version_rank = 1
            """
            total = conn.execute(f"SELECT COUNT(*) {latest_sql}", params).fetchone()[0]
            rows_sql = f"SELECT * {latest_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?"
        rows = conn.execute(rows_sql, [*params, limit, offset]).fetchall()
    return [row_to_report(row) for row in rows], int(total)
