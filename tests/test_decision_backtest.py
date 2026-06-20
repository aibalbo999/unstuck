import sys
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
