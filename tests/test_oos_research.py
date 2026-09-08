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
from oos_research.provenance import (
    classify_study_kind,
    exchange_date,
    verify_registration_receipt,
    verify_seal,
    verify_time_chain,
)
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
        "source_publication_at": "2025-01-01T16:00:00+08:00", "data_snapshot_hash": "",
    }
    if pipeline == "v1":
        report.update({"recommendation": "買入", "target_price": 110})
    elif pipeline == "v2":
        report.update({"direction": "Long", "plan": {"entry_zone": "100-102", "target_price": "110", "stop_loss": "95", "horizon_trading_days": 5, "observation_reason": ""}})
    elif pipeline == "v3":
        report.update({"direction": "Short", "plan": {"entry_zone": "100", "target_price": "90", "stop_loss": "105", "horizon_trading_days": 5, "observation_reason": ""}})
    else:
        report.update({"direction": "Long", "plan": {"entry_zone": "100", "target_price": "110", "stop_loss": "95", "observation_reason": ""}})
    snapshot = {"ticker": "2330", "pipeline": pipeline, "reproducibility_packet": {"data_snapshot_hash": ""}}
    snapshot_hash = content_hash({"ticker": "2330", "pipeline": pipeline, "reproducibility_packet": {}})
    snapshot["snapshot_hash"] = snapshot_hash
    snapshot["reproducibility_packet"]["data_snapshot_hash"] = snapshot_hash
    report["data_snapshot_hash"] = snapshot_hash
    artifacts = {name: _artifact(name, f"{pipeline}-{name}") for name in ("html", "markdown", "parsed_plan")}
    artifacts["snapshot"] = _artifact("snapshot", json.dumps(snapshot, sort_keys=True))
    return {
        "candidate_id": f"cand-{pipeline}", "sealed_at": sealed,
        "first_session_date": "2025-01-03",
        "report": report,
        "artifacts": artifacts,
    }


def _registration_evidence(manifest_sha256, *, observed_at="2025-01-01T00:00:00Z"):
    remote_evidence = f"{'c' * 40}\trefs/heads/prospective-study\n"
    return {"external_registration_receipt": {
        "schema_version": "oos.registration-receipt.v1",
        "source": "git_remote",
        "remote_url": "https://github.com/example/stock-agent.git",
        "ref": "refs/heads/prospective-study",
        "commit": "c" * 40,
        "observed_at": observed_at,
        "manifest_sha256": manifest_sha256,
        "remote_evidence": remote_evidence,
        "remote_evidence_sha256": hashlib.sha256(remote_evidence.encode()).hexdigest(),
    }}


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


