from types import MappingProxyType

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
        lambda _output_dir, **_kwargs: {"items": [{"ticker": "2308.TW", "enabled": True, "decision_priority": "high"}]},
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
    monkeypatch.setattr(
        watchlist_routes.job_observability,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "model_route_budget": {
                "warnings": [
                    {
                        "id": "quality_gate_failures",
                        "route": "v2/gemini-2.5-pro",
                        "message": "quality_gate_failures=1",
                    }
                ]
            }
        },
    )
    monkeypatch.setattr(
        watchlist_routes,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 3,
            "sent_count": 1,
            "failed_count": 2,
            "pending_count": 0,
            "retry_exhausted_count": 1,
            "channel_counts": {"telegram_webhook": 2, "local": 1},
        },
        raising=False,
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
    assert any(item["type"] == "model_route_warning" for item in payload["decision_queue"]["items"])
    delivery_item = next(item for item in payload["decision_queue"]["items"] if item["type"] == "fix_notification_delivery")
    assert delivery_item["failed_count"] == 2
    assert delivery_item["suppress_notification"] is True


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
            {
                "ticker": "2408.TW",
                "company_name": "南亞科",
                "score": 18680.0,
                "reason": "外資買超 15430 張、投信買超 3250 張、自營商 0 張",
                "quality_funnel": {"outcome": "pass"},
            },
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
    assert dashboard["top_candidates"][0] == {
        "ticker": "2408.TW",
        "company_name": "南亞科",
        "score": 18680.0,
        "quality_outcome": "pass",
        "reason": "外資買超 15430 張、投信買超 3250 張、自營商 0 張",
    }
    assert [action["type"] for action in dashboard["actions"][:2]] == ["rerun_report", "run_watchlist"]


