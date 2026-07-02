from daily_decision_dashboard import build_daily_decision_dashboard


def test_watchlist_daily_dashboard_route(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import api_routes.watchlist as watchlist_routes
    from api_routes.watchlist import WatchlistRouteDeps, create_watchlist_router

    monkeypatch.setattr(
        watchlist_routes.report_history_service,
        "list_reports",
        lambda **_kwargs: {"reports": [{"ticker": "2330.TW", "decision_freshness": {"requires_rerun": True}}]},
    )
    monkeypatch.setattr(
        watchlist_routes.watchlist_service,
        "list_watchlist_with_report_alerts",
        lambda _output_dir: {"items": [{"ticker": "2308.TW", "enabled": True, "decision_priority": "high"}]},
    )
    monkeypatch.setattr(
        watchlist_routes.market_screener,
        "list_auto_screener_watchlist",
        lambda _output_dir, **_kwargs: {"items": [{"ticker": "2454.TW", "score": 90}]},
    )
    monkeypatch.setattr(
        watchlist_routes.decision_tracking_service,
        "compute_tracking_performance_stats",
        lambda _output_dir: {"summary": {"hit_rate_pct": 50}},
    )

    app = FastAPI()
    app.include_router(create_watchlist_router(WatchlistRouteDeps(
        get_output_dir=lambda: str(tmp_path),
        get_task_queue=lambda: None,
        run_stock_analysis_job=lambda *_args: "task-id",
        create_job=lambda *_args: "job-id",
        find_active_job=lambda *_args: {},
        require_mutation_authorized=lambda _request: None,
    )))

    response = TestClient(app).get("/api/watchlist/daily-dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["reports_needing_rerun"] == 1
    assert payload["summary"]["watchlist_high_priority"] == 1
    assert payload["performance"]["hit_rate_pct"] == 50


def test_daily_decision_dashboard_prioritizes_reruns_watchlist_and_free_mode():
    reports = {
        "reports": [
            {
                "ticker": "2330.TW",
                "filename": "2330_report.html",
                "pipeline_id": "v1",
                "decision_freshness": {"requires_rerun": True},
                "data_trust": {"status": "fresh"},
            },
            {
                "ticker": "AAPL",
                "filename": "aapl_report.html",
                "pipeline_id": "v2",
                "data_trust": {"status": "partial"},
            },
        ]
    }
    watchlist = {
        "items": [
            {
                "ticker": "2308.TW",
                "enabled": True,
                "decision_priority": "high",
                "decision_alert": {"reason": "missing_report"},
            }
        ]
    }
    screener = {
        "items": [
            {"ticker": "2454.TW", "score": 91, "quality_funnel": {"outcome": "pass"}},
            {"ticker": "9999.TW", "score": 88, "quality_funnel": {"outcome": "reject"}},
        ]
    }
    performance = {
        "summary": {
            "total_predictions": 12,
            "hit_rate_pct": 58.33,
            "average_strategy_roi_pct": 6.2,
        }
    }
    free_mode = {
        "enabled": True,
        "can_run_without_paid_keys": True,
        "violations": [],
    }

    dashboard = build_daily_decision_dashboard(
        reports=reports,
        watchlist=watchlist,
        screener=screener,
        performance=performance,
        free_mode=free_mode,
    )

    assert dashboard["status"] == "action_required"
    assert dashboard["free_mode"]["can_run_without_paid_keys"] is True
    assert dashboard["summary"]["reports_needing_rerun"] == 1
    assert dashboard["summary"]["watchlist_high_priority"] == 1
    assert dashboard["performance"]["hit_rate_pct"] == 58.33
    assert [item["ticker"] for item in dashboard["top_candidates"]] == ["2454.TW"]
    assert [action["type"] for action in dashboard["actions"][:2]] == ["rerun_report", "run_watchlist"]
