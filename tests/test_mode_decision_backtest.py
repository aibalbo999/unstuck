"""Mode-specific backtests use isolated fixtures, never provider prices."""

from datetime import date, timedelta

import pytest


def test_avoid_has_cash_return_instead_of_synthetic_short_profit():
    from decision_backtest import evaluate_prediction

    result = evaluate_prediction(recommendation="避免", initial_price=100, actual_price=80)
    assert result["strategy_roi_pct"] == 0
    assert result["position_assumption"] == "cash_no_position_zero_interest"
    assert result["market_return_pct"] == -20


def test_hold_retains_the_existing_long_position_return():
    from decision_backtest import evaluate_prediction

    result = evaluate_prediction(recommendation="持有", initial_price=100, actual_price=125)
    assert result["strategy_roi_pct"] == 25
    assert result["position_assumption"] == "existing_long_position"


def test_calibration_does_not_invent_excess_return_or_drawdown():
    from outcome_calibration import build_outcome_calibration

    ledger = build_outcome_calibration(backtests=[{
        "report_filename": "sample_v4.html", "pipeline_id": "v4",
        "horizon_trading_days": 5, "outcome": "hit", "strategy_roi_pct": 10,
    }], reports=[])
    detail = ledger["details"][0]
    assert detail["excess_return_pct"] is None
    assert detail["max_drawdown_pct"] is None
    model = next(iter(ledger["strategy_evaluation"]["models"].values()))
    assert model["average_excess_return_pct"] is None
    assert model["worst_max_drawdown_pct"] is None


def test_calibration_keeps_non_trade_outcomes_out_of_hit_rate():
    from outcome_calibration import build_outcome_calibration

    ledger = build_outcome_calibration(backtests=[
        {"pipeline_id": "v4", "outcome": "hit", "strategy_roi_pct": 10},
        {"pipeline_id": "v4", "outcome": None, "status": "ambiguous", "strategy_roi_pct": None},
        {"pipeline_id": "v4", "outcome": None, "status": "not_entered", "strategy_roi_pct": 0},
    ], reports=[])
    assert ledger["summary"]["hit_rate_pct"] == 100
    assert ledger["summary"]["miss_count"] == 0
    assert ledger["summary"]["unscored_count"] == 2
    assert ledger["details"][1]["miss_attribution"] == "not_evaluated"


def test_temporal_memory_filters_same_ticker_and_mode(monkeypatch, tmp_path):
    import temporal_memory_service as service

    rows = [
        {"filename": "2330_v2_older.html", "ticker": "2330.TW", "pipeline_id": "v2", "date": "2026-08-01"},
        {"filename": "2330_v4_newer.html", "ticker": "2330.TW", "pipeline_id": "v4", "date": "2026-09-01"},
        {"filename": "2330other_v2.html", "ticker": "2330.OTHER", "pipeline_id": "v2", "date": "2026-09-02"},
    ]
    monkeypatch.setattr(service.report_history_service, "list_reports", lambda **kwargs: {"reports": rows})
    monkeypatch.setattr(service, "_list_backtests_for_temporal_memory", lambda filename: [])
    memory = service.build_temporal_memory("2330.TW", pipeline_id="v2", output_dir=str(tmp_path))
    assert memory["previous_report"]["filename"] == "2330_v2_older.html"
    assert service.build_temporal_memory("2330.TW", output_dir=str(tmp_path)) == {}


def test_valuation_memory_reads_canonical_roi_and_outcome():
    from temporal_memory_service import build_valuation_memory_slice

    memory = build_valuation_memory_slice({"backtests": [{"strategy_roi_pct": -8, "outcome": "miss"}]})
    assert memory["latest_backtest_roi"] == -8
    assert memory["latest_backtest_hit"] is False


def _bars(count=10):
    days = []
    day = date(2026, 1, 2)
    while len(days) < count:
        if day.weekday() < 5:
            days.append({"date": day.isoformat(), "open": 100, "high": 102, "low": 98, "close": 100})
        day += timedelta(days=1)
    return days


