from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from oos_research.manifest import build_manifest
from oos_research.policies import DEFAULT_POLICIES
from oos_research.provenance import verify_registration_capture_receipt, verify_registration_receipt


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/capture_oos_registration_receipt.py"


def _manifest():
    return build_manifest(
        schema_version="oos.manifest.v1",
        study_id="prospective-four-mode",
        study_kind="prospective",
        registered_at="2026-09-08T00:00:00Z",
        timezone="Asia/Taipei",
        selection_period={"start": "2026-09-09", "end": "2026-09-11"},
        ticker_universe=["1623.TW"],
        pipelines=["v1", "v2", "v3", "v4"],
        horizons={"v1": [3, 6, 12], "v2": [5], "v3": [5], "v4": [5, 10]},
        policies=dict(DEFAULT_POLICIES),
        evaluator_version="oos.evaluator.v1",
    )


def _load_module():
    spec = importlib.util.spec_from_file_location("capture_oos_registration_receipt_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_capture_binds_clean_head_manifest_and_remote_ref(tmp_path):
    module = _load_module()
    repo = tmp_path / "repo"
    manifest_path = repo / "docs" / "study.json"
    manifest_path.parent.mkdir(parents=True)
    manifest = _manifest()
    manifest_bytes = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    commit = "c" * 40
    ref = "refs/heads/prospective-study"
    remote_line = f"{commit}\t{ref}\n".encode()
    calls = []

    def run(command, *, timeout=15):
        calls.append(command)
        if command[-2:] == ["rev-parse", "--show-toplevel"]:
            return 0, f"{repo}\n".encode(), b""
        if command[-2:] == ["rev-parse", "HEAD"]:
            return 0, f"{commit}\n".encode(), b""
        if command[-3:] == ["status", "--porcelain=v1", "--untracked-files=normal"]:
            return 0, b"", b""
        if command[-2:] == ["remote", "get-url"]:
            raise AssertionError("remote name must be included")
        if command[-3:] == ["remote", "get-url", "origin"]:
            return 0, b"https://github.com/example/stock-agent.git\n", b""
        if command[-2:] == ["show", f"{commit}:docs/study.json"]:
            return 0, manifest_bytes, b""
        if command[-4:] == ["ls-remote", "--refs", "origin", ref]:
            return 0, remote_line, b""
        raise AssertionError(f"unexpected command: {command}")

    payload = module.capture(
        manifest_path=manifest_path,
        repo_root=repo,
        manifest_repo_path="docs/study.json",
        remote="origin",
        ref=ref,
        expected_commit=commit,
        observed_at="2026-09-08T01:00:00Z",
        run=run,
    )

    receipt = payload["external_registration_receipt"]
    assert receipt["manifest_sha256"] == manifest["manifest_sha256"]
    assert receipt["remote_evidence"] == remote_line.decode()
    assert receipt["remote_evidence_sha256"] == hashlib.sha256(remote_line).hexdigest()
    assert verify_registration_capture_receipt(
        payload, manifest_sha256=manifest["manifest_sha256"]
    ) == []
    assert verify_registration_receipt(
        payload, manifest_sha256=manifest["manifest_sha256"]
    ) == ["registration_time_not_externally_attested"]
    assert any("ls-remote" in command for command in calls)


def test_capture_rejects_manifest_not_present_in_expected_commit_before_remote_lookup(tmp_path):
    module = _load_module()
    repo = tmp_path / "repo"
    manifest_path = repo / "docs" / "study.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    commit = "c" * 40
    ref = "refs/heads/prospective-study"
    calls = []

    def run(command, *, timeout=15):
        calls.append(command)
        if command[-2:] == ["rev-parse", "--show-toplevel"]:
            return 0, f"{repo}\n".encode(), b""
        if command[-2:] == ["rev-parse", "HEAD"]:
            return 0, f"{commit}\n".encode(), b""
        if command[-3:] == ["status", "--porcelain=v1", "--untracked-files=normal"]:
            return 0, b"", b""
        if command[-2:] == ["show", f"{commit}:docs/study.json"]:
            return 0, b"different committed bytes", b""
        raise AssertionError("remote lookup must not run for an uncommitted manifest")

    with pytest.raises(RuntimeError, match="manifest bytes differ"):
        module.capture(
            manifest_path=manifest_path,
            repo_root=repo,
            manifest_repo_path="docs/study.json",
            remote="origin",
            ref=ref,
            expected_commit=commit,
            observed_at="2026-09-08T01:00:00Z",
            run=run,
        )

    assert not any("ls-remote" in command for command in calls)


def test_receipt_output_never_overwrites_existing_file(tmp_path):
    module = _load_module()
    output = tmp_path / "receipt.json"
    output.write_bytes(b"valuable existing receipt")

    with pytest.raises(ValueError, match="new absolute path"):
        module.write_exclusive(output, {"replacement": True})

    assert output.read_bytes() == b"valuable existing receipt"


def test_receipt_output_must_stay_outside_repository_even_through_symlink_parent(tmp_path):
    module = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(ValueError, match="outside the repository"):
        module.write_exclusive(repo / "receipt.json", {"receipt": True}, forbidden_root=repo)

    alias = tmp_path / "repo-alias"
    alias.symlink_to(repo, target_is_directory=True)
    with pytest.raises(ValueError, match="outside the repository"):
        module.write_exclusive(alias / "receipt.json", {"receipt": True}, forbidden_root=repo)

    assert not (repo / "receipt.json").exists()
