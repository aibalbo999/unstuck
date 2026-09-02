"""AI Agent review gate for decision-grade report certification."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from report_history_storage import load_storage_item, storage_for_existing_output_dir
from report_paths import report_storage_candidates_for_filename, report_review_filename_for_report
from storage.report_storage import ReportStorage


REVIEW_CONTENT_TYPE = "application/json"


class ReviewVerdict(str, Enum):
    PENDING = "pending_review"        # 剛生成，等待 AI 審閱
    AI_REVIEWING = "ai_reviewing"     # AI 審閱進行中
    APPROVED = "approved"             # AI 審閱通過 → 決策級
    CAUTION = "caution"               # AI 審閱有保留 → 可參考但需額外注意
    REJECTED = "rejected"             # AI 審閱發現重大問題 → 不建議使用


REVIEW_VERDICT_LABELS: dict[str, str] = {
    ReviewVerdict.PENDING:     "等待審閱",
    ReviewVerdict.AI_REVIEWING: "審閱中",
    ReviewVerdict.APPROVED:    "✅ 決策級",
    ReviewVerdict.CAUTION:     "⚠️ 審閱有保留",
    ReviewVerdict.REJECTED:    "❌ 不建議使用",
}


def _review_data_path(report_filename: str, output_dir: str) -> str:
    """Return the legacy flat path for a .review.json sidecar."""
    return os.path.join(output_dir, report_review_filename_for_report(report_filename))


def _decode_review_record(content: bytes) -> dict:
    try:
        record = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return record if isinstance(record, dict) else {}


def load_review_record(report_filename: str, output_dir: str, storage: ReportStorage | None = None) -> dict:
    """Load existing review record, or return empty dict if not found."""
    content_storage = storage_for_existing_output_dir(output_dir, storage)
    if content_storage is not None:
        item = load_storage_item(content_storage, report_filename, kind="review")
        if item is not None:
            return _decode_review_record(item.content)
    path = _review_data_path(report_filename, output_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        return record if isinstance(record, dict) else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def save_review_record(
    report_filename: str,
    output_dir: str,
    record: dict,
    storage: ReportStorage | None = None,
) -> bool:
    """Save review record to sidecar file."""
    content_storage = storage_for_existing_output_dir(output_dir, storage)
    if content_storage is not None:
        key = report_storage_candidates_for_filename(report_filename, kind="review")[0]
        try:
            content_storage.save_report(
                key,
                json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8"),
                content_type=REVIEW_CONTENT_TYPE,
            )
            return True
        except (OSError, ValueError):
            return False
    path = _review_data_path(report_filename, output_dir)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def get_review_status(report_filename: str, output_dir: str, storage: ReportStorage | None = None) -> dict:
    """Return current review status for a report."""
    record = load_review_record(report_filename, output_dir, storage=storage)
    verdict = record.get("verdict", ReviewVerdict.PENDING)
    return {
        "verdict": verdict,
        "verdict_label": REVIEW_VERDICT_LABELS.get(verdict, verdict),
        "is_decision_grade": verdict == ReviewVerdict.APPROVED,
        "reviewed_at": record.get("reviewed_at"),
        "review_summary": record.get("review_summary", ""),
        "critical_issues": record.get("critical_issues", []),
        "warnings": record.get("warnings", []),
        "review_agents_used": record.get("review_agents_used", []),
        "confidence_adjustment": record.get("confidence_adjustment", 0),
        "evidence_exit_gate": record.get("evidence_exit_gate", {}),
    }


def write_ai_review_result(
    report_filename: str,
    output_dir: str,
    *,
    verdict: str,
    review_summary: str,
    critical_issues: list[str],
    warnings: list[str],
    review_agents_used: list[str],
    confidence_adjustment: int = 0,
    raw_agent_outputs: Optional[dict] = None,
    evidence_exit_gate: Optional[dict] = None,
    storage: ReportStorage | None = None,
) -> dict:
    """Write AI review result to sidecar file."""
    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "report_filename": report_filename,
        "verdict": verdict,
        "verdict_label": REVIEW_VERDICT_LABELS.get(verdict, verdict),
        "reviewed_at": now_iso,
        "review_summary": review_summary,
        "critical_issues": critical_issues[:10],
        "warnings": warnings[:10],
        "review_agents_used": review_agents_used,
        "confidence_adjustment": confidence_adjustment,
        "evidence_exit_gate": evidence_exit_gate or {},
        "schema_version": 1,
    }
    if raw_agent_outputs:
        record["raw_agent_outputs"] = raw_agent_outputs
    save_review_record(report_filename, output_dir, record, storage=storage)
    return record


def determine_verdict(
    critical_issues: list[str],
    warnings: list[str],
    original_audit_status: str,
) -> str:
    """Determine final verdict based on review findings."""
    if len(critical_issues) >= 3:
        return ReviewVerdict.REJECTED
    if critical_issues or (len(warnings) >= 4):
        return ReviewVerdict.CAUTION
    if original_audit_status == "needs_attention":
        return ReviewVerdict.CAUTION
    return ReviewVerdict.APPROVED


def delete_review_record(
    report_filename: str,
    output_dir: str,
    storage: ReportStorage | None = None,
) -> bool:
    """Delete review sidecars when report is deleted."""
    content_storage = storage_for_existing_output_dir(output_dir, storage)
    if content_storage is not None:
        try:
            for key in report_storage_candidates_for_filename(report_filename, kind="review"):
                content_storage.delete_report(key)
        except (OSError, ValueError):
            return False
    path = _review_data_path(report_filename, output_dir)
    try:
        if os.path.exists(path):
            os.remove(path)
        return True
    except OSError:
        return False
