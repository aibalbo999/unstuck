"""Mode routing from stored report contracts to versioned OHLC evaluations."""

from __future__ import annotations

import json
from datetime import date
from statistics import mean

import trade_backtest_store
from final_audit_mode_contracts import (
    v2_position_plan_contract_issues,
    v3_short_setup_contract_issues,
    v4_trade_setup_contract_issues,
)
from recommendation_labels import normalize_recommendation_label
from report_artifacts import ReportArtifactLocator
from report_history_storage import storage_for_existing_output_dir
from trade_path_backtest import FINAL_STATUSES, evaluate_trade_path


def _parsed_snapshot(report: dict, output_dir: str) -> dict:
    storage = storage_for_existing_output_dir(output_dir, None)
    if storage is None:
        return {}
    key = ReportArtifactLocator(storage).existing_key(str(report.get("filename") or ""), kind="data")
    item = storage.get_report(key) if key else None
    if item is None:
        return {}
    snapshot = json.loads(item.content.decode("utf-8"))
    if not isinstance(snapshot, dict):
        raise ValueError("report data snapshot must be an object")
    context = snapshot.get("rerun_context")
    parsed = context.get("parsed") if isinstance(context, dict) else None
    return parsed if isinstance(parsed, dict) else {}


def _recommendation_label(parsed: dict) -> str:
    rec = parsed.get("recommendation") or {}
    return normalize_recommendation_label(rec.get("建議", rec.get("recommendation"))) if isinstance(rec, dict) else "N/A"


def _plan_inputs(pipeline_id: str, parsed: dict) -> tuple[dict | None, tuple[int, ...], str]:
    field = {"v2": "position_plan", "v3": "short_setup", "v4": "trade_setup"}[pipeline_id]
    plan = parsed.get(field)
    if not isinstance(plan, dict) or not plan:
        return None, (), "execution_plan_unavailable"
    if pipeline_id == "v4":
        horizons = (5, 10)
        direction = plan.get("trade_direction")
        inputs = {"direction": direction, "entry_zone": plan.get("entry_zone"),
                  "target_price": plan.get("target_price"), "stop_loss": plan.get("stop_loss")}
    else:
        horizon = plan.get("horizon_trading_days")
        if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 252:
            return None, (), "explicit_trade_horizon_required"
        horizons = (horizon,)
        if pipeline_id == "v2":
            action = plan.get("action")
            if action not in {"進場", "等待"}:
                return None, (), "existing_position_history_required"
            direction = "Short" if _recommendation_label(parsed) == "放空" else "Long"
            inputs = {"direction": "Neutral" if action == "等待" else direction,
                      "entry_zone": plan.get("entry_zone"), "target_price": plan.get("target_price"),
                      "stop_loss": plan.get("stop_loss")}
        else:
            label = _recommendation_label(parsed)
            if label not in {"避免", "放空"}:
                return None, (), "unsupported_execution_action"
            inputs = {"direction": "Short" if label == "放空" else "Neutral",
                      "entry_zone": plan.get("entry_trigger"), "target_price": plan.get("downside_target"),
                      "stop_loss": plan.get("cover_stop")}
    if inputs["direction"] == "Neutral":
        checker = {"v2": v2_position_plan_contract_issues, "v3": v3_short_setup_contract_issues,
                   "v4": v4_trade_setup_contract_issues}[pipeline_id]
        kwargs = {"recommendation": _recommendation_label(parsed)} if pipeline_id in {"v2", "v3"} else {}
        # Observation must mean the same thing at audit and evaluation time;
        # invalid or deferred orders cannot become terminal zero-return cash.
        if checker(plan, **kwargs):
            return None, (), "invalid_observation_contract"
    inputs["transaction_cost"] = plan.get("transaction_cost")
    return inputs, horizons, ""


def evaluate_report_trades(*, report: dict, pipeline_id: str, generated: date, as_of: date, output_dir: str, bar_fetcher) -> tuple[list[dict], list[dict]]:
    filename = str(report.get("filename") or "")
    parsed = _parsed_snapshot(report, output_dir)
    inputs, horizons, issue = _plan_inputs(pipeline_id, parsed)
    if issue:
        return [], [{"filename": filename, "reason": issue}]
    previous = {row["horizon_trading_days"]: row for row in trade_backtest_store.list_results(report_filename=filename)}
    pending = [horizon for horizon in horizons if previous.get(horizon, {}).get("status") not in FINAL_STATUSES]
    skipped = [{"filename": filename, "horizon_trading_days": horizon, "reason": "already_evaluated"}
               for horizon in horizons if horizon not in pending]
    if not pending or generated >= as_of:
        return [], skipped
    bars = bar_fetcher(str(report.get("ticker") or ""), generated, as_of)
    evaluated = []
    for horizon in pending:
        metrics = evaluate_trade_path(**inputs, bars=bars, generated_date=generated, as_of=as_of,
                                      horizon_trading_days=horizon)
        if metrics["status"] == "pending":
            skipped.append({"filename": filename, "horizon_trading_days": horizon, "reason": metrics["reason"]})
            continue
        result = {"report_filename": filename, "ticker": report.get("ticker", ""),
                  "pipeline_id": pipeline_id, "generated_date": generated.isoformat(),
                  "trade_direction": inputs["direction"], **metrics}
        if pipeline_id == "v2":
            result["direction_assumption"] = (
                "explicit_cash_plan" if inputs["direction"] == "Neutral" else
                "recommendation_label" if _recommendation_label(parsed) in {"買入", "放空"} else "legacy_long_default"
            )
        trade_backtest_store.save_result(result)
        evaluated.append(result)
    return evaluated, skipped


def trade_performance_summary(results: list[dict]) -> dict:
    hits = sum(row.get("outcome") == "hit" for row in results)
    misses = sum(row.get("outcome") == "miss" for row in results)
    rois = [row["strategy_roi_pct"] for row in results if row.get("strategy_roi_pct") is not None]
    statuses = {}
    for row in results:
        status = row.get("status", "unknown")
        statuses[status] = statuses.get(status, 0) + 1
    return {"total_evaluations": len(results), "hit_count": hits, "miss_count": misses,
            "unscored_count": len(results) - hits - misses,
            "hit_rate_pct": round(hits / (hits + misses) * 100, 2) if hits + misses else None,
            "average_strategy_roi_pct": round(mean(rois), 4) if rois else None, "status_counts": statuses}
