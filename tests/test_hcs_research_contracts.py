from datetime import date
from copy import deepcopy
import json
import pytest
from backtest_session_contract import session_window
from trade_path_backtest import evaluate_trade_path
from backtest_price_comparability import assess_price_comparability, assess_cost_evidence
from market_price_history import _nearest_close
from screener_signal_dimensions import separate_signals
from signal_increment_evaluation import evaluate_increment, POLICY_ID


def bars():
    window = session_window(date(2026, 1, 1), 10)
    return [{"date": day, "open": 100, "high": 112, "low": 98, "close": 101,
             "stock_splits": 0, "dividends": 0} for day in window["sessions"]]


def context():
    return {"data": {"ticker": "2330.TW", "quote_type": "EQUITY", "daily_market_data": {
        "price_adjustment_basis": "unadjusted_exchange_ohlc"}}, "setup": {
        "trade_direction": "Long", "entry_zone": 100, "target_price": 110, "stop_loss": 90}}


def evaluate(rows, **kwargs):
    args = dict(bars=rows, generated_date=date(2026, 1, 1), as_of=date(2026, 1, 20),
                direction="Long", entry_zone=100, target_price=110, stop_loss=90,
                horizon_trading_days=5, market="tw", execution_context=context())
    args.update(kwargs)
    return evaluate_trade_path(**args)


def test_no_future_close_fallback_and_verified_holiday_window():
    assert _nearest_close([(date(2026, 10, 5), 100)], date(2026, 10, 2)) is None
    window = session_window(date(2026, 9, 24), 1)
    assert window["sessions"] == ["2026-09-29"]
    assert session_window(date(2027, 1, 1), 10)["status"] == "calendar_unavailable"


def test_missing_session_cannot_extend_window_to_later_bars():
    rows = bars(); del rows[1]
    result = evaluate(rows)
    assert result["status"] == "insufficient_data" and result["reason"] == "session_coverage_incomplete"


def test_maturity_and_unknown_year_fail_closed():
    assert evaluate(bars(), as_of=date(2026, 1, 7))["status"] == "pending"
    result = evaluate([{"date":"2027-01-04","open":100,"high":112,"low":98,"close":101}],
                      generated_date=date(2027, 1, 1), as_of=date(2027, 2, 1))
    assert result["reason"] == "calendar_unavailable"


@pytest.mark.parametrize("failure, reason", [("adjusted","plan_price_basis_unverified"),
    ("split","corporate_action_requires_rebased_plan"), ("missing_actions","corporate_actions_coverage_unknown"),
    ("off_grid","off_grid_or_unknown_instrument"), ("unknown_type","off_grid_or_unknown_instrument")])
def test_price_comparability_rejects_unknown_or_incompatible_inputs(failure, reason):
    c = context(); rows = bars()
    if failure == "adjusted": c["data"]["daily_market_data"]["price_adjustment_basis"] = "provider adjusted"
    if failure == "split": rows[1]["stock_splits"] = 4
    if failure == "missing_actions": del rows[0]["dividends"]
    if failure == "off_grid": c["setup"]["entry_zone"] = 100.1
    if failure == "unknown_type": c["data"]["quote_type"] = None
    assert assess_price_comparability(c, rows)["reason"] == reason


def test_missing_cost_and_cash_do_not_invent_net_results():
    result = evaluate(bars())
    assert result["outcome"] == "hit" and result["net_outcome"] is None
    assert result["net_strategy_roi_pct"] is None
    result = evaluate(bars(), direction="Neutral")
    assert result["strategy_roi_pct"] == 0 and result["net_strategy_roi_pct"] is None
    assert evaluate(bars(), transaction_cost=0)["net_outcome"] is None


