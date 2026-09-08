from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

import oos_research.github_attestation as github_attestation
from oos_research.github_attestation import (
    GitHubAttestationPolicy,
    GitHubAttestationVerificationError,
    github_registration_projection,
    verify_github_registration_attestation,
)
from oos_research.manifest import build_manifest
from oos_research.policies import DEFAULT_POLICIES
from oos_research.provenance import (
    classify_study_kind,
    registration_receipt_projection,
    verify_registration_receipt,
)


REPOSITORY = "aibalbo999/unstuck"
SOURCE_COMMIT = "a" * 40
SOURCE_REF = "refs/heads/codex/analysis-credibility-spec"
CERTIFICATE_IDENTITY = (
    "https://github.com/aibalbo999/unstuck/"
    ".github/workflows/oos-register.yml@"
    f"{SOURCE_REF}"
)
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
PREDICATE_TYPE = "https://slsa.dev/provenance/v1"
VERIFIED_AT = "2026-09-08T00:01:00Z"


def _manifest() -> dict:
    return build_manifest(
        schema_version="oos.manifest.v1",
        study_id="prospective-attested-four-mode",
        study_kind="prospective",
        registered_at="2026-09-08T00:00:00Z",
        timezone="Asia/Taipei",
        selection_period={"start": "2026-09-08", "end": "2027-09-08"},
        ticker_universe=["1623.TW"],
        pipelines=["v1", "v2", "v3", "v4"],
        horizons={"v1": [3, 6, 12], "v2": [5], "v3": [5], "v4": [5, 10]},
        policies=dict(DEFAULT_POLICIES),
        evaluator_version="oos.evaluator.v1",
    )


def _paths(tmp_path: Path) -> tuple[dict, Path, Path, Path]:
    manifest = _manifest()
    manifest_path = tmp_path / "manifest.json"
    bundle_path = tmp_path / "attestation.bundle.jsonl"
    trusted_root_path = tmp_path / "trusted-root.jsonl"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
    bundle_path.write_text('{"bundle":"bounded fixture"}\n', encoding="utf-8")
    trusted_root_path.write_text('{"trustedRoot":"bounded fixture"}\n', encoding="utf-8")
    return manifest, manifest_path, bundle_path, trusted_root_path


def _policy() -> GitHubAttestationPolicy:
    return GitHubAttestationPolicy(
        repository=REPOSITORY,
        certificate_identity=CERTIFICATE_IDENTITY,
        oidc_issuer=OIDC_ISSUER,
        source_commit=SOURCE_COMMIT,
        source_ref=SOURCE_REF,
        predicate_type=PREDICATE_TYPE,
    )


def _verification_output(manifest_path: Path) -> list[dict]:
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return [{
        "attestation": {"bundle": {"untrustedSecret": "must-not-persist"}},
        "verificationResult": {
            "signature": {"certificate": {
                "subjectAlternativeName": CERTIFICATE_IDENTITY,
                "issuer": OIDC_ISSUER,
                "sourceRepositoryURI": f"https://github.com/{REPOSITORY}",
                "sourceRepositoryDigest": SOURCE_COMMIT,
                "sourceRepositoryRef": SOURCE_REF,
                "runnerEnvironment": "github-hosted",
            }},
            "verifiedTimestamps": [{
                "type": "Tlog",
                "uri": "https://rekor.sigstore.dev",
                "timestamp": VERIFIED_AT,
            }],
            "statement": {
                "predicateType": PREDICATE_TYPE,
                "subject": [{"name": manifest_path.name, "digest": {"sha256": digest}}],
                "predicate": {"untrustedSecret": "must-not-persist"},
            },
        },
    }]


def _verified(tmp_path: Path, *, output: list[dict] | None = None):
    manifest, manifest_path, bundle_path, trusted_root_path = _paths(tmp_path)
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(output if output is not None else _verification_output(manifest_path)),
            stderr="",
        )

    evidence = verify_github_registration_attestation(
        manifest_path=manifest_path,
        bundle_path=bundle_path,
        trusted_root_path=trusted_root_path,
        expected_manifest_sha256=manifest["manifest_sha256"],
        policy=_policy(),
        runner=runner,
    )
    return evidence, manifest, manifest_path, bundle_path, trusted_root_path, calls


