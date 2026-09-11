from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "oos-register.yml"
MANIFEST_PATH = "docs/oos-prospective-manifest-2026-09-08.json"
WORKFLOW_PATH = ".github/workflows/oos-register.yml"
CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
ATTEST_SHA = "1e69f48acb82d1966a394da916b4c1698aa569d6"
PRODUCTION_PARENT_COMMIT = "c" * 40
PROMPT_FINGERPRINT = "989c7d14adc206cd1d37a1e8ee8976b9383bc8d57e7d3b37f8e293064a043359"
MODEL_ROUTE_SHA256 = "e0a14c8450d78653e4cc1908f515c4132ed20e2313bdddbfb55349d312119822"
COHORT_SOURCE_SHA256 = "f9d697eacc525ba8c0bbd7d8d4dde0d8619982ee96da6076f2af3c7d2fce0af2"


def _workflow() -> dict:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _steps() -> list[dict]:
    jobs = _workflow()["jobs"]
    assert list(jobs) == ["attest-oos-manifest"]
    return jobs["attest-oos-manifest"]["steps"]


def _step(step_id: str) -> dict:
    return next(step for step in _steps() if step.get("id") == step_id)


def _heredoc_python(run: str) -> str:
    marker = "python3 - <<'PY'\n"
    assert run.count(marker) == 1
    body = run.split(marker, 1)[1]
    assert body.endswith("\nPY\n")
    return body[: -len("\nPY\n")]


def _manifest(**overrides: object) -> dict:
    payload = {
        "schema_version": "oos.manifest.v1",
        "study_id": "four-mode-credibility-prospective-r1",
        "study_kind": "prospective",
        "registered_at": "2026-09-08T00:00:00Z",
        "timezone": "Asia/Taipei",
        "selection_period": {"start": "2026-09-09", "end": "2026-09-11"},
        "ticker_universe": [
            "1623.TW",
            "2308.TW",
            "2367.TW",
            "3017.TW",
            "3324.TWO",
            "3653.TW",
            "6282.TW",
        ],
        "pipelines": ["v1", "v2", "v3", "v4"],
        "horizons": {
            "v1": [3, 6, 12],
            "v2": [5],
            "v3": [5],
            "v4": [5, 10],
        },
        "policies": {
            "v2_primary_horizon_trading_days": 5,
            "v3_primary_horizon_trading_days": 5,
            "cohort_source_manifest_sha256": COHORT_SOURCE_SHA256,
            "cohort_candidate_count": 28,
            "candidate_selection": "first_eligible_post_attestation_report_per_ticker_pipeline",
            "selection_window_inclusive": True,
            "session_open_local_time": "09:00:00",
        },
        "evaluator_version": "oos.evaluator.v1",
        "runtime_identity": {
            "production_parent_commit": PRODUCTION_PARENT_COMMIT,
            "prompt_fingerprint": PROMPT_FINGERPRINT,
            "model_route_policy_sha256": MODEL_ROUTE_SHA256,
        },
    }
    payload.update(overrides)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    payload["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def _run_manifest_verifier(tmp_path: Path, manifest: dict) -> subprocess.CompletedProcess[str]:
    path = tmp_path / MANIFEST_PATH
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return subprocess.run(
        ["python3", "-c", _heredoc_python(_step("verify-manifest")["run"])],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT / "backend"),
            "PRODUCTION_PARENT_COMMIT": PRODUCTION_PARENT_COMMIT,
        },
        text=True,
        capture_output=True,
        check=False,
    )


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", *files)
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _bootstrap_repo(tmp_path: Path, *, extra_path: bool = False) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    _commit(repo, {"README.md": "base\n"}, "base")
    files = {WORKFLOW_PATH: "workflow\n", MANIFEST_PATH: "manifest\n"}
    if extra_path:
        files["unexpected.txt"] = "not bootstrap scope\n"
    head = _commit(repo, files, "bootstrap")
    return repo, head


def _run_source_verifier(
    repo: Path, head: str, tmp_path: Path, *, event: str = "push", ref: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "GITHUB_EVENT_NAME": event,
        "GITHUB_REF": ref or "refs/heads/codex/analysis-credibility-spec",
        "GITHUB_SHA": head,
        "RUNNER_TEMP": str(tmp_path / "runner-temp"),
        "GITHUB_OUTPUT": str(tmp_path / "github-output"),
    }
    Path(env["RUNNER_TEMP"]).mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        ["bash", "-c", _step("verify-source")["run"]],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_workflow_has_exact_minimum_permissions_and_narrow_triggers():
    workflow = _workflow()

    assert workflow["on"] == {
        "workflow_dispatch": {},
        "push": {
            "branches": ["codex/analysis-credibility-spec"],
            "paths": [WORKFLOW_PATH, MANIFEST_PATH],
        },
    }
    assert workflow["permissions"] == {
        "contents": "read",
        "id-token": "write",
        "attestations": "write",
    }
    job = workflow["jobs"]["attest-oos-manifest"]
    assert job["runs-on"] == "ubuntu-24.04"
    assert "permissions" not in job
    assert isinstance(job.get("timeout-minutes"), int)

    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target" not in raw
    assert "self-hosted" not in raw
    assert "secrets." not in raw


