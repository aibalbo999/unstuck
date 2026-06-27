import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def _contrast_ratio(foreground: str, background: str) -> float:
    def channel(value: int) -> float:
        value = value / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    def luminance(color: str) -> float:
        color = color.lstrip("#")
        red, green, blue = (int(color[index:index + 2], 16) for index in (0, 2, 4))
        red_lum, green_lum, blue_lum = (channel(value) for value in (red, green, blue))
        return 0.2126 * red_lum + 0.7152 * green_lum + 0.0722 * blue_lum

    foreground_lum = luminance(foreground)
    background_lum = luminance(background)
    high, low = max(foreground_lum, background_lum), min(foreground_lum, background_lum)
    return (high + 0.05) / (low + 0.05)


def test_history_data_trust_filter_is_wired_to_api_params():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    api_client_js = (STATIC_DIR / "api_client.js").read_text(encoding="utf-8")
    history_filters_js = (STATIC_DIR / "history_filters.js").read_text(encoding="utf-8")
    history_workspace_js = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")

    assert 'id="history-data-trust-filter"' in index_html
    assert 'id="history-include-versions"' in index_html
    assert "historyDataTrustFilter" in app_js
    assert "historyIncludeVersions" in app_js
    assert "includeVersionsEl" in history_filters_js
    assert "includeVersions" in history_workspace_js
    assert "params.set('data_trust', dataTrust)" in api_client_js
    assert "params.set('include_versions', '1')" in api_client_js


