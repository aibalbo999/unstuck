"""AI Agent review gate for decision-grade report certification."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from data_trust import data_snapshot_filename_for_report


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
    """Return path to the .review.json sidecar file for a report."""
    base = report_filename.replace(".html", "").replace(".md", "")
    return os.path.join(output_dir, f"{base}.review.json")


def load_review_record(report_filename: str, output_dir: str) -> dict:
    """Load existing review record, or return empty dict if not found."""
    path = _review_data_path(report_filename, output_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        return record if isinstance(record, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_review_record(report_filename: str, output_dir: str, record: dict) -> bool:
    """Save review record to sidecar file."""
    path = _review_data_path(report_filename, output_dir)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def get_review_status(report_filename: str, output_dir: str) -> dict:
    """Return current review status for a report."""
    record = load_review_record(report_filename, output_dir)
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
        "schema_version": 1,
    }
    if raw_agent_outputs:
        record["raw_agent_outputs"] = raw_agent_outputs
    save_review_record(report_filename, output_dir, record)
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


def delete_review_record(report_filename: str, output_dir: str) -> bool:
    """Delete review sidecar when report is deleted."""
    path = _review_data_path(report_filename, output_dir)
    try:
        if os.path.exists(path):
            os.remove(path)
        return True
    except OSError:
        return False
