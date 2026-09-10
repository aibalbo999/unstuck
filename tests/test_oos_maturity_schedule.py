from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

import pytest

from oos_research.canonical import content_hash
from oos_research.maturity_schedule import plan_next_checkpoint, validate_maturity_schedule
from oos_research.records import make_record
from oos_research.store import StudyStore
from oos_research.summary import summary_markdown


ROOT = Path(__file__).resolve().parents[1]
FORMAL_SCHEDULE = ROOT / "docs/oos-maturity-schedule-2026-09-10.json"


def _schedule() -> dict:
    schedule = {
        "schema_version": "oos.maturity-schedule.v1",
        "study_id": "study",
        "timezone": "Asia/Taipei",
        "capture_local_time": "15:05:00",
        "fixed_candidate_denominator": 28,
        "inventory_sha256": "a" * 64,
        "known_report_horizon_total": 14,
        "session_calendar_sha256": "b" * 64,
        "checkpoints": [
            {
                "cutoff_session": "2026-09-15",
                "newly_mature_report_horizons": 7,
                "scope": "first session 2026-09-09; v2/v3/v4 5 trading sessions",
            },
            {
                "cutoff_session": "2026-09-16",
                "newly_mature_report_horizons": 7,
                "scope": "first session 2026-09-10; v2/v3/v4 5 trading sessions",
            },
        ],
        "deferred": [
            {
                "pipeline_id": "v1",
                "horizon_months": [6, 12],
                "reason_code": "official_2027_session_calendar_required",
            },
        ],
    }
    schedule["schedule_sha256"] = content_hash(schedule)
    return schedule


def test_schedule_requires_fixed_inventory_and_calendar_identities():
    schedule = _schedule()
    schedule.pop("inventory_sha256")
    schedule["schedule_sha256"] = content_hash({
        key: value for key, value in schedule.items() if key != "schedule_sha256"
    })

    with pytest.raises(ValueError, match="incomplete"):
        validate_maturity_schedule(schedule)


def _write_complete_checkpoint(tmp_path: Path, *, cutoff: str, run_id: str) -> None:
    checkpoint = tmp_path / "checkpoints" / run_id
    checkpoint.mkdir(parents=True, exist_ok=False)
    dataset = {
        "schema_version": "oos.dataset.v1",
        "provider": "TWSE_STOCK_DAY+TPEx_tradingStock",
        "timezone": "Asia/Taipei",
        "as_of": f"{cutoff}T07:05:00Z",
        "price_policy": "raw",
        "corporate_action_policy": "explicit_unprocessed_allowed",
        "calendar": [cutoff],
        "bars": {},
        "cutoff_session": cutoff,
    }
    dataset["dataset_sha256"] = content_hash(dataset)
    summary = {
        "schema_version": "oos.summary.v1",
        "cutoff": dataset["as_of"],
        "candidate_total": 28,
        "evaluation_total": 0,
        "groups": {},
    }
    replay = {
        "study_id": "study",
        "dataset_hash": dataset["dataset_sha256"],
        "summary": summary,
    }
    (checkpoint / "dataset.json").write_text(json.dumps(dataset), encoding="utf-8")
    (checkpoint / "replay-result.json").write_text(json.dumps(replay), encoding="utf-8")
    (checkpoint / "summary.md").write_text(summary_markdown(summary), encoding="utf-8")
    store = StudyStore(tmp_path / "study", study_id="study")
    store.put_record(make_record(
        "checkpoint",
        f"checkpoint-{dataset['dataset_sha256']}",
        {"schema_version": "oos.checkpoint.v1", "dataset_hash": dataset["dataset_sha256"]},
        created_at=dataset["as_of"],
    ))