def test_complete_declared_cost_can_turn_positive_gross_into_net_miss():
    c = context(); c["setup"]["transaction_cost_components"] = {
        "commission": .5, "transaction_tax": .5, "slippage": 1,
        "source":"fixture declared assumptions", "as_of":"2026-01-01", "unit":"round_trip_per_share"}
    rows = bars()
    for row in rows: row["high"] = 102
    result = evaluate(rows, transaction_cost=2, execution_context=c)
    assert result["outcome"] == "hit" and result["net_outcome"] == "miss"
    assert result["cost_evidence"]["status"] == "complete_declared_assumptions"
    assert assess_cost_evidence(c, 0)["status"] == "unverified"


def test_flow_normalization_sign_and_no_mixed_score():
    row = {"ticker":"2330.TW", "score":2000, "metrics": {
        "foreign_net_buy_shares":2e6, "investment_trust_net_buy_shares":1e6,
        "latest_volume":10e6, "flow_observation_date":"2026-01-02", "volume_observation_date":"2026-01-02", "bias_pct":-10, "volume_ratio":3}}
    result = separate_signals(row)
    assert result["score"] is None and result["legacy_score"] == 2000
    assert result["signal_dimensions"]["foreign_trust_net_buy_pct_of_volume"] == 30
    assert result["signal_dimensions"]["bias_direction"] == "negative"
    row["metrics"].pop("latest_volume")
    assert separate_signals(row)["metrics"]["normalized_flow_pct"] is None


def test_indexed_population_counts_unmatured_missing_versions_and_overlap(monkeypatch, tmp_path):
    import report_index
    from performance_population import indexed_population
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path/"index.sqlite3"))
    filenames = ["2330_TW_v4_report_20260101_090000.html", "2330_TW_v4_report_20260101_100000.html",
                 "2330_TW_v4_report_20260105_090000.html", "2317_TW_v4_report_20260114_090000.html"]
    for filename in filenames:
        (tmp_path/filename).write_text("<html>original</html>")
        (tmp_path/filename.replace(".html",".data.json")).write_text(json.dumps({"rerun_context":{"parsed":{"trade_setup":{"trade_direction":"Long"}}}}))
        assert report_index.upsert_report_metadata(filename, output_dir=str(tmp_path))
    result = indexed_population(str(tmp_path), as_of=date(2026,1,15), saved=[])
    assert result["status"] == "complete_index" and result["expected_slots"] == 8
    assert result["state_counts"]["not_matured"] > 0 and result["state_counts"]["matured_missing_result"] > 0
    assert result["excluded_primary_counts"] == {"same_day_report_version":1,"overlapping_ticker_window":1}
    assert result["independent_candidate_count"] == 2 and result["credible_strategy_performance"] is False


def observed(signal, ticker, flow, bias):
    window = session_window(date.fromisoformat(signal), 10)
    return {"ticker":ticker, "signal_date":signal,"available_at":signal+"T18:00:00+08:00",
            "entry_at":window["sessions"][0]+"T09:00:00+08:00", "window_end":window["maturity_date"],
            "industry":"fixture", "size_bin":"large", "momentum_bin":"flat", "flow_pct":flow,
            "bias_pct":bias, "net_return_pct":1, "control_net_return_pct":2,
            "source_provenance":{"source":"synthetic testing only"},"policy_id":POLICY_ID, "policy_registered_at":"2025-12-01T00:00:00+08:00",
            "control":{"industry":"fixture","size_bin":"large","momentum_bin":"flat", "entry_at":window["sessions"][0]+"T09:00:00+08:00", "window_end":window["maturity_date"]}}


def test_holdout_comparison_is_negative_descriptive_and_not_causal():
    rows = [observed("2026-01-01","2330.TW",1,1), observed("2026-03-02","2330.TW",-1,-1)]
    result = evaluate_increment(rows, cutoff="2026-02-01")
    assert result["status"] == "descriptive_holdout_only"
    assert all(row["mean_net_excess_pct"] == -1 for row in result["groups"])
    assert result["causal_effect_established"] is False
    assert result["statistical_significance_established"] is False
    rows[1]["available_at"] = "2026-03-06T18:00:00+08:00"
    assert evaluate_increment(rows, cutoff="2026-02-01")["status"] == "unavailable"
    assert evaluate_increment([], cutoff="2026-02-01")["status"] == "unavailable"


