"""Thin offline replay CLI. It consumes explicit JSON inputs only."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from .admission import evaluate_candidate
from .calendar import calendar_digest
from .canonical import content_hash, require_sha256_pin
from .cli_outputs import close_reservations, reserve_outputs, validate_new_outputs, write_reserved
from .dataset import validate_dataset
from .evaluation import make_evaluation
from .github_attestation import (
    EXPECTED_REPOSITORY,
    GITHUB_ACTIONS_OIDC_ISSUER,
    GitHubAttestationPolicy,
    SHA256_RE,
    verify_github_registration_attestation,
)
from .inventory import validate_inventory_scope
from .manifest import build_manifest
from .official_market_data import validate_session_calendar, verify_official_market_dataset
from .policies import validate_policies
from .prediction import evaluate_a_horizon
from .provenance import classify_study_kind, exchange_date, registration_receipt_projection, verify_registration_receipt
from .records import make_record
from .runner_identity import runner_identity
from .store import StudyStore
from .summary import summarize, summary_markdown
from .trades import evaluate_trade_oos


def _load(path: str) -> dict[str, Any]:
    if not path:
        raise ValueError("all input paths are required")
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("input JSON must be an object")
    return value


def run_replay(
    *,
    root: str,
    manifest_input: str,
    inventory_input: str,
    dataset_input: str,
    session_calendar_input: str | None = None,
    expected_inventory_sha256: str | None = None,
    expected_session_calendar_sha256: str | None = None,
    registration_input: str | None = None,
    registration_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if registration_input and registration_evidence is not None:
        raise ValueError("registration input and process-local evidence are mutually exclusive")
    manifest_data = _load(manifest_input)
    inventory = _load(inventory_input)
    dataset = _load(dataset_input)
    manifest = build_manifest(**manifest_data)
    if registration_evidence is None and registration_input:
        registration_evidence = _load(registration_input)
    inventory_hash = validate_inventory_scope(inventory, manifest=manifest)
    registered_count = manifest["policies"].get("cohort_candidate_count")
    if registered_count is not None:
        require_sha256_pin(inventory_hash, expected_inventory_sha256, label="inventory")
    if manifest["study_kind"] == "prospective":
        registration_reason_set = set(verify_registration_receipt(
            registration_evidence, manifest_sha256=manifest["manifest_sha256"]
        ))
        for candidate in inventory["candidates"]:
            report = candidate.get("report") if isinstance(candidate, Mapping) else None
            if isinstance(report, Mapping) and report.get("analysis_input_cutoff") is not None:
                registration_reason_set.update(verify_registration_receipt(
                    registration_evidence,
                    manifest_sha256=manifest["manifest_sha256"],
                    analysis_input_cutoff=report["analysis_input_cutoff"],
                ))
        registration_reasons = sorted(registration_reason_set)
    else:
        registration_reasons = []
    study_classification = classify_study_kind(
        manifest["study_kind"],
        evidence=registration_evidence,
        manifest_sha256=manifest["manifest_sha256"],
    )
    if registration_reasons and study_classification == "prospective":
        study_classification = "prospective_unverified"
    dataset_hash = validate_dataset(dataset)
    requires_official_dataset = (
        manifest["study_kind"] == "prospective"
        and manifest["policies"].get("calendar_policy") == "explicit_official_twse_sessions"
    )
    if requires_official_dataset and dataset.get("provider") != "TWSE_STOCK_DAY+TPEx_tradingStock":
        raise ValueError("registered prospective study requires an official reconstructed dataset")
    if dataset.get("provider") == "TWSE_STOCK_DAY+TPEx_tradingStock":
        if not session_calendar_input:
            raise ValueError("official dataset session calendar input is required")
        session_calendar = _load(session_calendar_input)
        _, session_calendar_hash = validate_session_calendar(session_calendar)
        require_sha256_pin(
            session_calendar_hash,
            expected_session_calendar_sha256,
            label="session calendar",
        )
        dataset_hash = verify_official_market_dataset(
            dataset,
            inventory=inventory,
            session_calendar=session_calendar,
            dataset_path=dataset_input,
        )
    dataset_inventory_hash = dataset.get("candidate_inventory_sha256")
    if dataset_inventory_hash is not None and dataset_inventory_hash != inventory_hash:
        raise ValueError("dataset candidate inventory hash mismatch")
    policy_hash = validate_policies(manifest["policies"])
    calendar_hash = calendar_digest(dataset["calendar"])
    replay_runner_identity = runner_identity()
    candidates: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    checkpoint_records: list[dict[str, Any]] = []
    checkpoint_created_at = str(dataset["as_of"])
    runtime_identity = manifest.get("runtime_identity")
    expected_prompt_fingerprint = (
        runtime_identity.get("prompt_fingerprint") if isinstance(runtime_identity, Mapping) else None
    )
    expected_model_route_policy_sha256 = (
        runtime_identity.get("model_route_policy_sha256") if isinstance(runtime_identity, Mapping) else None
    )
    session_open_local_time = manifest["policies"].get("session_open_local_time", "09:00:00")
    if registration_evidence is not None:
        checkpoint_records.append(make_record(
            "registration_receipt",
            f"registration-receipt-{dataset_hash}",
            {
                "evidence": registration_receipt_projection(registration_evidence),
                "reason_codes": registration_reasons,
                "study_classification": study_classification,
            },
            created_at=checkpoint_created_at,
        ))
    checkpoint_records.append(make_record(
        "dataset",
        f"dataset-{dataset_hash}",
        dataset,
        created_at=checkpoint_created_at,
    ))
    sessions = [date.fromisoformat(value) for value in dataset["calendar"]]
    for candidate in inventory["candidates"]:
        admission = evaluate_candidate(
            candidate,
            study_kind=manifest["study_kind"],
            registration_evidence=registration_evidence,
            manifest_sha256=manifest["manifest_sha256"],
            timezone_name=manifest["timezone"],
            selection_period=manifest["selection_period"],
            expected_horizons=manifest["horizons"],
            expected_prompt_fingerprint=expected_prompt_fingerprint,
            expected_model_route_policy_sha256=expected_model_route_policy_sha256,
            session_open_local_time=session_open_local_time,
        )
        candidate_row = dict(candidate)
        report_bundle_hash = (
            content_hash(candidate.get("artifacts", {}))
            if isinstance(candidate.get("report"), Mapping)
            else None
        )
        candidate_row.update({"admission_status": admission["status"], "admission_reasons": admission["reason_codes"],
                              "report_bundle_hash": report_bundle_hash})
        candidates.append(candidate_row)
        checkpoint_records.append(make_record(
            "admission",
            f"admission-{candidate['candidate_id']}-{dataset_hash}",
            admission,
            created_at=checkpoint_created_at,
        ))
        if admission["status"] != "admitted":
            continue
        report = candidate["report"]
        ticker = str(report["ticker"])
        rows = dataset["bars"].get(ticker, [])
        closes = {str(row["date"]): row["close"] for row in rows}
        available = exchange_date(report["report_available_at"], manifest["timezone"])
        try:
            first_session = date.fromisoformat(str(candidate["first_session_date"]))
        except (KeyError, ValueError):
            first_session = None
        for horizon in manifest["horizons"].get(report["pipeline_id"], []):
            if report["pipeline_id"] == "v1":
                targets = report.get("targets_by_horizon")
                target_price = targets.get(str(horizon)) if isinstance(targets, Mapping) else report.get("target_price")
                result = evaluate_a_horizon(report_available_date=available, sessions=sessions, closes=closes,
                                            recommendation=report.get("recommendation"), target_price=target_price,
                                            horizon_months=horizon, first_session_date=first_session)
                unit = "months"
            else:
                result = evaluate_trade_oos(bars=rows, generated_date=available, as_of=max(sessions),
                                            direction=report.get("direction"), plan=report.get("plan", {}),
                                            horizon_trading_days=horizon, first_session_date=first_session)
                unit = "trading_days"
            evaluation = make_evaluation(study_id=manifest["study_id"], candidate_id=candidate["candidate_id"],
                                         report_bundle_hash=candidate_row["report_bundle_hash"], horizon_unit=unit,
                                         horizon_value=horizon, evaluator_version=manifest["evaluator_version"],
                                         dataset_hash=dataset_hash, calendar_hash=calendar_hash,
                                         policy_hash=policy_hash, as_of=dataset["as_of"],
                                         result={"pipeline_id": report["pipeline_id"], "ticker": ticker, **result},
                                         run_metadata={"runner_source_sha256": replay_runner_identity["source_sha256"]})
            evaluations.append(evaluation)
            checkpoint_records.append(make_record(
                "evaluation",
                f"evaluation-{evaluation['result_identity']}",
                evaluation,
                created_at=checkpoint_created_at,
            ))
    result = summarize(candidates=candidates, evaluations=evaluations, cutoff=dataset["as_of"])
    summary_record_id = f"summary-{dataset_hash}"
    checkpoint_records.append(make_record(
        "summary", summary_record_id, result, created_at=checkpoint_created_at
    ))
    checkpoint_records.append(make_record(
        "checkpoint",
        f"checkpoint-{dataset_hash}",
        {
            "schema_version": "oos.checkpoint.v1",
            "manifest_hash": manifest["manifest_sha256"],
            "inventory_hash": inventory_hash,
            "dataset_hash": dataset_hash,
            "study_classification": study_classification,
            "registration_reason_codes": registration_reasons,
            "summary_record_id": summary_record_id,
            "runner_identity": replay_runner_identity,
        },
        created_at=checkpoint_created_at,
    ))
    store = StudyStore(root, study_id=str(manifest_data.get("study_id", "")))
    store.register_manifest(manifest)
    for record in checkpoint_records:
        store.put_record(record)
    return {
        "study_id": manifest["study_id"],
        "study_classification": study_classification,
        "registration_reason_codes": registration_reasons,
        "manifest_hash": manifest["manifest_sha256"],
        "inventory_hash": inventory_hash,
        "dataset_hash": dataset_hash,
        "runner_identity": replay_runner_identity,
        "summary": result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an explicitly offline OOS replay")
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--sessions")
    parser.add_argument("--expected-inventory-sha256")
    parser.add_argument("--expected-session-calendar-sha256")
    parser.add_argument("--registration")
    parser.add_argument("--attestation-bundle")
    parser.add_argument("--trusted-root")
    parser.add_argument("--expected-bundle-sha256")
    parser.add_argument("--expected-trusted-root-sha256")
    parser.add_argument("--source-commit")
    parser.add_argument("--source-ref", default="refs/heads/codex/analysis-credibility-spec")
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown-output")
    args = parser.parse_args(argv)
    output_paths = validate_new_outputs(args.output, args.markdown_output)
    reservations = reserve_outputs(output_paths)
    completed = False
    try:
        registration_evidence = None
        attestation_values = (
            args.attestation_bundle,
            args.trusted_root,
            args.expected_bundle_sha256,
            args.expected_trusted_root_sha256,
            args.source_commit,
        )
        if any(attestation_values):
            if not all(attestation_values) or args.registration:
                raise ValueError(
                    "attestation verification requires pinned bundle, trusted root and source commit only"
                )
            manifest = _load(args.manifest)
            certificate_identity = (
                f"https://github.com/{EXPECTED_REPOSITORY}/.github/workflows/"
                f"oos-register.yml@{args.source_ref}"
            )
            registration_evidence = verify_github_registration_attestation(
                manifest_path=Path(args.manifest),
                bundle_path=Path(args.attestation_bundle),
                trusted_root_path=Path(args.trusted_root),
                expected_manifest_sha256=manifest["manifest_sha256"],
                policy=GitHubAttestationPolicy(
                    repository=EXPECTED_REPOSITORY,
                    certificate_identity=certificate_identity,
                    oidc_issuer=GITHUB_ACTIONS_OIDC_ISSUER,
                    source_commit=args.source_commit,
                    source_ref=args.source_ref,
                    bundle_sha256=args.expected_bundle_sha256,
                    trusted_root_sha256=args.expected_trusted_root_sha256,
                ),
            )
        payload = run_replay(
            root=args.root,
            manifest_input=args.manifest,
            inventory_input=args.inventory,
            dataset_input=args.dataset,
            session_calendar_input=args.sessions,
            expected_inventory_sha256=args.expected_inventory_sha256,
            expected_session_calendar_sha256=args.expected_session_calendar_sha256,
            registration_input=args.registration,
            registration_evidence=registration_evidence,
        )
        output_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        markdown_text = summary_markdown(payload["summary"]) if args.markdown_output else None
        write_reserved(reservations[0][2], output_text)
        if args.markdown_output:
            write_reserved(reservations[1][2], markdown_text or "")
        completed = True
    finally:
        close_reservations(reservations, remove=not completed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
