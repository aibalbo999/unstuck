#!/usr/bin/env python3
"""Verify the prospective manifest attestation offline before cohort submission."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from oos_research.github_attestation import (
    EXPECTED_REPOSITORY,
    GITHUB_ACTIONS_OIDC_ISSUER,
    GitHubAttestationPolicy,
    github_registration_projection,
    load_manifest_sha256,
    verify_github_registration_attestation,
)


DEFAULT_SOURCE_REF = "refs/heads/codex/analysis-credibility-spec"


def _new_output(path: Path) -> Path:
    if not path.is_absolute() or path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("output must be a new absolute path in an existing directory")
    return path.parent.resolve() / path.name


def _write_exclusive(path: Path, payload: dict) -> None:
    data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short verification receipt write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def verify_and_write(
    *, manifest: Path, bundle: Path, trusted_root: Path, source_commit: str,
    source_ref: str, expected_bundle_sha256: str, expected_trusted_root_sha256: str,
    output: Path,
    verifier: Callable = verify_github_registration_attestation,
    projector: Callable = github_registration_projection,
) -> dict:
    output = _new_output(output)
    expected_manifest_sha256 = load_manifest_sha256(manifest)
    certificate_identity = (
        f"https://github.com/{EXPECTED_REPOSITORY}/.github/workflows/"
        f"oos-register.yml@{source_ref}"
    )
    evidence = verifier(
        manifest_path=manifest,
        bundle_path=bundle,
        trusted_root_path=trusted_root,
        expected_manifest_sha256=expected_manifest_sha256,
        policy=GitHubAttestationPolicy(
            repository=EXPECTED_REPOSITORY,
            certificate_identity=certificate_identity,
            oidc_issuer=GITHUB_ACTIONS_OIDC_ISSUER,
            source_commit=source_commit,
            source_ref=source_ref,
            bundle_sha256=expected_bundle_sha256,
            trusted_root_sha256=expected_trusted_root_sha256,
        ),
    )
    projection = projector(evidence)
    if not projection:
        raise RuntimeError("attestation verifier returned no runtime-verified projection")
    _write_exclusive(output, projection)
    return projection


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--attestation-bundle", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path, required=True)
    parser.add_argument("--expected-bundle-sha256", required=True)
    parser.add_argument("--expected-trusted-root-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-ref", default=DEFAULT_SOURCE_REF)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    projection = verify_and_write(
        manifest=args.manifest,
        bundle=args.attestation_bundle,
        trusted_root=args.trusted_root,
        expected_bundle_sha256=args.expected_bundle_sha256,
        expected_trusted_root_sha256=args.expected_trusted_root_sha256,
        source_commit=args.source_commit,
        source_ref=args.source_ref,
        output=args.output,
    )
    receipt = projection["external_registration_receipt"]
    print(json.dumps({
        "manifest_sha256": receipt["manifest_sha256"],
        "source_commit": receipt["source_commit"],
        "verified_at": receipt["verified_at"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