def test_workflow_pins_only_the_approved_actions_and_attests_fixed_manifest():
    steps = _steps()
    uses = [step["uses"] for step in steps if "uses" in step]
    assert uses == [f"actions/checkout@{CHECKOUT_SHA}", f"actions/attest@{ATTEST_SHA}"]
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", action) for action in uses)

    checkout = steps[0]
    assert checkout["with"] == {"fetch-depth": 2, "persist-credentials": False}
    attest = steps[-1]
    assert attest["id"] == "attest"
    assert attest["with"] == {"subject-path": MANIFEST_PATH}


def test_manifest_verifier_accepts_only_exact_cohort_and_canonical_hash(tmp_path):
    valid = _manifest()
    assert _run_manifest_verifier(tmp_path / "valid", valid).returncode == 0

    cases = []
    wrong_schema = _manifest(schema_version="oos.manifest.v2")
    cases.append(wrong_schema)
    wrong_kind = _manifest(study_kind="retrospective_replay")
    cases.append(wrong_kind)
    wrong_universe = _manifest(ticker_universe=valid["ticker_universe"][:-1])
    cases.append(wrong_universe)
    wrong_pipelines = _manifest(pipelines=["v1", "v2", "v3"])
    cases.append(wrong_pipelines)
    wrong_horizons = _manifest(horizons={**valid["horizons"], "v4": [10]})
    cases.append(wrong_horizons)
    wrong_selection = _manifest(selection_period={"start": "2026-09-10", "end": "2026-09-11"})
    cases.append(wrong_selection)
    wrong_runtime = _manifest(runtime_identity={
        **valid["runtime_identity"], "production_parent_commit": "d" * 40,
    })
    cases.append(wrong_runtime)
    wrong_source = _manifest(policies={
        **valid["policies"], "cohort_source_manifest_sha256": "e" * 64,
    })
    cases.append(wrong_source)
    bad_hash = copy.deepcopy(valid)
    bad_hash["manifest_sha256"] = "0" * 64
    cases.append(bad_hash)

    for index, manifest in enumerate(cases):
        result = _run_manifest_verifier(tmp_path / f"invalid-{index}", manifest)
        assert result.returncode != 0, result.stdout + result.stderr


def test_push_bootstrap_is_first_commit_and_exactly_two_paths(tmp_path):
    repo, head = _bootstrap_repo(tmp_path / "good")
    assert _run_source_verifier(repo, head, tmp_path / "good").returncode == 0

    wrong_ref = _run_source_verifier(
        repo, head, tmp_path / "wrong-ref", ref="refs/heads/main"
    )
    assert wrong_ref.returncode != 0

    future_head = _commit(repo, {MANIFEST_PATH: "changed\n"}, "future")
    repeated = _run_source_verifier(repo, future_head, tmp_path / "repeated")
    assert repeated.returncode != 0

    broad_repo, broad_head = _bootstrap_repo(tmp_path / "broad", extra_path=True)
    broad = _run_source_verifier(broad_repo, broad_head, tmp_path / "broad")
    assert broad.returncode != 0


def test_manual_dispatch_still_requires_exact_checkout_sha(tmp_path):
    repo, head = _bootstrap_repo(tmp_path)
    accepted = _run_source_verifier(
        repo, head, tmp_path / "manual", event="workflow_dispatch"
    )
    assert accepted.returncode == 0

    rejected = _run_source_verifier(
        repo, "0" * 40, tmp_path / "wrong-sha", event="workflow_dispatch"
    )
    assert rejected.returncode != 0

    wrong_ref = _run_source_verifier(
        repo, head, tmp_path / "manual-wrong-ref", event="workflow_dispatch", ref="refs/heads/main"
    )
    assert wrong_ref.returncode != 0


@pytest.mark.parametrize("event", ["pull_request", "pull_request_target", "schedule"])
def test_source_verifier_rejects_unexpected_events(tmp_path, event):
    repo, head = _bootstrap_repo(tmp_path)
    result = _run_source_verifier(repo, head, tmp_path / event, event=event)
    assert result.returncode != 0