def test_daily_decision_dashboard_keeps_monitor_only_notifications_quiet():
    dashboard = build_daily_decision_dashboard(
        reports={"reports": []},
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["status"] == "ok"
    assert dashboard["decision_queue"]["summary"]["total_actionable"] == 0
    assert dashboard["actions"][0]["type"] == "monitor"
    assert dashboard["notification_plan"]["status"] == "quiet"
    assert dashboard["notification_plan"]["messages"] == []


def test_daily_decision_dashboard_returns_full_rerun_report_list():
    reports = {
        "reports": [
            {
                "ticker": "6282.TW",
                "filename": "6282_v4.html",
                "pipeline_id": "v4",
                "decision_freshness": {
                    "requires_rerun": True,
                    "requires_rerun_reason": "資料快照與結論不同步",
                },
            },
            {
                "ticker": "3653.TW",
                "filename": "3653_v1.html",
                "pipeline_id": "v1",
                "analysis_text_stale": True,
                "analysis_text_stale_message": "資料快照已刷新，但報告本文未重跑。",
            },
            {
                "ticker": "2330.TW",
                "filename": "2330_v1.html",
                "pipeline_id": "v1",
                "decision_freshness": {"requires_rerun": False},
            },
        ]
    }

    dashboard = build_daily_decision_dashboard(
        reports=reports,
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["reports_needing_rerun"] == 2
    assert [item["filename"] for item in dashboard["rerun_reports"]] == [
        "6282_v4.html",
        "3653_v1.html",
    ]
    assert dashboard["rerun_reports"][0] == {
        "type": "rerun_report",
        "ticker": "6282.TW",
        "filename": "6282_v4.html",
        "pipeline_id": "v4",
        "title": "6282.TW v4 結論需重跑",
        "detail": "資料快照與結論不同步",
    }


def test_daily_decision_dashboard_accepts_mapping_decision_freshness_for_rerun_bucket():
    dashboard = build_daily_decision_dashboard(
        reports={
            "reports": [
                {
                    "ticker": "6282.TW",
                    "filename": "6282_v4.html",
                    "pipeline_id": "v4",
                    "decision_freshness": MappingProxyType(
                        {
                            "requires_rerun": True,
                            "requires_rerun_reason": "資料快照與結論不同步",
                        }
                    ),
                }
            ]
        },
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["reports_needing_rerun"] == 1
    assert dashboard["rerun_reports"][0]["filename"] == "6282_v4.html"
    assert dashboard["rerun_reports"][0]["detail"] == "資料快照與結論不同步"


def test_daily_decision_dashboard_rerun_report_filename_alias_uses_string_safe_selection():
    class BrokenFilename:
        def __bool__(self):
            raise RuntimeError("filename truthiness unavailable")

        def __str__(self):
            raise RuntimeError("filename text unavailable")

    dashboard = build_daily_decision_dashboard(
        reports={
            "reports": [
                {
                    "ticker": "6282.TW",
                    "filename": BrokenFilename(),
                    "report_filename": "6282_v4.html",
                    "pipeline_id": "v4",
                    "decision_freshness": {
                        "requires_rerun": True,
                        "requires_rerun_reason": "資料快照與結論不同步",
                    },
                }
            ]
        },
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["reports_needing_rerun"] == 1
    assert dashboard["rerun_reports"][0]["filename"] == "6282_v4.html"
    assert dashboard["actions"][0]["filename"] == "6282_v4.html"


def test_daily_decision_dashboard_rerun_reason_uses_string_safe_fallback():
    class BrokenReason:
        def __bool__(self):
            raise RuntimeError("reason truthiness unavailable")

        def __str__(self):
            raise RuntimeError("reason text unavailable")

    dashboard = build_daily_decision_dashboard(
        reports={
            "reports": [
                {
                    "ticker": "6282.TW",
                    "filename": "6282_v4.html",
                    "pipeline_id": "v4",
                    "analysis_text_stale_message": "資料快照已刷新，但報告本文未重跑。",
                    "decision_freshness": {
                        "requires_rerun": True,
                        "requires_rerun_reason": BrokenReason(),
                    },
                }
            ]
        },
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["reports_needing_rerun"] == 1
    assert dashboard["rerun_reports"][0]["detail"] == "資料快照已刷新，但報告本文未重跑。"


def test_daily_decision_dashboard_rerun_flags_use_bool_safe_fallback():
    class BrokenRerunFlag:
        def __bool__(self):
            raise RuntimeError("rerun flag truthiness unavailable")

    dashboard = build_daily_decision_dashboard(
        reports={
            "reports": [
                {
                    "ticker": "6282.TW",
                    "filename": "6282_v4.html",
                    "pipeline_id": "v4",
                    "analysis_text_stale": True,
                    "analysis_text_stale_message": "資料快照已刷新，但報告本文未重跑。",
                    "decision_freshness": {
                        "requires_rerun": BrokenRerunFlag(),
                    },
                }
            ]
        },
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["reports_needing_rerun"] == 1
    assert dashboard["rerun_reports"][0]["detail"] == "資料快照已刷新，但報告本文未重跑。"


def test_daily_decision_dashboard_report_rows_do_not_depend_on_truthiness():
    class FalseyDashboardReports(list):
        def __bool__(self):
            return False

    dashboard = build_daily_decision_dashboard(
        reports={
            "reports": FalseyDashboardReports(
                [
                    {
                        "ticker": "6282.TW",
                        "filename": "6282_v4.html",
                        "pipeline_id": "v4",
                        "decision_freshness": {
                            "requires_rerun": True,
                            "requires_rerun_reason": "資料快照與結論不同步",
                        },
                    }
                ]
            )
        },
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["sampled_reports"] == 1
    assert dashboard["summary"]["reports_needing_rerun"] == 1
    assert dashboard["rerun_reports"][0]["filename"] == "6282_v4.html"


def test_daily_decision_dashboard_report_envelope_uses_mapping_safe_items():
    class MisleadingDashboardReportsEnvelope(dict):
        def get(self, key, default=None):
            return []

    dashboard = build_daily_decision_dashboard(
        reports=MisleadingDashboardReportsEnvelope(
            {
                "reports": [
                    {
                        "ticker": "6282.TW",
                        "filename": "6282_v4.html",
                        "pipeline_id": "v4",
                        "decision_freshness": {
                            "requires_rerun": True,
                            "requires_rerun_reason": "資料快照與結論不同步",
                        },
                    }
                ]
            }
        ),
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["sampled_reports"] == 1
    assert dashboard["summary"]["reports_needing_rerun"] == 1
    assert dashboard["rerun_reports"][0]["filename"] == "6282_v4.html"


def test_daily_decision_dashboard_prioritizes_report_repair_queue_before_watchlist():
    dashboard = build_daily_decision_dashboard(
        reports={
            "reports": [
                {
                    "ticker": "2330.TW",
                    "filename": "2330_blocked.html",
                    "pipeline_id": "v2",
                    "content_credibility": {
                        "status": "blocked",
                        "summary": "目標價與買入建議不一致。",
                    },
                }
            ]
        },
        watchlist={"items": [{"ticker": "2308.TW", "enabled": True, "decision_priority": "high"}]},
        screener={"items": []},
        performance={"summary": {}},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["report_repairs_required"] == 1
    assert dashboard["repair_queue"]["items"][0]["filename"] == "2330_blocked.html"
    assert dashboard["actions"][0]["type"] == "manual_review"
    assert dashboard["actions"][0]["filename"] == "2330_blocked.html"
    assert dashboard["actions"][0]["title"] == "2330.TW v2 內容可信度未通過"


def test_daily_decision_dashboard_blocks_invalid_snapshot_before_rerun():
    dashboard = build_daily_decision_dashboard(
        reports={
            "reports": [
                {
                    "ticker": "2330.TW",
                    "filename": "2330_corrupt.html",
                    "pipeline_id": "v2",
                    "snapshot_integrity": {
                        "status": "invalid",
                        "errors": ["snapshot_hash mismatch"],
                    },
                    "decision_freshness": {"requires_rerun": True},
                }
            ]
        },
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["report_repairs_required"] == 1
    assert dashboard["summary"]["reports_needing_rerun"] == 0
    assert dashboard["repair_queue"]["items"][0]["recommended_action"] == "manual_review"
    assert dashboard["repair_queue"]["items"][0]["blocks_auto_rerun"] is True
    assert dashboard["actions"][0]["type"] == "manual_review"
    assert dashboard["actions"][0]["filename"] == "2330_corrupt.html"


def test_daily_decision_dashboard_excludes_blocked_repairs_from_direct_rerun_bucket():
    dashboard = build_daily_decision_dashboard(
        reports={
            "reports": [
                {
                    "ticker": "2330.TW",
                    "filename": "2330_blocked_stale.html",
                    "pipeline_id": "v2",
                    "content_credibility": {
                        "status": "blocked",
                        "summary": "買入建議與目標價方向互相矛盾。",
                    },
                    "decision_freshness": {
                        "requires_rerun": True,
                        "requires_rerun_reason": "資料快照已刷新，但內容可信度仍未通過。",
                    },
                }
            ]
        },
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["report_repairs_required"] == 1
    assert dashboard["summary"]["reports_needing_rerun"] == 0
    assert dashboard["rerun_reports"] == []
    assert dashboard["actions"][0]["type"] == "manual_review"
    assert dashboard["actions"][0]["filename"] == "2330_blocked_stale.html"


def test_daily_decision_dashboard_rerun_bucket_uses_full_repair_coverage_not_display_limit():
    reports = [
        {
            "ticker": f"100{index}.TW",
            "filename": f"100{index}_blocked.html",
            "pipeline_id": "v1",
            "content_credibility": {
                "status": "blocked",
                "summary": "內容可信度未通過。",
            },
        }
        for index in range(1, 6)
    ]
    reports.append({
        "ticker": "9999.TW",
        "filename": "9999_blocked_stale.html",
        "pipeline_id": "v2",
        "content_credibility": {
            "status": "blocked",
            "summary": "第六份 blocked report 不在顯示上限內。",
        },
        "decision_freshness": {
            "requires_rerun": True,
            "requires_rerun_reason": "資料快照已刷新，但內容仍需人工審核。",
        },
    })

    dashboard = build_daily_decision_dashboard(
        reports={"reports": reports},
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["report_repairs_required"] == 6
    assert len(dashboard["repair_queue"]["items"]) == 5
    assert "9999_blocked_stale.html" not in [item["filename"] for item in dashboard["repair_queue"]["items"]]
    assert dashboard["summary"]["reports_needing_rerun"] == 0
    assert dashboard["rerun_reports"] == []


def test_daily_decision_dashboard_queue_uses_full_repair_coverage_for_backtest_skip():
    reports = [
        {
            "ticker": f"200{index}.TW",
            "filename": f"200{index}_blocked.html",
            "pipeline_id": "v1",
            "content_credibility": {
                "status": "blocked",
                "summary": "內容可信度未通過。",
            },
        }
        for index in range(1, 6)
    ]
    reports.append({
        "ticker": "8888.TW",
        "filename": "8888_blocked_due.html",
        "pipeline_id": "v2",
        "date": "2025-01-01",
        "content_credibility": {
            "status": "blocked",
            "summary": "第六份 blocked report 已到回測期。",
        },
    })

    dashboard = build_daily_decision_dashboard(
        reports={"reports": reports},
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["report_repairs_required"] == 6
    assert len(dashboard["repair_queue"]["items"]) == 5
    assert "8888_blocked_due.html" not in [item["filename"] for item in dashboard["repair_queue"]["items"]]
    assert dashboard["decision_queue"]["summary"]["sources"]["report_repair"] == 6
    assert "backtest_due" not in dashboard["decision_queue"]["summary"]["sources"]


def test_daily_decision_dashboard_includes_outcome_calibration_from_backtests():
    dashboard = build_daily_decision_dashboard(
        reports={
            "reports": [
                {
                    "ticker": "2308.TW",
                    "filename": "2308_low_trust.html",
                    "pipeline_id": "v2",
                    "data_trust": {"status": "partial", "score": 45},
                    "content_credibility": {"status": "passed"},
                    "report_conformance": {"status": "passed"},
                }
            ]
        },
        watchlist={"items": []},
        screener={"items": []},
        performance={
            "summary": {"total_predictions": 1, "hit_rate_pct": 0},
            "details": [
                {
                    "report_filename": "2308_low_trust.html",
                    "ticker": "2308.TW",
                    "pipeline_id": "v2",
                    "horizon_months": 3,
                    "outcome": "miss",
                    "strategy_roi_pct": -9.5,
                    "reason": "buy_thesis_not_met",
                }
            ],
        },
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    calibration = dashboard["outcome_calibration"]
    assert calibration["summary"]["total_evaluated"] == 1
    assert calibration["summary"]["miss_attribution_counts"]["data_quality_issue"] == 1
    assert calibration["details"][0]["quality_signal"]["data_trust_status"] == "partial"


def test_daily_decision_dashboard_performance_envelope_uses_mapping_safe_items():
    class MisleadingDashboardPerformance(dict):
        def get(self, key, default=None):
            if key == "summary":
                return {}
            if key == "details":
                return []
            return default

    dashboard = build_daily_decision_dashboard(
        reports={
            "reports": [
                {
                    "ticker": "NVDA",
                    "filename": "nvda_v2.html",
                    "pipeline_id": "v2",
                    "data_trust": {
                        "status": "partial",
                        "reason_codes": ["provider_sla_critical"],
                    },
                    "content_credibility": {"status": "passed"},
                    "report_conformance": {"status": "passed"},
                }
            ]
        },
        watchlist={"items": []},
        screener={"items": []},
        performance=MisleadingDashboardPerformance(
            {
                "summary": {"total_predictions": 1, "hit_rate_pct": 50},
                "details": [
                    {
                        "ticker": "NVDA",
                        "report_filename": "nvda_v2.html",
                        "pipeline_id": "v2",
                        "horizon_months": 3,
                        "outcome": "miss",
                        "strategy_roi_pct": -9.5,
                        "reason": "buy_thesis_not_met",
                    }
                ],
            }
        ),
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["performance"]["hit_rate_pct"] == 50
    assert dashboard["outcome_calibration"]["summary"]["total_evaluated"] == 1
    assert dashboard["outcome_calibration"]["details"][0]["quality_signal"]["data_trust_status"] == "partial"


def test_daily_decision_dashboard_watchlist_envelope_uses_mapping_safe_items():
    class MisleadingDashboardWatchlist(dict):
        def get(self, key, default=None):
            if key == "items":
                return []
            return default

    dashboard = build_daily_decision_dashboard(
        reports={"reports": []},
        watchlist=MisleadingDashboardWatchlist(
            {
                "items": [
                    {
                        "ticker": "2454.TW",
                        "enabled": True,
                        "decision_priority": "high",
                        "decision_alert": {"reason": "missing_report"},
                    }
                ]
            }
        ),
        screener={"items": []},
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["watchlist_high_priority"] == 1
    assert dashboard["actions"][0]["type"] == "run_watchlist"
    assert dashboard["decision_queue"]["summary"]["sources"]["watchlist"] == 1


def test_daily_decision_dashboard_watchlist_priority_uses_string_safe_filtering():
    class BrokenPriority:
        def __bool__(self):
            raise RuntimeError("priority truthiness unavailable")

        def __str__(self):
            raise RuntimeError("priority text unavailable")

    dashboard = build_daily_decision_dashboard(
        reports={"reports": []},
        watchlist={
            "items": [
                {"ticker": "9999.TW", "enabled": True, "decision_priority": BrokenPriority()},
                {
                    "ticker": "2454.TW",
                    "enabled": True,
                    "decision_priority": "high",
                    "decision_alert": {"reason": "missing_report"},
                },
            ]
        },
        screener={"items": []},
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["watchlist_high_priority"] == 1
    assert dashboard["actions"][0]["type"] == "run_watchlist"
    assert dashboard["decision_queue"]["summary"]["sources"]["watchlist"] == 1


def test_daily_decision_dashboard_screener_envelope_uses_mapping_safe_items():
    class MisleadingDashboardScreener(dict):
        def get(self, key, default=None):
            if key == "items":
                return []
            return default

    dashboard = build_daily_decision_dashboard(
        reports={"reports": []},
        watchlist={"items": []},
        screener=MisleadingDashboardScreener(
            {
                "items": [
                    {
                        "ticker": "2408.TW",
                        "company_name": "南亞科",
                        "score": 18680.0,
                        "reason": "外資買超 15430 張、投信買超 3250 張",
                        "quality_funnel": {"outcome": "pass"},
                    }
                ]
            }
        ),
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["top_candidate_count"] == 1
    assert dashboard["top_candidates"][0]["ticker"] == "2408.TW"
    assert dashboard["actions"][0]["type"] == "review_candidate"
    assert dashboard["decision_queue"]["summary"]["sources"]["screener"] == 1


def test_daily_decision_dashboard_screener_quality_funnel_uses_mapping_safe_filtering():
    dashboard = build_daily_decision_dashboard(
        reports={"reports": []},
        watchlist={"items": []},
        screener={
            "items": [
                {
                    "ticker": "9999.TW",
                    "company_name": "Rejected Co",
                    "score": 99999,
                    "reason": "quality funnel rejected",
                    "quality_funnel": MappingProxyType({"outcome": "reject"}),
                },
                {
                    "ticker": "2408.TW",
                    "company_name": "南亞科",
                    "score": 18680.0,
                    "reason": "外資買超 15430 張、投信買超 3250 張",
                    "quality_funnel": MappingProxyType({"outcome": "pass"}),
                },
            ]
        },
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["top_candidate_count"] == 1
    assert dashboard["top_candidates"][0]["ticker"] == "2408.TW"
    assert dashboard["top_candidates"][0]["quality_outcome"] == "pass"
    assert dashboard["actions"][0]["ticker"] == "2408.TW"


def test_daily_decision_dashboard_screener_quality_outcome_uses_string_safe_filtering():
    class RejectOutcome:
        def __bool__(self):
            raise RuntimeError("quality outcome truthiness unavailable")

        def __str__(self):
            return "reject"

    dashboard = build_daily_decision_dashboard(
        reports={"reports": []},
        watchlist={"items": []},
        screener={
            "items": [
                {
                    "ticker": "9999.TW",
                    "company_name": "Rejected Co",
                    "score": 99999,
                    "reason": "quality funnel rejected",
                    "quality_funnel": {"outcome": RejectOutcome()},
                },
                {
                    "ticker": "2408.TW",
                    "company_name": "南亞科",
                    "score": 18680.0,
                    "reason": "外資買超 15430 張、投信買超 3250 張",
                    "quality_funnel": {"outcome": "pass"},
                },
            ]
        },
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["summary"]["top_candidate_count"] == 1
    assert dashboard["top_candidates"][0]["ticker"] == "2408.TW"
    assert dashboard["actions"][0]["ticker"] == "2408.TW"


def test_daily_decision_dashboard_screener_candidate_text_fields_use_string_safe_fallback():
    class TruthinessBrokenText:
        def __bool__(self):
            raise RuntimeError("text truthiness unavailable")

        def __str__(self):
            return "南亞科"

    class BrokenReason:
        def __bool__(self):
            raise RuntimeError("reason truthiness unavailable")

        def __str__(self):
            raise RuntimeError("reason text unavailable")

    dashboard = build_daily_decision_dashboard(
        reports={"reports": []},
        watchlist={"items": []},
        screener={
            "items": [
                {
                    "ticker": "2408.TW",
                    "company_name": TruthinessBrokenText(),
                    "score": 88,
                    "reason": BrokenReason(),
                    "category": "量價轉強",
                    "quality_funnel": {"outcome": "pass"},
                }
            ]
        },
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["top_candidates"][0]["company_name"] == "南亞科"
    assert dashboard["top_candidates"][0]["reason"] == "量價轉強"
    assert dashboard["actions"][0]["ticker"] == "2408.TW"


def test_daily_decision_dashboard_screener_score_uses_conversion_safe_payload_output():
    class CoercibleScore:
        def __bool__(self):
            raise RuntimeError("score truthiness unavailable")

        def __float__(self):
            return 88.5

    dashboard = build_daily_decision_dashboard(
        reports={"reports": []},
        watchlist={"items": []},
        screener={
            "items": [
                {
                    "ticker": "2408.TW",
                    "company_name": "南亞科",
                    "score": CoercibleScore(),
                    "reason": "量價轉強",
                    "quality_funnel": {"outcome": "pass"},
                }
            ]
        },
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["top_candidates"][0]["score"] == 88.5
    assert dashboard["actions"][0]["score"] == 88.5


def test_daily_decision_dashboard_screener_score_uses_conversion_safe_sorting():
    class BrokenScore:
        def __float__(self):
            raise ValueError("score unavailable")

    dashboard = build_daily_decision_dashboard(
        reports={"reports": []},
        watchlist={"items": []},
        screener={
            "items": [
                {
                    "ticker": "9999.TW",
                    "company_name": "Broken Score",
                    "score": BrokenScore(),
                    "reason": "score provider failed",
                    "quality_funnel": {"outcome": "pass"},
                },
                {
                    "ticker": "2408.TW",
                    "company_name": "南亞科",
                    "score": 88,
                    "reason": "外資買超 15430 張、投信買超 3250 張",
                    "quality_funnel": {"outcome": "pass"},
                },
            ]
        },
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    assert dashboard["top_candidates"][0]["ticker"] == "2408.TW"
    assert dashboard["actions"][0]["ticker"] == "2408.TW"
    assert dashboard["decision_queue"]["summary"]["sources"]["screener"] == 1


def test_daily_decision_dashboard_free_mode_envelope_uses_mapping_safe_items():
    class MisleadingDashboardFreeMode(dict):
        def get(self, key, default=None):
            if key == "enabled":
                return False
            if key == "can_run_without_paid_keys":
                return True
            if key == "violations":
                return []
            return default

    dashboard = build_daily_decision_dashboard(
        reports={"reports": []},
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}, "details": []},
        free_mode=MisleadingDashboardFreeMode(
            {
                "enabled": True,
                "can_run_without_paid_keys": False,
                "violations": ["provider:openai_paid_key_required"],
            }
        ),
    )

    assert dashboard["free_mode"]["enabled"] is True
    assert dashboard["free_mode"]["can_run_without_paid_keys"] is False
    assert dashboard["free_mode"]["violations"] == ["provider:openai_paid_key_required"]
    assert dashboard["actions"][0]["type"] == "fix_free_mode"
    assert dashboard["decision_queue"]["summary"]["sources"]["free_mode"] == 1


def test_daily_decision_dashboard_free_mode_violations_use_string_safe_list():
    class TruthinessBrokenViolations(list):
        def __bool__(self):
            raise RuntimeError("violations truthiness unavailable")

    class Violation:
        def __str__(self):
            return "provider:openai_paid_key_required"

    dashboard = build_daily_decision_dashboard(
        reports={"reports": []},
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}, "details": []},
        free_mode={
            "enabled": True,
            "can_run_without_paid_keys": False,
            "violations": TruthinessBrokenViolations([Violation()]),
        },
    )

    assert dashboard["free_mode"]["violations"] == ["provider:openai_paid_key_required"]
    assert dashboard["actions"][0]["type"] == "fix_free_mode"
    assert dashboard["actions"][0]["violations"] == ["provider:openai_paid_key_required"]


def test_daily_decision_dashboard_free_mode_flags_use_bool_safe_projection():
    class BrokenFlag:
        def __bool__(self):
            raise RuntimeError("free mode flag truthiness unavailable")

    dashboard = build_daily_decision_dashboard(
        reports={"reports": []},
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}, "details": []},
        free_mode={
            "enabled": BrokenFlag(),
            "can_run_without_paid_keys": BrokenFlag(),
            "violations": ["provider:openai_paid_key_required"],
        },
    )

    assert dashboard["free_mode"]["enabled"] is False
    assert dashboard["free_mode"]["can_run_without_paid_keys"] is False
    assert dashboard["actions"][0]["type"] == "fix_free_mode"
    assert dashboard["actions"][0]["violations"] == ["provider:openai_paid_key_required"]


def test_daily_decision_dashboard_includes_provider_impact_ledger():
    dashboard = build_daily_decision_dashboard(
        reports={
            "reports": [
                {
                    "ticker": "NVDA",
                    "filename": "nvda_provider.html",
                    "pipeline_id": "v2",
                    "data_trust": {
                        "status": "partial",
                        "reason_codes": ["provider_sla_critical"],
                        "provider_sla_alerts": [
                            {
                                "source": "market_data",
                                "provider": "yfinance",
                                "alert_level": "critical",
                                "current_status": "unavailable",
                            }
                        ],
                    },
                }
            ]
        },
        watchlist={"items": []},
        screener={"items": []},
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
    )

    ledger = dashboard["provider_impact_ledger"]
    assert ledger["summary"]["reports_with_impacts"] == 1
    assert ledger["summary"]["blocked_reports"] == 1
    assert ledger["items"][0]["filename"] == "nvda_provider.html"


def test_daily_decision_dashboard_exposes_prioritized_decision_queue():
    dashboard = build_daily_decision_dashboard(
        reports={
            "reports": [
                {
                    "ticker": "NVDA",
                    "filename": "nvda_provider.html",
                    "pipeline_id": "v2",
                    "data_trust": {
                        "status": "partial",
                        "reason_codes": ["provider_sla_critical"],
                        "provider_sla_alerts": [
                            {
                                "source": "market_data",
                                "provider": "yfinance",
                                "alert_level": "critical",
                                "current_status": "unavailable",
                            }
                        ],
                    },
                },
                {
                    "ticker": "2308.TW",
                    "filename": "2308_due.html",
                    "pipeline_id": "v1",
                    "date": "2025-01-02",
                    "decision_freshness": {"requires_rerun": True},
                },
            ]
        },
        watchlist={"items": [{"ticker": "2454.TW", "enabled": True, "decision_priority": "high"}]},
        screener={"items": []},
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "model_route_budget": {
                "warnings": [
                    {
                        "id": "quality_gate_failures",
                        "route": "v2/gemini-2.5-pro",
                        "message": "quality_gate_failures=1",
                    }
                ]
            }
        },
    )

    queue = dashboard["decision_queue"]
    assert queue["schema_version"] == "daily_decision_queue.v1"
    assert queue["items"][0]["type"] == "wait_provider_recovery"
    assert [item["type"] for item in dashboard["actions"][:3]] == [
        "wait_provider_recovery",
        "model_route_warning",
        "backtest_due",
    ]
    assert any(item["type"] == "model_route_warning" for item in queue["items"])