def _evaluate(bars, **kwargs):
    import importlib.util

    assert importlib.util.find_spec("trade_path_backtest") is not None, "OHLC evaluator is required"
    from trade_path_backtest import evaluate_trade_path

    return evaluate_trade_path(
        bars=bars, generated_date=date(2026, 1, 1), as_of=date(2026, 2, 1),
        **{"direction": "Long", "entry_zone": "100", "target_price": "110", "stop_loss": "90", "horizon_trading_days": 5, **kwargs},
    )


@pytest.mark.parametrize(("high", "low", "status", "roi"), [
    (112, 98, "target_first", 10),
    (102, 88, "stop_first", -10),
    (112, 88, "ambiguous", None),
])
def test_trade_path_uses_ohlc_first_touch_not_final_close(high, low, status, roi):
    bars = _bars()
    bars[1].update(high=high, low=low, close=100)
    result = _evaluate(bars)
    assert result["status"] == status
    assert result["strategy_roi_pct"] == roi
    assert result["horizon_trading_days"] == 5
    assert result["horizon_months"] is None


def test_trade_path_distinguishes_not_entered_missing_ohlc_and_not_due():
    assert _evaluate(_bars(), entry_zone="95")["status"] == "not_entered"
    missing = _bars()
    missing[0].pop("high")
    result = _evaluate(missing)
    assert result["status"] == "insufficient_data"
    assert result["strategy_roi_pct"] is None
    assert _evaluate(_bars(4))["status"] == "pending"


def test_trade_path_short_and_gap_stop_preserve_direction_and_slippage():
    bars = _bars()
    bars[1].update(open=115, high=117, low=112, close=114)
    result = _evaluate(bars, direction="Short", target_price="90", stop_loss="110")
    assert result["status"] == "stop_first"
    assert result["exit_price"] == 115
    assert result["strategy_roi_pct"] == -15


def test_trade_path_refuses_to_invent_order_after_intraday_entry():
    bars = _bars()
    bars[0].update(open=105, high=112, low=98, close=108)
    result = _evaluate(bars)
    assert result["status"] == "ambiguous"
    assert result["reason"] == "entry_exit_order_unknown"


def test_trade_path_5_and_10_sessions_are_distinct_and_ignore_future_bars():
    bars = _bars()
    bars[7].update(high=111, close=109)
    assert _evaluate(bars)["status"] == "horizon_exit"
    assert _evaluate(bars, horizon_trading_days=10)["status"] == "target_first"
    bars.append({"date": "2030-01-02", "open": 100, "high": 999, "low": 1, "close": 100})
    assert _evaluate(bars)["status"] == "horizon_exit"


def test_trade_path_cost_and_benchmark_remain_unknown_when_absent():
    result = _evaluate(_bars())
    assert result["net_strategy_roi_pct"] is None
    assert result["excess_return_pct"] is None
    assert result["max_drawdown_pct"] is None
    assert result["return_basis"] == "per_position_gross_price_return"


def test_backtest_bar_provider_returns_ohlc_without_lookahead():
    import pandas as pd
    import market_price_history

    fetcher = getattr(market_price_history, "fetch_backtest_bars", None)
    assert callable(fetcher), "OHLC history adapter is required"
    frame = pd.DataFrame({"Open": [100, 101], "High": [103, 105], "Low": [99, 100], "Close": [102, 104]},
                         index=pd.to_datetime(["2026-01-02", "2026-01-05"]))
    class Ticker:
        def history(self, **kwargs):
            assert kwargs["auto_adjust"] is False
            return frame
    rows = fetcher("TEST", date(2026, 1, 1), date(2026, 1, 2), ticker_factory=lambda _: Ticker())
    assert rows == [{"date": "2026-01-02", "open": 100.0, "high": 103.0, "low": 99.0, "close": 102.0}]


@pytest.fixture
def isolated_mode_service(monkeypatch, tmp_path):
    import decision_backtest_service as service
    import decision_tracking_store

    monkeypatch.setattr(decision_tracking_store, "DECISION_TRACKING_DB_PATH", str(tmp_path / "backtests.sqlite3"))
    decision_tracking_store.reset_decision_tracking_store_for_tests()
    return service, tmp_path


def _report(mode="v4", **updates):
    return {"filename": f"TEST_{mode}_report_20260101_090000.html", "ticker": "TEST",
            "pipeline_id": mode, "date": "2026-01-01 09:00", **updates}


