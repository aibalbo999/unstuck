import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def test_daily_quality_board_offers_historical_audit_navigation_for_latest_scope():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const html = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], {
  report_quality_audit: {
    selection_basis: 'latest_per_ticker_pipeline',
    audited_reports: 160,
    quality_metadata_missing_reports: 2,
    quality_metadata_coverage_pct: 98.75,
    quality_metadata_coverage_basis: 'verified_snapshot_reports',
    items_returned: 2,
    items_truncated: false,
    items: []
  },
  decision_queue: { items: [], summary: { total_actionable: 0 } }
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert 'data-quality-history-audit' in payload["html"]
    assert "查看歷史版本稽核" in payload["html"]


def test_watchlist_panel_delegates_historical_audit_navigation():
    module_path = STATIC_DIR / "watchlist_panel.js"
    script = """
global.window = {
  StockAgentWatchlistPanelHelpers: {
    itemPayload: () => ({}),
    renderSuggestions: () => {},
    resetForm: () => {},
    slotLabel: () => '',
    priorityLabel: () => '',
    reportButton: () => ''
  },
  StockAgentWatchlistPanelActions: { create: () => ({}) },
  StockAgentWatchlistTriggerForm: { renderItem: () => '' }
};
require(__MODULE_PATH__);
let handler;
let opened = 0;
const listEl = { addEventListener: (type, callback) => { if (type === 'click') handler = callback; } };
const panel = window.StockAgentWatchlistPanel.create({ elements: { listEl } });
window.StockAgentOpenHistoricalQualityAudit = () => { opened += 1; };
panel.bindEvents();
handler({ target: { closest: selector => selector === '[data-quality-history-audit]' ? {} : null } });
process.stdout.write(JSON.stringify({ opened }));
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["opened"] == 1


def test_history_workspace_ignores_stale_report_list_response():
    module_path = STATIC_DIR / "history_workspace.js"
    script = """
(async () => {
  global.window = {
    StockAgentHistoricalQualityAudit: { create: () => ({ load: () => {}, bindEvents: () => {} }) },
    StockAgentHistoryWorkspacePanels: {
      create: () => ({
        historyFilters: {
          values: (() => { let calls = 0; return () => ({ query: ['old', 'new'][calls++], pipelineFilter: 'all', recommendationFilter: 'all', dataTrustFilter: 'all', includeVersions: false }); })(),
          bind: () => {}
        },
        historyPanel: {
          renderReports: reports => { global.renderedQuery = reports[0]?.query || ''; },
          renderPagination: () => 1,
          setTrackingCompact: () => {},
          bindEvents: () => {},
          clearSelection: () => {}
        },
        reportPreviewPanel: { hide: () => {}, show: () => false },
        reportComparePanel: { bindEvents: () => {} },
        trackingSnapshotPanel: { bindEvents: () => {}, load: async () => {} },
        decisionTrackingPanel: {
          load: () => new Promise(resolve => global.trackingResolvers.push(resolve))
        }
      })
    },
    StockAgentHistoryWorkspaceActions: { create: () => ({}) }
  };
  global.trackingResolvers = [];
  const reportResolvers = {};
  const workspace = require(__MODULE_PATH__);
  const instance = window.StockAgentHistoryWorkspace.create({
    apiClient: {
      fetchReports: params => new Promise(resolve => { reportResolvers[params.query] = resolve; })
    },
    ui: {},
    elements: { historyIncludeVersions: { checked: false } },
    openReport: () => {}
  });
  const first = instance.loadHistory();
  const second = instance.loadHistory();
  global.trackingResolvers[1]({ items: [] });
  await Promise.resolve();
  global.trackingResolvers[0]({ items: [] });
  await Promise.resolve();
  reportResolvers.new({ reports: [{ query: 'new', filename: 'new.html' }] });
  await Promise.resolve();
  reportResolvers.old({ reports: [{ query: 'old', filename: 'old.html' }] });
  await Promise.all([first, second]);
  process.stdout.write(JSON.stringify({ renderedQuery: global.renderedQuery }));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["renderedQuery"] == "new"


def test_historical_audit_navigation_wiring_uses_cache_busters_and_existing_scope():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    history_workspace = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")
    watchlist_helpers = (STATIC_DIR / "watchlist_panel_helpers.js").read_text(encoding="utf-8")
    watchlist_panel = (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")

    assert "data-quality-history-audit" in watchlist_helpers
    assert "StockAgentOpenHistoricalQualityAudit" in watchlist_panel
    assert "openHistoricalQualityAudit" in history_workspace
    assert "StockAgentOpenHistoricalQualityAudit" in app_js
    assert "/static/watchlist_panel_helpers.js?v=20260816-historical-quality-artifact-summary" in index_html
    assert "/static/watchlist_panel.js?v=20260816-historical-quality-navigation" in index_html
    assert "/static/history_workspace.js?v=20260816-historical-quality-pipeline-filter" in index_html
    assert "/static/styles/watchlist.css?v=20260816-historical-quality-artifact-summary" in style_css
