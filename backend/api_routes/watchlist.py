"""Watchlist routes for scheduled batch analysis."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

import market_screener
import decision_tracking_service
import job_observability
from daily_decision_dashboard import build_daily_decision_dashboard
from free_mode_contract import build_free_mode_contract
from notification_delivery_audit import get_delivery_audit_summary
from portfolio_risk import analyze_portfolio_csv
import report_history_service
from symbol_tools import parse_watchlist_import, suggest_symbols
import watchlist_service


def _screener_status_message(result: dict) -> str:
    for warning in result.get("warnings") or []:
        if isinstance(warning, dict) and warning.get("message"):
            return f"市場掃描資料源暫無可用資料：{warning.get('message')}"
    for error in result.get("errors") or []:
        if isinstance(error, dict) and error.get("error"):
            return f"市場掃描資料源暫無可用資料：{error.get('error')}"
    if result.get("skipped"):
        return "市場掃描已略過。"
    return "市場掃描暫無可用候選股。"


def _renderable_screener_result(result: dict) -> dict:
    scan_success = bool(result.get("success", True))
    if scan_success:
        return {**result, "scan_success": True}
    return {
        **result,
        "success": True,
        "scan_success": False,
        "message": str(result.get("message") or _screener_status_message(result)),
    }


@dataclass(frozen=True)
class WatchlistRouteDeps:
    get_output_dir: Callable[[], str]
    get_task_queue: Callable[[], Any]
    run_stock_analysis_job: Callable[[str, str, str], str]
    create_job: Callable[[str, str], str]
    find_active_job: Callable[[str, str], dict]
    require_mutation_authorized: Callable[[Request], None]


def create_watchlist_router(deps: WatchlistRouteDeps) -> APIRouter:
    router = APIRouter(prefix="/api/watchlist")

    @router.get("")
    async def get_watchlist():
        return await asyncio.to_thread(
            watchlist_service.list_watchlist_with_report_alerts,
            deps.get_output_dir(),
        )

    @router.get("/screener")
    async def get_market_screener_watchlist(
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        category: list[str] | None = Query(None),
        min_score: float | None = Query(None),
        fundamental_revenue_growth_yoy_min: float | None = Query(None),
        fundamental_revenue_growth_yoy_max: float | None = Query(None),
        technical_rsi_min: float | None = Query(None),
        technical_rsi_max: float | None = Query(None),
        technical_macd_min: float | None = Query(None),
        technical_macd_histogram_min: float | None = Query(None),
        institutional_foreign_net_buy_min: float | None = Query(None),
        institutional_investment_trust_net_buy_min: float | None = Query(None),
        institutional_dealer_net_buy_min: float | None = Query(None),
        institutional_total_net_buy_min: float | None = Query(None),
        sort_by: str = Query("score", max_length=48),
        sort_direction: str = Query("desc", pattern="^(asc|desc)$"),
    ):
        filters = {
            "categories": category or [],
            "min_score": min_score,
            "fundamental": {
                "revenue_growth_yoy_pct_min": fundamental_revenue_growth_yoy_min,
                "revenue_growth_yoy_pct_max": fundamental_revenue_growth_yoy_max,
            },
            "technical": {
                "rsi_min": technical_rsi_min,
                "rsi_max": technical_rsi_max,
                "macd_min": technical_macd_min,
                "macd_histogram_min": technical_macd_histogram_min,
            },
            "institutional": {
                "foreign_net_buy_shares_min": institutional_foreign_net_buy_min,
                "investment_trust_net_buy_shares_min": institutional_investment_trust_net_buy_min,
                "dealer_net_buy_shares_min": institutional_dealer_net_buy_min,
                "total_net_buy_shares_min": institutional_total_net_buy_min,
            },
        }
        return await asyncio.to_thread(
            market_screener.list_auto_screener_watchlist,
            deps.get_output_dir(),
            filters=filters,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )

    @router.get("/symbols")
    async def suggest_watchlist_symbols(
        q: str = Query("", max_length=48),
        limit: int = Query(10, ge=1, le=25),
    ):
        return suggest_symbols(q, limit=limit)

    @router.get("/daily-dashboard")
    async def get_daily_decision_dashboard():
        output_dir = deps.get_output_dir()
        reports, watchlist, screener, performance, ops, notification_delivery = await asyncio.gather(
            asyncio.to_thread(
                report_history_service.list_reports,
                page=1,
                limit=20,
                q="",
                pipeline="all",
                recommendation="all",
                data_trust="all",
                include_versions=False,
                output_dir=output_dir,
                report_cache={},
            ),
            asyncio.to_thread(watchlist_service.list_watchlist_with_report_alerts, output_dir, sync_metadata=False),
            asyncio.to_thread(market_screener.list_auto_screener_watchlist, output_dir, limit=20, offset=0, sync_metadata=False),
            asyncio.to_thread(decision_tracking_service.compute_tracking_performance_stats, output_dir),
            asyncio.to_thread(job_observability.build_ops_dashboard_snapshot, completed_limit=200, telemetry_limit=5000),
            asyncio.to_thread(get_delivery_audit_summary),
        )
        ops = {**(ops if isinstance(ops, dict) else {}), "notification_delivery": notification_delivery}
        return build_daily_decision_dashboard(
            reports=reports,
            watchlist=watchlist,
            screener=screener,
            performance=performance,
            free_mode=build_free_mode_contract(),
            ops=ops,
        )

    @router.post("/portfolio/risk")
    async def analyze_portfolio_risk(request: Request):
        deps.require_mutation_authorized(request)
        payload = await request.json()
        csv_text = str((payload or {}).get("csv") or "") if isinstance(payload, dict) else ""
        thesis_health = (payload or {}).get("thesis_health") if isinstance(payload, dict) else {}
        if not csv_text.strip():
            raise HTTPException(status_code=400, detail="csv is required")
        return await asyncio.to_thread(
            analyze_portfolio_csv,
            csv_text,
            thesis_health=thesis_health if isinstance(thesis_health, dict) else {},
        )

    @router.post("/import")
    async def import_watchlist_items(request: Request):
        deps.require_mutation_authorized(request)
        payload = await request.json()
        text = str((payload or {}).get("text") or (payload or {}).get("csv") or "") if isinstance(payload, dict) else ""
        if not text.strip():
            raise HTTPException(status_code=400, detail="text is required")
        parsed = parse_watchlist_import(text)
        imported = []
        errors = list(parsed.get("errors") or [])
        for item in parsed.get("items") or []:
            try:
                await asyncio.to_thread(watchlist_service.upsert_watchlist_item, item)
                imported.append(item)
            except ValueError as exc:
                errors.append({"ticker": item.get("ticker"), "error": str(exc)})
        return {
            "success": not errors,
            "imported_count": len(imported),
            "items": imported,
            "errors": errors,
            "watchlist": await asyncio.to_thread(watchlist_service.list_watchlist),
        }

    @router.post("/screener/run")
    async def run_market_screener(request: Request):
        deps.require_mutation_authorized(request)
        payload = await request.json()
        force = bool(payload.get("force")) if isinstance(payload, dict) else False
        result = await asyncio.to_thread(market_screener.run_daily_market_screener, force=force)
        return _renderable_screener_result(result)

    @router.post("")
    async def upsert_watchlist_item(request: Request):
        deps.require_mutation_authorized(request)
        payload = await request.json()
        try:
            return await asyncio.to_thread(watchlist_service.upsert_watchlist_item, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.delete("/{ticker}")
    async def delete_watchlist_item(
        request: Request,
        ticker: str,
        pipeline: str = Query("all", max_length=24),
    ):
        deps.require_mutation_authorized(request)
        return await asyncio.to_thread(watchlist_service.delete_watchlist_item, ticker, pipeline)

    @router.get("/due")
    async def get_due_watchlist_items():
        return {"items": await asyncio.to_thread(watchlist_service.due_watchlist_items)}

    @router.post("/run")
    async def run_watchlist_items(request: Request):
        deps.require_mutation_authorized(request)
        payload = await request.json()
        requested = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(requested, list):
            requested = [
                item for item in watchlist_service.list_watchlist().get("items", [])
                if item.get("enabled")
            ]
        return await asyncio.to_thread(
            watchlist_service.enqueue_watchlist_items,
            requested,
            create_job=deps.create_job,
            find_active_job=deps.find_active_job,
            task_queue=deps.get_task_queue(),
            run_stock_analysis_job=deps.run_stock_analysis_job,
        )

    return router