def _snapshot(tmp_path, report, parsed):
    import json

    path = tmp_path / report["filename"].replace(".html", ".data.json")
    path.write_text(json.dumps({"pipeline": report["pipeline_id"], "rerun_context": {"parsed": parsed}}), encoding="utf-8")


def test_service_routes_d_to_5_10_sessions_and_separate_idempotent_store(isolated_mode_service, monkeypatch):
    service, tmp_path = isolated_mode_service
    import decision_tracking_store
    report = _report()
    _snapshot(tmp_path, report, {"trade_setup": {"trade_direction": "Long", "entry_zone": "100", "target_price": "110", "stop_loss": "90"}})
    monkeypatch.setattr(service.report_history_service, "list_reports", lambda **kwargs: {"reports": [report]})
    calls = []
    def prices(*args):
        pytest.fail("D must not use calendar-month closing-price backtests")
    def bars(*args):
        calls.append(args)
        result = _bars()
        result[1].update(high=112)
        return result
    first = service.run_due_backtests(output_dir=str(tmp_path), as_of=date(2026, 2, 1), price_fetcher=prices, bar_fetcher=bars)
    second = service.run_due_backtests(output_dir=str(tmp_path), as_of=date(2026, 2, 1), price_fetcher=prices, bar_fetcher=bars)
    assert first["errors"] == []
    assert {row["horizon_trading_days"] for row in first["evaluated"]} == {5, 10}
    assert second["evaluated_count"] == 0
    assert len(calls) == 1
    assert decision_tracking_store.list_backtest_results() == []
    stats = service.compute_performance_stats()
    assert stats["trade_summary"]["total_evaluations"] == 2
    assert {row["schema_version"] for row in stats["details"]} == {"trade_path_backtest.v1"}


@pytest.mark.parametrize("mode", ["v2", "v3"])
def test_service_requires_same_period_execution_plan_for_b_c(isolated_mode_service, monkeypatch, mode):
    service, tmp_path = isolated_mode_service
    report = _report(mode, recommendation={"recommendation": "買入", "target_12m": "150"})
    monkeypatch.setattr(service.report_history_service, "list_reports", lambda **kwargs: {"reports": [report]})
    result = service.run_due_backtests(output_dir=str(tmp_path), as_of=date(2027, 2, 1),
                                      price_fetcher=lambda *a: pytest.fail("No long-term target substitution"),
                                      bar_fetcher=lambda *a: pytest.fail("Missing plan must not fetch"))
    assert result["errors"] == []
    assert result["evaluated_count"] == 0
    assert result["skipped"][0]["reason"] == "execution_plan_unavailable"


@pytest.mark.parametrize(("mode", "parsed", "expected"), [
    ("v2", {"position_plan": {"action": "進場", "entry_zone": "100", "stop_loss": "90", "target_price": "110", "horizon_trading_days": 5}}, "horizon_exit"),
    ("v3", {"recommendation": {"建議": "放空"}, "short_setup": {"entry_trigger": "100", "cover_stop": "110", "downside_target": "90", "horizon_trading_days": 5}}, "horizon_exit"),
    ("v3", {"recommendation": {"建議": "避免"}, "short_setup": {
        "entry_trigger": "暫不放空，等待下次財報驗證應收帳款", "horizon_trading_days": 5,
        "squeeze_risk": "借券回補可能推高股價", "thesis_invalidation": "下次法說若上修毛利率則重新評估",
    }}, "no_trade"),
])
def test_service_evaluates_only_explicit_b_c_contract(isolated_mode_service, monkeypatch, mode, parsed, expected):
    service, tmp_path = isolated_mode_service
    report = _report(mode)
    _snapshot(tmp_path, report, parsed)
    monkeypatch.setattr(service.report_history_service, "list_reports", lambda **kwargs: {"reports": [report]})
    result = service.run_due_backtests(output_dir=str(tmp_path), as_of=date(2026, 2, 1), bar_fetcher=lambda *a: _bars())
    assert result["errors"] == []
    assert result["evaluated_count"] == 1
    assert result["evaluated"][0]["status"] == expected