def test_factory_runs_one_locked_offline_gh_verification_and_returns_safe_runtime_evidence(tmp_path):
    evidence, manifest, manifest_path, bundle_path, trusted_root_path, calls = _verified(tmp_path)

    assert calls == [([
        "gh", "attestation", "verify", str(manifest_path.resolve()),
        "--bundle", str(bundle_path.resolve()),
        "--custom-trusted-root", str(trusted_root_path.resolve()),
        "--repo", REPOSITORY,
        "--cert-identity", CERTIFICATE_IDENTITY,
        "--cert-oidc-issuer", OIDC_ISSUER,
        "--source-digest", SOURCE_COMMIT,
        "--source-ref", SOURCE_REF,
        "--predicate-type", PREDICATE_TYPE,
        "--deny-self-hosted-runners",
        "--digest-alg=sha256",
        "--format=json",
    ], {
        "capture_output": True,
        "check": False,
        "text": True,
        "timeout": 30,
    })]
    assert verify_registration_receipt(
        evidence,
        manifest_sha256=manifest["manifest_sha256"],
        analysis_input_cutoff="2026-09-08T00:02:00Z",
    ) == []
    assert classify_study_kind(
        "prospective", evidence=evidence, manifest_sha256=manifest["manifest_sha256"]
    ) == "prospective"
    projection = registration_receipt_projection(evidence)
    serialized = json.dumps(projection, sort_keys=True)
    assert "must-not-persist" not in serialized
    receipt = projection["external_registration_receipt"]
    assert receipt["schema_version"] == "oos.registration-receipt.v2"
    assert receipt["manifest_file_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert receipt["manifest_sha256"] == manifest["manifest_sha256"]
    assert receipt["bundle_sha256"] == hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    assert receipt["trusted_root_sha256"] == hashlib.sha256(trusted_root_path.read_bytes()).hexdigest()
    assert receipt["verified_at"] == VERIFIED_AT


def test_v1_stays_unattested_and_plain_json_v2_cannot_recreate_runtime_verification(tmp_path):
    evidence, manifest, *_ = _verified(tmp_path)
    plain_v2 = json.loads(json.dumps(github_registration_projection(evidence)))

    assert verify_registration_receipt(
        plain_v2, manifest_sha256=manifest["manifest_sha256"]
    ) == ["registration_attestation_not_runtime_verified"]
    assert registration_receipt_projection(plain_v2) == {}
    assert classify_study_kind(
        "prospective", evidence=plain_v2, manifest_sha256=manifest["manifest_sha256"]
    ) == "prospective_unverified"

    remote_evidence = f"{'c' * 40}\trefs/heads/prospective-study\n"
    v1 = {"external_registration_receipt": {
        "schema_version": "oos.registration-receipt.v1",
        "source": "git_remote",
        "remote_url": "https://github.com/example/stock-agent.git",
        "ref": "refs/heads/prospective-study",
        "commit": "c" * 40,
        "observed_at": "2026-09-07T00:00:00Z",
        "manifest_sha256": manifest["manifest_sha256"],
        "remote_evidence": remote_evidence,
        "remote_evidence_sha256": hashlib.sha256(remote_evidence.encode()).hexdigest(),
    }}
    assert verify_registration_receipt(
        v1, manifest_sha256=manifest["manifest_sha256"]
    ) == ["registration_time_not_externally_attested"]


def test_verified_timestamp_is_the_only_v2_cutoff_clock(tmp_path):
    evidence, manifest, *_ = _verified(tmp_path)
    assert verify_registration_receipt(
        evidence,
        manifest_sha256=manifest["manifest_sha256"],
        analysis_input_cutoff="2026-09-08T00:00:59Z",
    ) == ["registration_after_analysis_input_cutoff"]


@pytest.mark.parametrize(
    ("field_path", "bad_value"),
    [
        (("signature", "certificate", "subjectAlternativeName"), "https://github.com/evil/workflow.yml"),
        (("signature", "certificate", "issuer"), "https://issuer.invalid"),
        (("signature", "certificate", "sourceRepositoryURI"), "https://github.com/evil/repo"),
        (("signature", "certificate", "sourceRepositoryDigest"), "b" * 40),
        (("signature", "certificate", "sourceRepositoryRef"), "refs/heads/other"),
        (("signature", "certificate", "runnerEnvironment"), "self-hosted"),
        (("statement", "predicateType"), "https://example.invalid/predicate"),
        (("statement", "subject", 0, "digest", "sha256"), "b" * 64),
        (("verifiedTimestamps",), []),
    ],
)
def test_factory_rechecks_every_security_critical_gh_result_field(tmp_path, field_path, bad_value):
    manifest, manifest_path, bundle_path, trusted_root_path = _paths(tmp_path)
    output = _verification_output(manifest_path)
    target = output[0]["verificationResult"]
    for key in field_path[:-1]:
        target = target[key]
    target[field_path[-1]] = bad_value

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(output), stderr="")

    with pytest.raises(GitHubAttestationVerificationError):
        verify_github_registration_attestation(
            manifest_path=manifest_path,
            bundle_path=bundle_path,
            trusted_root_path=trusted_root_path,
            expected_manifest_sha256=manifest["manifest_sha256"],
            policy=_policy(),
            runner=runner,
        )


def test_manifest_canonical_hash_and_raw_file_digest_are_both_bound(tmp_path):
    manifest, manifest_path, bundle_path, trusted_root_path = _paths(tmp_path)
    called = False

    def runner(argv, **kwargs):
        nonlocal called
        called = True
        return subprocess.CompletedProcess(argv, 0, stdout="[]", stderr="")

    with pytest.raises(GitHubAttestationVerificationError):
        verify_github_registration_attestation(
            manifest_path=manifest_path,
            bundle_path=bundle_path,
            trusted_root_path=trusted_root_path,
            expected_manifest_sha256="b" * 64,
            policy=_policy(),
            runner=runner,
        )
    assert called is False


