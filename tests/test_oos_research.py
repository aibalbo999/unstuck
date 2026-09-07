from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from oos_research.admission import evaluate_candidate
from oos_research.calendar import calendar_digest, first_session_after, validate_sessions
from oos_research.canonical import canonical_bytes, content_hash, sha256_bytes
from oos_research.dataset import validate_dataset
from oos_research.evaluation import make_evaluation, select_latest_revisions, validate_evaluation
from oos_research.inventory import validate_inventory
from oos_research.manifest import build_manifest, manifest_hash, validate_manifest
from oos_research.policies import DEFAULT_POLICIES, validate_policies
from oos_research.prediction import evaluate_a_horizon, evaluate_prediction_oos
from oos_research.provenance import classify_study_kind, verify_seal, verify_time_chain
from oos_research.records import make_record, validate_record
from oos_research.store import StoreError, StudyStore
from oos_research.summary import summarize, summary_markdown
from oos_research.trades import evaluate_trade_oos
from oos_research.cli import run_replay


def _manifest(study_id="synthetic-four-mode"):
    return build_manifest(
        schema_version="oos.manifest.v1", study_id=study_id, study_kind="synthetic_validation",
        registered_at="2026-09-07T00:00:00Z", timezone="Asia/Taipei",
        selection_period={"start": "2025-01-01", "end": "2025-12-31"},
        ticker_universe=["2330"], pipelines=["v1", "v2", "v3", "v4"],
        horizons={"v1": [3, 6, 12], "v2": [5], "v3": [5], "v4": [5, 10]},
        policies=dict(DEFAULT_POLICIES), evaluator_version="oos.evaluator.v1",
    )


def _artifact(name, content):
    raw = content.encode()
    return {"content": content, "sha256": sha256_bytes(raw)}


def _candidate(pipeline="v1", *, available="2025-01-02T09:00:00+08:00", sealed="2025-01-02T09:30:00+08:00"):
    quality = {"score": 80, "status": "sufficient"}
    report = {
        "ticker": "2330", "pipeline_id": pipeline, "prompt_fingerprint": "a" * 64,
        "code_commit": "abc123", "code_dirty": False, "model_id": "model-x",
        "quality_metadata": quality, "quality_metadata_hash": content_hash(quality),
        "analysis_input_cutoff": "2025-01-01T18:00:00+08:00",
        "input_first_available_at": "2025-01-01T17:00:00+08:00",
        "conclusion_generated_at": "2025-01-02T08:00:00+08:00", "report_available_at": available,
        "source_publication_at": "2025-01-01T16:00:00+08:00", "data_snapshot_hash": "b" * 64,
    }
    if pipeline == "v1":
        report.update({"recommendation": "買入", "target_price": 110})
    elif pipeline == "v2":
        report.update({"direction": "Long", "plan": {"entry_zone": "100-102", "target_price": "110", "stop_loss": "95", "horizon_trading_days": 5, "observation_reason": ""}})
    elif pipeline == "v3":
        report.update({"direction": "Short", "plan": {"entry_zone": "100", "target_price": "90", "stop_loss": "105", "horizon_trading_days": 5, "observation_reason": ""}})
    else:
        report.update({"direction": "Long", "plan": {"entry_zone": "100", "target_price": "110", "stop_loss": "95", "observation_reason": ""}})
    return {
        "candidate_id": f"cand-{pipeline}", "sealed_at": sealed,
        "first_session_date": "2025-01-03",
        "report": report,
        "artifacts": {name: _artifact(name, f"{pipeline}-{name}") for name in ("html", "markdown", "snapshot", "parsed_plan")},
    }


def _dataset():
    sessions = ["2025-01-03", "2025-02-03", "2025-04-02", "2025-07-02", "2026-01-02"]
    rows = [
        {"date": d, "open": 100 + i, "high": 110 + i, "low": 95 + i, "close": 105 + i,
         "complete": True, "completed_at": f"{d}T06:00:00Z"} for i, d in enumerate(sessions)
    ]
    return {"schema_version": "oos.dataset.v1", "provider": "fixture", "timezone": "Asia/Taipei",
            "as_of": "2026-01-03T00:00:00Z", "price_policy": "raw",
            "corporate_action_policy": "explicit_unprocessed_allowed", "calendar": sessions, "bars": {"2330": rows}}