def test_service_missing_trade_horizon_is_explicitly_unverifiable(isolated_mode_service, monkeypatch):
    service, tmp_path = isolated_mode_service
    report = _report("v2")
    _snapshot(tmp_path, report, {"position_plan": {"action": "進場", "entry_zone": "100", "stop_loss": "90", "target_price": "110"}})
    monkeypatch.setattr(service.report_history_service, "list_reports", lambda **kwargs: {"reports": [report]})
    result = service.run_due_backtests(output_dir=str(tmp_path), as_of=date(2026, 2, 1), bar_fetcher=lambda *a: pytest.fail("No inferred horizon"))
    assert result["skipped"][0]["reason"] == "explicit_trade_horizon_required"


def test_trade_store_leaves_legacy_rows_unchanged_and_preserves_unknowns(isolated_mode_service):
    import importlib.util
    import sqlite3

    assert importlib.util.find_spec("trade_backtest_store") is not None, "Versioned trade store is required"
    import trade_backtest_store as store
    import decision_tracking_store
    decision_tracking_store.list_backtest_results()
    with sqlite3.connect(decision_tracking_store.DECISION_TRACKING_DB_PATH) as conn:
        conn.execute("INSERT INTO decision_tracking_meta(key,value) VALUES ('legacy-marker','unchanged')")
    payload = {"report_filename": "sample_v4.html", "pipeline_id": "v4", "ticker": "TEST",
               "horizon_trading_days": 5, "schema_version": "trade_path_backtest.v1", "status": "ambiguous",
               "evaluation_date": "2026-01-08", "strategy_roi_pct": None, "outcome": None}
    store.save_result(payload)
    store.save_result(payload)
    assert store.list_results() == [payload]
    with sqlite3.connect(decision_tracking_store.DECISION_TRACKING_DB_PATH) as conn:
        assert conn.execute("SELECT value FROM decision_tracking_meta WHERE key='legacy-marker'").fetchone()[0] == "unchanged"
        assert conn.execute("SELECT COUNT(*) FROM decision_backtest_results").fetchone()[0] == 0


def test_temporal_memory_reads_versioned_trade_result(isolated_mode_service, monkeypatch):
    import temporal_memory_service
    import trade_backtest_store

    service, tmp_path = isolated_mode_service
    report = _report()
    monkeypatch.setattr(service.report_history_service, "list_reports", lambda **kwargs: {"reports": [report]})
    trade_backtest_store.save_result({"report_filename": report["filename"], "ticker": "TEST", "pipeline_id": "v4",
        "horizon_trading_days": 5, "schema_version": "trade_path_backtest.v1", "status": "stop_first",
        "outcome": "miss", "strategy_roi_pct": -10, "evaluation_date": "2026-01-08"})
    memory = temporal_memory_service.build_temporal_memory("TEST", pipeline_id="v4", output_dir=str(tmp_path))
    assert memory["backtests"][0]["horizon_trading_days"] == 5
    assert memory["backtests"][0]["strategy_roi_pct"] == -10
    assert "5 個交易日" in memory["reflection_prompt"]
    assert "3/6/12 月目標價" not in memory["reflection_prompt"]


def test_no_historical_ohlc_is_insufficient_evidence_not_a_pending_trade():
    assert _evaluate([])["status"] == "insufficient_data"


def test_known_trade_cost_and_benchmark_are_applied_only_when_provided():
    bars = _bars()
    bars[1].update(high=112)
    result = _evaluate(bars, transaction_cost=1, benchmark_return_pct=3)
    assert result["net_strategy_roi_pct"] == 9
    assert result["excess_return_pct"] == 7


def test_trade_store_read_does_not_create_any_database(isolated_mode_service):
    import decision_tracking_store
    import trade_backtest_store
    from pathlib import Path

    path = Path(decision_tracking_store.DECISION_TRACKING_DB_PATH)
    assert not path.exists()
    assert trade_backtest_store.list_results() == []
    assert not path.exists()


def test_explicit_breakdown_trigger_fills_gap_open_after_trigger():
    bars = _bars()
    bars[0].update(open=95, high=98, low=92, close=95)
    result = _evaluate(bars, direction="Short", entry_zone="跌破 100", target_price="90", stop_loss="110")
    assert result["entry_price"] == 95
    assert result["entry_date"] == "2026-01-02"
    assert result["execution_assumption"] == "price_stop_trigger_daily_ohlc"


