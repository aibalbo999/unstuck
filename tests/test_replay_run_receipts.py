"""Fixed-corpus comparisons must bind inputs, validators, and observed outcomes."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sqlite3

import pytest


def module():
    path = Path(__file__).parents[1] / "scripts/replay_error_prevention.py"
    spec = importlib.util.spec_from_file_location("replay_receipts_test", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def corpus(tmp_path, *, identity="neutral"):
    setup = {"trade_direction": "Neutral", "entry_zone": "N/A", "target_price": "N/A",
             "stop_loss": "N/A", "core_catalyst": "等待量縮後，再重新評估是否有明確進場時點。", "risk_level": "High"}
    case = {"kind": "job", "identity": identity, "labels": ["mode_execution"],
            "data": {"ticker": "2305.TW"}, "context": {"pipeline_id": "v4",
            "analyses": {"24": "等待重新評估"}, "structured_outputs": {"24": setup}}}
    payload = json.dumps(case, ensure_ascii=False).encode()
    (tmp_path / "case.json").write_bytes(payload)
    manifest = {"schema_version": 1, "cases": [{"identity": identity, "payload": "case.json",
                "sha256": hashlib.sha256(payload).hexdigest()}]}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def test_replay_binds_each_attempt_to_input_code_and_output_without_mutation(tmp_path):
    m = module(); path = corpus(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    first = m.replay_manifest(path); second = m.replay_manifest(path)
    assert first["run_receipt"]["run_id"] != second["run_receipt"]["run_id"]
    assert first["run_receipt"]["execution_status"] == "completed"
    assert first["run_receipt"]["quality_accepted"] is None
    receipt = first["case_receipts"][0]
    assert receipt["run_id"] == first["run_receipt"]["run_id"]
    assert receipt["payload_sha256"] == hashlib.sha256((tmp_path / "case.json").read_bytes()).hexdigest()
    assert receipt["result_sha256"] == m.sha256(m.encoded(first["results"][0]))
    assert first["run_receipt"]["validator_sha256"] == m.sha256(m.encoded(first["replay_code_receipt"]))
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert m.compare_replays(second, first)["status"] == "unchanged"


def test_same_classification_with_changed_gate_findings_needs_review(tmp_path, monkeypatch):
    m = module(); path = corpus(tmp_path)
    baseline = m.replay_manifest(path)
    original = m.replay_case
    def changed(case):
        result = original(case)
        result["checks"]["mode_execution"].append("new deterministic finding")
        return result
    monkeypatch.setattr(m, "replay_case", changed)
    current = m.replay_manifest(path)
    assert current["results"][0]["classification"] == baseline["results"][0]["classification"]
    comparison = m.compare_replays(current, baseline)
    assert comparison["status"] == "changed"
    assert comparison["changed_cases"] == ["neutral"]


@pytest.mark.parametrize("mutation", ["identity", "empty", "duplicate"])
def test_manifest_identity_and_nonempty_unique_case_set_are_required(tmp_path, mutation):
    m = module(); path = corpus(tmp_path)
    manifest = json.loads(path.read_text())
    if mutation == "identity": manifest["cases"][0]["identity"] = "another-job"
    elif mutation == "empty": manifest["cases"] = []
    else: manifest["cases"] *= 2
    path.write_text(json.dumps(manifest))
    if mutation == "identity":
        result = m.replay_manifest(path)
        assert result["run_receipt"]["execution_status"] == "incomplete"
        assert result["case_receipts"][0]["payload_sha256"] is None
    else:
        with pytest.raises(ValueError): m.replay_manifest(path)


@pytest.mark.parametrize("mutation", ["manifest", "result", "code", "legacy", "missing"])
def test_unbound_or_incomplete_baseline_cannot_pass(tmp_path, mutation):
    m = module(); current = m.replay_manifest(corpus(tmp_path))
    baseline = copy.deepcopy(current)
    if mutation == "manifest": baseline["manifest_sha256"] = "0" * 64
    elif mutation == "result": baseline["results"][0]["checks"] = {}
    elif mutation == "code": baseline["replay_code_receipt"] = {}
    elif mutation == "legacy": baseline.pop("case_receipts")
    else: baseline["run_receipt"]["execution_status"] = "incomplete"
    assert m.compare_replays(current, baseline)["status"] == "not_comparable"


def test_cli_incomplete_is_nonzero_and_never_overwrites_evidence(tmp_path):
    m = module(); path = corpus(tmp_path)
    (tmp_path / "case.json").write_text("corrupted")
    output = tmp_path / "result.json"
    assert m.main(["replay", str(path), "--result", str(output)]) == 3
    assert json.loads(output.read_text())["run_receipt"]["execution_status"] == "incomplete"
    original = path.read_bytes()
    assert m.main(["replay", str(path), "--result", str(path)]) == 3
    assert path.read_bytes() == original


def test_cli_baseline_comparison_records_exact_baseline_and_refuses_overwrite(tmp_path):
    m = module(); path = corpus(tmp_path)
    baseline = tmp_path / "baseline.json"; output = tmp_path / "current.json"
    assert m.main(["replay", str(path), "--result", str(baseline)]) == 0
    original = baseline.read_bytes()
    assert m.main(["replay", str(path), "--baseline", str(baseline), "--result", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["comparison"]["status"] == "unchanged"
    assert result["comparison"]["baseline_sha256"] == hashlib.sha256(original).hexdigest()
    assert m.main(["replay", str(path), "--result", str(baseline)]) == 3
    assert baseline.read_bytes() == original


def test_cli_replay_blocks_network_and_database_access(tmp_path, monkeypatch):
    m = module(); path = corpus(tmp_path)
    def external_access(case):
        with pytest.raises(OSError): socket.create_connection(("127.0.0.1", 8080))
        with pytest.raises(OSError): sqlite3.connect(tmp_path / "must-not-exist.sqlite3")
        return {"identity": case["identity"], "classification": "still_reproduced", "checks": {}}
    monkeypatch.setattr(m, "replay_case", external_access)
    assert m.main(["replay", str(path), "--result", str(tmp_path / "result.json")]) == 0
    assert not (tmp_path / "must-not-exist.sqlite3").exists()


def test_validator_change_during_run_is_incomplete(tmp_path, monkeypatch):
    m = module(); path = corpus(tmp_path)
    receipts = iter([{"code.py": "a" * 64}, {"code.py": "b" * 64}])
    monkeypatch.setattr(m, "validator_receipt", lambda: next(receipts))
    result = m.replay_manifest(path)
    assert result["run_receipt"]["code_stable_during_run"] is False
    assert result["run_receipt"]["execution_status"] == "incomplete"


def test_cli_changed_baseline_exits_four_without_promoting_it(tmp_path, monkeypatch):
    m = module(); path = corpus(tmp_path)
    baseline = tmp_path / "baseline.json"
    assert m.main(["replay", str(path), "--result", str(baseline)]) == 0
    original = baseline.read_bytes(); replay_case = m.replay_case
    def changed(case):
        result = replay_case(case)
        result["checks"]["mode_execution"].append("changed finding")
        return result
    monkeypatch.setattr(m, "replay_case", changed)
    assert m.main(["replay", str(path), "--baseline", str(baseline),
                   "--result", str(tmp_path / "changed.json")]) == 4
    assert baseline.read_bytes() == original


def test_nonobject_baseline_is_not_comparable(tmp_path):
    m = module()
    assert m.compare_replays(m.replay_manifest(corpus(tmp_path)), [])["status"] == "not_comparable"


def test_gate_exception_keeps_verified_input_but_cannot_pass(tmp_path, monkeypatch):
    m = module(); path = corpus(tmp_path)
    def broken(case): raise RuntimeError("gate failed")
    monkeypatch.setattr(m, "replay_case", broken)
    result = m.replay_manifest(path)
    assert result["case_receipts"][0]["payload_sha256"] == hashlib.sha256((tmp_path / "case.json").read_bytes()).hexdigest()
    assert result["run_receipt"]["execution_status"] == "incomplete"
    assert m.compare_replays(result, result)["status"] == "not_comparable"