def test_provider_sla_and_manual_refresh_controls_are_wired():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    provider_sla_js = (STATIC_DIR / "provider_sla_panel.js").read_text(encoding="utf-8")
    active_jobs_js = (STATIC_DIR / "active_jobs_panel.js").read_text(encoding="utf-8")
    operator_summary_js = (STATIC_DIR / "operator_summary_panel.js").read_text(encoding="utf-8")
    api_quota_panel_js = (STATIC_DIR / "api_quota_panel.js").read_text(encoding="utf-8")
    performance_panel_js = (STATIC_DIR / "performance_panel.js").read_text(encoding="utf-8")
    api_client_extensions_js = (STATIC_DIR / "api_client_extensions.js").read_text(encoding="utf-8")
    ops_workspace_js = (STATIC_DIR / "ops_workspace.js").read_text(encoding="utf-8")
    maintenance_js = (STATIC_DIR / "maintenance_panel.js").read_text(encoding="utf-8")
    home_tabs_js = (STATIC_DIR / "home_tabs.js").read_text(encoding="utf-8")
    report_rerun_js = (STATIC_DIR / "report_rerun.js").read_text(encoding="utf-8")
    analysis_stream_js = (STATIC_DIR / "analysis_stream.js").read_text(encoding="utf-8")
    history_workspace_js = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    report_preview_js = (STATIC_DIR / "report_preview_panel.js").read_text(encoding="utf-8")
    temporal_memory_js = (STATIC_DIR / "temporal_memory_panel.js").read_text(encoding="utf-8")
    report_compare_js = (STATIC_DIR / "report_compare_panel.js").read_text(encoding="utf-8")
    report_navigation_js = (STATIC_DIR / "report_navigation.js").read_text(encoding="utf-8")
    api_client_js = (STATIC_DIR / "api_client.js").read_text(encoding="utf-8")
    ui_helpers_js = (STATIC_DIR / "ui_helpers.js").read_text(encoding="utf-8")
    notification_center_js = (STATIC_DIR / "notification_center.js").read_text(encoding="utf-8")
    history_list_css = (STATIC_DIR / "styles" / "history_list.css").read_text(encoding="utf-8")
    preview_panel_css = (STATIC_DIR / "styles" / "preview_panel.css").read_text(encoding="utf-8")
    loading_report_css = (STATIC_DIR / "styles" / "loading_report.css").read_text(encoding="utf-8")

    assert 'id="provider-sla-panel"' in index_html
    assert 'id="operator-summary-panel"' in index_html
    assert 'id="operator-active-jobs"' in index_html
    assert 'id="operator-data-trust"' in index_html
    assert 'id="operator-api-quota"' in index_html
    assert 'id="operator-rerun"' in index_html
    assert 'id="api-quota-panel"' in index_html
    assert 'id="watchlist-panel"' in index_html
    assert 'id="performance-panel"' in index_html
    assert 'id="performance-summary"' in index_html
    assert 'id="performance-list"' in index_html
    assert 'id="toast-region"' in index_html
    assert 'id="confirm-dialog"' in index_html
    assert 'id="home-tab-analysis"' in index_html
    assert 'id="home-tab-ops"' in index_html
    assert 'id="home-panel-ops"' in index_html
    assert 'role="tablist"' in index_html
    assert index_html.index('id="home-panel-analysis"') < index_html.index('id="history-search"') < index_html.index('id="home-panel-ops"')
    assert "系統狀態與維護" in index_html
    assert "全系統資料來源狀態" in index_html
    assert "本報告資料狀態" in index_html
    assert 'id="active-jobs-panel"' in index_html
    assert 'id="maintenance-panel"' in index_html
    assert "本機維護" in index_html
    assert "清理任務紀錄" in index_html
    assert 'id="provider-sla-window"' in index_html
    assert '<option value="last_24h" selected>24 小時</option>' in index_html
    assert 'id="preview-refresh-data-btn"' in index_html
    assert 'id="preview-rerun-final-btn"' in index_html
    assert 'id="preview-rerun-full-btn"' in index_html
    assert 'id="preview-rerun-modeb-btn"' in index_html
    assert 'id="preview-rerun-cancel-btn"' in index_html
    assert 'id="preview-compare-add-btn"' in index_html
    assert 'id="report-compare-panel"' in index_html
    assert 'id="preview-stale-notice"' in index_html
    assert 'id="preview-tracking"' in index_html
    assert 'id="preview-temporal-memory"' in index_html
    assert 'id="preview-tracking-return"' in index_html
    assert 'id="history-tracking-table"' in index_html
    assert "/static/provider_sla_panel.js" in index_html
    assert "/static/api_quota_panel.js" in index_html
    assert "/static/active_jobs_panel.js" in index_html
    assert "/static/operator_summary_panel.js" in index_html
    assert "/static/watchlist_panel.js" in index_html
    assert "/static/watchlist_trigger_form.js" in index_html
    assert "/static/temporal_memory_panel.js" in index_html
    assert "/static/performance_panel.js" in index_html
    assert "/static/ops_workspace.js" in index_html
    assert "/static/maintenance_panel.js" in index_html
    assert "/static/home_tabs.js" in index_html
    assert "/static/report_rerun.js" in index_html
    assert "/static/analysis_stream.js" in index_html
    assert "/static/history_panel.js" in index_html
    assert "/static/report_preview_panel.js" in index_html
    assert "/static/view_controller.js" in index_html
    assert "/static/history_filters.js" in index_html
    assert "/static/report_actions.js" in index_html
    assert "/static/report_navigation.js" in index_html
    assert "/static/history_workspace.js" in index_html
    assert "/static/ui_helpers.js" in index_html
    assert "/static/api_client.js" in index_html
    assert "/static/api_client_extensions.js" in index_html
    assert "/static/notification_center.js" in index_html
    assert "StockAgentNotificationCenter.create" in app_js
    assert "StockAgentNotificationCenter" in notification_center_js
    assert "aria-live" in notification_center_js
    assert "confirm(" not in history_workspace_js
    assert "alert(" not in app_js
    assert "alert(" not in history_workspace_js
    assert "window.alert" not in report_rerun_js
    assert "notify.confirm" in history_workspace_js
    assert "notify.success" in history_workspace_js
    assert "notify.error" in history_workspace_js
    assert "notify.success" in report_rerun_js
    assert "notify.error" in report_rerun_js
    assert "providerSlaWindow" in ops_workspace_js
    assert "StockAgentProviderSlaPanel.render" in ops_workspace_js
    assert "StockAgentActiveJobsPanel.render" in ops_workspace_js
    assert "StockAgentPerformancePanel.render" in ops_workspace_js
    assert "decision_priority" in (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")
    assert "需重跑" in (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")
    assert "StockAgentOpsWorkspace.create" in app_js
    assert "StockAgentOperatorSummaryPanel.create" in app_js
    assert "operatorSummary.load" in app_js
    assert "StockAgentHistoryPanel.create" in history_workspace_js
    assert "StockAgentReportPreviewPanel.create" in history_workspace_js
    assert "StockAgentTemporalMemoryPanel.render" in report_preview_js
    assert "Agent 歷史反思" in temporal_memory_js
    assert "StockAgentViewController.create" in app_js
    assert "StockAgentHistoryFilters.create" in history_workspace_js
    assert "StockAgentReportActions.bindDownloads" in app_js
    assert "StockAgentReportNavigation.bind" in app_js
    assert "StockAgentHomeTabs" in home_tabs_js
    assert "data-home-tab" in home_tabs_js
    assert "onActivate" in home_tabs_js
    assert "loadAllOnce" in app_js
    assert "refreshProviderSlaIfLoaded" in app_js
    assert "refreshProviderSlaIfLoaded" in ops_workspace_js
    assert "providerSlaDirty" in ops_workspace_js
    assert "loadProviderSla" not in history_workspace_js
    assert "refreshProviderSlaIfLoaded" in history_workspace_js
    assert "refreshProviderSlaIfLoaded" in report_rerun_js
    assert "opsWorkspace.loadAll();" not in app_js
    assert "targetForItem" in report_navigation_js
    assert "scrollIntoView" in report_navigation_js
    assert "doc.getElementById(id)" in report_navigation_js
    assert "ensureLabel" in report_navigation_js
    assert "history-item" in history_panel_js
    assert "history-tracking" in history_panel_js
    assert "decision_tracking" in history_panel_js
    assert "decision-tracking-title" in history_panel_js
    assert "preview-date" in report_preview_js
    assert "preview-tracking-latest" in report_preview_js
    assert "decision_tracking" in report_preview_js
    assert "decision_freshness" in report_preview_js
    assert "requires_rerun" in report_preview_js
    assert "configureRerunButtons" in report_preview_js
    assert "shortLabel" in report_preview_js
    assert "重跑${shortLabel}最終建議" in report_preview_js
    assert "完整重跑${shortLabel}" in report_preview_js
    assert "模式 C：逆勢交易與泡沫狙擊" in ui_helpers_js
    assert "full_report" in report_rerun_js
    assert "rerunModeBBtn.hidden = isModeB" in report_preview_js
    assert "產生模式 B 報告" in report_preview_js
    assert "產生模式 B 報告" in index_html
    assert "history-item" not in app_js
    assert "providerSlaStatsForWindow" in provider_sla_js
    assert "groupedProviderRows" in provider_sla_js
    assert "股價與基本資料" in provider_sla_js
    assert "同業指標" in provider_sla_js
    assert "可安心使用" in provider_sla_js
    assert "provider-sla-insight" in provider_sla_js
    assert "正式分析流程" in provider_sla_js
    assert "有效快取或備援來源" in provider_sla_js
    assert "先使用仍有效的快取" in provider_sla_js
    assert "系統會優先補快取" not in provider_sla_js
    assert "資料取得率" in provider_sla_js
    assert "來源明細" in provider_sla_js
    assert "provider-sla-provider-list" in provider_sla_js
    assert "analysis_text_stale" in history_workspace_js
    assert "payload.analysis_text_stale ?? previewReport.analysis_text_stale" in history_workspace_js
    assert "payload.analysis_text_stale_message ?? previewReport.analysis_text_stale_message" in history_workspace_js
    assert "rerunPreviewReport" in history_workspace_js
    assert "StockAgentReportRerun.rerunPreviewReport" in history_workspace_js
    assert "/rerun?scope=" in report_rerun_js
    assert "/rerun/cancel" in report_rerun_js
    assert "buttons.cancel" in report_rerun_js
    assert "new EventSource" in report_rerun_js
    assert "StockAgentAnalysisStream.create" in app_js
    assert "resetAndConnect" in analysis_stream_js
    assert "/api/analyze/" in analysis_stream_js
    assert "new EventSource" in analysis_stream_js
    assert "params.set('window'" in api_client_js
    assert "/api/observability/provider-sla" in api_client_js
    assert "/api/observability/active-jobs" in api_client_js
    assert "/api/observability/api-quotas" in api_client_extensions_js
    assert "/api/reports/compare" in api_client_extensions_js
    assert "決策狀態" in report_compare_js
    assert "decision_freshness" in report_compare_js
    assert "/api/watchlist" in api_client_extensions_js
    assert "watchlist-trigger-vix" in index_html
    assert "StockAgentWatchlistTriggerForm" in (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")
    assert "latest_trigger_event" in (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")
    assert "watchlist-trigger-summary" in (STATIC_DIR / "watchlist_trigger_form.js").read_text(encoding="utf-8")
    assert "/api/performance/stats" in api_client_extensions_js
    assert "fetchPerformanceStats" in api_client_extensions_js
    assert "命中率" in performance_panel_js
    assert "平均 ROI" in performance_panel_js
    assert "recent-backtest" in performance_panel_js
    assert "/api/maintenance/storage-summary" in api_client_js
    assert "mutation: true" in api_client_js
    assert "cleanupAnalysisHistory" in api_client_js
    assert "StockAgentMaintenancePanel" in maintenance_js
    assert "maintenance-clean-provider-sla" in maintenance_js
    assert "LLM 健康" in index_html
    assert "刷新 LLM 健康" in index_html
    assert "LLM 健康讀取失敗" in ops_workspace_js
    assert "LLM/API 健康" in api_quota_panel_js
    assert "LLM 健康" in operator_summary_js
    assert "llm_error_counts" in active_jobs_js
    assert "token_estimate" not in active_jobs_js
    assert "估算 token" not in active_jobs_js
    assert "stage_summary" in active_jobs_js
    assert "最近完成任務" in active_jobs_js
    assert "模型重試" in active_jobs_js
    assert "模型錯誤" in active_jobs_js
    assert "renderPipelineModeBadge" in ui_helpers_js
    assert "renderDataTrustReason" in ui_helpers_js
    assert "data-trust-reason" in ui_helpers_js
    assert "本報告資料新鮮" in ui_helpers_js
    assert "系統來源當時不穩" in ui_helpers_js
    assert "/refresh/data" in api_client_js
    assert "historyWorkspaceEl" in app_js
    assert "workspace: elements.historyWorkspace" in history_workspace_js
    assert ".history-workspace.has-preview" in history_list_css
    assert ".report-preview[hidden]" in preview_panel_css
    assert "display: none" in preview_panel_css
    assert "visibility: hidden" not in preview_panel_css
    assert "style=" not in index_html
    assert ".report-actions" in loading_report_css
    assert ".report-download-button" in loading_report_css
    assert "@media (max-width: 640px)" in loading_report_css
    assert "await res.text()" in api_client_js
    assert "JSON.parse" in api_client_js
    assert "payload.message" in api_client_js
    assert "/api/client-config" in api_client_js
    assert "mutation_token" in api_client_js
    assert "X-Mutation-Token" in api_client_js
    assert "window.StockAgentApiClient.requestJson" in api_client_extensions_js
    assert "apiClient.requestJson" in report_rerun_js
    assert "fetchActiveJobs" in operator_summary_js
    assert "fetchApiQuotas" in operator_summary_js


def test_decision_tracking_bulk_actions_and_compact_colors_are_wired():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    history_workspace_js = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")
    decision_tracking_js = (STATIC_DIR / "decision_tracking_panel.js").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    decision_tracking_css = (STATIC_DIR / "styles" / "decision_tracking.css").read_text(encoding="utf-8")

    assert 'id="decision-tracking-run-actions"' in index_html
    assert "decisionTrackingRunActions" in app_js
    assert "runActionsBtn: elements.decisionTrackingRunActions" in history_workspace_js
    assert "runAllRecommendedActions" in decision_tracking_js
    assert "refreshReportDataSnapshot" in decision_tracking_js
    assert "/rerun?scope=full_report" in decision_tracking_js
    assert "recommendedActionForReport" in decision_tracking_js
    assert "failed += 1" in decision_tracking_js
    assert "trackingSummaryTone" in history_panel_js
    assert ".tracking-compact-note.is-above-target" in decision_tracking_css
    assert ".tracking-compact-note.is-near-target" in decision_tracking_css
    assert ".tracking-compact-note.is-below-target" in decision_tracking_css


def test_compact_tracking_cards_render_target_comparison_tones():
    history_panel_path = STATIC_DIR / "history_panel.js"
    script = """
global.window = {};
require(__HISTORY_PANEL_PATH__);
const table = { hidden: false, innerHTML: '', classList: { toggle() {} } };
const panel = window.StockAgentHistoryPanel.create({
  listEl: null,
  trackingTableEl: table,
  paginationEl: null,
  prevBtn: null,
  nextBtn: null,
  pageInfoEl: null,
  escapeHtml: value => String(value ?? ''),
  normalizeRecommendation: value => String(value ?? ''),
  renderPipelineModeBadge: () => '',
  renderDataTrustBadge: () => '',
  renderDataTrustReason: () => '',
  recommendationTone: () => ''
});
const report = (filename, summary, status) => ({
  filename,
  ticker: '2308.TW',
  pipeline_id: 'v2',
  date: '2026-06-20',
  decision_tracking: {
    status: 'tracked',
    recommendation: '買入',
    latest_price: 100,
    tracking_summary_status: summary,
    target_comparisons: {
      target_3m: { status: 'below_target', target: 120 },
      target_6m: { status: 'below_target', target: 130 },
      target_12m: { status, target: 140 }
    }
  }
});
panel.setTrackingCompact(true);
panel.renderTrackingGroups([{
  ticker: '2308.TW',
  company_name: '台達電',
  reports: [
    report('above.html', '高於12月目標', 'above_target'),
    report('near.html', '接近12月目標', 'near_target'),
    report('below.html', '距12月目標 +40.00%', 'below_target')
  ]
}]);
process.stdout.write(table.innerHTML);
""".replace("__HISTORY_PANEL_PATH__", json.dumps(str(history_panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert 'tracking-compact-note is-above-target' in result.stdout
    assert 'tracking-compact-note is-near-target' in result.stdout
    assert 'tracking-compact-note is-below-target' in result.stdout


def test_report_preview_panel_renders_mode_specific_preview_metrics():
    report_preview_path = STATIC_DIR / "report_preview_panel.js"
    script = """
global.window = {};
require(__REPORT_PREVIEW_PATH__);
const el = () => ({ hidden: false, textContent: '', innerHTML: '', className: '', classList: { toggle() {} }, querySelector: () => null });
const elements = {
  workspace: el(),
  root: el(),
  mode: el(),
  title: el(),
  decisionRow: el(),
  targets: el(),
  price: el(),
  recommendation: el(),
  confidence: el(),
  target3m: el(),
  target6m: el(),
  target12m: el(),
  summary: el(),
  staleNotice: el()
};
const panel = window.StockAgentReportPreviewPanel.create({
  elements,
  escapeHtml: value => String(value ?? '').replace(/[&<>]/g, ''),
  renderPipelineModeBadge: () => '',
  renderDataTrustBadge: () => '',
  pipelineMeta: () => ({ shortLabel: '短線波段派' }),
  normalizeRecommendation: value => String(value ?? ''),
  recommendationTone: () => 'is-hold'
});
panel.show({
  ticker: '2449',
  pipeline_id: 'v4',
  date: '2026-06-20',
  recommendation: {},
  preview: {
    kind: 'swing_trade',
    title: '2449 極短線交易預覽',
    primary: { label: '交易方向', value: '偏多 Long', tone: 'is-long' },
    metrics: [{ label: '當日股價', value: 'NT$309.50' }, { label: '風險', value: 'Medium' }],
    targets: [{ label: '進場區間', value: 'NT$300-305' }, { label: '1-2週目標', value: 'NT$330' }, { label: '停損', value: '跌破 NT$292' }],
    summary: '外資回補與突破月線'
  }
});
process.stdout.write(JSON.stringify({
  title: elements.title.textContent,
  decision: elements.decisionRow.innerHTML,
  targets: elements.targets.innerHTML,
  summary: elements.summary.textContent
}));
""".replace("__REPORT_PREVIEW_PATH__", json.dumps(str(report_preview_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["title"] == "2449 極短線交易預覽"
    assert "交易方向" in payload["decision"]
    assert "偏多 Long" in payload["decision"]
    assert "1-2週目標" in payload["targets"]
    assert "跌破 NT$292" in payload["targets"]
    assert payload["summary"] == "外資回補與突破月線"


def test_tracking_equal_prices_show_zero_after_snapshot_refresh():
    history_panel_path = STATIC_DIR / "history_panel.js"
    report_preview_path = STATIC_DIR / "report_preview_panel.js"
    script = """
global.window = {};
require(__HISTORY_PANEL_PATH__);
require(__REPORT_PREVIEW_PATH__);
const list = { innerHTML: '', querySelectorAll: () => [] };
const historyPanel = window.StockAgentHistoryPanel.create({
  listEl: list,
  trackingTableEl: null,
  paginationEl: null,
  prevBtn: null,
  nextBtn: null,
  pageInfoEl: null,
  escapeHtml: value => String(value ?? ''),
  normalizeRecommendation: value => String(value ?? ''),
  renderPipelineModeBadge: () => '',
  renderDataTrustBadge: () => '',
  renderDataTrustReason: () => '',
  recommendationTone: () => ''
});
const el = () => ({ hidden: false, textContent: '', innerHTML: '', className: '', classList: { toggle() {} }, querySelector: () => null });
const elements = {
  workspace: el(),
  root: el(),
  mode: el(),
  title: el(),
  decisionRow: el(),
  targets: el(),
  summary: el(),
  trackingRoot: el(),
  trackingLatest: el(),
  trackingReturn: el(),
  trackingGap: el(),
  trackingSummary: el()
};
const previewPanel = window.StockAgentReportPreviewPanel.create({
  elements,
  escapeHtml: value => String(value ?? ''),
  renderPipelineModeBadge: () => '',
  renderDataTrustBadge: () => '',
  pipelineMeta: () => ({ shortLabel: '價值投資派' }),
  normalizeRecommendation: value => String(value ?? ''),
  recommendationTone: () => ''
});
const tracking = {
  status: 'tracked',
  recommendation: '買入',
  initial_price: 100,
  latest_price: 100,
  return_pct: 0,
  target_12m_gap_pct: 10,
  snapshot_refreshed_at: '2026-06-27T11:31:50+00:00',
  summary: '建議後報酬 0.00%'
};
historyPanel.renderReports([{
  filename: '2449_v1_report_20260627_010000.html',
  ticker: '2449',
  pipeline_id: 'v1',
  date: '2026-06-27',
  data_trust: { status: 'fresh' },
  recommendation: { recommendation: '買入', target_12m: 'NT$110', confidence: '8/10' },
  decision_tracking: tracking
}], null);
previewPanel.show({
  ticker: '2449',
  pipeline_id: 'v1',
  date: '2026-06-27',
  recommendation: { recommendation: '買入' },
  preview: { title: '2449 投資建議', primary: { label: '建議', value: '買入' }, metrics: [], targets: [], summary: '摘要' },
  decision_tracking: tracking
});
process.stdout.write(JSON.stringify({
  history: list.innerHTML,
  previewReturn: elements.trackingReturn.textContent,
  previewSummary: elements.trackingSummary.textContent
}));
""".replace("__HISTORY_PANEL_PATH__", json.dumps(str(history_panel_path))).replace("__REPORT_PREVIEW_PATH__", json.dumps(str(report_preview_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "待新價格" not in payload["history"]
    assert "追蹤 0.00%" in payload["history"]
    assert payload["previewReturn"] == "0.00%"
    assert payload["previewSummary"] == "建議後報酬 0.00%"


def test_history_list_uses_preview_list_metrics_for_non_investment_modes():
    history_panel_path = STATIC_DIR / "history_panel.js"
    script = """
global.window = {};
require(__HISTORY_PANEL_PATH__);
const list = { innerHTML: '', querySelectorAll: () => [] };
const panel = window.StockAgentHistoryPanel.create({
  listEl: list,
  trackingTableEl: null,
  paginationEl: null,
  prevBtn: null,
  nextBtn: null,
  pageInfoEl: null,
  escapeHtml: value => String(value ?? ''),
  normalizeRecommendation: value => String(value ?? ''),
  renderPipelineModeBadge: () => '',
  renderDataTrustBadge: () => '',
  renderDataTrustReason: () => '',
  recommendationTone: () => ''
});
panel.renderReports([{
  filename: '2449_v4_report_20260620_010000.html',
  ticker: '2449',
  pipeline_id: 'v4',
  date: '2026-06-20',
  data_trust: { status: 'fresh' },
  recommendation: { recommendation: 'N/A', target_12m: 'N/A', confidence: 'N/A' },
  preview: {
    primary: { value: '偏多 Long' },
    list_metrics: [{ value: 'NT$330' }, { value: '跌破 NT$292' }]
  }
}], null);
process.stdout.write(list.innerHTML);
""".replace("__HISTORY_PANEL_PATH__", json.dumps(str(history_panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "偏多 Long" in result.stdout
    assert "NT$330" in result.stdout
    assert "跌破 NT$292" in result.stdout
    assert "<span>N/A</span>\\n                            <span>N/A</span>" not in result.stdout


def test_operator_workbench_surfaces_actionable_daily_workflow():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    operator_summary_js = (STATIC_DIR / "operator_summary_panel.js").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    watchlist_panel_js = (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")
    maintenance_js = (STATIC_DIR / "maintenance_panel.js").read_text(encoding="utf-8")
    operator_css = (STATIC_DIR / "styles" / "operator_summary.css").read_text(encoding="utf-8")
    history_css = (STATIC_DIR / "styles" / "history_list.css").read_text(encoding="utf-8")
    watchlist_css = (STATIC_DIR / "styles" / "watchlist.css").read_text(encoding="utf-8")
    provider_sla_css = (STATIC_DIR / "styles" / "provider_sla.css").read_text(encoding="utf-8")

    assert 'id="operator-action-list"' in index_html
    assert "今日待處理" in index_html
    assert "operatorActionItems" in operator_summary_js
    assert "fetchWatchlist" in operator_summary_js
    assert "runWatchlist" in operator_summary_js
    assert "data-operator-action" in operator_summary_js
    assert "查看報告" in operator_summary_js
    assert "批次分析" in operator_summary_js
    assert "系統維護" in operator_summary_js

    assert "reportActionBadge" in history_panel_js
    assert "可直接使用" in history_panel_js
    assert "建議刷新資料" in history_panel_js
    assert "建議完整重跑" in history_panel_js
    assert "暫勿採用" in history_panel_js
    assert "history-action-badge" in history_panel_js
    assert ".history-action-badge" in history_css

    assert "watchlistDailyBoard" in watchlist_panel_js
    assert "今日工作台" in watchlist_panel_js
    assert "需處理" in watchlist_panel_js
    assert "watchlist-daily-board" in watchlist_panel_js
    assert ".watchlist-daily-board" in watchlist_css

    assert "<details" in index_html
    assert "maintenance-details" in index_html
    assert "健康摘要" in maintenance_js
    assert ".maintenance-details" in provider_sla_css
    assert ".operator-action-list" in operator_css
    assert ".operator-action-button" in operator_css


def test_market_screener_frontend_tab_is_wired():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    api_client_extensions_js = (STATIC_DIR / "api_client_extensions.js").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    market_screener_js = (STATIC_DIR / "market_screener_panel.js").read_text(encoding="utf-8")
    market_screener_css = (STATIC_DIR / "styles" / "market_screener.css").read_text(encoding="utf-8")
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")

    assert 'id="home-tab-screener"' in index_html
    assert 'id="home-panel-screener"' in index_html
    assert 'id="market-screener-panel"' in index_html
    assert "/static/market_screener_panel.js" in index_html
    assert "/static/styles/market_screener.css" in style_css
    assert "fetchMarketScreener" in api_client_extensions_js
    assert "runMarketScreener" in api_client_extensions_js
    assert "StockAgentMarketScreenerPanel" in app_js
    assert "marketScreenerPanel.loadOnce" in app_js
    assert "Auto-Screener" in market_screener_js
    assert "market-screener-chip" in market_screener_js
    assert "scan_success" in market_screener_js
    assert "result.message" in market_screener_js
    assert "providers" in market_screener_js
    assert "資料源" in market_screener_js
    assert "company_name" in market_screener_js
    assert "data-screener-select" in market_screener_js
    assert "runWatchlist" in market_screener_js
    assert "模式 A" in market_screener_js and "模式 D" in market_screener_js
    assert ".market-screener-grid" in market_screener_css
    assert ".market-screener-mode-picker" in market_screener_css


def test_report_actions_do_not_prompt_refresh_for_provider_sla_only_partial_reports():
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    operator_summary_js = (STATIC_DIR / "operator_summary_panel.js").read_text(encoding="utf-8")
    ui_helpers_js = (STATIC_DIR / "ui_helpers.js").read_text(encoding="utf-8")

    for source in (history_panel_js, operator_summary_js):
        assert "hasRefreshableDataTrustIssue" in source
        assert "provider_sla_critical" in source
        assert "status === 'stale' || status === 'partial'" not in source

    assert "providerSlaOnlyPartial" in ui_helpers_js
    assert "本報告來源提醒" in ui_helpers_js
    assert "本報告部分異常" not in ui_helpers_js
    assert "來源提醒" in history_panel_js
    assert "來源需留意" not in history_panel_js
    assert "isSourceNotice" in operator_summary_js
    assert "requiresDataTrustAction" in operator_summary_js
    assert "sourceNoticeReports" in operator_summary_js
    assert "來源提醒" in operator_summary_js
    assert "無需刷新/重跑" in operator_summary_js
    assert "份需留意" not in operator_summary_js


def test_report_actions_can_add_report_catalysts_to_watchlist_radar():
    report_actions_js = (STATIC_DIR / "report_actions.js").read_text(encoding="utf-8")
    report_navigation_js = (STATIC_DIR / "report_navigation.js").read_text(encoding="utf-8")

    assert "bindWatchlistRadarButtons" in report_actions_js
    assert ".add-to-watchlist-btn" in report_actions_js
    assert "saveWatchlistItem" in report_actions_js
    assert "trigger_condition" in report_actions_js
    assert "impact_direction" in report_actions_js
    assert "notify.success" in report_actions_js
    assert "notify.error" in report_actions_js
    assert "StockAgentReportActions.bindWatchlistRadarButtons" in report_navigation_js


def test_operator_signals_avoid_misleading_health_and_tracking_copy():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    provider_sla_js = (STATIC_DIR / "provider_sla_panel.js").read_text(encoding="utf-8")
    api_quota_js = (STATIC_DIR / "api_quota_panel.js").read_text(encoding="utf-8")
    operator_summary_js = (STATIC_DIR / "operator_summary_panel.js").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    report_preview_js = (STATIC_DIR / "report_preview_panel.js").read_text(encoding="utf-8")

    assert "<span>近期資料信任</span>" in index_html
    assert "無檢查樣本" in provider_sla_js
    assert "尚無檢查樣本，請查看 24 小時或全部紀錄" in provider_sla_js
    assert "全球市場脈絡" in provider_sla_js
    assert "國際新聞脈絡" in provider_sla_js
    assert "總經、匯率、利率與美股風險偏好" in provider_sla_js
    assert "國際重大新聞與供應鏈事件" in provider_sla_js
    assert "rowStateLabel" in provider_sla_js
    assert "row.level === 'ok' && !row.attempts" in provider_sla_js
    assert "quotaHealth" in api_quota_js
    assert "quotaHealth" in operator_summary_js
    assert "LLM/API 健康警示" in api_quota_js
    assert "is-${quotaHealth(service).tone}" in api_quota_js
    assert "awaitingTrackingPrice" in history_panel_js
    assert "待新價格" in history_panel_js
    assert "awaitingTrackingPrice" in report_preview_js
    assert "尚待新價格" in report_preview_js


def test_provider_sla_shows_global_context_sources_before_first_sample():
    provider_sla_js = (STATIC_DIR / "provider_sla_panel.js").read_text(encoding="utf-8")

    assert "EXPECTED_CONTEXT_SOURCES" in provider_sla_js
    assert "mergeExpectedContextRows" in provider_sla_js
    assert "global_market_context" in provider_sla_js
    assert "international_news_context" in provider_sla_js
    assert "hasSource" in provider_sla_js
    assert "尚未建立檢查樣本" in provider_sla_js


def test_decision_tracking_controls_and_target_statuses_are_wired():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    api_client_extensions_js = (STATIC_DIR / "api_client_extensions.js").read_text(encoding="utf-8")
    history_workspace_js = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    decision_tracking_css = (STATIC_DIR / "styles" / "decision_tracking.css").read_text(encoding="utf-8")

    assert 'id="decision-tracking-refresh"' in index_html
    assert 'id="decision-tracking-summary"' in index_html
    assert 'id="decision-tracking-density"' in index_html
    assert "fetchDecisionTracking" in api_client_extensions_js
    assert "saveDecisionTrackingItem" in api_client_extensions_js
    assert "deleteDecisionTrackingItem" in api_client_extensions_js
    assert "refreshDecisionTracking" in api_client_extensions_js

    assert "trackedTickers" in history_workspace_js
    assert "toggleDecisionTracking" in history_workspace_js
    assert "setTrackingCompact" in history_workspace_js
    assert "previewCompactMode" in history_workspace_js
    assert "decision-track-toggle" in history_panel_js
    assert "加入追蹤" in history_panel_js
    assert "取消追蹤" in history_panel_js
    assert "renderTrackingGroups" in history_panel_js
    assert "tracking-stock-group" in history_panel_js
    assert "tracking-report-card" in history_panel_js
    assert "tracking-group-reports" in history_panel_js
    assert "高密度三模式比較" in history_panel_js
    assert "/static/history_workspace.js?v=20260619-tracking-preview-map" in index_html
    assert "mergeTrackingReports" in history_workspace_js
    assert "trackingPayload" in history_workspace_js
    assert "item.latest_reports" in history_workspace_js
    assert "模式 C" in history_panel_js
    assert "latest_reports" in (STATIC_DIR / "decision_tracking_panel.js").read_text(encoding="utf-8")
    assert "tracking-stock-cell" in history_panel_js
    assert "tracking-company-name" in history_panel_js
    assert "tracking-report-cell" in history_panel_js
    assert "tracking-report-date" in history_panel_js

    assert "targetComparisonCell" in history_panel_js
    assert "3月目標" in history_panel_js
    assert "6月目標" in history_panel_js
    assert "12月目標" in history_panel_js
    assert "低於目標" in history_panel_js
    assert "接近目標" in history_panel_js
    assert "已高於目標" in history_panel_js
    assert "tracking-target-cell" in history_panel_js
    assert ".tracking-target-cell" in decision_tracking_css
    assert ".is-below-target" in decision_tracking_css
    assert ".is-near-target" in decision_tracking_css
    assert ".is-above-target" in decision_tracking_css
    assert ".tracking-stock-cell" in decision_tracking_css
    assert ".tracking-report-cell" in decision_tracking_css
    assert ".tracking-stock-group" in decision_tracking_css
    assert ".tracking-report-card" in decision_tracking_css
    assert ".is-compact" in decision_tracking_css
    assert "white-space: normal" in decision_tracking_css


def test_decision_tracking_dense_layout_uses_workspace_efficiently():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    base_css = (STATIC_DIR / "styles" / "base.css").read_text(encoding="utf-8")
    history_list_css = (STATIC_DIR / "styles" / "history_list.css").read_text(encoding="utf-8")
    decision_tracking_css = (STATIC_DIR / "styles" / "decision_tracking.css").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")

    assert "style.css?v=20260627-mode-aware-preview" in index_html
    assert "/static/history_panel.js?v=20260627-mode-aware-preview" in index_html
    assert "/static/report_preview_panel.js?v=20260627-mode-aware-preview" in index_html
    assert "preview_panel.css?v=20260627-mode-aware-preview" in style_css
    assert "decision_tracking.css?v=20260620-compact-colors" in style_css
    assert "max-width: min(1360px, 100%)" in base_css
    assert "grid-template-columns: minmax(520px, 1.35fr) minmax(360px, 0.85fr)" in history_list_css
    assert "tracking-density-row" in history_panel_js
    assert "tracking-report-head" in history_panel_js
    assert "tracking-report-metrics" in history_panel_js
    assert "tracking-target-chip" in history_panel_js
    assert "tracking-target-period" in history_panel_js
    assert "tracking-target-value" in history_panel_js
    assert "tracking-target-label" in history_panel_js
    assert "高密度三模式比較" in history_panel_js
    assert ".tracking-stock-group { display: grid; grid-template-columns: minmax(96px, 0.24fr) minmax(0, 1fr)" in decision_tracking_css
    assert ".tracking-group-reports { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr))" in decision_tracking_css
    assert ".tracking-report-card { min-height: 98px; display: grid; grid-template-columns: 1fr" in decision_tracking_css
    assert ".tracking-target-chip" in decision_tracking_css
    assert ".tracking-target-period" in decision_tracking_css
    assert ".tracking-target-value" in decision_tracking_css
    assert ".tracking-target-label" in decision_tracking_css
    assert ".decision-tracking-table.is-compact .tracking-report-card" in decision_tracking_css


def test_frontend_uiux_accessibility_contracts_are_wired():
    base_css = (STATIC_DIR / "styles" / "base.css").read_text(encoding="utf-8")
    forms_css = (STATIC_DIR / "styles" / "forms_controls.css").read_text(encoding="utf-8")
    history_shell_css = (STATIC_DIR / "styles" / "history_shell.css").read_text(encoding="utf-8")
    history_list_css = (STATIC_DIR / "styles" / "history_list.css").read_text(encoding="utf-8")
    loading_report_css = (STATIC_DIR / "styles" / "loading_report.css").read_text(encoding="utf-8")
    notifications_css = (STATIC_DIR / "styles" / "notifications.css").read_text(encoding="utf-8")
    preview_panel_css = (STATIC_DIR / "styles" / "preview_panel.css").read_text(encoding="utf-8")
    provider_sla_css = (STATIC_DIR / "styles" / "provider_sla.css").read_text(encoding="utf-8")
    watchlist_css = (STATIC_DIR / "styles" / "watchlist.css").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    home_tabs_js = (STATIC_DIR / "home_tabs.js").read_text(encoding="utf-8")
    notification_center_js = (STATIC_DIR / "notification_center.js").read_text(encoding="utf-8")

    assert _contrast_ratio("#ffffff", "#1d4ed8") >= 4.5
    assert _contrast_ratio("#94a3b8", "#0f172a") >= 4.5
    assert "--primary-action: #1d4ed8" in base_css
    assert ".hint-text" in loading_report_css
    assert "color: var(--text-secondary)" in loading_report_css
    assert "background: var(--primary-action)" in loading_report_css

    assert 'aria-label="預覽 ${escapeHtml(r.ticker' in history_panel_js
    assert 'aria-label="刪除 ${escapeHtml(r.ticker' in history_panel_js
    assert 'role="button" tabindex="0" aria-label="預覽 ${escapeHtml(report.ticker' in history_panel_js
    assert "isActivationKey" in history_panel_js
    assert "event.key === ' '" in history_panel_js
    assert "event.preventDefault()" in history_panel_js

    assert "activateNextTab" in home_tabs_js
    assert "ArrowRight" in home_tabs_js
    assert "ArrowLeft" in home_tabs_js
    assert "Home" in home_tabs_js
    assert "End" in home_tabs_js
    assert "tabIndex" in home_tabs_js

    assert "focusableSelectors" in notification_center_js
    assert "trapFocus" in notification_center_js
    assert "event.key === 'Tab'" in notification_center_js
    assert "firstFocusable" in notification_center_js
    assert "lastFocusable" in notification_center_js

    combined_css = "\n".join([
        base_css,
        forms_css,
        history_shell_css,
        history_list_css,
        loading_report_css,
        notifications_css,
        preview_panel_css,
        provider_sla_css,
        watchlist_css,
    ])
    assert "transition: all" not in combined_css
    assert "@media (prefers-reduced-motion: reduce)" in base_css
    assert "transition-duration: 0.01ms" in base_css
    assert "animation: none" in base_css

    assert ".home-tab-button" in history_shell_css and "min-height: 44px" in history_shell_css
    assert ".history-filter-select" in history_list_css and "min-height: 44px" in history_list_css
    assert ".history-version-toggle" in history_list_css and "min-height: 44px" in history_list_css
    assert ".history-search" in history_list_css and "min-height: 44px" in history_list_css
    assert ".delete-btn" in history_list_css and "min-width: 44px" in history_list_css
    assert ".pager-btn" in history_list_css and "width: 44px" in history_list_css
    assert ".report-download-button" in loading_report_css and "min-height: 44px" in loading_report_css
    assert ".confirm-dialog-button" in notifications_css and "min-height: 44px" in notifications_css
    assert ".toast-close" in notifications_css and "width: 44px" in notifications_css
    assert ".preview-refresh-button" in preview_panel_css and "min-height: 44px" in preview_panel_css
    assert ".preview-rerun-button" in preview_panel_css and "min-height: 44px" in preview_panel_css
    assert ".provider-sla-window" in provider_sla_css and "min-height: 44px" in provider_sla_css
    assert ".maintenance-button" in provider_sla_css and "min-height: 44px" in provider_sla_css
    assert ".watchlist-delete-button" in watchlist_css and "min-height: 44px" in watchlist_css


def test_frontend_static_modules_are_sized():
    size_limits = {
        "app.js": 300,
        "history_workspace.js": 260,
        "ui_helpers.js": 140,
        "api_client.js": 110,
        "provider_sla_panel.js": 210,
        "maintenance_panel.js": 150,
        "view_controller.js": 40,
        "history_filters.js": 50,
        "report_actions.js": 45,
        "report_navigation.js": 100,
        "home_tabs.js": 50,
        "style.css": 40,
        "notification_center.js": 120,
        "styles/history_list.css": 320,
        "styles/decision_tracking.css": 80,
        "styles/notifications.css": 160,
        "styles/preview_panel.css": 220,
        "styles/report_compare.css": 90,
        "styles/provider_sla.css": 220,
        "styles/watchlist.css": 80,
        "styles/market_screener.css": 90,
        "api_client_extensions.js": 90,
        "ops_workspace.js": 160,
        "market_screener_panel.js": 140,
        "api_quota_panel.js": 100,
        "performance_panel.js": 100,
        "watchlist_trigger_form.js": 90,
        "temporal_memory_panel.js": 70,
        "watchlist_panel.js": 180,
        "report_compare_panel.js": 160,
        "operator_summary_panel.js": 150,
        "decision_tracking_panel.js": 160,
    }
    for relative_path, limit in size_limits.items():
        path = STATIC_DIR / relative_path
        assert len(path.read_text(encoding="utf-8").splitlines()) < limit, relative_path


def test_visual_regression_script_is_documented():
    script = ROOT / "scripts" / "visual_regression.sh"
    setup_script = ROOT / "scripts" / "setup_visual_regression.sh"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert script.exists()
    assert setup_script.exists()
    assert "tests/test_frontend_visual_optional.py" in script.read_text(encoding="utf-8")
    assert "tests/test_report_chart_visual_optional.py" in script.read_text(encoding="utf-8")
    assert "VISUAL_REGRESSION_REQUIRED" in script.read_text(encoding="utf-8")
    assert "playwright install chromium" in setup_script.read_text(encoding="utf-8")
    assert "scripts/setup_visual_regression.sh" in readme
    assert "scripts/visual_regression.sh" in readme
    assert "RUN_VISUAL_REGRESSION=1 scripts/ci_gate.sh" in readme
