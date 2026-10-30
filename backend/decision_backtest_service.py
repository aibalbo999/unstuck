"""Due-report discovery, price evaluation, and performance aggregation."""

from __future__ import annotations

from performance_sample_context import sample_context

from datetime import date, datetime
from statistics import mean
from typing import Callable

import decision_tracking_store
import report_history_service
import trade_backtest_store
from decision_backtest import BACKTEST_HORIZONS, add_calendar_months, evaluate_prediction
from decision_tracking import parse_optional_price
from market_price_history import fetch_backtest_prices, fetch_backtest_bars
from mode_trade_backtest import evaluate_report_trades, trade_performance_summary
from report_pipeline_identity import resolve_report_pipeline_id


def run_due_backtests(
    *,
    output_dir: str,
    as_of: date | None = None,
    price_fetcher: Callable = fetch_backtest_prices,
    bar_fetcher: Callable = fetch_backtest_bars,
    allow_historical_evaluation: bool = False,
) -> dict:
    if as_of is None:
        from market_evidence_policy import completed_evidence_session
        from zoneinfo import ZoneInfo
        completed = completed_evidence_session(datetime.now(ZoneInfo("Asia/Taipei")))
        if completed is None:
            return {"success": False, "evaluated_count": 0, "evaluated": [], "skipped": [], "errors": [{"reason": "completed_session_unknown"}]}
        evaluation_day = date.fromisoformat(completed)
    else:
        from market_evidence_policy import completed_evidence_session
        from zoneinfo import ZoneInfo
        completed=completed_evidence_session(datetime.now(ZoneInfo("Asia/Taipei")))
        if completed is None:
            return {"success":False,"evaluated_count":0,"evaluated":[],"skipped":[],"errors":[{"reason":"completed_evidence_session_unknown"}]}
        evaluation_day=min(as_of,date.fromisoformat(completed))
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
        from report_publication_identity import read_report_publication_identity, non_prediction_reason
        if not read_report_publication_identity(report, output_dir)["prediction_eligible"]:
            skipped.append({"filename": report.get("filename"), "reason": non_prediction_reason(read_report_publication_identity(report, output_dir))})
            continue
        generated = _report_date(report)
        filename = str(report.get("filename") or "")
        if generated is None:
            skipped.append({"filename": filename, "reason": "invalid_report_date"})
            continue
        pipeline_id = resolve_report_pipeline_id(filename, stored_pipeline=report.get("pipeline_id"))
        if pipeline_id != "v1":
            try:
                trades, trade_skips = evaluate_report_trades(
                    report=report, pipeline_id=pipeline_id, generated=generated, as_of=evaluation_day,
                    output_dir=output_dir, bar_fetcher=bar_fetcher, allow_historical_evaluation=allow_historical_evaluation,
                )
                evaluated.extend(trades)
                skipped.extend(trade_skips)
            except Exception as exc:
                errors.append({"filename": filename, "pipeline_id": pipeline_id, "error": str(exc)[:240]})
            continue
        recommendation = report.get("recommendation") if isinstance(report.get("recommendation"), dict) else {}
        for horizon in BACKTEST_HORIZONS:
            due_date = add_calendar_months(generated, horizon)
            if due_date > evaluation_day:
                continue
            if decision_tracking_store.backtest_result_exists(filename, horizon):
                skipped.append({"filename": filename, "horizon_months": horizon, "reason": "already_evaluated"})
                continue
            try:
                prices = price_fetcher(str(report.get("ticker") or ""), generated, due_date)
                target = parse_optional_price(recommendation.get(f"target_{horizon}m"), target_context=True)
                metrics = evaluate_prediction(
                    recommendation=recommendation.get("recommendation", ""),
                    initial_price=prices["initial_price"],
                    actual_price=prices["actual_price"],
                    target_price=target,
                )
                result = {
                    "report_filename": filename,
                    "ticker": report.get("ticker", ""),
                    "pipeline_id": resolve_report_pipeline_id(
                        filename,
                        stored_pipeline=report.get("pipeline_id"),
                    ),
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
    from legacy_evidence_revisions import run_due_revisions
    revisions = run_due_revisions(output_dir=output_dir, as_of=evaluation_day, bar_fetcher=bar_fetcher)
    return {
        "success": not errors,
        "legacy_evidence_revisions": revisions,
        "evaluated_count": len(evaluated),
        "evaluated": evaluated,
        "skipped": skipped,
        "errors": errors,
    }


def compute_performance_stats(output_dir: str | None = None) -> dict:
    results = decision_tracking_store.list_backtest_results(limit=2000)
    total = len(results)
    hit_count = sum(1 for row in results if row.get("outcome") == "hit")
    summary = {
        **sample_context(results),
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
            **sample_context(rows),
            "horizon_months": horizon,
            "total": len(rows),
            "hit_rate_pct": round(hits / len(rows) * 100, 2) if rows else 0.0,
            "average_strategy_roi_pct": round(mean(float(row.get("strategy_roi_pct") or 0) for row in rows), 2) if rows else 0.0,
        })
    from performance_population import read_all_saved_trades
    trades = read_all_saved_trades() if output_dir else trade_backtest_store.list_results(limit=2000)
    from performance_evidence_quarantine import project_results, quarantine_summary
    trades = project_results(trades)
    return {
        "population": _population_or_unavailable(output_dir, trades),
        "research_validation": __import__("signal_increment_evaluation").validation_manifest(),
        "performance_evidence_quarantine": quarantine_summary(trades),
        "legacy_evidence_revisions": __import__("legacy_evidence_revisions").revision_summary(),
        "summary": summary, "by_horizon": by_horizon,
        "legacy_metric_scope": "calendar_month_predictions",
        "trade_summary": trade_performance_summary(trades),
        "trade_by_horizon": {
            str(horizon): trade_performance_summary([row for row in trades if row.get("horizon_trading_days") == horizon])
            for horizon in sorted({row["horizon_trading_days"] for row in trades})
        },
        "details": sorted([*results, *trades], key=lambda row: str(row.get("evaluation_date") or ""), reverse=True)[:50],
    }


def _report_date(report: dict) -> date | None:
    try:
        return datetime.fromisoformat(str(report.get("date") or "")[:16]).date()
    except ValueError:
        pass
    try:
        timestamp = float(report.get("timestamp") or 0)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    try:
        return datetime.fromtimestamp(timestamp).date()
    except (OSError, OverflowError, ValueError):
        return None


def _population_or_unavailable(output_dir, trades):
    if not output_dir:
        return {"status": "unavailable", "reason": "output_dir_not_provided", "credible_strategy_performance": False}
    from performance_population import indexed_population
    try:
        return indexed_population(output_dir, saved=trades)
    except Exception:
        return {"status": "unavailable", "reason": "population_read_failed", "credible_strategy_performance": False}
