"""Fixed trust policy types and identifiers for GitHub OIDC attestations."""

from __future__ import annotations

from dataclasses import dataclass
import re


SLSA_PROVENANCE_V1 = "https://slsa.dev/provenance/v1"
GITHUB_ACTIONS_OIDC_ISSUER = "https://token.actions.githubusercontent.com"
EXPECTED_REPOSITORY = "aibalbo999/unstuck"
EXPECTED_SIGNER_WORKFLOW = ".github/workflows/oos-register.yml"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
SAFE_REF_RE = re.compile(r"refs/(?:heads|tags)/[A-Za-z0-9._/-]+")


@dataclass(frozen=True)
class GitHubAttestationPolicy:
    repository: str
    certificate_identity: str
    oidc_issuer: str
    source_commit: str
    source_ref: str
    bundle_sha256: str
    trusted_root_sha256: str
    predicate_type: str = SLSA_PROVENANCE_V1
