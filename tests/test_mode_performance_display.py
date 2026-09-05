"""Run actual panel JavaScript against versioned trading-result fixtures."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest


def test_panels_preserve_trading_days_unknown_returns_and_non_scored_status():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for panel contract")
    static = Path(__file__).resolve().parents[1] / "backend/static"
    scripts = "\n".join((static / filename).read_text() for filename in ["performance_panel.js", "temporal_memory_panel.js"])
    fixture = {"summary": {}, "by_horizon": [], "trade_summary": {
        "total_evaluations": 1, "hit_rate_pct": None, "average_strategy_roi_pct": None},
        "trade_by_horizon": {"5": {"total_evaluations": 1, "hit_rate_pct": None, "average_strategy_roi_pct": None}},
        "details": [{"ticker": "TEST", "horizon_months": None, "horizon_trading_days": 5,
                     "outcome": None, "status": "ambiguous", "strategy_roi_pct": None,
                     "entry_price": 100, "exit_price": None}]}
    harness = "const window = {};\n" + scripts + "\nconst payload = " + json.dumps(fixture) + ";\n"
    harness += """
const summaryEl = {}, listEl = {}, memoryRoot = {};
window.StockAgentPerformancePanel.render(payload, {summaryEl, listEl, escapeHtml: value => String(value)});
window.StockAgentTemporalMemoryPanel.render({previous_report: {filename:'prior.html'},
    backtests: payload.details}, memoryRoot, value => String(value));
console.log(JSON.stringify({summary: summaryEl.textContent, html: listEl.innerHTML, memory: memoryRoot.innerHTML}));
"""
    result = subprocess.run([node, "-e", harness], text=True, capture_output=True, check=True)
    rendered = json.loads(result.stdout)
    assert "交易計畫" in rendered["summary"]
    for field in ("html", "memory"):
        assert "5 交易日" in rendered[field]
        assert "nullM" not in rendered[field] and "?M" not in rendered[field]
        assert "N/A" in rendered[field]
        assert "miss" not in rendered[field]
    assert "0.00%" not in rendered["html"]
