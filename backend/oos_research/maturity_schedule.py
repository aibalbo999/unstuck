"""Deterministic scheduling for the registered OOS maturity checkpoints."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .canonical import content_hash
from .checkpoint_preflight import inspect_checkpoint_cutoff


_TIMEZONE_NAME = "Asia/Taipei"
_CAPTURE_LOCAL_TIME = "15:05:00"


def validate_maturity_schedule(schedule: Mapping[str, Any]) -> str:
    required = {
        "schema_version",
        "study_id",
        "timezone",
        "capture_local_time",
        "fixed_candidate_denominator",
        "inventory_sha256",
        "known_report_horizon_total",
        "session_calendar_sha256",
        "checkpoints",
        "deferred",
        "schedule_sha256",
    }
    if not isinstance(schedule, Mapping) or required - set(schedule):
        raise ValueError("maturity schedule is incomplete")
    if schedule["schema_version"] != "oos.maturity-schedule.v1":
        raise ValueError("maturity schedule schema is unsupported")
    if schedule["timezone"] != _TIMEZONE_NAME or schedule["capture_local_time"] != _CAPTURE_LOCAL_TIME:
        raise ValueError("maturity schedule market boundary is invalid")
    if not isinstance(schedule["study_id"], str) or not schedule["study_id"]:
        raise ValueError("maturity schedule study_id is invalid")
    for field in ("inventory_sha256", "session_calendar_sha256"):
        value = schedule[field]
        if not isinstance(value, str) or len(value) != 64 or any(
            character not in "0123456789abcdef" for character in value
        ):
            raise ValueError("maturity schedule evidence identity is invalid")
    denominator = schedule["fixed_candidate_denominator"]
    expected_total = schedule["known_report_horizon_total"]
    if isinstance(denominator, bool) or not isinstance(denominator, int) or denominator <= 0:
        raise ValueError("maturity schedule denominator is invalid")
    if isinstance(expected_total, bool) or not isinstance(expected_total, int) or expected_total <= 0:
        raise ValueError("maturity schedule total is invalid")
    checkpoints = schedule["checkpoints"]
    if not isinstance(checkpoints, list) or not checkpoints:
        raise ValueError("maturity schedule checkpoints are invalid")
    dates: list[str] = []
    actual_total = 0
    for entry in checkpoints:
        if not isinstance(entry, Mapping):
            raise ValueError("maturity schedule checkpoint is invalid")
        cutoff = entry.get("cutoff_session")
        try:
            parsed = date.fromisoformat(cutoff)
        except (TypeError, ValueError):
            raise ValueError("maturity schedule cutoff is invalid") from None
        if parsed.isoformat() != cutoff:
            raise ValueError("maturity schedule cutoff is invalid")
        count = entry.get("newly_mature_report_horizons")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError("maturity schedule checkpoint count is invalid")
        if not isinstance(entry.get("scope"), str) or not entry["scope"]:
            raise ValueError("maturity schedule checkpoint scope is invalid")
        dates.append(cutoff)
        actual_total += count
    if dates != sorted(set(dates)):
        raise ValueError("maturity schedule cutoffs must be unique and ordered")
    if actual_total != expected_total:
        raise ValueError("maturity schedule total does not match checkpoints")
    if not isinstance(schedule["deferred"], list):
        raise ValueError("maturity schedule deferred items are invalid")
    actual_hash = content_hash({key: value for key, value in schedule.items() if key != "schedule_sha256"})
    if schedule["schedule_sha256"] != actual_hash:
        raise ValueError("maturity schedule hash mismatch")
    return actual_hash


def _capture_not_before(cutoff_session: str) -> str:
    cutoff = date.fromisoformat(cutoff_session)
    hour, minute, second = (int(value) for value in _CAPTURE_LOCAL_TIME.split(":"))
    return datetime.combine(
        cutoff,
        time(hour, minute, second),
        ZoneInfo(_TIMEZONE_NAME),
    ).isoformat()


def _recommended_run_id(
    cutoff_session: str,
    inspection: Mapping[str, Any],
    observed_at: datetime,
) -> str:
    revisions = [
        int(checkpoint["run_id"].rsplit("-r", 1)[1])
        for checkpoint in inspection["checkpoints"]
    ]
    local_time = observed_at.astimezone(ZoneInfo(_TIMEZONE_NAME))
    return (
        f"{cutoff_session}T{local_time:%H%M%S}{local_time:%z}"
        f"-r{max(revisions, default=0) + 1}"
    )


def plan_next_checkpoint(
    *,
    schedule: Mapping[str, Any],
    checkpoints_root: str | Path,
    study_root: str | Path,
    study_id: str,
    current_time: datetime | None = None,
) -> dict[str, Any]:
    """Select the earliest registered cutoff that still needs a checkpoint."""
    validate_maturity_schedule(schedule)
    if schedule["study_id"] != study_id:
        raise ValueError("maturity schedule study_id does not match")
    observed_at = current_time or datetime.now(ZoneInfo(_TIMEZONE_NAME))
    inspections = [
        inspect_checkpoint_cutoff(
            checkpoints_root=checkpoints_root,
            study_root=study_root,
            study_id=study_id,
            cutoff_session=entry["cutoff_session"],
            current_time=observed_at,
        )
        for entry in schedule["checkpoints"]
    ]
    complete_cutoffs = [
        entry["cutoff_session"]
        for entry, inspection in zip(schedule["checkpoints"], inspections, strict=True)
        if inspection["status"] == "complete"
    ]
    for entry, inspection in zip(schedule["checkpoints"], inspections, strict=True):
        if inspection["status"] == "conflict":
            return {
                "schema_version": "oos.maturity-plan.v1",
                "study_id": study_id,
                "status": "conflict",
                "should_capture": False,
                "cutoff_session": entry["cutoff_session"],
                "checkpoint_status": "conflict",
                "complete_cutoffs": complete_cutoffs,
            }
    for entry, inspection in zip(schedule["checkpoints"], inspections, strict=True):
        if inspection["status"] == "complete":
            continue
        common = {
            "schema_version": "oos.maturity-plan.v1",
            "study_id": study_id,
            "cutoff_session": entry["cutoff_session"],
            "capture_not_before": _capture_not_before(entry["cutoff_session"]),
            "checkpoint_status": inspection["status"],
            "newly_mature_report_horizons": entry["newly_mature_report_horizons"],
            "scope": entry["scope"],
            "complete_cutoffs": complete_cutoffs,
        }
        if inspection["should_capture"]:
            return {
                **common,
                "status": "ready",
                "should_capture": True,
                "recommended_run_id": _recommended_run_id(
                    entry["cutoff_session"],
                    inspection,
                    observed_at,
                ),
            }
        if inspection["status"] == "not_due":
            return {**common, "status": "waiting", "should_capture": False}
        raise ValueError("maturity checkpoint inspection returned an unsafe decision")
    return {
        "schema_version": "oos.maturity-plan.v1",
        "study_id": study_id,
        "status": "schedule_exhausted",
        "should_capture": False,
        "complete_cutoffs": complete_cutoffs,
        "deferred": schedule["deferred"],
    }
