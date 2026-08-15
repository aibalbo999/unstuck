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
    quality_metadata_coverage_pct: 98.75,
    quality_metadata_coverage_basis: 'verified_snapshot_reports'
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "全量報告品質" in payload["board"]
    assert "2 份待人工核對" in payload["board"]
    assert "已驗證快照覆蓋 98.75%" in payload["board"]


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


def test_watchlist_board_provides_read_only_report_targets_for_missing_quality_items():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    panel_path = STATIC_DIR / "watchlist_panel.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: {
    quality_metadata_missing_reports: 2,
    quality_metadata_coverage_pct: 98.75,
    items: [
      { ticker: '1623.TW', filename: '1623_v2.html', pipeline_id: 'v2' },
      { ticker: '1623.TW', filename: '1623_v1.html', pipeline_id: 'v1' }
    ]
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    panel = panel_path.read_text(encoding="utf-8")

    assert 'data-quality-report="1623_v2.html"' in payload["board"]
    assert "查看 1623.TW v2" in payload["board"]
    assert "data-quality-report" in panel
    assert "onOpenReport" in panel


def test_watchlist_quality_report_targets_expose_human_reason_and_reason_codes():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: {
    quality_metadata_missing_reports: 1,
    items: [{
      ticker: '1623.TW',
      filename: '1623_v2.html',
      pipeline_id: 'v2',
      title: '刷新後品質證據缺口',
      detail: '資料快照曾在報告後刷新，採用前需人工查看 artifact 與 freshness。',
      reason_codes: ['quality_metadata_missing', 'quality_metadata_after_refresh']
    }]
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert 'title="資料快照曾在報告後刷新，採用前需人工查看 artifact 與 freshness。"' in payload["board"]
    assert 'aria-label="人工核對 1623.TW v2：刷新後品質證據缺口"' in payload["board"]
    assert 'data-quality-reason-codes="quality_metadata_missing,quality_metadata_after_refresh"' in payload["board"]


def test_quality_report_button_opens_the_audited_report_through_existing_callback():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    panel_path = STATIC_DIR / "watchlist_panel.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
let clickHandler;
let opened;
window.StockAgentWatchlistPanelActions = { create: () => ({}) };
require(__PANEL_PATH__);
const listEl = { addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; } };
const panel = window.StockAgentWatchlistPanel.create({
  elements: { listEl },
  onOpenReport: (...args) => { opened = args; }
});
panel.bindEvents();
const qualityButton = {
  dataset: {
    qualityReport: '1623_TW_v2_report_20260815_154718.html',
    qualityReportTicker: '1623.TW',
    qualityReportPipeline: 'v2'
  }
};
clickHandler({ target: { closest: selector => selector === '[data-quality-report]' ? qualityButton : null } });
process.stdout.write(JSON.stringify({ opened }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__PANEL_PATH__", json.dumps(str(panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["opened"] == [
        "1623_TW_v2_report_20260815_154718.html",
        "1623.TW",
        "v2",
    ]