def test_compound_event_trigger_is_not_replaced_with_a_price_touch():
    result = _evaluate(_bars(), direction="Short", entry_zone="法說下修且跌破 100", target_price="90", stop_loss="110")
    assert result["status"] == "insufficient_data"
    assert result["reason"] == "unsupported_conditional_entry"
    assert result["entry_price"] is None


def test_gap_beyond_entry_and_stop_on_same_open_is_not_simulated():
    bars = _bars()
    bars[0].update(open=115, high=117, low=114, close=116)
    result = _evaluate(bars, entry_zone="突破 100", target_price="110", stop_loss="90")
    assert result["status"] == "insufficient_data"
    assert result["reason"] == "gap_entry_outside_execution_levels"


def test_service_neutral_plan_cannot_invent_cash_from_nonzero_position(isolated_mode_service, monkeypatch):
    service, tmp_path = isolated_mode_service
    report = _report("v2")
    _snapshot(tmp_path, report, {"position_plan": {"action": "等待", "position_size": "25%", "horizon_trading_days": 5}})
    monkeypatch.setattr(service.report_history_service, "list_reports", lambda **kwargs: {"reports": [report]})
    result = service.run_due_backtests(output_dir=str(tmp_path), as_of=date(2026, 2, 1), bar_fetcher=lambda *a: pytest.fail("Invalid cash assumption"))
    assert result["skipped"][0]["reason"] == "invalid_observation_contract"


def test_trade_calibration_does_not_group_session_horizon_as_unknown_month():
    from outcome_calibration import build_outcome_calibration

    result = build_outcome_calibration(backtests=[{
        "pipeline_id": "v4", "horizon_trading_days": 5,
        "outcome": None, "status": "not_entered", "strategy_roi_pct": 0,
    }], reports=[])
    assert result["by_horizon"] == {}
    assert result["by_trading_horizon"]["5"]["count"] == 1


@pytest.mark.parametrize(("direction", "first_bar", "target", "stop"), [
    ("Long", {"open": 95, "high": 105, "low": 94, "close": 102}, "120", "90"),
    ("Short", {"open": 115, "high": 116, "low": 105, "close": 108}, "90", "120"),
])
def test_partial_entry_zone_touch_uses_observed_conservative_price(direction, first_bar, target, stop):
    bars = _bars()
    bars[0].update(first_bar)
    result = _evaluate(bars, direction=direction, entry_zone="100-110", target_price=target, stop_loss=stop)
    assert result["entry_date"] == bars[0]["date"]
    assert result["entry_price"] == 105
    assert first_bar["low"] <= result["entry_price"] <= first_bar["high"]


@pytest.mark.parametrize("entry", ["訂單確認後 100 元", "公告通過後 100", "利多確認 100", "100 元且管理層確認"])
def test_unrecognized_entry_event_is_not_silently_simulated_as_price_touch(entry):
    result = _evaluate(_bars(), entry_zone=entry)
    assert result["status"] == "insufficient_data"
    assert result["reason"] == "unsupported_conditional_entry"
    assert result["entry_price"] is None


@pytest.mark.parametrize("entry", ["NT$ 99–NT$ 101", "99 元至 101 元", "ＴＷＤ ９９－１０１ 元", "99 to 101"])
def test_supported_plain_price_range_grammar_remains_executable(entry):
    result = _evaluate(_bars(), entry_zone=entry)
    assert result["status"] == "horizon_exit"
    assert result["entry_price"] == 100


def test_service_b_short_recommendation_uses_same_plan_short_prices(isolated_mode_service, monkeypatch):
    service, tmp_path = isolated_mode_service
    report = _report("v2")
    _snapshot(tmp_path, report, {"recommendation": {"建議": "放空"}, "position_plan": {
        "action": "進場", "entry_zone": "100", "target_price": "80", "stop_loss": "110", "horizon_trading_days": 5,
    }})
    bars = _bars()
    bars[1].update(open=100, high=102, low=79, close=82)
    monkeypatch.setattr(service.report_history_service, "list_reports", lambda **kwargs: {"reports": [report]})
    result = service.run_due_backtests(output_dir=str(tmp_path), as_of=date(2026, 2, 1), bar_fetcher=lambda *a: bars)
    assert result["errors"] == []
    assert result["evaluated"][0]["status"] == "target_first"
    assert result["evaluated"][0]["strategy_roi_pct"] == 20
    assert result["evaluated"][0]["trade_direction"] == "Short"


