from __future__ import annotations

import json
import hashlib
import os
from datetime import datetime
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

from oos_research.canonical import content_hash
from oos_research.checkpoint_preflight import inspect_checkpoint_cutoff
from oos_research.records import make_record
from oos_research.store import StudyStore
from oos_research.summary import summary_markdown


ROOT = Path(__file__).resolve().parents[1]
AT_DATA_READY_BOUNDARY = datetime(2026, 9, 15, 15, 5, tzinfo=ZoneInfo("Asia/Taipei"))


def test_preflight_blocks_capture_before_market_data_ready_boundary(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    study = tmp_path / "study"
    StudyStore(study, study_id="study")

    result = inspect_checkpoint_cutoff(
        checkpoints_root=checkpoints,
        study_root=study,
        study_id="study",
        cutoff_session="2026-09-15",
        current_time=datetime(2026, 9, 15, 15, 4, 59, tzinfo=ZoneInfo("Asia/Taipei")),
    )

    assert result["status"] == "not_due"
    assert result["should_capture"] is False
    assert result["capture_not_before"] == "2026-09-15T15:05:00+08:00"


def _dataset(cutoff: str = "2026-09-15") -> dict:
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
    return dataset


def _write_complete_checkpoint(tmp_path: Path, *, run_id: str = "2026-09-15T150500+0800-r1"):
    checkpoints = tmp_path / "checkpoints"
    checkpoint = checkpoints / run_id
    checkpoint.mkdir(parents=True)
    dataset = _dataset()
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
    return checkpoints, tmp_path / "study", dataset["dataset_sha256"]


def test_preflight_detects_complete_cutoff_and_blocks_recapture(tmp_path):
    checkpoints, study, dataset_hash = _write_complete_checkpoint(tmp_path)

    result = inspect_checkpoint_cutoff(
        checkpoints_root=checkpoints,
        study_root=study,
        study_id="study",
        cutoff_session="2026-09-15",
        current_time=AT_DATA_READY_BOUNDARY,
    )

    assert result == {
        "schema_version": "oos.checkpoint-preflight.v1",
        "cutoff_session": "2026-09-15",
        "status": "complete",
        "should_capture": False,
        "complete_count": 1,
        "incomplete_count": 0,
        "checkpoints": [{
            "run_id": "2026-09-15T150500+0800-r1",
            "status": "complete",
            "dataset_hash": dataset_hash,
            "reason_codes": [],
        }],
    }


def test_preflight_allows_capture_when_cutoff_has_no_revision(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    study = tmp_path / "study"
    StudyStore(study, study_id="study")

    result = inspect_checkpoint_cutoff(
        checkpoints_root=checkpoints,
        study_root=study,
        study_id="study",
        cutoff_session="2026-09-15",
        current_time=AT_DATA_READY_BOUNDARY,
    )

    assert result["status"] == "not_found"
    assert result["should_capture"] is True
    assert result["checkpoints"] == []


def test_preflight_preserves_incomplete_revision_and_allows_new_revision(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    checkpoint = checkpoints / "2026-09-15T150500+0800-r1"
    checkpoint.mkdir(parents=True)
    dataset = _dataset()
    (checkpoint / "dataset.json").write_text(json.dumps(dataset), encoding="utf-8")
    study = tmp_path / "study"
    StudyStore(study, study_id="study")

    result = inspect_checkpoint_cutoff(
        checkpoints_root=checkpoints,
        study_root=study,
        study_id="study",
        cutoff_session="2026-09-15",
        current_time=AT_DATA_READY_BOUNDARY,
    )

    assert result["status"] == "incomplete"
    assert result["should_capture"] is True
    assert result["checkpoints"][0]["reason_codes"] == [
        "checkpoint_record_missing_or_invalid",
        "replay_missing_or_unsafe",
        "summary_missing_or_unsafe",
    ]


def test_preflight_does_not_follow_symlink_checkpoint_or_evidence(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (checkpoints / "2026-09-15T150500+0800-r1").symlink_to(outside, target_is_directory=True)
    complete_root, study, _ = _write_complete_checkpoint(
        tmp_path,
        run_id="2026-09-15T150600+0800-r2",
    )
    summary = complete_root / "2026-09-15T150600+0800-r2" / "summary.md"
    summary.unlink()
    summary.symlink_to(tmp_path / "outside-summary.md")

    result = inspect_checkpoint_cutoff(
        checkpoints_root=checkpoints,
        study_root=study,
        study_id="study",
        cutoff_session="2026-09-15",
        current_time=AT_DATA_READY_BOUNDARY,
    )

    assert result["status"] == "incomplete"
    assert result["should_capture"] is True
    assert result["checkpoints"][0]["reason_codes"] == ["unsafe_checkpoint_entry"]
    assert result["checkpoints"][1]["reason_codes"] == ["summary_missing_or_unsafe"]


def test_preflight_rejects_replay_identity_mismatch(tmp_path):
    checkpoints, study, _ = _write_complete_checkpoint(tmp_path)
    replay_path = checkpoints / "2026-09-15T150500+0800-r1" / "replay-result.json"
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    replay["dataset_hash"] = "0" * 64
    replay_path.write_text(json.dumps(replay), encoding="utf-8")

    result = inspect_checkpoint_cutoff(
        checkpoints_root=checkpoints,
        study_root=study,
        study_id="study",
        cutoff_session="2026-09-15",
        current_time=AT_DATA_READY_BOUNDARY,
    )

    assert result["status"] == "incomplete"
    assert result["should_capture"] is True
    assert result["checkpoints"][0]["reason_codes"] == ["replay_identity_mismatch"]


def test_preflight_rejects_dataset_hash_and_summary_mismatches(tmp_path):
    checkpoints, study, _ = _write_complete_checkpoint(tmp_path)
    checkpoint = checkpoints / "2026-09-15T150500+0800-r1"
    dataset_path = checkpoint / "dataset.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    dataset["dataset_sha256"] = "0" * 64
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")
    (checkpoint / "summary.md").write_text("not the replay summary\n", encoding="utf-8")

    result = inspect_checkpoint_cutoff(
        checkpoints_root=checkpoints,
        study_root=study,
        study_id="study",
        cutoff_session="2026-09-15",
        current_time=AT_DATA_READY_BOUNDARY,
    )

    assert result["status"] == "incomplete"
    assert result["should_capture"] is True
    assert result["checkpoints"][0]["reason_codes"] == [
        "dataset_invalid",
        "replay_identity_mismatch",
        "summary_mismatch",
    ]


def test_preflight_stops_when_same_cutoff_has_two_complete_revisions(tmp_path):
    checkpoints, study, _ = _write_complete_checkpoint(tmp_path)
    _write_complete_checkpoint(tmp_path, run_id="2026-09-15T150600+0800-r2")

    result = inspect_checkpoint_cutoff(
        checkpoints_root=checkpoints,
        study_root=study,
        study_id="study",
        cutoff_session="2026-09-15",
    )

    assert result["status"] == "conflict"
    assert result["should_capture"] is False
    assert result["complete_count"] == 2


def _tree_fingerprint(root: Path) -> list[tuple[str, int, str]]:
    rows = []
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        info = path.lstat()
        if path.is_symlink():
            content = os.readlink(path)
        elif path.is_file():
            content = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            content = ""
        rows.append((relative, info.st_mode, content))
    return rows


def test_preflight_is_read_only(tmp_path):
    checkpoints, study, _ = _write_complete_checkpoint(tmp_path)
    before = _tree_fingerprint(tmp_path)

    inspect_checkpoint_cutoff(
        checkpoints_root=checkpoints,
        study_root=study,
        study_id="study",
        cutoff_session="2026-09-15",
    )

    assert _tree_fingerprint(tmp_path) == before


def test_preflight_cli_prints_machine_readable_result(tmp_path):
    checkpoints, study, _ = _write_complete_checkpoint(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/inspect_oos_maturity_checkpoints.py"),
            "--checkpoints-root",
            str(checkpoints),
            "--study-root",
            str(study),
            "--study-id",
            "study",
            "--cutoff-session",
            "2026-09-15",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert json.loads(completed.stdout)["status"] == "complete"


def test_preflight_cli_fails_closed_on_conflicting_complete_revisions(tmp_path):
    checkpoints, study, _ = _write_complete_checkpoint(tmp_path)
    _write_complete_checkpoint(tmp_path, run_id="2026-09-15T150600+0800-r2")

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/inspect_oos_maturity_checkpoints.py"),
            "--checkpoints-root",
            str(checkpoints),
            "--study-root",
            str(study),
            "--study-id",
            "study",
            "--cutoff-session",
            "2026-09-15",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert json.loads(completed.stdout)["status"] == "conflict"
