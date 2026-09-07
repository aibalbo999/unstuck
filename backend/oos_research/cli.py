"""Thin offline replay CLI. It consumes explicit JSON inputs only."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from .admission import evaluate_candidate
from .calendar import calendar_digest
from .canonical import content_hash
from .dataset import validate_dataset
from .evaluation import make_evaluation
from .inventory import validate_inventory
from .manifest import build_manifest
from .policies import validate_policies
from .prediction import evaluate_a_horizon
from .records import make_record
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


def run_replay(*, root: str, manifest_input: str, inventory_input: str, dataset_input: str) -> dict[str, Any]:
    manifest_data = _load(manifest_input)
    inventory = _load(inventory_input)
    dataset = _load(dataset_input)
    store = StudyStore(root, study_id=str(manifest_data.get("study_id", "")))
    manifest = build_manifest(**manifest_data)
    store.register_manifest(manifest)
    inventory_hash = validate_inventory(inventory)
    dataset_hash = validate_dataset(dataset)
    policy_hash = validate_policies(manifest["policies"])
    calendar_hash = calendar_digest(dataset["calendar"])
    candidates: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    sessions = [date.fromisoformat(value) for value in dataset["calendar"]]
    for candidate in inventory["candidates"]:
        admission = evaluate_candidate(candidate, study_kind=manifest["study_kind"])
        candidate_row = dict(candidate)
        candidate_row.update({"admission_status": admission["status"], "admission_reasons": admission["reason_codes"],
                              "report_bundle_hash": content_hash(candidate.get("artifacts", {}))})
        candidates.append(candidate_row)
        store.put_record(make_record("admission", candidate["candidate_id"], admission, created_at=manifest["registered_at"]))
        if admission["status"] != "admitted":
            continue
        report = candidate["report"]
        ticker = str(report["ticker"])
        rows = dataset["bars"].get(ticker, [])
        closes = {str(row["date"]): row["close"] for row in rows}
        available = date.fromisoformat(str(report["report_available_at"])[:10])
        for horizon in manifest["horizons"].get(report["pipeline_id"], []):
            if report["pipeline_id"] == "v1":
                result = evaluate_a_horizon(report_available_date=available, sessions=sessions, closes=closes,
                                            recommendation=report.get("recommendation"), target_price=report.get("target_price"),
                                            horizon_months=horizon)
                unit = "months"
            else:
                result = evaluate_trade_oos(bars=rows, generated_date=available, as_of=max(sessions),
                                            direction=report.get("direction"), plan=report.get("plan", {}),
                                            horizon_trading_days=horizon)
                unit = "trading_days"
            evaluation = make_evaluation(study_id=manifest["study_id"], candidate_id=candidate["candidate_id"],
                                         report_bundle_hash=candidate_row["report_bundle_hash"], horizon_unit=unit,
                                         horizon_value=horizon, evaluator_version=manifest["evaluator_version"],
                                         dataset_hash=dataset_hash, calendar_hash=calendar_hash,
                                         policy_hash=policy_hash, as_of=dataset["as_of"],
                                         result={"pipeline_id": report["pipeline_id"], "ticker": ticker, **result})
            evaluations.append(evaluation)
            store.put_record(make_record("evaluation", f"{candidate['candidate_id']}-{unit}-{horizon}", evaluation,
                                         created_at=manifest["registered_at"]))
    result = summarize(candidates=candidates, evaluations=evaluations, cutoff=dataset["as_of"])
    store.put_record(make_record("summary", "summary", result, created_at=manifest["registered_at"]))
    return {"study_id": manifest["study_id"], "manifest_hash": manifest["manifest_sha256"],
            "inventory_hash": inventory_hash, "dataset_hash": dataset_hash, "summary": result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an explicitly offline OOS replay")
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown-output")
    args = parser.parse_args(argv)
    payload = run_replay(root=args.root, manifest_input=args.manifest, inventory_input=args.inventory, dataset_input=args.dataset)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.markdown_output:
        Path(args.markdown_output).write_text(summary_markdown(payload["summary"]), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