def test_real_performance_get_exposes_full_index_and_nonvalidated_research(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_routes.performance import create_performance_router, PerformanceRouteDeps
    import report_index
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path/"index.sqlite3"))
    filename="2330_TW_v4_report_20260101_090000.html"
    (tmp_path/filename).write_text("<html>unchanged</html>")
    (tmp_path/filename.replace(".html",".data.json")).write_text(json.dumps({"rerun_context":{"parsed":{"trade_setup":{"trade_direction":"Long"}}}}))
    assert report_index.upsert_report_metadata(filename, output_dir=str(tmp_path))
    app=FastAPI();app.include_router(create_performance_router(PerformanceRouteDeps(lambda:str(tmp_path))))
    response=TestClient(app).get("/api/performance/stats")
    assert response.status_code==200
    population=response.json()["population"]
    assert population["expected_slots"]==2 and population["independent_candidate_count"]==1
    assert population["comparable_assumed_cost_net_result_count"]==0
    assert response.json()["research_validation"]["status"]=="not_validated"
    assert (tmp_path/filename).read_text()=="<html>unchanged</html>"


def test_historical_failed_row_is_preserved_without_automatic_recompute(monkeypatch):
    import mode_trade_backtest as module
    monkeypatch.setattr(module,"_parsed_snapshot",lambda *a:{"trade_setup":{"trade_direction":"Long","entry_zone":100,"target_price":110,"stop_loss":90}})
    old=[{"horizon_trading_days":5,"status":"insufficient_data"},{"horizon_trading_days":10,"status":"insufficient_data"}]
    monkeypatch.setattr(module.trade_backtest_store,"list_results",lambda **kw:old)
    result=module.evaluate_report_trades(report={"filename":"fixture","ticker":"2330.TW"},pipeline_id="v4",generated=date(2026,1,1),as_of=date(2026,2,1),output_dir="unused",bar_fetcher=lambda *a:pytest.fail("must not refetch and overwrite history"))
    assert result[0]==[] and len(result[1])==2
    assert all(row["status"]=="insufficient_data" for row in old)


def test_old_missing_results_do_not_trigger_automatic_history_fill(monkeypatch):
    import mode_trade_backtest as module
    monkeypatch.setattr(module,"_parsed_snapshot",lambda *a:{"trade_setup":{"trade_direction":"Long","entry_zone":100,"target_price":110,"stop_loss":90}})
    monkeypatch.setattr(module.trade_backtest_store,"list_results",lambda **kw:[])
    rows, skipped=module.evaluate_report_trades(report={"filename":"old","ticker":"2330.TW"},pipeline_id="v4",generated=date(2026,1,1),as_of=date(2026,2,1),output_dir="unused",bar_fetcher=lambda *a:pytest.fail("No bulk historical population fill"))
    assert rows==[] and len(skipped)==2
    assert all(row["reason"]=="historical_missing_result_requires_explicit_evaluation" for row in skipped)


def test_real_screener_js_does_not_display_unknown_flow_as_zero():
    import shutil,subprocess
    from pathlib import Path
    node=shutil.which("node");assert node
    root=Path(__file__).resolve().parents[1]/"backend/static"
    scripts="const window={};"+(root/"market_screener_helpers.js").read_text()+(root/"market_screener_panel.js").read_text()
    harness=scripts+";const panel=window.StockAgentMarketScreenerPanel.create({apiClient:{}});const html=panel.renderTable([{ticker:'2330.TW',score:null,metrics:{normalized_flow_pct:null,bias_pct:-10}}]);console.log(JSON.stringify({html,params:panel.params(),unknown:window.StockAgentMarketScreenerHelpers.numberValue(null)}));"
    result=json.loads(subprocess.run([node,"-e",harness],check=True,capture_output=True,text=True).stdout)
    assert result["unknown"] is None
    assert result["params"]["sort_by"]=="ticker" and "min_score" not in result["params"]
    assert "外資投信/量%" in result["html"] and "-10.0%" in result["html"]
    assert '>0.00%</span>' not in result["html"]
