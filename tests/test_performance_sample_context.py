import json
import shutil
import subprocess
from pathlib import Path
import pytest
from performance_sample_context import sample_context


@pytest.mark.parametrize("rows, scored, rate, status", [([], 0, None, "no_scored_results"),
    ([{"outcome": "miss"}], 1, 0.0, "insufficient_sample"),
    ([{"outcome": None, "status": "ambiguous"}], 0, None, "no_scored_results"),
    ([{"outcome": "hit"}, {"outcome": "miss"}], 2, 50.0, "descriptive_only")])
def test_empty_negative_and_boundary_samples(rows, scored, rate, status):
    result = sample_context(rows)
    assert result["scored_count"] == scored
    assert result["descriptive_hit_ratio_pct"] == rate
    assert result["sample_status"] == status
    assert result["headline_hit_rate_pct"] is None
    assert result["observation_window"]["pending_unstored_count"] is None


def test_one_of_fifty_does_not_claim_reliable_performance_in_actual_api_and_ui(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import decision_backtest_service as service
    from api_routes.performance import create_performance_router, PerformanceRouteDeps
    rows = [{"outcome": "hit", "strategy_roi_pct": 1.0, "net_strategy_roi_pct": -1.0,
             "transaction_cost": 2, "horizon_trading_days": 10, "generated_date": "2026-09-15",
             "evaluation_date": "2026-09-30", "status": "horizon_exit"}] + [
            {"outcome": None, "status": "no_trade", "reason": "explicit_observation_plan",
             "horizon_trading_days": 10} for _ in range(49)]
    monkeypatch.setattr(service.decision_tracking_store, "list_backtest_results", lambda **kw: [])
    monkeypatch.setattr(service.trade_backtest_store, "list_results", lambda **kw: rows)
    import performance_population
    monkeypatch.setattr(performance_population, "read_all_saved_trades", lambda: rows)
    app = FastAPI();app.include_router(create_performance_router(PerformanceRouteDeps(lambda: "unused")))
    response = TestClient(app).get("/api/performance/stats")
    assert response.status_code == 200
    payload = response.json();summary = payload["trade_summary"]
    assert summary["hit_rate_pct"] == 100.0  # gross-positive remains descriptive 1/1
    assert summary["scored_count"] == 1 and summary["stored_result_count"] == 50
    assert summary["unscored_reason_counts"] == {"explicit_observation_plan": 49}
    assert summary["sample_status"] == "insufficient_sample"
    assert summary["cost_coverage"]["scored_cost_recorded"] == 1
    assert summary["observation_window"]["evaluation_dates"]["end"] == "2026-09-30"
    node = shutil.which("node")
    assert node, "Node required to verify actual UI renderer"
    script = (Path(__file__).resolve().parents[1]/"backend/static/performance_panel.js").read_text()
    harness = "const window={};" + script + "\nconst payload=" + json.dumps(payload) + "; const summaryEl={},listEl={};window.StockAgentPerformancePanel.render(payload,{summaryEl,listEl,escapeHtml:x=>String(x)});console.log(JSON.stringify({summary:summaryEl.textContent,html:listEl.innerHTML}));"
    rendered = json.loads(subprocess.run([node,"-e",harness],check=True,capture_output=True,text=True).stdout)
    assert "已評分 1/50" in rendered["summary"]
    assert "樣本不足" in rendered["summary"] and "未成熟" in rendered["summary"]
    assert "100.00%" not in rendered["summary"]
    assert "描述性命中率 100.00%" in rendered["html"]
    assert "10 交易日" in rendered["html"]


def test_outcome_ledger_keeps_reason_window_and_unknown_cost():
    from outcome_calibration import build_outcome_calibration
    result = build_outcome_calibration(backtests=[{"outcome":"hit","horizon_trading_days":10,
       "generated_date":"2026-09-15","evaluation_date":"2026-09-30"},
       {"outcome":None,"status":"pending","reason":"horizon_not_observed"}], reports=[])
    summary=result["summary"]
    assert summary["scored_count"]==1 and summary["unscored_reason_counts"]=={"horizon_not_observed":1}
    assert summary["cost_coverage"]["scored_cost_unknown"]==1
    assert summary["observation_window"]["horizon_trading_days"]==["10"]
    assert result["by_trading_horizon"]["10"]["sample_status"]=="insufficient_sample"
