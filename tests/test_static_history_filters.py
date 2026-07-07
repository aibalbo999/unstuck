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
    assert '<span>報告建議</span>' in index_html
    assert '<option value="all">全部報告建議</option>' in index_html
    assert '<span>投資建議</span>' not in index_html
    assert '<option value="all">全部建議</option>' not in index_html
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
    assert 'id="watchlist-symbol-suggestions"' in index_html
    assert 'id="watchlist-import-text"' in index_html
    assert 'id="watchlist-import-btn"' in index_html
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
    assert "fetchDailyDecisionDashboard" in api_client_extensions_js
    assert "fetchSymbolSuggestions" in api_client_extensions_js
    assert "importWatchlistText" in api_client_extensions_js
    assert "apiClient.fetchDailyDecisionDashboard" in operator_summary_js
    assert "reports_needing_rerun" in operator_summary_js
    assert "watchlist_high_priority" in operator_summary_js
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
    assert "重跑${shortLabel}報告結論" in report_preview_js
    assert "重跑${shortLabel}最終建議" not in report_preview_js
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
    assert "degraded_enrichment_count" in provider_sla_js
    assert "降級可用" in provider_sla_js
    assert "availabilityAttemptsForStats" in provider_sla_js
    assert "未設定" in provider_sla_js
    assert "先使用仍有效的快取" in provider_sla_js
    assert "系統會優先補快取" not in provider_sla_js
    assert "資料取得率" in provider_sla_js

    assert "來源明細" in provider_sla_js
    assert "provider-sla-provider-list" in provider_sla_js
    assert "analysis_text_stale" in history_workspace_js
    assert "payload.analysis_text_stale ?? previewReport.analysis_text_stale" in history_workspace_js
    assert "payload.analysis_text_stale_message ?? previewReport.analysis_text_stale_message" in history_workspace_js
    assert "evidence_exit_gate" in history_panel_js
    assert "report_conformance" in history_panel_js
    assert "數字證據需人工核對" in history_panel_js
    assert "報告符合性未通過" in history_panel_js
    assert "reportQualityBadge" in report_preview_js
    assert "證據抽查未通過" in report_preview_js
    assert "報告符合性未通過" in report_preview_js
    assert '<h2 id="preview-title" class="preview-title">報告建議</h2>' in index_html
    assert '<h2 id="preview-title" class="preview-title">投資建議</h2>' not in index_html
    assert 'aria-label="關閉報告預覽"' in index_html
    assert 'aria-label="關閉投資建議預覽"' not in index_html
    assert '<span class="preview-label">報告建議</span>' in index_html
    assert '<span>重跑報告結論</span>' in index_html
    assert "重跑最終建議" not in index_html
    assert "報告建議" in report_preview_js
    assert "仍需自行判斷" in report_preview_js
    assert "${report.ticker} 投資建議" not in report_preview_js
    assert "label: '建議'" not in report_preview_js
    assert "證據抽查未通過" in operator_summary_js
    assert "報告符合性未通過" in operator_summary_js
    assert "資料新鮮 ${fresh} / 抽樣 ${reports.length}" in operator_summary_js
    assert "fresh ${fresh} / sampled ${reports.length}" not in operator_summary_js
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
    assert "pipelineModeLabel" in report_compare_js
    assert "window.StockAgentUi?.pipelineModeLabel" in report_compare_js
    assert "pipelineModeLabel: ui.pipelineModeLabel" in history_workspace_js
    assert "${report.pipeline_id || 'v1'}" not in report_compare_js
    assert "比較基準" in report_compare_js
    assert "比較樣本" in report_compare_js
    assert "比較結論" in report_compare_js
    assert "compareSummaryLabel" in report_compare_js
    assert "同股票同模式" in report_compare_js
    assert "報告建議變化" in report_compare_js
    assert "使用提醒" in report_compare_js
    assert "不代表即時交易指令" in report_compare_js
    assert "判讀層次" in report_compare_js
    assert "報告差異不等於市場因果" in report_compare_js
    assert "搭配資料可信度與追蹤報酬判讀" in report_compare_js
    assert "['建議'" not in report_compare_js
    assert "pipelineModeLabel(left.pipeline_id || 'v1')" in report_compare_js
    assert "dateOrderLabel(compatibility.date_order)" in report_compare_js
    assert "compareWarningMessage" in report_compare_js
    assert "different_pipeline" in report_compare_js
    assert "兩份報告模式不同" in report_compare_js
    assert "跨視角比較" in report_compare_js
    assert "decision_needs_rerun" in report_compare_js
    assert "若要比較投資判斷，需先重跑結論" in report_compare_js
    assert "需先重跑結論，再比較投資判斷" not in report_compare_js
    assert " vs " not in report_compare_js
    assert "/api/watchlist" in api_client_extensions_js
    assert "watchlist-trigger-vix" in index_html
    assert "StockAgentWatchlistTriggerForm" in (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")
    assert "fetchSymbolSuggestions" in (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")
    assert "importWatchlistText" in (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")
    assert "latest_trigger_event" in (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")
    assert "watchlist-trigger-summary" in (STATIC_DIR / "watchlist_trigger_form.js").read_text(encoding="utf-8")
    assert "/api/performance/stats" in api_client_extensions_js
    assert "fetchPerformanceStats" in api_client_extensions_js
    assert "命中率" in performance_panel_js
    assert "平均 ROI" in performance_panel_js
    assert "sampleConfidenceLabel" in performance_panel_js
    assert "樣本不足，僅供觀察" in performance_panel_js
    assert "count >= 10" in performance_panel_js
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
    assert "pipelineModeLabel" in active_jobs_js
    assert "pipelineModeLabel: ui.pipelineModeLabel" in ops_workspace_js
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


def test_stock_snapshot_panel_is_wired_for_consumer_stock_page():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    api_client_extensions_js = (STATIC_DIR / "api_client_extensions.js").read_text(encoding="utf-8")
    stock_snapshot_js = (STATIC_DIR / "stock_snapshot_panel.js").read_text(encoding="utf-8")
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    stock_snapshot_css = (STATIC_DIR / "styles" / "stock_snapshot.css").read_text(encoding="utf-8")

    assert 'id="stock-snapshot-panel"' in index_html
    assert 'id="stock-snapshot-load-btn"' in index_html
    assert 'id="stock-snapshot-shortcuts"' in index_html
    assert "股票快照" in index_html
    assert "/static/stock_snapshot_panel.js" in index_html
    assert "fetchStockSnapshot" in api_client_extensions_js
    assert "/api/stocks/" in api_client_extensions_js
    assert "StockAgentStockSnapshotPanel.create" in app_js
    assert "stockSnapshotPanel.bindEvents" in app_js
    assert "shortcutsRoot: stockSnapshotShortcutsEl" in app_js
    assert "getRecentTickers" in stock_snapshot_js
    assert "rememberTicker" in stock_snapshot_js
    assert "normalizeTickerInput" in stock_snapshot_js
    assert "data-stock-snapshot-shortcut" in stock_snapshot_js
    assert "stock-snapshot-summary-rail" in stock_snapshot_js
    assert "stock-snapshot-grid" in stock_snapshot_js
    assert "company_profile" in stock_snapshot_js
    assert "renderCompanyProfile" in stock_snapshot_js
    assert "mode_suggestions" in stock_snapshot_js
    assert "data_quality" in stock_snapshot_js
    assert "market_session" in stock_snapshot_js
    assert "renderMarketSession" in stock_snapshot_js
    assert "price_trend" in stock_snapshot_js
    assert "renderTrend" in stock_snapshot_js
    assert "performance_history" in stock_snapshot_js
    assert "renderPerformanceHistory" in stock_snapshot_js
    assert "selectPerformanceRange" in stock_snapshot_js
    assert "technical_summary" in stock_snapshot_js
    assert "renderTechnicalSummary" in stock_snapshot_js
    assert "analyst_outlook" in stock_snapshot_js
    assert "renderAnalystOutlook" in stock_snapshot_js
    assert "earnings_forecast" in stock_snapshot_js
    assert "renderEarningsForecast" in stock_snapshot_js
    assert "share_statistics" in stock_snapshot_js
    assert "renderShareStatistics" in stock_snapshot_js
    assert "risk_liquidity" in stock_snapshot_js
    assert "renderRiskLiquidity" in stock_snapshot_js
    assert "profitability_quality" in stock_snapshot_js
    assert "renderProfitabilityQuality" in stock_snapshot_js
    assert "financial_health" in stock_snapshot_js
    assert "renderFinancialHealth" in stock_snapshot_js
    assert "financial_trends" in stock_snapshot_js
    assert "renderFinancialTrends" in stock_snapshot_js
    assert "dividend_profile" in stock_snapshot_js
    assert "renderDividendProfile" in stock_snapshot_js
    assert "event_calendar" in stock_snapshot_js
    assert "renderEventCalendar" in stock_snapshot_js
    assert "alert_suggestions" in stock_snapshot_js
    assert "renderAlertSuggestions" in stock_snapshot_js
    assert "applyAlertSuggestion" in stock_snapshot_js
    assert "peer_comparison" in stock_snapshot_js
    assert "renderPeerComparison" in stock_snapshot_js
    assert "ownership_flow" in stock_snapshot_js
    assert "renderOwnershipFlow" in stock_snapshot_js
    assert "valuation_range" in stock_snapshot_js
    assert "renderValuationRange" in stock_snapshot_js
    assert "stock-snapshot-trend" in stock_snapshot_js
    assert "stock-snapshot-performance" in stock_snapshot_js
    assert "stock-snapshot-company-profile" in stock_snapshot_js
    assert "stock-snapshot-session" in stock_snapshot_js
    assert "stock-snapshot-technical" in stock_snapshot_js
    assert "stock-snapshot-analyst" in stock_snapshot_js
    assert "stock-snapshot-earnings" in stock_snapshot_js
    assert "stock-snapshot-shares" in stock_snapshot_js
    assert "stock-snapshot-risk" in stock_snapshot_js
    assert "stock-snapshot-profitability" in stock_snapshot_js
    assert "stock-snapshot-dividend" in stock_snapshot_js
    assert "stock-snapshot-calendar" in stock_snapshot_js
    assert "stock-snapshot-alerts" in stock_snapshot_js
    assert "stock-snapshot-fundamentals" in stock_snapshot_js
    assert "stock-snapshot-financial-trends" in stock_snapshot_js
    assert "stock-snapshot-peers" in stock_snapshot_js
    assert "stock-snapshot-ownership" in stock_snapshot_js
    assert "stock-snapshot-valuation-range" in stock_snapshot_js
    assert "<polyline" in stock_snapshot_js
    assert "styles/stock_snapshot.css" in style_css
    assert ".stock-snapshot-panel" in stock_snapshot_css
    assert ".stock-snapshot-shortcuts" in stock_snapshot_css
    assert ".stock-snapshot-summary-rail" in stock_snapshot_css
    assert ".stock-snapshot-grid" in stock_snapshot_css
    assert ".stock-snapshot-session" in stock_snapshot_css
    assert ".stock-snapshot-session-grid" in stock_snapshot_css
    assert ".stock-snapshot-trend" in stock_snapshot_css
    assert ".stock-snapshot-trend-chart" in stock_snapshot_css
    assert ".stock-snapshot-performance" in stock_snapshot_css
    assert ".stock-snapshot-performance-controls" in stock_snapshot_css
    assert ".stock-snapshot-performance-chart" in stock_snapshot_css
    assert ".stock-snapshot-company-profile" in stock_snapshot_css
    assert ".stock-snapshot-company-profile-grid" in stock_snapshot_css
    assert ".stock-snapshot-technical" in stock_snapshot_css
    assert ".stock-snapshot-technical-grid" in stock_snapshot_css
    assert ".stock-snapshot-analyst" in stock_snapshot_css
    assert ".stock-snapshot-analyst-grid" in stock_snapshot_css
    assert ".stock-snapshot-earnings" in stock_snapshot_css
    assert ".stock-snapshot-earnings-grid" in stock_snapshot_css
    assert ".stock-snapshot-shares" in stock_snapshot_css
    assert ".stock-snapshot-shares-grid" in stock_snapshot_css
    assert ".stock-snapshot-risk" in stock_snapshot_css
    assert ".stock-snapshot-risk-grid" in stock_snapshot_css
    assert ".stock-snapshot-profitability" in stock_snapshot_css
    assert ".stock-snapshot-profitability-grid" in stock_snapshot_css
    assert ".stock-snapshot-dividend" in stock_snapshot_css
    assert ".stock-snapshot-dividend-bars" in stock_snapshot_css
    assert ".stock-snapshot-calendar" in stock_snapshot_css
    assert ".stock-snapshot-calendar-grid" in stock_snapshot_css
    assert ".stock-snapshot-alerts" in stock_snapshot_css
    assert ".stock-snapshot-alert-grid" in stock_snapshot_css
    assert ".stock-snapshot-fundamentals" in stock_snapshot_css
    assert ".stock-snapshot-fundamental-grid" in stock_snapshot_css
    assert ".stock-snapshot-financial-trends" in stock_snapshot_css
    assert ".stock-snapshot-financial-trend-row" in stock_snapshot_css
    assert ".stock-snapshot-peers" in stock_snapshot_css
    assert ".stock-snapshot-peer-table" in stock_snapshot_css
    assert ".stock-snapshot-ownership" in stock_snapshot_css
    assert ".stock-snapshot-ownership-grid" in stock_snapshot_css
    assert ".stock-snapshot-valuation-range" in stock_snapshot_css
    assert ".stock-snapshot-valuation-band" in stock_snapshot_css


def test_stock_snapshot_panel_renders_price_trend_sparkline():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  price_trend: {
    label: '近一年月收盤',
    latest_price: 950,
    returns: { '1m': 3.26, '3m': 7.95, '1y': 35.71 },
    sparkline: [
      { date: '2025-08-31', price: 700 },
      { date: '2026-07-31', price: 950 }
    ]
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-trend" in result.stdout
    assert "<polyline" in result.stdout
    assert "1M" in result.stdout
    assert "+3.3%" in result.stdout
    assert "3M" in result.stdout
    assert "+8.0%" in result.stdout
    assert "1Y" in result.stdout
    assert "+35.7%" in result.stdout


def test_stock_snapshot_enter_loads_normalized_taiwan_ticker():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {
  localStorage: {
    getItem: () => '[]',
    setItem: () => {}
  }
};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const listeners = {};
const tickerInput = {
  value: '2330',
  addEventListener: (event, handler) => { listeners[event] = handler; }
};
const root = {
  hidden: true,
  innerHTML: '',
  addEventListener: () => {}
};
const loadButton = {
  disabled: false,
  querySelector: () => ({ textContent: '' }),
  addEventListener: () => {}
};
let requestedTicker = '';
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root, loadButton, tickerInput },
  apiClient: {
    fetchStockSnapshot: async ticker => {
      requestedTicker = ticker;
      return { ticker, identity: {}, quote: {}, valuation: {}, dividends: {}, chip: {}, data_quality: {} };
    }
  },
  notify: { error: () => {} }
});
panel.bindEvents();
const event = {
  key: 'Enter',
  defaultPrevented: false,
  stopped: false,
  preventDefault() { this.defaultPrevented = true; },
  stopPropagation() { this.stopped = true; }
};
Promise.resolve(listeners.keydown(event)).then(() => {
  process.stdout.write(JSON.stringify({ requestedTicker, inputValue: tickerInput.value, defaultPrevented: event.defaultPrevented, stopped: event.stopped }));
});
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    payload = json.loads(result.stdout)
    assert payload == {
        "requestedTicker": "2330.TW",
        "inputValue": "2330.TW",
        "defaultPrevented": True,
        "stopped": True,
    }


def test_stock_snapshot_panel_renders_shortcuts_with_recent_tickers():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {
  localStorage: {
    getItem: key => key === 'stockAgent.stockSnapshot.recentTickers' ? '["2308.TW","AAPL"]' : null,
    setItem: () => {}
  }
};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const shortcutsRoot = { innerHTML: '', addEventListener: () => {} };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { shortcutsRoot }
});
panel.bindEvents();
process.stdout.write(shortcutsRoot.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-shortcuts" in result.stdout
    assert "data-stock-snapshot-shortcut=\"2308.TW\"" in result.stdout
    assert "data-stock-snapshot-shortcut=\"AAPL\"" in result.stdout
    assert "data-stock-snapshot-shortcut=\"2330.TW\"" in result.stdout
    assert "最近" in result.stdout
    assert "常用" in result.stdout


def test_stock_snapshot_panel_renders_company_profile():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  company_profile: {
    status: 'available',
    label: '公司檔案',
    summary: '台積電提供晶圓代工與先進封裝服務，服務全球無晶圓廠客戶。',
    website: 'https://www.tsmc.com',
    facts: [
      { label: '產業', value: 'Technology / Semiconductors' },
      { label: '市場', value: 'Taiwan · TAI' },
      { label: '幣別', value: 'TWD' },
      { label: '員工', value: '77,000' }
    ]
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-company-profile" in result.stdout
    assert "公司檔案" in result.stdout
    assert "台積電提供晶圓代工與先進封裝服務" in result.stdout
    assert "https://www.tsmc.com" in result.stdout
    assert "官網" in result.stdout
    assert "Technology / Semiconductors" in result.stdout
    assert "Taiwan · TAI" in result.stdout
    assert "77,000" in result.stdout


def test_stock_snapshot_panel_renders_performance_history_ranges():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  performance_history: {
    status: 'available',
    label: '多週期走勢',
    default_range: '1y',
    ranges: [
      { key: '1m', label: '1M', return_pct: 3.26, points: [{ date: '2026-06-30', price: 920 }, { date: '2026-07-31', price: 950 }] },
      { key: '3m', label: '3M', return_pct: 7.95, points: [{ date: '2026-04-30', price: 880 }, { date: '2026-07-31', price: 950 }] },
      { key: '1y', label: '1Y', return_pct: 35.71, points: [{ date: '2025-07-31', price: 700 }, { date: '2026-07-31', price: 950 }] },
      { key: '5y', label: '5Y', return_pct: 216.67, points: [{ date: '2021-07-31', price: 300 }, { date: '2026-07-31', price: 950 }] }
    ]
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-performance" in result.stdout
    assert "多週期走勢" in result.stdout
    assert "data-stock-snapshot-range=\"1m\"" in result.stdout
    assert "data-stock-snapshot-range=\"3m\"" in result.stdout
    assert "data-stock-snapshot-range=\"1y\"" in result.stdout
    assert "data-stock-snapshot-range=\"5y\"" in result.stdout
    assert "+35.7%" in result.stdout
    assert "+216.7%" not in result.stdout
    assert "<polyline" in result.stdout
    assert "1Y" in result.stdout


def test_stock_snapshot_panel_switches_performance_history_range():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const chart = { innerHTML: '' };
const buttons = [
  { dataset: { stockSnapshotRange: '1y' }, classList: { active: false, toggle(name, value) { if (name === 'is-active') this.active = Boolean(value); } } },
  { dataset: { stockSnapshotRange: '5y' }, classList: { active: false, toggle(name, value) { if (name === 'is-active') this.active = Boolean(value); } } }
];
const root = {
  hidden: true,
  innerHTML: '',
  querySelector: selector => selector === '[data-stock-snapshot-performance-chart]' ? chart : null,
  querySelectorAll: selector => selector === '[data-stock-snapshot-range]' ? buttons : []
};
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  performance_history: {
    status: 'available',
    label: '多週期走勢',
    default_range: '1y',
    ranges: [
      { key: '1y', label: '1Y', return_pct: 35.71, points: [{ date: '2025-07-31', price: 700 }, { date: '2026-07-31', price: 950 }] },
      { key: '5y', label: '5Y', return_pct: 216.67, points: [{ date: '2021-07-31', price: 300 }, { date: '2026-07-31', price: 950 }] }
    ]
  }
});
panel.selectPerformanceRange('5y');
process.stdout.write(JSON.stringify({ html: chart.innerHTML, active: buttons.map(button => button.classList.active) }));
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    payload = json.loads(result.stdout)
    assert "5Y" in payload["html"]
    assert "+216.7%" in payload["html"]
    assert payload["active"] == [False, True]


def test_stock_snapshot_panel_renders_market_session_summary():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  market_session: {
    current_price: 950,
    change: 20,
    change_pct: 2.15,
    direction: 'up',
    open: 940,
    previous_close: 930,
    day_range: { low: 925, high: 955 },
    day_position_pct: 83.33,
    volume: 130000000,
    avg_volume: 100000000,
    volume_vs_avg_pct: 30
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-session" in result.stdout
    assert "今日行情" in result.stdout
    assert "+20.00" in result.stdout
    assert "+2.2%" in result.stdout
    assert "開盤" in result.stdout
    assert "940" in result.stdout
    assert "昨收" in result.stdout
    assert "930" in result.stdout
    assert "日內" in result.stdout
    assert "925 / 955" in result.stdout
    assert "量 1.3億" in result.stdout
    assert "較均量 +30.0%" in result.stdout


def test_stock_snapshot_panel_renders_technical_summary():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  technical_summary: {
    status: 'available',
    label: '上升趨勢',
    moving_averages: {
      ma_3m: { label: '3M 均線', value: 923.33, distance_pct: 2.89 },
      ma_6m: { label: '6M 均線', value: 891.67, distance_pct: 6.54 },
      ma_12m: { label: '12M 均線', value: 827.5, distance_pct: 14.8 }
    },
    range_52w: { low: 580, high: 1000, position_pct: 88.1, drawdown_from_high_pct: -5 },
    momentum: { '1m': 3.26, '3m': 7.95, '1y': 35.71 },
    signals: ['現價高於 3M / 6M 均線', '接近 52 週高檔', '3M 動能 +8.0%']
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-technical" in result.stdout
    assert "技術面" in result.stdout
    assert "上升趨勢" in result.stdout
    assert "3M 均線" in result.stdout
    assert "923.33" in result.stdout
    assert "+2.9%" in result.stdout
    assert "52週位置" in result.stdout
    assert "88.1%" in result.stdout
    assert "距高點 -5.0%" in result.stdout
    assert "3M 動能 +8.0%" in result.stdout
    assert "接近 52 週高檔" in result.stdout


def test_stock_snapshot_panel_renders_analyst_outlook():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  analyst_outlook: {
    status: 'available',
    label: '目標價上行',
    target: { price: 1050, label: 'NT$1050.00', upside_pct: 10.53 },
    consensus: { recommendation: 'buy', recommendation_label: '買進', analyst_count: 32 },
    valuation: { forward_pe: { value: 19.8, label: '19.8x' } },
    growth: { earnings_growth: { value: 14, label: '14.0%' } },
    signals: ['目標價上行 +10.5%', '32 位分析師共識買進', 'EPS 成長 14.0%']
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-analyst" in result.stdout
    assert "分析師展望" in result.stdout
    assert "目標價上行" in result.stdout
    assert "目標價" in result.stdout
    assert "NT$1050.00" in result.stdout
    assert "+10.5%" in result.stdout
    assert "共識" in result.stdout
    assert "買進" in result.stdout
    assert "32 位" in result.stdout
    assert "Forward P/E" in result.stdout
    assert "19.8x" in result.stdout
    assert "EPS 成長" in result.stdout
    assert "14.0%" in result.stdout


def test_stock_snapshot_panel_renders_earnings_forecast():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  earnings_forecast: {
    status: 'available',
    label: 'EPS 預期成長',
    trailing_eps: { value: 45, label: '45.00' },
    forward_eps: { value: 50, label: '50.00' },
    forward_eps_change_pct: 11.11,
    growth: {
      earnings_growth: { value: 14, label: '14.0%' },
      revenue_growth: { value: 18.4, label: '18.4%' }
    },
    analyst_count: 32,
    next_earnings: { type: 'earnings_date', label: '財報日', date: '2026-07-18', days_until: 13 },
    signals: ['Forward EPS +11.1%', 'EPS 成長 14.0%', '32 位分析師覆蓋']
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-earnings" in result.stdout
    assert "盈餘預估" in result.stdout
    assert "EPS 預期成長" in result.stdout
    assert "Forward EPS +11.1%" in result.stdout
    assert "Trailing EPS" in result.stdout
    assert "45.00" in result.stdout
    assert "Forward EPS" in result.stdout
    assert "50.00" in result.stdout
    assert "EPS 成長" in result.stdout
    assert "14.0%" in result.stdout
    assert "下次財報" in result.stdout
    assert "2026-07-18" in result.stdout
    assert "32 位分析師" in result.stdout


def test_stock_snapshot_panel_renders_share_statistics():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  share_statistics: {
    status: 'available',
    label: '機構持股高',
    shares_outstanding: 1000000000,
    float_shares: 800000000,
    float_pct_of_shares: 80,
    insider_ownership_pct: 12,
    institutional_ownership_pct: 70,
    short_interest: {
      shares_short: 20000000,
      short_ratio: 1.8,
      short_percent_of_float_pct: 2.5
    },
    signals: ['流通股 80.0%', '機構持股 70.0%', '空單占流通股 2.5%']
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-shares" in result.stdout
    assert "股本結構" in result.stdout
    assert "機構持股高" in result.stdout
    assert "流通股 80.0%" in result.stdout
    assert "在外股數" in result.stdout
    assert "10.0億" in result.stdout
    assert "流通股數" in result.stdout
    assert "8.0億" in result.stdout
    assert "機構持股" in result.stdout
    assert "70.0%" in result.stdout
    assert "放空壓力" in result.stdout
    assert "2,000.0萬" in result.stdout
    assert "空單/流通 2.5%" in result.stdout


def test_stock_snapshot_panel_renders_risk_liquidity():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  risk_liquidity: {
    status: 'available',
    label: '流動性活躍',
    beta: { value: 1.05, label: '1.05' },
    drawdown_from_52w_high_pct: -5,
    volume_vs_avg_pct: 30,
    debt_to_equity_pct: 28,
    current_ratio: { value: 2.1, label: '2.10' },
    signals: ['Beta 1.05', '距52週高點 -5.0%', '成交量較均量 +30.0%']
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-risk" in result.stdout
    assert "風險與流動性" in result.stdout
    assert "流動性活躍" in result.stdout
    assert "Beta 1.05" in result.stdout
    assert "Beta" in result.stdout
    assert "1.05" in result.stdout
    assert "52週回撤" in result.stdout
    assert "-5.0%" in result.stdout
    assert "成交量/均量" in result.stdout
    assert "+30.0%" in result.stdout
    assert "負債權益比" in result.stdout
    assert "28.0%" in result.stdout
    assert "流動比率" in result.stdout
    assert "2.10" in result.stdout


def test_stock_snapshot_panel_renders_profitability_quality():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  profitability_quality: {
    status: 'available',
    label: '獲利品質強',
    gross_margin_pct: 56,
    operating_margin_pct: 45,
    net_margin_pct: 38,
    roe_pct: 31,
    roa_pct: 16.5,
    fcf_margin_pct: 34,
    signals: ['ROE 31.0%', '淨利率 38.0%', 'FCF margin 34.0%']
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-profitability" in result.stdout
    assert "獲利品質" in result.stdout
    assert "獲利品質強" in result.stdout
    assert "ROE 31.0%" in result.stdout
    assert "毛利率" in result.stdout
    assert "56.0%" in result.stdout
    assert "營業利益率" in result.stdout
    assert "45.0%" in result.stdout
    assert "淨利率" in result.stdout
    assert "38.0%" in result.stdout
    assert "ROA" in result.stdout
    assert "16.5%" in result.stdout
    assert "FCF margin" in result.stdout
    assert "34.0%" in result.stdout


def test_stock_snapshot_panel_renders_summary_rail():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: { price_label: '950.00' },
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  market_session: { current_price: 950, change_pct: 2.15, direction: 'up' },
  valuation_range: { status: 'available', label: '合理區間' },
  analyst_outlook: { status: 'available', label: '目標價上行' },
  profitability_quality: { status: 'available', label: '獲利品質強' },
  event_calendar: { status: 'available', next_event: { label: '財報日', date_label: '2026-07-18', days_until: 13 } }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-summary-rail" in result.stdout
    assert "現價" in result.stdout
    assert "950.00" in result.stdout
    assert "+2.2%" in result.stdout
    assert "估值" in result.stdout
    assert "合理區間" in result.stdout
    assert "獲利" in result.stdout
    assert "獲利品質強" in result.stdout
    assert "事件" in result.stdout
    assert "財報日" in result.stdout


def test_stock_snapshot_panel_renders_dividend_profile():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  dividend_profile: {
    status: 'available',
    label: '配息穩定',
    annual_dividend: { value: 12, label: 'NT$12.00' },
    yield: { value: 0.025, label: '2.50%' },
    payout_ratio: { value: 0.42, label: '42.00%' },
    history: {
      years: ['2022', '2023', '2024', '2025', '2026'],
      dividends: [8.5, 10, 11.5, 12, 13],
      year_count: 5,
      latest_annual_dividend: 13,
      latest_yoy_pct: 8.33
    },
    coverage: { fcf_coverage_ratio: 70.83 },
    signals: ['連續 5 年有配息', '近一年配息成長 +8.3%', 'FCF 覆蓋 70.8x']
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-dividend" in result.stdout
    assert "股利品質" in result.stdout
    assert "配息穩定" in result.stdout
    assert "年化股利" in result.stdout
    assert "NT$12.00" in result.stdout
    assert "殖利率" in result.stdout
    assert "2.50%" in result.stdout
    assert "配息率" in result.stdout
    assert "42.00%" in result.stdout
    assert "FCF 覆蓋" in result.stdout
    assert "70.8x" in result.stdout
    assert "2026" in result.stdout
    assert "13" in result.stdout
    assert "近一年配息成長 +8.3%" in result.stdout


def test_stock_snapshot_panel_renders_event_calendar():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  event_calendar: {
    status: 'available',
    label: '下一事件：財報日',
    next_event: { type: 'earnings_date', label: '財報日', days_until: 13 },
    events: [
      {
        type: 'earnings_date',
        label: '財報日',
        date_label: '2026-07-18 - 2026-07-20',
        timing: 'upcoming',
        days_until: 13,
        source: 'yfinance calendar'
      },
      {
        type: 'ex_dividend_date',
        label: '除息日',
        date_label: '2026-08-01',
        timing: 'upcoming',
        days_until: 27,
        source: 'yfinance calendar'
      }
    ]
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-calendar" in result.stdout
    assert "關鍵日期" in result.stdout
    assert "下一事件：財報日" in result.stdout
    assert "財報日" in result.stdout
    assert "2026-07-18 - 2026-07-20" in result.stdout
    assert "13 天後" in result.stdout
    assert "除息日" in result.stdout
    assert "2026-08-01" in result.stdout
    assert "27 天後" in result.stdout
    assert "yfinance calendar" in result.stdout


def test_stock_snapshot_panel_renders_alert_suggestions():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  alert_suggestions: {
    status: 'available',
    label: '建議設定 2 個提醒',
    suggestions: [
      {
        key: 'event_earnings_date_2026-07-18',
        category: 'event',
        label: '財報日前提醒',
        detail: '財報日 2026-07-18 前 14 天提醒',
        pipeline: 'v4',
        schedule_slots: ['pre_market'],
        triggers: [{ type: 'event_upcoming', event_type: 'earnings_date', target_date: '2026-07-18', days_before: 14, label: '財報日' }]
      },
      {
        key: 'price_analyst_target',
        category: 'price',
        label: '接近分析師目標價',
        detail: '現價接近 1,050 時提醒',
        pipeline: 'v2',
        schedule_slots: ['pre_market'],
        triggers: [{ type: 'price_near_level', label: '接近分析師目標價', target_price: 1050, threshold_pct: 5 }]
      }
    ]
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-alerts" in result.stdout
    assert "提醒建議" in result.stdout
    assert "建議設定 2 個提醒" in result.stdout
    assert "財報日前提醒" in result.stdout
    assert "財報日 2026-07-18 前 14 天提醒" in result.stdout
    assert "接近分析師目標價" in result.stdout
    assert "套用提醒" in result.stdout
    assert "data-stock-snapshot-alert" in result.stdout


def test_stock_snapshot_panel_applies_alert_suggestion_to_watchlist():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
(async () => {
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '', querySelectorAll: () => [] };
let saved = null;
const panel = window.StockAgentStockSnapshotPanel.create({
  apiClient: { saveWatchlistItem: async item => { saved = item; return {}; } },
  ui: { escapeHtml: value => String(value ?? '') },
  notify: { success: () => {}, error: () => {} },
  elements: { root },
  onWatchlistUpdated: async () => {}
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  alert_suggestions: {
    status: 'available',
    label: '建議設定 1 個提醒',
    suggestions: [
      {
        key: 'event_earnings_date_2026-07-18',
        category: 'event',
        label: '財報日前提醒',
        pipeline: 'v4',
        schedule_slots: ['pre_market'],
        triggers: [{ type: 'event_upcoming', event_type: 'earnings_date', target_date: '2026-07-18', days_before: 14, label: '財報日' }]
      }
    ]
  }
});
await panel.applyAlertSuggestion(0);
process.stdout.write(JSON.stringify(saved));
})().catch(err => { console.error(err); process.exit(1); });
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    saved = json.loads(result.stdout)
    assert saved == {
        "ticker": "2330.TW",
        "pipeline": "v4",
        "enabled": True,
        "schedule_slots": ["pre_market"],
        "triggers": [
            {
                "type": "event_upcoming",
                "event_type": "earnings_date",
                "target_date": "2026-07-18",
                "days_before": 14,
                "label": "財報日",
            }
        ],
        "trigger_source": "stock_snapshot_suggestion",
    }


def test_stock_snapshot_panel_renders_financial_health_summary():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  financial_health: {
    revenue_ttm: { label: 'NT$25,000.00億' },
    revenue_growth: { label: '18.4%' },
    gross_margin: { label: '56.0%' },
    profit_margin: { label: '38.0%' },
    free_cash_flow: { label: 'NT$8,500.00億' },
    balance_sheet: { cash_label: 'NT$19,000.00億', debt_label: 'NT$9,000.00億', debt_to_equity_label: '28.0%' },
    highlights: ['營收成長', 'FCF 為正', '現金高於負債']
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-fundamentals" in result.stdout
    assert "基本面" in result.stdout
    assert "TTM 營收" in result.stdout
    assert "NT$25,000.00億" in result.stdout
    assert "營收成長" in result.stdout
    assert "自由現金流" in result.stdout
    assert "現金高於負債" in result.stdout


def test_stock_snapshot_panel_renders_financial_trends_table():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  financial_trends: {
    status: 'available',
    label: '營收與獲利成長',
    period_type: 'annual',
    signals: ['營收 YoY +28.0%', '淨利 YoY +22.2%', 'FCF YoY +5.9%'],
    rows: [
      { period: '2024', revenue: 2000, revenue_yoy_pct: 11.1, net_income: 720, net_income_yoy_pct: 10.8, free_cash_flow: 550, free_cash_flow_yoy_pct: 22.2, gross_margin_pct: 53, operating_margin_pct: 42 },
      { period: '2025', revenue: 2500, revenue_yoy_pct: 25.0, net_income: 900, net_income_yoy_pct: 25.0, free_cash_flow: 850, free_cash_flow_yoy_pct: 54.5, gross_margin_pct: 56, operating_margin_pct: 45 },
      { period: '2026', revenue: 3200, revenue_yoy_pct: 28.0, net_income: 1100, net_income_yoy_pct: 22.2, free_cash_flow: 900, free_cash_flow_yoy_pct: 5.9, gross_margin_pct: 57, operating_margin_pct: 46 }
    ]
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-financial-trends" in result.stdout
    assert "財報趨勢" in result.stdout
    assert "營收與獲利成長" in result.stdout
    assert "營收 YoY +28.0%" in result.stdout
    assert "2026" in result.stdout
    assert "3,200B" in result.stdout
    assert "+28.0%" in result.stdout
    assert "毛利率 57.0%" in result.stdout
    assert "營業 46.0%" in result.stdout


def test_stock_snapshot_panel_renders_peer_comparison_table():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  peer_comparison: {
    summary: {
      peer_count: 2,
      valuation_label: '接近同業',
      pe_vs_peer_median_pct: 2.3,
      gross_margin_spread_pct: 18
    },
    target: { ticker: '2330.TW', name: '台積電', gross_margin_pct: 56, roe_pct: 30, pe_ttm: 22.5, ps_ttm: 9.1 },
    peers: [
      { ticker: '2303.TW', name: '聯電', gross_margin_pct: 36, roe_pct: 17.5, pe_ttm: 14, ps_ttm: 3 },
      { ticker: 'INTC', name: 'Intel', gross_margin_pct: 38, roe_pct: 5, pe_ttm: 34, ps_ttm: 2.6 }
    ]
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-peers" in result.stdout
    assert "同業比較" in result.stdout
    assert "接近同業" in result.stdout
    assert "P/E vs 同業中位 +2.3%" in result.stdout
    assert "毛利差 +18.0pp" in result.stdout
    assert "台積電" in result.stdout
    assert "聯電" in result.stdout
    assert "Intel" in result.stdout
    assert "56.0%" in result.stdout


def test_stock_snapshot_panel_renders_ownership_flow_summary():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  ownership_flow: {
    status: 'available',
    label: '法人買超',
    institutional: {
      total_net_buy_thousand_shares: 2500,
      last_5_trading_days_net_buy_thousand_shares: 1200,
      categories: [
        { key: 'foreign', label: '外資', net_buy_thousand_shares: 1200 },
        { key: 'investment_trust', label: '投信', net_buy_thousand_shares: 800 },
        { key: 'dealer', label: '自營商', net_buy_thousand_shares: 500 }
      ]
    },
    margin: { margin_balance: 12000, short_balance: 350 },
    holders: { major_holders_gt_1000_lots_pct: 78.5, retail_holders_lt_50_lots_pct: 12.3 },
    signals: ['近30日法人合計買超 2,500張', '外資買超 1,200張', '千張以上大戶 78.5%']
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-ownership" in result.stdout
    assert "籌碼結構" in result.stdout
    assert "法人買超" in result.stdout
    assert "近30日法人合計買超 2,500張" in result.stdout
    assert "外資" in result.stdout
    assert "1,200張" in result.stdout
    assert "投信" in result.stdout
    assert "800張" in result.stdout
    assert "融資餘額" in result.stdout
    assert "12,000張" in result.stdout
    assert "千張以上大戶" in result.stdout
    assert "78.5%" in result.stdout


def test_stock_snapshot_panel_renders_valuation_range_reference():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const root = { hidden: true, innerHTML: '' };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { root }
});
panel.render({
  ticker: '2330.TW',
  identity: { company_name: '台積電' },
  quote: {},
  valuation: {},
  dividends: {},
  chip: {},
  data_quality: { status: 'fresh', score: 90 },
  valuation_range: {
    status: 'available',
    label: '合理區間',
    current_price: 950,
    mid_price: 1000,
    price_vs_mid_pct: -5,
    source: 'FinMind 5-year PER quantiles',
    bands: [
      { label: '15x', multiple: 15, price: 750 },
      { label: '20x', multiple: 20, price: 1000 },
      { label: '25x', multiple: 25, price: 1250 }
    ]
  }
});
process.stdout.write(root.innerHTML);
""".replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "stock-snapshot-valuation-range" in result.stdout
    assert "估值區間" in result.stdout
    assert "合理區間" in result.stdout
    assert "距中位 -5.0%" in result.stdout
    assert "15x" in result.stdout
    assert "750" in result.stdout
    assert "20x" in result.stdout
    assert "1,000" in result.stdout
    assert "25x" in result.stdout
    assert "FinMind 5-year PER quantiles" in result.stdout


def test_stock_snapshot_can_add_current_ticker_to_watchlist():
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stock_snapshot_js = (STATIC_DIR / "stock_snapshot_panel.js").read_text(encoding="utf-8")
    stock_snapshot_css = (STATIC_DIR / "styles" / "stock_snapshot.css").read_text(encoding="utf-8")

    assert "data-stock-snapshot-watchlist" in stock_snapshot_js
    assert "saveWatchlistItem" in stock_snapshot_js
    assert "加入追蹤" in stock_snapshot_js
    assert "onWatchlistUpdated" in stock_snapshot_js
    assert "stock-snapshot-actions-row" in stock_snapshot_js
    assert "loadWatchlistOnce" in app_js
    assert "onWatchlistUpdated: opsWorkspace.loadWatchlistOnce" in app_js
    assert ".stock-snapshot-actions-row" in stock_snapshot_css


def test_watchlist_is_first_class_tracking_tab_for_consumers():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    ops_workspace_js = (STATIC_DIR / "ops_workspace.js").read_text(encoding="utf-8")
    watchlist_panel_js = (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")
    watchlist_css = (STATIC_DIR / "styles" / "watchlist.css").read_text(encoding="utf-8")
    history_shell_css = (STATIC_DIR / "styles" / "history_shell.css").read_text(encoding="utf-8")

    assert 'id="home-tab-tracking"' in index_html
    assert 'data-home-tab="tracking"' in index_html
    assert 'id="home-panel-tracking"' in index_html
    assert 'id="watchlist-stock-snapshot-panel"' in index_html
    assert "追蹤" in index_html
    assert index_html.index('id="home-panel-tracking"') < index_html.index('id="watchlist-panel"')
    assert index_html.index('id="watchlist-panel"') < index_html.index('id="home-panel-ops"')
    assert "watchlistPanel.load" in ops_workspace_js
    assert "watchlistStockSnapshotPanel" in ops_workspace_js
    assert "onOpenSnapshot" in ops_workspace_js
    assert "onOpenReport: options.onOpenReport" in ops_workspace_js
    assert "loadWatchlistOnce" in ops_workspace_js
    assert "data-watchlist-snapshot" in watchlist_panel_js
    assert "data-watchlist-report" in watchlist_panel_js
    assert "最新報告" in watchlist_panel_js
    assert ".watchlist-ticker-button" in watchlist_css
    assert ".watchlist-report-button" in watchlist_css
    assert "tabName === 'tracking'" in app_js
    assert "opsWorkspace.loadWatchlistOnce" in app_js
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in history_shell_css


def test_watchlist_panel_opens_snapshot_and_latest_report_from_row():
    watchlist_panel_path = STATIC_DIR / "watchlist_panel.js"
    script = """
global.window = {
  clearTimeout: () => {},
  setTimeout: fn => { fn(); return 1; },
  StockAgentWatchlistTriggerForm: {
    renderItem: () => '',
    payload: () => [],
    reset: () => {}
  }
};
require(__WATCHLIST_PANEL_PATH__);
const listeners = {};
const listEl = {
  innerHTML: '',
  addEventListener: (event, handler) => { listeners[event] = handler; }
};
const summaryEl = { textContent: '' };
const opened = { snapshot: '', report: null };
const panel = window.StockAgentWatchlistPanel.create({
  ui: { pipelineModeLabel: value => `模式 ${value}` },
  escapeHtml: value => String(value ?? ''),
  apiClient: {
    fetchWatchlist: async () => ({
      schedules: { pre_market: { label: '盤前' } },
      items: [{
        ticker: '2330.TW',
        pipeline: 'v2',
        enabled: true,
        schedule_slots: ['pre_market'],
        decision_priority: 'high',
        latest_report: { filename: '2330_v2_report.html', pipeline_id: 'v2', date: '2026-07-05' }
      }]
    })
  },
  onOpenSnapshot: ticker => { opened.snapshot = ticker; },
  onOpenReport: (filename, ticker, pipeline) => { opened.report = { filename, ticker, pipeline }; },
  elements: { listEl, summaryEl, refreshBtn: { disabled: false, addEventListener: () => {} } }
});
panel.bindEvents();
panel.load().then(() => {
  listeners.click({
    target: {
      closest: selector => selector === '[data-watchlist-snapshot]' ? { dataset: { watchlistSnapshot: '2330.TW' } } : null
    }
  });
  listeners.click({
    target: {
      closest: selector => selector === '[data-watchlist-report]' ? { dataset: { watchlistReport: '2330_v2_report.html', watchlistReportTicker: '2330.TW', watchlistReportPipeline: 'v2' } } : null
    }
  });
  process.stdout.write(JSON.stringify({ html: listEl.innerHTML, opened }));
});
""".replace("__WATCHLIST_PANEL_PATH__", json.dumps(str(watchlist_panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    payload = json.loads(result.stdout)
    assert "data-watchlist-snapshot=\"2330.TW\"" in payload["html"]
    assert "data-watchlist-report=\"2330_v2_report.html\"" in payload["html"]
    assert "最新報告" in payload["html"]
    assert payload["opened"] == {
        "snapshot": "2330.TW",
        "report": {"filename": "2330_v2_report.html", "ticker": "2330.TW", "pipeline": "v2"},
    }


def test_portfolio_risk_panel_is_wired_into_tracking_tab():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    ops_workspace_js = (STATIC_DIR / "ops_workspace.js").read_text(encoding="utf-8")
    api_client_extensions_js = (STATIC_DIR / "api_client_extensions.js").read_text(encoding="utf-8")
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    portfolio_js_path = STATIC_DIR / "portfolio_risk_panel.js"
    portfolio_css_path = STATIC_DIR / "styles" / "portfolio_risk.css"

    assert portfolio_js_path.exists()
    assert portfolio_css_path.exists()
    portfolio_js = portfolio_js_path.read_text(encoding="utf-8")
    portfolio_css = portfolio_css_path.read_text(encoding="utf-8")

    assert 'id="portfolio-risk-panel"' in index_html
    assert 'id="portfolio-risk-csv"' in index_html
    assert 'id="portfolio-risk-run-btn"' in index_html
    assert 'id="portfolio-risk-result"' in index_html
    assert index_html.index('id="watchlist-panel"') < index_html.index('id="portfolio-risk-panel"') < index_html.index('id="home-panel-ops"')
    assert "/static/portfolio_risk_panel.js" in index_html
    assert "StockAgentPortfolioRiskPanel.create" in ops_workspace_js
    assert "portfolioRiskPanel.bindEvents" in ops_workspace_js
    assert "analyzePortfolioRisk" in api_client_extensions_js
    assert "portfolioRiskPanel" not in app_js
    assert "styles/portfolio_risk.css" in style_css
    assert "portfolio-risk-summary-grid" in portfolio_js
    assert "risk_flags" in portfolio_js
    assert ".portfolio-risk-panel" in portfolio_css
    assert ".portfolio-risk-summary-grid" in portfolio_css


def test_portfolio_risk_panel_renders_concentration_and_thesis_gaps():
    portfolio_panel_path = STATIC_DIR / "portfolio_risk_panel.js"
    script = """
global.window = {};
require(__PORTFOLIO_PANEL_PATH__);
const elements = {
  summaryEl: { textContent: '' },
  csvInput: { value: 'ticker,weight,sector,country\\n2330.TW,60,Semiconductor,TW' },
  runBtn: { disabled: false, querySelector: () => ({ textContent: '' }) },
  resultEl: { hidden: true, innerHTML: '' }
};
const payload = {
  total_positions: 2,
  risk_flags: ['single_position_over_40_pct', 'sector_over_60_pct'],
  concentration: {
    top_position: { ticker: '2330.TW', weight_pct: 60 },
    sector_weights: { Semiconductor: 85, Software: 15 },
    country_weights: { TW: 85, US: 15 }
  },
  thesis_health: { invalidated: ['2454.TW'], missing: ['AAPL'] }
};
const panel = window.StockAgentPortfolioRiskPanel.create({
  apiClient: { analyzePortfolioRisk: async () => payload },
  ui: { escapeHtml: value => String(value ?? '') },
  elements
});
panel.analyze().then(() => process.stdout.write(JSON.stringify({
  summary: elements.summaryEl.textContent,
  hidden: elements.resultEl.hidden,
  html: elements.resultEl.innerHTML
})));
""".replace("__PORTFOLIO_PANEL_PATH__", json.dumps(str(portfolio_panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["summary"] == "2 檔持股 · 2 個風險旗標"
    assert payload["hidden"] is False
    assert "2330.TW" in payload["html"]
    assert "60%" in payload["html"]
    assert "單一持股超過 40%" in payload["html"]
    assert "產業曝險超過 60%" in payload["html"]
    assert "2454.TW" in payload["html"]
    assert "AAPL" in payload["html"]


def test_home_tabs_present_five_even_desktop_choices():
    history_shell_css = (STATIC_DIR / "styles" / "history_shell.css").read_text(encoding="utf-8")
    responsive_css = (STATIC_DIR / "styles" / "responsive.css").read_text(encoding="utf-8")

    assert ".home-tabs" in history_shell_css
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in history_shell_css
    assert ".home-tab-button" in history_shell_css and "min-height: 44px;" in history_shell_css
    assert ".home-tabs {\n        grid-template-columns: 1fr;" in responsive_css


def test_pipeline_mode_options_explain_decision_intent():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert "長線研究 · 10 Agent" in index_html
    assert "部位決策 · 8 Agent" in index_html
    assert "逆勢風控 · 5 Agent" in index_html
    assert "事件波段 · 3 Agent" in index_html
    assert "三視角交叉檢查 · 23 模組" in index_html


def test_home_subtitle_describes_user_outcome_not_internal_agent_shape():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert "研究報告與決策追蹤工作台" in index_html
    assert "連續式股票分析 Agent" not in index_html


def test_pipeline_selection_updates_decision_intent_hint():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    ui_helpers_js = (STATIC_DIR / "ui_helpers.js").read_text(encoding="utf-8")
    forms_controls_css = (STATIC_DIR / "styles" / "forms_controls.css").read_text(encoding="utf-8")

    assert 'id="pipeline-mode-hint"' in index_html
    assert "pipelineModeHint" in app_js
    assert "updatePipelineModeHint" in app_js
    assert ".pipeline-mode-hint" in forms_controls_css
    assert "intent:" in ui_helpers_js
    assert "適合判斷是否納入長線研究清單" in ui_helpers_js
    assert "適合決定進場、續抱或減碼" in ui_helpers_js
    assert "適合檢查泡沫、避險與做空風險" in ui_helpers_js
    assert "適合短線事件與波段交易計畫" in ui_helpers_js


def test_pipeline_mode_frontend_labels_share_single_metadata_source():
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    ui_helpers_js = (STATIC_DIR / "ui_helpers.js").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    market_screener_js = (STATIC_DIR / "market_screener_panel.js").read_text(encoding="utf-8")
    watchlist_panel_js = (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")

    assert "function pipelineChoices" in ui_helpers_js
    assert "function pipelineCtaLabel" in ui_helpers_js
    assert "ui.pipelineCtaLabel(getSelectedPipeline())" in app_js
    assert "selectedPipeline === 'v4'" not in app_js
    assert "this.ui.pipelineChoices" in market_screener_js
    assert "const PIPELINE_OPTIONS = [" not in market_screener_js
    assert "window.StockAgentUi?.pipelineModeLabel" in history_panel_js
    assert "const labels = {" not in history_panel_js
    assert "ui.pipelineModeLabel" in watchlist_panel_js
    assert ".toUpperCase())" not in watchlist_panel_js


def test_primary_cta_has_readable_contrast_on_cyan_action_background():
    forms_controls_css = (STATIC_DIR / "styles" / "forms_controls.css").read_text(encoding="utf-8")

    assert ".glow-button" in forms_controls_css
    assert "background: var(--accent);" in forms_controls_css
    assert "color: #03111f;" in forms_controls_css
    assert _contrast_ratio("#03111f", "#00d4ff") >= 4.5


def test_history_version_toggle_checkbox_is_visually_legible():
    history_list_css = (STATIC_DIR / "styles" / "history_list.css").read_text(encoding="utf-8")

    assert ".history-version-toggle input" in history_list_css
    assert "width: 22px;" in history_list_css
    assert "height: 22px;" in history_list_css


def test_decision_tracking_mobile_cards_prioritize_readable_single_column_data():
    decision_tracking_css = (STATIC_DIR / "styles" / "decision_tracking.css").read_text(encoding="utf-8")

    assert ".tracking-target-chip { min-height: 40px;" in decision_tracking_css
    assert ".tracking-target-period { grid-area: period; font-size: 0.68rem;" in decision_tracking_css
    assert ".tracking-target-value { grid-area: value; color: inherit; font-size: 0.78rem;" in decision_tracking_css
    assert ".tracking-target-label { grid-area: label; font-size: 0.68rem;" in decision_tracking_css
    assert ".tracking-report-card, .decision-tracking-table.is-compact .tracking-report-card { grid-template-columns: 1fr;" in decision_tracking_css


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


def test_mode_d_tracking_card_uses_trade_setup_instead_of_target_comparison():
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
panel.renderTrackingGroups([{
  ticker: '1623.TW',
  company_name: '大東電',
  reports: [{
    filename: '1623_v4_report_job_fff62ba7fd52.html',
    ticker: '1623.TW',
    company_name: '大東電',
    pipeline_id: 'v4',
    date: '2026-07-01 09:13',
    preview: {
      kind: 'swing_trade',
      primary: { label: '交易方向', value: '中性 Neutral', tone: 'is-neutral' },
      list_metrics: [{ label: '短線目標', value: '213' }, { label: '停損', value: '跌破 205' }]
    },
    recommendation: { recommendation: 'N/A' },
    decision_tracking: {
      status: 'tracked',
      recommendation: 'N/A',
      latest_price: 213,
      return_pct: 0,
      tracking_summary_status: '尚無法比較目標',
      target_comparisons: {
        target_3m: { status: 'unavailable', target: 0, label: '無法比較' },
        target_6m: { status: 'unavailable', target: 0, label: '無法比較' },
        target_12m: { status: 'unavailable', target: 0, label: '無法比較' }
      }
    }
  }]
}]);
process.stdout.write(table.innerHTML);
""".replace("__HISTORY_PANEL_PATH__", json.dumps(str(history_panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "大東電" in result.stdout
    assert "中性 Neutral" in result.stdout
    assert "短線目標" in result.stdout
    assert "跌破 205" in result.stdout
    assert "無法比較" not in result.stdout
    assert "尚無法比較目標" not in result.stdout


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


def test_report_preview_panel_uses_decision_boundary_for_legacy_preview():
    report_preview_path = STATIC_DIR / "report_preview_panel.js"
    script = """
global.window = {};
require(__REPORT_PREVIEW_PATH__);
const el = () => ({ hidden: false, textContent: '', innerHTML: '', className: '', classList: { toggle() {} }, querySelector: () => null });
const button = () => {
  const span = { textContent: '' };
  return { hidden: false, disabled: false, querySelector: () => span, span };
};
const rerunFinalBtn = button();
const rerunFullBtn = button();
const elements = {
  workspace: el(),
  root: el(),
  mode: el(),
  title: el(),
  decisionRow: el(),
  targets: el(),
  summary: el(),
  staleNotice: el(),
  rerunFinalBtn,
  rerunFullBtn
};
const panel = window.StockAgentReportPreviewPanel.create({
  elements,
  escapeHtml: value => String(value ?? '').replace(/[&<>]/g, ''),
  renderPipelineModeBadge: () => '',
  renderDataTrustBadge: () => '',
  pipelineMeta: () => ({ shortLabel: '價值投資派' }),
  normalizeRecommendation: value => String(value ?? ''),
  recommendationTone: () => 'is-buy'
});
panel.show({
  ticker: '2449',
  pipeline_id: 'v1',
  date: '2026-06-27',
  recommendation: { recommendation: '買入', current_price: 'NT$100', confidence: '8/10' }
});
process.stdout.write(JSON.stringify({
  title: elements.title.textContent,
  decision: elements.decisionRow.innerHTML,
  summary: elements.summary.textContent,
  rerunFinal: rerunFinalBtn.span.textContent,
  rerunFull: rerunFullBtn.span.textContent
}));
""".replace("__REPORT_PREVIEW_PATH__", json.dumps(str(report_preview_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["title"] == "2449 報告建議"
    assert "報告建議" in payload["decision"]
    assert "投資建議" not in payload["title"]
    assert "仍需自行判斷" in payload["summary"]
    assert payload["rerunFinal"] == "重跑價值投資派報告結論"
    assert payload["rerunFull"] == "完整重跑價值投資派"


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
    assert 'id="operator-shift-summary"' in index_html
    assert "data-operator-shift-summary" in index_html
    assert 'role="status"' in index_html
    assert "今日待處理" in index_html
    assert "操作者值班摘要" in index_html
    assert "operatorActionItems" in operator_summary_js
    assert "setShift" in operator_summary_js
    assert "querySelectorAll('[data-operator-shift-summary]')" in operator_summary_js
    assert "下一步：" in operator_summary_js
    assert "toLocaleTimeString" in operator_summary_js
    assert "fetchWatchlist" in operator_summary_js
    assert "runWatchlist" in operator_summary_js
    assert "data-operator-action" in operator_summary_js
    assert "查看報告" in operator_summary_js
    assert "建立/更新報告" in operator_summary_js
    assert "watchlistActionDetail" in operator_summary_js
    assert "尚未建立報告" in operator_summary_js
    assert "資料更新需重跑" in operator_summary_js
    assert "待建立/更新報告" in operator_summary_js
    assert "rerun_reports" in operator_summary_js
    assert "rerun-report" in operator_summary_js
    assert "rerun-all-reports" in operator_summary_js
    assert "全部重跑" in operator_summary_js
    assert "/rerun?scope=full_report" in operator_summary_js
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
    assert ".operator-shift-summary" in operator_css
    assert "grid-column: 1 / -1;" in operator_css
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
    assert "股價大漲跌/成交量暴增" in market_screener_js
    assert "技術/量能異常" not in market_screener_js
    assert "scan_success" in market_screener_js
    assert "result.message" in market_screener_js
    assert "providers" in market_screener_js
    assert "資料源" in market_screener_js
    assert "company_name" in market_screener_js
    assert "data-screener-select" in market_screener_js
    assert "runWatchlist" in market_screener_js
    assert "模式 A" in market_screener_js and "模式 D" in market_screener_js
    assert "class MarketScreenerPanel" in market_screener_js
    assert "data-screener-sort" in market_screener_js
    assert "formatSignedMetric" in market_screener_js
    assert "setLoading" in market_screener_js
    assert "查無資料，請放寬條件" in market_screener_js
    assert "market-screener-range" in market_screener_js
    assert "market-screener-filter-select" in market_screener_js
    assert "fundamental_revenue_growth_yoy_min" in market_screener_js
    assert "technical_rsi_min" in market_screener_js
    assert "technical_macd_histogram_min" in market_screener_js
    assert "institutional_total_net_buy_min" in market_screener_js
    assert "market-screener-number" in market_screener_js
    assert "market-screener-pager" in market_screener_js
    assert "營收 YoY 下限" in market_screener_js
    assert "MACD 柱下限" in market_screener_js
    assert "法人總買超" in market_screener_js
    assert "每頁" in market_screener_js
    assert ".market-screener-grid" in market_screener_css
    assert ".market-screener-table-shell" in market_screener_css
    assert ".market-screener-sort-button" in market_screener_css
    assert ".metric-positive" in market_screener_css
    assert ".metric-negative" in market_screener_css
    assert ".market-screener-empty" in market_screener_css
    assert "overflow-x: auto" in market_screener_css
    assert ".market-screener-mode-picker" in market_screener_css
    assert ".market-screener-mode-option:has(input:checked)" in market_screener_css
    assert ".market-screener-mode-option input" in market_screener_css
    assert ".market-screener-number" in market_screener_css
    assert ".market-screener-pager" in market_screener_css
    assert "accent-color" in market_screener_css


def test_market_screener_panel_builds_commercial_filter_params():
    market_screener_path = STATIC_DIR / "market_screener_panel.js"
    script = """
global.window = {};
require(__MARKET_SCREENER_PANEL_PATH__);
const panel = window.StockAgentMarketScreenerPanel.create({
  apiClient: { fetchMarketScreener: async () => ({ items: [] }) },
  ui: { escapeHtml: value => String(value ?? '') },
  elements: {}
});
panel.sort = { key: 'revenue_growth_yoy_pct', direction: 'desc' };
panel.offset = 25;
Object.assign(panel.filters, {
  category: 'technical_heat',
  minScore: 70,
  revenueGrowthMin: 12,
  revenueGrowthMax: 80,
  rsiMin: 45,
  rsiMax: 70,
  macdMin: 0.5,
  macdHistogramMin: 0.2,
  totalNetBuyMin: 1000000,
  foreignNetBuyMin: 500000,
  investmentTrustNetBuyMin: 200000,
  dealerNetBuyMin: 100000,
  pageSize: 25
});
process.stdout.write(JSON.stringify(panel.params()));
""".replace("__MARKET_SCREENER_PANEL_PATH__", json.dumps(str(market_screener_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    params = json.loads(result.stdout)

    assert params == {
        "limit": 25,
        "offset": 25,
        "sort_by": "revenue_growth_yoy_pct",
        "sort_direction": "desc",
        "category": "technical_heat",
        "min_score": 70,
        "fundamental_revenue_growth_yoy_min": 12,
        "fundamental_revenue_growth_yoy_max": 80,
        "technical_rsi_min": 45,
        "technical_rsi_max": 70,
        "technical_macd_min": 0.5,
        "technical_macd_histogram_min": 0.2,
        "institutional_total_net_buy_min": 1000000,
        "institutional_foreign_net_buy_min": 500000,
        "institutional_investment_trust_net_buy_min": 200000,
        "institutional_dealer_net_buy_min": 100000,
    }


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
    assert "LLM/API 本機觀測：" in api_quota_js
    assert "LLM/API 健康：" not in api_quota_js
    assert "LLM 本機觀測正常" in operator_summary_js
    assert "LLM 健康正常" not in operator_summary_js
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
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    api_client_extensions_js = (STATIC_DIR / "api_client_extensions.js").read_text(encoding="utf-8")
    history_workspace_js = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    decision_tracking_css = (STATIC_DIR / "styles" / "decision_tracking.css").read_text(encoding="utf-8")

    assert 'id="decision-tracking-refresh"' in index_html
    assert 'id="decision-tracking-summary"' in index_html
    assert 'id="decision-tracking-density"' in index_html
    assert 'id="decision-tracking-stock-snapshot-panel"' in index_html
    assert "decisionTrackingStockSnapshotPanel" in app_js
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
    assert "tracking-stock-snapshot-button" in history_panel_js
    assert "data-tracking-snapshot" in history_panel_js
    assert "onOpenSnapshot" in history_panel_js
    assert "trackingSnapshotPanel" in history_workspace_js
    assert "StockAgentStockSnapshotPanel.create" in history_workspace_js
    assert "tracking-report-card" in history_panel_js
    assert "tracking-group-reports" in history_panel_js
    assert "高密度三模式比較" in history_panel_js
    assert "/static/history_workspace.js?v=20260705-tracking-snapshot" in index_html
    assert "mergeTrackingReports" in history_workspace_js
    assert "trackingPayload" in history_workspace_js
    assert "item.latest_reports" in history_workspace_js
    assert "window.StockAgentUi?.pipelineModeLabel" in history_panel_js
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
    assert ".tracking-stock-snapshot-button" in decision_tracking_css
    assert ".decision-tracking-stock-snapshot-panel" in decision_tracking_css
    assert ".is-compact" in decision_tracking_css
    assert "white-space: normal" in decision_tracking_css


def test_decision_tracking_table_ticker_opens_stock_snapshot():
    history_panel_path = STATIC_DIR / "history_panel.js"
    script = """
global.window = { StockAgentUi: { normalizeRecommendation: value => String(value || '') } };
require(__HISTORY_PANEL_PATH__);
const listEl = { addEventListener: () => {}, querySelectorAll: () => [] };
const trackingTableEl = {
  hidden: true,
  innerHTML: '',
  classList: { toggle: () => {} },
  listeners: {},
  addEventListener(event, handler) { this.listeners[event] = handler; },
  querySelectorAll: () => []
};
let openedTicker = '';
const panel = window.StockAgentHistoryPanel.create({
  listEl,
  trackingTableEl,
  escapeHtml: value => String(value ?? ''),
  recommendationTone: () => 'is-neutral',
  normalizeRecommendation: value => String(value || ''),
  renderPipelineModeBadge: () => '',
  renderDataTrustBadge: () => '',
  renderDataTrustReason: () => ''
});
panel.bindEvents({
  onDelete: () => {},
  onSelect: () => {},
  onToggleTracking: () => {},
  onOpenSnapshot: ticker => { openedTicker = ticker; }
});
panel.renderTrackingGroups([{
  ticker: '2330.TW',
  company_name: '台積電',
  reports: [{
    filename: '2330_v2.html',
    ticker: '2330.TW',
    pipeline_id: 'v2',
    date: '2026-07-05',
    decision_tracking: { status: 'tracked', latest_price: 950, return_pct: 2.5, target_comparisons: {}, recommendation: '買入' },
    recommendation: { recommendation: '買入' }
  }]
}]);
trackingTableEl.listeners.click({
  target: { closest: selector => selector === '[data-tracking-snapshot]' ? { dataset: { trackingSnapshot: '2330.TW' } } : null }
});
process.stdout.write(JSON.stringify({ html: trackingTableEl.innerHTML, openedTicker }));
""".replace("__HISTORY_PANEL_PATH__", json.dumps(str(history_panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert 'class="tracking-stock-snapshot-button"' in payload["html"]
    assert 'data-tracking-snapshot="2330.TW"' in payload["html"]
    assert payload["openedTicker"] == "2330.TW"


def test_decision_tracking_dense_layout_uses_workspace_efficiently():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    base_css = (STATIC_DIR / "styles" / "base.css").read_text(encoding="utf-8")
    history_list_css = (STATIC_DIR / "styles" / "history_list.css").read_text(encoding="utf-8")
    decision_tracking_css = (STATIC_DIR / "styles" / "decision_tracking.css").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")

    assert "style.css?v=20260707-operator-human-factors" in index_html
    assert "/static/history_panel.js?v=20260705-tracking-snapshot" in index_html
    assert "/static/report_preview_panel.js?v=20260627-mode-aware-preview" in index_html
    assert "preview_panel.css?v=20260627-mode-aware-preview" in style_css
    assert "decision_tracking.css?v=20260705-tracking-snapshot" in style_css
    assert "history_shell.css?v=20260707-operator-human-factors" in style_css
    assert "responsive.css?v=20260705-commercial-launchpad2" in style_css
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


def test_home_commercial_tab_is_a_restart_safe_product_launchpad():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    history_shell_css = (STATIC_DIR / "styles" / "history_shell.css").read_text(encoding="utf-8")
    responsive_css = (STATIC_DIR / "styles" / "responsive.css").read_text(encoding="utf-8")

    assert "style.css?v=20260707-operator-human-factors" in index_html
    assert "history_shell.css?v=20260707-operator-human-factors" in style_css
    assert "responsive.css?v=20260705-commercial-launchpad2" in style_css

    assert 'id="home-panel-commercial"' in index_html
    assert 'class="commercial-entry-launchpad"' in index_html
    assert 'id="commercial-operator-shift-summary"' in index_html
    assert 'class="commercial-operator-brief is-loading"' in index_html
    assert 'class="commercial-entry-command-row"' in index_html
    assert "商業版投資工作區" in index_html
    assert "操作者值班摘要" in index_html
    assert "重啟後從 8080 首頁直接進入新版前端" in index_html
    assert "研究工作台" in index_html
    assert "單股研究" in index_html
    assert "組合健檢" in index_html
    assert "決策佇列" in index_html
    assert "快照研究" in index_html
    assert "曝險透視" in index_html

    for href in (
        "/static/commercial/research-workbench.html",
        "/static/commercial/stock-detail.html",
        "/static/commercial/portfolio-dashboard.html",
    ):
        assert href in index_html

    for marker in (
        'data-commercial-entry="workbench"',
        'data-commercial-entry="stock"',
        'data-commercial-entry="portfolio"',
        'class="commercial-entry-card-metrics"',
        'class="commercial-entry-card-actions"',
        "追蹤表工作台",
        "單股研究頁",
        "組合健檢頁",
        "風險旗標",
        "開啟快照",
        "財務資料",
        "建立再平衡單",
    ):
        assert marker in index_html

    for legacy_label in (
        "Commercial OS",
        "Watchlist Queue",
        "Stock Snapshot",
        "Portfolio X-Ray",
        "Open Snapshot",
        "AI Report",
        "Rebalance Ticket",
        "Client Pack",
    ):
        assert legacy_label not in index_html

    for selector in (
        ".commercial-entry-launchpad",
        ".commercial-operator-brief",
        ".commercial-entry-command-row",
        ".commercial-entry-status-grid",
        ".commercial-entry-card-metrics",
        ".commercial-entry-card-actions",
        ".commercial-entry-card-action",
    ):
        assert selector in history_shell_css
    assert "grid-template-columns: minmax(280px, 0.62fr) minmax(0, 1fr);" in history_shell_css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in history_shell_css
    assert ".commercial-entry-launchpad" in responsive_css
    assert ".commercial-entry-command-row" in responsive_css
    assert ".commercial-entry-status-grid" in responsive_css


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
