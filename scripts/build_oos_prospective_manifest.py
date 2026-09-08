#!/usr/bin/env python3
"""Build the fixed 28-candidate prospective manifest exactly once."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from oos_research.canonical import canonical_bytes
from oos_research.manifest import build_manifest
from oos_research.policies import DEFAULT_POLICIES, validate_policies


TICKERS = ["1623.TW", "2308.TW", "2367.TW", "3017.TW", "3324.TWO", "3653.TW", "6282.TW"]
PIPELINES = ["v1", "v2", "v3", "v4"]
SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


def build(
    *, source: Path, source_sha256: str, registered_at: str,
    production_parent_commit: str, prompt_fingerprint: str,
    model_route_policy_sha256: str,
) -> dict:
    if source.is_symlink() or not source.is_file():
        raise ValueError("cohort source must be a regular non-symlink file")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source_sha256 or not SHA256_RE.fullmatch(source_sha256):
        raise ValueError("cohort source SHA-256 does not match")
    scope = json.loads(raw)
    jobs = scope.get("jobs") if isinstance(scope, dict) else None
    identities = [(row.get("ticker"), row.get("pipeline_id")) for row in jobs or [] if isinstance(row, dict)]
    expected = [(ticker, pipeline) for ticker in TICKERS for pipeline in PIPELINES]
    if (
        not isinstance(jobs, list)
        or len(jobs) != 28
        or identities != expected
        or scope.get("prepare_only") is not True
        or scope.get("refresh_candidate_count") != 28
    ):
        raise ValueError("cohort source is not the fixed ordered 7 x 4 candidate scope")
    if not COMMIT_RE.fullmatch(production_parent_commit):
        raise ValueError("production parent commit must be a lowercase 40-character Git commit")
    if not SHA256_RE.fullmatch(prompt_fingerprint) or not SHA256_RE.fullmatch(model_route_policy_sha256):
        raise ValueError("runtime fingerprints must be lowercase SHA-256 values")
    policies = {
        **DEFAULT_POLICIES,
        "v2_primary_horizon_trading_days": 5,
        "v2_horizon_source": "report_explicit_and_preregistered",
        "v3_primary_horizon_trading_days": 5,
        "v3_horizon_source": "report_explicit_and_preregistered",
        "cohort_source_manifest_sha256": source_sha256,
        "cohort_candidate_count": 28,
        "candidate_selection": "first_eligible_post_attestation_report_per_ticker_pipeline",
        "selection_window_inclusive": True,
        "source_provenance_coverage_required": "complete",
        "calendar_policy": "explicit_official_twse_sessions",
        "session_open_local_time": "09:00:00",
        "corporate_action_policy": "explicit_unprocessed_allowed",
        "missing_report_policy": "retain_in_denominator",
        "unknown_model_revision_policy": "preserve_and_stratify",
        "artifact_seal_policy": "before_first_post_report_exchange_session",
        "evaluation_revision_policy": "append_only_latest_at_explicit_cutoff",
        "paid_data_sources": "not_added",
    }
    validate_policies(policies)
    return build_manifest(
        schema_version="oos.manifest.v1",
        study_id="four-mode-credibility-prospective-r1",
        study_kind="prospective",
        registered_at=registered_at,
        timezone="Asia/Taipei",
        selection_period={"start": "2026-09-09", "end": "2026-09-11"},
        ticker_universe=TICKERS,
        pipelines=PIPELINES,
        horizons={"v1": [3, 6, 12], "v2": [5], "v3": [5], "v4": [5, 10]},
        policies=policies,
        evaluator_version="oos.evaluator.v1",
        runtime_identity={
            "production_parent_commit": production_parent_commit,
            "prompt_fingerprint": prompt_fingerprint,
            "model_route_policy_sha256": model_route_policy_sha256,
        },
    )


def write_exclusive(output: Path, manifest: dict) -> None:
    if not output.is_absolute() or output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("output must be a new absolute path in an existing directory")
    data = canonical_bytes(manifest) + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(output.parent.resolve() / output.name, flags, 0o644)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short manifest write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--registered-at", required=True)
    parser.add_argument("--production-parent-commit", required=True)
    parser.add_argument("--prompt-fingerprint", required=True)
    parser.add_argument("--model-route-policy-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = build(
        source=args.source,
        source_sha256=args.source_sha256,
        registered_at=args.registered_at,
        production_parent_commit=args.production_parent_commit,
        prompt_fingerprint=args.prompt_fingerprint,
        model_route_policy_sha256=args.model_route_policy_sha256,
    )
    write_exclusive(args.output, manifest)
    print(json.dumps({"manifest_sha256": manifest["manifest_sha256"], "candidate_count": 28}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