def test_oos_store_rejects_symlinked_records_and_read_only_open_of_incomplete_layout(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(StoreError, match="layout"):
        StudyStore(empty, study_id="x", create=False)

    store = StudyStore(tmp_path / "study", study_id="x")
    target = tmp_path / "outside.json"
    target.write_text("{}")
    (store.records_dir / "linked.json").symlink_to(target)
    with pytest.raises(StoreError, match="malformed"):
        store.read_record("linked")


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
    assert exchange_date("2026-09-08T16:30:00Z", "Asia/Taipei").isoformat() == "2026-09-09"
    assert verify_seal(
        study_kind="prospective", report_available_at="2026-09-08T15:30:00Z",
        sealed_at="2026-09-08T16:30:00Z", first_session_date="2026-09-09",
        timezone_name="Asia/Taipei",
    ) == []
    assert verify_seal(
        study_kind="prospective", report_available_at="2026-09-08T15:30:00Z",
        sealed_at="2026-09-09T01:00:00Z", first_session_date="2026-09-09",
        timezone_name="Asia/Taipei",
    ) == ["late_seal"]
    assert classify_study_kind("retrospective_replay") == "retrospective_replay"
    assert classify_study_kind("prospective") == "prospective_unverified"
    assert classify_study_kind(
        "prospective", evidence={"external_registration_receipt": True}
    ) == "prospective_unverified"
    manifest_sha256 = "a" * 64
    evidence = _registration_evidence(manifest_sha256)
    assert verify_registration_receipt(evidence, manifest_sha256=manifest_sha256) == [
        "registration_time_not_externally_attested"
    ]
    assert classify_study_kind(
        "prospective", evidence=evidence, manifest_sha256=manifest_sha256
    ) == "prospective_unverified"
    assert set(verify_registration_receipt(
        evidence,
        manifest_sha256=manifest_sha256,
        analysis_input_cutoff="2024-12-31T23:59:59Z",
    )) == {
        "registration_after_analysis_input_cutoff",
        "registration_time_not_externally_attested",
    }
    assert "registration_manifest_hash_mismatch" in verify_registration_receipt(
        evidence, manifest_sha256="b" * 64
    )
    forged = json.loads(json.dumps(evidence))
    forged["external_registration_receipt"]["remote_evidence"] = (
        f"{'d' * 40}\trefs/heads/prospective-study\n"
    )
    assert "registration_evidence_hash_mismatch" in verify_registration_receipt(
        forged, manifest_sha256=manifest_sha256
    )
    malformed_url = json.loads(json.dumps(evidence))
    malformed_url["external_registration_receipt"]["remote_url"] = "https://["
    assert "invalid_registration_receipt_url" in verify_registration_receipt(
        malformed_url, manifest_sha256=manifest_sha256
    )


def test_prospective_admission_requires_receipt_bound_before_analysis():
    manifest_fields = dict(_manifest())
    manifest_fields.pop("manifest_sha256")
    manifest_fields["study_kind"] = "prospective"
    manifest = build_manifest(**manifest_fields)
    candidate = _candidate()

    missing = evaluate_candidate(
        candidate,
        study_kind="prospective",
        manifest_sha256=manifest["manifest_sha256"],
    )
    assert missing["status"] == "insufficient_provenance"
    assert "missing_or_invalid_external_registration_receipt" in missing["reason_codes"]

    captured_but_unattested = evaluate_candidate(
        candidate,
        study_kind="prospective",
        registration_evidence=_registration_evidence(manifest["manifest_sha256"]),
        manifest_sha256=manifest["manifest_sha256"],
    )
    assert captured_but_unattested["status"] == "insufficient_provenance"
    assert "registration_time_not_externally_attested" in captured_but_unattested["reason_codes"]

    late = evaluate_candidate(
        candidate,
        study_kind="prospective",
        registration_evidence=_registration_evidence(
            manifest["manifest_sha256"], observed_at="2025-01-02T00:00:00Z"
        ),
        manifest_sha256=manifest["manifest_sha256"],
    )
    assert "registration_after_analysis_input_cutoff" in late["reason_codes"]


def test_prospective_admission_rejects_placeholder_identity_and_late_publication():
    candidate = _candidate()
    candidate["report"]["source_publication_at"] = "2025-01-01T19:00:00+08:00"

    result = evaluate_candidate(candidate, study_kind="prospective", manifest_sha256="a" * 64)

    assert "invalid_code_commit" in result["reason_codes"]
    assert "source_publication_after_analysis_input_cutoff" in result["reason_codes"]
    assert "missing_analysis_input_hash" in result["reason_codes"]
    assert "missing_model_execution_receipt" in result["reason_codes"]


def test_prospective_admission_preserves_selection_and_registered_horizon_boundaries():
    candidate = _candidate("v2", available="2026-09-12T00:00:00+08:00")
    candidate["ticker"] = candidate["report"]["ticker"]
    candidate["pipeline_id"] = "v2"
    candidate["report"].update({
        "prompt_fingerprint": "a" * 64,
        "analysis_input_hash": "b" * 64,
        "data_snapshot_hash": "c" * 64,
        "model_route_policy_sha256": "d" * 64,
        "code_commit": "e" * 40,
        "model_executions": [{
            "agent_num": 16,
            "model_id": "model-x",
            "route_index": 0,
            "route_considered": ["model-x"],
            "provider_call_models": ["model-x"],
            "route_skipped": [],
            "failed_models": [],
            "fallback_used": False,
            "cache_hit": False,
        }],
        "model_revision_unknown": True,
        "source_provenance_coverage": "complete",
    })
    candidate["report"]["plan"]["horizon_trading_days"] = 10

    result = evaluate_candidate(
        candidate,
        study_kind="prospective",
        manifest_sha256="f" * 64,
        selection_period={"start": "2026-09-09", "end": "2026-09-11"},
        expected_horizons={"v2": [5]},
    )

    assert "report_outside_selection_period" in result["reason_codes"]
    assert "trade_horizon_not_registered" in result["reason_codes"]


def test_prospective_admission_rejects_internally_inconsistent_model_receipt():
    candidate = _candidate("v2")
    candidate["ticker"] = candidate["report"]["ticker"]
    candidate["pipeline_id"] = "v2"
    candidate["report"].update({
        "prompt_fingerprint": "a" * 64,
        "analysis_input_hash": "b" * 64,
        "data_snapshot_hash": "c" * 64,
        "model_route_policy_sha256": "d" * 64,
        "code_commit": "e" * 40,
        "model_executions": [{
            "agent_num": 16,
            "model_id": "model-x",
            "route_index": 0,
            "route_considered": ["different-model"],
            "provider_call_models": [],
            "route_skipped": [],
            "failed_models": [],
            "fallback_used": False,
            "cache_hit": False,
        }],
        "model_revision_unknown": True,
        "source_provenance_coverage": "complete",
    })

    result = evaluate_candidate(
        candidate,
        study_kind="prospective",
        manifest_sha256="f" * 64,
        selection_period={"start": "2026-09-09", "end": "2026-09-11"},
        expected_horizons={"v2": [5]},
    )

    assert "invalid_model_execution_receipt" in result["reason_codes"]


def test_time_chain_still_rejects_required_order_when_first_available_is_missing():
    assert set(verify_time_chain({
        "analysis_input_cutoff": "2026-09-09T02:00:00Z",
        "conclusion_generated_at": "2026-09-09T01:00:00Z",
        "report_available_at": "2026-09-09T03:00:00Z",
    })) == {"missing_input_first_available_at", "timestamp_order_invalid"}


def test_prospective_seal_uses_explicit_exchange_open_instead_of_calendar_date():
    assert verify_seal(
        study_kind="prospective",
        report_available_at="2026-09-09T08:00:00+08:00",
        sealed_at="2026-09-09T08:30:00+08:00",
        first_session_date="2026-09-09",
        timezone_name="Asia/Taipei",
        session_open_local_time="09:00:00",
    ) == []
    assert "late_seal" in verify_seal(
        study_kind="prospective",
        report_available_at="2026-09-09T08:00:00+08:00",
        sealed_at="2026-09-09T09:00:00+08:00",
        first_session_date="2026-09-09",
        timezone_name="Asia/Taipei",
        session_open_local_time="09:00:00",
    )


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


def test_prospective_cli_records_receipt_classification_and_controls_admission(tmp_path):
    manifest_fields = dict(_manifest("prospective-four-mode"))
    manifest_fields.pop("manifest_sha256")
    manifest_fields["study_kind"] = "prospective"
    manifest = build_manifest(**manifest_fields)
    manifest_path = tmp_path / "manifest.json"
    inventory_path = tmp_path / "inventory.json"
    dataset_path = tmp_path / "dataset.json"
    receipt_path = tmp_path / "registration.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    inventory_path.write_text(json.dumps({
        "coverage_status": "closed", "candidates": [_candidate("v1")]
    }), encoding="utf-8")
    dataset_path.write_text(json.dumps(_dataset()), encoding="utf-8")

    unverified = run_replay(
        root=str(tmp_path / "unverified-study"),
        manifest_input=str(manifest_path),
        inventory_input=str(inventory_path),
        dataset_input=str(dataset_path),
    )
    assert unverified["study_classification"] == "prospective_unverified"
    assert unverified["summary"]["admission_counts"] == {"insufficient_provenance": 1}
    assert unverified["summary"]["evaluation_total"] == 0

    receipt_path.write_text(json.dumps(
        _registration_evidence(manifest["manifest_sha256"])
    ), encoding="utf-8")
    captured = run_replay(
        root=str(tmp_path / "captured-study"),
        manifest_input=str(manifest_path),
        inventory_input=str(inventory_path),
        dataset_input=str(dataset_path),
        registration_input=str(receipt_path),
    )
    assert captured["study_classification"] == "prospective_unverified"
    assert captured["registration_reason_codes"] == [
        "registration_time_not_externally_attested"
    ]
    assert captured["summary"]["admission_counts"] == {"insufficient_provenance": 1}
    assert captured["summary"]["evaluation_total"] == 0
    assert "registration-receipt" in StudyStore(
        tmp_path / "captured-study", study_id=manifest["study_id"], create=False
    ).list_records()

    receipt_path.write_text(json.dumps(_registration_evidence(
        manifest["manifest_sha256"], observed_at="2025-01-02T00:00:00Z"
    )), encoding="utf-8")
    late = run_replay(
        root=str(tmp_path / "late-study"),
        manifest_input=str(manifest_path),
        inventory_input=str(inventory_path),
        dataset_input=str(dataset_path),
        registration_input=str(receipt_path),
    )
    assert late["study_classification"] == "prospective_unverified"
    assert "registration_after_analysis_input_cutoff" in late["registration_reason_codes"]
    assert late["summary"]["admission_counts"] == {"insufficient_provenance": 1}
    assert late["summary"]["evaluation_total"] == 0
    late_record = StudyStore(
        tmp_path / "late-study", study_id=manifest["study_id"], create=False
    ).read_record("registration-receipt")
    assert late_record["payload"]["study_classification"] == "prospective_unverified"
    assert "registration_after_analysis_input_cutoff" in late_record["payload"]["reason_codes"]

    unsafe_evidence = _registration_evidence(manifest["manifest_sha256"])
    unsafe_evidence["external_registration_receipt"]["api_key"] = "must-not-persist"
    receipt_path.write_text(json.dumps(unsafe_evidence), encoding="utf-8")
    unsafe = run_replay(
        root=str(tmp_path / "unsafe-study"),
        manifest_input=str(manifest_path),
        inventory_input=str(inventory_path),
        dataset_input=str(dataset_path),
        registration_input=str(receipt_path),
    )
    assert unsafe["study_classification"] == "prospective_unverified"
    stored = StudyStore(
        tmp_path / "unsafe-study", study_id=manifest["study_id"], create=False
    ).read_record("registration-receipt")
    assert "must-not-persist" not in json.dumps(stored)