def test_path_and_size_checks_fail_before_command_execution(tmp_path, monkeypatch):
    manifest, manifest_path, bundle_path, trusted_root_path = _paths(tmp_path)
    symlink = tmp_path / "bundle-link.jsonl"
    symlink.symlink_to(bundle_path)
    calls = []

    def runner(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="[]", stderr="")

    with pytest.raises(GitHubAttestationVerificationError):
        verify_github_registration_attestation(
            manifest_path=manifest_path.name,
            bundle_path=bundle_path,
            trusted_root_path=trusted_root_path,
            expected_manifest_sha256=manifest["manifest_sha256"],
            policy=_policy(),
            runner=runner,
        )
    with pytest.raises(GitHubAttestationVerificationError):
        verify_github_registration_attestation(
            manifest_path=manifest_path,
            bundle_path=symlink,
            trusted_root_path=trusted_root_path,
            expected_manifest_sha256=manifest["manifest_sha256"],
            policy=_policy(),
            runner=runner,
        )
    monkeypatch.setattr(github_attestation, "MAX_BUNDLE_BYTES", 4)
    with pytest.raises(GitHubAttestationVerificationError):
        verify_github_registration_attestation(
            manifest_path=manifest_path,
            bundle_path=bundle_path,
            trusted_root_path=trusted_root_path,
            expected_manifest_sha256=manifest["manifest_sha256"],
            policy=_policy(),
            runner=runner,
        )
    assert calls == []


@pytest.mark.parametrize("stdout", ["not-json", "{}", "[]", "[null]"])
def test_malformed_or_empty_gh_json_fails_closed(tmp_path, stdout):
    manifest, manifest_path, bundle_path, trusted_root_path = _paths(tmp_path)

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    with pytest.raises(GitHubAttestationVerificationError):
        verify_github_registration_attestation(
            manifest_path=manifest_path,
            bundle_path=bundle_path,
            trusted_root_path=trusted_root_path,
            expected_manifest_sha256=manifest["manifest_sha256"],
            policy=_policy(),
            runner=runner,
        )


def test_nonstandard_json_number_in_ignored_gh_field_still_fails_closed(tmp_path):
    manifest, manifest_path, bundle_path, trusted_root_path = _paths(tmp_path)
    stdout = json.dumps(_verification_output(manifest_path)).replace(
        '"untrustedSecret": "must-not-persist"', '"untrustedSecret": NaN', 1
    )

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    with pytest.raises(GitHubAttestationVerificationError):
        verify_github_registration_attestation(
            manifest_path=manifest_path,
            bundle_path=bundle_path,
            trusted_root_path=trusted_root_path,
            expected_manifest_sha256=manifest["manifest_sha256"],
            policy=_policy(),
            runner=runner,
        )


def test_command_failure_and_errors_never_echo_runner_secrets(tmp_path):
    manifest, manifest_path, bundle_path, trusted_root_path = _paths(tmp_path)

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv, 1, stdout='{"token":"stdout-secret"}', stderr="stderr-secret"
        )

    with pytest.raises(GitHubAttestationVerificationError) as raised:
        verify_github_registration_attestation(
            manifest_path=manifest_path,
            bundle_path=bundle_path,
            trusted_root_path=trusted_root_path,
            expected_manifest_sha256=manifest["manifest_sha256"],
            policy=_policy(),
            runner=runner,
        )
    assert "secret" not in str(raised.value)


def test_runner_decode_or_execution_exception_fails_closed_without_echo(tmp_path):
    manifest, manifest_path, bundle_path, trusted_root_path = _paths(tmp_path)

    def runner(argv, **kwargs):
        raise UnicodeDecodeError("utf-8", b"private", 0, 1, "runner-secret")

    with pytest.raises(GitHubAttestationVerificationError) as raised:
        verify_github_registration_attestation(
            manifest_path=manifest_path,
            bundle_path=bundle_path,
            trusted_root_path=trusted_root_path,
            expected_manifest_sha256=manifest["manifest_sha256"],
            policy=_policy(),
            runner=runner,
        )
    assert "secret" not in str(raised.value)


def test_input_snapshot_change_during_verification_fails_closed(tmp_path):
    manifest, manifest_path, bundle_path, trusted_root_path = _paths(tmp_path)

    def runner(argv, **kwargs):
        bundle_path.write_text('{"bundle":"changed during verification"}\n', encoding="utf-8")
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(_verification_output(manifest_path)), stderr=""
        )

    with pytest.raises(GitHubAttestationVerificationError):
        verify_github_registration_attestation(
            manifest_path=manifest_path,
            bundle_path=bundle_path,
            trusted_root_path=trusted_root_path,
            expected_manifest_sha256=manifest["manifest_sha256"],
            policy=_policy(),
            runner=runner,
        )
