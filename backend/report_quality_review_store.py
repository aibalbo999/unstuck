"""Append-only operator review ledger for historical report quality gaps."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mapping_fields import safe_text, safe_text_list
from report_index_parsing import is_safe_report_filename
from runtime_paths import current_runtime_paths
from storage.sqlite_resource import ThreadLocalSqliteResource


SCHEMA_VERSION = "report_quality_review.v1"
QUALITY_REVIEW_DB_PATH = os.getenv("QUALITY_REVIEW_DB_PATH", str(current_runtime_paths().task_db))
VALID_REVIEW_DECISIONS = frozenset({"approved_with_gap", "rejected", "deferred"})
QUALITY_METADATA_FIELDS = frozenset({"report_conformance", "evidence_exit_gate", "content_credibility"})
REVIEW_DECISION_LABELS = {
    "pending": "待人工核對",
    "approved_with_gap": "已核准保留缺口",
    "rejected": "退回處理",
    "deferred": "已暫緩",
}


def _db_path() -> Path:
    return Path(QUALITY_REVIEW_DB_PATH)


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS report_quality_review_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            output_dir TEXT NOT NULL,
            filename TEXT NOT NULL,
            ticker TEXT NOT NULL,
            pipeline_id TEXT NOT NULL,
            report_quality_revision TEXT NOT NULL,
            decision TEXT NOT NULL,
            reviewer_label TEXT NOT NULL,
            note TEXT NOT NULL,
            missing_quality_fields_json TEXT NOT NULL,
            artifact_quality_summary_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_report_quality_review_target
        ON report_quality_review_events (
            output_dir, filename, pipeline_id, report_quality_revision, event_id DESC
        )
        """
    )


_resource = ThreadLocalSqliteResource(_db_path, init_schema=_init_schema, row_factory=sqlite3.Row)


def reset_report_quality_review_store_for_tests() -> None:
    _resource.reset()
    path = _db_path()
    if not path.exists():
        return
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE IF EXISTS report_quality_review_events")
        _init_schema(conn)


def record_review(
    *,
    output_dir: str,
    filename: str,
    ticker: str,
    pipeline_id: str,
    report_quality_revision: str,
    missing_quality_fields: list[str] | tuple[str, ...],
    artifact_quality_summary: dict[str, Any] | None,
    decision: str,
    note: str,
    reviewer_label: str = "local_operator",
    now: str | None = None,
) -> dict[str, Any]:
    normalized_filename = safe_text(filename).strip()
    if not is_safe_report_filename(normalized_filename, ".html"):
        raise ValueError("invalid report filename")
    normalized_decision = safe_text(decision).strip().lower()
    if normalized_decision not in VALID_REVIEW_DECISIONS:
        raise ValueError(f"unsupported review decision: {normalized_decision}")
    normalized_note = safe_text(note).strip()
    if not normalized_note:
        raise ValueError("review note is required")
    if len(normalized_note) > 2000:
        raise ValueError("review note is too long")
    normalized_revision = safe_text(report_quality_revision).strip()
    if not normalized_revision:
        raise ValueError("report quality revision is required")
    if len(normalized_revision) > 128:
        raise ValueError("report quality revision is too long")
    normalized_reviewer = safe_text(reviewer_label).strip() or "local_operator"
    if len(normalized_reviewer) > 80:
        raise ValueError("reviewer label is too long")
    normalized_fields = _quality_fields(missing_quality_fields)
    normalized_artifact = _artifact_summary(artifact_quality_summary)
    created_at = safe_text(now).strip() or datetime.now(timezone.utc).isoformat()
    output_dir_key = str(Path(output_dir).expanduser().resolve(strict=False))
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO report_quality_review_events (
                output_dir, filename, ticker, pipeline_id, report_quality_revision,
                decision, reviewer_label, note, missing_quality_fields_json,
                artifact_quality_summary_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                output_dir_key,
                normalized_filename,
                safe_text(ticker).strip(),
                safe_text(pipeline_id).strip() or "v1",
                normalized_revision,
                normalized_decision,
                normalized_reviewer,
                normalized_note,
                json.dumps(normalized_fields, ensure_ascii=False, separators=(",", ":")),
                json.dumps(normalized_artifact, ensure_ascii=False, separators=(",", ":")),
                created_at,
            ),
        )
        row = conn.execute(
            "SELECT * FROM report_quality_review_events WHERE event_id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        event_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM report_quality_review_events
            WHERE output_dir = ? AND filename = ? AND pipeline_id = ? AND report_quality_revision = ?
            """,
            (output_dir_key, normalized_filename, safe_text(pipeline_id).strip() or "v1", normalized_revision),
        ).fetchone()["count"]
    return _row_to_review(row, event_count=event_count)


def list_latest_reviews(
    output_dir: str,
    targets: list[tuple[str, str, str]] | tuple[tuple[str, str, str], ...],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    normalized_targets = {
        (safe_text(filename).strip(), safe_text(pipeline_id).strip() or "v1", safe_text(revision).strip())
        for filename, pipeline_id, revision in targets
        if safe_text(filename).strip() and safe_text(revision).strip()
    }
    if not normalized_targets:
        return {}
    output_dir_key = str(Path(output_dir).expanduser().resolve(strict=False))
    filenames = sorted({filename for filename, _pipeline_id, _revision in normalized_targets})
    placeholders = ", ".join("?" for _ in filenames)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT *,
                   COUNT(*) OVER (
                       PARTITION BY filename, pipeline_id, report_quality_revision
                   ) AS event_count,
                   ROW_NUMBER() OVER (
                       PARTITION BY filename, pipeline_id, report_quality_revision
                       ORDER BY event_id DESC
                   ) AS latest_rank
            FROM report_quality_review_events
            WHERE output_dir = ? AND filename IN ({placeholders})
            """,
            (output_dir_key, *filenames),
        ).fetchall()
    result = {}
    for row in rows:
        key = (safe_text(row["filename"]).strip(), safe_text(row["pipeline_id"]).strip() or "v1", safe_text(row["report_quality_revision"]).strip())
        if row["latest_rank"] == 1 and key in normalized_targets:
            result[key] = _row_to_review(row, event_count=row["event_count"])
    return result


