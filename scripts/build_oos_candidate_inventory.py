#!/usr/bin/env python3
"""Seal completed formal reports and build the fixed prospective OOS inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from oos_candidate_inventory import finalize_inventory, seal_ready
from oos_research.calendar import validate_sessions
from oos_research.github_attestation import (
    EXPECTED_REPOSITORY,
    GITHUB_ACTIONS_OIDC_ISSUER,
    GitHubAttestationPolicy,
    github_registration_projection,
    verify_github_registration_attestation,
)


MAX_INPUT_BYTES = 32 * 1024 * 1024


def _unique_object(pairs):
    value = {}
    for key, child in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def _load_json(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"input must be a regular non-symlink file: {path}")
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_INPUT_BYTES:
        raise ValueError(f"JSON input size is invalid: {path}")
    payload = json.loads(
        raw,
        object_pairs_hook=_unique_object,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-finite JSON number: {value}")),
    )
    if not isinstance(payload, (dict, list)):
        raise ValueError(f"JSON input must be an object or list: {path}")
    return payload, hashlib.sha256(raw).hexdigest()


def _resolved_file(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("all evidence input paths must be absolute")
    if path.is_symlink():
        raise ValueError("evidence input path must not be a symlink")
    return path.resolve(strict=True)


def _resolved_output(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("output must be a new absolute non-symlink path")
    parent = path.parent.resolve(strict=True)
    return parent / path.name


def _resolved_directory(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("directory input must be an absolute non-symlink path")
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("directory input must identify an existing directory")
    return resolved


def _write_exclusive(path: Path, payload) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short inventory write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _inputs(args):
    manifest, _ = _load_json(_resolved_file(args.manifest))
    scope, scope_sha256 = _load_json(_resolved_file(args.scope))
    submission, _ = _load_json(_resolved_file(args.submission))
    policies = manifest.get("policies") if isinstance(manifest, dict) else None
    expected = policies.get("cohort_source_manifest_sha256") if isinstance(policies, dict) else None
    if scope_sha256 != expected:
        raise ValueError("cohort source file does not match the attested manifest SHA-256")
    return manifest, scope, submission


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seal-ready", "finalize"))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--submission", required=True)
    parser.add_argument("--study-root", required=True)
    parser.add_argument("--operational-db")
    parser.add_argument("--report-root")
    parser.add_argument("--sessions")
    parser.add_argument("--registration")
    parser.add_argument("--attestation-bundle")
    parser.add_argument("--trusted-root")
    parser.add_argument("--source-commit")
    parser.add_argument("--source-ref", default="refs/heads/codex/analysis-credibility-spec")
    parser.add_argument("--registration-output")
    parser.add_argument("--output")
    parser.add_argument("--selection-closed", action="store_true")
    args = parser.parse_args(argv)
    manifest, scope, submission = _inputs(args)
    study_root = Path(args.study_root)
    if not study_root.is_absolute():
        raise ValueError("study root must be absolute")

    if args.action == "seal-ready":
        if not all((args.operational_db, args.report_root, args.sessions)):
            raise ValueError("seal-ready requires --operational-db, --report-root and --sessions")
        sessions_payload, _ = _load_json(_resolved_file(args.sessions))
        sessions = sessions_payload.get("sessions") if isinstance(sessions_payload, dict) else sessions_payload
        validate_sessions(sessions)
        result = seal_ready(
            manifest=manifest,
            scope=scope,
            submission=submission,
            operational_db=_resolved_file(args.operational_db),
            report_root=_resolved_directory(args.report_root),
            sessions=sessions,
            study_root=study_root,
        )
    else:
        if not args.output:
            raise ValueError("finalize requires --output")
        registration = None
        attestation_values = (args.attestation_bundle, args.trusted_root, args.source_commit)
        if any(attestation_values):
            if not all(attestation_values) or args.registration:
                raise ValueError("attestation verification requires bundle, trusted root and source commit only")
            certificate_identity = (
                f"https://github.com/{EXPECTED_REPOSITORY}/.github/workflows/"
                f"oos-register.yml@{args.source_ref}"
            )
            registration = verify_github_registration_attestation(
                manifest_path=_resolved_file(args.manifest),
                bundle_path=_resolved_file(args.attestation_bundle),
                trusted_root_path=_resolved_file(args.trusted_root),
                expected_manifest_sha256=manifest["manifest_sha256"],
                policy=GitHubAttestationPolicy(
                    repository=EXPECTED_REPOSITORY,
                    certificate_identity=certificate_identity,
                    oidc_issuer=GITHUB_ACTIONS_OIDC_ISSUER,
                    source_commit=args.source_commit,
                    source_ref=args.source_ref,
                ),
            )
        elif args.registration:
            registration, _ = _load_json(_resolved_file(args.registration))
        if args.registration_output:
            projection = github_registration_projection(registration)
            if not projection:
                raise ValueError("registration output requires a runtime-verified GitHub attestation")
            _write_exclusive(_resolved_output(args.registration_output), projection)
        result = finalize_inventory(
            manifest=manifest,
            scope=scope,
            submission=submission,
            study_root=study_root,
            registration_evidence=registration,
            selection_closed=args.selection_closed,
        )
        _write_exclusive(_resolved_output(args.output), result)
    print(json.dumps(result if args.action == "seal-ready" else {
        "coverage_status": result["coverage_status"],
        "candidate_count": len(result["candidates"]),
        "inventory_sha256": result["inventory_sha256"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