def test_plan_selects_earliest_due_unfinished_cutoff(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    study = tmp_path / "study"
    StudyStore(study, study_id="study")

    result = plan_next_checkpoint(
        schedule=_schedule(),
        checkpoints_root=checkpoints,
        study_root=study,
        study_id="study",
        current_time=datetime(2026, 9, 16, 15, 5, tzinfo=ZoneInfo("Asia/Taipei")),
    )

    assert result == {
        "schema_version": "oos.maturity-plan.v1",
        "study_id": "study",
        "status": "ready",
        "should_capture": True,
        "cutoff_session": "2026-09-15",
        "capture_not_before": "2026-09-15T15:05:00+08:00",
        "checkpoint_status": "not_found",
        "newly_mature_report_horizons": 7,
        "scope": "first session 2026-09-09; v2/v3/v4 5 trading sessions",
        "complete_cutoffs": [],
    }


def test_plan_waits_for_earliest_registered_cutoff(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    study = tmp_path / "study"
    StudyStore(study, study_id="study")

    result = plan_next_checkpoint(
        schedule=_schedule(),
        checkpoints_root=checkpoints,
        study_root=study,
        study_id="study",
        current_time=datetime(2026, 9, 15, 15, 4, 59, tzinfo=ZoneInfo("Asia/Taipei")),
    )

    assert result["status"] == "waiting"
    assert result["should_capture"] is False
    assert result["cutoff_session"] == "2026-09-15"
    assert result["capture_not_before"] == "2026-09-15T15:05:00+08:00"


def test_plan_advances_past_a_complete_cutoff(tmp_path):
    _write_complete_checkpoint(
        tmp_path,
        cutoff="2026-09-15",
        run_id="2026-09-15T150500+0800-r1",
    )

    result = plan_next_checkpoint(
        schedule=_schedule(),
        checkpoints_root=tmp_path / "checkpoints",
        study_root=tmp_path / "study",
        study_id="study",
        current_time=datetime(2026, 9, 16, 15, 5, tzinfo=ZoneInfo("Asia/Taipei")),
    )

    assert result["status"] == "ready"
    assert result["cutoff_session"] == "2026-09-16"
    assert result["checkpoint_status"] == "not_found"
    assert result["complete_cutoffs"] == ["2026-09-15"]


def test_plan_stops_on_any_conflicting_complete_cutoff(tmp_path):
    _write_complete_checkpoint(
        tmp_path,
        cutoff="2026-09-15",
        run_id="2026-09-15T150500+0800-r1",
    )
    _write_complete_checkpoint(
        tmp_path,
        cutoff="2026-09-15",
        run_id="2026-09-15T150600+0800-r2",
    )

    result = plan_next_checkpoint(
        schedule=_schedule(),
        checkpoints_root=tmp_path / "checkpoints",
        study_root=tmp_path / "study",
        study_id="study",
        current_time=datetime(2026, 9, 16, 15, 5, tzinfo=ZoneInfo("Asia/Taipei")),
    )

    assert result["status"] == "conflict"
    assert result["should_capture"] is False
    assert result["cutoff_session"] == "2026-09-15"


def test_plan_reports_schedule_exhaustion_without_inventing_deferred_dates(tmp_path):
    _write_complete_checkpoint(
        tmp_path,
        cutoff="2026-09-15",
        run_id="2026-09-15T150500+0800-r1",
    )
    _write_complete_checkpoint(
        tmp_path,
        cutoff="2026-09-16",
        run_id="2026-09-16T150500+0800-r1",
    )

    result = plan_next_checkpoint(
        schedule=_schedule(),
        checkpoints_root=tmp_path / "checkpoints",
        study_root=tmp_path / "study",
        study_id="study",
        current_time=datetime(2026, 9, 17, 15, 5, tzinfo=ZoneInfo("Asia/Taipei")),
    )

    assert result["status"] == "schedule_exhausted"
    assert result["should_capture"] is False
    assert result["complete_cutoffs"] == ["2026-09-15", "2026-09-16"]
    assert result["deferred"] == _schedule()["deferred"]


def test_schedule_hash_and_totals_are_fail_closed():
    tampered_hash = _schedule()
    tampered_hash["checkpoints"][0]["cutoff_session"] = "2026-09-14"
    tampered_total = _schedule()
    tampered_total["known_report_horizon_total"] = 15
    unordered = _schedule()
    unordered["checkpoints"].reverse()
    unordered["schedule_sha256"] = content_hash({
        key: value for key, value in unordered.items() if key != "schedule_sha256"
    })

    for schedule, message in (
        (tampered_hash, "hash mismatch"),
        (tampered_total, "total does not match"),
        (unordered, "unique and ordered"),
    ):
        try:
            validate_maturity_schedule(schedule)
        except ValueError as error:
            assert message in str(error)
        else:
            raise AssertionError("invalid maturity schedule was accepted")


def test_formal_schedule_pins_all_known_cutoffs_and_deferred_horizons():
    schedule = json.loads(FORMAL_SCHEDULE.read_text(encoding="utf-8"))

    assert validate_maturity_schedule(schedule) == (
        "deb484beae83b19438e6e12d3b21b0c467ba2fd9330c594341ee725e9841be43"
    )
    assert [entry["cutoff_session"] for entry in schedule["checkpoints"]] == [
        "2026-09-15",
        "2026-09-16",
        "2026-09-17",
        "2026-09-22",
        "2026-09-23",
        "2026-09-24",
        "2026-12-09",
        "2026-12-10",
    ]
    assert sum(entry["newly_mature_report_horizons"] for entry in schedule["checkpoints"]) == 33
    assert schedule["deferred"] == [{
        "pipeline_id": "v1",
        "horizon_months": [6, 12],
        "reason_code": "official_2027_session_calendar_required",
    }]


def test_schedule_cli_selects_from_pinned_machine_readable_schedule(tmp_path):
    schedule = _schedule()
    schedule_path = tmp_path / "schedule.json"
    schedule_path.write_text(json.dumps(schedule), encoding="utf-8")
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    study = tmp_path / "study"
    StudyStore(study, study_id="study")

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/plan_oos_maturity_checkpoint.py"),
            "--schedule",
            str(schedule_path),
            "--expected-schedule-sha256",
            schedule["schedule_sha256"],
            "--checkpoints-root",
            str(checkpoints),
            "--study-root",
            str(study),
            "--study-id",
            "study",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    result = json.loads(completed.stdout)
    assert result["status"] == "waiting"
    assert result["cutoff_session"] == "2026-09-15"


def test_schedule_cli_rejects_wrong_external_pin(tmp_path):
    schedule = _schedule()
    schedule_path = tmp_path / "schedule.json"
    schedule_path.write_text(json.dumps(schedule), encoding="utf-8")
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    study = tmp_path / "study"
    StudyStore(study, study_id="study")

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/plan_oos_maturity_checkpoint.py"),
            "--schedule",
            str(schedule_path),
            "--expected-schedule-sha256",
            "0" * 64,
            "--checkpoints-root",
            str(checkpoints),
            "--study-root",
            str(study),
            "--study-id",
            "study",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert json.loads(completed.stderr)["status"] == "error"