def pending_review(*, report_quality_revision: str) -> dict[str, Any]:
    return {
        "status": "pending",
        "decision": "",
        "decision_label": REVIEW_DECISION_LABELS["pending"],
        "reviewer_label": "",
        "note": "",
        "reviewed_at": None,
        "event_count": 0,
        "report_quality_revision": safe_text(report_quality_revision).strip(),
    }


def _connect() -> sqlite3.Connection:
    return _resource.connect()


def _quality_fields(values: list[str] | tuple[str, ...] | None) -> list[str]:
    return [field for field in safe_text_list(values) if field in QUALITY_METADATA_FIELDS]


def _artifact_summary(value: dict[str, Any] | None) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    return {
        "status": safe_text(payload.get("status")).strip(),
        "source": safe_text(payload.get("source")).strip(),
        "fields": _quality_fields(payload.get("fields")),
    }


def _row_to_review(row: sqlite3.Row, *, event_count: int) -> dict[str, Any]:
    decision = safe_text(row["decision"]).strip().lower()
    try:
        missing_fields = json.loads(row["missing_quality_fields_json"])
    except (TypeError, ValueError, json.JSONDecodeError):
        missing_fields = []
    try:
        artifact_summary = json.loads(row["artifact_quality_summary_json"])
    except (TypeError, ValueError, json.JSONDecodeError):
        artifact_summary = {}
    return {
        "status": decision or "pending",
        "decision": decision,
        "decision_label": REVIEW_DECISION_LABELS.get(decision, decision),
        "reviewer_label": safe_text(row["reviewer_label"]).strip(),
        "note": safe_text(row["note"]),
        "reviewed_at": safe_text(row["created_at"]).strip(),
        "event_count": max(0, int(event_count or 0)),
        "report_quality_revision": safe_text(row["report_quality_revision"]).strip(),
        "missing_quality_fields": _quality_fields(missing_fields),
        "artifact_quality_summary": _artifact_summary(artifact_summary),
    }


__all__ = [
    "QUALITY_REVIEW_DB_PATH",
    "REVIEW_DECISION_LABELS",
    "SCHEMA_VERSION",
    "VALID_REVIEW_DECISIONS",
    "list_latest_reviews",
    "pending_review",
    "record_review",
    "reset_report_quality_review_store_for_tests",
]
