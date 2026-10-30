"""Read-only, offline audit of saved v4 source references; never repairs artifacts.

The index is opened mode=ro and artifacts through ReportArtifactLocator with a
read-only adapter. stdout is the sole output. --code-root selects the exact
implementation being audited, so an isolated repair can be compared to baseline.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import json
from pathlib import Path
import socket
import sqlite3
import sys
from types import SimpleNamespace
from zoneinfo import ZoneInfo


def _deny_network(*args, **kwargs):
    raise OSError("Saved-source audit is offline; provider/runtime access forbidden")


class ReadOnlyArtifacts:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)

    def _path(self, key):
        path = (self.root / key).resolve(strict=False)
        if not path.is_relative_to(self.root):
            raise ValueError("Artifact key escaped the source root")
        return path

    def exists(self, key):
        return self._path(key).is_file()

    def get_report(self, key):
        return SimpleNamespace(content=self._path(key).read_bytes())


def latest_rows(index, output):
    from report_pipeline_identity import resolve_report_pipeline_id
    with sqlite3.connect(Path(index).resolve().as_uri() + "?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT filename,ticker,pipeline_id,report_date FROM reports WHERE output_dir=? ORDER BY report_date DESC,filename DESC,timestamp DESC", (str(Path(output).resolve()),)).fetchall()
    selected, seen = [], set()
    for raw in rows:
        row = dict(raw)
        row["pipeline_id"] = resolve_report_pipeline_id(row["filename"], stored_pipeline=row["pipeline_id"])
        key = (str(row["ticker"]).split(".", 1)[0].lower(), row["pipeline_id"])
        if key not in seen:
            seen.add(key)
            selected.append(row)
    return selected


def original_catalog(snapshot):
    from report_analysis_evidence import validate_analysis_evidence
    from workflow_trade_evidence import trade_manifest_matches_input
    packet = validate_analysis_evidence(snapshot.get("analysis_evidence"))
    sections = packet.get("sections", {})
    manifest = sections.get("trade_source_manifest", {}).get("data", {})
    inputs = sections.get("analysis_input", {}).get("data", {})
    valid = packet.get("input_verification") == "hash_verified" and trade_manifest_matches_input(manifest, inputs)
    return (manifest.get("catalog", {}) if valid else {}), bool(valid)


def _identity(value):
    if not isinstance(value, dict):
        return value
    return {key: value[key] for key in ("path", "value", "unit", "population", "window", "observed_at", "provider", "date", "high", "low", "close", "title", "published_at", "url", "ticker", "threshold") if key in value}


def ref_family(ref):
    if not isinstance(ref, str):
        return "invalid"
    for name in ("institutional_evidence", "ownership_evidence", "recent_news", "event_calendar", "technical_indicators", "daily_market_data"):
        if "." + name + "." in ref:
            return name
    return "other"


def _same_record_paths(catalog, ref, value):
    import re
    match = re.fullmatch(r"(.+)\[\d+\]", str(ref))
    if not match or not isinstance(value, dict):
        return []
    from trade_source_contract import resolve_reference
    records = resolve_reference(catalog, match[1])
    if not isinstance(records, list):
        return []
    return [f"{match[1]}[{i}]" for i, item in enumerate(records) if _identity(item) == _identity(value)]


def classify_reference(ref, current, frozen, frozen_valid, as_of):
    from trade_source_contract import resolve_reference, reference_is_evidence
    now = resolve_reference(current, ref)
    old = resolve_reference(frozen, ref)
    usable = isinstance(ref, str) and reference_is_evidence(current, ref, "catalyst_source_refs")
    original_usable = frozen_valid and isinstance(ref, str) and reference_is_evidence(frozen, ref, "catalyst_source_refs")
    reasons = []
    matches = _same_record_paths(current, ref, old)
    if not usable:
        if not isinstance(ref, str):
            reasons.append("malformed_reference")
        elif original_usable:
            if matches and ref not in matches:
                reasons.append("catalog_index_drift_original_record_still_present")
            else:
                observed = (old.get("observed_at") or old.get("published_at") or old.get("date")) if isinstance(old, dict) else None
                try:
                    age = (as_of - date.fromisoformat(str(observed)[:10])).days
                except ValueError:
                    age = None
                window = 7 if ref_family(ref) == "institutional_evidence" else 14 if ref_family(ref) in {"recent_news", "ownership_evidence"} else None
                if age is not None and age < 0:
                    reasons.append("original_observation_future")
                elif age is not None and window is not None and age > window:
                    reasons.append("original_evidence_expired_current_window")
                else:
                    reasons.append("original_reference_not_in_current_catalog")
        elif not frozen_valid:
            reasons.append("original_catalog_unavailable_or_unbound")
        elif old is None:
            reasons.append("reference_absent_in_bound_original_catalog")
        else:
            reasons.append("bound_original_value_not_admissible")
        if now is not None:
            reasons.append("current_value_not_admissible")
    elif original_usable and _identity(now) != _identity(old):
        reasons.append("same_index_rebound_to_different_record")
    return {"ref": ref, "family": ref_family(ref), "current_usable": bool(usable), "original_usable": bool(original_usable), "reason_codes": reasons, "original_value": _identity(old), "current_value": _identity(now), "same_original_record_current_paths": matches}


def audit_snapshot(row, snapshot, as_of):
    import inspect
    import re
    from unittest.mock import patch
    from trade_catalog_evidence import add_catalog_observations
    from short_term_market_data import build_short_term_market_context
    from reporting.content_credibility_trade_basis import evaluate_trade_basis
    context = {**snapshot.get("rerun_context", {}), "candidate_evaluation_at": as_of.isoformat() + "T23:00:00+08:00"}
    data = snapshot.get("data", {})
    current = {"short_term_market_context": add_catalog_observations(build_short_term_market_context(data, as_of=as_of, compact=True), data)}
    frozen, frozen_valid = original_catalog(snapshot)
    # The explicit audit date governs the baseline projection too. This changes
    # only an in-memory dependency during this single call, never saved code/data.
    with patch("reporting.content_credibility_trade_basis.source_catalog", return_value=current):
        kwargs = {"snapshot": snapshot} if "snapshot" in inspect.signature(evaluate_trade_basis).parameters else {}
        result = evaluate_trade_basis(context, data, row["pipeline_id"], **kwargs)
    blockers = sorted({item.get("id") for item in result.get("blocking_issues", [])})
    saved = snapshot.get("content_credibility", {})
    saved_blockers = {item.get("id") for item in saved.get("blocking_issues", [])}
    setup = context.get("parsed", {}).get("trade_setup", {})
    refs = []
    for field in ("catalyst_source_refs", "observed_source_refs"):
        for ref in setup.get(field, []) if isinstance(setup.get(field), list) else []:
            detail = classify_reference(ref, current, frozen, frozen_valid, as_of)
            if detail["reason_codes"]:
                refs.append({"field": field, **detail})
    reasons = sorted({reason for item in refs for reason in item["reason_codes"]})
    missing_ref_claims = []
    from trade_catalyst_claims import catalyst_observation_text
    for field, refs_field in (("core_catalyst", "catalyst_source_refs"), ("observed_signal", "observed_source_refs")):
        text = str(setup.get(field) or "")
        claim = catalyst_observation_text(text) if field == "core_catalyst" else text
        if (not setup.get(refs_field) and re.search(r"外資|投信|自營商|法人(?!說明會)|大戶", claim)
                and re.search(r"買超|賣超|增持|減持|持股|連續|持續|集中", claim)):
            missing_ref_claims.append({"field": field, "text": claim,
                "interpretation": "unreferenced asserted or ambiguous condition; no automatic prose rewrite"})
    if missing_ref_claims:
        reasons.append("unreferenced_institutional_assertion_or_ambiguous_condition")
    if "v4_trade_reason_source_missing" in blockers and not reasons:
        reasons.append("unclassified_missing_source_requires_review")
    packet = snapshot.get("analysis_evidence", {})
    return {**row, "source_missing_now": "v4_trade_reason_source_missing" in blockers, "source_missing_saved": "v4_trade_reason_source_missing" in saved_blockers, "original_catalog_bound": frozen_valid, "decision_validity_status": snapshot.get("decision_validity_status"), "blocker_codes": blockers, "reason_codes": sorted(set(reasons)), "reference_details": refs, "unreferenced_claims": missing_ref_claims,
            "packet_reason_codes": packet.get("reason_codes", []), "saved_manifest_status": packet.get("sections", {}).get("trade_source_manifest", {}).get("status")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--code-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--as-of", default=datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat())
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(Path(args.code_root) / "backend"))
    socket.socket.connect = _deny_network
    socket.socket.connect_ex = _deny_network
    socket.create_connection = _deny_network
    from report_artifacts import ReportArtifactLocator
    rows = latest_rows(args.index, args.output_root)
    locator = ReportArtifactLocator(ReadOnlyArtifacts(args.output_root))
    results, errors = [], []
    for row in rows:
        if row["pipeline_id"] != "v4":
            continue
        try:
            snapshot = locator.require_bundle(row["filename"]).read_data_snapshot()
            results.append(audit_snapshot(row, snapshot, date.fromisoformat(args.as_of)))
        except Exception as exc:
            errors.append({"filename": row["filename"], "error": type(exc).__name__ + ": " + str(exc)})
    missing = [row for row in results if row["source_missing_now"] or row["source_missing_saved"]]
    counts = Counter(reason for row in missing for reason in row["reason_codes"])
    drift = [row for row in results if any("rebound" in reason or "index_drift" in reason for reason in row["reason_codes"])]
    report = {"as_of": args.as_of, "code_root": args.code_root, "selection_basis": "latest_per_ticker_pipeline", "latest_count": len(rows), "v4_audited": len(results), "errors": errors, "source_missing_now": sum(row["source_missing_now"] for row in results), "source_missing_saved": sum(row["source_missing_saved"] for row in results), "missing_union": len(missing), "reason_report_counts_overlap": dict(counts), "drift_or_rebound_reports": len(drift), "drift_or_rebound_filenames": [row["filename"] for row in drift]}
    report["all_trade_blocker_report_counts_overlap"] = dict(Counter(code for row in results for code in row["blocker_codes"]))
    if args.details:
        report["reports"] = [row for row in results if row["blocker_codes"] or row in missing or row in drift]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
