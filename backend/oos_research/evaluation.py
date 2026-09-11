"""Deterministic evaluation envelopes and revision selection."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .canonical import content_hash
from .records import result_identity


def make_evaluation(*, study_id: str, candidate_id: str, report_bundle_hash: str, horizon_unit: str,
                    horizon_value: int, evaluator_version: str, dataset_hash: str, calendar_hash: str,
                    policy_hash: str, as_of: str, result: Mapping[str, Any], revision: int = 1,
                    run_metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    identity = result_identity(study_id=study_id, candidate_id=candidate_id, report_bundle_hash=report_bundle_hash,
                               horizon_unit=horizon_unit, horizon_value=horizon_value,
                               evaluator_version=evaluator_version, dataset_hash=dataset_hash,
                               calendar_hash=calendar_hash, policy_hash=policy_hash, as_of=as_of)
    payload = {
        "schema_version": "oos.evaluation.v1", "result_identity": identity, "study_id": study_id,
        "candidate_id": candidate_id, "report_bundle_hash": report_bundle_hash,
        "horizon_unit": horizon_unit, "horizon_value": horizon_value,
        "evaluator_version": evaluator_version, "dataset_hash": dataset_hash,
        "calendar_hash": calendar_hash, "policy_hash": policy_hash, "as_of": as_of,
        "revision": revision, "result": dict(result),
    }
    payload["deterministic_sha256"] = content_hash(payload)
    if run_metadata:
        payload["run_metadata"] = dict(run_metadata)
    return payload


def validate_evaluation(evaluation: Mapping[str, Any]) -> None:
    required = {"schema_version", "result_identity", "study_id", "candidate_id", "report_bundle_hash",
                "horizon_unit", "horizon_value", "evaluator_version", "dataset_hash", "calendar_hash",
                "policy_hash", "as_of", "revision", "result", "deterministic_sha256"}
    if not required <= set(evaluation):
        raise ValueError("evaluation missing required identity fields")
    body = dict(evaluation)
    body.pop("run_metadata", None)
    expected = body.pop("deterministic_sha256")
    if expected != content_hash(body):
        raise ValueError("evaluation deterministic hash mismatch")
    expected_identity = result_identity(study_id=evaluation["study_id"], candidate_id=evaluation["candidate_id"],
                                        report_bundle_hash=evaluation["report_bundle_hash"],
                                        horizon_unit=evaluation["horizon_unit"], horizon_value=evaluation["horizon_value"],
                                        evaluator_version=evaluation["evaluator_version"], dataset_hash=evaluation["dataset_hash"],
                                        calendar_hash=evaluation["calendar_hash"], policy_hash=evaluation["policy_hash"],
                                        as_of=evaluation["as_of"])
    if expected_identity != evaluation["result_identity"]:
        raise ValueError("evaluation identity mismatch")


def select_latest_revisions(evaluations: Iterable[Mapping[str, Any]], *, cutoff: str | None = None) -> list[Mapping[str, Any]]:
    selected: dict[str, Mapping[str, Any]] = {}
    for evaluation in evaluations:
        validate_evaluation(evaluation)
        if cutoff is not None and str(evaluation["as_of"]) > cutoff:
            continue
        identity = str(evaluation["result_identity"])
        previous = selected.get(identity)
        if previous is None or int(evaluation["revision"]) > int(previous["revision"]):
            selected[identity] = evaluation
        elif int(evaluation["revision"]) == int(previous["revision"]) and evaluation != previous:
            raise ValueError("conflicting evaluation revision")
    return list(selected.values())
