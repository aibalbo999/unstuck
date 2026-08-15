import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def test_watchlist_board_surfaces_full_quality_audit_without_creating_daily_action():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: {
    scope: 'all_indexed_reports',
    audited_reports: 160,
    quality_metadata_missing_reports: 2,
    quality_metadata_coverage_pct: 98.75
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "全量報告品質" in payload["board"]
    assert "2 份待人工核對" in payload["board"]
    assert "98.75%" in payload["board"]


def test_watchlist_board_does_not_treat_unavailable_quality_audit_as_zero_gaps():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: { status: 'unavailable', error_code: 'quality_audit_unavailable' }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "全量報告品質：暫時無法讀取" in payload["board"]
    assert "0 份待人工核對" not in payload["board"]


def test_watchlist_board_surfaces_snapshots_excluded_from_quality_coverage():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: {
    snapshot_invalid_reports: 1,
    snapshot_unverified_reports: 1,
    quality_metadata_coverage_pct: 100
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "2 份 snapshot 無法驗證" in payload["board"]
