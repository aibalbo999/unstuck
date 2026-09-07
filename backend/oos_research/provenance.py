"""Time and provenance checks for frozen research candidates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def parse_timestamp(value: Any, *, field: str = "timestamp") -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be an offset-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def verify_time_chain(values: Mapping[str, Any]) -> list[str]:
    """Return stable reason codes; no timestamp is inferred from mtime."""
    required = ("analysis_input_cutoff", "conclusion_generated_at", "report_available_at")
    parsed: dict[str, datetime] = {}
    reasons: list[str] = []
    for field in required:
        try:
            parsed[field] = parse_timestamp(values.get(field), field=field)
        except ValueError:
            reasons.append(f"missing_or_invalid_{field}")
    first_available = values.get("input_first_available_at")
    try:
        first = parse_timestamp(first_available, field="input_first_available_at")
    except ValueError:
        first = None
        reasons.append("missing_input_first_available_at")
    if not reasons and first and not (first <= parsed["analysis_input_cutoff"] <= parsed["conclusion_generated_at"] <= parsed["report_available_at"]):
        reasons.append("timestamp_order_invalid")
    return reasons


def verify_seal(*, study_kind: str, report_available_at: Any, sealed_at: Any, first_session_date: str | None) -> list[str]:
    reasons: list[str] = []
    try:
        available = parse_timestamp(report_available_at, field="report_available_at")
        sealed = parse_timestamp(sealed_at, field="sealed_at")
    except ValueError:
        return ["missing_or_invalid_seal_receipt"]
    if study_kind == "prospective":
        if not first_session_date:
            reasons.append("missing_first_session")
        else:
            try:
                first_session = datetime.fromisoformat(first_session_date).date()
                if sealed.date() >= first_session:
                    reasons.append("late_seal")
            except ValueError:
                reasons.append("invalid_first_session")
        if sealed < available:
            reasons.append("seal_before_report_available")
    return reasons


def classify_study_kind(study_kind: str, *, evidence: Mapping[str, Any] | None = None) -> str:
    """Never upgrade retrospective/synthetic data to prospective."""
    if study_kind not in {"synthetic_validation", "retrospective_replay", "prospective"}:
        raise ValueError("unknown study kind")
    if study_kind != "prospective":
        return study_kind
    evidence = evidence or {}
    if not evidence.get("external_registration_receipt"):
        return "prospective_unverified"
    return "prospective"
