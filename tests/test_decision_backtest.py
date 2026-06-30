import sys
import sqlite3
from datetime import date
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_add_calendar_months_clamps_month_end():
    from decision_backtest import add_calendar_months

    assert add_calendar_months(date(2026, 1, 31), 3) == date(2026, 4, 30)
    assert add_calendar_months(date(2024, 2, 29), 12) == date(2025, 2, 28)


@pytest.mark.parametrize(
    ("recommendation", "initial", "actual", "target", "expected_roi", "expected_outcome"),
    [
        ("買入", 100, 125, 120, 25.0, "hit"),
        ("買進", 100, 90, 120, -10.0, "miss"),
        ("強烈放空", 100, 75, 80, 25.0, "hit"),
        ("避免", 100, 115, 90, -15.0, "miss"),
        ("持有", 100, 106, 100, 0.0, "hit"),
        ("持有", 100, 118, 100, 0.0, "miss"),
    ],
)
def test_evaluate_prediction_returns_strategy_roi_and_hit(
    recommendation, initial, actual, target, expected_roi, expected_outcome
):
    from decision_backtest import evaluate_prediction

    result = evaluate_prediction(
        recommendation=recommendation,
        initial_price=initial,
        actual_price=actual,
        target_price=target,
    )

    assert result["strategy_roi_pct"] == pytest.approx(expected_roi)
    assert result["outcome"] == expected_outcome


def test_backtest_store_upserts_once_and_aggregates(monkeypatch, tmp_path):
    import decision_tracking_store

    monkeypatch.setattr(decision_tracking_store, "DECISION_TRACKING_DB_PATH", str(tmp_path / "tracking.sqlite3"))
    decision_tracking_store.reset_decision_tracking_store_for_tests()
    row = {
        "report_filename": "2308_v2_report_20260320_150000.html",
        "ticker": "2308.TW",
        "pipeline_id": "v2",
        "horizon_months": 3,
        "generated_date": "2026-03-20",
        "evaluation_date": "2026-06-20",
        "initial_price": 100,
        "actual_price": 125,
        "target_price": 120,
        "recommendation": "買入",
        "market_return_pct": 25,
        "strategy_roi_pct": 25,
        "target_error_pct": 4.1667,
        "outcome": "hit",
        "reason": "direction_and_target_met",
    }

    decision_tracking_store.upsert_backtest_result(row)
    decision_tracking_store.upsert_backtest_result({**row, "strategy_roi_pct": 99})

    results = decision_tracking_store.list_backtest_results()
    assert len(results) == 1
    assert results[0]["strategy_roi_pct"] == pytest.approx(99)
    assert decision_tracking_store.backtest_result_exists(row["report_filename"], 3) is True


