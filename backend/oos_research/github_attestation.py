"""Offline GitHub/Sigstore registration verification.

Serialized v2 projections are not portable proof; each process must rerun ``gh``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .manifest import manifest_hash, validate_manifest
SLSA_PROVENANCE_V1 = "https://slsa.dev/provenance/v1"
GITHUB_ACTIONS_OIDC_ISSUER = "https://token.actions.githubusercontent.com"
EXPECTED_REPOSITORY = "aibalbo999/unstuck"
EXPECTED_SIGNER_WORKFLOW = ".github/workflows/oos-register.yml"
MAX_MANIFEST_BYTES = 1_048_576
MAX_BUNDLE_BYTES = 8_388_608
MAX_TRUSTED_ROOT_BYTES = 8_388_608
MAX_GH_STDOUT_BYTES = 4_194_304
MAX_VERIFIED_ATTESTATIONS = 30
GH_TIMEOUT_SECONDS = 30
SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
SAFE_REF_RE = re.compile(r"refs/(?:heads|tags)/[A-Za-z0-9._/-]+")
V2_RECEIPT_FIELDS = frozenset("""
schema_version source repository certificate_identity oidc_issuer source_commit
source_ref predicate_type manifest_file_sha256 manifest_sha256 bundle_sha256
trusted_root_sha256 verified_at
""".split())
_RUNTIME_TOKEN = object()
class GitHubAttestationVerificationError(ValueError):
    """Raised when no bounded, policy-conforming attestation can be verified."""
@dataclass(frozen=True)
class GitHubAttestationPolicy:
    repository: str
    certificate_identity: str
    oidc_issuer: str
    source_commit: str
    source_ref: str
    predicate_type: str = SLSA_PROVENANCE_V1
class _RuntimeVerifiedGitHubRegistration(Mapping[str, Any]):
    """Process-local capability proving that the offline verifier ran successfully."""

    __slots__ = ("_receipt", "_token")
    def __init__(self, receipt: Mapping[str, Any], *, token: object) -> None:
        if token is not _RUNTIME_TOKEN:
            raise TypeError("runtime verification evidence is factory-only")
        self._receipt = MappingProxyType(dict(receipt))
        self._token = token
    def __getitem__(self, key: str) -> Any:
        if key != "external_registration_receipt":
            raise KeyError(key)
        return self._receipt
    def __iter__(self) -> Iterator[str]:
        yield "external_registration_receipt"
    def __len__(self) -> int:
        return 1
def _fail(message: str) -> GitHubAttestationVerificationError:
    return GitHubAttestationVerificationError(message)
def _read_bounded(path_value: str | Path, *, maximum: int, label: str) -> tuple[Path, bytes]:
    path = Path(path_value)
    if not path.is_absolute() or path.is_symlink():
        raise _fail(f"{label} path must be an absolute non-symlink file")
    try:
        resolved = path.resolve(strict=True)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(resolved, flags)
    except (OSError, RuntimeError):
        raise _fail(f"{label} file is unavailable") from None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size <= 0 or metadata.st_size > maximum:
            raise _fail(f"{label} file size is invalid")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            data = handle.read(maximum + 1)
        if not data or len(data) > maximum:
            raise _fail(f"{label} file size is invalid")
    finally:
        os.close(descriptor)
    return resolved, data
def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value
def _load_json(data: bytes | str, *, label: str) -> Any:
    try:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data, object_pairs_hook=_reject_duplicate_keys,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise _fail(f"{label} JSON is invalid") from None
def _validate_policy(policy: GitHubAttestationPolicy) -> None:
    if not isinstance(policy, GitHubAttestationPolicy):
        raise _fail("GitHub attestation policy is invalid")
    if policy.repository != EXPECTED_REPOSITORY:
        raise _fail("GitHub attestation repository policy is invalid")
    if policy.oidc_issuer != GITHUB_ACTIONS_OIDC_ISSUER:
        raise _fail("GitHub attestation OIDC issuer policy is invalid")
    if policy.predicate_type != SLSA_PROVENANCE_V1:
        raise _fail("GitHub attestation predicate policy is invalid")
    if not COMMIT_RE.fullmatch(policy.source_commit):
        raise _fail("GitHub attestation source commit policy is invalid")
    invalid_ref = (
        not SAFE_REF_RE.fullmatch(policy.source_ref)
        or ".." in policy.source_ref
        or "//" in policy.source_ref
        or policy.source_ref.endswith(("/", ".", ".lock"))
    )
    if invalid_ref:
        raise _fail("GitHub attestation source ref policy is invalid")
    expected_identity = (
        f"https://github.com/{policy.repository}/{EXPECTED_SIGNER_WORKFLOW}@{policy.source_ref}"
    )
    if policy.certificate_identity != expected_identity:
        raise _fail("GitHub attestation certificate identity policy is invalid")
def _parse_manifest(data: bytes, expected_manifest_sha256: str) -> Mapping[str, Any]:
    if not isinstance(expected_manifest_sha256, str) or not SHA256_RE.fullmatch(expected_manifest_sha256):
        raise _fail("expected canonical manifest hash is invalid")
    manifest = _load_json(data, label="manifest")
    if not isinstance(manifest, Mapping):
        raise _fail("manifest JSON is invalid")
    try:
        validate_manifest(manifest)
        calculated = manifest_hash(manifest)
    except (TypeError, ValueError):
        raise _fail("manifest canonical hash is invalid") from None
    if manifest.get("manifest_sha256") != calculated or calculated != expected_manifest_sha256:
        raise _fail("manifest canonical hash does not match")
    return manifest
def load_manifest_sha256(manifest_path: str | Path) -> str:
    """Load and validate the canonical manifest identity from a bounded file."""
    _, manifest_data = _read_bounded(
        manifest_path, maximum=MAX_MANIFEST_BYTES, label="manifest"
    )
    manifest = _load_json(manifest_data, label="manifest")
    if not isinstance(manifest, Mapping):
        raise _fail("manifest JSON is invalid")
    expected = manifest.get("manifest_sha256")
    if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
        raise _fail("manifest canonical hash is invalid")
    _parse_manifest(manifest_data, expected)
    return expected
def _subject_alternative_name(certificate: Mapping[str, Any]) -> Any:
    value = certificate.get("subjectAlternativeName")
    if isinstance(value, Mapping):
        return value.get("value")
    return value
def _parse_verified_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise _fail("verified attestation timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _fail("verified attestation timestamp is invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _fail("verified attestation timestamp is invalid")
    return parsed
def _validate_gh_result(
    result: Any, *, manifest_file_sha256: str, policy: GitHubAttestationPolicy,
) -> str:
    if not isinstance(result, list) or not (1 <= len(result) <= MAX_VERIFIED_ATTESTATIONS):
        raise _fail("gh attestation verification result is invalid")
    verified_times: list[datetime] = []
    expected_repository_uri = f"https://github.com/{policy.repository}"
    for entry in result:
        if not isinstance(entry, Mapping):
            raise _fail("gh attestation verification result is invalid")
        verification = entry.get("verificationResult")
        if not isinstance(verification, Mapping):
            raise _fail("gh attestation verification result is invalid")
        signature = verification.get("signature")
        certificate = signature.get("certificate") if isinstance(signature, Mapping) else None
        if not isinstance(certificate, Mapping):
            raise _fail("verified attestation certificate is invalid")
        required_certificate_values = {
            "issuer": policy.oidc_issuer,
            "sourceRepositoryURI": expected_repository_uri,
            "sourceRepositoryDigest": policy.source_commit,
            "sourceRepositoryRef": policy.source_ref,
            "runnerEnvironment": "github-hosted",
        }
        if _subject_alternative_name(certificate) != policy.certificate_identity:
            raise _fail("verified attestation certificate identity does not match")
        if any(certificate.get(key) != expected for key, expected in required_certificate_values.items()):
            raise _fail("verified attestation certificate source does not match")
        statement = verification.get("statement")
        if not isinstance(statement, Mapping) or statement.get("predicateType") != policy.predicate_type:
            raise _fail("verified attestation predicate does not match")
        subjects = statement.get("subject")
        if not isinstance(subjects, list) or len(subjects) != 1 or not isinstance(subjects[0], Mapping):
            raise _fail("verified attestation subject is invalid")
        digest = subjects[0].get("digest")
        if not isinstance(digest, Mapping) or digest.get("sha256") != manifest_file_sha256:
            raise _fail("verified attestation subject digest does not match")
        timestamps = verification.get("verifiedTimestamps")
        if not isinstance(timestamps, list) or not timestamps or len(timestamps) > 64:
            raise _fail("verified attestation timestamps are invalid")
        for timestamp in timestamps:
            if not isinstance(timestamp, Mapping):
                raise _fail("verified attestation timestamp is invalid")
            verified_times.append(_parse_verified_timestamp(timestamp.get("timestamp")))
    earliest = min(verified_times).astimezone(timezone.utc)
    return earliest.isoformat(timespec="seconds").replace("+00:00", "Z")


def _run_gh(argv: list[str], runner: Callable[..., Any] | None) -> str:
    command_runner = runner or subprocess.run
    try:
        completed = command_runner(
            argv,
            capture_output=True,
            check=False,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError, TimeoutError, UnicodeError):
        raise _fail("gh attestation verification command failed") from None
    if getattr(completed, "returncode", None) != 0:
        raise _fail("gh attestation verification command failed")
    stdout = getattr(completed, "stdout", None)
    if not isinstance(stdout, str) or not stdout or len(stdout.encode("utf-8")) > MAX_GH_STDOUT_BYTES:
        raise _fail("gh attestation verification output is invalid")
    return stdout


def verify_github_registration_attestation(
    *, manifest_path: str | Path, bundle_path: str | Path,
    trusted_root_path: str | Path,
    expected_manifest_sha256: str,
    policy: GitHubAttestationPolicy,
    runner: Callable[..., Any] | None = None,
) -> Mapping[str, Any]:
    """Rerun bounded offline verification and return a process-local v2 capability."""
    _validate_policy(policy)
    manifest_file, manifest_data = _read_bounded(
        manifest_path, maximum=MAX_MANIFEST_BYTES, label="manifest"
    )
    bundle_file, bundle_data = _read_bounded(
        bundle_path, maximum=MAX_BUNDLE_BYTES, label="attestation bundle"
    )
    trusted_root_file, trusted_root_data = _read_bounded(
        trusted_root_path, maximum=MAX_TRUSTED_ROOT_BYTES, label="trusted root"
    )
    _parse_manifest(manifest_data, expected_manifest_sha256)
    manifest_file_sha256 = hashlib.sha256(manifest_data).hexdigest()
    argv = [
        "gh", "attestation", "verify", str(manifest_file),
        "--bundle", str(bundle_file),
        "--custom-trusted-root", str(trusted_root_file),
        "--repo", policy.repository,
        "--cert-identity", policy.certificate_identity,
        "--cert-oidc-issuer", policy.oidc_issuer,
        "--source-digest", policy.source_commit,
        "--source-ref", policy.source_ref,
        "--predicate-type", policy.predicate_type,
        "--deny-self-hosted-runners",
        "--digest-alg=sha256",
        "--format=json",
    ]
    stdout = _run_gh(argv, runner)
    snapshots = (
        (manifest_file, manifest_data, MAX_MANIFEST_BYTES, "manifest"),
        (bundle_file, bundle_data, MAX_BUNDLE_BYTES, "attestation bundle"),
        (trusted_root_file, trusted_root_data, MAX_TRUSTED_ROOT_BYTES, "trusted root"),
    )
    for path, expected, maximum, label in snapshots:
        if _read_bounded(path, maximum=maximum, label=label)[1] != expected:
            raise _fail(f"{label} changed during verification")
    result = _load_json(stdout, label="gh attestation verification output")
    verified_at = _validate_gh_result(
        result,
        manifest_file_sha256=manifest_file_sha256,
        policy=policy,
    )
    receipt = {
        "schema_version": "oos.registration-receipt.v2",
        "source": "github_sigstore_offline",
        "repository": policy.repository,
        "certificate_identity": policy.certificate_identity,
        "oidc_issuer": policy.oidc_issuer,
        "source_commit": policy.source_commit,
        "source_ref": policy.source_ref,
        "predicate_type": policy.predicate_type,
        "manifest_file_sha256": manifest_file_sha256,
        "manifest_sha256": expected_manifest_sha256,
        "bundle_sha256": hashlib.sha256(bundle_data).hexdigest(),
        "trusted_root_sha256": hashlib.sha256(trusted_root_data).hexdigest(),
        "verified_at": verified_at,
    }
    return _RuntimeVerifiedGitHubRegistration(receipt, token=_RUNTIME_TOKEN)


def verify_runtime_github_registration(
    evidence: Mapping[str, Any] | None, *, manifest_sha256: str | None,
    analysis_input_cutoff: Any = None,
) -> list[str]:
    """Validate a process-local capability; serialized v2 JSON never passes."""
    if type(evidence) is not _RuntimeVerifiedGitHubRegistration:
        return ["registration_attestation_not_runtime_verified"]
    if evidence._token is not _RUNTIME_TOKEN:  # type: ignore[attr-defined]
        return ["registration_attestation_not_runtime_verified"]
    receipt = evidence["external_registration_receipt"]
    reasons: list[str] = []
    if set(receipt) != V2_RECEIPT_FIELDS:
        reasons.append("unexpected_registration_receipt_fields")
    if receipt.get("manifest_sha256") != manifest_sha256:
        reasons.append("registration_manifest_hash_mismatch")
    try:
        verified_at = _parse_verified_timestamp(receipt.get("verified_at"))
    except GitHubAttestationVerificationError:
        verified_at = None
        reasons.append("missing_or_invalid_registration_verified_at")
    if analysis_input_cutoff is not None and verified_at is not None:
        try:
            cutoff = _parse_verified_timestamp(analysis_input_cutoff)
        except GitHubAttestationVerificationError:
            cutoff = None
        if cutoff is not None and verified_at > cutoff:
            reasons.append("registration_after_analysis_input_cutoff")
    return sorted(set(reasons))


def github_registration_projection(evidence: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project only non-secret receipt fields; plain JSON v2 is not persisted as proof."""
    if type(evidence) is not _RuntimeVerifiedGitHubRegistration:
        return {}
    if evidence._token is not _RUNTIME_TOKEN:  # type: ignore[attr-defined]
        return {}
    receipt = evidence["external_registration_receipt"]
    return {"external_registration_receipt": {
        key: receipt[key] for key in V2_RECEIPT_FIELDS
    }}