def test_oos_01_root_is_explicit_and_safe(tmp_path):
    with pytest.raises(StoreError):
        StudyStore("", study_id="x")
    with pytest.raises(StoreError):
        StudyStore("/", study_id="x")
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "target", target_is_directory=False)
    with pytest.raises(StoreError):
        StudyStore(link, study_id="x")


def test_oos_02_manifest_record_and_store_are_immutable(tmp_path):
    manifest = _manifest()
    validate_manifest(manifest)
    assert manifest_hash(manifest) == manifest["manifest_sha256"]
    with pytest.raises(ValueError):
        build_manifest(**{**manifest, "policies": {"price_policy": "adjusted"}})
    record = make_record("candidate", "c1", {"x": 1}, created_at="2026-09-07T00:00:00Z")
    validate_record(record)
    tampered = {**record, "payload": {"x": 2}}
    with pytest.raises(ValueError):
        validate_record(tampered)
    store = StudyStore(tmp_path / "study", study_id=manifest["study_id"])
    store.register_manifest(manifest)
    store.put_record(record)
    with pytest.raises(StoreError):
        store.put_record({**record, "payload": {"x": 2}, "payload_sha256": content_hash({"x": 2})})
    assert set(store.list_records()) == {"manifest", "c1"}


def test_oos_03_admission_keeps_failures_in_denominator():
    candidate = _candidate()
    assert evaluate_candidate(candidate, study_kind="synthetic_validation")["status"] == "admitted"
    bad = _candidate()
    bad["artifacts"]["html"]["content"] = "changed"
    assert evaluate_candidate(bad, study_kind="synthetic_validation")["status"] == "integrity_failed"
    missing = _candidate()
    missing["report"] = None
    assert evaluate_candidate(missing, study_kind="synthetic_validation")["status"] == "missing_report"


def test_oos_04_time_and_study_classification_never_upgrade():
    candidate = _candidate()
    assert verify_time_chain(candidate["report"]) == []
    assert verify_seal(study_kind="prospective", report_available_at="2025-01-02T09:00:00+08:00",
                       sealed_at="2025-01-03T09:00:00+08:00", first_session_date="2025-01-03") == ["late_seal"]
    assert classify_study_kind("retrospective_replay") == "retrospective_replay"
    assert classify_study_kind("prospective") == "prospective_unverified"


def test_oos_05_a_calendar_and_strict_prices():
    assert validate_sessions(["2025-01-01", "2025-01-02"])
    assert first_session_after(["2025-01-02", "2025-01-03"], date(2025, 1, 2)) == date(2025, 1, 3)
    assert evaluate_prediction_oos(recommendation="未知", initial_price=100, actual_price=110)["outcome"] is None
    assert evaluate_prediction_oos(recommendation="買入", initial_price=True, actual_price=110, target_price=120)["reason"] == "invalid_price_input"
    result = evaluate_a_horizon(report_available_date=date(2025, 1, 2), sessions=[date(2025, 1, 3), date(2025, 4, 2)],
                                closes={"2025-01-03": 100, "2025-04-02": 120}, recommendation="買入", target_price=110, horizon_months=3)
    assert result["outcome"] == "hit"


def test_oos_06_b_c_d_path_and_unknown_direction():
    bars = [{"date": "2025-01-03", "open": 100, "high": 111, "low": 99, "close": 105},
            {"date": "2025-01-06", "open": 105, "high": 112, "low": 104, "close": 110}]
    neutral = evaluate_trade_oos(bars=bars, generated_date=date(2025, 1, 2), as_of=date(2025, 1, 6), direction="Neutral",
                                 plan={"observation_reason": "等待財報"}, horizon_trading_days=1)
    assert neutral["status"] == "no_trade"
    assert evaluate_trade_oos(bars=bars, generated_date=date(2025, 1, 2), as_of=date(2025, 1, 6), direction="Unknown",
                              plan={}, horizon_trading_days=1)["status"] == "insufficient_data"
    ambiguous = evaluate_trade_oos(bars=[{"date": "2025-01-03", "open": 100, "high": 110, "low": 90, "close": 100}],
                                    generated_date=date(2025, 1, 2), as_of=date(2025, 1, 3), direction="Long",
                                    plan={"entry_zone": "100", "target_price": "110", "stop_loss": "90"}, horizon_trading_days=1)
    assert ambiguous["status"] == "ambiguous"