def test_decision_tracking_store_migrates_legacy_sqlite_to_operational_db(monkeypatch, tmp_path):
    import decision_tracking_store

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    legacy_db = cache_dir / "decision_tracking.sqlite3"
    operational_db = cache_dir / "operational.sqlite3"

    with sqlite3.connect(legacy_db) as conn:
        conn.row_factory = sqlite3.Row
        decision_tracking_store._init_schema(conn)
        conn.execute(
            """
            INSERT INTO decision_tracking_items (
                ticker, enabled, last_refresh_date, last_refresh_at,
                last_refresh_status, last_refresh_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2308.TW",
                1,
                "2026-06-29",
                "2026-06-29T15:30:00",
                "ok",
                "legacy item",
                "2026-06-20T10:00:00",
                "2026-06-29T15:30:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO decision_backtest_results (
                report_filename, ticker, pipeline_id, horizon_months,
                generated_date, evaluation_date, initial_price, actual_price,
                target_price, recommendation, market_return_pct, strategy_roi_pct,
                target_error_pct, outcome, reason, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2308_v2_report.html",
                "2308.TW",
                "v2",
                3,
                "2026-03-29",
                "2026-06-29",
                100,
                125,
                120,
                "買入",
                25,
                25,
                4.1667,
                "hit",
                "direction_and_target_met",
                "2026-06-29T16:00:00",
            ),
        )

    monkeypatch.setattr(decision_tracking_store, "DECISION_TRACKING_DB_PATH", str(operational_db))
    monkeypatch.setattr(decision_tracking_store, "LEGACY_DECISION_TRACKING_DB_PATH", legacy_db, raising=False)
    decision_tracking_store.reset_decision_tracking_store_for_tests()

    items = decision_tracking_store.list_items()
    backtests = decision_tracking_store.list_backtest_results()

    assert [item["ticker"] for item in items] == ["2308.TW"]
    assert items[0]["last_refresh_message"] == "legacy item"
    assert [row["report_filename"] for row in backtests] == ["2308_v2_report.html"]
    assert backtests[0]["strategy_roi_pct"] == pytest.approx(25)

    decision_tracking_store.list_items()
    with sqlite3.connect(operational_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM decision_tracking_items").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM decision_backtest_results").fetchone()[0] == 1


def test_run_due_backtests_is_idempotent_and_builds_stats(monkeypatch, tmp_path):
    import decision_tracking_service
    import decision_tracking_store

    monkeypatch.setattr(decision_tracking_store, "DECISION_TRACKING_DB_PATH", str(tmp_path / "tracking.sqlite3"))
    decision_tracking_store.reset_decision_tracking_store_for_tests()
    reports = [{
        "filename": "2308_v2_report_20260320_150000.html",
        "ticker": "2308.TW",
        "pipeline_id": "v2",
        "date": "2026-03-20 15:00",
        "recommendation": {
            "recommendation": "買入",
            "current_price": "NT$100",
            "target_3m": "NT$120",
            "target_6m": "NT$135",
            "target_12m": "NT$150",
        },
    }]
    monkeypatch.setattr(
        decision_tracking_service.report_history_service,
        "list_reports",
        lambda **kwargs: {"reports": reports, "pagination": {}},
    )
    calls = []

    def fake_prices(ticker, generated_date, evaluation_date):
        calls.append((ticker, generated_date, evaluation_date))
        return {
            "initial_price": 100,
            "initial_price_date": "2026-03-20",
            "actual_price": 125,
            "actual_price_date": "2026-06-19",
        }

    first = decision_tracking_service.run_due_backtests(
        output_dir=str(tmp_path), as_of=date(2026, 6, 20), price_fetcher=fake_prices
    )
    second = decision_tracking_service.run_due_backtests(
        output_dir=str(tmp_path), as_of=date(2026, 6, 20), price_fetcher=fake_prices
    )
    stats = decision_tracking_service.compute_tracking_performance_stats(str(tmp_path))

    assert first["evaluated_count"] == 1
    assert second["evaluated_count"] == 0
    assert len(calls) == 1
    assert stats["summary"]["total_predictions"] == 1
    assert stats["summary"]["hit_rate_pct"] == pytest.approx(100)
    assert stats["summary"]["average_strategy_roi_pct"] == pytest.approx(25)
    assert stats["by_horizon"][0]["horizon_months"] == 3


def test_run_due_backtests_uses_timestamp_when_report_date_is_job_id(monkeypatch, tmp_path):
    import decision_tracking_service
    import decision_tracking_store

    monkeypatch.setattr(decision_tracking_store, "DECISION_TRACKING_DB_PATH", str(tmp_path / "tracking.sqlite3"))
    decision_tracking_store.reset_decision_tracking_store_for_tests()
    reports = [{
        "filename": "2493_TW_v4_report_job_feacc8d8b11b.html",
        "ticker": "2493.TW",
        "pipeline_id": "v4",
        "date": "job_feacc8d8b11b",
        "timestamp": 1782652409.7299187,
        "recommendation": {"recommendation": "買入", "target_3m": "NT$120"},
    }]
    monkeypatch.setattr(
        decision_tracking_service.report_history_service,
        "list_reports",
        lambda **kwargs: {"reports": reports, "pagination": {}},
    )
    calls = []

    result = decision_tracking_service.run_due_backtests(
        output_dir=str(tmp_path),
        as_of=date(2026, 6, 29),
        price_fetcher=lambda *args: calls.append(args),
    )

    assert result["errors"] == []
    assert result["evaluated_count"] == 0
    assert calls == []


def test_run_due_backtests_skips_reports_without_generation_date(monkeypatch, tmp_path):
    import decision_tracking_service
    import decision_tracking_store

    monkeypatch.setattr(decision_tracking_store, "DECISION_TRACKING_DB_PATH", str(tmp_path / "tracking.sqlite3"))
    decision_tracking_store.reset_decision_tracking_store_for_tests()
    reports = [{
        "filename": "legacy_report.html",
        "ticker": "2493.TW",
        "pipeline_id": "v4",
        "date": "job_without_timestamp",
        "recommendation": {"recommendation": "買入", "target_3m": "NT$120"},
    }]
    monkeypatch.setattr(
        decision_tracking_service.report_history_service,
        "list_reports",
        lambda **kwargs: {"reports": reports, "pagination": {}},
    )

    result = decision_tracking_service.run_due_backtests(
        output_dir=str(tmp_path),
        as_of=date(2026, 6, 29),
        price_fetcher=lambda *args: pytest.fail("missing-date reports should not fetch prices"),
    )

    assert result["errors"] == []
    assert result["skipped"] == [{"filename": "legacy_report.html", "reason": "invalid_report_date"}]
