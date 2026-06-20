"""Due-report discovery, price evaluation, and performance aggregation."""

from __future__ import annotations

from datetime import date, datetime
from statistics import mean
from typing import Callable

import decision_tracking_store
import report_history_service
from decision_backtest import BACKTEST_HORIZONS, add_calendar_months, evaluate_prediction
from decision_tracking import parse_optional_price
from market_price_history import fetch_backtest_prices


def run_due_backtests(
    *,
    output_dir: str,
    as_of: date | None = None,
    price_fetcher: Callable = fetch_backtest_prices,
) -> dict:
    evaluation_day = as_of or date.today()
    reports = report_history_service.list_reports(
        page=1,
        limit=2000,
        q="",
        pipeline="all",
        recommendation="all",
        data_trust="all",
        include_versions=True,
        output_dir=output_dir,
        report_cache={},
    ).get("reports", [])
    evaluated = []
    skipped = []
    errors = []
    for report in reports:
        generated = _report_date(report)
        if generated is None:
            errors.append({"filename": report.get("filename"), "error": "invalid_report_date"})
            continue
        recommendation = report.get("recommendation") if isinstance(report.get("recommendation"), dict) else {}
        for horizon in BACKTEST_HORIZONS:
            due_date = add_calendar_months(generated, horizon)
            filename = str(report.get("filename") or "")
            if due_date > evaluation_day:
                continue
            if decision_tracking_store.backtest_result_exists(filename, horizon):
                skipped.append({"filename": filename, "horizon_months": horizon, "reason": "already_evaluated"})
                continue
            try:
                prices = price_fetcher(str(report.get("ticker") or ""), generated, due_date)
                target = parse_optional_price(recommendation.get(f"target_{horizon}m"))
                metrics = evaluate_prediction(
                    recommendation=recommendation.get("recommendation", ""),
                    initial_price=prices["initial_price"],
                    actual_price=prices["actual_price"],
                    target_price=target,
                )
                result = {
                    "report_filename": filename,
                    "ticker": report.get("ticker", ""),
                    "pipeline_id": report.get("pipeline_id", "v1"),
                    "horizon_months": horizon,
                    "generated_date": generated.isoformat(),
                    "evaluation_date": str(prices.get("actual_price_date") or due_date.isoformat()),
                    "initial_price": prices["initial_price"],
                    "actual_price": prices["actual_price"],
                    "target_price": target,
                    **metrics,
                }
                decision_tracking_store.upsert_backtest_result(result)
                evaluated.append(result)
            except Exception as exc:
                errors.append({"filename": filename, "horizon_months": horizon, "error": str(exc)[:240]})
    return {
        "success": not errors,
        "evaluated_count": len(evaluated),
        "evaluated": evaluated,
        "skipped": skipped,
        "errors": errors,
    }


def compute_performance_stats() -> dict:
    results = decision_tracking_store.list_backtest_results(limit=2000)
    total = len(results)
    hit_count = sum(1 for row in results if row.get("outcome") == "hit")
    summary = {
        "total_predictions": total,
        "hit_count": hit_count,
        "miss_count": total - hit_count,
        "hit_rate_pct": round(hit_count / total * 100, 2) if total else 0.0,
        "average_strategy_roi_pct": round(mean(float(row.get("strategy_roi_pct") or 0) for row in results), 2) if total else 0.0,
    }
    by_horizon = []
    for horizon in BACKTEST_HORIZONS:
        rows = [row for row in results if int(row.get("horizon_months") or 0) == horizon]
        hits = sum(1 for row in rows if row.get("outcome") == "hit")
        by_horizon.append({
            "horizon_months": horizon,
            "total": len(rows),
            "hit_rate_pct": round(hits / len(rows) * 100, 2) if rows else 0.0,
            "average_strategy_roi_pct": round(mean(float(row.get("strategy_roi_pct") or 0) for row in rows), 2) if rows else 0.0,
        })
    return {"summary": summary, "by_horizon": by_horizon, "details": results[:50]}


def _report_date(report: dict) -> date | None:
    try:
        return datetime.fromisoformat(str(report.get("date") or "")[:16]).date()
    except ValueError:
        return None