def test_oos_07_dataset_rejects_incomplete_or_mixed_data():
    dataset = _dataset()
    assert validate_dataset(dataset)
    bad = json.loads(json.dumps(dataset))
    bad["bars"]["2330"][0]["complete"] = False
    with pytest.raises(ValueError):
        validate_dataset(bad)
    bad = json.loads(json.dumps(dataset))
    bad["bars"]["2330"].append(dict(bad["bars"]["2330"][0]))
    with pytest.raises(ValueError):
        validate_dataset(bad)


def test_oos_08_evaluation_identity_is_deterministic_and_revisioned():
    kwargs = dict(study_id="s", candidate_id="c", report_bundle_hash="a" * 64, horizon_unit="months", horizon_value=3,
                  evaluator_version="v1", dataset_hash="b" * 64, calendar_hash="c" * 64, policy_hash="d" * 64, as_of="2026-01-01")
    one = make_evaluation(**kwargs, result={"pipeline_id": "v1", "outcome": "hit"})
    two = make_evaluation(**kwargs, result={"pipeline_id": "v1", "outcome": "hit"})
    assert one["deterministic_sha256"] == two["deterministic_sha256"]
    validate_evaluation(one)
    mature = make_evaluation(**kwargs, result={"pipeline_id": "v1", "outcome": "hit"}, revision=2)
    assert len(select_latest_revisions([one, mature])) == 1


def test_oos_09_summary_preserves_denominators_and_nulls():
    candidate = {"candidate_id": "c", "ticker": "2330", "report_bundle_hash": "r", "admission_status": "admitted"}
    evaluation = make_evaluation(study_id="s", candidate_id="c", report_bundle_hash="r", horizon_unit="months", horizon_value=3,
                                 evaluator_version="v1", dataset_hash="d", calendar_hash="c", policy_hash="p", as_of="2026-01-01",
                                 result={"pipeline_id": "v1", "status": "pending", "outcome": None})
    summary = summarize(candidates=[candidate], evaluations=[evaluation])
    group = summary["groups"]["v1:months:3"]
    assert group["hit_rate_pct"] is None and group["average_gross_roi_pct"] is None and group["total"] == 1
    assert "| Group | Total | Scored |" in summary_markdown(summary)


def test_oos_10_offline_four_mode_fixture_has_explicit_hashes(tmp_path):
    manifest = _manifest()
    inventory = {"coverage_status": "closed", "candidates": [_candidate(mode) for mode in ("v1", "v2", "v3", "v4")]}
    validate_inventory(inventory)
    dataset = _dataset()
    validate_dataset(dataset)
    policy_hash = validate_policies(manifest["policies"])
    assert policy_hash and calendar_digest(dataset["calendar"])
    store = StudyStore(tmp_path / "replay", study_id=manifest["study_id"])
    store.register_manifest(manifest)
    for candidate in inventory["candidates"]:
        admission = evaluate_candidate(candidate, study_kind=manifest["study_kind"])
        assert admission["status"] == "admitted"
        store.put_record(make_record("admission", candidate["candidate_id"], admission))
    assert len(store.list_records()) == 5


def test_oos_10_cli_replay_writes_complete_bundle(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    inventory_path = tmp_path / "inventory.json"
    dataset_path = tmp_path / "dataset.json"
    manifest_path.write_text(json.dumps(_manifest(), ensure_ascii=False), encoding="utf-8")
    inventory_path.write_text(json.dumps({"coverage_status": "closed", "candidates": [_candidate("v1")]}, ensure_ascii=False), encoding="utf-8")
    dataset_path.write_text(json.dumps(_dataset(), ensure_ascii=False), encoding="utf-8")
    output = run_replay(root=str(tmp_path / "study"), manifest_input=str(manifest_path),
                        inventory_input=str(inventory_path), dataset_input=str(dataset_path))
    assert output["summary"]["candidate_total"] == 1
    assert output["summary"]["evaluation_total"] == 3
