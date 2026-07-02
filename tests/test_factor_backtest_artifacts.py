from datetime import date

import pytest

from backtest_artifacts import build_backtest_artifact
from factor_store import build_factor_snapshot, factor_snapshot_id


def test_build_factor_snapshot_is_deterministic_and_uses_free_local_inputs():
    prices = [
        {"date": "2026-06-01", "close": 100, "volume": 1000},
        {"date": "2026-06-02", "close": 105, "volume": 1500},
        {"date": "2026-06-03", "close": 110, "volume": 1300},
        {"date": "2026-06-04", "close": 121, "volume": 1800},
    ]
    fundamentals = {
        "roe_pct": 18,
        "free_cash_flow_raw": 120_000_000,
        "net_income_ttm_raw": 100_000_000,
        "pe_ratio_raw": 20,
    }

    snapshot = build_factor_snapshot("2330.TW", prices, fundamentals, as_of=date(2026, 6, 4))

    assert snapshot["schema_version"] == "factor_snapshot.v1"
    assert snapshot["ticker"] == "2330.TW"
    assert snapshot["as_of"] == "2026-06-04"
    assert snapshot["source_mode"] == "free_local"
    assert snapshot["factors"]["momentum_total_pct"] == pytest.approx(21.0)
    assert snapshot["factors"]["quality_score"] > 70
    assert snapshot["factors"]["valuation_pe"] == 20
    assert factor_snapshot_id(snapshot) == factor_snapshot_id(dict(snapshot))


def test_build_backtest_artifact_links_decision_factor_snapshot_and_benchmark():
    factor_snapshot = build_factor_snapshot(
        "AAPL",
        [{"date": "2026-01-01", "close": 100}, {"date": "2026-04-01", "close": 130}],
        {"roe_pct": 25, "free_cash_flow_raw": 10, "net_income_ttm_raw": 8, "pe_ratio_raw": 30},
        as_of=date(2026, 1, 1),
    )
    decision = {
        "decision_id": "report-aapl-v1-20260101",
        "ticker": "AAPL",
        "alpha_model_id": "mode-a-deep-research",
        "recommendation": "買入",
        "generated_date": "2026-01-01",
        "target_price": 125,
    }

    artifact = build_backtest_artifact(
        decision,
        price_path=[{"date": "2026-01-01", "close": 100}, {"date": "2026-04-01", "close": 130}],
        benchmark_path=[{"date": "2026-01-01", "close": 100}, {"date": "2026-04-01", "close": 110}],
        factor_snapshot=factor_snapshot,
    )

    assert artifact["schema_version"] == "backtest_artifact.v1"
    assert artifact["decision_id"] == "report-aapl-v1-20260101"
    assert artifact["alpha_model_id"] == "mode-a-deep-research"
    assert artifact["factor_snapshot_id"] == factor_snapshot_id(factor_snapshot)
    assert artifact["metrics"]["strategy_roi_pct"] == pytest.approx(30)
    assert artifact["metrics"]["benchmark_return_pct"] == pytest.approx(10)
    assert artifact["metrics"]["excess_return_pct"] == pytest.approx(20)
    assert artifact["metrics"]["max_drawdown_pct"] == pytest.approx(0)
