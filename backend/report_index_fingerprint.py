"""Read-only fingerprints for report-index cache invalidation."""

from __future__ import annotations

import sqlite3
from hashlib import sha256
from typing import Optional

from mapping_fields import safe_text


REPORT_INDEX_FINGERPRINT_FIELDS = (
    "output_dir",
    "filename",
    "pipeline_id",
    "updated_at",
    "file_mtime",
    "data_snapshot_hash",
    "html_hash",
    "markdown_hash",
    "data_file_hash",
)


def report_rows_fingerprint(rows) -> str:
    digest = sha256()
    for row in rows:
        values = []
        for field in REPORT_INDEX_FINGERPRINT_FIELDS:
            value = row.get(field) if isinstance(row, dict) else row[field]
            values.append(safe_text(value))
        digest.update("\x1f".join(values).encode("utf-8"))
        digest.update(b"\x1e")
    return digest.hexdigest()


def report_metadata_fingerprint(
    q: str = "",
    pipeline: str = "all",
    recommendation: str = "all",
    data_trust: str = "all",
    include_versions: bool = False,
    output_dir: Optional[str] = None,
    sync_metadata: bool = True,
) -> str | None:
    """Return a cheap fingerprint without hydrating report artifacts."""
    from report_index import _connect, sync_report_metadata
    from report_index_parsing import output_dir_key

    out_dir = output_dir_key(output_dir)
    try:
        if sync_metadata:
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
        order_sql = "report_date DESC, filename DESC, timestamp DESC"
        with _connect() as conn:
            if include_versions:
                rows_sql = f"SELECT * FROM reports WHERE {where_sql} ORDER BY {order_sql}"
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
                rows_sql = f"SELECT * {latest_sql} ORDER BY {order_sql}"
            rows = conn.execute(rows_sql, params).fetchall()
        return report_rows_fingerprint(rows)
    except (OSError, sqlite3.Error):
        return None