def test_service_b_missing_recommendation_labels_legacy_long_assumption(isolated_mode_service, monkeypatch):
    service, tmp_path = isolated_mode_service
    report = _report("v2")
    _snapshot(tmp_path, report, {"position_plan": {
        "action": "進場", "entry_zone": "100", "target_price": "110", "stop_loss": "90", "horizon_trading_days": 5,
    }})
    monkeypatch.setattr(service.report_history_service, "list_reports", lambda **kwargs: {"reports": [report]})
    result = service.run_due_backtests(output_dir=str(tmp_path), as_of=date(2026, 2, 1), bar_fetcher=lambda *a: _bars())
    assert result["evaluated"][0]["trade_direction"] == "Long"
    assert result["evaluated"][0]["direction_assumption"] == "legacy_long_default"


def _observation_contract(mode):
    return {
        "v2": {"position_plan": {
            "action": "等待", "position_size": "0%", "entry_zone": None, "target_price": None,
            "stop_loss": None, "risk_reward": None, "horizon_trading_days": 5,
            "invalidation_condition": "下次營收公布後檢查是否轉為衰退",
        }},
        "v3": {"recommendation": {"建議": "避免"}, "short_setup": {
            "entry_trigger": "暫不放空，等待下次財報驗證應收帳款", "horizon_trading_days": 5,
            "downside_target": None, "cover_stop": None,
            "squeeze_risk": "借券回補可能推高股價", "thesis_invalidation": "下次法說若上修毛利率則重新評估",
        }},
        "v4": {"trade_setup": {
            "trade_direction": "Neutral", "entry_zone": "暫不進場，等待法說公布營收指引",
            "target_price": None, "stop_loss": None, "support_level": None, "resistance_level": None,
            "core_catalyst": "下週法說後重新檢查營收指引", "risk_level": "Medium",
        }},
    }[mode]


@pytest.mark.parametrize(("mode", "field", "updates"), [
    ("v2", "position_plan", {"entry_zone": "等待跌破 100 後買入"}),
    ("v3", "short_setup", {"entry_trigger": "等待跌破100後放空"}),
    ("v4", "trade_setup", {"entry_zone": "等待突破 100 後買入"}),
    ("v2", "position_plan", {"invalidation_condition": "N/A"}),
    ("v3", "short_setup", {"squeeze_risk": "N/A"}),
    ("v4", "trade_setup", {"core_catalyst": "N/A"}),
])
def test_service_invalid_observation_neither_fetches_nor_persists_cash_roi(isolated_mode_service, monkeypatch, mode, field, updates):
    import trade_backtest_store

    service, tmp_path = isolated_mode_service
    report = _report(mode)
    parsed = _observation_contract(mode)
    parsed[field].update(updates)
    _snapshot(tmp_path, report, parsed)
    monkeypatch.setattr(service.report_history_service, "list_reports", lambda **kwargs: {"reports": [report]})
    result = service.run_due_backtests(output_dir=str(tmp_path), as_of=date(2026, 2, 1),
        bar_fetcher=lambda *a: pytest.fail("Invalid observation must be rejected before fetching prices"))
    assert result["errors"] == []
    assert result["evaluated"] == []
    assert result["skipped"][0]["reason"] == "invalid_observation_contract"
    assert trade_backtest_store.list_results() == []


@pytest.mark.parametrize("mode", ["v2", "v3", "v4"])
def test_service_complete_observation_contract_records_explicit_cash_assumption(isolated_mode_service, monkeypatch, mode):
    service, tmp_path = isolated_mode_service
    report = _report(mode)
    _snapshot(tmp_path, report, _observation_contract(mode))
    monkeypatch.setattr(service.report_history_service, "list_reports", lambda **kwargs: {"reports": [report]})
    result = service.run_due_backtests(output_dir=str(tmp_path), as_of=date(2026, 2, 1), bar_fetcher=lambda *a: _bars())
    assert result["errors"] == []
    assert result["evaluated_count"] == (2 if mode == "v4" else 1)
    for row in result["evaluated"]:
        assert row["status"] == "no_trade"
        assert row["strategy_roi_pct"] == 0
        assert row["position_assumption"] == "cash_no_position_zero_interest"
