"""Read-only indexed Taiwan two-week population; original results remain intact."""
import json
import sqlite3
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from report_index import query_report_metadata
from report_history_storage import storage_for_existing_output_dir
from report_artifacts import ReportArtifactLocator
from backtest_session_contract import session_window
from mode_trade_backtest import trade_performance_summary
from performance_blockers import blocker_summary, net_eligible
from config import REPORT_RETENTION_DAYS


def read_all_saved_trades():
    import decision_tracking_store
    path = Path(decision_tracking_store.DECISION_TRACKING_DB_PATH).resolve()
    if not path.exists():
        return []
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='trade_evaluation_results_v1'").fetchone():
            return []
        return [json.loads(row[0]) for row in conn.execute("SELECT payload_json FROM trade_evaluation_results_v1 ORDER BY evaluation_date DESC,report_filename,horizon_trading_days")]


def indexed_population(output_dir, *, as_of=None, saved=None):
    if as_of is None:
        from two_week_market_eligibility import completed_session
        completed = completed_session(datetime.now(ZoneInfo("Asia/Taipei")))
        if completed is None:
            return {"status": "unavailable", "reason": "completed_session_unknown", "credible_strategy_performance": False}
        as_of = date.fromisoformat(completed)
    saved = read_all_saved_trades() if saved is None else saved
    from performance_evidence_quarantine import project_results
    saved = project_results(saved)
    indexed = []
    page = 1
    while True:
        batch, total = query_report_metadata(page=page, limit=100, pipeline="v4", include_versions=True,
                                            output_dir=output_dir, sync_metadata=False, row_mapper=lambda row: dict(row))
        indexed.extend(batch)
        if len(indexed) >= total:
            break
        if not batch:
            return {"status": "unavailable", "reason": "incomplete_index", "credible_strategy_performance": False}
        page += 1
    lookup = {(r.get("report_filename"), r.get("horizon_trading_days")): r for r in saved}
    storage = storage_for_existing_output_dir(output_dir, None)
    locator = ReportArtifactLocator(storage) if storage else None
    rows = []
    excluded_non_predictions = []
    windows = {}  # Call-local: no stale calendar/as-of state between requests.
    for report in indexed:
        ticker, filename = str(report.get("ticker") or ""), report["filename"]
        if not ticker.endswith((".TW", ".TWO")):
            continue
        from report_publication_identity import (read_report_publication_identity,
                                                read_report_publication_snapshot, non_prediction_reason)
        snapshot = read_report_publication_snapshot(report, output_dir, storage=storage, locator=locator) if storage else None
        identity = read_report_publication_identity(report, output_dir, snapshot=snapshot)
        if not identity["prediction_eligible"]:
            excluded_non_predictions.append({"filename": filename, "reason": non_prediction_reason(identity), "identity": identity})
            continue
        try:
            generated = date.fromisoformat(str(report.get("report_date") or report.get("date"))[:10])
        except ValueError:
            rows.append({"ticker": ticker, "report_filename": filename, "state": "invalid_report_date"})
            continue
        try:
            # Preserve bundle availability semantics without reading/parsing data twice.
            setup = (snapshot.get("rerun_context", {}).get("parsed", {}).get("trade_setup", {})
                     if isinstance(snapshot, dict) and locator and locator.existing_key(filename, kind="html") else {})
        except (OSError, ValueError, TypeError, AttributeError):
            setup = {}
        for horizon in (5, 10):
            key = (generated, horizon)
            if key not in windows:
                windows[key] = session_window(generated, horizon)
            window = windows[key]
            old = lookup.get((filename, horizon))
            if window["status"] != "verified":
                state = window["status"]
            elif window["maturity_date"] > as_of.isoformat():
                state = "not_matured"
            elif old:
                state = old.get("status") or "stored_status_unknown"
            else:
                state = "matured_missing_result" if setup else "execution_plan_unavailable"
            rows.append({"ticker": ticker, "report_filename": filename, "generated_date": generated.isoformat(), "published_at": str(report.get("report_date") or report.get("date") or ""),
                         "horizon_trading_days": horizon, "maturity_date": window.get("maturity_date"),
                         "state": state, "stored_result": old, "window": window})
    # First published version of the 10-session decision is selected BEFORE looking at outcome.
    primary = sorted((r for r in rows if r.get("horizon_trading_days") == 10),
                     key=lambda r: (r["generated_date"], r["published_at"], r["report_filename"]))
    selected, excluded, occupied = [], Counter(), {}
    identities = set()
    for row in primary:
        identity = (row["ticker"], row["generated_date"])
        if identity in identities:
            excluded["same_day_report_version"] += 1
            continue
        identities.add(identity)
        if row["window"]["status"] != "verified":
            excluded["calendar_unavailable"] += 1
            continue
        if row["generated_date"] <= occupied.get(row["ticker"], ""):
            excluded["overlapping_ticker_window"] += 1
            continue
        selected.append(row)
        occupied[row["ticker"]] = row["maturity_date"]
    counts = Counter(r["state"] for r in rows)
    selected_saved = [r["stored_result"] for r in selected if r.get("stored_result") and r["state"] != "not_matured"]
    indexed_files = {r["filename"] for r in indexed}
    orphan_count = sum(r.get("report_filename") not in indexed_files for r in saved if r.get("pipeline_id") == "v4")
    return {"status": "complete_index", "as_of": as_of.isoformat(), "scope": "all_indexed_tw_v4_versions",
            "excluded_non_prediction_count": len(excluded_non_predictions),
            "excluded_non_predictions": excluded_non_predictions,
            "excluded_non_prediction_slots": 2 * len(excluded_non_predictions),
            "denominator_semantics": {
                "kind": "surviving_indexed_reports",
                "retention_days": REPORT_RETENTION_DAYS,
                "retention_basis": "artifact_mtime;expired_html_removes_bundle",
                "fixed_historical_universe": False,
                "cross_period_comparability": "not_established",
            },
            "expected_slots": len(rows), "report_count": len({r["report_filename"] for r in rows}),
            "state_counts": dict(sorted(counts.items())), "orphan_saved_results": orphan_count,
            "primary_horizon_trading_days": 10, "independent_candidate_count": len(selected),
            "independent_state_counts": dict(Counter(r["state"] for r in selected)),
            "excluded_primary_counts": dict(excluded),
            "independent_descriptive_results": trade_performance_summary(selected_saved),
            "comparable_assumed_cost_net_result_count": sum(net_eligible(r) for r in selected),
            "net_result_diagnostics": {"all_indexed_slots": blocker_summary(rows), "primary_nonoverlapping_slots": blocker_summary(selected)},
            "credible_strategy_performance": False,
            "selection_policy": "first version per ticker/day;10-session window;chronological nonoverlap;selection ignores outcome",
            "limitation": "Indexed surviving artifacts are not a historical market universe; saved legacy sessions/prices/costs may be unverified. Independence across different stocks is not established."}
