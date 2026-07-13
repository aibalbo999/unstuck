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
    app_panels_js = (STATIC_DIR / "app_panels.js").read_text(encoding="utf-8")
    api_client_js = (STATIC_DIR / "api_client.js").read_text(encoding="utf-8")
    history_filters_js = (STATIC_DIR / "history_filters.js").read_text(encoding="utf-8")
    history_workspace_js = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")

    assert 'id="history-data-trust-filter"' in index_html
    assert 'id="history-include-versions"' in index_html
    assert '<span>報告建議</span>' in index_html
    assert '<option value="all">全部報告建議</option>' in index_html
    assert '<span>投資建議</span>' not in index_html
    assert '<option value="all">全部建議</option>' not in index_html
    assert "historyDataTrustFilter" in app_panels_js
    assert "historyIncludeVersions" in app_panels_js
    assert "includeVersionsEl" in history_filters_js
    assert "includeVersions" in history_workspace_js
    assert "params.set('data_trust', dataTrust)" in api_client_js
    assert "params.set('include_versions', '1')" in api_client_js


def test_provider_sla_and_manual_refresh_controls_are_wired():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_elements_path = STATIC_DIR / "app_elements.js"
    assert app_elements_path.exists()
    app_elements_js = app_elements_path.read_text(encoding="utf-8")
    decision_tracking_helpers_path = STATIC_DIR / "decision_tracking_helpers.js"
    assert decision_tracking_helpers_path.exists()
    decision_tracking_helpers_js = decision_tracking_helpers_path.read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    app_pipeline_controls_path = STATIC_DIR / "app_pipeline_controls.js"
    assert app_pipeline_controls_path.exists()
    app_pipeline_controls_js = app_pipeline_controls_path.read_text(encoding="utf-8")
    app_panels_path = STATIC_DIR / "app_panels.js"
    assert app_panels_path.exists()
    app_panels_js = app_panels_path.read_text(encoding="utf-8")
    provider_sla_helpers_path = STATIC_DIR / "provider_sla_helpers.js"
    assert provider_sla_helpers_path.exists()
    provider_sla_helpers_js = provider_sla_helpers_path.read_text(encoding="utf-8")
    provider_sla_js = (STATIC_DIR / "provider_sla_panel.js").read_text(encoding="utf-8")
    active_jobs_js = (STATIC_DIR / "active_jobs_panel.js").read_text(encoding="utf-8")
    report_quality_gate_policy_path = STATIC_DIR / "report_quality_gate_policy.js"
    assert report_quality_gate_policy_path.exists()
    report_quality_gate_policy_js = report_quality_gate_policy_path.read_text(encoding="utf-8")
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    assert report_quality_policy_path.exists()
    report_quality_policy_js = report_quality_policy_path.read_text(encoding="utf-8")
    report_reading_boundary_path = STATIC_DIR / "report_reading_boundary_policy.js"
    assert report_reading_boundary_path.exists()
    report_reading_boundary_js = report_reading_boundary_path.read_text(encoding="utf-8")
    operator_summary_quality_helpers_path = STATIC_DIR / "operator_summary_quality_helpers.js"
    assert operator_summary_quality_helpers_path.exists()
    operator_summary_quality_helpers_js = operator_summary_quality_helpers_path.read_text(encoding="utf-8")
    operator_summary_helpers_path = STATIC_DIR / "operator_summary_helpers.js"
    assert operator_summary_helpers_path.exists()
    operator_summary_helpers_js = operator_summary_helpers_path.read_text(encoding="utf-8")
    operator_summary_js = (STATIC_DIR / "operator_summary_panel.js").read_text(encoding="utf-8")
    api_quota_panel_js = (STATIC_DIR / "api_quota_panel.js").read_text(encoding="utf-8")
    performance_panel_js = (STATIC_DIR / "performance_panel.js").read_text(encoding="utf-8")
    api_client_extensions_js = (STATIC_DIR / "api_client_extensions.js").read_text(encoding="utf-8")
    ops_workspace_js = (STATIC_DIR / "ops_workspace.js").read_text(encoding="utf-8")
    ops_workspace_elements_path = STATIC_DIR / "ops_workspace_elements.js"
    assert ops_workspace_elements_path.exists()
    ops_workspace_elements_js = ops_workspace_elements_path.read_text(encoding="utf-8")
    ops_workspace_loaders_path = STATIC_DIR / "ops_workspace_loaders.js"
    assert ops_workspace_loaders_path.exists()
    ops_workspace_loaders_js = ops_workspace_loaders_path.read_text(encoding="utf-8")
    ops_workspace_panels_path = STATIC_DIR / "ops_workspace_panels.js"
    assert ops_workspace_panels_path.exists()
    ops_workspace_panels_js = ops_workspace_panels_path.read_text(encoding="utf-8")
    maintenance_js = (STATIC_DIR / "maintenance_panel.js").read_text(encoding="utf-8")
    maintenance_helpers_path = STATIC_DIR / "maintenance_panel_helpers.js"
    assert maintenance_helpers_path.exists()
    maintenance_helpers_js = maintenance_helpers_path.read_text(encoding="utf-8")
    home_tabs_js = (STATIC_DIR / "home_tabs.js").read_text(encoding="utf-8")
    report_rerun_js = (STATIC_DIR / "report_rerun.js").read_text(encoding="utf-8")
    report_rerun_stream_path = STATIC_DIR / "report_rerun_stream.js"
    assert report_rerun_stream_path.exists()
    report_rerun_stream_js = report_rerun_stream_path.read_text(encoding="utf-8")
    analysis_stream_events_path = STATIC_DIR / "analysis_stream_events.js"
    assert analysis_stream_events_path.exists()
    analysis_stream_events_js = analysis_stream_events_path.read_text(encoding="utf-8")
    analysis_stream_js = (STATIC_DIR / "analysis_stream.js").read_text(encoding="utf-8")
    history_workspace_js = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")
    history_workspace_panels_path = STATIC_DIR / "history_workspace_panels.js"
    assert history_workspace_panels_path.exists()
    history_workspace_panels_js = history_workspace_panels_path.read_text(encoding="utf-8")
    history_workspace_actions_path = STATIC_DIR / "history_workspace_actions.js"
    assert history_workspace_actions_path.exists()
    history_workspace_actions_js = history_workspace_actions_path.read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    assert history_panel_quality_helpers_path.exists()
    history_panel_quality_helpers_js = history_panel_quality_helpers_path.read_text(encoding="utf-8")
    history_panel_helpers_js = (STATIC_DIR / "history_panel_helpers.js").read_text(encoding="utf-8")
    history_panel_renderers_path = STATIC_DIR / "history_panel_renderers.js"
    assert history_panel_renderers_path.exists()
    history_panel_renderers_js = history_panel_renderers_path.read_text(encoding="utf-8")
    report_preview_helpers_path = STATIC_DIR / "report_preview_helpers.js"
    assert report_preview_helpers_path.exists()
    report_preview_helpers_js = report_preview_helpers_path.read_text(encoding="utf-8")
    report_preview_tracking_helpers_path = STATIC_DIR / "report_preview_tracking_helpers.js"
    assert report_preview_tracking_helpers_path.exists()
    report_preview_tracking_helpers_js = report_preview_tracking_helpers_path.read_text(encoding="utf-8")
    report_preview_rerun_helpers_path = STATIC_DIR / "report_preview_rerun_helpers.js"
    assert report_preview_rerun_helpers_path.exists()
    report_preview_rerun_helpers_js = report_preview_rerun_helpers_path.read_text(encoding="utf-8")
    report_preview_js = (STATIC_DIR / "report_preview_panel.js").read_text(encoding="utf-8")
    temporal_memory_js = (STATIC_DIR / "temporal_memory_panel.js").read_text(encoding="utf-8")
    report_compare_js = (STATIC_DIR / "report_compare_panel.js").read_text(encoding="utf-8")
    report_compare_helpers_path = STATIC_DIR / "report_compare_helpers.js"
    assert report_compare_helpers_path.exists()
    report_compare_helpers_js = report_compare_helpers_path.read_text(encoding="utf-8")
    report_compare_renderers_path = STATIC_DIR / "report_compare_renderers.js"
    assert report_compare_renderers_path.exists()
    report_compare_renderers_js = report_compare_renderers_path.read_text(encoding="utf-8")
    decision_tracking_js = (STATIC_DIR / "decision_tracking_panel.js").read_text(encoding="utf-8")
    report_navigation_targets_path = STATIC_DIR / "report_navigation_targets.js"
    assert report_navigation_targets_path.exists()
    report_navigation_targets_js = report_navigation_targets_path.read_text(encoding="utf-8")
    report_navigation_js = (STATIC_DIR / "report_navigation.js").read_text(encoding="utf-8")
    api_request_path = STATIC_DIR / "api_request.js"
    assert api_request_path.exists()
    api_request_js = api_request_path.read_text(encoding="utf-8")
    api_client_js = (STATIC_DIR / "api_client.js").read_text(encoding="utf-8")
    ui_data_trust_path = STATIC_DIR / "ui_data_trust.js"
    assert ui_data_trust_path.exists()
    ui_data_trust_js = ui_data_trust_path.read_text(encoding="utf-8")
    pipeline_mode_fallback_js = (STATIC_DIR / "pipeline_mode_fallback.js").read_text(encoding="utf-8")
    ui_helpers_js = (STATIC_DIR / "ui_helpers.js").read_text(encoding="utf-8")
    notification_center_js = (STATIC_DIR / "notification_center.js").read_text(encoding="utf-8")
    maintenance_notification_js = (STATIC_DIR / "maintenance_notification_delivery.js").read_text(encoding="utf-8")
    operator_dashboard_actions_js = (STATIC_DIR / "operator_dashboard_actions.js").read_text(encoding="utf-8")
    watchlist_helpers_path = STATIC_DIR / "watchlist_panel_helpers.js"
    assert watchlist_helpers_path.exists()
    watchlist_helpers_js = watchlist_helpers_path.read_text(encoding="utf-8")
    watchlist_actions_path = STATIC_DIR / "watchlist_panel_actions.js"
    assert watchlist_actions_path.exists()
    watchlist_actions_js = watchlist_actions_path.read_text(encoding="utf-8")
    watchlist_panel_js = (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")
    market_screener_helpers_path = STATIC_DIR / "market_screener_helpers.js"
    assert market_screener_helpers_path.exists()
    market_screener_helpers_js = market_screener_helpers_path.read_text(encoding="utf-8")
    history_list_css = (STATIC_DIR / "styles" / "history_list.css").read_text(encoding="utf-8")
    history_list_controls_css_path = STATIC_DIR / "styles" / "history_list_controls.css"
    assert history_list_controls_css_path.exists()
    history_list_controls_css = history_list_controls_css_path.read_text(encoding="utf-8")
    preview_panel_css = (STATIC_DIR / "styles" / "preview_panel.css").read_text(encoding="utf-8")
    preview_panel_quality_css_path = STATIC_DIR / "styles" / "preview_panel_quality.css"
    assert preview_panel_quality_css_path.exists()
    preview_panel_quality_css = preview_panel_quality_css_path.read_text(encoding="utf-8")
    preview_panel_actions_css_path = STATIC_DIR / "styles" / "preview_panel_actions.css"
    assert preview_panel_actions_css_path.exists()
    preview_panel_actions_css = preview_panel_actions_css_path.read_text(encoding="utf-8")
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
    assert 'id="preview-reading-notice"' in index_html
    assert "previewReadingNotice" in app_elements_js
    assert "readingNotice: elements.previewReadingNotice" in history_workspace_panels_js
    assert 'id="preview-tracking"' in index_html
    assert 'id="preview-temporal-memory"' in index_html
    assert 'id="preview-tracking-return"' in index_html
    assert 'id="history-tracking-table"' in index_html
    assert "/static/provider_sla_helpers.js" in index_html
    assert "/static/provider_sla_panel.js" in index_html
    assert index_html.index("/static/provider_sla_helpers.js") < index_html.index("/static/provider_sla_panel.js")
    assert "/static/api_quota_panel.js" in index_html
    assert "/static/active_jobs_panel.js" in index_html
    assert "/static/operator_dashboard_actions.js" in index_html
    assert "/static/report_quality_gate_policy.js" in index_html
    assert "/static/report_reading_boundary_policy.js" in index_html
    assert "/static/report_quality_policy.js" in index_html
    assert "/static/operator_summary_quality_helpers.js" in index_html
    assert "/static/operator_summary_helpers.js" in index_html
    assert "/static/operator_summary_panel.js" in index_html
    assert index_html.index("/static/operator_dashboard_actions.js") < index_html.index("/static/report_quality_gate_policy.js")
    assert index_html.index("/static/report_quality_gate_policy.js") < index_html.index("/static/report_reading_boundary_policy.js")
    assert index_html.index("/static/report_reading_boundary_policy.js") < index_html.index("/static/report_quality_policy.js")
    assert index_html.index("/static/report_quality_gate_policy.js") < index_html.index("/static/report_quality_policy.js")
    assert index_html.index("/static/report_quality_policy.js") < index_html.index("/static/ui_data_trust.js")
    assert index_html.index("/static/report_quality_policy.js") < index_html.index("/static/operator_summary_quality_helpers.js")
    assert index_html.index("/static/operator_dashboard_actions.js") < index_html.index("/static/operator_summary_quality_helpers.js")
    assert index_html.index("/static/operator_summary_quality_helpers.js") < index_html.index("/static/operator_summary_helpers.js")
    assert index_html.index("/static/operator_summary_helpers.js") < index_html.index("/static/operator_summary_panel.js")
    assert index_html.index("/static/operator_dashboard_actions.js") < index_html.index("/static/operator_summary_panel.js")
    assert "/static/watchlist_panel_helpers.js" in index_html
    assert "/static/watchlist_panel_actions.js" in index_html
    assert "/static/watchlist_panel.js" in index_html
    assert index_html.index("/static/watchlist_panel_helpers.js") < index_html.index("/static/watchlist_panel_actions.js")
    assert index_html.index("/static/watchlist_panel_actions.js") < index_html.index("/static/watchlist_panel.js")
    assert index_html.index("/static/watchlist_panel_helpers.js") < index_html.index("/static/watchlist_panel.js")
    assert "/static/watchlist_trigger_form.js" in index_html
    assert "/static/market_screener_helpers.js" in index_html
    assert "/static/market_screener_panel.js" in index_html
    assert index_html.index("/static/market_screener_helpers.js") < index_html.index("/static/market_screener_panel.js")
    assert "/static/temporal_memory_panel.js" in index_html
    assert "/static/performance_panel.js" in index_html
    assert "/static/ops_workspace_elements.js" in index_html
    assert "/static/ops_workspace_loaders.js" in index_html
    assert "/static/ops_workspace_panels.js" in index_html
    assert "/static/ops_workspace.js" in index_html
    assert index_html.index("/static/ops_workspace_elements.js") < index_html.index("/static/ops_workspace.js")
    assert index_html.index("/static/ops_workspace_loaders.js") < index_html.index("/static/ops_workspace.js")
    assert index_html.index("/static/ops_workspace_loaders.js") < index_html.index("/static/ops_workspace_panels.js")
    assert index_html.index("/static/ops_workspace_panels.js") < index_html.index("/static/ops_workspace.js")
    assert "/static/maintenance_notification_delivery.js" in index_html
    assert "/static/daily_decision_queue_context.js" in index_html
    assert index_html.index("/static/daily_decision_queue_context.js") < index_html.index("/static/maintenance_notification_delivery.js")
    assert "/static/maintenance_panel_helpers.js" in index_html
    assert "/static/maintenance_panel.js" in index_html
    assert index_html.index("/static/maintenance_notification_delivery.js") < index_html.index("/static/maintenance_panel_helpers.js")
    assert index_html.index("/static/maintenance_panel_helpers.js") < index_html.index("/static/maintenance_panel.js")
    assert index_html.index("/static/maintenance_notification_delivery.js") < index_html.index("/static/maintenance_panel.js")
    assert "/static/home_tabs.js" in index_html
    assert "/static/report_rerun_stream.js" in index_html
    assert "/static/report_rerun.js" in index_html
    assert index_html.index("/static/report_rerun_stream.js") < index_html.index("/static/report_rerun.js")
    assert "/static/analysis_stream_events.js" in index_html
    assert "/static/analysis_stream.js" in index_html
    assert index_html.index("/static/analysis_stream_events.js") < index_html.index("/static/analysis_stream.js")
    assert "/static/history_panel_quality_helpers.js" in index_html
    assert "/static/history_panel_helpers.js" in index_html
    assert "/static/history_panel_renderers.js" in index_html
    assert "/static/history_panel.js" in index_html
    assert index_html.index("/static/report_quality_policy.js") < index_html.index("/static/history_panel_quality_helpers.js")
    assert index_html.index("/static/history_panel_quality_helpers.js") < index_html.index("/static/history_panel_helpers.js")
    assert index_html.index("/static/history_panel_helpers.js") < index_html.index("/static/history_panel_renderers.js")
    assert index_html.index("/static/history_panel_renderers.js") < index_html.index("/static/history_panel.js")
    assert index_html.index("/static/history_panel_helpers.js") < index_html.index("/static/history_panel.js")
    assert "/static/report_preview_helpers.js" in index_html
    assert "/static/report_preview_tracking_helpers.js" in index_html
    assert "/static/report_preview_rerun_helpers.js" in index_html
    assert "/static/report_preview_panel.js" in index_html
    assert index_html.index("/static/report_quality_policy.js") < index_html.index("/static/report_preview_helpers.js")
    assert index_html.index("/static/report_preview_helpers.js") < index_html.index("/static/report_preview_tracking_helpers.js")
    assert index_html.index("/static/report_preview_tracking_helpers.js") < index_html.index("/static/report_preview_panel.js")
    assert index_html.index("/static/report_preview_helpers.js") < index_html.index("/static/report_preview_panel.js")
    assert index_html.index("/static/report_preview_rerun_helpers.js") < index_html.index("/static/report_preview_panel.js")
    assert "/static/view_controller.js" in index_html
    assert "/static/history_filters.js" in index_html
    assert "/static/report_actions.js" in index_html
    assert "/static/report_navigation_targets.js" in index_html
    assert "/static/report_navigation.js" in index_html
    assert index_html.index("/static/report_navigation_targets.js") < index_html.index("/static/report_navigation.js")
    assert "/static/report_compare_helpers.js" in index_html
    assert "/static/report_compare_renderers.js" in index_html
    assert "/static/report_compare_panel.js" in index_html
    assert index_html.index("/static/report_quality_policy.js") < index_html.index("/static/report_compare_helpers.js")
    assert index_html.index("/static/report_compare_helpers.js") < index_html.index("/static/report_compare_renderers.js")
    assert index_html.index("/static/report_compare_renderers.js") < index_html.index("/static/report_compare_panel.js")
    assert "/static/history_workspace_actions.js" in index_html
    assert "/static/history_workspace.js" in index_html
    assert index_html.index("/static/report_compare_helpers.js") < index_html.index("/static/report_compare_panel.js")
    assert "/static/decision_tracking_helpers.js" in index_html
    assert index_html.index("/static/report_quality_policy.js") < index_html.index("/static/decision_tracking_helpers.js")
    assert index_html.index("/static/decision_tracking_helpers.js") < index_html.index("/static/decision_tracking_panel.js")
    assert "/static/history_workspace_panels.js" in index_html
    assert index_html.index("/static/history_workspace_panels.js") < index_html.index("/static/history_workspace_actions.js")
    assert index_html.index("/static/history_workspace_actions.js") < index_html.index("/static/history_workspace.js")
    assert "/static/ui_data_trust.js" in index_html
    assert "/static/pipeline_mode_fallback.js" in index_html
    assert "/static/ui_helpers.js" in index_html
    assert index_html.index("/static/ui_data_trust.js") < index_html.index("/static/pipeline_mode_fallback.js") < index_html.index("/static/ui_helpers.js")
    assert "/static/api_request.js" in index_html
    assert "/static/api_client.js" in index_html
    assert index_html.index("/static/api_request.js") < index_html.index("/static/api_client.js")
    assert "/static/api_client_extensions.js" in index_html
    assert "/static/notification_center.js" in index_html
    assert "/static/app_elements.js" in index_html
    assert "/static/app_pipeline_controls.js" in index_html
    assert "/static/app_panels.js" in index_html
    assert index_html.index("/static/app_elements.js") < index_html.index("/static/app.js")
    assert index_html.index("/static/app_pipeline_controls.js") < index_html.index("/static/app.js")
    assert index_html.index("/static/app_pipeline_controls.js") < index_html.index("/static/app_panels.js")
    assert index_html.index("/static/app_panels.js") < index_html.index("/static/app.js")
    assert "StockAgentAppElements.collect" in app_js
    assert "StockAgentAppElements" in app_elements_js
    assert "StockAgentAppPipelineControls.create" in app_js
    assert "StockAgentAppPipelineControls" in app_pipeline_controls_js
    assert "StockAgentAppPanels.create" in app_js
    assert "StockAgentAppPanels" in app_panels_js
    assert "historyDataTrustFilter" in app_elements_js
    assert "decisionTrackingRunActions" in app_elements_js
    assert "StockAgentNotificationCenter.create" in app_js
    assert "StockAgentNotificationCenter" in notification_center_js
    assert "aria-live" in notification_center_js
    assert "confirm(" not in history_workspace_js
    assert "alert(" not in app_js
    assert "alert(" not in history_workspace_js
    assert "window.alert" not in report_rerun_js
    assert "notify.confirm" in history_workspace_actions_js
    assert "notify.success" in history_workspace_actions_js
    assert "notify.error" in history_workspace_actions_js
    assert "notify.success" in report_rerun_js
    assert "notify.error" in report_rerun_js
    assert "StockAgentOpsWorkspaceElements.collect" in ops_workspace_js
    assert "StockAgentOpsWorkspaceElements" in ops_workspace_elements_js
    assert "providerSlaWindow" in ops_workspace_elements_js
    assert "watchlistStockSnapshotRoot" in ops_workspace_elements_js
    assert "portfolioRiskElements" in ops_workspace_elements_js
    assert "StockAgentOpsWorkspaceLoaders" in ops_workspace_js
    assert "StockAgentOpsWorkspaceLoaders" in ops_workspace_loaders_js
    assert "StockAgentOpsWorkspacePanels" in ops_workspace_js
    assert "StockAgentOpsWorkspacePanels" in ops_workspace_panels_js
    assert "loadPanel" in ops_workspace_loaders_js
    assert "請稍後重試" in ops_workspace_loaders_js
    assert "providerSlaWindow" in ops_workspace_panels_js
    assert "StockAgentProviderSlaPanel.render" in ops_workspace_panels_js
    assert "StockAgentActiveJobsPanel.render" in ops_workspace_panels_js
    assert "StockAgentPerformancePanel.render" in ops_workspace_panels_js
    assert "StockAgentMarketScreenerHelpers" in market_screener_helpers_js
    assert "StockAgentMarketScreenerHelpers" in (STATIC_DIR / "market_screener_panel.js").read_text(encoding="utf-8")
    assert "StockAgentWatchlistPanelHelpers" in watchlist_panel_js
    assert "StockAgentWatchlistPanelHelpers" in watchlist_helpers_js
    assert "StockAgentWatchlistPanelActions" in watchlist_panel_js
    assert "StockAgentWatchlistPanelActions" in watchlist_actions_js
    assert "decision_priority" in watchlist_helpers_js
    assert "需重跑" in watchlist_helpers_js
    assert "StockAgentOpsWorkspace.create" in app_panels_js
    assert "StockAgentOperatorSummaryPanel.create" in app_panels_js
    assert "StockAgentOperatorSummaryHelpers" in operator_summary_js
    assert "StockAgentOperatorSummaryHelpers" in operator_summary_helpers_js
    assert "operatorSummary.load" in app_panels_js
    assert "fetchDailyDecisionDashboard" in api_client_extensions_js
    assert "fetchSymbolSuggestions" in api_client_extensions_js
    assert "importWatchlistText" in api_client_extensions_js
    assert "apiClient.fetchDailyDecisionDashboard" in operator_summary_js
    assert "reports_needing_rerun" in operator_dashboard_actions_js
    assert "watchlist_high_priority" in operator_dashboard_actions_js
    assert "StockAgentHistoryWorkspacePanels" in history_workspace_js
    assert "StockAgentHistoryWorkspacePanels" in history_workspace_panels_js
    assert "StockAgentHistoryWorkspaceActions" in history_workspace_js
    assert "StockAgentHistoryWorkspaceActions" in history_workspace_actions_js
    assert "StockAgentHistoryPanel.create" in history_workspace_panels_js
    assert "StockAgentReportPreviewPanel.create" in history_workspace_panels_js
    assert "StockAgentReportCompareHelpers" in report_compare_helpers_js
    assert "StockAgentReportQualityPolicy" in report_compare_helpers_js
    assert "StockAgentReportCompareRenderers" in report_compare_js
    assert "StockAgentReportCompareRenderers" in report_compare_renderers_js
    assert "StockAgentReportCompareHelpers" in report_compare_renderers_js
    assert "formatDelta" in report_compare_helpers_js
    assert "compareSummaryLabel" in report_compare_helpers_js
    assert "compareWarningMessage" in report_compare_helpers_js
    assert "reportDecisionStatusLabel" in report_compare_helpers_js
    assert "StockAgentDecisionTrackingHelpers" in decision_tracking_js
    assert "StockAgentDecisionTrackingHelpers" in decision_tracking_helpers_js
    assert "StockAgentReportQualityPolicy" in decision_tracking_helpers_js
    assert "uniqueRecommendedActions" in decision_tracking_helpers_js
    assert "trackedGroups" in decision_tracking_helpers_js
    assert "StockAgentTemporalMemoryPanel.render" in report_preview_js
    assert "Agent 歷史反思" in temporal_memory_js
    assert "StockAgentViewController.create" in app_js
    assert "StockAgentHistoryFilters.create" in history_workspace_panels_js
    assert "StockAgentReportActions.bindDownloads" in app_js
    assert "StockAgentReportNavigation.bind" in app_js
    assert "StockAgentHomeTabs" in home_tabs_js
    assert "data-home-tab" in home_tabs_js
    assert "onActivate" in home_tabs_js
    assert "loadAllOnce" in app_js
    assert "refreshProviderSlaIfLoaded" in app_panels_js

    assert "refreshProviderSlaIfLoaded" in ops_workspace_js
    assert "providerSlaDirty" in ops_workspace_js
    assert "loadProviderSla" not in history_workspace_js
    assert "refreshProviderSlaIfLoaded" in history_workspace_js
    assert "refreshProviderSlaIfLoaded" in report_rerun_js
    assert "opsWorkspace.loadAll();" not in app_js
    assert "StockAgentReportNavigationTargets" in report_navigation_js
    assert "StockAgentReportNavigationTargets" in report_navigation_targets_js
    assert "targetForItem" in report_navigation_targets_js
    assert "scrollIntoView" in report_navigation_js
    assert "doc.getElementById(id)" in report_navigation_targets_js
    assert "ensureLabel" in report_navigation_targets_js
    assert "StockAgentHistoryPanelRenderers" in history_panel_renderers_js
    assert "StockAgentReportQualityGatePolicy" in report_quality_gate_policy_js
    assert "StockAgentReportQualityPolicy" in report_quality_policy_js
    assert "StockAgentReportReadingBoundaryPolicy" in report_reading_boundary_js
    assert "reportReadingBoundary" in report_quality_policy_js
    assert "reportRerunMessage" in report_quality_policy_js
    assert "StockAgentReportQualityPolicy" in history_panel_quality_helpers_js
    assert "StockAgentReportQualityPolicy" in operator_summary_quality_helpers_js
    assert "StockAgentHistoryPanelQualityHelpers" in history_panel_quality_helpers_js
    assert "StockAgentHistoryPanelQualityHelpers" in history_panel_helpers_js
    assert "history-item" in history_panel_renderers_js
    assert "history-tracking" in history_panel_helpers_js
    assert "decision_tracking" in history_panel_renderers_js
    assert "decision-tracking-title" in history_panel_renderers_js
    assert "preview-date" in report_preview_js
    assert "preview-tracking-latest" in report_preview_js
    assert "decision_tracking" in report_preview_js
    assert "StockAgentReportQualityPolicy" in report_preview_js
    assert "reportRecommendedAction?.(report)" in report_preview_js
    assert "reportNeedsRerun?.(report)" in report_preview_js
    assert "reportRerunMessage" in report_preview_js
    assert "reportRerunMessage" in history_panel_quality_helpers_js
    assert "StockAgentReportPreviewHelpers" in report_preview_js
    assert "StockAgentReportPreviewTrackingHelpers" in report_preview_js
    assert "StockAgentReportPreviewTrackingHelpers" in report_preview_tracking_helpers_js
    assert "trackingView" in report_preview_tracking_helpers_js
    assert "renderTracking" in report_preview_tracking_helpers_js
    assert "awaitingTrackingPrice" in report_preview_tracking_helpers_js
    assert "尚待新價格" in report_preview_tracking_helpers_js
    assert "StockAgentReportPreviewRerunHelpers" in report_preview_js
    assert "StockAgentReportPreviewRerunHelpers" in report_preview_rerun_helpers_js
    assert "configureRerunButtons" in report_preview_rerun_helpers_js
    assert "shortLabel" in report_preview_rerun_helpers_js
    assert "重跑${shortLabel}報告結論" in report_preview_rerun_helpers_js
    assert "重跑${shortLabel}最終建議" not in report_preview_js
    assert "完整重跑${shortLabel}" in report_preview_rerun_helpers_js
    assert "模式 C：逆勢交易與泡沫狙擊" in pipeline_mode_fallback_js
    assert "full_report" in report_rerun_js
    assert "rerunModeBBtn.hidden = isModeB" in report_preview_rerun_helpers_js
    assert "產生模式 B 報告" in report_preview_rerun_helpers_js
    assert "產生模式 B 報告" in index_html
    assert "history-item" not in app_js
    assert "providerSlaStatsForWindow" in provider_sla_js
    assert "StockAgentProviderSlaHelpers" in provider_sla_js
    assert "StockAgentProviderSlaHelpers" in provider_sla_helpers_js
    assert "groupedProviderRows" in provider_sla_helpers_js
    assert "股價與基本資料" in provider_sla_helpers_js
    assert "同業指標" in provider_sla_helpers_js
    assert "可安心使用" in provider_sla_helpers_js
    assert "provider-sla-insight" in provider_sla_js
    assert "正式分析流程" in provider_sla_helpers_js
    assert "有效快取或備援來源" in provider_sla_helpers_js
    assert "degraded_enrichment_count" in provider_sla_helpers_js
    assert "降級可用" in provider_sla_helpers_js
    assert "availabilityAttemptsForStats" in provider_sla_helpers_js
    assert "not_configured" in provider_sla_helpers_js
    assert "選用來源略過" in provider_sla_helpers_js
    assert "先使用仍有效的快取" in provider_sla_helpers_js
    assert "系統會優先補快取" not in provider_sla_helpers_js
    assert "資料取得率" in provider_sla_js

    assert "來源明細" in provider_sla_js
    assert "provider-sla-provider-list" in provider_sla_js
    assert "analysis_text_stale" in history_workspace_actions_js
    assert "payload.analysis_text_stale ?? previewReport.analysis_text_stale" in history_workspace_actions_js
    assert "payload.analysis_text_stale_message ?? previewReport.analysis_text_stale_message" in history_workspace_actions_js
    assert "evidence_exit_gate" in report_quality_policy_js
    assert "report_conformance" in report_quality_policy_js
    assert "數字證據需人工核對" in report_quality_gate_policy_js
    assert "報告符合性未通過" in report_quality_gate_policy_js
    assert "reportQualityBadge" in report_preview_helpers_js
    assert "reportReadingNotice" in report_preview_helpers_js
    assert "reportReadingBoundary" in report_preview_js
    assert ".preview-reading-notice" in preview_panel_quality_css
    assert "StockAgentReportQualityPolicy" in report_preview_helpers_js
    assert "freshness.requires_rerun_reason" not in report_preview_js
    assert "freshness.requires_rerun" not in report_preview_js
    assert "report.analysis_text_stale" not in report_preview_js
    assert "report.analysis_text_stale_message" not in report_preview_js
    assert "conformance.status" not in report_preview_helpers_js
    assert "gate.verdict" not in report_preview_helpers_js
    assert "reportQualityGateAction" in report_quality_policy_js
    assert "證據抽查未通過" in report_quality_gate_policy_js
    assert "報告符合性未通過" in report_quality_gate_policy_js
    assert '<h2 id="preview-title" class="preview-title">報告建議</h2>' in index_html
    assert '<h2 id="preview-title" class="preview-title">投資建議</h2>' not in index_html
    assert 'aria-label="關閉報告預覽"' in index_html
    assert 'aria-label="關閉投資建議預覽"' not in index_html
    assert '<span class="preview-label">報告建議</span>' in index_html
    assert '<span>重跑報告結論</span>' in index_html
    assert "重跑最終建議" not in index_html
    assert "報告建議" in report_preview_helpers_js
    assert "仍需自行判斷" in report_preview_helpers_js
    assert "${report.ticker} 投資建議" not in report_preview_js
    assert "label: '建議'" not in report_preview_helpers_js
    assert "StockAgentOperatorSummaryQualityHelpers" in operator_summary_quality_helpers_js
    assert "StockAgentOperatorSummaryQualityHelpers" in operator_summary_helpers_js
    assert "證據抽查未通過" in report_quality_gate_policy_js
    assert "報告符合性未通過" in report_quality_gate_policy_js
    assert "資料新鮮 ${fresh} / 抽樣 ${reports.length}" in operator_summary_helpers_js
    assert "fresh ${fresh} / sampled ${reports.length}" not in operator_summary_helpers_js
    assert "rerunPreviewReport" in history_workspace_actions_js
    assert "StockAgentReportRerun.rerunPreviewReport" in history_workspace_actions_js
    assert "/rerun?scope=" in report_rerun_js
    assert "/rerun/cancel" in report_rerun_js
    assert "buttons.cancel" in report_rerun_js
    assert "StockAgentReportRerunStream" in report_rerun_js
    assert "StockAgentReportRerunStream" in report_rerun_stream_js
    assert "new EventSource" in report_rerun_stream_js
    assert "StockAgentAnalysisStream.create" in app_js
    assert "resetAndConnect" in analysis_stream_js
    assert "/api/analyze/" in analysis_stream_js
    assert "new EventSource" in analysis_stream_js
    assert "StockAgentAnalysisStreamEvents" in analysis_stream_js
    assert "StockAgentAnalysisStreamEvents" in analysis_stream_events_js
    assert "pipeline_start" in analysis_stream_events_js
    assert "pendingAuditNotice" in analysis_stream_events_js
    assert "params.set('window'" in api_client_js
    assert "/api/observability/provider-sla" in api_client_js
    assert "/api/observability/active-jobs" in api_client_js
    assert "/api/observability/api-quotas" in api_client_extensions_js
    assert "/api/reports/compare" in api_client_extensions_js
    assert "決策狀態" in report_compare_renderers_js
    assert "reportDecisionStatusLabel(left)" in report_compare_renderers_js
    assert "decisionStatusLabel(left.decision_freshness)" not in report_compare_renderers_js
    assert "pipelineModeLabel" in report_compare_js
    assert "pipelineModeLabel" in report_compare_helpers_js
    assert "window.StockAgentUi?.pipelineModeLabel" in report_compare_js
    assert "pipelineModeLabel: ui.pipelineModeLabel" in history_workspace_panels_js
    assert "${report.pipeline_id || 'v1'}" not in report_compare_js
    assert "比較基準" in report_compare_renderers_js
    assert "比較樣本" in report_compare_renderers_js
    assert "比較結論" in report_compare_renderers_js
    assert "compareSummaryLabel" in report_compare_helpers_js
    assert "同股票同模式" in report_compare_helpers_js
    assert "報告建議變化" in report_compare_renderers_js
    assert "使用提醒" in report_compare_renderers_js
    assert "不代表即時交易指令" in report_compare_renderers_js
    assert "判讀層次" in report_compare_renderers_js
    assert "報告差異不等於市場因果" in report_compare_renderers_js
    assert "搭配資料可信度與追蹤報酬判讀" in report_compare_renderers_js
    assert "['建議'" not in report_compare_js
    assert "pipelineModeLabel(left.pipeline_id || 'v1')" in report_compare_renderers_js
    assert "dateOrderLabel(compatibility.date_order)" in report_compare_renderers_js
    assert "dateOrderLabel(compatibility.date_order)" in report_compare_helpers_js
    assert "compareWarningMessage" in report_compare_helpers_js
    assert "different_pipeline" in report_compare_helpers_js
    assert "兩份報告模式不同" in report_compare_helpers_js
    assert "跨視角比較" in report_compare_helpers_js
    assert "decision_needs_rerun" in report_compare_helpers_js
    assert "若要比較投資判斷，需先重跑結論" in report_compare_helpers_js
    assert "需先重跑結論，再比較投資判斷" not in report_compare_js
    assert " vs " not in report_compare_js
    assert "/api/watchlist" in api_client_extensions_js
    assert "watchlist-trigger-vix" in index_html
    assert "StockAgentWatchlistTriggerForm" in watchlist_helpers_js
    assert "fetchSymbolSuggestions" in watchlist_actions_js
    assert "importWatchlistText" in watchlist_actions_js
    assert "latest_trigger_event" in watchlist_panel_js
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
    assert "/api/observability/dashboard" in api_client_js
    assert "mutation: true" in api_client_js
    assert "fetchOpsDashboard" in api_client_js
    assert "cleanupAnalysisHistory" in api_client_js
    assert "StockAgentMaintenancePanel" in maintenance_js
    assert "StockAgentMaintenancePanelHelpers" in maintenance_js
    assert "StockAgentMaintenanceNotificationDelivery" in maintenance_helpers_js
    assert "StockAgentMaintenancePanelHelpers" in maintenance_helpers_js
    assert "StockAgentMaintenanceNotificationDelivery" in maintenance_notification_js
    assert "maintenance-clean-provider-sla" in maintenance_js
    assert "notification_delivery" in maintenance_js
    assert "retry_exhausted_count" in maintenance_notification_js
    assert "channel_counts" in maintenance_notification_js
    assert "failure_reason_counts" in maintenance_notification_js
    assert "LLM 健康" in index_html
    assert "刷新 LLM 健康" in index_html
    assert "LLM 健康讀取失敗" in ops_workspace_panels_js
    assert "LLM/API 健康" in api_quota_panel_js
    assert "LLM 健康" in operator_summary_helpers_js
    assert "llm_error_counts" in active_jobs_js
    assert "token_estimate" not in active_jobs_js
    assert "估算 token" not in active_jobs_js
    assert "stage_summary" in active_jobs_js
    assert "最近完成任務" in active_jobs_js
    assert "模型重試" in active_jobs_js
    assert "模型錯誤" in active_jobs_js
    assert "pipelineModeLabel" in active_jobs_js
    assert "pipelineModeLabel: ui.pipelineModeLabel" in ops_workspace_panels_js
    assert "renderPipelineModeBadge" in ui_helpers_js
    assert "renderDataTrustReason" in ui_helpers_js
    assert "data-trust-reason" in ui_helpers_js
    assert "StockAgentUiDataTrust" in ui_data_trust_js
    assert "StockAgentUiDataTrust" in ui_helpers_js
    assert "本報告資料新鮮" in ui_data_trust_js
    assert "系統來源當時不穩" in ui_data_trust_js
    assert "/refresh/data" in api_client_js
    assert "historyWorkspaceEl" in app_elements_js
    assert "historyWorkspace: elements.historyWorkspaceEl" in app_panels_js
    assert "workspace: elements.historyWorkspace" in history_workspace_panels_js
    assert ".history-workspace.has-preview" in history_list_css
    for selector in (
        ".history-controls",
        ".history-filter-row",
        ".history-filter-select",
        ".history-version-toggle",
        ".history-search",
        ".delete-btn",
        ".history-pagination",
        ".pager-btn",
    ):
        assert selector not in history_list_css
        assert selector in history_list_controls_css
    assert ".report-preview[hidden]" in preview_panel_css
    assert "display: none" in preview_panel_css
    assert "visibility: hidden" not in preview_panel_css
    assert ".preview-open-button" not in preview_panel_css
    assert ".preview-open-button" in preview_panel_actions_css
    assert ".preview-refresh-button" not in preview_panel_css
    assert ".preview-refresh-button" in preview_panel_actions_css
    assert ".preview-rerun-row" not in preview_panel_css
    assert ".preview-rerun-row" in preview_panel_actions_css
    assert ".preview-rerun-button" not in preview_panel_css
    assert ".preview-rerun-button" in preview_panel_actions_css
    assert ".preview-rerun-cancel-button" not in preview_panel_css
    assert ".preview-rerun-cancel-button" in preview_panel_actions_css
    assert "style=" not in index_html
    assert ".report-actions" in loading_report_css
    assert ".report-download-button" in loading_report_css
    assert "@media (max-width: 640px)" in loading_report_css
    assert "await res.text()" in api_request_js
    assert "JSON.parse" in api_request_js
    assert "payload.message" in api_request_js
    assert "/api/client-config" in api_request_js
    assert "mutation_token" in api_request_js
    assert "X-Mutation-Token" in api_request_js
    assert "StockAgentApiRequest" in api_request_js
    assert "StockAgentApiRequest.requestJson" in api_client_js
    assert "window.StockAgentApiClient.requestJson" in api_client_extensions_js
    assert "apiClient.requestJson" in report_rerun_js
    assert "fetchActiveJobs" in operator_summary_js
    assert "fetchApiQuotas" in operator_summary_js


def test_stock_snapshot_panel_is_wired_for_consumer_stock_page():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    app_panels_js = (STATIC_DIR / "app_panels.js").read_text(encoding="utf-8")
    app_panels_js = (STATIC_DIR / "app_panels.js").read_text(encoding="utf-8")
    api_client_extensions_js = (STATIC_DIR / "api_client_extensions.js").read_text(encoding="utf-8")
    stock_snapshot_numeric_format_helpers_path = STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"
    assert stock_snapshot_numeric_format_helpers_path.exists()
    stock_snapshot_numeric_format_helpers_js = stock_snapshot_numeric_format_helpers_path.read_text(encoding="utf-8")
    stock_snapshot_domain_format_helpers_path = STATIC_DIR / "stock_snapshot_domain_format_helpers.js"
    assert stock_snapshot_domain_format_helpers_path.exists()
    stock_snapshot_domain_format_helpers_js = stock_snapshot_domain_format_helpers_path.read_text(encoding="utf-8")
    stock_snapshot_performance_helpers_path = STATIC_DIR / "stock_snapshot_performance_helpers.js"
    assert stock_snapshot_performance_helpers_path.exists()
    stock_snapshot_performance_helpers_js = stock_snapshot_performance_helpers_path.read_text(encoding="utf-8")
    stock_snapshot_format_helpers_path = STATIC_DIR / "stock_snapshot_format_helpers.js"
    assert stock_snapshot_format_helpers_path.exists()
    stock_snapshot_format_helpers_js = stock_snapshot_format_helpers_path.read_text(encoding="utf-8")
    stock_snapshot_helpers_path = STATIC_DIR / "stock_snapshot_helpers.js"
    assert stock_snapshot_helpers_path.exists()
    stock_snapshot_helpers_js = stock_snapshot_helpers_path.read_text(encoding="utf-8")
    stock_snapshot_input_helpers_path = STATIC_DIR / "stock_snapshot_input_helpers.js"
    assert stock_snapshot_input_helpers_path.exists()
    stock_snapshot_input_helpers_js = stock_snapshot_input_helpers_path.read_text(encoding="utf-8")
    stock_snapshot_load_helpers_path = STATIC_DIR / "stock_snapshot_load_helpers.js"
    assert stock_snapshot_load_helpers_path.exists()
    stock_snapshot_load_helpers_js = stock_snapshot_load_helpers_path.read_text(encoding="utf-8")
    stock_snapshot_action_helpers_path = STATIC_DIR / "stock_snapshot_action_helpers.js"
    assert stock_snapshot_action_helpers_path.exists()
    stock_snapshot_action_helpers_js = stock_snapshot_action_helpers_path.read_text(encoding="utf-8")
    stock_snapshot_summary_helpers_path = STATIC_DIR / "stock_snapshot_summary_helpers.js"
    assert stock_snapshot_summary_helpers_path.exists()
    stock_snapshot_summary_helpers_js = stock_snapshot_summary_helpers_path.read_text(encoding="utf-8")
    stock_snapshot_sections_path = STATIC_DIR / "stock_snapshot_sections.js"
    assert stock_snapshot_sections_path.exists()
    stock_snapshot_sections_js = stock_snapshot_sections_path.read_text(encoding="utf-8")
    stock_snapshot_overview_sections_path = STATIC_DIR / "stock_snapshot_overview_sections.js"
    assert stock_snapshot_overview_sections_path.exists()
    stock_snapshot_overview_sections_js = stock_snapshot_overview_sections_path.read_text(encoding="utf-8")
    stock_snapshot_research_sections_path = STATIC_DIR / "stock_snapshot_research_sections.js"
    assert stock_snapshot_research_sections_path.exists()
    stock_snapshot_research_sections_js = stock_snapshot_research_sections_path.read_text(encoding="utf-8")
    stock_snapshot_signal_sections_path = STATIC_DIR / "stock_snapshot_signal_sections.js"
    assert stock_snapshot_signal_sections_path.exists()
    stock_snapshot_signal_sections_js = stock_snapshot_signal_sections_path.read_text(encoding="utf-8")
    stock_snapshot_supplemental_sections_path = STATIC_DIR / "stock_snapshot_supplemental_sections.js"
    assert stock_snapshot_supplemental_sections_path.exists()
    stock_snapshot_supplemental_sections_js = stock_snapshot_supplemental_sections_path.read_text(encoding="utf-8")
    stock_snapshot_interaction_helpers_path = STATIC_DIR / "stock_snapshot_interaction_helpers.js"
    assert stock_snapshot_interaction_helpers_path.exists()
    stock_snapshot_interaction_helpers_js = stock_snapshot_interaction_helpers_path.read_text(encoding="utf-8")
    stock_snapshot_render_helpers_path = STATIC_DIR / "stock_snapshot_render_helpers.js"
    assert stock_snapshot_render_helpers_path.exists()
    stock_snapshot_render_helpers_js = stock_snapshot_render_helpers_path.read_text(encoding="utf-8")
    stock_snapshot_event_helpers_path = STATIC_DIR / "stock_snapshot_event_helpers.js"
    assert stock_snapshot_event_helpers_path.exists()
    stock_snapshot_event_helpers_js = stock_snapshot_event_helpers_path.read_text(encoding="utf-8")
    stock_snapshot_js = (STATIC_DIR / "stock_snapshot_panel.js").read_text(encoding="utf-8")
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    stock_snapshot_shell_css_path = STATIC_DIR / "styles" / "stock_snapshot_shell.css"
    assert stock_snapshot_shell_css_path.exists()
    stock_snapshot_shell_css = stock_snapshot_shell_css_path.read_text(encoding="utf-8")
    stock_snapshot_overview_css_path = STATIC_DIR / "styles" / "stock_snapshot_overview.css"
    assert stock_snapshot_overview_css_path.exists()
    stock_snapshot_overview_css = stock_snapshot_overview_css_path.read_text(encoding="utf-8")
    stock_snapshot_overview_trend_css_path = STATIC_DIR / "styles" / "stock_snapshot_overview_trend.css"
    assert stock_snapshot_overview_trend_css_path.exists()
    stock_snapshot_overview_trend_css = stock_snapshot_overview_trend_css_path.read_text(encoding="utf-8")
    stock_snapshot_overview_performance_css_path = STATIC_DIR / "styles" / "stock_snapshot_overview_performance.css"
    assert stock_snapshot_overview_performance_css_path.exists()
    stock_snapshot_overview_performance_css = stock_snapshot_overview_performance_css_path.read_text(encoding="utf-8")
    stock_snapshot_overview_technical_css_path = STATIC_DIR / "styles" / "stock_snapshot_overview_technical.css"
    assert stock_snapshot_overview_technical_css_path.exists()
    stock_snapshot_overview_technical_css = stock_snapshot_overview_technical_css_path.read_text(encoding="utf-8")
    stock_snapshot_research_css_path = STATIC_DIR / "styles" / "stock_snapshot_research.css"
    assert stock_snapshot_research_css_path.exists()
    stock_snapshot_research_css = stock_snapshot_research_css_path.read_text(encoding="utf-8")
    stock_snapshot_research_analyst_css_path = STATIC_DIR / "styles" / "stock_snapshot_research_analyst.css"
    assert stock_snapshot_research_analyst_css_path.exists()
    stock_snapshot_research_analyst_css = stock_snapshot_research_analyst_css_path.read_text(encoding="utf-8")
    stock_snapshot_signal_css_path = STATIC_DIR / "styles" / "stock_snapshot_signal.css"
    assert stock_snapshot_signal_css_path.exists()
    stock_snapshot_signal_css = stock_snapshot_signal_css_path.read_text(encoding="utf-8")
    stock_snapshot_signal_dividend_css_path = STATIC_DIR / "styles" / "stock_snapshot_signal_dividend.css"
    assert stock_snapshot_signal_dividend_css_path.exists()
    stock_snapshot_signal_dividend_css = stock_snapshot_signal_dividend_css_path.read_text(encoding="utf-8")
    stock_snapshot_signal_events_css_path = STATIC_DIR / "styles" / "stock_snapshot_signal_events.css"
    assert stock_snapshot_signal_events_css_path.exists()
    stock_snapshot_signal_events_css = stock_snapshot_signal_events_css_path.read_text(encoding="utf-8")
    stock_snapshot_core_css_path = STATIC_DIR / "styles" / "stock_snapshot_core.css"
    assert stock_snapshot_core_css_path.exists()
    stock_snapshot_core_css = stock_snapshot_core_css_path.read_text(encoding="utf-8")
    stock_snapshot_core_peer_ownership_css_path = STATIC_DIR / "styles" / "stock_snapshot_core_peer_ownership.css"
    assert stock_snapshot_core_peer_ownership_css_path.exists()
    stock_snapshot_core_peer_ownership_css = stock_snapshot_core_peer_ownership_css_path.read_text(encoding="utf-8")
    stock_snapshot_supplemental_css_path = STATIC_DIR / "styles" / "stock_snapshot_supplemental.css"
    assert stock_snapshot_supplemental_css_path.exists()
    stock_snapshot_supplemental_css = stock_snapshot_supplemental_css_path.read_text(encoding="utf-8")
    stock_snapshot_responsive_css_path = STATIC_DIR / "styles" / "stock_snapshot_responsive.css"
    assert stock_snapshot_responsive_css_path.exists()
    stock_snapshot_responsive_css = stock_snapshot_responsive_css_path.read_text(encoding="utf-8")
    stock_snapshot_responsive_headers_css_path = STATIC_DIR / "styles" / "stock_snapshot_responsive_headers.css"
    assert stock_snapshot_responsive_headers_css_path.exists()
    stock_snapshot_responsive_headers_css = stock_snapshot_responsive_headers_css_path.read_text(encoding="utf-8")
    stock_snapshot_responsive_mobile_css_path = STATIC_DIR / "styles" / "stock_snapshot_responsive_mobile.css"
    assert stock_snapshot_responsive_mobile_css_path.exists()
    stock_snapshot_responsive_mobile_css = stock_snapshot_responsive_mobile_css_path.read_text(encoding="utf-8")
    stock_snapshot_css_path = STATIC_DIR / "styles" / "stock_snapshot.css"
    assert not stock_snapshot_css_path.exists()

    assert 'id="stock-snapshot-panel"' in index_html
    assert 'id="stock-snapshot-load-btn"' in index_html
    assert 'id="stock-snapshot-shortcuts"' in index_html
    assert "股票快照" in index_html
    assert "/static/stock_snapshot_numeric_format_helpers.js" in index_html
    assert "/static/stock_snapshot_domain_format_helpers.js" in index_html
    assert "/static/stock_snapshot_performance_helpers.js" in index_html
    assert "/static/stock_snapshot_format_helpers.js" in index_html
    assert "/static/stock_snapshot_helpers.js" in index_html
    assert "/static/stock_snapshot_input_helpers.js" in index_html
    assert "/static/stock_snapshot_load_helpers.js" in index_html
    assert "/static/stock_snapshot_action_helpers.js" in index_html
    assert "/static/stock_snapshot_summary_helpers.js" in index_html
    assert "/static/stock_snapshot_sections.js" in index_html
    assert "/static/stock_snapshot_overview_sections.js" in index_html
    assert "/static/stock_snapshot_research_sections.js" in index_html
    assert "/static/stock_snapshot_signal_sections.js" in index_html
    assert "/static/stock_snapshot_supplemental_sections.js" in index_html
    assert "/static/stock_snapshot_interaction_helpers.js" in index_html
    assert "/static/stock_snapshot_render_helpers.js" in index_html
    assert "/static/stock_snapshot_event_helpers.js" in index_html
    assert "/static/stock_snapshot_panel.js" in index_html
    assert index_html.index("/static/stock_snapshot_numeric_format_helpers.js") < index_html.index("/static/stock_snapshot_domain_format_helpers.js")
    assert index_html.index("/static/stock_snapshot_domain_format_helpers.js") < index_html.index("/static/stock_snapshot_performance_helpers.js")
    assert index_html.index("/static/stock_snapshot_performance_helpers.js") < index_html.index("/static/stock_snapshot_format_helpers.js")
    assert index_html.index("/static/stock_snapshot_format_helpers.js") < index_html.index("/static/stock_snapshot_helpers.js")
    assert index_html.index("/static/stock_snapshot_helpers.js") < index_html.index("/static/stock_snapshot_input_helpers.js")
    assert index_html.index("/static/stock_snapshot_input_helpers.js") < index_html.index("/static/stock_snapshot_load_helpers.js")
    assert index_html.index("/static/stock_snapshot_load_helpers.js") < index_html.index("/static/stock_snapshot_action_helpers.js")
    assert index_html.index("/static/stock_snapshot_action_helpers.js") < index_html.index("/static/stock_snapshot_summary_helpers.js")
    assert index_html.index("/static/stock_snapshot_summary_helpers.js") < index_html.index("/static/stock_snapshot_sections.js")
    assert index_html.index("/static/stock_snapshot_sections.js") < index_html.index("/static/stock_snapshot_overview_sections.js")
    assert index_html.index("/static/stock_snapshot_overview_sections.js") < index_html.index("/static/stock_snapshot_research_sections.js")
    assert index_html.index("/static/stock_snapshot_research_sections.js") < index_html.index("/static/stock_snapshot_signal_sections.js")
    assert index_html.index("/static/stock_snapshot_signal_sections.js") < index_html.index("/static/stock_snapshot_supplemental_sections.js")
    assert index_html.index("/static/stock_snapshot_supplemental_sections.js") < index_html.index("/static/stock_snapshot_interaction_helpers.js")
    assert index_html.index("/static/stock_snapshot_interaction_helpers.js") < index_html.index("/static/stock_snapshot_render_helpers.js")
    assert index_html.index("/static/stock_snapshot_render_helpers.js") < index_html.index("/static/stock_snapshot_event_helpers.js")
    assert index_html.index("/static/stock_snapshot_event_helpers.js") < index_html.index("/static/stock_snapshot_panel.js")
    assert "fetchStockSnapshot" in api_client_extensions_js
    assert "/api/stocks/" in api_client_extensions_js
    assert "StockAgentStockSnapshotPanel.create" in app_panels_js
    assert "stockSnapshotPanel.bindEvents" in app_panels_js
    assert "shortcutsRoot: elements.stockSnapshotShortcutsEl" in app_panels_js
    assert "StockAgentStockSnapshotHelpers" in stock_snapshot_js
    assert "StockAgentStockSnapshotInputHelpers" in stock_snapshot_js
    assert "StockAgentStockSnapshotLoadHelpers" in stock_snapshot_js
    assert "StockAgentStockSnapshotActionHelpers" in stock_snapshot_js
    assert "StockAgentStockSnapshotSummaryHelpers" in stock_snapshot_js
    assert "StockAgentStockSnapshotSections" in stock_snapshot_js
    assert "StockAgentStockSnapshotOverviewSections" in stock_snapshot_js
    assert "StockAgentStockSnapshotResearchSections" in stock_snapshot_js
    assert "StockAgentStockSnapshotSignalSections" in stock_snapshot_js
    assert "StockAgentStockSnapshotSupplementalSections" in stock_snapshot_js
    assert "StockAgentStockSnapshotInteractionHelpers" in stock_snapshot_js
    assert "StockAgentStockSnapshotRenderHelpers" in stock_snapshot_js
    assert "StockAgentStockSnapshotEventHelpers" in stock_snapshot_js
    assert "StockAgentStockSnapshotNumericFormatHelpers" in stock_snapshot_numeric_format_helpers_js
    assert "StockAgentStockSnapshotNumericFormatHelpers" in stock_snapshot_format_helpers_js
    assert "StockAgentStockSnapshotDomainFormatHelpers" in stock_snapshot_domain_format_helpers_js
    assert "StockAgentStockSnapshotDomainFormatHelpers" in stock_snapshot_format_helpers_js
    assert "StockAgentStockSnapshotPerformanceHelpers" in stock_snapshot_performance_helpers_js
    assert "StockAgentStockSnapshotPerformanceHelpers" in stock_snapshot_format_helpers_js
    assert "StockAgentStockSnapshotFormatHelpers" in stock_snapshot_format_helpers_js
    assert "StockAgentStockSnapshotFormatHelpers" in stock_snapshot_helpers_js
    assert "panelMethods" in stock_snapshot_helpers_js
    assert "fragmentMethods" in stock_snapshot_helpers_js
    assert "inputMethods" in stock_snapshot_input_helpers_js
    assert "loadMethods" in stock_snapshot_load_helpers_js
    assert "actionMethods" in stock_snapshot_action_helpers_js
    assert "summaryMethods" in stock_snapshot_summary_helpers_js
    assert "sectionMethods" in stock_snapshot_sections_js
    assert "overviewSectionMethods" in stock_snapshot_overview_sections_js
    assert "researchSectionMethods" in stock_snapshot_research_sections_js
    assert "signalSectionMethods" in stock_snapshot_signal_sections_js
    assert "supplementalSectionMethods" in stock_snapshot_supplemental_sections_js
    assert "interactionMethods" in stock_snapshot_interaction_helpers_js
    assert "renderMethods" in stock_snapshot_render_helpers_js
    assert "eventMethods" in stock_snapshot_event_helpers_js
    assert "priceLabel" in stock_snapshot_numeric_format_helpers_js
    assert "compact(value)" not in stock_snapshot_numeric_format_helpers_js
    assert "compact(value)" in stock_snapshot_domain_format_helpers_js
    assert "financialValueLabel(value)" not in stock_snapshot_numeric_format_helpers_js
    assert "financialValueLabel(value)" in stock_snapshot_domain_format_helpers_js
    assert "lotsLabel(value)" not in stock_snapshot_numeric_format_helpers_js
    assert "lotsLabel(value)" in stock_snapshot_domain_format_helpers_js
    assert "flowWord(value)" not in stock_snapshot_numeric_format_helpers_js
    assert "flowWord(value)" in stock_snapshot_domain_format_helpers_js
    assert "coverageLabel(value)" not in stock_snapshot_numeric_format_helpers_js
    assert "coverageLabel(value)" in stock_snapshot_domain_format_helpers_js
    assert "performanceRangeChart" in stock_snapshot_performance_helpers_js
    assert "performanceRangeChart" not in stock_snapshot_helpers_js
    assert "eventTimingLabel" in stock_snapshot_format_helpers_js
    assert "financialTrendRow" in stock_snapshot_helpers_js
    assert "dividendBars" in stock_snapshot_helpers_js
    assert "peerRow" in stock_snapshot_helpers_js
    assert "getRecentTickers" in stock_snapshot_input_helpers_js
    assert "rememberTicker" in stock_snapshot_input_helpers_js
    assert "normalizeTickerInput" in stock_snapshot_input_helpers_js
    assert "data-stock-snapshot-shortcut" in stock_snapshot_input_helpers_js
    assert "loadFromInput" in stock_snapshot_load_helpers_js
    assert "fetchStockSnapshot" in stock_snapshot_load_helpers_js
    assert "setLoading" in stock_snapshot_load_helpers_js
    assert "renderHeader" in stock_snapshot_summary_helpers_js
    assert "renderSummaryRail" in stock_snapshot_summary_helpers_js
    assert "renderError" in stock_snapshot_summary_helpers_js
    assert "stock-snapshot-summary-rail" in stock_snapshot_summary_helpers_js
    assert "stock-snapshot-grid" in stock_snapshot_supplemental_sections_js
    assert "company_profile" in stock_snapshot_overview_sections_js
    assert "renderCompanyProfile" in stock_snapshot_overview_sections_js
    assert "mode_suggestions" in stock_snapshot_supplemental_sections_js
    assert "data_quality" in stock_snapshot_summary_helpers_js
    assert "market_session" in stock_snapshot_overview_sections_js
    assert "renderMarketSession" in stock_snapshot_overview_sections_js
    assert "price_trend" in stock_snapshot_overview_sections_js
    assert "renderTrend" in stock_snapshot_overview_sections_js
    assert "performance_history" in stock_snapshot_overview_sections_js
    assert "renderPerformanceHistory" in stock_snapshot_overview_sections_js
    assert "selectPerformanceRange" in stock_snapshot_interaction_helpers_js
    assert "renderHeader" in stock_snapshot_render_helpers_js
    assert "bindEvents" in stock_snapshot_event_helpers_js
    assert "technical_summary" in stock_snapshot_overview_sections_js
    assert "renderTechnicalSummary" in stock_snapshot_overview_sections_js
    assert "analyst_outlook" in stock_snapshot_research_sections_js
    assert "renderAnalystOutlook" in stock_snapshot_research_sections_js
    assert "earnings_forecast" in stock_snapshot_research_sections_js
    assert "renderEarningsForecast" in stock_snapshot_research_sections_js
    assert "share_statistics" in stock_snapshot_signal_sections_js
    assert "renderShareStatistics" in stock_snapshot_signal_sections_js
    assert "risk_liquidity" in stock_snapshot_signal_sections_js
    assert "renderRiskLiquidity" in stock_snapshot_signal_sections_js
    assert "profitability_quality" in stock_snapshot_signal_sections_js
    assert "renderProfitabilityQuality" in stock_snapshot_signal_sections_js
    assert "financial_health" in stock_snapshot_sections_js
    assert "renderFinancialHealth" in stock_snapshot_sections_js
    assert "financial_trends" in stock_snapshot_sections_js
    assert "renderFinancialTrends" in stock_snapshot_sections_js
    assert "dividend_profile" in stock_snapshot_signal_sections_js
    assert "renderDividendProfile" in stock_snapshot_signal_sections_js
    assert "event_calendar" in stock_snapshot_signal_sections_js
    assert "renderEventCalendar" in stock_snapshot_signal_sections_js
    assert "alert_suggestions" in stock_snapshot_signal_sections_js
    assert "renderAlertSuggestions" in stock_snapshot_signal_sections_js
    assert "addToWatchlist" in stock_snapshot_action_helpers_js
    assert "applyAlertSuggestion" in stock_snapshot_action_helpers_js
    assert "resolveWatchlistPipeline" in stock_snapshot_action_helpers_js
    assert "peer_comparison" in stock_snapshot_sections_js
    assert "renderPeerComparison" in stock_snapshot_sections_js
    assert "ownership_flow" in stock_snapshot_sections_js
    assert "renderOwnershipFlow" in stock_snapshot_sections_js
    assert "valuation_range" in stock_snapshot_research_sections_js
    assert "renderValuationRange" in stock_snapshot_research_sections_js
    assert "stock-snapshot-trend" in stock_snapshot_overview_sections_js
    assert "stock-snapshot-performance" in stock_snapshot_overview_sections_js
    assert "stock-snapshot-company-profile" in stock_snapshot_overview_sections_js
    assert "stock-snapshot-session" in stock_snapshot_overview_sections_js
    assert "stock-snapshot-technical" in stock_snapshot_overview_sections_js
    assert "stock-snapshot-analyst" in stock_snapshot_research_sections_js
    assert "stock-snapshot-earnings" in stock_snapshot_research_sections_js
    assert "stock-snapshot-shares" in stock_snapshot_signal_sections_js
    assert "stock-snapshot-risk" in stock_snapshot_signal_sections_js
    assert "stock-snapshot-profitability" in stock_snapshot_signal_sections_js
    assert "stock-snapshot-dividend" in stock_snapshot_signal_sections_js
    assert "stock-snapshot-calendar" in stock_snapshot_signal_sections_js
    assert "stock-snapshot-alerts" in stock_snapshot_signal_sections_js
    assert "stock-snapshot-fundamentals" in stock_snapshot_sections_js
    assert "stock-snapshot-financial-trends" in stock_snapshot_sections_js
    assert "stock-snapshot-peers" in stock_snapshot_sections_js
    assert "stock-snapshot-ownership" in stock_snapshot_sections_js
    assert "stock-snapshot-valuation-range" in stock_snapshot_research_sections_js
    assert "stock-snapshot-strip" in stock_snapshot_supplemental_sections_js
    assert "stock-snapshot-news" in stock_snapshot_supplemental_sections_js
    assert "stock-snapshot-modes" in stock_snapshot_supplemental_sections_js
    assert "<polyline" in stock_snapshot_performance_helpers_js
    assert "styles/stock_snapshot_shell.css" in style_css
    assert "styles/stock_snapshot_overview.css" in style_css
    assert "styles/stock_snapshot_overview_trend.css" in style_css
    assert "styles/stock_snapshot_overview_performance.css" in style_css
    assert "styles/stock_snapshot_overview_technical.css" in style_css
    assert "styles/stock_snapshot_research.css" in style_css
    assert "styles/stock_snapshot_research_analyst.css" in style_css
    assert "styles/stock_snapshot_signal.css" in style_css
    assert "styles/stock_snapshot_signal_dividend.css" in style_css
    assert "styles/stock_snapshot_signal_events.css" in style_css
    assert "styles/stock_snapshot_core.css" in style_css
    assert "styles/stock_snapshot_core_peer_ownership.css" in style_css
    assert "styles/stock_snapshot_supplemental.css" in style_css
    assert "styles/stock_snapshot_responsive_headers.css" in style_css
    assert "styles/stock_snapshot_responsive.css" in style_css
    assert "styles/stock_snapshot_responsive_mobile.css" in style_css
    assert "/static/styles/stock_snapshot.css?v=" not in style_css
    assert style_css.index("styles/stock_snapshot_shell.css") < style_css.index("styles/stock_snapshot_overview.css")
    assert style_css.index("styles/stock_snapshot_overview.css") < style_css.index("styles/stock_snapshot_overview_trend.css")
    assert style_css.index("styles/stock_snapshot_overview_trend.css") < style_css.index("styles/stock_snapshot_overview_performance.css")
    assert style_css.index("styles/stock_snapshot_overview_performance.css") < style_css.index("styles/stock_snapshot_overview_technical.css")
    assert style_css.index("styles/stock_snapshot_overview_technical.css") < style_css.index("styles/stock_snapshot_research.css")
    assert style_css.index("styles/stock_snapshot_research.css") < style_css.index("styles/stock_snapshot_research_analyst.css")
    assert style_css.index("styles/stock_snapshot_research_analyst.css") < style_css.index("styles/stock_snapshot_signal.css")
    assert style_css.index("styles/stock_snapshot_signal.css") < style_css.index("styles/stock_snapshot_signal_dividend.css")
    assert style_css.index("styles/stock_snapshot_signal_dividend.css") < style_css.index("styles/stock_snapshot_signal_events.css")
    assert style_css.index("styles/stock_snapshot_signal_events.css") < style_css.index("styles/stock_snapshot_core.css")
    assert style_css.index("styles/stock_snapshot_core.css") < style_css.index("styles/stock_snapshot_core_peer_ownership.css")
    assert style_css.index("styles/stock_snapshot_core_peer_ownership.css") < style_css.index("styles/stock_snapshot_supplemental.css")
    assert style_css.index("styles/stock_snapshot_supplemental.css") < style_css.index("styles/stock_snapshot_responsive_headers.css")
    assert style_css.index("styles/stock_snapshot_responsive_headers.css") < style_css.index("styles/stock_snapshot_responsive.css")
    assert style_css.index("styles/stock_snapshot_responsive.css") < style_css.index("styles/stock_snapshot_responsive_mobile.css")
    assert ".stock-snapshot-panel" in stock_snapshot_shell_css
    assert ".stock-snapshot-shortcuts" in stock_snapshot_shell_css
    assert ".stock-snapshot-summary-rail" in stock_snapshot_shell_css
    assert ".stock-snapshot-actions-row" in stock_snapshot_shell_css
    assert ".stock-snapshot-summary-rail {\n    display: grid;" in stock_snapshot_shell_css
    assert ".stock-snapshot-panel {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-summary-rail {\n    display: grid;" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-grid {" in stock_snapshot_supplemental_css
    assert ".stock-snapshot-metric {" in stock_snapshot_supplemental_css
    assert ".stock-snapshot-strip" in stock_snapshot_supplemental_css
    assert ".stock-snapshot-news" in stock_snapshot_supplemental_css
    assert ".stock-snapshot-modes" in stock_snapshot_supplemental_css
    assert ".stock-snapshot-error {" in stock_snapshot_supplemental_css
    assert ".stock-snapshot-company-profile {" in stock_snapshot_overview_css
    assert ".stock-snapshot-company-profile-grid {" in stock_snapshot_overview_css
    assert ".stock-snapshot-session {" in stock_snapshot_overview_css
    assert ".stock-snapshot-session-grid {" in stock_snapshot_overview_css
    assert ".stock-snapshot-trend {" not in stock_snapshot_overview_css
    assert ".stock-snapshot-trend-chart {" not in stock_snapshot_overview_css
    assert ".stock-snapshot-trend {" in stock_snapshot_overview_trend_css
    assert ".stock-snapshot-trend-chart {" in stock_snapshot_overview_trend_css
    assert ".stock-snapshot-trend-returns {" in stock_snapshot_overview_trend_css
    assert ".stock-snapshot-company-profile {" not in stock_snapshot_overview_trend_css
    assert ".stock-snapshot-session {" not in stock_snapshot_overview_trend_css
    assert ".stock-snapshot-performance {" not in stock_snapshot_overview_css
    assert ".stock-snapshot-performance {" in stock_snapshot_overview_performance_css
    assert ".stock-snapshot-performance-controls {" in stock_snapshot_overview_performance_css
    assert ".stock-snapshot-performance-chart {" in stock_snapshot_overview_performance_css
    assert ".stock-snapshot-technical {" not in stock_snapshot_overview_css
    assert ".stock-snapshot-technical-grid {" not in stock_snapshot_overview_css
    assert ".stock-snapshot-company-profile {" not in stock_snapshot_overview_technical_css
    assert ".stock-snapshot-session {" not in stock_snapshot_overview_technical_css
    assert ".stock-snapshot-trend {" not in stock_snapshot_overview_technical_css
    assert ".stock-snapshot-technical {" in stock_snapshot_overview_technical_css
    assert ".stock-snapshot-technical-grid {" in stock_snapshot_overview_technical_css
    assert ".stock-snapshot-company-profile {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-session {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-trend {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-performance {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-technical {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-valuation-range {" in stock_snapshot_research_css
    assert ".stock-snapshot-valuation-band {" in stock_snapshot_research_css
    assert ".stock-snapshot-analyst {" not in stock_snapshot_research_css
    assert ".stock-snapshot-analyst-grid {" not in stock_snapshot_research_css
    assert ".stock-snapshot-earnings {" in stock_snapshot_research_css
    assert ".stock-snapshot-earnings-grid {" in stock_snapshot_research_css
    assert ".stock-snapshot-analyst {" in stock_snapshot_research_analyst_css
    assert ".stock-snapshot-analyst-grid {" in stock_snapshot_research_analyst_css
    assert ".stock-snapshot-valuation-range {" not in stock_snapshot_research_analyst_css
    assert ".stock-snapshot-earnings {" not in stock_snapshot_research_analyst_css
    assert ".stock-snapshot-valuation-range {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-valuation-band {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-analyst {\n    border:" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-earnings {\n    border:" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-shares {" in stock_snapshot_signal_css
    assert ".stock-snapshot-shares-grid {" in stock_snapshot_signal_css
    assert ".stock-snapshot-risk {" in stock_snapshot_signal_css
    assert ".stock-snapshot-risk-grid {" in stock_snapshot_signal_css
    assert ".stock-snapshot-profitability {" in stock_snapshot_signal_css
    assert ".stock-snapshot-profitability-grid {" in stock_snapshot_signal_css
    assert ".stock-snapshot-dividend {" not in stock_snapshot_signal_css
    assert ".stock-snapshot-dividend-bars {" not in stock_snapshot_signal_css
    assert ".stock-snapshot-shares {" not in stock_snapshot_signal_dividend_css
    assert ".stock-snapshot-risk {" not in stock_snapshot_signal_dividend_css
    assert ".stock-snapshot-profitability {" not in stock_snapshot_signal_dividend_css
    assert ".stock-snapshot-dividend {" in stock_snapshot_signal_dividend_css
    assert ".stock-snapshot-dividend-bars {" in stock_snapshot_signal_dividend_css
    assert ".stock-snapshot-calendar {" not in stock_snapshot_signal_css
    assert ".stock-snapshot-calendar {" in stock_snapshot_signal_events_css
    assert ".stock-snapshot-calendar-grid {" in stock_snapshot_signal_events_css
    assert ".stock-snapshot-alerts {" not in stock_snapshot_signal_css
    assert ".stock-snapshot-alerts {" in stock_snapshot_signal_events_css
    assert ".stock-snapshot-alert-grid {" in stock_snapshot_signal_events_css
    assert ".stock-snapshot-shares {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-risk {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-profitability {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-dividend {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-calendar {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-alerts {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-fundamentals {" in stock_snapshot_core_css
    assert ".stock-snapshot-fundamental-grid {" in stock_snapshot_core_css
    assert ".stock-snapshot-financial-trends {" in stock_snapshot_core_css
    assert ".stock-snapshot-financial-trend-row {" in stock_snapshot_core_css
    assert ".stock-snapshot-peers {" not in stock_snapshot_core_css
    assert ".stock-snapshot-peer-table {" not in stock_snapshot_core_css
    assert ".stock-snapshot-ownership {" not in stock_snapshot_core_css
    assert ".stock-snapshot-ownership-grid {" not in stock_snapshot_core_css
    assert ".stock-snapshot-fundamentals {" not in stock_snapshot_core_peer_ownership_css
    assert ".stock-snapshot-financial-trends {" not in stock_snapshot_core_peer_ownership_css
    assert ".stock-snapshot-peers {" in stock_snapshot_core_peer_ownership_css
    assert ".stock-snapshot-peer-table {" in stock_snapshot_core_peer_ownership_css
    assert ".stock-snapshot-ownership {" in stock_snapshot_core_peer_ownership_css
    assert ".stock-snapshot-ownership-grid {" in stock_snapshot_core_peer_ownership_css
    assert ".stock-snapshot-fundamentals {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-financial-trends {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-peers {" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-ownership {" not in stock_snapshot_supplemental_css
    assert "@media (max-width: 760px)" in stock_snapshot_responsive_css
    assert "@media (max-width: 520px)" not in stock_snapshot_responsive_css
    assert ".stock-snapshot-header," not in stock_snapshot_responsive_css
    assert ".stock-snapshot-grid {" in stock_snapshot_responsive_css
    assert ".stock-snapshot-summary-rail {" in stock_snapshot_responsive_css
    assert ".stock-snapshot-peer-row {" in stock_snapshot_responsive_css
    assert ".stock-snapshot-peer-table {" not in stock_snapshot_responsive_css
    assert ".stock-snapshot-financial-trend-row {" not in stock_snapshot_responsive_css
    assert "@media (max-width: 760px)" in stock_snapshot_responsive_headers_css
    assert "@media (max-width: 520px)" not in stock_snapshot_responsive_headers_css
    assert ".stock-snapshot-header," in stock_snapshot_responsive_headers_css
    assert ".stock-snapshot-company-profile-header," in stock_snapshot_responsive_headers_css
    assert ".stock-snapshot-alert-header {" in stock_snapshot_responsive_headers_css
    assert ".stock-snapshot-grid {" not in stock_snapshot_responsive_headers_css
    assert "@media (max-width: 760px)" not in stock_snapshot_responsive_mobile_css
    assert "@media (max-width: 520px)" in stock_snapshot_responsive_mobile_css
    assert ".stock-snapshot-peer-table {" in stock_snapshot_responsive_mobile_css
    assert ".stock-snapshot-financial-trend-row {" in stock_snapshot_responsive_mobile_css
    assert ".stock-snapshot-valuation-bands" in stock_snapshot_responsive_mobile_css
    assert "@media (max-width: 760px)" not in stock_snapshot_supplemental_css
    assert "@media (max-width: 520px)" not in stock_snapshot_supplemental_css
    assert ".stock-snapshot-valuation-range" in stock_snapshot_research_css
    assert ".stock-snapshot-valuation-band" in stock_snapshot_research_css


def test_stock_snapshot_format_helpers_format_labels_and_range_chart():
    stock_snapshot_format_helpers_path = STATIC_DIR / "stock_snapshot_format_helpers.js"
    stock_snapshot_helpers_path = STATIC_DIR / "stock_snapshot_helpers.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
const methods = window.StockAgentStockSnapshotHelpers.panelMethods;
const numericMethods = window.StockAgentStockSnapshotNumericFormatHelpers.numericMethods;
const formatMethods = window.StockAgentStockSnapshotFormatHelpers.panelMethods;
const performanceMethods = window.StockAgentStockSnapshotPerformanceHelpers.performanceMethods;
const ctx = Object.assign({ escapeHtml: value => String(value ?? '') }, methods);
const chart = ctx.performanceRangeChart({
  key: '1y',
  label: '1Y',
  return_pct: 35.71,
  start_price: 700,
  end_price: 950,
  points: [
    { date: '2025-07-31', price: 700 },
    { date: '2026-07-31', price: 950 }
  ]
});
process.stdout.write(JSON.stringify({
  normalizedPrice: ctx.priceLabel(1234.567),
  positiveReturn: ctx.returnLabel(3.26),
  negativeDelta: ctx.percentDeltaLabel(-4.44),
  pointDelta: ctx.pointDeltaLabel(1.25),
  compact: ctx.compact(125000000),
  timingFuture: ctx.eventTimingLabel({ days_until: 3 }),
  timingPast: ctx.eventTimingLabel({ days_until: -2 }),
  flowBuy: ctx.flowWord(10),
  numericPrice: numericMethods.priceLabel(1234.567),
  formatPrice: formatMethods.priceLabel(1234.567),
  performancePoints: performanceMethods.sparklinePoints([{ price: 700 }, { price: 950 }], 140, 52),
  chart
}));
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(stock_snapshot_format_helpers_path))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(stock_snapshot_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["normalizedPrice"] == "1,234.57"
    assert payload["positiveReturn"] == "+3.3%"
    assert payload["negativeDelta"] == "-4.4%"
    assert payload["pointDelta"] == "+1.3pp"
    assert payload["compact"] == "1.3億"
    assert payload["timingFuture"] == "3 天後"
    assert payload["timingPast"] == "2 天前"
    assert payload["flowBuy"] == "買超"
    assert payload["numericPrice"] == "1,234.57"
    assert payload["formatPrice"] == "1,234.57"
    assert payload["performancePoints"] == "0.0,48.0 140.0,4.0"
    assert "<polyline" in payload["chart"]
    assert "+35.7%" in payload["chart"]


def test_stock_snapshot_interaction_helpers_select_performance_range():
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
const helper = window.StockAgentStockSnapshotHelpers;
const interaction = window.StockAgentStockSnapshotInteractionHelpers;
const toggles = [];
const buttons = ['1m', '1y'].map(key => ({
  dataset: { stockSnapshotRange: key },
  classList: { toggle: (className, active) => toggles.push(`${key}:${className}:${active}`) }
}));
const chart = { innerHTML: '' };
const root = {
  querySelector: selector => selector === '[data-stock-snapshot-performance-chart]' ? chart : null,
  querySelectorAll: selector => selector === '[data-stock-snapshot-range]' ? buttons : []
};
const ctx = Object.assign({
  escapeHtml: value => String(value ?? ''),
  elements: { root },
  lastSnapshot: {
    performance_history: {
      ranges: [{
        key: '1m',
        label: '1M',
        return_pct: 3.21,
        start_price: 900,
        end_price: 929,
        points: [{ date: '2026-06-01', price: 900 }, { date: '2026-07-01', price: 929 }]
      }, {
        key: '1y',
        label: '1Y',
        return_pct: 35.71,
        start_price: 700,
        end_price: 950,
        points: [{ date: '2025-07-01', price: 700 }, { date: '2026-07-01', price: 950 }]
      }]
    }
  }
}, helper.panelMethods, interaction.interactionMethods);
ctx.selectPerformanceRange('1y');
const chartAfterKnownRange = chart.innerHTML;
ctx.selectPerformanceRange('missing');
process.stdout.write(JSON.stringify({ chartAfterKnownRange, chartAfterMissingRange: chart.innerHTML, toggles }));
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "<polyline" in payload["chartAfterKnownRange"]
    assert "+35.7%" in payload["chartAfterKnownRange"]
    assert payload["chartAfterMissingRange"] == payload["chartAfterKnownRange"]
    assert payload["toggles"] == ["1m:is-active:false", "1y:is-active:true"]


def test_stock_snapshot_render_helpers_compose_sections_in_order():
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
const render = window.StockAgentStockSnapshotRenderHelpers;
const root = { hidden: true, innerHTML: '' };
const calls = [];
const names = [
  'renderHeader',
  'renderSummaryRail',
  'renderCompanyProfile',
  'renderMarketSession',
  'renderTrend',
  'renderPerformanceHistory',
  'renderTechnicalSummary',
  'renderValuationRange',
  'renderAnalystOutlook',
  'renderEarningsForecast',
  'renderShareStatistics',
  'renderRiskLiquidity',
  'renderProfitabilityQuality',
  'renderDividendProfile',
  'renderEventCalendar',
  'renderAlertSuggestions',
  'renderFinancialHealth',
  'renderFinancialTrends',
  'renderPeerComparison',
  'renderOwnershipFlow',
  'renderGrid',
  'renderEvents',
  'renderNews',
  'renderModes'
];
const ctx = Object.assign({ elements: { root } }, render.renderMethods);
names.forEach(name => {
  ctx[name] = snapshot => {
    calls.push(`${name}:${snapshot.ticker}`);
    return `<section>${name}</section>`;
  };
});
ctx.render({ ticker: '2330.TW' });
const missingRootCtx = Object.assign({ elements: {} }, render.renderMethods);
missingRootCtx.render({ ticker: 'TSM' });
process.stdout.write(JSON.stringify({
  hidden: root.hidden,
  lastTicker: ctx.lastSnapshot.ticker,
  html: root.innerHTML,
  calls,
  missingLastSnapshot: missingRootCtx.lastSnapshot || null
}));
""".replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["hidden"] is False
    assert payload["lastTicker"] == "2330.TW"
    assert payload["html"].startswith("<section>renderHeader</section><section>renderSummaryRail</section>")
    assert payload["html"].endswith("<section>renderNews</section><section>renderModes</section>")
    assert payload["calls"][0] == "renderHeader:2330.TW"
    assert payload["calls"][-1] == "renderModes:2330.TW"
    assert payload["missingLastSnapshot"] is None


def test_stock_snapshot_event_helpers_bind_panel_actions():
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
const event = window.StockAgentStockSnapshotEventHelpers;
function listenerTarget() {
  const listeners = {};
  return { listeners, addEventListener: (type, handler) => { listeners[type] = handler; } };
}
function eventFor(selector, dataset) {
  return { target: { closest: asked => asked === selector ? { dataset } : null } };
}
const calls = [];
const loadButton = listenerTarget();
const tickerInput = listenerTarget();
const shortcutsRoot = listenerTarget();
const root = listenerTarget();
const ctx = Object.assign({
  elements: { loadButton, tickerInput, shortcutsRoot, root },
  loadFromInput: () => calls.push('load-input'),
  normalizeTickerInput: value => value ? `N:${value}` : '',
  setTickerInput: ticker => calls.push(`set:${ticker}`),
  load: ticker => calls.push(`load:${ticker}`),
  renderShortcuts: () => calls.push('shortcuts'),
  addToWatchlist: ticker => calls.push(`watch:${ticker}`),
  applyAlertSuggestion: index => calls.push(`alert:${index}:${typeof index}`),
  selectPerformanceRange: range => calls.push(`range:${range}`),
  onSelectPipeline: pipeline => calls.push(`pipe:${pipeline}`)
}, event.eventMethods);
ctx.bindEvents();
loadButton.listeners.click();
tickerInput.listeners.keydown({
  key: 'Enter',
  preventDefault: () => calls.push('prevent'),
  stopPropagation: () => calls.push('stop'),
  stopImmediatePropagation: () => calls.push('stop-immediate')
});
tickerInput.listeners.keydown({ key: 'Enter', ctrlKey: true });
shortcutsRoot.listeners.click(eventFor('[data-stock-snapshot-shortcut]', { stockSnapshotShortcut: '2330' }));
root.listeners.click(eventFor('[data-stock-snapshot-watchlist]', { stockSnapshotWatchlist: 'TSM' }));
root.listeners.click(eventFor('[data-stock-snapshot-alert]', { stockSnapshotAlert: '2' }));
root.listeners.click(eventFor('[data-stock-snapshot-range]', { stockSnapshotRange: '1y' }));
root.listeners.click(eventFor('[data-stock-snapshot-pipeline]', { stockSnapshotPipeline: 'v4' }));
process.stdout.write(JSON.stringify({ calls, bound: Object.keys(loadButton.listeners).concat(Object.keys(tickerInput.listeners), Object.keys(shortcutsRoot.listeners), Object.keys(root.listeners)) }));
""".replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["bound"] == ["click", "keydown", "click", "click"]
    assert payload["calls"] == [
        "shortcuts",
        "load-input",
        "prevent",
        "stop",
        "stop-immediate",
        "load-input",
        "set:N:2330",
        "load:N:2330",
        "watch:TSM",
        "alert:2:number",
        "range:1y",
        "pipe:v4",
    ]


def test_stock_snapshot_helpers_render_fragment_rows():
    stock_snapshot_format_helpers_path = STATIC_DIR / "stock_snapshot_format_helpers.js"
    stock_snapshot_helpers_path = STATIC_DIR / "stock_snapshot_helpers.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
const helper = window.StockAgentStockSnapshotHelpers;
const ctx = Object.assign({ escapeHtml: value => String(value ?? '') }, helper.panelMethods, helper.fragmentMethods);
const metric = ctx.metric('現價', '950', '52週 700 / 980');
const trendRow = ctx.financialTrendRow({
  period: '2026Q2',
  revenue: 20.5,
  revenue_yoy_pct: 12.34,
  net_income: 8.1,
  net_income_yoy_pct: -2.1,
  free_cash_flow: 6.2,
  free_cash_flow_yoy_pct: 4.4,
  gross_margin_pct: 55.5,
  operating_margin_pct: 45.2
});
const bars = ctx.dividendBars({ years: [2024, 2025], dividends: [3, 6] });
const peer = ctx.peerRow({ name: '台積電', ticker: '2330.TW', gross_margin_pct: 55.5, roe_pct: 28.2, pe_ttm: 22.4, ps_ttm: 8.9, is_target: true });
const balance = ctx.balanceDetail({ debt_label: '100B', debt_to_equity_label: '35%' });
process.stdout.write(JSON.stringify({ metric, trendRow, bars, peer, balance }));
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(stock_snapshot_format_helpers_path))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(stock_snapshot_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "stock-snapshot-metric" in payload["metric"]
    assert "52週 700 / 980" in payload["metric"]
    assert "stock-snapshot-financial-trend-row" in payload["trendRow"]
    assert "+12.3%" in payload["trendRow"]
    assert "-2.1%" in payload["trendRow"]
    assert "stock-snapshot-dividend-bars" in payload["bars"]
    assert "height:54px" in payload["bars"]
    assert "stock-snapshot-peer-row is-target" in payload["peer"]
    assert "台積電 · 2330.TW" in payload["peer"]
    assert payload["balance"] == "負債 100B · D/E 35%"


def test_stock_snapshot_input_helpers_normalize_recent_and_render_shortcuts():
    script = """
let stored = '["2330","aapl","2330.TW",""]';
global.window = {
  localStorage: {
    getItem: key => key === 'stockAgent.stockSnapshot.recentTickers' ? stored : null,
    setItem: (key, value) => { if (key === 'stockAgent.stockSnapshot.recentTickers') stored = value; }
  }
};
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
const input = window.StockAgentStockSnapshotInputHelpers;
const shortcutsRoot = { innerHTML: '' };
const tickerInput = { value: '' };
const ctx = Object.assign({
  escapeHtml: value => String(value ?? ''),
  elements: { shortcutsRoot, tickerInput },
  defaultShortcuts: ['2330.TW', '2317.TW', 'AAPL', 'nvda']
}, input.inputMethods);
ctx.renderShortcuts();
ctx.rememberTicker('2454');
ctx.setTickerInput('NVDA');
process.stdout.write(JSON.stringify({
  normalizedTaiwanTicker: ctx.normalizeTickerInput('2330'),
  normalizedWhitespaceTicker: ctx.normalizeTickerInput(' brk b '),
  recent: ctx.getRecentTickers(),
  shortcutsHtml: shortcutsRoot.innerHTML,
  stored,
  inputValue: tickerInput.value
}));
""".replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["normalizedTaiwanTicker"] == "2330.TW"
    assert payload["normalizedWhitespaceTicker"] == "BRKB"
    assert payload["recent"] == ["2454.TW", "2330.TW", "AAPL"]
    assert "data-stock-snapshot-shortcut=\"2330.TW\"" in payload["shortcutsHtml"]
    assert "data-stock-snapshot-shortcut=\"2317.TW\"" in payload["shortcutsHtml"]
    assert "data-stock-snapshot-shortcut=\"NVDA\"" in payload["shortcutsHtml"]
    assert "常用" in payload["shortcutsHtml"]
    assert json.loads(payload["stored"])[0] == "2454.TW"
    assert payload["inputValue"] == "NVDA"


def test_stock_snapshot_load_helpers_manage_fetch_loading_and_errors():
    script = """
global.window = {
  localStorage: {
    value: '[]',
    getItem: () => window.localStorage.value,
    setItem: (_key, value) => { window.localStorage.value = value; }
  }
};
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
const input = window.StockAgentStockSnapshotInputHelpers;
const load = window.StockAgentStockSnapshotLoadHelpers;
const label = { textContent: '股票快照' };
const loadButton = { disabled: false, querySelector: () => label };
const tickerInput = { value: ' 2330 ' };
const fetchCalls = [];
const renderCalls = [];
const renderErrors = [];
const notifyErrors = [];
let shortcutCount = 0;
const ctx = Object.assign({
  apiClient: {
    fetchStockSnapshot: async ticker => {
      fetchCalls.push(ticker);
      if (ticker === 'FAIL') throw new Error('quote unavailable');
      return { ticker, quote: { price: 1000 } };
    }
  },
  notify: { error: message => notifyErrors.push(message) },
  elements: { tickerInput, loadButton },
  defaultShortcuts: [],
  escapeHtml: value => String(value ?? '')
}, input.inputMethods, {
  renderShortcuts: () => { shortcutCount += 1; },
  render: snapshot => renderCalls.push(snapshot.ticker),
  renderError: err => renderErrors.push(err.message || String(err))
}, load.loadMethods);
Promise.resolve()
  .then(() => ctx.loadFromInput())
  .then(() => {
    tickerInput.value = '';
    return ctx.loadFromInput();
  })
  .then(() => ctx.load(' fail '))
  .then(() => {
    process.stdout.write(JSON.stringify({
      fetchCalls,
      renderCalls,
      renderErrors,
      notifyErrors,
      shortcutCount,
      currentTicker: ctx.currentTicker,
      inputValue: tickerInput.value,
      buttonDisabled: loadButton.disabled,
      buttonLabel: label.textContent,
      stored: window.localStorage.value
    }));
  });
""".replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["fetchCalls"] == ["2330.TW", "FAIL"]
    assert payload["renderCalls"] == ["2330.TW"]
    assert payload["renderErrors"] == ["quote unavailable"]
    assert payload["notifyErrors"] == ["請輸入股票代號。"]
    assert payload["shortcutCount"] == 1
    assert payload["currentTicker"] == "FAIL"
    assert payload["inputValue"] == "FAIL"
    assert payload["buttonDisabled"] is False
    assert payload["buttonLabel"] == "股票快照"
    assert json.loads(payload["stored"]) == ["2330.TW"]


def test_stock_snapshot_action_helpers_save_watchlist_and_alert_suggestions():
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
const action = window.StockAgentStockSnapshotActionHelpers;
const savedItems = [];
const successMessages = [];
let updateCount = 0;
const watchlistLabel = { textContent: '加入追蹤' };
const watchlistButton = { disabled: false, querySelector: () => watchlistLabel };
const alertButton = { disabled: false };
const root = {
  querySelectorAll: selector => {
    if (selector === '[data-stock-snapshot-watchlist]') return [watchlistButton];
    if (selector === '[data-stock-snapshot-alert]') return [alertButton];
    return [];
  }
};
const ctx = Object.assign({
  apiClient: {
    saveWatchlistItem: async item => {
      savedItems.push(item);
      return {};
    }
  },
  notify: {
    success: message => successMessages.push(message),
    error: message => successMessages.push(`ERROR:${message}`)
  },
  onWatchlistUpdated: async () => { updateCount += 1; },
  getSelectedPipeline: () => '',
  elements: { root },
  currentTicker: 'TSM',
  lastSnapshot: {
    ticker: 'TSM',
    mode_suggestions: [{ pipeline_id: 'v4' }],
    alert_suggestions: {
      suggestions: [{
        label: '突破提醒',
        pipeline: 'v2',
        schedule_slots: ['close'],
        triggers: [{ field: 'price', op: '>=', value: 200 }]
      }]
    }
  }
}, action.actionMethods);
Promise.resolve()
  .then(() => ctx.addToWatchlist('tsm'))
  .then(() => ctx.applyAlertSuggestion(0))
  .then(() => {
    process.stdout.write(JSON.stringify({
      savedItems,
      successMessages,
      updateCount,
      watchlistDisabled: watchlistButton.disabled,
      watchlistLabel: watchlistLabel.textContent,
      alertDisabled: alertButton.disabled
    }));
  });
""".replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["savedItems"][0] == {
        "ticker": "TSM",
        "pipeline": "v4",
        "enabled": True,
        "schedule_slots": ["pre_market"],
        "triggers": [],
    }
    assert payload["savedItems"][1] == {
        "ticker": "TSM",
        "pipeline": "v2",
        "enabled": True,
        "schedule_slots": ["close"],
        "triggers": [{"field": "price", "op": ">=", "value": 200}],
        "trigger_source": "stock_snapshot_suggestion",
    }
    assert payload["successMessages"] == ["TSM 已加入追蹤清單。", "TSM 已套用「突破提醒」。"]
    assert payload["updateCount"] == 2
    assert payload["watchlistDisabled"] is False
    assert payload["watchlistLabel"] == "加入追蹤"
    assert payload["alertDisabled"] is False


def test_stock_snapshot_summary_helpers_render_header_rail_and_error():
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
const helper = window.StockAgentStockSnapshotHelpers;
const summary = window.StockAgentStockSnapshotSummaryHelpers;
const root = { hidden: true, innerHTML: '' };
const ctx = Object.assign({
  escapeHtml: value => String(value ?? ''),
  currentTicker: 'TSM',
  elements: { root }
}, helper.panelMethods, summary.summaryMethods);
const snapshot = {
  ticker: 'TSM',
  identity: { company_name: 'Taiwan Semi', sector: 'Technology', industry: 'Semiconductors' },
  data_quality: { status: 'ok', score: 87.4 },
  market_session: { current_price: 1000, change_pct: 1.25, direction: 'positive' },
  quote: {},
  valuation_range: { label: '合理區間', price_vs_mid_pct: -4.4 },
  analyst_outlook: { label: '偏多', target: { upside_pct: 8.2 } },
  profitability_quality: { label: '高品質', signals: ['毛利率穩定'] },
  event_calendar: { next_event: { label: '法說會', date_label: '2026-07-20', days_until: 11 } }
};
const header = ctx.renderHeader(snapshot);
const rail = ctx.renderSummaryRail(snapshot);
ctx.renderError(new Error('quote unavailable'));
process.stdout.write(JSON.stringify({ header, rail, errorHtml: root.innerHTML, hidden: root.hidden }));
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "stock-snapshot-header" in payload["header"]
    assert "TSM Taiwan Semi" in payload["header"]
    assert "Technology · Semiconductors" in payload["header"]
    assert "data-stock-snapshot-watchlist=\"TSM\"" in payload["header"]
    assert "ok · 87分" in payload["header"]
    assert "stock-snapshot-summary-rail" in payload["rail"]
    assert "現價" in payload["rail"]
    assert "1,000" in payload["rail"]
    assert "+1.3%" in payload["rail"]
    assert "合理區間" in payload["rail"]
    assert "-4.4%" in payload["rail"]
    assert "法說會" in payload["rail"]
    assert payload["hidden"] is False
    assert "股票快照讀取失敗" in payload["errorHtml"]
    assert "quote unavailable" in payload["errorHtml"]


def test_stock_snapshot_sections_render_financial_peer_and_ownership_sections():
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
const helper = window.StockAgentStockSnapshotHelpers;
const sections = window.StockAgentStockSnapshotSections;
const ctx = Object.assign({ escapeHtml: value => String(value ?? '') }, helper.panelMethods, helper.fragmentMethods, sections.sectionMethods);
const financialHealth = ctx.renderFinancialHealth({
  financial_health: {
    revenue_ttm: { label: 'NT$25,000.00億' },
    revenue_growth: { label: '18.4%' },
    gross_margin: { label: '56.0%' },
    profit_margin: { label: '38.0%' },
    free_cash_flow: { label: 'NT$8,500.00億' },
    balance_sheet: { cash_label: 'NT$19,000.00億', debt_label: 'NT$9,000.00億', debt_to_equity_label: '28.0%' },
    highlights: ['營收成長']
  }
});
const financialTrends = ctx.renderFinancialTrends({
  financial_trends: {
    status: 'available',
    label: '營收與獲利成長',
    rows: [
      { period: '2026', revenue: 3200, revenue_yoy_pct: 28, net_income: 1100, net_income_yoy_pct: 22.2, free_cash_flow: 900, free_cash_flow_yoy_pct: 5.9, gross_margin_pct: 57, operating_margin_pct: 46 }
    ]
  }
});
const peers = ctx.renderPeerComparison({
  peer_comparison: {
    summary: { valuation_label: '接近同業', pe_vs_peer_median_pct: 2.3, gross_margin_spread_pct: 18 },
    target: { ticker: '2330.TW', name: '台積電', is_target: true, gross_margin_pct: 56, roe_pct: 30, pe_ttm: 22.5, ps_ttm: 9.1 },
    peers: [{ ticker: '2303.TW', name: '聯電', gross_margin_pct: 36, roe_pct: 17.5, pe_ttm: 14, ps_ttm: 3 }]
  }
});
const ownership = ctx.renderOwnershipFlow({
  ownership_flow: {
    status: 'available',
    label: '法人買超',
    institutional: { categories: [{ label: '外資', net_buy_thousand_shares: 1200 }] },
    margin: { margin_balance: 12000, short_balance: 350 },
    holders: { major_holders_gt_1000_lots_pct: 78.5, retail_holders_lt_50_lots_pct: 12.3 },
    signals: ['近30日法人合計買超 2,500張']
  }
});
process.stdout.write(JSON.stringify({ financialHealth, financialTrends, peers, ownership }));
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "stock-snapshot-fundamentals" in payload["financialHealth"]
    assert "財務健康摘要" in payload["financialHealth"]
    assert "stock-snapshot-financial-trend-row" in payload["financialTrends"]
    assert "stock-snapshot-peer-row is-target" in payload["peers"]
    assert "P/E vs 同業中位" in payload["peers"]
    assert "stock-snapshot-ownership" in payload["ownership"]
    assert "買超" in payload["ownership"]


def test_stock_snapshot_overview_sections_render_profile_market_trend_and_technical_sections():
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
const helper = window.StockAgentStockSnapshotHelpers;
const overview = window.StockAgentStockSnapshotOverviewSections;
const ctx = Object.assign({ escapeHtml: value => String(value ?? '') }, helper.panelMethods, helper.fragmentMethods, overview.overviewSectionMethods);
const profile = ctx.renderCompanyProfile({
  company_profile: {
    status: 'available',
    label: '公司檔案',
    summary: '台積電提供晶圓代工與先進封裝服務，服務全球無晶圓廠客戶。',
    website: 'https://www.tsmc.com',
    facts: [{ label: '產業', value: 'Technology / Semiconductors' }]
  }
});
const session = ctx.renderMarketSession({
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
    volume_vs_avg_pct: 30
  }
});
const trend = ctx.renderTrend({
  price_trend: {
    label: '近一年月收盤',
    latest_price: 950,
    returns: { '1m': 3.26, '3m': 7.95, '1y': 35.71 },
    sparkline: [{ date: '2025-08-31', price: 700 }, { date: '2026-07-31', price: 950 }]
  }
});
const performance = ctx.renderPerformanceHistory({
  performance_history: {
    status: 'available',
    label: '多週期走勢',
    default_range: '1y',
    ranges: [
      { key: '1m', label: '1M', return_pct: 3.26, points: [{ date: '2026-06-30', price: 920 }, { date: '2026-07-31', price: 950 }] },
      { key: '1y', label: '1Y', return_pct: 35.71, points: [{ date: '2025-07-31', price: 700 }, { date: '2026-07-31', price: 950 }] }
    ]
  }
});
const technical = ctx.renderTechnicalSummary({
  technical_summary: {
    status: 'available',
    label: '技術摘要',
    moving_averages: { ma_3m: { value: 900, distance_pct: 5.56 }, ma_6m: { value: 860, distance_pct: 10.47 } },
    range_52w: { position_pct: 83.3, drawdown_from_high_pct: -3.1 },
    momentum: { '3m': 7.95, '1y': 35.71 },
    signals: ['站上均線']
  }
});
process.stdout.write(JSON.stringify({ profile, session, trend, performance, technical }));
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "stock-snapshot-company-profile" in payload["profile"]
    assert "官網" in payload["profile"]
    assert "stock-snapshot-session is-up" in payload["session"]
    assert "今日行情" in payload["session"]
    assert "stock-snapshot-trend" in payload["trend"]
    assert "<polyline" in payload["trend"]
    assert "stock-snapshot-performance" in payload["performance"]
    assert "data-stock-snapshot-range=\"1y\"" in payload["performance"]
    assert "stock-snapshot-technical" in payload["technical"]
    assert "站上均線" in payload["technical"]


def test_stock_snapshot_research_sections_render_valuation_analyst_and_earnings_sections():
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
const helper = window.StockAgentStockSnapshotHelpers;
const research = window.StockAgentStockSnapshotResearchSections;
const ctx = Object.assign({ escapeHtml: value => String(value ?? '') }, helper.panelMethods, helper.fragmentMethods, research.researchSectionMethods);
const valuation = ctx.renderValuationRange({
  valuation_range: {
    status: 'available',
    label: '合理區間',
    current_price: 950,
    mid_price: 1000,
    price_vs_mid_pct: -5,
    source: 'FinMind 5-year PER quantiles',
    bands: [
      { label: '15x', multiple: 15, price: 750 },
      { label: '20x', multiple: 20, price: 1000 }
    ]
  }
});
const analyst = ctx.renderAnalystOutlook({
  analyst_outlook: {
    status: 'available',
    label: '目標價上行',
    target: { price: 1050, label: 'NT$1050.00', upside_pct: 10.53 },
    consensus: { recommendation_label: '買進', analyst_count: 32 },
    valuation: { forward_pe: { label: '19.8x' } },
    growth: { earnings_growth: { label: '14.0%' } },
    signals: ['目標價上行 +10.5%']
  }
});
const earnings = ctx.renderEarningsForecast({
  earnings_forecast: {
    status: 'available',
    label: 'EPS 預期成長',
    trailing_eps: { label: '45.00' },
    forward_eps: { label: '50.00' },
    forward_eps_change_pct: 11.11,
    growth: { earnings_growth: { label: '14.0%' }, revenue_growth: { label: '18.4%' } },
    analyst_count: 32,
    next_earnings: { date: '2026-07-18', days_until: 13 },
    signals: ['Forward EPS +11.1%']
  }
});
process.stdout.write(JSON.stringify({ valuation, analyst, earnings }));
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "stock-snapshot-valuation-range" in payload["valuation"]
    assert "距中位 -5.0%" in payload["valuation"]
    assert "stock-snapshot-analyst" in payload["analyst"]
    assert "目標價上行" in payload["analyst"]
    assert "stock-snapshot-earnings" in payload["earnings"]
    assert "EPS 預期成長" in payload["earnings"]
    assert "32 位分析師" in payload["earnings"]


def test_stock_snapshot_signal_sections_render_share_risk_dividend_events_and_alerts():
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
const helper = window.StockAgentStockSnapshotHelpers;
const signals = window.StockAgentStockSnapshotSignalSections;
const ctx = Object.assign({ escapeHtml: value => String(value ?? '') }, helper.panelMethods, helper.fragmentMethods, signals.signalSectionMethods);
const shares = ctx.renderShareStatistics({
  share_statistics: {
    status: 'available',
    label: '股本集中',
    shares_outstanding: 1000000000,
    float_shares: 800000000,
    float_pct_of_shares: 80,
    institutional_ownership_pct: 62.5,
    insider_ownership_pct: 4.5,
    short_interest: { shares_short: 12000000, short_percent_of_float_pct: 1.5, short_ratio: 2.2 },
    signals: ['機構持股穩定']
  }
});
const risk = ctx.renderRiskLiquidity({
  risk_liquidity: {
    status: 'available',
    label: '低波動',
    beta: { label: '0.92' },
    drawdown_from_52w_high_pct: -4.2,
    volume_vs_avg_pct: 15.4,
    debt_to_equity_pct: 32.1,
    current_ratio: { label: '2.3x' },
    signals: ['流動性良好']
  }
});
const profitability = ctx.renderProfitabilityQuality({
  profitability_quality: {
    status: 'available',
    label: '高毛利',
    gross_margin_pct: 56.1,
    operating_margin_pct: 45.2,
    net_margin_pct: 38.6,
    roe_pct: 28.3,
    roa_pct: 17.4,
    fcf_margin_pct: 30.2,
    signals: ['FCF 穩定']
  }
});
const dividend = ctx.renderDividendProfile({
  dividend_profile: {
    status: 'available',
    label: '穩定配息',
    annual_dividend: { label: 'NT$12.00' },
    yield: { label: '1.8%' },
    payout_ratio: { label: '42%' },
    coverage: { fcf_coverage_ratio: 2.4 },
    history: { years: [2024, 2025], dividends: [10, 12] },
    signals: ['連續配息']
  }
});
const calendar = ctx.renderEventCalendar({
  event_calendar: {
    status: 'available',
    label: '近期事件',
    next_event: { days_until: 5 },
    events: [{ type: 'earnings', label: '法說會', date_label: '2026-07-18' }]
  }
});
const alerts = ctx.renderAlertSuggestions({
  alert_suggestions: {
    status: 'available',
    label: '建議提醒',
    suggestions: [{ label: '跌破支撐', detail: '低於 900 提醒', triggers: [{ field: 'price', op: '<', value: 900 }] }]
  }
});
process.stdout.write(JSON.stringify({ shares, risk, profitability, dividend, calendar, alerts }));
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "stock-snapshot-shares" in payload["shares"]
    assert "股本集中" in payload["shares"]
    assert "stock-snapshot-risk" in payload["risk"]
    assert "低波動" in payload["risk"]
    assert "stock-snapshot-profitability" in payload["profitability"]
    assert "高毛利" in payload["profitability"]
    assert "stock-snapshot-dividend" in payload["dividend"]
    assert "穩定配息" in payload["dividend"]
    assert "stock-snapshot-calendar" in payload["calendar"]
    assert "5 天後" in payload["calendar"]
    assert "stock-snapshot-alerts" in payload["alerts"]
    assert "data-stock-snapshot-alert=\"0\"" in payload["alerts"]


def test_stock_snapshot_supplemental_sections_render_grid_events_news_and_modes():
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
const helper = window.StockAgentStockSnapshotHelpers;
const supplemental = window.StockAgentStockSnapshotSupplementalSections;
const ctx = Object.assign({ escapeHtml: value => String(value ?? '') }, helper.panelMethods, helper.fragmentMethods, supplemental.supplementalSectionMethods);
const grid = ctx.renderGrid({
  quote: { price_label: '950.00', range_52w: { low: 700, high: 980 }, market_cap_label: 'NT$24.6兆', beta: 0.92, volume: 123000000 },
  valuation: { pe_ratio: { label: '22.5x' }, analyst_target: { label: 'NT$1050', upside_pct: 10.5 } },
  dividends: { yield_label: '1.8%', annual_dividend_label: '12.00' },
  chip: { institutional_summary: '外資買超', foreign_net_buy: 1200 }
});
const events = ctx.renderEvents({
  events: [{ type: 'earnings', label: '法說會' }]
});
const news = ctx.renderNews({
  news: [{ title: '先進製程需求升溫', source: '交易所', published_at: '2026-07-09' }]
});
const modes = ctx.renderModes({
  mode_suggestions: [{ pipeline_id: 'v4', label: '學術深度派', decision: '驗證長線 thesis' }]
});
process.stdout.write(JSON.stringify({ grid, events, news, modes }));
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "stock-snapshot-grid" in payload["grid"]
    assert "NT$24.6兆" in payload["grid"]
    assert "外資買超" in payload["grid"]
    assert "stock-snapshot-strip" in payload["events"]
    assert "法說會" in payload["events"]
    assert "stock-snapshot-news" in payload["news"]
    assert "先進製程需求升溫" in payload["news"]
    assert "stock-snapshot-modes" in payload["modes"]
    assert "data-stock-snapshot-pipeline=\"v4\"" in payload["modes"]


def test_stock_snapshot_panel_renders_price_trend_sparkline():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PANEL_PATH__);
const shortcutsRoot = { innerHTML: '', addEventListener: () => {} };
const panel = window.StockAgentStockSnapshotPanel.create({
  ui: { escapeHtml: value => String(value ?? '') },
  elements: { shortcutsRoot }
});
panel.bindEvents();
process.stdout.write(shortcutsRoot.innerHTML);
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    payload = json.loads(result.stdout)
    assert "5Y" in payload["html"]
    assert "+216.7%" in payload["html"]
    assert payload["active"] == [False, True]


def test_stock_snapshot_panel_renders_market_session_summary():
    stock_snapshot_path = STATIC_DIR / "stock_snapshot_panel.js"
    script = """
global.window = {};
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
require(__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__);
require(__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__);
require(__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__);
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
""".replace("__STOCK_SNAPSHOT_NUMERIC_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_numeric_format_helpers.js"))).replace("__STOCK_SNAPSHOT_DOMAIN_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_domain_format_helpers.js"))).replace("__STOCK_SNAPSHOT_PERFORMANCE_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_performance_helpers.js"))).replace("__STOCK_SNAPSHOT_FORMAT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_format_helpers.js"))).replace("__STOCK_SNAPSHOT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_helpers.js"))).replace("__STOCK_SNAPSHOT_INPUT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_input_helpers.js"))).replace("__STOCK_SNAPSHOT_LOAD_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_load_helpers.js"))).replace("__STOCK_SNAPSHOT_ACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_action_helpers.js"))).replace("__STOCK_SNAPSHOT_SUMMARY_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_summary_helpers.js"))).replace("__STOCK_SNAPSHOT_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_sections.js"))).replace("__STOCK_SNAPSHOT_OVERVIEW_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_overview_sections.js"))).replace("__STOCK_SNAPSHOT_RESEARCH_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_research_sections.js"))).replace("__STOCK_SNAPSHOT_SIGNAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_signal_sections.js"))).replace("__STOCK_SNAPSHOT_SUPPLEMENTAL_SECTIONS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_supplemental_sections.js"))).replace("__STOCK_SNAPSHOT_INTERACTION_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_interaction_helpers.js"))).replace("__STOCK_SNAPSHOT_RENDER_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_render_helpers.js"))).replace("__STOCK_SNAPSHOT_EVENT_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "stock_snapshot_event_helpers.js"))).replace("__STOCK_SNAPSHOT_PANEL_PATH__", json.dumps(str(stock_snapshot_path)))
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
    app_panels_js = (STATIC_DIR / "app_panels.js").read_text(encoding="utf-8")
    stock_snapshot_js = (STATIC_DIR / "stock_snapshot_panel.js").read_text(encoding="utf-8")
    stock_snapshot_action_helpers_js = (STATIC_DIR / "stock_snapshot_action_helpers.js").read_text(encoding="utf-8")
    stock_snapshot_summary_helpers_js = (STATIC_DIR / "stock_snapshot_summary_helpers.js").read_text(encoding="utf-8")
    stock_snapshot_shell_css = (STATIC_DIR / "styles" / "stock_snapshot_shell.css").read_text(encoding="utf-8")

    assert "data-stock-snapshot-watchlist" in stock_snapshot_summary_helpers_js
    assert "saveWatchlistItem" in stock_snapshot_action_helpers_js
    assert "加入追蹤" in stock_snapshot_action_helpers_js
    assert "onWatchlistUpdated" in stock_snapshot_js
    assert "stock-snapshot-actions-row" in stock_snapshot_summary_helpers_js
    assert "loadWatchlistOnce" in app_js
    assert "onWatchlistUpdated: opsWorkspace.loadWatchlistOnce" in app_panels_js
    assert ".stock-snapshot-actions-row" in stock_snapshot_shell_css


def test_watchlist_is_first_class_tracking_tab_for_consumers():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    app_panels_js = (STATIC_DIR / "app_panels.js").read_text(encoding="utf-8")
    ops_workspace_js = (STATIC_DIR / "ops_workspace.js").read_text(encoding="utf-8")
    ops_workspace_panels_js = (STATIC_DIR / "ops_workspace_panels.js").read_text(encoding="utf-8")
    watchlist_panel_js = (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")
    watchlist_helpers_js = (STATIC_DIR / "watchlist_panel_helpers.js").read_text(encoding="utf-8")
    watchlist_css = (STATIC_DIR / "styles" / "watchlist.css").read_text(encoding="utf-8")
    history_shell_tabs_css = (STATIC_DIR / "styles" / "history_shell_tabs.css").read_text(encoding="utf-8")

    assert 'id="home-tab-tracking"' in index_html
    assert 'data-home-tab="tracking"' in index_html
    assert 'id="home-panel-tracking"' in index_html
    assert 'id="watchlist-stock-snapshot-panel"' in index_html
    assert "追蹤" in index_html
    assert index_html.index('id="home-panel-tracking"') < index_html.index('id="watchlist-panel"')
    assert index_html.index('id="watchlist-panel"') < index_html.index('id="home-panel-ops"')
    assert "watchlistPanel.load" in ops_workspace_js
    assert "watchlistStockSnapshotPanel" in ops_workspace_panels_js
    assert "onOpenSnapshot" in ops_workspace_panels_js
    assert "onOpenReport: options.onOpenReport" in ops_workspace_panels_js
    assert "loadWatchlistOnce" in ops_workspace_js
    assert "data-watchlist-snapshot" in watchlist_panel_js
    assert "data-watchlist-report" in watchlist_panel_js
    assert "最新報告" in watchlist_helpers_js
    assert ".watchlist-ticker-button" in watchlist_css
    assert ".watchlist-report-button" in watchlist_css
    assert "tabName === 'tracking'" in app_js
    assert "opsWorkspace.loadWatchlistOnce" in app_js
    assert "loadWatchlistOnce" in app_panels_js
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in history_shell_tabs_css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in history_shell_tabs_css


def test_watchlist_panel_opens_snapshot_and_latest_report_from_row():
    watchlist_helpers_path = STATIC_DIR / "watchlist_panel_helpers.js"
    watchlist_actions_path = STATIC_DIR / "watchlist_panel_actions.js"
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
require(__WATCHLIST_HELPERS_PATH__);
require(__WATCHLIST_ACTIONS_PATH__);
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
""".replace("__WATCHLIST_HELPERS_PATH__", json.dumps(str(watchlist_helpers_path))).replace("__WATCHLIST_ACTIONS_PATH__", json.dumps(str(watchlist_actions_path))).replace("__WATCHLIST_PANEL_PATH__", json.dumps(str(watchlist_panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    payload = json.loads(result.stdout)
    assert "data-watchlist-snapshot=\"2330.TW\"" in payload["html"]
    assert "data-watchlist-report=\"2330_v2_report.html\"" in payload["html"]
    assert "最新報告" in payload["html"]
    assert payload["opened"] == {
        "snapshot": "2330.TW",
        "report": {"filename": "2330_v2_report.html", "ticker": "2330.TW", "pipeline": "v2"},
    }


def test_watchlist_panel_actions_handle_api_lifecycle_without_panel():
    watchlist_actions_path = STATIC_DIR / "watchlist_panel_actions.js"
    script = """
global.window = {
  StockAgentWatchlistPanelHelpers: {
    itemPayload: () => ({ ticker: '2330.TW', pipeline: 'v2', enabled: true, schedule_slots: ['pre_market'], triggers: [] }),
    renderSuggestions: (elements, payload) => { elements.suggestionList.innerHTML = payload.items.map(item => `<option value="${item.ticker}">${item.name}</option>`).join(''); },
    resetForm: () => { calls.reset += 1; }
  }
};
const calls = { reset: 0, render: 0, queued: null, deleted: null, saved: null, imported: null, suggestions: null, summaries: [] };
require(__WATCHLIST_ACTIONS_PATH__);
let currentPayload = { items: [], schedules: {} };
let currentDaily = null;
const elements = {
  refreshBtn: { disabled: false },
  saveBtn: { disabled: false },
  importBtn: { disabled: false },
  runBtn: { disabled: false },
  tickerInput: { value: '2330.TW' },
  importText: { value: '2330.TW,v2' },
  suggestionList: { innerHTML: '' }
};
const actions = window.StockAgentWatchlistPanelActions.create({
  apiClient: {
    fetchWatchlist: async () => ({ items: [{ ticker: '2330.TW' }], schedules: {} }),
    fetchDailyDecisionDashboard: async () => ({ decision_queue: { summary: { total_actionable: 1 } } }),
    saveWatchlistItem: async item => { calls.saved = item; return { items: [{ ticker: item.ticker, pipeline: item.pipeline }], schedules: {} }; },
    fetchSymbolSuggestions: async query => { calls.suggestions = query; return { items: [{ ticker: '2330.TW', name: '台積電' }] }; },
    importWatchlistText: async text => { calls.imported = text; return { imported_count: 1, watchlist: { items: [{ ticker: '2317.TW' }], schedules: {} } }; },
    deleteWatchlistItem: async (ticker, pipeline) => { calls.deleted = { ticker, pipeline }; },
    runWatchlist: async () => ({ queued: [{ ticker: '2330.TW' }], skipped: [{ ticker: '1101.TW' }] })
  },
  elements,
  getPayload: () => currentPayload,
  setPayload: payload => { currentPayload = payload; },
  setDailyPayload: payload => { currentDaily = payload; },
  setSummary: message => calls.summaries.push(message),
  renderList: () => { calls.render += 1; },
  onRunQueued: result => { calls.queued = result; }
});
async function main() {
  await actions.load();
  await actions.save();
  await actions.loadSuggestions();
  await actions.importItems();
  await actions.runAll();
  await actions.remove('2330.TW', 'v2');
  process.stdout.write(JSON.stringify({ calls, currentPayload, currentDaily, elements }));
}
main();
""".replace("__WATCHLIST_ACTIONS_PATH__", json.dumps(str(watchlist_actions_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    payload = json.loads(result.stdout)
    assert payload["calls"]["saved"]["ticker"] == "2330.TW"
    assert payload["calls"]["saved"]["pipeline"] == "v2"
    assert payload["calls"]["reset"] == 1
    assert payload["calls"]["suggestions"] == "2330.TW"
    assert payload["calls"]["imported"] == "2330.TW,v2"
    assert payload["calls"]["deleted"] == {"ticker": "2330.TW", "pipeline": "v2"}
    assert payload["calls"]["queued"]["queued"][0]["ticker"] == "2330.TW"
    assert "已匯入 1 檔" in payload["calls"]["summaries"]
    assert "已排入 1 檔，略過 1 檔" in payload["calls"]["summaries"]
    assert payload["currentPayload"]["items"][0]["ticker"] == "2330.TW"
    assert payload["currentDaily"]["decision_queue"]["summary"]["total_actionable"] == 1
    assert payload["elements"]["suggestionList"]["innerHTML"] == '<option value="2330.TW">台積電</option>'
    assert payload["elements"]["importText"]["value"] == ""
    assert payload["elements"]["refreshBtn"]["disabled"] is False
    assert payload["elements"]["saveBtn"]["disabled"] is False
    assert payload["elements"]["importBtn"]["disabled"] is False
    assert payload["elements"]["runBtn"]["disabled"] is False
    assert payload["calls"]["render"] >= 4


def test_portfolio_risk_panel_is_wired_into_tracking_tab():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    app_panels_js = (STATIC_DIR / "app_panels.js").read_text(encoding="utf-8")
    ops_workspace_js = (STATIC_DIR / "ops_workspace.js").read_text(encoding="utf-8")
    ops_workspace_panels_js = (STATIC_DIR / "ops_workspace_panels.js").read_text(encoding="utf-8")
    ops_workspace_elements_js = (STATIC_DIR / "ops_workspace_elements.js").read_text(encoding="utf-8")
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
    assert "StockAgentPortfolioRiskPanel.create" in ops_workspace_panels_js
    assert "portfolioRiskElements" in ops_workspace_elements_js
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


def test_home_tabs_present_in_two_desktop_workspaces():
    history_shell_css = (STATIC_DIR / "styles" / "history_shell.css").read_text(encoding="utf-8")
    history_shell_tabs_css = (STATIC_DIR / "styles" / "history_shell_tabs.css").read_text(encoding="utf-8")
    responsive_css = (STATIC_DIR / "styles" / "responsive.css").read_text(encoding="utf-8")

    assert ".home-tabs" not in history_shell_css
    assert ".home-tab-button" not in history_shell_css
    assert ".home-tabs" in history_shell_tabs_css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in history_shell_tabs_css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in history_shell_tabs_css
    assert ".home-tab-button" in history_shell_tabs_css and "min-height: 44px;" in history_shell_tabs_css
    assert ".home-tabs {\n        grid-template-columns: 1fr;" in responsive_css


def test_home_workspace_groups_separate_analysis_and_monitoring_navigation():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    tabs_js = (STATIC_DIR / "home_tabs.js").read_text(encoding="utf-8")
    tabs_css = (STATIC_DIR / "styles" / "history_shell_tabs.css").read_text(encoding="utf-8")
    responsive_css = (STATIC_DIR / "styles" / "responsive.css").read_text(encoding="utf-8")

    assert 'class="home-workspace-nav"' in index_html
    assert 'class="home-workspace-group is-analysis"' in index_html
    assert 'class="home-workspace-group is-monitoring"' in index_html
    assert 'id="home-workspace-analysis-label"' in index_html and "分析工作台" in index_html
    assert 'id="home-workspace-monitoring-label"' in index_html and "監控工作台" in index_html
    assert 'aria-label="分析工作台"' in index_html
    assert 'aria-label="監控工作台"' in index_html
    assert "closest('[role=\"tablist\"]')" in tabs_js
    assert ".home-workspace-nav" in tabs_css
    assert ".home-workspace-group" in tabs_css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in tabs_css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in tabs_css
    assert ".home-workspace-nav {\n        grid-template-columns: 1fr;" in responsive_css


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
    app_pipeline_controls_path = STATIC_DIR / "app_pipeline_controls.js"
    assert app_pipeline_controls_path.exists()
    app_pipeline_controls_js = app_pipeline_controls_path.read_text(encoding="utf-8")
    pipeline_mode_fallback_js = (STATIC_DIR / "pipeline_mode_fallback.js").read_text(encoding="utf-8")
    ui_helpers_js = (STATIC_DIR / "ui_helpers.js").read_text(encoding="utf-8")
    forms_controls_css = (STATIC_DIR / "styles" / "forms_controls.css").read_text(encoding="utf-8")

    assert 'id="pipeline-mode-hint"' in index_html
    assert "pipelineModeHint" in app_js
    assert "updatePipelineModeHint" in app_pipeline_controls_js
    assert ".pipeline-mode-hint" in forms_controls_css
    assert '"intent":' in pipeline_mode_fallback_js
    assert "適合判斷是否納入長線研究清單" in pipeline_mode_fallback_js
    assert "適合決定進場、續抱或減碼" in pipeline_mode_fallback_js
    assert "適合檢查泡沫、避險與做空風險" in pipeline_mode_fallback_js
    assert "適合短線事件與波段交易計畫" in pipeline_mode_fallback_js


def test_pipeline_mode_frontend_labels_share_single_metadata_source():
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    app_pipeline_controls_path = STATIC_DIR / "app_pipeline_controls.js"
    assert app_pipeline_controls_path.exists()
    app_pipeline_controls_js = app_pipeline_controls_path.read_text(encoding="utf-8")
    ui_helpers_js = (STATIC_DIR / "ui_helpers.js").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    history_panel_helpers_js = (STATIC_DIR / "history_panel_helpers.js").read_text(encoding="utf-8")
    market_screener_js = (STATIC_DIR / "market_screener_panel.js").read_text(encoding="utf-8")
    watchlist_panel_js = (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")

    assert "function pipelineChoices" in ui_helpers_js
    assert "function pipelineCtaLabel" in ui_helpers_js
    assert "ui.pipelineCtaLabel(getSelectedPipeline())" in app_pipeline_controls_js
    assert "pipelineControls.getSelectedPipeline" in app_js
    assert "selectedPipeline === 'v4'" not in app_js
    assert "this.ui.pipelineChoices" in market_screener_js
    assert "const PIPELINE_OPTIONS = [" not in market_screener_js
    assert "window.StockAgentUi?.pipelineModeLabel" in history_panel_helpers_js
    assert "const labels = {" not in history_panel_js
    assert "ui.pipelineModeLabel" in watchlist_panel_js
    assert ".toUpperCase())" not in watchlist_panel_js


def test_app_pipeline_controls_sync_labels_and_selection():
    app_pipeline_controls_path = STATIC_DIR / "app_pipeline_controls.js"
    script = """
global.window = {};
require(__APP_PIPELINE_CONTROLS_PATH__);
const titles = {}, subtitles = {}, historyOptions = {}, watchlistOptions = {};
const pipelineInputs = ['v1', 'v4'].map(value => ({
  value,
  checked: value === 'v1',
  closest: () => ({
    querySelector: selector => {
      if (selector === 'strong') return titles[value] ||= { textContent: '' };
      if (selector === 'small') return subtitles[value] ||= { textContent: '' };
      return null;
    }
  })
}));
const doc = {
  querySelector(selector) {
    if (selector === 'input[name="pipeline-mode"]:checked') return pipelineInputs.find(input => input.checked) || null;
    if (selector === '#watchlist-pipeline-select option[value="v1"]') return watchlistOptions.v1 ||= { textContent: '' };
    if (selector === '#watchlist-pipeline-select option[value="v4"]') return watchlistOptions.v4 ||= { textContent: '' };
    if (selector.includes('value="v1"')) return pipelineInputs[0];
    if (selector.includes('value="v4"')) return pipelineInputs[1];
    return null;
  }
};
const historyPipelineFilter = {
  querySelector(selector) {
    if (selector === 'option[value="v1"]') return historyOptions.v1 ||= { textContent: '' };
    if (selector === 'option[value="v4"]') return historyOptions.v4 ||= { textContent: '' };
    return null;
  }
};
const analyzeBtnText = { textContent: '' };
const pipelineModeHint = { textContent: '' };
const controls = window.StockAgentAppPipelineControls.create({
  ui: {
    pipelineChoices: () => [
      { value: 'v1', codeLabel: '模式 A', optionLabel: '長線研究', intent: '長線 thesis' },
      { value: 'v4', codeLabel: '模式 D', optionLabel: '事件波段', intent: '事件交易' }
    ],
    pipelineModeLabel: value => `Label ${value}`,
    pipelineCtaLabel: value => `Analyze ${value}`,
    pipelineMeta: value => ({ intent: `Intent ${value}` })
  },
  doc,
  pipelineInputs,
  analyzeBtnText,
  pipelineModeHint,
  historyPipelineFilter
});
controls.syncPipelineOptionLabels();
controls.selectPipelineMode('v4');
process.stdout.write(JSON.stringify({
  selected: controls.getSelectedPipeline(),
  checked: pipelineInputs.map(input => [input.value, input.checked]),
  cta: analyzeBtnText.textContent,
  hint: pipelineModeHint.textContent,
  title: titles.v4.textContent,
  subtitle: subtitles.v4.textContent,
  history: historyOptions.v4.textContent,
  watchlist: watchlistOptions.v4.textContent
}));
""".replace("__APP_PIPELINE_CONTROLS_PATH__", json.dumps(str(app_pipeline_controls_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["selected"] == "v4"
    assert payload["checked"] == [["v1", False], ["v4", True]]
    assert payload["cta"] == "Analyze v4"
    assert payload["hint"] == "Intent v4"
    assert payload["title"] == "模式 D"
    assert payload["subtitle"] == "事件波段"
    assert payload["history"] == "Label v4"
    assert payload["watchlist"] == "Label v4"


def test_app_panels_create_and_initialize_workspaces_without_app_entrypoint():
    app_panels_path = STATIC_DIR / "app_panels.js"
    script = """
global.window = {};
const calls = [];
const opsWorkspace = {
  loadWatchlistOnce: () => calls.push('ops:watchlist'),
  refreshProviderSlaIfLoaded: () => calls.push('ops:provider-sla'),
  loadAllOnce: () => calls.push('ops:all'),
  bindEvents: () => calls.push('ops:bind')
};
window.StockAgentOpsWorkspace = { create: options => {
  calls.push(`ops:create:${options.getSelectedPipeline()}`);
  options.onOpenReport('report.html', 'TSM', 'v2');
  options.onSelectPipeline('v2');
  return opsWorkspace;
}};
window.StockAgentOperatorSummaryPanel = { create: () => ({ load: () => calls.push('summary:load') }) };
window.StockAgentMarketScreenerPanel = { create: options => {
  calls.push(`screener:create:${Boolean(options.elements.runBtn)}`);
  return { loadOnce: () => calls.push('screener:load'), bindEvents: () => calls.push('screener:bind') };
}};
window.StockAgentStockSnapshotPanel = { create: options => {
  calls.push(`snapshot:create:${Boolean(options.elements.shortcutsRoot)}`);
  options.onWatchlistUpdated();
  return { bindEvents: () => calls.push('snapshot:bind') };
}};
window.StockAgentHistoryWorkspace = { create: options => {
  calls.push(`history:create:${Boolean(options.elements.reportPreview)}`);
  options.refreshProviderSlaIfLoaded();
  options.openReport('history.html', 'AAPL', 'v4');
  return { loadHistory: () => calls.push('history:load'), bindEvents: () => calls.push('history:bind') };
}};
require(__APP_PANELS_PATH__);
const doc = { getElementById: id => ({ id }) };
const elements = {
  stockSnapshotPanelEl: {}, stockSnapshotLoadBtn: {}, stockSnapshotShortcutsEl: {}, tickerInput: {},
  historyWorkspaceEl: {}, historyList: {}, historySearch: {}, historyPipelineFilter: {}, historyRecommendationFilter: {},
  historyDataTrustFilter: {}, historyIncludeVersions: {}, historyPagination: {}, historyPrev: {}, historyNext: {},
  historyPageInfo: {}, historyTrackingTable: {}, decisionTrackingStockSnapshotPanel: {}, decisionTrackingSummary: {},
  decisionTrackingRefresh: {}, decisionTrackingDensity: {}, decisionTrackingRunActions: {}, reportPreview: {},
  previewMode: {}, previewTitle: {}, previewPrice: {}, previewRecommendation: {}, previewConfidence: {},
  previewTarget3m: {}, previewTarget6m: {}, previewTarget12m: {}, previewSummary: {}, previewStaleNotice: {},
  previewOpenReportBtn: {}, previewRefreshDataBtn: {}, previewCompareAddBtn: {}, previewRerunFinalBtn: {},
  previewRerunFullBtn: {}, previewRerunModeBBtn: {}, previewRerunCancelBtn: {}, previewCloseBtn: {},
  reportCompareSummary: {}, reportCompareResult: {}, reportCompareClearBtn: {}
};
const panels = window.StockAgentAppPanels.create({
  apiClient: {}, ui: {}, notify: {}, elements, doc,
  openReport: (filename, ticker, pipeline) => calls.push(`open:${filename}:${ticker}:${pipeline}`),
  selectPipelineMode: value => calls.push(`select:${value}`),
  getSelectedPipeline: () => 'v1'
});
panels.bindPanelEvents();
panels.loadInitialPanels();
panels.marketScreenerPanel.loadOnce();
panels.opsWorkspace.loadAllOnce();
process.stdout.write(JSON.stringify(calls));
""".replace("__APP_PANELS_PATH__", json.dumps(str(app_panels_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    calls = json.loads(result.stdout)

    assert calls[:2] == ["ops:create:v1", "open:report.html:TSM:v2"]
    assert "select:v2" in calls
    assert "ops:watchlist" in calls
    assert "ops:provider-sla" in calls
    assert "history:create:true" in calls
    assert "open:history.html:AAPL:v4" in calls
    assert calls[-8:] == ["history:bind", "ops:bind", "screener:bind", "snapshot:bind", "history:load", "summary:load", "screener:load", "ops:all"]


def test_app_panels_candidate_actions_reuse_snapshot_and_analysis_workflows():
    app_panels_path = STATIC_DIR / "app_panels.js"
    script = """
global.window = {};
const calls = [];
let candidateCallbacks;
let summaryNotify;
const analysisTab = { click: () => calls.push('analysis:tab') };
const analyzeButton = { click: () => calls.push('analysis:run') };
const notify = { error: message => calls.push(`error:${message}`) };
let tickerValue = '';
const tickerInput = {
  get value() { return tickerValue; },
  set value(value) { tickerValue = value; calls.push(`ticker:${value}`); },
  focus: () => calls.push('ticker:focus')
};
const checkedMode = { focus: () => calls.push('mode:focus') };
const pipelineSelector = {
  querySelector: selector => selector === 'input:checked' ? checkedMode : null,
  scrollIntoView: options => calls.push(`pipeline:scroll:${options.behavior}:${options.block}`)
};
const snapshotRoot = { scrollIntoView: options => calls.push(`snapshot:scroll:${options.behavior}:${options.block}`) };
const doc = {
  getElementById: id => id === 'home-tab-analysis' ? analysisTab : id === 'ticker-input' ? tickerInput : id === 'analyze-btn' ? analyzeButton : ({ id }),
  querySelector: selector => selector === '.pipeline-selector' ? pipelineSelector : null
};
window.StockAgentOpsWorkspace = { create: () => ({ loadWatchlistOnce: () => {}, bindEvents: () => {}, loadAllOnce: () => {} }) };
window.StockAgentOperatorSummaryPanel = { create: options => {
  calls.push('summary:create');
  summaryNotify = options.notify;
  candidateCallbacks = {
    snapshot: options.onCandidateSnapshot,
    watchlist: options.onCandidateWatchlist,
    prepareAnalysis: options.onCandidatePrepareAnalysis
  };
  return { load: () => {}, bindEvents: () => {} };
}};
window.StockAgentMarketScreenerPanel = { create: () => ({ loadOnce: () => {}, bindEvents: () => {} }) };
window.StockAgentStockSnapshotPanel = { create: () => {
  calls.push('snapshot:create');
  return {
    load: async ticker => { calls.push(`snapshot:${ticker}`); await Promise.resolve(); calls.push('snapshot:loaded'); },
    addToWatchlist: async ticker => calls.push(`watchlist:${ticker}`),
    bindEvents: () => {}
  };
} };
window.StockAgentHistoryWorkspace = { create: () => ({ loadHistory: () => {}, bindEvents: () => {} }) };
require(__APP_PANELS_PATH__);
const panels = window.StockAgentAppPanels.create({
  apiClient: {}, ui: {}, notify,
  elements: { tickerInput, stockSnapshotPanelEl: snapshotRoot, analyzeBtn: analyzeButton }, doc,
  switchView: view => calls.push(`view:${view}`),
  selectPipelineMode: pipeline => calls.push(`pipeline:${pipeline}`),
  getSelectedPipeline: () => 'v3'
});
(async () => {
  await candidateCallbacks.snapshot(' 2330.tw ');
  await candidateCallbacks.watchlist('2454.tw');
  await candidateCallbacks.prepareAnalysis(' 2317.tw ');
  process.stdout.write(JSON.stringify({ calls, notifyPassed: summaryNotify === notify, ticker: tickerInput.value }));
})();
""".replace("__APP_PANELS_PATH__", json.dumps(str(app_panels_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["calls"] == [
        "snapshot:create", "summary:create",
        "view:home-view", "analysis:tab", "ticker:2330.TW", "snapshot:2330.TW", "snapshot:loaded", "snapshot:scroll:smooth:start",
        "watchlist:2454.TW",
        "view:home-view", "analysis:tab", "ticker:2317.TW", "pipeline:scroll:smooth:start", "mode:focus",
    ]
    assert payload["calls"].index("snapshot:create") < payload["calls"].index("summary:create")
    assert payload["calls"].index("ticker:2330.TW") < payload["calls"].index("snapshot:2330.TW")
    assert payload["calls"].index("ticker:2317.TW") < payload["calls"].index("pipeline:scroll:smooth:start") < payload["calls"].index("mode:focus")
    assert payload["notifyPassed"] is True
    assert payload["ticker"] == "2317.TW"
    assert "analysis:run" not in payload["calls"]
    assert "ticker:focus" not in payload["calls"]
    assert "pipeline:v3" not in payload["calls"]


def test_ops_workspace_panels_create_panels_and_loaders_without_workspace():
    panels_path = STATIC_DIR / "ops_workspace_panels.js"
    script = """
global.window = {};
const calls = [];
const root = { hidden: true, scrollIntoView: opts => calls.push(`scroll:${opts.block}`) };
window.StockAgentStockSnapshotPanel = { create: options => ({
  load: ticker => {
    calls.push(`snapshot:${ticker}:${options.getSelectedPipeline()}`);
    return Promise.resolve();
  }
}) };
window.StockAgentWatchlistPanel = { create: options => {
  calls.push(`watchlist:create:${Boolean(options.onRunQueued)}:${Boolean(options.onOpenReport)}`);
  options.onRunQueued();
  return { bindEvents: () => calls.push('watchlist:bind'), load: () => calls.push('watchlist:load') };
} };
window.StockAgentPortfolioRiskPanel = { create: options => {
  calls.push(`portfolio:create:${Boolean(options.elements)}`);
  return { bindEvents: () => calls.push('portfolio:bind') };
} };
window.StockAgentProviderSlaPanel = { render: payload => calls.push(`render:sla:${payload.kind}`) };
window.StockAgentActiveJobsPanel = { render: payload => calls.push(`render:jobs:${payload.kind}`) };
window.StockAgentApiQuotaPanel = { render: payload => calls.push(`render:quota:${payload.kind}`) };
window.StockAgentPerformancePanel = { render: payload => calls.push(`render:perf:${payload.kind}`) };
require(__PANELS_PATH__);
const apiClient = {
  fetchProviderSla: options => { calls.push(`fetch:sla:${options.windowValue}:${options.limit}`); return Promise.resolve({ kind: 'sla' }); },
  fetchActiveJobs: options => { calls.push(`fetch:jobs:${options.limit}:${options.eventLimit}`); return Promise.resolve({ kind: 'jobs' }); },
  fetchApiQuotas: () => { calls.push('fetch:quota'); return Promise.resolve({ kind: 'quota' }); },
  fetchPerformanceStats: () => { calls.push('fetch:perf'); return Promise.resolve({ kind: 'perf' }); }
};
const ui = { escapeHtml: value => String(value ?? ''), pipelineModeLabel: value => `模式 ${value}` };
const elements = {
  watchlistStockSnapshotRoot: root,
  watchlistElements: {},
  portfolioRiskElements: {},
  providerSlaSummary: {}, providerSlaList: {}, providerSlaRefresh: {}, providerSlaWindow: { value: 'last_24h' },
  activeJobsSummary: {}, activeJobsList: {}, activeJobsRefresh: {},
  apiQuotaSummary: {}, apiQuotaList: {}, apiQuotaRefresh: {},
  performanceSummary: {}, performanceList: {}, performanceRefresh: {}
};
const loadPanel = async config => {
  calls.push(`load:${config.errorLabel}:${config.failureMessage}`);
  config.renderPayload(await config.fetchPayload());
};
(async () => {
  const loaders = window.StockAgentOpsWorkspacePanels.createLoaders({ apiClient, ui, elements, loadPanel });
  const panels = window.StockAgentOpsWorkspacePanels.createPanels({
    apiClient, ui, elements, notify: {}, loadActiveJobs: loaders.loadActiveJobs,
    onSelectPipeline: value => calls.push(`select:${value}`),
    getSelectedPipeline: () => 'v4',
    onOpenReport: () => calls.push('open-report')
  });
  await panels.onOpenSnapshot('2330.TW');
  panels.watchlistPanel.bindEvents();
  panels.portfolioRiskPanel.bindEvents();
  await loaders.loadProviderSla();
  await loaders.loadActiveJobs();
  await loaders.loadApiQuotas();
  await loaders.loadPerformance();
  process.stdout.write(JSON.stringify({ calls, rootHidden: root.hidden }));
})().catch(err => {
  console.error(err);
  process.exit(1);
});
""".replace("__PANELS_PATH__", json.dumps(str(panels_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["rootHidden"] is False
    assert "snapshot:2330.TW:v4" in payload["calls"]
    assert "scroll:nearest" in payload["calls"]
    assert "watchlist:create:true:true" in payload["calls"]
    assert "portfolio:create:true" in payload["calls"]
    assert "fetch:sla:last_24h:100" in payload["calls"]
    assert "fetch:jobs:5:40" in payload["calls"]
    assert "render:sla:sla" in payload["calls"]
    assert "render:jobs:jobs" in payload["calls"]
    assert "render:quota:quota" in payload["calls"]
    assert "render:perf:perf" in payload["calls"]
    assert any("LLM 健康讀取失敗" in item for item in payload["calls"])


def test_report_compare_renderers_build_summary_and_result_without_panel():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    helpers_path = STATIC_DIR / "report_compare_helpers.js"
    renderers_path = STATIC_DIR / "report_compare_renderers.js"
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
require(__HELPERS_PATH__);
require(__RENDERERS_PATH__);
const renderers = window.StockAgentReportCompareRenderers.create({
  helpers: window.StockAgentReportCompareHelpers,
  escapeHtml: value => String(value ?? ''),
  pipelineModeLabel: value => `模式 ${value}`
});
const summary = renderers.selectionSummary([
  { ticker: '2330.TW', pipeline_id: 'v1', date: '2026-07-08' },
  { ticker: '2330.TW', pipeline_id: 'v2', date: '2026-07-09' }
]);
const html = renderers.resultHtml({
  left: { ticker: '2330.TW', filename: 'left.html', pipeline_id: 'v1', date: '2026-07-08', analysis_text_stale: true, decision_freshness: { status: 'current' } },
  right: { ticker: '2330.TW', filename: 'right.html', pipeline_id: 'v2', date: '2026-07-09', decision_freshness: { status: 'current' } },
  compatibility: { same_ticker: true, same_pipeline: false, date_order: 'chronological', warnings: [{ code: 'different_pipeline', level: 'warning' }] },
  diff: {
    recommendation: { before: '持有', after: '買進' },
    current_price: { delta: 12.3, delta_pct: 1.23 },
    target_3m: { delta: 5 },
    target_6m: { delta: -2 },
    target_12m: { delta: 8 },
    data_trust: { status_before: 'partial', status_after: 'fresh', score: { delta: 0.2 } },
    tracking: { return_pct: { delta: 3.4 }, latest_price: { delta: 15 } }
  }
});
process.stdout.write(JSON.stringify({ summary, html }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HELPERS_PATH__", json.dumps(str(helpers_path))).replace("__RENDERERS_PATH__", json.dumps(str(renderers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["summary"] == "2330.TW · 模式 v1 · 2026-07-08 ↔ 2330.TW · 模式 v2 · 2026-07-09"
    assert "兩份報告模式不同" in payload["html"]
    assert "跨視角比較" in payload["html"]
    assert "比較基準" in payload["html"]
    assert "報告建議變化" in payload["html"]
    assert "持有 → 買進" in payload["html"]
    assert "決策狀態" in payload["html"]
    assert "需重跑 → 有效" in payload["html"]
    assert "報告差異不等於市場因果" in payload["html"]


def test_report_compare_decision_status_uses_report_quality_policy():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    helpers_path = STATIC_DIR / "report_compare_helpers.js"
    report_quality_policy_js = report_quality_policy_path.read_text(encoding="utf-8")
    helpers_js = helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportDecisionStatusLabel = report => report?.policy_label || 'policy-current';
require(__HELPERS_PATH__);
const label = window.StockAgentReportCompareHelpers.reportDecisionStatusLabel({
  policy_label: 'policy-current',
  analysis_text_stale: true,
  requires_rerun: true,
  decision_freshness: { requires_rerun: true, status: 'needs_rerun' }
});
process.stdout.write(JSON.stringify({ label }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HELPERS_PATH__", json.dumps(str(helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportDecisionStatusLabel" in report_quality_policy_js
    assert "reportDecisionStatusLabel?.(report)" in helpers_js
    assert "freshness.requires_rerun" not in helpers_js
    assert "freshness.status === 'needs_rerun'" not in helpers_js
    assert payload["label"] == "policy-current"


def test_report_rerun_stream_reports_status_and_resolves_without_rerun_module():
    stream_path = STATIC_DIR / "report_rerun_stream.js"
    script = """
global.window = {};
let source = null;
class FakeEventSource {
  constructor(url) {
    this.url = url;
    source = this;
  }
  close() {
    this.closed = true;
  }
  emit(payload) {
    this.onmessage({ data: JSON.stringify(payload) });
  }
}
global.EventSource = FakeEventSource;
require(__STREAM_PATH__);
const statuses = [];
(async () => {
  const pending = window.StockAgentReportRerunStream.open({
    streamUrl: '/rerun-stream',
    onStatus: message => statuses.push(message)
  });
  source.emit({ type: 'status', message: '排入重跑' });
  source.emit({ type: 'progress', name: '基本面分析' });
  source.emit({ type: 'report_done' });
  source.emit({ type: 'done', filename: '2330.html', scope_label: '局部重跑' });
  const payload = await pending;
  process.stdout.write(JSON.stringify({
    url: source.url,
    closed: source.closed,
    statuses,
    filename: payload.filename
  }));
})().catch(err => {
  console.error(err);
  process.exit(1);
});
""".replace("__STREAM_PATH__", json.dumps(str(stream_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["url"] == "/rerun-stream"
    assert payload["closed"] is True
    assert payload["statuses"] == [
        "排入重跑",
        "報告重跑中：基本面分析",
        "新報告已產生，正在整理列表...",
    ]
    assert payload["filename"] == "2330.html"


def test_analysis_stream_events_handle_state_and_report_completion_without_stream():
    events_path = STATIC_DIR / "analysis_stream_events.js"
    script = """
global.window = {};
const calls = [];
const stateValue = { currentPipeline: 'v1', pendingAuditNotice: { status: 'ok', message: 'old audit' } };
global.setTimeout = (fn, delay) => {
  calls.push(`timeout:${delay}`);
  fn();
};
function element(name) {
  return {
    _text: '',
    set textContent(value) {
      this._text = value;
      calls.push(`${name}:${value}`);
    },
    get textContent() {
      return this._text;
    },
    style: {}
  };
}
const progressBar = element('progress');
Object.defineProperty(progressBar.style, 'width', {
  set(value) {
    calls.push(`progressWidth:${value}`);
  }
});
require(__EVENTS_PATH__);
const events = window.StockAgentAnalysisStreamEvents.create({
  state: () => stateValue,
  patchState: patch => {
    Object.assign(stateValue, patch);
    calls.push(`patch:${Object.keys(patch).sort().join(',')}`);
  },
  close: () => calls.push('close'),
  setCurrentJobId: jobId => calls.push(`job:${jobId}`),
  updateLastEventId: value => calls.push(`last:${value}`),
  loadingHint: element('hint'),
  loadingStatus: element('status'),
  loadingMsg: element('msg'),
  progressBar,
  reportTickerTitle: element('title'),
  reportIframe: { set src(value) { calls.push(`iframe:${value}`); } },
  pipelineMeta: pipeline => ({ hint: `hint ${pipeline}`, reportSuffix: `suffix ${pipeline}` }),
  pipelineModeLabel: pipeline => `模式 ${pipeline}`,
  setAuditNotice: audit => calls.push(`audit:${audit.message}`),
  switchView: view => calls.push(`view:${view}`),
  loadHistory: () => calls.push('history')
});
events.handle({ type: 'job', job_id: 'job-1', pipeline_id: 'v2', resume_after_id: 9 }, 'TSM');
events.handle({ type: 'progress', current: 2, total: 4, name: '估值分析' }, 'TSM');
events.handle({ type: 'report_done', pipeline_id: 'v2', pipeline_index: 1, pipeline_total: 2 }, 'TSM');
events.handle({ type: 'audit', audit: { status: 'needs_attention', message: '需人工檢查' } }, 'TSM');
events.handle({ type: 'done', filename: 'report.html', filenames: ['a.html', 'b.html'], pipeline_id: 'both', audit: { message: 'done audit' } }, 'TSM');
events.handle({ type: 'error', message: '資料不足' }, 'TSM');
process.stdout.write(JSON.stringify({ calls, stateValue }));
""".replace("__EVENTS_PATH__", json.dumps(str(events_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "job:job-1" in payload["calls"]
    assert "last:9" in payload["calls"]
    assert "hint:hint v2" in payload["calls"]
    assert "status:分析中：第 2/4 位分析師" in payload["calls"]
    assert "progressWidth:50%" in payload["calls"]
    assert "status:模式 v2 報告完成" in payload["calls"]
    assert "history" in payload["calls"]
    assert "status:需人工檢查" in payload["calls"]
    assert "title:TSM 2 模式分析完成" in payload["calls"]
    assert "iframe:/api/report/report.html" in payload["calls"]
    assert "view:report-view" in payload["calls"]
    assert "status:發生錯誤" in payload["calls"]
    assert payload["stateValue"]["currentPipeline"] == "v3"
    assert payload["stateValue"]["currentReportFilename"] == "report.html"


def test_primary_cta_has_readable_contrast_on_cyan_action_background():
    forms_controls_css = (STATIC_DIR / "styles" / "forms_controls.css").read_text(encoding="utf-8")

    assert ".glow-button" in forms_controls_css
    assert "background: var(--accent);" in forms_controls_css
    assert "color: #03111f;" in forms_controls_css
    assert _contrast_ratio("#03111f", "#00d4ff") >= 4.5


def test_history_version_toggle_checkbox_is_visually_legible():
    history_list_css = (STATIC_DIR / "styles" / "history_list.css").read_text(encoding="utf-8")
    history_list_controls_css = (STATIC_DIR / "styles" / "history_list_controls.css").read_text(encoding="utf-8")

    assert ".history-version-toggle input" not in history_list_css
    assert ".history-version-toggle input" in history_list_controls_css
    assert "width: 22px;" in history_list_controls_css
    assert "height: 22px;" in history_list_controls_css


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
    app_panels_js = (STATIC_DIR / "app_panels.js").read_text(encoding="utf-8")
    history_workspace_js = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")
    history_workspace_panels_js = (STATIC_DIR / "history_workspace_panels.js").read_text(encoding="utf-8")
    decision_tracking_js = (STATIC_DIR / "decision_tracking_panel.js").read_text(encoding="utf-8")
    decision_tracking_helpers_js = (STATIC_DIR / "decision_tracking_helpers.js").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    history_panel_helpers_js = (STATIC_DIR / "history_panel_helpers.js").read_text(encoding="utf-8")
    decision_tracking_css = (STATIC_DIR / "styles" / "decision_tracking.css").read_text(encoding="utf-8")

    assert 'id="decision-tracking-run-actions"' in index_html
    assert "decisionTrackingRunActions" in app_panels_js
    assert "runActionsBtn: elements.decisionTrackingRunActions" in history_workspace_panels_js
    assert "runAllRecommendedActions" in decision_tracking_js
    assert "refreshReportDataSnapshot" in decision_tracking_js
    assert "/rerun?scope=full_report" in decision_tracking_js
    assert "recommendedActionForReport" in decision_tracking_helpers_js
    assert "uniqueRecommendedActions" in decision_tracking_helpers_js
    assert "failed += 1" in decision_tracking_js
    assert "trackingSummaryTone" in history_panel_helpers_js
    assert ".tracking-compact-note.is-above-target" in decision_tracking_css
    assert ".tracking-compact-note.is-near-target" in decision_tracking_css
    assert ".tracking-compact-note.is-below-target" in decision_tracking_css


def test_decision_tracking_actions_share_report_quality_policy():
    report_quality_gate_policy_path = STATIC_DIR / "report_quality_gate_policy.js"
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    report_quality_policy_js = report_quality_policy_path.read_text(encoding="utf-8")
    decision_tracking_helpers_path = STATIC_DIR / "decision_tracking_helpers.js"
    decision_tracking_helpers_js = decision_tracking_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_GATE_POLICY_PATH__);
require(__REPORT_QUALITY_POLICY_PATH__);
require(__DECISION_TRACKING_HELPERS_PATH__);
const helpers = window.StockAgentDecisionTrackingHelpers;
const providerOnlyReport = {
  filename: 'provider_only.html',
  data_trust: { status: 'partial', reason_codes: ['provider_sla_critical'] }
};
const actions = helpers.uniqueRecommendedActions({
  items: [{
    enabled: true,
    ticker: '2330.TW',
    latest_reports: [
      providerOnlyReport,
      {
        filename: 'blocked.html',
        data_trust: { status: 'fresh' },
        report_conformance: { status: 'blocked', summary: 'report contract broken' }
      },
      {
        filename: 'data_error.html',
        data_trust: { status: 'error', reason_codes: ['source_error:price'] }
      },
      {
        filename: 'stale.html',
        data_trust: { status: 'stale', stale_sources: ['price'], reason_codes: ['source_stale:price'] }
      },
      {
        filename: 'partial.html',
        data_trust: { status: 'partial', reason_codes: ['missing_data_trust_snapshot'] }
      },
      {
        filename: 'rerun.html',
        decision_freshness: { requires_rerun: true }
      }
    ]
  }]
});
window.StockAgentReportQualityPolicy = {
  reportRecommendedAction: () => null,
  dataTrustStatus: report => report?.data_trust?.status || 'fresh'
};
const suppressedRerun = helpers.recommendedActionForReport({
  filename: 'raw_rerun.html',
  analysis_text_stale: true,
  requires_rerun: true,
  decision_freshness: { requires_rerun: true }
});
const suppressedRefresh = helpers.recommendedActionForReport({
  filename: 'raw_stale.html',
  data_trust: { status: 'stale', stale_sources: ['price'], reason_codes: ['source_stale:price'] }
});
const suppressedPartial = helpers.recommendedActionForReport({
  filename: 'raw_partial.html',
  data_trust: { status: 'partial', reason_codes: ['missing_data_trust_snapshot'] }
});
process.stdout.write(JSON.stringify({
  providerAction: helpers.recommendedActionForReport(providerOnlyReport),
  suppressedRerun,
  suppressedRefresh,
  suppressedPartial,
  actions
}));
""".replace("__REPORT_QUALITY_GATE_POLICY_PATH__", json.dumps(str(report_quality_gate_policy_path))).replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__DECISION_TRACKING_HELPERS_PATH__", json.dumps(str(decision_tracking_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportNeedsDataRefresh" in report_quality_policy_js
    assert "reportRecommendedAction" in report_quality_policy_js
    assert "StockAgentReportQualityPolicy" in decision_tracking_helpers_js
    assert "reportRecommendedAction?.(report)" in decision_tracking_helpers_js
    assert "reportNeedsRerun?.(report)" not in decision_tracking_helpers_js
    assert "reportNeedsDataRefresh?.(report)" not in decision_tracking_helpers_js
    assert "dataTrustReasonCodes" not in decision_tracking_helpers_js
    assert "dataTrustStatus(report) === 'stale'" not in decision_tracking_helpers_js
    assert "dataTrustStatus(report) === 'partial'" not in decision_tracking_helpers_js
    assert "report?.analysis_text_stale" not in decision_tracking_helpers_js
    assert "report?.decision_freshness?.requires_rerun" not in decision_tracking_helpers_js
    assert "report?.requires_rerun" not in decision_tracking_helpers_js
    assert payload["providerAction"] is None
    assert payload["suppressedRerun"] is None
    assert payload["suppressedRefresh"] is None
    assert payload["suppressedPartial"] is None
    assert payload["actions"] == [
        {"type": "manual_review", "filename": "blocked.html"},
        {"type": "manual_review", "filename": "data_error.html"},
        {"type": "refresh_data_snapshot", "filename": "stale.html"},
        {"type": "refresh_data_snapshot", "filename": "partial.html"},
        {"type": "rerun_full_report", "filename": "rerun.html"},
    ]


def test_decision_tracking_bulk_actions_do_not_auto_execute_manual_review():
    report_quality_gate_policy_path = STATIC_DIR / "report_quality_gate_policy.js"
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    decision_tracking_helpers_path = STATIC_DIR / "decision_tracking_helpers.js"
    decision_tracking_path = STATIC_DIR / "decision_tracking_panel.js"
    decision_tracking_js = decision_tracking_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_GATE_POLICY_PATH__);
require(__REPORT_QUALITY_POLICY_PATH__);
require(__DECISION_TRACKING_HELPERS_PATH__);
require(__DECISION_TRACKING_PATH__);
const payload = { items: [{
  enabled: true,
  ticker: '2330.TW',
  latest_reports: [
    { filename: 'manual.html', ticker: '2330.TW', report_conformance: { status: 'blocked' } },
    { filename: 'stale.html', ticker: '2330.TW', data_trust: { status: 'stale', stale_sources: ['price'], reason_codes: ['source_stale:price'] } }
  ]
}] };
const refreshCalls = [], requestCalls = [], successMessages = [], errorMessages = [];
const panel = window.StockAgentDecisionTrackingPanel.create({
  apiClient: {
    async fetchDecisionTracking() { return payload; },
    async refreshReportDataSnapshot(filename) { refreshCalls.push(filename); return {}; },
    async requestJson(path) { requestCalls.push(path); return {}; }
  },
  historyPanel: { renderTrackingGroups() {} },
  notify: {
    success(message) { successMessages.push(message); },
    error(message) { errorMessages.push(message); }
  },
  elements: { runActionsBtn: { disabled: false, addEventListener() {} }, summaryEl: { textContent: '' } },
  onChange: () => {}
});
(async () => {
  await panel.load();
  await panel.runAllRecommendedActions();
  process.stdout.write(JSON.stringify({ refreshCalls, requestCalls, successMessages, errorMessages }));
})();
""".replace("__REPORT_QUALITY_GATE_POLICY_PATH__", json.dumps(str(report_quality_gate_policy_path))).replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__DECISION_TRACKING_HELPERS_PATH__", json.dumps(str(decision_tracking_helpers_path))).replace("__DECISION_TRACKING_PATH__", json.dumps(str(decision_tracking_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "manual_review" in decision_tracking_js
    assert "manualReview" in decision_tracking_js
    assert payload["refreshCalls"] == ["stale.html"]
    assert payload["requestCalls"] == []
    assert payload["errorMessages"] == []
    assert payload["successMessages"] == ["已送出 1 個自動警示動作，1 個需人工查看"]


def test_compact_tracking_cards_render_target_comparison_tones():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    history_panel_renderers_path = STATIC_DIR / "history_panel_renderers.js"
    history_panel_path = STATIC_DIR / "history_panel.js"
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
require(__HISTORY_PANEL_RENDERERS_PATH__);
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
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path))).replace("__HISTORY_PANEL_RENDERERS_PATH__", json.dumps(str(history_panel_renderers_path))).replace("__HISTORY_PANEL_PATH__", json.dumps(str(history_panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert 'tracking-compact-note is-above-target' in result.stdout
    assert 'tracking-compact-note is-near-target' in result.stdout
    assert 'tracking-compact-note is-below-target' in result.stdout


def test_mode_d_tracking_card_uses_trade_setup_instead_of_target_comparison():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    history_panel_renderers_path = STATIC_DIR / "history_panel_renderers.js"
    history_panel_path = STATIC_DIR / "history_panel.js"
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
require(__HISTORY_PANEL_RENDERERS_PATH__);
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
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path))).replace("__HISTORY_PANEL_RENDERERS_PATH__", json.dumps(str(history_panel_renderers_path))).replace("__HISTORY_PANEL_PATH__", json.dumps(str(history_panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "大東電" in result.stdout
    assert "中性 Neutral" in result.stdout
    assert "短線目標" in result.stdout
    assert "跌破 205" in result.stdout
    assert "無法比較" not in result.stdout
    assert "尚無法比較目標" not in result.stdout


def test_tracking_card_surfaces_full_rerun_action_when_snapshot_outpaces_conclusion():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    history_panel_renderers_path = STATIC_DIR / "history_panel_renderers.js"
    history_panel_path = STATIC_DIR / "history_panel.js"
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
require(__HISTORY_PANEL_RENDERERS_PATH__);
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
    filename: '1623_v1_report_job_stale.html',
    ticker: '1623.TW',
    company_name: '大東電',
    pipeline_id: 'v1',
    date: '2026-07-03 20:58',
    analysis_text_stale: true,
    decision_freshness: {
      requires_rerun: true,
      message: '資料快照已刷新，但 HTML/Markdown 分析本文未重新執行。'
    },
    recommendation: { recommendation: '持有' },
    decision_tracking: {
      status: 'tracked',
      recommendation: '持有',
      latest_price: 230.5,
      return_pct: 7.7,
      tracking_summary_status: '高於6月目標',
      target_comparisons: {
        target_3m: { status: 'above_target', target: 174.5 },
        target_6m: { status: 'above_target', target: 214 },
        target_12m: { status: 'below_target', target: 318.5 }
      }
    }
  }]
}]);
process.stdout.write(table.innerHTML);
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path))).replace("__HISTORY_PANEL_RENDERERS_PATH__", json.dumps(str(history_panel_renderers_path))).replace("__HISTORY_PANEL_PATH__", json.dumps(str(history_panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "需完整重跑" in result.stdout
    assert "tracking-action-note is-critical" in result.stdout
    assert "資料快照已刷新" in result.stdout


def test_decision_tracking_groups_prefer_full_report_ticker_for_display():
    decision_tracking_path = STATIC_DIR / "decision_tracking_panel.js"
    decision_tracking_helpers_path = STATIC_DIR / "decision_tracking_helpers.js"
    script = """
global.window = {};
require(__DECISION_TRACKING_HELPERS_PATH__);
require(__DECISION_TRACKING_PATH__);
let renderedGroups = [];
const panel = window.StockAgentDecisionTrackingPanel.create({
  apiClient: {
    async fetchDecisionTracking() {
      return {
        items: [{
          ticker: '1623',
          enabled: true,
          company_name: '大東電',
          latest_report: {
            filename: '1623_TW_v1_report.html',
            ticker: '1623.TW',
            company_name: '大東電',
            decision_tracking: { status: 'tracked' }
          },
          latest_reports: [{
            filename: '1623_TW_v1_report.html',
            ticker: '1623.TW',
            company_name: '大東電',
            decision_tracking: { status: 'tracked' }
          }]
        }]
      };
    }
  },
  historyPanel: { renderTrackingGroups(groups) { renderedGroups = groups; } },
  elements: {},
  onChange: () => {}
});
panel.load().then(() => process.stdout.write(JSON.stringify(renderedGroups)));
""".replace("__DECISION_TRACKING_HELPERS_PATH__", json.dumps(str(decision_tracking_helpers_path))).replace("__DECISION_TRACKING_PATH__", json.dumps(str(decision_tracking_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload[0]["ticker"] == "1623.TW"


def test_report_preview_panel_renders_mode_specific_preview_metrics():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    report_preview_helpers_path = STATIC_DIR / "report_preview_helpers.js"
    report_preview_tracking_helpers_path = STATIC_DIR / "report_preview_tracking_helpers.js"
    report_preview_rerun_helpers_path = STATIC_DIR / "report_preview_rerun_helpers.js"
    report_preview_path = STATIC_DIR / "report_preview_panel.js"
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
require(__REPORT_PREVIEW_HELPERS_PATH__);
require(__REPORT_PREVIEW_TRACKING_HELPERS_PATH__);
require(__REPORT_PREVIEW_RERUN_HELPERS_PATH__);
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
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__REPORT_PREVIEW_HELPERS_PATH__", json.dumps(str(report_preview_helpers_path))).replace("__REPORT_PREVIEW_TRACKING_HELPERS_PATH__", json.dumps(str(report_preview_tracking_helpers_path))).replace("__REPORT_PREVIEW_RERUN_HELPERS_PATH__", json.dumps(str(report_preview_rerun_helpers_path))).replace("__REPORT_PREVIEW_PATH__", json.dumps(str(report_preview_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["title"] == "2449 極短線交易預覽"
    assert "交易方向" in payload["decision"]
    assert "偏多 Long" in payload["decision"]
    assert "1-2週目標" in payload["targets"]
    assert "跌破 NT$292" in payload["targets"]
    assert payload["summary"] == "外資回補與突破月線"


def test_report_preview_panel_uses_decision_boundary_for_legacy_preview():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    report_preview_helpers_path = STATIC_DIR / "report_preview_helpers.js"
    report_preview_tracking_helpers_path = STATIC_DIR / "report_preview_tracking_helpers.js"
    report_preview_rerun_helpers_path = STATIC_DIR / "report_preview_rerun_helpers.js"
    report_preview_path = STATIC_DIR / "report_preview_panel.js"
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
require(__REPORT_PREVIEW_HELPERS_PATH__);
require(__REPORT_PREVIEW_TRACKING_HELPERS_PATH__);
require(__REPORT_PREVIEW_RERUN_HELPERS_PATH__);
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
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__REPORT_PREVIEW_HELPERS_PATH__", json.dumps(str(report_preview_helpers_path))).replace("__REPORT_PREVIEW_TRACKING_HELPERS_PATH__", json.dumps(str(report_preview_tracking_helpers_path))).replace("__REPORT_PREVIEW_RERUN_HELPERS_PATH__", json.dumps(str(report_preview_rerun_helpers_path))).replace("__REPORT_PREVIEW_PATH__", json.dumps(str(report_preview_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["title"] == "2449 報告建議"
    assert "報告建議" in payload["decision"]
    assert "投資建議" not in payload["title"]
    assert "仍需自行判斷" in payload["summary"]
    assert payload["rerunFinal"] == "重跑價值投資派報告結論"
    assert payload["rerunFull"] == "完整重跑價值投資派"


def test_report_preview_panel_uses_quality_policy_for_rerun_notice():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    report_preview_helpers_path = STATIC_DIR / "report_preview_helpers.js"
    report_preview_tracking_helpers_path = STATIC_DIR / "report_preview_tracking_helpers.js"
    report_preview_rerun_helpers_path = STATIC_DIR / "report_preview_rerun_helpers.js"
    report_preview_path = STATIC_DIR / "report_preview_panel.js"
    report_preview_js = report_preview_path.read_text(encoding="utf-8")
    history_panel_quality_helpers_js = (STATIC_DIR / "history_panel_quality_helpers.js").read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
require(__REPORT_PREVIEW_HELPERS_PATH__);
require(__REPORT_PREVIEW_TRACKING_HELPERS_PATH__);
require(__REPORT_PREVIEW_RERUN_HELPERS_PATH__);
require(__REPORT_PREVIEW_PATH__);
const el = () => ({ hidden: false, textContent: '', innerHTML: '', className: '', classList: { toggle() {} }, querySelector: () => null });
const elements = {
  workspace: el(),
  root: el(),
  mode: el(),
  title: el(),
  decisionRow: el(),
  targets: el(),
  summary: el(),
  staleNotice: el()
};
const panel = window.StockAgentReportPreviewPanel.create({
  elements,
  escapeHtml: value => String(value ?? ''),
  renderPipelineModeBadge: () => '',
  renderDataTrustBadge: () => '',
  pipelineMeta: () => ({ shortLabel: '價值投資派' }),
  normalizeRecommendation: value => String(value ?? ''),
  recommendationTone: () => ''
});
window.StockAgentReportQualityPolicy.reportNeedsRerun = () => false;
window.StockAgentReportQualityPolicy.reportRecommendedAction = () => ({ type: 'rerun_full_report', filename: 'policy-rerun.html' });
window.StockAgentReportQualityPolicy.reportRerunMessage = () => 'policy reason';
panel.show({
  ticker: '2330',
  filename: 'policy-rerun.html',
  pipeline_id: 'v1',
  recommendation: { recommendation: '持有' },
  decision_freshness: { requires_rerun: false }
});
window.StockAgentReportQualityPolicy = {
  reportNeedsRerun: () => true,
  reportRecommendedAction: () => null,
  reportRerunMessage: () => 'policy says current',
  reportConformanceStatus: () => '',
  evidenceExitGateVerdict: () => ''
};
const suppressedElements = {
  workspace: el(),
  root: el(),
  mode: el(),
  title: el(),
  decisionRow: el(),
  targets: el(),
  summary: el(),
  staleNotice: el()
};
const suppressedPanel = window.StockAgentReportPreviewPanel.create({
  elements: suppressedElements,
  escapeHtml: value => String(value ?? ''),
  renderPipelineModeBadge: () => '',
  renderDataTrustBadge: () => '',
  pipelineMeta: () => ({ shortLabel: '價值投資派' }),
  normalizeRecommendation: value => String(value ?? ''),
  recommendationTone: () => ''
});
suppressedPanel.show({
  ticker: '2330',
  filename: 'policy-current.html',
  pipeline_id: 'v1',
  recommendation: { recommendation: '持有' },
  analysis_text_stale: true,
  decision_freshness: { requires_rerun: true, requires_rerun_reason: 'raw reason' }
});
process.stdout.write(JSON.stringify({
  staleHidden: elements.staleNotice.hidden,
  staleText: elements.staleNotice.textContent,
  suppressedHidden: suppressedElements.staleNotice.hidden,
  suppressedText: suppressedElements.staleNotice.textContent,
  policyFallback: window.StockAgentReportQualityPolicy.reportRerunMessage({ analysis_text_stale: true })
}));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__REPORT_PREVIEW_HELPERS_PATH__", json.dumps(str(report_preview_helpers_path))).replace("__REPORT_PREVIEW_TRACKING_HELPERS_PATH__", json.dumps(str(report_preview_tracking_helpers_path))).replace("__REPORT_PREVIEW_RERUN_HELPERS_PATH__", json.dumps(str(report_preview_rerun_helpers_path))).replace("__REPORT_PREVIEW_PATH__", json.dumps(str(report_preview_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "StockAgentReportQualityPolicy" in report_preview_js
    assert "reportRecommendedAction?.(report)" in report_preview_js
    assert "reportRerunMessage" in report_preview_js
    assert "reportRerunMessage" in history_panel_quality_helpers_js
    assert "freshness.requires_rerun_reason" not in report_preview_js
    assert "freshness.requires_rerun" not in report_preview_js
    assert "report.analysis_text_stale" not in report_preview_js
    assert "report.analysis_text_stale_message" not in report_preview_js
    assert payload["staleHidden"] is False
    assert payload["staleText"] == "policy reason"
    assert payload["suppressedHidden"] is True
    assert payload["suppressedText"] == "policy says current"


def test_report_preview_helpers_render_quality_and_legacy_preview():
    report_quality_gate_policy_path = STATIC_DIR / "report_quality_gate_policy.js"
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    report_preview_helpers_path = STATIC_DIR / "report_preview_helpers.js"
    script = """
global.window = {};
require(__REPORT_QUALITY_GATE_POLICY_PATH__);
require(__REPORT_QUALITY_POLICY_PATH__);
require(__REPORT_PREVIEW_HELPERS_PATH__);
const helpers = window.StockAgentReportPreviewHelpers;
const escapeHtml = value => String(value ?? '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const badge = helpers.reportQualityBadge({
  report_conformance: { status: 'blocked', summary: '缺少必要章節 <A>' },
  evidence_exit_gate: { verdict: 'passed' }
}, escapeHtml);
const legacy = helpers.legacyPreview(
  { ticker: '2330' },
  { recommendation: '買入', current_price: 'NT$100', confidence: '8/10' },
  { normalizeRecommendation: value => value, recommendationTone: () => 'is-buy' }
);
process.stdout.write(JSON.stringify({ badge, legacy }));
""".replace("__REPORT_QUALITY_GATE_POLICY_PATH__", json.dumps(str(report_quality_gate_policy_path))).replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__REPORT_PREVIEW_HELPERS_PATH__", json.dumps(str(report_preview_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "報告符合性未通過" in payload["badge"]
    assert "&lt;A&gt;" in payload["badge"]
    assert payload["legacy"]["title"] == "2330 報告建議"
    assert payload["legacy"]["summary"] == "這份報告沒有可讀的一頁式摘要，可直接查看完整報告；報告建議仍需自行判斷。"


def test_report_quality_gate_policy_is_split_from_core_policy():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    report_quality_gate_policy_path = STATIC_DIR / "report_quality_gate_policy.js"
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    assert report_quality_gate_policy_path.exists()
    report_quality_gate_policy_js = report_quality_gate_policy_path.read_text(encoding="utf-8")
    report_quality_policy_js = report_quality_policy_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_GATE_POLICY_PATH__);
require(__REPORT_QUALITY_POLICY_PATH__);
const defaultAction = window.StockAgentReportQualityPolicy.reportQualityGateAction({
  report_conformance: { status: 'blocked', summary: 'split <summary>' },
  evidence_exit_gate: { verdict: 'caution', summary: 'gate summary' }
});
window.StockAgentReportQualityGatePolicy.reportQualityGateAction = () => ({
  label: 'split gate',
  tone: 'warning',
  detail: 'split detail'
});
const overrideAction = window.StockAgentReportQualityPolicy.reportQualityGateAction({});
process.stdout.write(JSON.stringify({ defaultAction, overrideAction }));
""".replace("__REPORT_QUALITY_GATE_POLICY_PATH__", json.dumps(str(report_quality_gate_policy_path))).replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert index_html.index("/static/report_quality_gate_policy.js") < index_html.index("/static/report_quality_policy.js")
    assert "StockAgentReportQualityGatePolicy" in report_quality_gate_policy_js
    assert "reportQualityGateAction(report, helpers = {})" in report_quality_gate_policy_js
    assert "StockAgentReportQualityGatePolicy?.reportQualityGateAction" in report_quality_policy_js
    assert "報告符合性未通過" in report_quality_gate_policy_js
    assert "證據抽查未通過" in report_quality_gate_policy_js
    assert "報告符合性未通過" not in report_quality_policy_js
    assert "證據抽查未通過" not in report_quality_policy_js
    assert payload["defaultAction"]["label"] == "報告符合性未通過"
    assert payload["defaultAction"]["detail"] == "split <summary>"
    assert payload["overrideAction"]["label"] == "split gate"
    assert payload["overrideAction"]["detail"] == "split detail"


def test_report_preview_quality_badge_uses_report_quality_policy_gate_action():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    report_preview_helpers_path = STATIC_DIR / "report_preview_helpers.js"
    report_quality_policy_js = report_quality_policy_path.read_text(encoding="utf-8")
    report_preview_helpers_js = report_preview_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportQualityGateAction = () => ({
  label: 'policy gate label',
  tone: 'critical',
  detail: 'policy <detail>'
});
require(__REPORT_PREVIEW_HELPERS_PATH__);
const helpers = window.StockAgentReportPreviewHelpers;
const escapeHtml = value => String(value ?? '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const badge = helpers.reportQualityBadge({ report_conformance: { status: 'passed' } }, escapeHtml);
process.stdout.write(JSON.stringify({ badge }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__REPORT_PREVIEW_HELPERS_PATH__", json.dumps(str(report_preview_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportQualityGateAction" in report_quality_policy_js
    assert "reportQualityGateAction?.(report)" in report_preview_helpers_js
    assert "reportConformanceStatus?.(report)" not in report_preview_helpers_js
    assert "evidenceExitGateVerdict?.(report)" not in report_preview_helpers_js
    assert "policy gate label" in payload["badge"]
    assert "policy &lt;detail&gt;" in payload["badge"]


def test_report_preview_tracking_helpers_render_waiting_and_short_return_states():
    tracking_helpers_path = STATIC_DIR / "report_preview_tracking_helpers.js"
    script = """
global.window = {
  StockAgentUi: {
    normalizeRecommendation: value => String(value || '')
  }
};
require(__TRACKING_HELPERS_PATH__);
const helpers = window.StockAgentReportPreviewTrackingHelpers;
const awaiting = {
  status: 'tracked',
  recommendation: '買入',
  initial_price: 100,
  latest_price: 100,
  return_pct: 0,
  target_12m_gap_pct: 8
};
const shortWin = {
  status: 'tracked',
  recommendation: '放空',
  initial_price: 100,
  latest_price: 92,
  return_pct: -8,
  target_12m_gap_pct: -3,
  snapshot_refreshed_at: '2026-07-09T09:30:00+08:00',
  summary: '放空後避開下跌'
};
const elements = {
  trackingRoot: { hidden: true },
  trackingLatest: { textContent: '' },
  trackingReturn: { textContent: '', className: '' },
  trackingGap: { textContent: '', className: '' },
  trackingSummary: { textContent: '' }
};
helpers.renderTracking(shortWin, elements);
process.stdout.write(JSON.stringify({
  awaiting: helpers.trackingView(awaiting),
  shortWin: helpers.trackingView(shortWin),
  rendered: {
    hidden: elements.trackingRoot.hidden,
    latest: elements.trackingLatest.textContent,
    returnText: elements.trackingReturn.textContent,
    returnTone: elements.trackingReturn.className,
    gapText: elements.trackingGap.textContent,
    summary: elements.trackingSummary.textContent
  }
}));
""".replace("__TRACKING_HELPERS_PATH__", json.dumps(str(tracking_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["awaiting"]["returnText"] == "待新價格"
    assert payload["awaiting"]["returnTone"] == "is-neutral"
    assert payload["awaiting"]["summary"] == "尚待新價格更新後計算建議後報酬。"
    assert payload["shortWin"]["returnText"] == "-8.00%"
    assert payload["shortWin"]["returnTone"] == "is-positive"
    assert payload["rendered"]["hidden"] is False
    assert payload["rendered"]["latest"] == "92"
    assert payload["rendered"]["returnText"] == "-8.00%"
    assert payload["rendered"]["returnTone"] == "is-positive"
    assert payload["rendered"]["gapText"] == "-3.00%"
    assert payload["rendered"]["summary"] == "放空後避開下跌"


def test_report_preview_rerun_helpers_configure_mode_specific_buttons():
    rerun_helpers_path = STATIC_DIR / "report_preview_rerun_helpers.js"
    script = """
global.window = {};
require(__RERUN_HELPERS_PATH__);
function button() {
  const span = { textContent: '' };
  return { hidden: false, querySelector: () => span, span };
}
const modeA = { rerunFinalBtn: button(), rerunFullBtn: button(), rerunModeBBtn: button() };
const modeB = { rerunFinalBtn: button(), rerunFullBtn: button(), rerunModeBBtn: button() };
const pipelineMeta = pipeline => ({ shortLabel: pipeline === 'v2' ? '成長突破派' : '價值投資派' });
window.StockAgentReportPreviewRerunHelpers.configureRerunButtons(modeA, 'v1', pipelineMeta);
window.StockAgentReportPreviewRerunHelpers.configureRerunButtons(modeB, 'v2', pipelineMeta);
process.stdout.write(JSON.stringify({
  modeAFinal: modeA.rerunFinalBtn.span.textContent,
  modeAFull: modeA.rerunFullBtn.span.textContent,
  modeBAction: modeA.rerunModeBBtn.span.textContent,
  modeBHiddenForA: modeA.rerunModeBBtn.hidden,
  modeBHiddenForB: modeB.rerunModeBBtn.hidden,
  modeBFinal: modeB.rerunFinalBtn.span.textContent
}));
""".replace("__RERUN_HELPERS_PATH__", json.dumps(str(rerun_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["modeAFinal"] == "重跑價值投資派報告結論"
    assert payload["modeAFull"] == "完整重跑價值投資派"
    assert payload["modeBAction"] == "產生模式 B 報告"
    assert payload["modeBHiddenForA"] is False
    assert payload["modeBHiddenForB"] is True
    assert payload["modeBFinal"] == "重跑成長突破派報告結論"


def test_tracking_equal_prices_show_zero_after_snapshot_refresh():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    history_panel_renderers_path = STATIC_DIR / "history_panel_renderers.js"
    history_panel_path = STATIC_DIR / "history_panel.js"
    report_preview_helpers_path = STATIC_DIR / "report_preview_helpers.js"
    report_preview_tracking_helpers_path = STATIC_DIR / "report_preview_tracking_helpers.js"
    report_preview_rerun_helpers_path = STATIC_DIR / "report_preview_rerun_helpers.js"
    report_preview_path = STATIC_DIR / "report_preview_panel.js"
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
require(__HISTORY_PANEL_RENDERERS_PATH__);
require(__HISTORY_PANEL_PATH__);
require(__REPORT_PREVIEW_HELPERS_PATH__);
require(__REPORT_PREVIEW_TRACKING_HELPERS_PATH__);
require(__REPORT_PREVIEW_RERUN_HELPERS_PATH__);
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
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path))).replace("__HISTORY_PANEL_RENDERERS_PATH__", json.dumps(str(history_panel_renderers_path))).replace("__HISTORY_PANEL_PATH__", json.dumps(str(history_panel_path))).replace("__REPORT_PREVIEW_HELPERS_PATH__", json.dumps(str(report_preview_helpers_path))).replace("__REPORT_PREVIEW_TRACKING_HELPERS_PATH__", json.dumps(str(report_preview_tracking_helpers_path))).replace("__REPORT_PREVIEW_RERUN_HELPERS_PATH__", json.dumps(str(report_preview_rerun_helpers_path))).replace("__REPORT_PREVIEW_PATH__", json.dumps(str(report_preview_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "待新價格" not in payload["history"]
    assert "追蹤 0.00%" in payload["history"]
    assert payload["previewReturn"] == "0.00%"
    assert payload["previewSummary"] == "建議後報酬 0.00%"


def test_history_list_uses_preview_list_metrics_for_non_investment_modes():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    history_panel_renderers_path = STATIC_DIR / "history_panel_renderers.js"
    history_panel_path = STATIC_DIR / "history_panel.js"
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
require(__HISTORY_PANEL_RENDERERS_PATH__);
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
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path))).replace("__HISTORY_PANEL_RENDERERS_PATH__", json.dumps(str(history_panel_renderers_path))).replace("__HISTORY_PANEL_PATH__", json.dumps(str(history_panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "偏多 Long" in result.stdout
    assert "NT$330" in result.stdout
    assert "跌破 NT$292" in result.stdout
    assert "<span>N/A</span>\\n                            <span>N/A</span>" not in result.stdout


def test_operator_workbench_surfaces_actionable_daily_workflow():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    report_quality_gate_policy_js = (STATIC_DIR / "report_quality_gate_policy.js").read_text(encoding="utf-8")
    report_quality_policy_js = (STATIC_DIR / "report_quality_policy.js").read_text(encoding="utf-8")
    operator_dashboard_actions_js = (STATIC_DIR / "operator_dashboard_actions.js").read_text(encoding="utf-8")
    operator_summary_quality_helpers_js = (STATIC_DIR / "operator_summary_quality_helpers.js").read_text(encoding="utf-8")
    operator_summary_helpers_js = (STATIC_DIR / "operator_summary_helpers.js").read_text(encoding="utf-8")
    operator_summary_js = (STATIC_DIR / "operator_summary_panel.js").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    history_panel_quality_helpers_js = (STATIC_DIR / "history_panel_quality_helpers.js").read_text(encoding="utf-8")
    history_panel_helpers_js = (STATIC_DIR / "history_panel_helpers.js").read_text(encoding="utf-8")
    watchlist_panel_js = (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")
    watchlist_helpers_js = (STATIC_DIR / "watchlist_panel_helpers.js").read_text(encoding="utf-8")
    watchlist_actions_js = (STATIC_DIR / "watchlist_panel_actions.js").read_text(encoding="utf-8")
    maintenance_js = (STATIC_DIR / "maintenance_panel.js").read_text(encoding="utf-8")
    maintenance_helpers_js = (STATIC_DIR / "maintenance_panel_helpers.js").read_text(encoding="utf-8")
    maintenance_notification_js = (STATIC_DIR / "maintenance_notification_delivery.js").read_text(encoding="utf-8")
    operator_css = (STATIC_DIR / "styles" / "operator_summary.css").read_text(encoding="utf-8")
    history_css = (STATIC_DIR / "styles" / "history_list.css").read_text(encoding="utf-8")
    watchlist_css = (STATIC_DIR / "styles" / "watchlist.css").read_text(encoding="utf-8")
    provider_sla_css = (STATIC_DIR / "styles" / "provider_sla.css").read_text(encoding="utf-8")
    provider_sla_controls_css_path = STATIC_DIR / "styles" / "provider_sla_controls.css"
    assert provider_sla_controls_css_path.exists()
    provider_sla_controls_css = provider_sla_controls_css_path.read_text(encoding="utf-8")

    assert 'id="operator-action-list"' in index_html
    assert 'id="operator-shift-summary"' in index_html
    assert "data-operator-shift-summary" in index_html
    assert 'role="status"' in index_html
    assert "今日待處理" in index_html
    assert "操作者值班摘要" in index_html
    assert "StockAgentOperatorSummaryQualityHelpers" in operator_summary_helpers_js
    assert "hasRefreshableDataTrustIssue" in operator_summary_quality_helpers_js
    assert "建議刷新資料" in operator_summary_quality_helpers_js
    assert "證據抽查未通過" in report_quality_gate_policy_js
    assert "證據抽查未通過" not in report_quality_policy_js
    assert "operatorActionItems" in operator_summary_helpers_js
    assert "setShift" in operator_summary_js
    assert "querySelectorAll('[data-operator-shift-summary]')" in operator_summary_js
    assert "下一步：" in operator_summary_js
    assert "toLocaleTimeString" in operator_summary_js
    assert "fetchWatchlist" in operator_summary_js
    assert "runWatchlist" in operator_summary_js
    assert "data-operator-action" in operator_summary_js
    assert "查看報告" in operator_summary_helpers_js
    assert "建立/更新報告" in operator_summary_helpers_js
    assert "watchlistActionDetail" in operator_summary_helpers_js
    assert "尚未建立報告" in operator_summary_helpers_js
    assert "資料更新需重跑" in operator_summary_helpers_js
    assert "待建立/更新報告" in operator_summary_helpers_js
    assert "rerun_reports" in operator_dashboard_actions_js
    assert "StockAgentOperatorDashboardActions" in operator_summary_js
    assert "dashboardActionItems" in operator_summary_js
    assert "dashboardText" in operator_summary_js
    assert "decision_queue" in operator_dashboard_actions_js
    assert "secondary_count" in operator_dashboard_actions_js
    assert "priority_score" in operator_dashboard_actions_js
    assert "model_route_warning" in operator_dashboard_actions_js
    assert "notification_delivery" in operator_dashboard_actions_js
    assert "fix_notification_delivery" in operator_dashboard_actions_js
    assert "通知通道" in operator_dashboard_actions_js
    assert "查看通知通道" in operator_dashboard_actions_js
    assert "operator_action_label" in operator_dashboard_actions_js
    assert "operator_action || mapped[0]" in operator_dashboard_actions_js
    assert "operator_action_label || item.action_label" in operator_dashboard_actions_js
    assert "次要待辦" in operator_dashboard_actions_js
    assert "來源：" in operator_dashboard_actions_js
    assert "report_repairs_required" in operator_dashboard_actions_js
    assert "repair_queue" in operator_dashboard_actions_js
    assert "manual_review" in operator_dashboard_actions_js
    assert "wait_provider_recovery" in operator_dashboard_actions_js
    assert "refresh_data_snapshot" in operator_dashboard_actions_js
    assert "refresh-report" in operator_dashboard_actions_js
    assert "rerun-report" in operator_dashboard_actions_js
    assert "rerun-all-reports" in operator_dashboard_actions_js
    assert "全部重跑" in operator_dashboard_actions_js
    assert "/rerun?scope=full_report" in operator_summary_js
    assert "系統維護" in operator_summary_helpers_js
    assert "data-target-tab" in operator_summary_js
    assert "data-target-panel" in operator_summary_js
    assert "targetPanelForAction" in operator_dashboard_actions_js
    assert "performance-panel" in operator_dashboard_actions_js
    assert "provider-sla-panel" in operator_dashboard_actions_js
    assert "api-quota-panel" in operator_dashboard_actions_js
    assert "market-screener-panel" in operator_dashboard_actions_js
    assert "watchlist-panel" in operator_dashboard_actions_js
    assert "maintenance-panel" in operator_dashboard_actions_js
    assert "scrollIntoView" in operator_summary_js
    assert "actionableActionCount" in operator_dashboard_actions_js
    assert "item.action !== 'monitor'" in operator_dashboard_actions_js


    assert "reportActionBadge" in history_panel_helpers_js
    assert "可直接使用" in history_panel_quality_helpers_js
    assert "建議刷新資料" in history_panel_quality_helpers_js
    assert "建議完整重跑" in history_panel_quality_helpers_js
    assert "暫勿採用" in history_panel_quality_helpers_js
    assert "history-action-badge" in history_panel_quality_helpers_js
    assert ".history-action-badge" in history_css

    assert "watchlistDailyBoard" in watchlist_helpers_js
    assert "今日工作台" in watchlist_helpers_js
    assert "fetchDailyDecisionDashboard" in watchlist_actions_js
    assert "decision_queue" in watchlist_helpers_js
    assert "secondary_count" in watchlist_helpers_js
    assert "priority_score" in watchlist_helpers_js
    assert "StockAgentDailyQueueContext?.sourceLabel" in watchlist_helpers_js
    assert "top.type !== 'monitor'" in watchlist_helpers_js
    assert "total > 0" in watchlist_helpers_js
    assert "最高優先" in watchlist_helpers_js
    assert "次要待辦" in watchlist_helpers_js
    assert "來源：" in watchlist_helpers_js
    assert "需處理" in watchlist_helpers_js
    assert "watchlist-daily-board" in watchlist_helpers_js
    assert ".watchlist-daily-board" in watchlist_css

    assert "<details" in index_html
    assert "maintenance-details" in index_html
    assert "健康摘要" in maintenance_helpers_js
    assert "通知通道" in maintenance_notification_js
    assert "retry_exhausted_count" in maintenance_notification_js
    assert "channel_counts" in maintenance_notification_js
    assert ".maintenance-details" not in provider_sla_css
    assert ".maintenance-details" in provider_sla_controls_css
    assert ".maintenance-actions" not in provider_sla_css
    assert ".maintenance-actions" in provider_sla_controls_css
    assert ".operator-shift-summary" in operator_css
    assert "grid-column: 1 / -1;" in operator_css
    assert ".operator-action-list" in operator_css
    assert ".operator-action-button" in operator_css


def test_candidate_dashboard_action_preserves_context_without_internal_scores():
    operator_actions_path = STATIC_DIR / "operator_dashboard_actions.js"
    script = """
global.window = {
  StockAgentDailyQueueContext: {
    sourceLabel: source => source === 'market_screener' ? '市場掃描' : source
  }
};
require(__OPERATOR_ACTIONS_PATH__);
const payload = {
  decision_queue: {
    items: [{
      type: 'review_candidate',
      ticker: '2408.TW',
      company_name: '南亞科',
      reason: '外資買超且記憶體報價回升',
      detail: '成交量同步放大',
      source: 'market_screener',
      score: 18680,
      priority_score: 420
    }, {
      type: 'review_candidate',
      ticker: '2408.TW',
      detail: '市場掃描候選',
      score: 12000,
      priority_score: 420
    }]
  }
};
const items = window.StockAgentOperatorDashboardActions.dashboardActionItems(payload);
process.stdout.write(JSON.stringify(items));
""".replace("__OPERATOR_ACTIONS_PATH__", json.dumps(str(operator_actions_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    item, missing_company = json.loads(result.stdout)

    assert item["action"] == "candidate-snapshot"
    assert item["label"] == "查看股票快照"
    assert item["type"] == "review_candidate"
    assert item["ticker"] == "2408.TW"
    assert item["companyName"] == "南亞科"
    assert item["title"] == "2408.TW · 南亞科"
    assert item["reason"] == "外資買超且記憶體報價回升"
    assert item["score"] == 18680
    assert "外資買超且記憶體報價回升" in item["detail"]
    assert "來源：市場掃描" in item["detail"]
    assert "score 18680.0" not in item["detail"]
    assert "priority_score 420" not in item["detail"]
    assert item.get("targetPanel") != "market-screener-panel"
    assert missing_company["companyName"] == ""
    assert missing_company["title"] == "2408.TW"
    assert missing_company["detail"] == "市場掃描候選"
    assert "score" not in missing_company["detail"]
    assert "priority_score" not in missing_company["detail"]


def test_candidate_actions_render_and_delegate_three_safe_next_steps():
    operator_actions_path = STATIC_DIR / "operator_dashboard_actions.js"
    operator_summary_path = STATIC_DIR / "operator_summary_panel.js"
    script = """
global.window = {};
let clickHandler;
const actionList = {
  innerHTML: '',
  addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; }
};
global.document = {
  getElementById: id => id === 'operator-action-list' ? actionList : null,
  querySelectorAll: () => []
};
window.StockAgentOperatorSummaryHelpers = {
  activeJobText: () => ({ tone: 'ok', value: '', detail: '' }),
  quotaText: () => ({ tone: 'ok', value: '', detail: '' }),
  trustText: () => ({ tone: 'ok', value: '', detail: '' }),
  rerunText: () => ({ tone: 'ok', value: '', detail: '' }),
  operatorActionItems: () => []
};
require(__OPERATOR_ACTIONS_PATH__);
require(__OPERATOR_SUMMARY_PATH__);
const calls = { snapshot: [], watchlist: [], analysis: [] };
const restored = [];
let currentButton;
const apiClient = {
  fetchActiveJobs: async () => ({}),
  fetchApiQuotas: async () => ({}),
  fetchReports: async () => ({ reports: [] }),
  fetchWatchlist: async () => ({ items: [] }),
  fetchDailyDecisionDashboard: async () => ({
    decision_queue: { items: [{
      type: 'review_candidate', ticker: '2408.TW', company_name: '南亞科',
      reason: '外資買超且記憶體報價回升', source: 'market_screener', score: 18680
    }] }
  })
};
const panel = window.StockAgentOperatorSummaryPanel.create({
  apiClient,
  ui: { escapeHtml: value => String(value ?? '') },
  notify: { error: () => {} },
  onCandidateSnapshot: async ticker => calls.snapshot.push([ticker, currentButton.disabled, currentButton.textContent]),
  onCandidateWatchlist: async ticker => calls.watchlist.push([ticker, currentButton.disabled, currentButton.textContent]),
  onCandidatePrepareAnalysis: async ticker => calls.analysis.push([ticker, currentButton.disabled, currentButton.textContent])
});
const click = async action => {
  const button = {
    dataset: { candidateAction: action, ticker: '2408.TW' },
    disabled: false,
    textContent: action,
  };
  currentButton = button;
  await clickHandler({ target: { closest: selector => selector === '[data-candidate-action]' ? button : null } });
  restored.push([action, button.disabled, button.textContent]);
};
(async () => {
  await panel.load();
  await click('candidate-snapshot');
  await click('candidate-watchlist');
  await click('candidate-prepare-analysis');
  process.stdout.write(JSON.stringify({ html: actionList.innerHTML, calls, restored }));
})();
""".replace("__OPERATOR_ACTIONS_PATH__", json.dumps(str(operator_actions_path))).replace("__OPERATOR_SUMMARY_PATH__", json.dumps(str(operator_summary_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    html = payload["html"]
    assert 'data-candidate-action="candidate-snapshot"' in html
    assert 'data-candidate-action="candidate-watchlist"' in html
    assert 'data-candidate-action="candidate-prepare-analysis"' in html
    assert html.count('data-ticker="2408.TW"') == 3
    assert "2408.TW" in html
    assert "南亞科" in html
    assert "外資買超且記憶體報價回升" in html
    assert payload["calls"] == {
        "snapshot": [["2408.TW", True, "載入快照中…"]],
        "watchlist": [["2408.TW", True, "加入追蹤中…"]],
        "analysis": [["2408.TW", True, "準備分析中…"]],
    }
    assert payload["restored"] == [
        ["candidate-snapshot", False, "candidate-snapshot"],
        ["candidate-watchlist", False, "candidate-watchlist"],
        ["candidate-prepare-analysis", False, "candidate-prepare-analysis"],
    ]


def test_candidate_actions_reject_missing_ticker_before_callback():
    operator_summary_path = STATIC_DIR / "operator_summary_panel.js"
    script = """
global.window = {
  StockAgentOperatorDashboardActions: {
    actionableActionCount: () => 0,
    candidateActionModel: item => item,
    dashboardActionItems: () => [],
    dashboardText: () => ({ tone: 'ok', value: '', detail: '' })
  },
  StockAgentOperatorSummaryHelpers: {}
};
let clickHandler;
const actionList = { addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; } };
global.document = {
  getElementById: id => id === 'operator-action-list' ? actionList : null,
  querySelectorAll: () => []
};
require(__OPERATOR_SUMMARY_PATH__);
const calls = [];
const errors = [];
window.StockAgentOperatorSummaryPanel.create({
  apiClient: {}, ui: {}, notify: { error: message => errors.push(message) },
  onCandidateSnapshot: async ticker => calls.push(`snapshot:${ticker}`),
  onCandidateWatchlist: async ticker => calls.push(`watchlist:${ticker}`),
  onCandidatePrepareAnalysis: async ticker => calls.push(`analysis:${ticker}`)
});
const click = async action => {
  const button = { dataset: { candidateAction: action, ticker: '' }, disabled: false, textContent: action };
  await clickHandler({ target: { closest: selector => selector === '[data-candidate-action]' ? button : null } });
};
(async () => {
  await click('candidate-snapshot');
  await click('candidate-watchlist');
  await click('candidate-prepare-analysis');
  process.stdout.write(JSON.stringify({ calls, errors }));
})();
""".replace("__OPERATOR_SUMMARY_PATH__", json.dumps(str(operator_summary_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["calls"] == []
    assert payload["errors"] == ["候選股票代號遺失，請重新整理後再試。"] * 3


def test_candidate_actions_notify_when_callback_is_missing_or_rejects():
    operator_summary_path = STATIC_DIR / "operator_summary_panel.js"
    script = """
global.window = {
  StockAgentOperatorDashboardActions: {
    actionableActionCount: () => 0,
    candidateActionModel: item => item,
    dashboardActionItems: () => [],
    dashboardText: () => ({ tone: 'ok', value: '', detail: '' })
  },
  StockAgentOperatorSummaryHelpers: {}
};
let clickHandler;
const actionList = { addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; } };
global.document = {
  getElementById: id => id === 'operator-action-list' ? actionList : null,
  querySelectorAll: () => []
};
require(__OPERATOR_SUMMARY_PATH__);
const calls = [];
const errors = [];
window.StockAgentOperatorSummaryPanel.create({
  apiClient: {}, ui: {}, notify: { error: message => errors.push(message) },
  onCandidateWatchlist: async ticker => {
    calls.push(`watchlist:${ticker}`);
    throw new Error('watchlist unavailable');
  },
  onCandidatePrepareAnalysis: async ticker => calls.push(`analysis:${ticker}`)
});
const click = async (action, text) => {
  const button = { dataset: { candidateAction: action, ticker: '2408.TW' }, disabled: false, textContent: text };
  await clickHandler({ target: { closest: selector => selector === '[data-candidate-action]' ? button : null } });
  return [button.disabled, button.textContent];
};
(async () => {
  const missingRestored = await click('candidate-snapshot', '查看股票快照');
  const callsAfterMissing = [...calls];
  const rejectedRestored = await click('candidate-watchlist', '加入追蹤');
  process.stdout.write(JSON.stringify({ calls, callsAfterMissing, errors, missingRestored, rejectedRestored }));
})();
""".replace("__OPERATOR_SUMMARY_PATH__", json.dumps(str(operator_summary_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["callsAfterMissing"] == []
    assert payload["calls"] == ["watchlist:2408.TW"]
    assert payload["errors"] == [
        "候選操作目前無法使用，請重新整理後再試。",
        "候選操作失敗，請稍後再試。",
    ]
    assert payload["missingRestored"] == [False, "查看股票快照"]
    assert payload["rejectedRestored"] == [False, "加入追蹤"]


def test_candidate_action_css_keeps_primary_full_width_and_controls_accessible():
    operator_css = (STATIC_DIR / "styles" / "operator_summary.css").read_text(encoding="utf-8")
    mobile_rules = operator_css.split("@media (max-width: 720px) {", 1)[1].split("@media (max-width: 360px)", 1)[0]
    mobile_candidate_rule = mobile_rules.split(".operator-candidate-actions {", 1)[1].split("}", 1)[0]

    assert ".operator-candidate-actions" in operator_css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in operator_css
    assert ".operator-candidate-actions .operator-action-button.is-primary" in operator_css
    assert "grid-column: 1 / -1;" in operator_css
    assert "min-height: 44px" in operator_css
    assert ".operator-action-button:focus-visible" in operator_css
    assert ".operator-action-button:disabled" in operator_css
    assert "max-width: 100%;" in operator_css
    assert "overflow-wrap: anywhere;" in operator_css
    assert "flex: 0 0 auto;" in mobile_candidate_rule
    assert "@media (max-width: 360px)" in operator_css


def test_candidate_next_actions_assets_use_shared_cache_buster():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")

    assert "/static/style.css?v=20260711-candidate-next-actions-v3" in index_html
    assert "/static/operator_dashboard_actions.js?v=20260711-candidate-next-actions-v3" in index_html
    assert "/static/operator_summary_panel.js?v=20260711-candidate-next-actions-v3" in index_html
    assert "/static/app_panels.js?v=20260711-candidate-next-actions-v3" in index_html
    assert "/static/styles/operator_summary.css?v=20260711-candidate-next-actions-v3" in style_css


def test_daily_workbench_renders_notification_attention_contexts():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    daily_context_path = STATIC_DIR / "daily_decision_queue_context.js"
    operator_actions_path = STATIC_DIR / "operator_dashboard_actions.js"
    watchlist_helpers_path = STATIC_DIR / "watchlist_panel_helpers.js"

    assert "/static/daily_decision_queue_context.js" in index_html
    assert index_html.index("/static/daily_decision_queue_context.js") < index_html.index("/static/operator_dashboard_actions.js")
    assert index_html.index("/static/daily_decision_queue_context.js") < index_html.index("/static/watchlist_panel_helpers.js")

    script = """
global.window = {};
require(__DAILY_CONTEXT_PATH__);
require(__OPERATOR_ACTIONS_PATH__);
require(__WATCHLIST_HELPERS_PATH__);
const payload = {
  decision_queue: {
    summary: { total_actionable: 1 },
    secondary_count: 0,
    items: [{
      source: 'notification_delivery',
      type: 'fix_notification_delivery',
      title: '通知通道發送異常',
      detail: '通知通道有 2 筆失敗',
      priority_score: 96,
      attention_contexts: [{
        delivery_key: 'notification_delivery.v1|telegram_webhook|provider-action',
        context: {
          source: 'provider_impact',
          ticker: 'NVDA',
          filename: 'nvda_provider.html',
          target_panel: 'provider-sla-panel',
          operator_action_label: '查看來源',
          queue_rank: 1,
          queue_displayed_count: 5,
          is_top_priority: true
        }
      }]
    }]
  }
};
const actions = window.StockAgentOperatorDashboardActions.dashboardActionItems(payload);
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ detail: actions[0].detail, board }));
""".replace("__DAILY_CONTEXT_PATH__", json.dumps(str(daily_context_path))).replace("__OPERATOR_ACTIONS_PATH__", json.dumps(str(operator_actions_path))).replace("__WATCHLIST_HELPERS_PATH__", json.dumps(str(watchlist_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    for expected in [
        "影響 NVDA",
        "報告 nvda_provider.html",
        "CTA 查看來源",
        "原始來源 資料來源 (provider_impact)",
        "隊列 1",
        "顯示 5",
        "最高優先",
    ]:
        assert expected in payload["detail"]
        assert expected in payload["board"]


def test_daily_queue_attention_context_uses_row_metadata_fallback():
    daily_context_path = STATIC_DIR / "daily_decision_queue_context.js"
    script = """
global.window = {};
require(__DAILY_CONTEXT_PATH__);
const text = window.StockAgentDailyQueueContext.attentionContextText({
  attention_contexts: [{
    delivery_key: 'notification_delivery.v1|telegram_webhook|provider-action',
    channel_id: 'telegram_webhook',
    delivery_status: 'failed',
    attempt_count: 2,
    last_error: 'temporary webhook timeout',
    context: {}
  }]
});
process.stdout.write(JSON.stringify({ text }));
""".replace("__DAILY_CONTEXT_PATH__", json.dumps(str(daily_context_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    for expected in ["通道 telegram_webhook", "狀態 failed", "嘗試 2"]:
        assert expected in payload["text"]
    assert "temporary webhook timeout" not in payload["text"]


def test_daily_queue_source_labels_are_shared_with_operator_actions():
    daily_context_path = STATIC_DIR / "daily_decision_queue_context.js"
    operator_actions_path = STATIC_DIR / "operator_dashboard_actions.js"
    watchlist_helpers_path = STATIC_DIR / "watchlist_panel_helpers.js"
    daily_context_js = daily_context_path.read_text(encoding="utf-8")
    operator_actions_js = operator_actions_path.read_text(encoding="utf-8")
    watchlist_helpers_js = watchlist_helpers_path.read_text(encoding="utf-8")

    assert "sourceLabel" in daily_context_js
    assert "StockAgentDailyQueueContext?.sourceLabel" in operator_actions_js
    assert "StockAgentDailyQueueContext?.sourceLabel" in watchlist_helpers_js
    assert "const actionSources" not in operator_actions_js
    assert "const sourceLabels" not in watchlist_helpers_js

    script = """
global.window = {};
require(__DAILY_CONTEXT_PATH__);
require(__OPERATOR_ACTIONS_PATH__);
require(__WATCHLIST_HELPERS_PATH__);
const payload = {
  decision_queue: {
    summary: { total_actionable: 1 },
    items: [{
      source: 'watchlist',
      type: 'run_watchlist',
      detail: '追蹤清單有 1 件待跑',
      priority_score: 72,
      attention_contexts: [{
        context: {
          source: 'watchlist',
          ticker: 'TSM',
          operator_action_label: '建立/更新報告'
        }
      }]
    }]
  }
};
const actions = window.StockAgentOperatorDashboardActions.dashboardActionItems(payload);
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({
  detail: actions[0].detail,
  board,
  sourceLabel: window.StockAgentDailyQueueContext.sourceLabel('watchlist'),
  sourceText: window.StockAgentDailyQueueContext.sourceText('watchlist'),
  monitorLabel: window.StockAgentDailyQueueContext.sourceLabel('monitor'),
  monitorText: window.StockAgentDailyQueueContext.sourceText('monitor')
}));
""".replace("__DAILY_CONTEXT_PATH__", json.dumps(str(daily_context_path))).replace("__OPERATOR_ACTIONS_PATH__", json.dumps(str(operator_actions_path))).replace("__WATCHLIST_HELPERS_PATH__", json.dumps(str(watchlist_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["sourceLabel"] == "追蹤清單"
    assert payload["sourceText"] == "追蹤清單 (watchlist)"
    assert payload["monitorLabel"] == "監控"
    assert payload["monitorText"] == "監控 (monitor)"
    assert "原始來源 追蹤清單 (watchlist)" in payload["detail"]
    assert "來源：追蹤清單" in payload["detail"]
    assert "原始來源 追蹤清單 (watchlist)" in payload["board"]
    assert "來源：追蹤清單" in payload["board"]


def test_daily_queue_attention_context_prefers_persisted_source_text():
    daily_context_path = STATIC_DIR / "daily_decision_queue_context.js"
    script = """
global.window = {};
require(__DAILY_CONTEXT_PATH__);
const text = window.StockAgentDailyQueueContext.attentionContextText({
  attention_contexts: [{
    delivery_key: 'notification_delivery.v1|partner_webhook|custom-source-action',
    context: {
      source: 'partner_feed',
      source_text: '合作來源 (partner_feed)',
      ticker: 'ACME'
    }
  }]
});
process.stdout.write(JSON.stringify({ text }));
""".replace("__DAILY_CONTEXT_PATH__", json.dumps(str(daily_context_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "影響 ACME" in payload["text"]
    assert "原始來源 合作來源 (partner_feed)" in payload["text"]
    assert "原始來源 partner_feed" not in payload["text"]


def test_daily_queue_attention_context_ignores_blank_persisted_source_display():
    daily_context_path = STATIC_DIR / "daily_decision_queue_context.js"
    script = """
global.window = {};
require(__DAILY_CONTEXT_PATH__);
const text = window.StockAgentDailyQueueContext.attentionContextText({
  attention_contexts: [{
    delivery_key: 'notification_delivery.v1|partner_webhook|blank-source-action',
    context: {
      source: 'provider_impact',
      source_label: '\\t',
      source_text: '   ',
      ticker: 'NVDA'
    }
  }]
});
process.stdout.write(JSON.stringify({ text }));
""".replace("__DAILY_CONTEXT_PATH__", json.dumps(str(daily_context_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "影響 NVDA" in payload["text"]
    assert "原始來源 資料來源 (provider_impact)" in payload["text"]
    assert "原始來源    " not in payload["text"]


def test_daily_queue_frontend_source_labels_trim_source_keys_before_lookup():
    daily_context_path = STATIC_DIR / "daily_decision_queue_context.js"
    script = """
global.window = {};
require(__DAILY_CONTEXT_PATH__);
const text = window.StockAgentDailyQueueContext.attentionContextText({
  attention_contexts: [{
    context: {
      source: ' provider_impact ',
      ticker: 'NVDA'
    }
  }]
});
process.stdout.write(JSON.stringify({
  sourceLabel: window.StockAgentDailyQueueContext.sourceLabel(' watchlist '),
  sourceText: window.StockAgentDailyQueueContext.sourceText('\\twatchlist\\n'),
  text
}));
""".replace("__DAILY_CONTEXT_PATH__", json.dumps(str(daily_context_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["sourceLabel"] == "追蹤清單"
    assert payload["sourceText"] == "追蹤清單 (watchlist)"
    assert "原始來源 資料來源 (provider_impact)" in payload["text"]
    assert " provider_impact " not in payload["text"]


def test_daily_queue_frontend_source_labels_match_backend_contract():
    from daily_decision_source_labels import SOURCE_LABELS

    daily_context_path = STATIC_DIR / "daily_decision_queue_context.js"
    script = """
global.window = {};
require(__DAILY_CONTEXT_PATH__);
process.stdout.write(JSON.stringify({
  sourceLabels: window.StockAgentDailyQueueContext.sourceLabels
}));
""".replace("__DAILY_CONTEXT_PATH__", json.dumps(str(daily_context_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["sourceLabels"] == SOURCE_LABELS


def test_operator_summary_helpers_build_status_and_fallback_actions_without_panel():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    operator_summary_quality_helpers_path = STATIC_DIR / "operator_summary_quality_helpers.js"
    operator_summary_helpers_path = STATIC_DIR / "operator_summary_helpers.js"
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
require(__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__);
require(__OPERATOR_SUMMARY_HELPERS_PATH__);
const helpers = window.StockAgentOperatorSummaryHelpers;
const providerOnly = helpers.trustText({ reports: [{
  ticker: '2330.TW',
  data_trust: { status: 'partial', reason_codes: ['provider_sla_critical'] }
}] });
const staleReport = {
  filename: '2330_v1.html',
  ticker: '2330.TW',
  pipeline_id: 'v1',
  data_trust: { status: 'stale', stale_sources: ['price'], reason_codes: ['source_stale:price'] }
};
const actions = helpers.operatorActionItems(
  { active_count: 0, jobs: [] },
  { services: [{ configured: true, usage: { observed_24h_errors: 0 } }] },
  { reports: [staleReport] },
  { items: [{ ticker: '2317.TW', enabled: true, decision_priority: 'high', decision_alert: { reason: 'missing_report' } }] }
);
process.stdout.write(JSON.stringify({
  providerOnly,
  quotaWarning: helpers.quotaText({ services: [{ configured: true, usage: { observed_quota_errors_since_reset: 2 } }] }),
  rerun: helpers.rerunText({ reports: [{ ticker: '2454.TW', decision_freshness: { requires_rerun: true } }] }),
  actions
}));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__", json.dumps(str(operator_summary_quality_helpers_path))).replace("__OPERATOR_SUMMARY_HELPERS_PATH__", json.dumps(str(operator_summary_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["providerOnly"]["value"] == "1 份來源提醒"
    assert "無需刷新/重跑" in payload["providerOnly"]["detail"]
    assert payload["quotaWarning"]["value"] == "LLM 健康警示"
    assert payload["rerun"]["value"] == "1 份需重跑"
    assert payload["actions"][0]["action"] == "refresh-report"
    assert payload["actions"][0]["filename"] == "2330_v1.html"
    assert payload["actions"][1]["action"] == "run-watchlist"
    assert "尚未建立報告" in payload["actions"][1]["detail"]


def test_operator_summary_fresh_count_uses_report_quality_policy():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    operator_summary_quality_helpers_path = STATIC_DIR / "operator_summary_quality_helpers.js"
    operator_summary_helpers_path = STATIC_DIR / "operator_summary_helpers.js"
    report_quality_policy_js = report_quality_policy_path.read_text(encoding="utf-8")
    operator_summary_quality_helpers_js = operator_summary_quality_helpers_path.read_text(encoding="utf-8")
    operator_summary_helpers_js = operator_summary_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportHasFreshData = report => report?.filename === 'policy-fresh.html';
require(__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__);
require(__OPERATOR_SUMMARY_HELPERS_PATH__);
const helpers = window.StockAgentOperatorSummaryHelpers;
const trust = helpers.trustText({ reports: [{
  filename: 'policy-fresh.html',
  ticker: '2330.TW',
  data_trust: { status: 'stale', stale_sources: ['price'], reason_codes: ['source_stale:price'] }
}] });
process.stdout.write(JSON.stringify({ trust }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__", json.dumps(str(operator_summary_quality_helpers_path))).replace("__OPERATOR_SUMMARY_HELPERS_PATH__", json.dumps(str(operator_summary_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportHasFreshData" in report_quality_policy_js
    assert "reportHasFreshData" in operator_summary_quality_helpers_js
    assert "report?.data_trust?.status === 'fresh'" not in operator_summary_helpers_js
    assert "資料新鮮 1 / 抽樣 1" in payload["trust"]["detail"]


def test_operator_summary_action_count_uses_report_recommended_action_boundary():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    operator_summary_quality_helpers_path = STATIC_DIR / "operator_summary_quality_helpers.js"
    operator_summary_helpers_path = STATIC_DIR / "operator_summary_helpers.js"
    operator_summary_helpers_js = operator_summary_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportRecommendedAction = () => null;
window.StockAgentReportQualityPolicy.requiresDataTrustAction = report => report?.filename === 'raw-action.html' || !report?.filename;
require(__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__);
require(__OPERATOR_SUMMARY_HELPERS_PATH__);
const helpers = window.StockAgentOperatorSummaryHelpers;
const suppressedTrust = helpers.trustText({ reports: [{
  filename: 'raw-action.html',
  ticker: '2454.TW',
  data_trust: { status: 'stale', stale_sources: ['price'] }
}] });
const legacyTrust = helpers.trustText({ reports: [{
  ticker: '2317.TW',
  data_trust: { status: 'stale', stale_sources: ['price'] }
}] });
process.stdout.write(JSON.stringify({ suppressedTrust, legacyTrust }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__", json.dumps(str(operator_summary_quality_helpers_path))).replace("__OPERATOR_SUMMARY_HELPERS_PATH__", json.dumps(str(operator_summary_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportRecommendedAction?.(report)" in operator_summary_helpers_js
    assert payload["suppressedTrust"]["value"] != "1 份需處理"
    assert payload["legacyTrust"]["value"] == "1 份需處理"


def test_operator_summary_report_action_refresh_uses_report_quality_policy():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    operator_summary_quality_helpers_path = STATIC_DIR / "operator_summary_quality_helpers.js"
    operator_summary_helpers_path = STATIC_DIR / "operator_summary_helpers.js"
    operator_summary_quality_helpers_js = operator_summary_quality_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportNeedsDataRefresh = () => false;
window.StockAgentReportQualityPolicy.reportRecommendedAction = () => ({ type: 'refresh_data_snapshot', filename: 'policy-refresh.html' });
require(__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__);
require(__OPERATOR_SUMMARY_HELPERS_PATH__);
const helpers = window.StockAgentOperatorSummaryHelpers;
const actions = helpers.operatorActionItems(
  { active_count: 0, jobs: [] },
  { services: [{ configured: true, usage: { observed_24h_errors: 0 } }] },
  { reports: [{
    filename: 'policy-refresh.html',
    ticker: '2330.TW',
    pipeline_id: 'v1',
    data_trust: { status: 'partial', reason_codes: ['provider_sla_critical'] }
  }] },
  { items: [] }
);
process.stdout.write(JSON.stringify({ action: actions[0] }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__", json.dumps(str(operator_summary_quality_helpers_path))).replace("__OPERATOR_SUMMARY_HELPERS_PATH__", json.dumps(str(operator_summary_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportRecommendedAction?.(report)" in operator_summary_quality_helpers_js
    assert "if (hasRefreshableDataTrustIssue(report)) return { title: '建議刷新資料'" not in operator_summary_quality_helpers_js
    assert payload["action"]["action"] == "refresh-report"
    assert payload["action"]["filename"] == "policy-refresh.html"


def test_operator_summary_report_action_rerun_detail_uses_report_quality_policy():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    operator_summary_quality_helpers_path = STATIC_DIR / "operator_summary_quality_helpers.js"
    operator_summary_helpers_path = STATIC_DIR / "operator_summary_helpers.js"
    operator_summary_quality_helpers_js = operator_summary_quality_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportNeedsRerun = () => false;
window.StockAgentReportQualityPolicy.reportRecommendedAction = () => ({ type: 'rerun_full_report', filename: 'policy-rerun.html' });
window.StockAgentReportQualityPolicy.reportRerunMessage = () => 'policy rerun detail';
require(__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__);
require(__OPERATOR_SUMMARY_HELPERS_PATH__);
const helpers = window.StockAgentOperatorSummaryHelpers;
const actions = helpers.operatorActionItems(
  { active_count: 0, jobs: [] },
  { services: [{ configured: true, usage: { observed_24h_errors: 0 } }] },
  { reports: [{
    filename: 'policy-rerun.html',
    ticker: '2330.TW',
    pipeline_id: 'v1',
    data_trust: { status: 'fresh' },
    decision_freshness: { status: 'current' }
  }] },
  { items: [] }
);
process.stdout.write(JSON.stringify({ action: actions[0] }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__", json.dumps(str(operator_summary_quality_helpers_path))).replace("__OPERATOR_SUMMARY_HELPERS_PATH__", json.dumps(str(operator_summary_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportRerunMessage" in operator_summary_quality_helpers_js
    assert "reportRecommendedAction?.(report)" in operator_summary_quality_helpers_js
    assert "detail: '結論與資料可能不同步'" not in operator_summary_quality_helpers_js
    assert payload["action"]["action"] == "view-report"
    assert payload["action"]["detail"] == "policy rerun detail"


def test_operator_summary_rerun_text_uses_report_recommended_action_policy():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    operator_summary_quality_helpers_path = STATIC_DIR / "operator_summary_quality_helpers.js"
    operator_summary_helpers_path = STATIC_DIR / "operator_summary_helpers.js"
    operator_summary_helpers_js = operator_summary_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportNeedsRerun = report => !report?.filename || report?.filename === 'raw-stale.html';
window.StockAgentReportQualityPolicy.reportRecommendedAction = report => (
  report?.filename === 'policy-rerun.html'
    ? { type: 'rerun_full_report', filename: report.filename }
    : null
);
require(__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__);
require(__OPERATOR_SUMMARY_HELPERS_PATH__);
const helpers = window.StockAgentOperatorSummaryHelpers;
const rerun = helpers.rerunText({ reports: [
  { filename: 'policy-rerun.html', ticker: '2330.TW', decision_freshness: { status: 'current' } },
  { filename: 'raw-stale.html', ticker: '2454.TW', decision_freshness: { requires_rerun: true } }
] });
const legacy = helpers.rerunText({ reports: [
  { ticker: '2317.TW', decision_freshness: { requires_rerun: true } }
] });
process.stdout.write(JSON.stringify({ rerun, legacy }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__", json.dumps(str(operator_summary_quality_helpers_path))).replace("__OPERATOR_SUMMARY_HELPERS_PATH__", json.dumps(str(operator_summary_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportRecommendedAction?.(report)" in operator_summary_helpers_js
    assert payload["rerun"]["value"] == "1 份需重跑"
    assert payload["rerun"]["detail"] == "2330.TW"
    assert payload["legacy"]["value"] == "1 份需重跑"
    assert payload["legacy"]["detail"] == "2317.TW"


def test_operator_summary_report_action_manual_review_uses_report_recommended_action():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    operator_summary_quality_helpers_path = STATIC_DIR / "operator_summary_quality_helpers.js"
    operator_summary_helpers_path = STATIC_DIR / "operator_summary_helpers.js"
    operator_summary_quality_helpers_js = operator_summary_quality_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportRecommendedAction = () => ({ type: 'manual_review', filename: 'policy-manual.html' });
window.StockAgentReportQualityPolicy.reportQualityGateAction = () => null;
require(__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__);
require(__OPERATOR_SUMMARY_HELPERS_PATH__);
const helpers = window.StockAgentOperatorSummaryHelpers;
const actions = helpers.operatorActionItems(
  { active_count: 0, jobs: [] },
  { services: [{ configured: true, usage: { observed_24h_errors: 0 } }] },
  { reports: [{
    filename: 'policy-manual.html',
    ticker: '2330.TW',
    pipeline_id: 'v1',
    data_trust: { status: 'fresh' }
  }] },
  { items: [] }
);
process.stdout.write(JSON.stringify({ action: actions[0] }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__", json.dumps(str(operator_summary_quality_helpers_path))).replace("__OPERATOR_SUMMARY_HELPERS_PATH__", json.dumps(str(operator_summary_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportRecommendedAction?.(report)" in operator_summary_quality_helpers_js
    assert payload["action"]["action"] == "view-report"
    assert payload["action"]["title"] == "2330.TW 需人工查看"
    assert payload["action"]["detail"] == "請開啟報告確認品質警示"


def test_operator_summary_report_action_limits_raw_refresh_fallback_to_legacy_reports():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    operator_summary_quality_helpers_path = STATIC_DIR / "operator_summary_quality_helpers.js"
    operator_summary_quality_helpers_js = operator_summary_quality_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportRecommendedAction = () => null;
window.StockAgentReportQualityPolicy.reportNeedsDataRefresh = report => report?.filename === 'raw-refresh.html' || !report?.filename;
window.StockAgentReportQualityPolicy.reportNeedsRerun = () => false;
require(__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__);
const helpers = window.StockAgentOperatorSummaryQualityHelpers;
const suppressedAction = helpers.reportAction({
  filename: 'raw-refresh.html',
  ticker: '2454.TW',
  data_trust: { status: 'stale', stale_sources: ['price'] }
});
const legacyAction = helpers.reportAction({
  ticker: '2317.TW',
  data_trust: { status: 'stale', stale_sources: ['price'] }
});
process.stdout.write(JSON.stringify({ suppressedAction, legacyAction }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__", json.dumps(str(operator_summary_quality_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportRecommendedAction?.(report)" in operator_summary_quality_helpers_js
    assert payload["suppressedAction"] is None
    assert payload["legacyAction"]["action"] == "refresh-report"
    assert payload["legacyAction"]["title"] == "建議刷新資料"


def test_operator_summary_report_action_limits_quality_gate_fallback_to_legacy_reports():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    operator_summary_quality_helpers_path = STATIC_DIR / "operator_summary_quality_helpers.js"
    operator_summary_quality_helpers_js = operator_summary_quality_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportRecommendedAction = () => null;
window.StockAgentReportQualityPolicy.reportQualityGateAction = () => ({
  label: 'raw operator gate',
  tone: 'critical',
  detail: 'raw operator detail'
});
require(__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__);
const helpers = window.StockAgentOperatorSummaryQualityHelpers;
const suppressedAction = helpers.reportAction({
  filename: 'raw-gate.html',
  ticker: '2454.TW',
  data_trust: { status: 'fresh' }
});
const legacyAction = helpers.reportAction({
  ticker: '2317.TW',
  data_trust: { status: 'fresh' }
});
process.stdout.write(JSON.stringify({ suppressedAction, legacyAction }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__", json.dumps(str(operator_summary_quality_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportQualityGateAction?.(report)" in operator_summary_quality_helpers_js
    assert payload["suppressedAction"] is None
    assert payload["legacyAction"]["title"] == "raw operator gate"
    assert payload["legacyAction"]["detail"] == "raw operator detail"


def test_operator_summary_report_action_quality_gate_uses_report_quality_policy():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    operator_summary_quality_helpers_path = STATIC_DIR / "operator_summary_quality_helpers.js"
    operator_summary_helpers_path = STATIC_DIR / "operator_summary_helpers.js"
    operator_summary_quality_helpers_js = operator_summary_quality_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportQualityGateAction = () => ({
  label: 'policy operator gate',
  tone: 'critical',
  detail: 'operator <detail>'
});
window.StockAgentReportQualityPolicy.reportRecommendedAction = report => ({ type: 'manual_review', filename: report.filename });
require(__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__);
require(__OPERATOR_SUMMARY_HELPERS_PATH__);
const helpers = window.StockAgentOperatorSummaryHelpers;
const actions = helpers.operatorActionItems(
  { active_count: 0, jobs: [] },
  { services: [{ configured: true, usage: { observed_24h_errors: 0 } }] },
  { reports: [{
    filename: 'policy-gate.html',
    ticker: '2330.TW',
    pipeline_id: 'v1',
    data_trust: { status: 'fresh' },
    report_conformance: { status: 'passed' },
    evidence_exit_gate: { verdict: 'passed' }
  }] },
  { items: [] }
);
process.stdout.write(JSON.stringify({ action: actions[0] }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__OPERATOR_SUMMARY_QUALITY_HELPERS_PATH__", json.dumps(str(operator_summary_quality_helpers_path))).replace("__OPERATOR_SUMMARY_HELPERS_PATH__", json.dumps(str(operator_summary_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportQualityGateAction?.(report)" in operator_summary_quality_helpers_js
    assert "reportConformanceStatus?.(report)" not in operator_summary_quality_helpers_js
    assert "evidenceExitGateVerdict?.(report)" not in operator_summary_quality_helpers_js
    assert payload["action"]["title"] == "2330.TW policy operator gate"
    assert payload["action"]["detail"] == "operator <detail>"


def test_maintenance_panel_renders_notification_delivery_audit_health():
    maintenance_panel_path = STATIC_DIR / "maintenance_panel.js"
    maintenance_helpers_path = STATIC_DIR / "maintenance_panel_helpers.js"
    maintenance_notification_path = STATIC_DIR / "maintenance_notification_delivery.js"
    daily_context_path = STATIC_DIR / "daily_decision_queue_context.js"
    script = """
global.window = {};
global.document = { addEventListener: () => {}, getElementById: () => null };
require(__DAILY_CONTEXT_PATH__);
require(__MAINTENANCE_NOTIFICATION_PATH__);
require(__MAINTENANCE_HELPERS_PATH__);
require(__MAINTENANCE_PANEL_PATH__);
const summaryEl = { textContent: '' };
const listEl = { innerHTML: '' };
const resultEl = { textContent: '' };
window.StockAgentMaintenancePanel.render({
  summary: {
    cache_db: { tables: { reports: 2 }, report_index_orphans: { orphan_rows: 0 } },
    task_db: { tables: { analysis_jobs: 4, provider_sla_events: 3 }, analysis_history: { stale_terminal_jobs: 0, orphan_events: 0 } }
  },
  notification_delivery: {
    health: 'warning',
    total_count: 3,
    failed_count: 2,
    retry_exhausted_count: 1,
    pending_count: 0,
    channel_counts: { telegram_webhook: 2, local: 1 },
    failure_reason_counts: { timeout: 2, auth: 1 },
    attention_contexts: [{
      delivery_key: 'notification_delivery.v1|telegram_webhook|provider-action',
      context: {
        ticker: 'NVDA',
        filename: 'nvda_provider.html',
        operator_action_label: '查看來源'
      }
    }]
  }
}, { summaryEl, listEl, resultEl, escapeHtml: value => String(value ?? '') });
process.stdout.write(JSON.stringify({ summary: summaryEl.textContent, list: listEl.innerHTML, result: resultEl.textContent }));
""".replace("__MAINTENANCE_PANEL_PATH__", json.dumps(str(maintenance_panel_path))).replace("__MAINTENANCE_HELPERS_PATH__", json.dumps(str(maintenance_helpers_path))).replace("__MAINTENANCE_NOTIFICATION_PATH__", json.dumps(str(maintenance_notification_path))).replace("__DAILY_CONTEXT_PATH__", json.dumps(str(daily_context_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "通知通道異常" in payload["summary"]
    assert "通知通道" in payload["list"]
    assert "失敗 2" in payload["list"]
    assert "重試耗盡 1" in payload["list"]
    assert "telegram_webhook 2" in payload["list"]
    assert "失敗原因 timeout 2" in payload["list"]
    assert "auth 1" in payload["list"]
    assert "影響 NVDA" in payload["list"]
    assert "報告 nvda_provider.html" in payload["list"]
    assert "CTA 查看來源" in payload["list"]
    assert "通知通道有失敗或重試耗盡項目" in payload["result"]


def test_maintenance_panel_helpers_render_summary_and_action_copy_without_panel():
    maintenance_helpers_path = STATIC_DIR / "maintenance_panel_helpers.js"
    maintenance_notification_path = STATIC_DIR / "maintenance_notification_delivery.js"
    script = """
global.window = {};
require(__MAINTENANCE_NOTIFICATION_PATH__);
require(__MAINTENANCE_HELPERS_PATH__);
const helpers = window.StockAgentMaintenancePanelHelpers;
const summary = {
  cache_db: { tables: { reports: 9 }, report_index_orphans: { orphan_rows: 2 } },
  task_db: { tables: { analysis_jobs: 4, provider_sla_events: 3 }, analysis_history: { stale_terminal_jobs: 1, orphan_events: 1 } }
};
const delivery = { health: 'warning', total_count: 5, failed_count: 1, retry_exhausted_count: 0, pending_count: 2, channel_counts: { local: 5 }, failure_reason_counts: { timeout: 1 } };
process.stdout.write(JSON.stringify({
  text: helpers.summaryText(summary, delivery),
  chips: helpers.storageChips(summary, delivery, value => String(value ?? '')),
  result: helpers.defaultResultText(delivery),
  action: helpers.actionMessage('analysis-history', { result: { deleted_jobs: 2, deleted_events: 3 } })
}));
""".replace("__MAINTENANCE_HELPERS_PATH__", json.dumps(str(maintenance_helpers_path))).replace("__MAINTENANCE_NOTIFICATION_PATH__", json.dumps(str(maintenance_notification_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "通知通道異常" in payload["text"]
    assert "4 筆可清理資料" in payload["text"]
    assert "報告索引" in payload["chips"]
    assert "任務紀錄" in payload["chips"]
    assert "來源健康紀錄" in payload["chips"]
    assert "通知通道" in payload["chips"]
    assert "通知通道有失敗或重試耗盡項目" in payload["result"]
    assert payload["action"] == "已清理任務 2 筆、事件 3 筆"


def test_market_screener_frontend_tab_is_wired():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    api_client_extensions_js = (STATIC_DIR / "api_client_extensions.js").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    app_panels_js = (STATIC_DIR / "app_panels.js").read_text(encoding="utf-8")
    market_screener_helpers_path = STATIC_DIR / "market_screener_helpers.js"
    assert market_screener_helpers_path.exists()
    market_screener_helpers_js = market_screener_helpers_path.read_text(encoding="utf-8")
    market_screener_js = (STATIC_DIR / "market_screener_panel.js").read_text(encoding="utf-8")
    market_screener_css = (STATIC_DIR / "styles" / "market_screener.css").read_text(encoding="utf-8")
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")

    assert 'id="home-tab-screener"' in index_html
    assert 'id="home-panel-screener"' in index_html
    assert 'id="market-screener-panel"' in index_html
    assert "/static/market_screener_helpers.js" in index_html
    assert "/static/market_screener_panel.js" in index_html
    assert index_html.index("/static/market_screener_helpers.js") < index_html.index("/static/market_screener_panel.js")
    assert "/static/styles/market_screener.css" in style_css
    assert "fetchMarketScreener" in api_client_extensions_js
    assert "runMarketScreener" in api_client_extensions_js
    assert "StockAgentMarketScreenerPanel" in app_panels_js
    assert "marketScreenerPanel.loadOnce" in app_js
    assert "StockAgentMarketScreenerHelpers" in market_screener_js
    assert "StockAgentMarketScreenerHelpers" in market_screener_helpers_js
    assert "Auto-Screener" in market_screener_helpers_js
    assert "market-screener-chip" in market_screener_js
    assert "股價大漲跌/成交量暴增" in market_screener_helpers_js
    assert "技術/量能異常" not in market_screener_js
    assert "scan_success" in market_screener_js
    assert "result.message" in market_screener_js
    assert "providers" in market_screener_js
    assert "資料源" in market_screener_js
    assert "company_name" in market_screener_helpers_js
    assert "data-screener-select" in market_screener_js
    assert "runWatchlist" in market_screener_js
    assert "模式 A" in market_screener_helpers_js and "模式 D" in market_screener_helpers_js
    assert "class MarketScreenerPanel" in market_screener_js
    assert "data-screener-sort" in market_screener_js
    assert "formatSignedMetric" in market_screener_js
    assert "setLoading" in market_screener_js
    assert "查無資料，請放寬條件" in market_screener_js
    assert "market-screener-range" in market_screener_js
    assert "market-screener-filter-select" in market_screener_js
    assert "fundamental_revenue_growth_yoy_min" in market_screener_helpers_js
    assert "technical_rsi_min" in market_screener_helpers_js
    assert "technical_macd_histogram_min" in market_screener_helpers_js
    assert "institutional_total_net_buy_min" in market_screener_helpers_js
    assert "market-screener-number" in market_screener_js
    assert "market-screener-pager" in market_screener_js
    assert "營收 YoY 下限" in market_screener_helpers_js
    assert "MACD 柱下限" in market_screener_helpers_js
    assert "法人總買超" in market_screener_helpers_js
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
    market_screener_helpers_path = STATIC_DIR / "market_screener_helpers.js"
    market_screener_path = STATIC_DIR / "market_screener_panel.js"
    script = """
global.window = {};
require(__MARKET_SCREENER_HELPERS_PATH__);
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
""".replace("__MARKET_SCREENER_HELPERS_PATH__", json.dumps(str(market_screener_helpers_path))).replace("__MARKET_SCREENER_PANEL_PATH__", json.dumps(str(market_screener_path)))
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
    history_panel_helpers_js = (STATIC_DIR / "history_panel_helpers.js").read_text(encoding="utf-8")
    report_quality_policy_js = (STATIC_DIR / "report_quality_policy.js").read_text(encoding="utf-8")
    history_panel_quality_helpers_js = (STATIC_DIR / "history_panel_quality_helpers.js").read_text(encoding="utf-8")
    operator_summary_quality_helpers_js = (STATIC_DIR / "operator_summary_quality_helpers.js").read_text(encoding="utf-8")
    operator_summary_helpers_js = (STATIC_DIR / "operator_summary_helpers.js").read_text(encoding="utf-8")
    ui_data_trust_js = (STATIC_DIR / "ui_data_trust.js").read_text(encoding="utf-8")

    assert "hasRefreshableDataTrustIssue" in report_quality_policy_js
    assert "provider_sla_critical" in report_quality_policy_js
    assert "status === 'stale' || status === 'partial'" not in report_quality_policy_js

    assert "providerSlaOnlyPartial" in ui_data_trust_js
    assert "本報告來源提醒" in ui_data_trust_js
    assert "本報告部分異常" not in ui_data_trust_js
    assert "StockAgentReportQualityPolicy" in history_panel_quality_helpers_js
    assert "StockAgentReportQualityPolicy" in operator_summary_quality_helpers_js
    assert "StockAgentHistoryPanelQualityHelpers" in history_panel_helpers_js
    assert "來源提醒" in history_panel_quality_helpers_js
    assert "來源需留意" not in history_panel_quality_helpers_js
    assert "isSourceNotice" in operator_summary_helpers_js
    assert "requiresDataTrustAction" in operator_summary_helpers_js
    assert "sourceNoticeReports" in operator_summary_helpers_js
    assert "StockAgentOperatorSummaryQualityHelpers" in operator_summary_helpers_js
    assert "來源提醒" in operator_summary_helpers_js
    assert "無需刷新/重跑" in operator_summary_helpers_js
    assert "份需留意" not in operator_summary_helpers_js


def test_ui_data_trust_provider_sla_notice_uses_report_quality_policy():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    ui_data_trust_path = STATIC_DIR / "ui_data_trust.js"
    report_quality_policy_js = report_quality_policy_path.read_text(encoding="utf-8")
    ui_data_trust_js = ui_data_trust_path.read_text(encoding="utf-8")
    script = """
global.window = {};
require(__REPORT_QUALITY_POLICY_PATH__);
const policyFailure = window.StockAgentReportQualityPolicy.hasProviderSlaOnlyPartial({
  data_trust: {
    status: 'partial',
    reason_codes: ['provider_sla_critical'],
    critical_failures: ['market_data']
  }
});
window.StockAgentReportQualityPolicy.dataTrustProviderSlaOnlyPartial = () => true;
require(__UI_DATA_TRUST_PATH__);
const labelWithOverride = window.StockAgentUiDataTrust.dataTrustLabel({
  status: 'partial',
  reason_codes: [],
  critical_failures: ['market_data']
});
process.stdout.write(JSON.stringify({ policyFailure, labelWithOverride }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__UI_DATA_TRUST_PATH__", json.dumps(str(ui_data_trust_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "dataTrustProviderSlaOnlyPartial" in report_quality_policy_js
    assert "StockAgentReportQualityPolicy" in ui_data_trust_js
    assert "codes.includes('provider_sla_critical')" not in ui_data_trust_js
    assert "critical_failures" not in ui_data_trust_js
    assert payload["policyFailure"] is False
    assert payload["labelWithOverride"] == "本報告來源提醒"


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
    provider_sla_helpers_js = (STATIC_DIR / "provider_sla_helpers.js").read_text(encoding="utf-8")
    api_quota_js = (STATIC_DIR / "api_quota_panel.js").read_text(encoding="utf-8")
    operator_summary_helpers_js = (STATIC_DIR / "operator_summary_helpers.js").read_text(encoding="utf-8")
    history_panel_helpers_js = (STATIC_DIR / "history_panel_helpers.js").read_text(encoding="utf-8")
    report_preview_helpers_js = (STATIC_DIR / "report_preview_helpers.js").read_text(encoding="utf-8")
    report_preview_tracking_helpers_js = (STATIC_DIR / "report_preview_tracking_helpers.js").read_text(encoding="utf-8")

    assert "<span>近期資料信任</span>" in index_html
    assert "無檢查樣本" in provider_sla_helpers_js
    assert "尚無檢查樣本，請查看 24 小時或全部紀錄" in provider_sla_helpers_js
    assert "全球市場脈絡" in provider_sla_helpers_js
    assert "國際新聞脈絡" in provider_sla_helpers_js
    assert "總經、匯率、利率與美股風險偏好" in provider_sla_helpers_js
    assert "國際重大新聞與供應鏈事件" in provider_sla_helpers_js
    assert "rowStateLabel" in provider_sla_helpers_js
    assert "row.level === 'ok' && !row.attempts" in provider_sla_helpers_js
    assert "quotaHealth" in api_quota_js
    assert "quotaHealth" in operator_summary_helpers_js
    assert "LLM/API 健康警示" in api_quota_js
    assert "LLM/API 本機觀測：" in api_quota_js
    assert "LLM/API 健康：" not in api_quota_js
    assert "LLM 本機觀測正常" in operator_summary_helpers_js
    assert "LLM 健康正常" not in operator_summary_helpers_js
    assert "is-${quotaHealth(service).tone}" in api_quota_js
    assert "awaitingTrackingPrice" in history_panel_helpers_js
    assert "待新價格" in history_panel_helpers_js
    assert "awaitingTrackingPrice" not in report_preview_helpers_js
    assert "awaitingTrackingPrice" in report_preview_tracking_helpers_js
    assert "尚待新價格" in report_preview_tracking_helpers_js


def test_provider_sla_shows_global_context_sources_before_first_sample():
    provider_sla_helpers_js = (STATIC_DIR / "provider_sla_helpers.js").read_text(encoding="utf-8")

    assert "EXPECTED_CONTEXT_SOURCES" in provider_sla_helpers_js
    assert "mergeExpectedContextRows" in provider_sla_helpers_js
    assert "global_market_context" in provider_sla_helpers_js
    assert "international_news_context" in provider_sla_helpers_js
    assert "hasSource" in provider_sla_helpers_js
    assert "尚未建立檢查樣本" in provider_sla_helpers_js


def test_provider_sla_copy_distinguishes_core_and_enrichment_critical_sources():
    provider_sla_helpers_js = (STATIC_DIR / "provider_sla_helpers.js").read_text(encoding="utf-8")

    assert "CORE_ANALYSIS_SOURCES" in provider_sla_helpers_js
    assert "sourceIsCore" in provider_sla_helpers_js
    assert "核心資料可能影響分析" in provider_sla_helpers_js
    assert "補充資料不穩" in provider_sla_helpers_js
    assert "核心分析仍可進行" in provider_sla_helpers_js


def test_provider_sla_helpers_group_rows_and_copy_without_panel():
    provider_sla_helpers_path = STATIC_DIR / "provider_sla_helpers.js"
    script = """
global.window = {};
require(__PROVIDER_SLA_HELPERS_PATH__);
const helpers = window.StockAgentProviderSlaHelpers;
const providers = [{
  source: 'market_data',
  provider: 'primary',
  attempts: 4,
  availability_attempts: 4,
  success_count: 1,
  skipped_fresh_cache_count: 0,
  degraded_enrichment_count: 0,
  total_records: 1,
  alert_level: 'critical',
  last_status: 'error'
}];
const rows = helpers.mergeExpectedContextRows(helpers.groupedProviderRows(providers, 'last_24h'));
const market = rows.find(row => row.source === 'market_data');
const globalContext = rows.find(row => row.source === 'global_market_context');
process.stdout.write(JSON.stringify({
  marketLevel: market.level,
  marketState: helpers.rowStateLabel(market),
  marketInsight: helpers.insightText(market),
  summary: helpers.summaryText(rows, '近 24 小時', providers),
  visibleSources: helpers.visibleProviderRows(rows).map(row => row.source),
  globalState: helpers.rowStateLabel(globalContext),
  globalInsight: helpers.insightText(globalContext)
}));
""".replace("__PROVIDER_SLA_HELPERS_PATH__", json.dumps(str(provider_sla_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["marketLevel"] == "critical"
    assert payload["marketState"] == "核心資料可能影響分析"
    assert "可能需要稍後重跑" in payload["marketInsight"]
    assert "核心資料可能影響分析" in payload["summary"]
    assert "global_market_context" in payload["visibleSources"]
    assert payload["globalState"] == "無檢查樣本"
    assert "尚未建立檢查樣本" in payload["globalInsight"]


def test_provider_sla_groups_do_not_escalate_healthy_fallbacks_to_critical():
    provider_sla_helpers_path = STATIC_DIR / "provider_sla_helpers.js"
    provider_sla_path = STATIC_DIR / "provider_sla_panel.js"
    script = """
global.window = {};
require(__PROVIDER_SLA_HELPERS_PATH__);
require(__PROVIDER_SLA_PANEL_PATH__);
const providers = [
  {
    source: 'market_data',
    provider: 'taiwan_yfinance_finmind',
    attempts: 20,
    availability_attempts: 20,
    success_count: 20,
    skipped_fresh_cache_count: 0,
    degraded_enrichment_count: 0,
    total_records: 20,
    alert_level: 'ok',
    last_status: 'success'
  },
  {
    source: 'market_data',
    provider: 'FMP stable quote',
    attempts: 20,
    availability_attempts: 20,
    success_count: 0,
    skipped_fresh_cache_count: 0,
    degraded_enrichment_count: 0,
    total_records: 0,
    alert_level: 'critical',
    last_status: 'unavailable'
  },
  {
    source: 'recent_catalysts',
    provider: 'Recent catalysts providers',
    attempts: 10,
    availability_attempts: 10,
    success_count: 10,
    skipped_fresh_cache_count: 0,
    degraded_enrichment_count: 0,
    total_records: 10,
    alert_level: 'ok',
    last_status: 'success'
  },
  {
    source: 'recent_catalysts',
    provider: 'PTT Stock',
    attempts: 10,
    availability_attempts: 10,
    success_count: 0,
    skipped_fresh_cache_count: 0,
    degraded_enrichment_count: 0,
    total_records: 0,
    alert_level: 'critical',
    last_status: 'unavailable'
  },
  {
    source: 'dynamic_peer_metrics',
    provider: 'FinMind/yfinance',
    attempts: 100,
    availability_attempts: 100,
    success_count: 60,
    skipped_fresh_cache_count: 0,
    degraded_enrichment_count: 0,
    total_records: 120,
    alert_level: 'warning',
    last_status: 'success'
  }
];
const rows = window.StockAgentProviderSlaPanel.groupedProviderRows(providers, 'last_24h');
const listEl = { innerHTML: '' };
window.StockAgentProviderSlaPanel.render(
  { providers },
  { summaryEl: { textContent: '' }, listEl, windowEl: { value: 'last_24h' }, escapeHtml: value => String(value ?? '') }
);
process.stdout.write(JSON.stringify({ rows: rows.map(row => ({ source: row.source, level: row.level })), html: listEl.innerHTML }));
""".replace("__PROVIDER_SLA_HELPERS_PATH__", json.dumps(str(provider_sla_helpers_path))).replace("__PROVIDER_SLA_PANEL_PATH__", json.dumps(str(provider_sla_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    rows = {row["source"]: row["level"] for row in payload["rows"]}

    assert rows["market_data"] == "ok"
    assert rows["recent_catalysts"] == "ok"
    assert rows["dynamic_peer_metrics"] == "ok"
    assert "不可用" not in payload["html"]
    assert "尚無紀錄 · 未設定" not in payload["html"]


def test_ops_provider_sla_loads_enough_rows_for_whole_system_status():
    ops_workspace_js = (STATIC_DIR / "ops_workspace.js").read_text(encoding="utf-8")
    ops_workspace_panels_js = (STATIC_DIR / "ops_workspace_panels.js").read_text(encoding="utf-8")

    assert "limit: 100" in ops_workspace_panels_js
    assert "limit: 12" not in ops_workspace_js


def test_decision_tracking_controls_and_target_statuses_are_wired():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    app_panels_js = (STATIC_DIR / "app_panels.js").read_text(encoding="utf-8")
    api_client_extensions_js = (STATIC_DIR / "api_client_extensions.js").read_text(encoding="utf-8")
    history_workspace_js = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")
    history_workspace_actions_js = (STATIC_DIR / "history_workspace_actions.js").read_text(encoding="utf-8")
    history_workspace_panels_js = (STATIC_DIR / "history_workspace_panels.js").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    history_panel_helpers_js = (STATIC_DIR / "history_panel_helpers.js").read_text(encoding="utf-8")
    history_panel_renderers_js = (STATIC_DIR / "history_panel_renderers.js").read_text(encoding="utf-8")
    decision_tracking_helpers_js = (STATIC_DIR / "decision_tracking_helpers.js").read_text(encoding="utf-8")
    decision_tracking_css = (STATIC_DIR / "styles" / "decision_tracking.css").read_text(encoding="utf-8")

    assert 'id="decision-tracking-refresh"' in index_html
    assert 'id="decision-tracking-summary"' in index_html
    assert 'id="decision-tracking-density"' in index_html
    assert 'id="decision-tracking-stock-snapshot-panel"' in index_html
    assert "decisionTrackingStockSnapshotPanel" in app_panels_js
    assert "fetchDecisionTracking" in api_client_extensions_js
    assert "saveDecisionTrackingItem" in api_client_extensions_js
    assert "deleteDecisionTrackingItem" in api_client_extensions_js
    assert "refreshDecisionTracking" in api_client_extensions_js

    assert "trackedTickers" in history_workspace_js
    assert "toggleDecisionTracking" in history_workspace_actions_js
    assert "setTrackingCompact" in history_workspace_js
    assert "previewCompactMode" in history_workspace_js
    assert "decision-track-toggle" in history_panel_renderers_js
    assert "加入追蹤" in history_panel_renderers_js
    assert "取消追蹤" in history_panel_renderers_js
    assert "renderTrackingGroups" in history_panel_js
    assert "tracking-stock-group" in history_panel_renderers_js
    assert "tracking-stock-snapshot-button" in history_panel_renderers_js
    assert "data-tracking-snapshot" in history_panel_renderers_js
    assert "onOpenSnapshot" in history_panel_js
    assert "trackingSnapshotPanel" in history_workspace_js
    assert "StockAgentHistoryWorkspaceActions" in history_workspace_js
    assert "StockAgentStockSnapshotPanel.create" in history_workspace_panels_js
    assert "tracking-report-card" in history_panel_renderers_js
    assert "tracking-group-reports" in history_panel_renderers_js
    assert "高密度三模式比較" in history_panel_renderers_js
    assert "/static/history_workspace_panels.js" in index_html
    assert "/static/history_workspace_actions.js" in index_html
    assert index_html.index("/static/history_workspace_panels.js") < index_html.index("/static/history_workspace_actions.js")
    assert index_html.index("/static/history_workspace_actions.js") < index_html.index("/static/history_workspace.js")
    assert "/static/history_workspace.js?v=20260705-tracking-snapshot" in index_html
    assert "mergeTrackingReports" in history_workspace_js
    assert "trackingPayload" in history_workspace_js
    assert "item.latest_reports" in history_workspace_js
    assert "window.StockAgentUi?.pipelineModeLabel" in history_panel_helpers_js
    assert "latest_reports" in decision_tracking_helpers_js
    assert "tracking-stock-cell" in history_panel_renderers_js
    assert "tracking-company-name" in history_panel_renderers_js
    assert "tracking-report-cell" in history_panel_renderers_js
    assert "tracking-report-date" in history_panel_renderers_js

    assert "targetComparisonCell" in history_panel_helpers_js
    assert "3月目標" in history_panel_helpers_js
    assert "6月目標" in history_panel_helpers_js
    assert "12月目標" in history_panel_helpers_js
    assert "低於目標" in history_panel_helpers_js
    assert "接近目標" in history_panel_helpers_js
    assert "已高於目標" in history_panel_helpers_js
    assert "tracking-target-cell" in history_panel_renderers_js
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


def test_history_workspace_panel_helper_wires_tracking_changes():
    history_workspace_panels_path = STATIC_DIR / "history_workspace_panels.js"
    script = """
global.window = {
  StockAgentHistoryFilters: { create: () => ({}) },
  StockAgentHistoryPanel: { create: () => ({
    setTrackedTickers: tickers => { global.__seen = Array.from(tickers); }
  }) },
  StockAgentReportPreviewPanel: { create: () => ({}) },
  StockAgentReportComparePanel: { create: () => ({}) },
  StockAgentStockSnapshotPanel: { create: () => ({}) },
  StockAgentDecisionTrackingPanel: {
    create: options => { options.onChange(new Set(['2330.TW'])); return {}; }
  }
};
require(__HISTORY_WORKSPACE_PANELS_PATH__);
let callbackTickers = [];
window.StockAgentHistoryWorkspacePanels.create({
  apiClient: {},
  ui: {},
  elements: {},
  notify: {},
  onTrackedTickersChange: tickers => { callbackTickers = Array.from(tickers); }
});
process.stdout.write(JSON.stringify({ panel: global.__seen, callback: callbackTickers }));
""".replace("__HISTORY_WORKSPACE_PANELS_PATH__", json.dumps(str(history_workspace_panels_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["panel"] == ["2330.TW"]
    assert payload["callback"] == ["2330.TW"]


def test_history_workspace_actions_refresh_preview_snapshot_state():
    history_workspace_actions_path = STATIC_DIR / "history_workspace_actions.js"
    script = """
global.window = { StockAgentReportRerun: { rerunPreviewReport: () => {} } };
require(__HISTORY_WORKSPACE_ACTIONS_PATH__);
const calls = [];
const label = { textContent: '刷新資料快照' };
const button = { disabled: false, querySelector: selector => selector === 'span' ? label : null };
let previewReport = {
  filename: '2330_v1.html',
  data_trust: { status: 'stale' },
  data_snapshot_filename: 'old.data.json',
  analysis_text_stale: true,
  analysis_text_stale_message: 'old',
  decision_freshness: { status: 'old' }
};
let savedReport = null;
const actions = window.StockAgentHistoryWorkspaceActions.create({
  apiClient: {
    refreshReportDataSnapshot: async filename => ({
      data_trust: { status: 'fresh' },
      data_filename: `${filename}.data.json`,
      analysis_text_stale: false,
      analysis_text_stale_message: 'fresh',
      decision_freshness: { status: 'current' },
      refresh_diff: { summary: ['價格已更新', '基本面已核對', '多餘項目', '忽略項目'] }
    })
  },
  notify: {
    success: message => calls.push(`success:${message}`),
    error: message => calls.push(`error:${message}`),
    confirm: async () => true
  },
  elements: { previewRefreshDataBtn: button },
  decisionTrackingPanel: { toggleDecisionTracking: async () => {} },
  getPreviewReport: () => previewReport,
  setPreviewReport: value => { previewReport = value; },
  getReport: () => previewReport,
  setReport: (filename, value) => { savedReport = { filename, value }; },
  showReportPreview: filename => calls.push(`show:${filename}`),
  hideReportPreview: () => calls.push('hide'),
  loadHistory: async () => calls.push('loadHistory'),
  refreshProviderSlaIfLoaded: async () => calls.push('providerSla'),
  openReport: () => {}
});
(async () => {
  await actions.refreshPreviewDataSnapshot();
  process.stdout.write(JSON.stringify({
    calls,
    buttonDisabled: button.disabled,
    label: label.textContent,
    savedReport,
    previewReport
  }));
})();
""".replace("__HISTORY_WORKSPACE_ACTIONS_PATH__", json.dumps(str(history_workspace_actions_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["buttonDisabled"] is False
    assert payload["label"] == "刷新資料快照"
    assert payload["savedReport"]["filename"] == "2330_v1.html"
    assert payload["savedReport"]["value"]["data_trust"] == {"status": "fresh"}
    assert payload["previewReport"]["analysis_text_stale"] is False
    assert payload["previewReport"]["analysis_text_stale_message"] == "fresh"
    assert payload["previewReport"]["decision_freshness"] == {"status": "current"}
    assert payload["calls"][:3] == ["show:2330_v1.html", "loadHistory", "providerSla"]
    assert payload["calls"][-1] == "success:資料快照已刷新：價格已更新；基本面已核對；多餘項目"


def test_history_panel_helpers_render_quality_and_target_chips():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    script = """
global.window = {
  StockAgentUi: {
    normalizeRecommendation: value => String(value || ''),
    pipelineModeLabel: value => `模式 ${value}`
  }
};
require(__REPORT_QUALITY_POLICY_PATH__);
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
const helpers = window.StockAgentHistoryPanelHelpers;
const escapeHtml = value => String(value ?? '');
const stale = helpers.reportActionBadge({
  data_trust: { status: 'stale', reason_codes: ['source_stale:price'], stale_sources: ['price'] }
}, escapeHtml);
const staleNote = helpers.trackingActionNote({
  data_trust: { status: 'stale', reason_codes: ['source_stale:price'], stale_sources: ['price'] }
}, escapeHtml);
const providerOnly = helpers.reportActionBadge({
  data_trust: { status: 'partial', reason_codes: ['provider_sla_critical'] }
}, escapeHtml);
const providerOnlyNote = helpers.trackingActionNote({
  data_trust: { status: 'partial', reason_codes: ['provider_sla_critical'] }
}, escapeHtml);
const target = helpers.targetComparisonCell({
  target_3m: 105,
  target_comparisons: { target_3m: { status: 'near_target', label: '接近目標', gap_pct: -1.23, target: 105 } }
}, 'target_3m', escapeHtml);
process.stdout.write(JSON.stringify({
  stale,
  staleNote,
  providerOnly,
  providerOnlyNote,
  target,
  tone: helpers.trackingSummaryTone({ target_comparisons: { target_12m: { status: 'below_target' } } })
}));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "建議刷新資料" in payload["stale"]
    assert "需刷新資料" in payload["staleNote"]
    assert "來源提醒" in payload["providerOnly"]
    assert payload["providerOnlyNote"] == ""
    assert "3月" in payload["target"]
    assert "接近" in payload["target"]
    assert payload["tone"] == "is-below-target"


def test_history_report_action_badge_quality_gate_uses_report_quality_policy():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    history_panel_quality_helpers_js = history_panel_quality_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {
  StockAgentUi: {
    normalizeRecommendation: value => String(value || ''),
    pipelineModeLabel: value => `模式 ${value}`
  }
};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportQualityGateAction = () => ({
  label: 'policy history gate',
  tone: 'critical',
  detail: 'history <detail>'
});
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
const helpers = window.StockAgentHistoryPanelHelpers;
const escapeHtml = value => String(value ?? '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const badge = helpers.reportActionBadge({
  data_trust: { status: 'fresh' },
  report_conformance: { status: 'passed' }
}, escapeHtml);
process.stdout.write(JSON.stringify({ badge }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportQualityGateAction?.(report)" in history_panel_quality_helpers_js
    assert "reportConformanceStatus?.(report)" not in history_panel_quality_helpers_js
    assert "evidenceExitGateVerdict?.(report)" not in history_panel_quality_helpers_js
    assert "policy history gate" in payload["badge"]
    assert "history &lt;detail&gt;" in payload["badge"]


def test_history_tracking_refresh_note_uses_report_quality_policy():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    report_quality_policy_js = report_quality_policy_path.read_text(encoding="utf-8")
    history_panel_quality_helpers_js = history_panel_quality_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {
  StockAgentUi: {
    normalizeRecommendation: value => String(value || ''),
    pipelineModeLabel: value => `模式 ${value}`
  }
};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportNeedsDataRefresh = () => false;
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
const helpers = window.StockAgentHistoryPanelHelpers;
const escapeHtml = value => String(value ?? '');
const note = helpers.trackingActionNote({
  data_trust: { status: 'partial', reason_codes: ['missing_data_trust_snapshot'] }
}, escapeHtml);
process.stdout.write(JSON.stringify({ note }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportNeedsDataRefresh" in report_quality_policy_js
    assert "reportNeedsDataRefresh" in history_panel_quality_helpers_js
    assert "status === 'partial' && !hasProviderSlaOnlyPartial(report)" not in history_panel_quality_helpers_js
    assert payload["note"] == ""


def test_history_report_action_badge_refresh_uses_report_quality_policy():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    history_panel_quality_helpers_js = history_panel_quality_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {
  StockAgentUi: {
    normalizeRecommendation: value => String(value || ''),
    pipelineModeLabel: value => `模式 ${value}`
  }
};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportNeedsDataRefresh = () => false;
window.StockAgentReportQualityPolicy.reportRecommendedAction = () => ({ type: 'refresh_data_snapshot', filename: 'policy-refresh.html' });
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
const helpers = window.StockAgentHistoryPanelHelpers;
const escapeHtml = value => String(value ?? '');
const badge = helpers.reportActionBadge({
  data_trust: { status: 'partial', reason_codes: ['provider_sla_critical'] }
}, escapeHtml);
process.stdout.write(JSON.stringify({ badge }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportRecommendedAction?.(report)" in history_panel_quality_helpers_js
    assert "hasRefreshableDataTrustIssue(report))" not in history_panel_quality_helpers_js
    assert "建議刷新資料" in payload["badge"]


def test_history_report_action_badge_manual_review_uses_report_recommended_action():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    history_panel_quality_helpers_js = history_panel_quality_helpers_path.read_text(encoding="utf-8")
    script = """
global.window = {
  StockAgentUi: {
    normalizeRecommendation: value => String(value || ''),
    pipelineModeLabel: value => `模式 ${value}`
  }
};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportRecommendedAction = () => ({ type: 'manual_review', filename: 'manual.html' });
window.StockAgentReportQualityPolicy.reportQualityGateAction = () => null;
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
const helpers = window.StockAgentHistoryPanelHelpers;
const escapeHtml = value => String(value ?? '');
const badge = helpers.reportActionBadge({
  filename: 'manual.html',
  data_trust: { status: 'fresh' }
}, escapeHtml);
process.stdout.write(JSON.stringify({ badge }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "reportRecommendedAction?.(report)" in history_panel_quality_helpers_js
    assert "需人工查看" in payload["badge"]
    assert "請開啟報告確認品質警示" in payload["badge"]


def test_history_report_action_badge_limits_raw_refresh_fallback_to_legacy_reports():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    script = """
global.window = {
  StockAgentUi: {
    normalizeRecommendation: value => String(value || ''),
    pipelineModeLabel: value => `模式 ${value}`
  }
};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportRecommendedAction = () => null;
window.StockAgentReportQualityPolicy.reportNeedsDataRefresh = report => report?.filename === 'raw-refresh.html' || !report?.filename;
window.StockAgentReportQualityPolicy.reportNeedsRerun = () => false;
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
const helpers = window.StockAgentHistoryPanelHelpers;
const escapeHtml = value => String(value ?? '');
const suppressedBadge = helpers.reportActionBadge({
  filename: 'raw-refresh.html',
  ticker: '2454.TW',
  data_trust: { status: 'stale', stale_sources: ['price'] }
}, escapeHtml);
const legacyBadge = helpers.reportActionBadge({
  ticker: '2317.TW',
  data_trust: { status: 'stale', stale_sources: ['price'] }
}, escapeHtml);
process.stdout.write(JSON.stringify({ suppressedBadge, legacyBadge }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "建議刷新資料" not in payload["suppressedBadge"]
    assert "可直接使用" in payload["suppressedBadge"]
    assert "建議刷新資料" in payload["legacyBadge"]


def test_history_report_action_badge_limits_quality_gate_fallback_to_legacy_reports():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    script = """
global.window = {
  StockAgentUi: {
    normalizeRecommendation: value => String(value || ''),
    pipelineModeLabel: value => `模式 ${value}`
  }
};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportRecommendedAction = () => null;
window.StockAgentReportQualityPolicy.reportQualityGateAction = () => ({
  label: 'raw gate fallback',
  tone: 'critical',
  detail: 'raw gate detail'
});
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
const helpers = window.StockAgentHistoryPanelHelpers;
const escapeHtml = value => String(value ?? '');
const suppressedBadge = helpers.reportActionBadge({
  filename: 'raw-gate.html',
  ticker: '2454.TW',
  data_trust: { status: 'fresh' }
}, escapeHtml);
const legacyBadge = helpers.reportActionBadge({
  ticker: '2317.TW',
  data_trust: { status: 'fresh' }
}, escapeHtml);
process.stdout.write(JSON.stringify({ suppressedBadge, legacyBadge }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "raw gate fallback" not in payload["suppressedBadge"]
    assert "可直接使用" in payload["suppressedBadge"]
    assert "raw gate fallback" in payload["legacyBadge"]


def test_history_tracking_action_note_uses_report_recommended_action_policy():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    script = """
global.window = {
  StockAgentUi: {
    normalizeRecommendation: value => String(value || ''),
    pipelineModeLabel: value => `模式 ${value}`
  }
};
require(__REPORT_QUALITY_POLICY_PATH__);
window.StockAgentReportQualityPolicy.reportNeedsRerun = report => !report?.filename || report?.filename === 'raw-stale.html';
window.StockAgentReportQualityPolicy.reportNeedsDataRefresh = () => true;
window.StockAgentReportQualityPolicy.reportRecommendedAction = report => (
  report?.filename === 'policy-rerun.html'
    ? { type: 'rerun_full_report', filename: report.filename }
    : null
);
window.StockAgentReportQualityPolicy.reportRerunMessage = () => 'policy rerun note';
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
const helpers = window.StockAgentHistoryPanelHelpers;
const escapeHtml = value => String(value ?? '');
const rerunNote = helpers.trackingActionNote({
  filename: 'policy-rerun.html',
  ticker: '2330.TW',
  decision_freshness: { status: 'current' }
}, escapeHtml);
const suppressedNote = helpers.trackingActionNote({
  filename: 'raw-stale.html',
  ticker: '2454.TW',
  decision_freshness: { requires_rerun: true },
  data_trust: { status: 'stale', stale_sources: ['price'] }
}, escapeHtml);
const legacyNote = helpers.trackingActionNote({
  ticker: '2317.TW',
  decision_freshness: { requires_rerun: true }
}, escapeHtml);
process.stdout.write(JSON.stringify({ rerunNote, suppressedNote, legacyNote }));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "需完整重跑" in payload["rerunNote"]
    assert "policy rerun note" in payload["rerunNote"]
    assert payload["suppressedNote"] == ""
    assert "需完整重跑" in payload["legacyNote"]


def test_history_panel_renderers_build_rows_without_panel():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    history_panel_renderers_path = STATIC_DIR / "history_panel_renderers.js"
    script = """
global.window = {
  StockAgentUi: {
    normalizeRecommendation: value => String(value || ''),
    pipelineModeLabel: value => `模式 ${value}`
  }
};
require(__REPORT_QUALITY_POLICY_PATH__);
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
require(__HISTORY_PANEL_RENDERERS_PATH__);
const escapeHtml = value => String(value ?? '');
const renderers = window.StockAgentHistoryPanelRenderers.create({
  helpers: window.StockAgentHistoryPanelHelpers,
  escapeHtml,
  normalizeRecommendation: value => String(value || ''),
  recommendationTone: () => 'is-buy',
  renderPipelineModeBadge: value => `<b>${value}</b>`,
  renderDataTrustBadge: () => '',
  renderDataTrustReason: () => '',
  reportTracked: report => report.filename === 'tracked.html'
});
const report = {
  filename: 'tracked.html',
  ticker: '2330.TW',
  company_name: '台積電',
  pipeline_id: 'v2',
  date: '2026-07-09',
  preview: { primary: { value: '買入' }, list_metrics: [{ value: 'NT$1000' }, { value: '信心 8/10' }] },
  recommendation: { recommendation: '買入' },
  data_trust: { status: 'fresh' },
  decision_tracking: {
    status: 'tracked',
    recommendation: '買入',
    latest_price: 950,
    return_pct: 2.5,
    target_comparisons: { target_12m: { status: 'near_target', target: 1000 } }
  }
};
process.stdout.write(JSON.stringify({
  history: renderers.renderHistoryList([report]),
  tracking: renderers.renderTrackingGroups([{ ticker: '2330.TW', company_name: '台積電', reports: [report] }], false)
}));
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path))).replace("__HISTORY_PANEL_RENDERERS_PATH__", json.dumps(str(history_panel_renderers_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "history-item" in payload["history"]
    assert "取消追蹤" in payload["history"]
    assert "NT$1000" in payload["history"]
    assert "decision-tracking-title" in payload["tracking"]
    assert "tracking-report-card" in payload["tracking"]
    assert "data-tracking-snapshot=\"2330.TW\"" in payload["tracking"]


def test_decision_tracking_table_ticker_opens_stock_snapshot():
    report_quality_policy_path = STATIC_DIR / "report_quality_policy.js"
    history_panel_quality_helpers_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_panel_helpers_path = STATIC_DIR / "history_panel_helpers.js"
    history_panel_renderers_path = STATIC_DIR / "history_panel_renderers.js"
    history_panel_path = STATIC_DIR / "history_panel.js"
    script = """
global.window = { StockAgentUi: { normalizeRecommendation: value => String(value || '') } };
require(__REPORT_QUALITY_POLICY_PATH__);
require(__HISTORY_PANEL_QUALITY_HELPERS_PATH__);
require(__HISTORY_PANEL_HELPERS_PATH__);
require(__HISTORY_PANEL_RENDERERS_PATH__);
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
""".replace("__REPORT_QUALITY_POLICY_PATH__", json.dumps(str(report_quality_policy_path))).replace("__HISTORY_PANEL_QUALITY_HELPERS_PATH__", json.dumps(str(history_panel_quality_helpers_path))).replace("__HISTORY_PANEL_HELPERS_PATH__", json.dumps(str(history_panel_helpers_path))).replace("__HISTORY_PANEL_RENDERERS_PATH__", json.dumps(str(history_panel_renderers_path))).replace("__HISTORY_PANEL_PATH__", json.dumps(str(history_panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert 'class="tracking-stock-snapshot-button"' in payload["html"]
    assert 'data-tracking-snapshot="2330.TW"' in payload["html"]
    assert payload["openedTicker"] == "2330.TW"


def test_decision_tracking_dense_layout_uses_workspace_efficiently():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    base_css = (STATIC_DIR / "styles" / "base.css").read_text(encoding="utf-8")
    history_list_css = (STATIC_DIR / "styles" / "history_list.css").read_text(encoding="utf-8")
    history_list_controls_css = (STATIC_DIR / "styles" / "history_list_controls.css").read_text(encoding="utf-8")
    decision_tracking_css = (STATIC_DIR / "styles" / "decision_tracking.css").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    history_panel_helpers_js = (STATIC_DIR / "history_panel_helpers.js").read_text(encoding="utf-8")
    history_panel_renderers_js = (STATIC_DIR / "history_panel_renderers.js").read_text(encoding="utf-8")
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")

    assert "style.css?v=20260711-candidate-next-actions-v3" in index_html
    assert "/static/provider_sla_panel.js?v=20260708-provider-waterfall-health" in index_html
    assert "/static/ops_workspace.js?v=20260708-provider-group-health" in index_html
    assert "/static/history_panel.js?v=20260708-tracking-action-notes" in index_html
    assert "/static/decision_tracking_panel.js?v=20260708-tracking-action-notes" in index_html
    assert "/static/report_preview_helpers.js?v=20260709-report-preview-helpers" in index_html
    assert "/static/report_preview_tracking_helpers.js?v=20260709-report-preview-tracking-helpers" in index_html
    assert "/static/report_preview_panel.js?v=20260709-report-preview-helpers" in index_html
    assert "provider_sla.css?v=20260628-glass-dark" in style_css
    assert "provider_sla_controls.css?v=20260709-provider-sla-controls" in style_css
    assert style_css.index("provider_sla.css?v=20260628-glass-dark") < style_css.index("provider_sla_controls.css?v=20260709-provider-sla-controls")
    assert style_css.index("provider_sla_controls.css?v=20260709-provider-sla-controls") < style_css.index("operator_summary.css?v=20260711-candidate-next-actions-v3")
    assert "preview_panel.css?v=20260627-mode-aware-preview" in style_css
    assert "preview_panel_actions.css?v=20260709-preview-panel-actions" in style_css
    assert style_css.index("preview_panel.css?v=20260627-mode-aware-preview") < style_css.index("preview_panel_actions.css?v=20260709-preview-panel-actions")
    assert style_css.index("preview_panel_actions.css?v=20260709-preview-panel-actions") < style_css.index("report_compare.css?v=20260628-glass-dark")
    assert "history_list.css?v=20260628-glass-dark" in style_css
    assert "history_list_controls.css?v=20260709-history-list-controls" in style_css
    assert style_css.index("history_list.css?v=20260628-glass-dark") < style_css.index("history_list_controls.css?v=20260709-history-list-controls")
    assert style_css.index("history_list_controls.css?v=20260709-history-list-controls") < style_css.index("decision_tracking.css?v=20260708-tracking-action-notes")
    assert "decision_tracking.css?v=20260708-tracking-action-notes" in style_css
    assert "history_shell.css?v=20260707-operator-human-factors" in style_css
    assert "history_shell_tabs.css?v=20260711-home-workspaces" in style_css
    assert style_css.index("history_shell.css?v=20260707-operator-human-factors") < style_css.index("history_shell_tabs.css?v=20260711-home-workspaces")
    assert style_css.index("history_shell_tabs.css?v=20260711-home-workspaces") < style_css.index("provider_sla.css?v=20260628-glass-dark")
    assert "responsive.css?v=20260705-commercial-launchpad2" in style_css
    assert "max-width: min(1360px, 100%)" in base_css
    assert "grid-template-columns: minmax(520px, 1.35fr) minmax(360px, 0.85fr)" in history_list_css
    assert ".history-filter-row" in history_list_controls_css
    assert "tracking-density-row" in history_panel_renderers_js
    assert "tracking-report-head" in history_panel_renderers_js
    assert "tracking-report-metrics" in history_panel_renderers_js
    assert "tracking-target-chip" in history_panel_renderers_js
    assert "tracking-target-period" in history_panel_helpers_js
    assert "tracking-target-value" in history_panel_helpers_js
    assert "tracking-target-label" in history_panel_helpers_js
    assert "高密度三模式比較" in history_panel_renderers_js
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
    entry_css = (STATIC_DIR / "commercial" / "styles" / "home_entry.css").read_text(encoding="utf-8")

    assert "style.css?v=20260711-candidate-next-actions-v3" in index_html
    assert "/static/commercial/styles/home_entry.css?v=20260711-simple" in index_html
    assert 'id="home-panel-commercial"' in index_html
    assert 'class="commercial-entry-launchpad"' in index_html
    assert 'class="commercial-entry-primary"' in index_html
    assert index_html.count('class="commercial-entry-secondary"') == 2
    assert "今天先處理什麼" in index_html
    assert "研究一檔股票" in index_html
    assert "檢查整體持股風險" in index_html

    for href in (
        "/static/commercial/research-workbench.html",
        "/static/commercial/stock-detail.html",
        "/static/commercial/portfolio-dashboard.html",
    ):
        assert href in index_html

    for removed_control in (
        'id="commercial-operator-shift-summary"',
        'class="commercial-entry-command-row"',
        'class="commercial-entry-card"',
        "產生 AI 報告",
        "建立再平衡單",
        "整理客戶包",
    ):
        assert removed_control not in index_html

    assert ".commercial-entry-primary" in entry_css
    assert ".commercial-entry-secondary" in entry_css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in entry_css
    assert "@media (max-width: 560px)" in entry_css


def test_frontend_uiux_accessibility_contracts_are_wired():
    base_css = (STATIC_DIR / "styles" / "base.css").read_text(encoding="utf-8")
    forms_css = (STATIC_DIR / "styles" / "forms_controls.css").read_text(encoding="utf-8")
    history_shell_css = (STATIC_DIR / "styles" / "history_shell.css").read_text(encoding="utf-8")
    history_shell_tabs_css = (STATIC_DIR / "styles" / "history_shell_tabs.css").read_text(encoding="utf-8")
    history_list_css = (STATIC_DIR / "styles" / "history_list.css").read_text(encoding="utf-8")
    history_list_controls_css = (STATIC_DIR / "styles" / "history_list_controls.css").read_text(encoding="utf-8")
    loading_report_css = (STATIC_DIR / "styles" / "loading_report.css").read_text(encoding="utf-8")
    notifications_css = (STATIC_DIR / "styles" / "notifications.css").read_text(encoding="utf-8")
    preview_panel_css = (STATIC_DIR / "styles" / "preview_panel.css").read_text(encoding="utf-8")
    preview_panel_actions_css = (STATIC_DIR / "styles" / "preview_panel_actions.css").read_text(encoding="utf-8")
    provider_sla_css = (STATIC_DIR / "styles" / "provider_sla.css").read_text(encoding="utf-8")
    provider_sla_controls_css = (STATIC_DIR / "styles" / "provider_sla_controls.css").read_text(encoding="utf-8")
    watchlist_css = (STATIC_DIR / "styles" / "watchlist.css").read_text(encoding="utf-8")
    history_panel_js = (STATIC_DIR / "history_panel.js").read_text(encoding="utf-8")
    history_panel_helpers_js = (STATIC_DIR / "history_panel_helpers.js").read_text(encoding="utf-8")
    history_panel_renderers_js = (STATIC_DIR / "history_panel_renderers.js").read_text(encoding="utf-8")
    home_tabs_js = (STATIC_DIR / "home_tabs.js").read_text(encoding="utf-8")
    notification_center_js = (STATIC_DIR / "notification_center.js").read_text(encoding="utf-8")

    assert _contrast_ratio("#ffffff", "#1d4ed8") >= 4.5
    assert _contrast_ratio("#94a3b8", "#0f172a") >= 4.5
    assert "--primary-action: #1d4ed8" in base_css
    assert ".hint-text" in loading_report_css
    assert "color: var(--text-secondary)" in loading_report_css
    assert "background: var(--primary-action)" in loading_report_css

    assert 'aria-label="預覽 ${escapeHtml(r.ticker' in history_panel_renderers_js
    assert 'aria-label="刪除 ${escapeHtml(r.ticker' in history_panel_renderers_js
    assert 'role="button" tabindex="0" aria-label="預覽 ${escapeHtml(report.ticker' in history_panel_renderers_js
    assert "isActivationKey" in history_panel_js
    assert "event.key === ' '" in history_panel_helpers_js
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
        history_shell_tabs_css,
        history_list_css,
        history_list_controls_css,
        loading_report_css,
        notifications_css,
        preview_panel_css,
        preview_panel_actions_css,
        provider_sla_css,
        provider_sla_controls_css,
        watchlist_css,
    ])
    assert "transition: all" not in combined_css
    assert "@media (prefers-reduced-motion: reduce)" in base_css
    assert "transition-duration: 0.01ms" in base_css
    assert "animation: none" in base_css

    assert ".home-tab-button" not in history_shell_css
    assert ".home-tab-button" in history_shell_tabs_css and "min-height: 44px" in history_shell_tabs_css
    assert ".history-filter-select" not in history_list_css
    assert ".history-filter-select" in history_list_controls_css and "min-height: 44px" in history_list_controls_css
    assert ".history-version-toggle" not in history_list_css
    assert ".history-version-toggle" in history_list_controls_css and "min-height: 44px" in history_list_controls_css
    assert ".history-search" not in history_list_css
    assert ".history-search" in history_list_controls_css and "min-height: 44px" in history_list_controls_css
    assert ".delete-btn" not in history_list_css
    assert ".delete-btn" in history_list_controls_css and "min-width: 44px" in history_list_controls_css
    assert ".pager-btn" not in history_list_css
    assert ".pager-btn" in history_list_controls_css and "width: 44px" in history_list_controls_css
    assert ".report-download-button" in loading_report_css and "min-height: 44px" in loading_report_css
    assert ".confirm-dialog-button" in notifications_css and "min-height: 44px" in notifications_css
    assert ".toast-close" in notifications_css and "width: 44px" in notifications_css
    assert ".preview-refresh-button" in preview_panel_actions_css and "min-height: 44px" in preview_panel_actions_css
    assert ".preview-rerun-button" in preview_panel_actions_css and "min-height: 44px" in preview_panel_actions_css
    assert ".provider-sla-window" not in provider_sla_css
    assert ".provider-sla-window" in provider_sla_controls_css and "min-height: 44px" in provider_sla_controls_css
    assert ".maintenance-button" not in provider_sla_css
    assert ".maintenance-button" in provider_sla_controls_css and "min-height: 44px" in provider_sla_controls_css
    assert ".watchlist-delete-button" in watchlist_css and "min-height: 44px" in watchlist_css


def test_frontend_static_modules_are_sized():
    size_limits = {
        "app.js": 180,
        "app_elements.js": 90,
        "app_pipeline_controls.js": 90,
        "app_panels.js": 130,
        "history_workspace.js": 180,
        "history_workspace_panels.js": 100,
        "history_workspace_actions.js": 120,
        "history_panel.js": 170,
        "report_quality_gate_policy.js": 45,
        "report_quality_policy.js": 80,
        "report_reading_boundary_policy.js": 60,
        "history_panel_quality_helpers.js": 120,
        "history_panel_helpers.js": 110,
        "history_panel_renderers.js": 180,
        "ui_helpers.js": 100,
        "pipeline_mode_fallback.js": 90,
        "pipeline_mode_catalog.js": 60,
        "ui_data_trust.js": 90,
        "api_request.js": 80,
        "api_client.js": 90,
        "provider_sla_panel.js": 120,
        "provider_sla_helpers.js": 170,
        "maintenance_panel.js": 105,
        "maintenance_panel_helpers.js": 100,
        "maintenance_notification_delivery.js": 80,
        "daily_decision_queue_context.js": 60,
        "view_controller.js": 40,
        "history_filters.js": 50,
        "report_actions.js": 45,
        "report_navigation.js": 75,
        "report_navigation_targets.js": 70,
        "home_tabs.js": 60,
        "report_rerun.js": 105,
        "report_rerun_stream.js": 80,
        "analysis_stream.js": 95,
        "analysis_stream_events.js": 120,
        "style.css": 45,
        "notification_center.js": 120,
        "styles/history_shell.css": 80,
        "styles/history_shell_tabs.css": 80,
        "styles/history_shell_commercial.css": 230,
        "styles/stock_snapshot_shell.css": 230,
        "styles/stock_snapshot_overview.css": 170,
        "styles/stock_snapshot_overview_trend.css": 90,
        "styles/stock_snapshot_overview_performance.css": 120,
        "styles/stock_snapshot_overview_technical.css": 90,
        "styles/stock_snapshot_research.css": 170,
        "styles/stock_snapshot_research_analyst.css": 90,
        "styles/stock_snapshot_signal.css": 240,
        "styles/stock_snapshot_signal_dividend.css": 130,
        "styles/stock_snapshot_signal_events.css": 180,
        "styles/stock_snapshot_core.css": 220,
        "styles/stock_snapshot_core_peer_ownership.css": 180,
        "styles/stock_snapshot_supplemental.css": 140,
        "styles/stock_snapshot_responsive_headers.css": 190,
        "styles/stock_snapshot_responsive.css": 90,
        "styles/stock_snapshot_responsive_mobile.css": 60,
        "styles/history_list.css": 240,
        "styles/history_list_controls.css": 110,
        "styles/decision_tracking.css": 80,
        "styles/notifications.css": 160,
        "styles/preview_panel.css": 160,
        "styles/preview_panel_quality.css": 60,
        "styles/preview_panel_actions.css": 100,
        "styles/report_compare.css": 90,
        "styles/provider_sla.css": 160,
        "styles/provider_sla_controls.css": 100,
        "styles/watchlist.css": 80,
        "styles/market_screener.css": 90,
        "api_client_extensions.js": 90,
        "ops_workspace.js": 90,
        "ops_workspace_elements.js": 80,
        "ops_workspace_loaders.js": 80,
        "ops_workspace_panels.js": 130,
        "market_screener_panel.js": 120,
        "market_screener_helpers.js": 90,
        "api_quota_panel.js": 100,
        "performance_panel.js": 100,
        "watchlist_trigger_form.js": 90,
        "temporal_memory_panel.js": 70,
        "stock_snapshot_panel.js": 80,
        "stock_snapshot_numeric_format_helpers.js": 70,
        "stock_snapshot_domain_format_helpers.js": 55,
        "stock_snapshot_performance_helpers.js": 60,
        "stock_snapshot_format_helpers.js": 85,
        "stock_snapshot_helpers.js": 130,
        "stock_snapshot_input_helpers.js": 100,
        "stock_snapshot_load_helpers.js": 90,
        "stock_snapshot_action_helpers.js": 120,
        "stock_snapshot_summary_helpers.js": 120,
        "stock_snapshot_sections.js": 160,
        "stock_snapshot_overview_sections.js": 130,
        "stock_snapshot_research_sections.js": 100,
        "stock_snapshot_signal_sections.js": 120,
        "stock_snapshot_supplemental_sections.js": 90,
        "stock_snapshot_interaction_helpers.js": 70,
        "stock_snapshot_render_helpers.js": 80,
        "stock_snapshot_event_helpers.js": 80,
        "watchlist_panel.js": 120,
        "watchlist_panel_helpers.js": 95,
        "watchlist_panel_actions.js": 120,
        "report_compare_panel.js": 90,
        "report_compare_helpers.js": 80,
        "report_compare_renderers.js": 100,
        "report_preview_panel.js": 130,
        "report_preview_helpers.js": 75,
        "report_preview_tracking_helpers.js": 85,
        "report_preview_rerun_helpers.js": 60,
        "operator_summary_panel.js": 105,
        "operator_summary_quality_helpers.js": 95,
        "operator_summary_helpers.js": 90,
        "operator_dashboard_actions.js": 90,
        "decision_tracking_panel.js": 125,
        "decision_tracking_helpers.js": 80,
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
    assert "scripts/check_visual_regression.py" in setup_script.read_text(encoding="utf-8")
    assert "scripts/setup_visual_regression.sh" in readme
    assert "scripts/visual_regression.sh" in readme
    assert "scripts/check_visual_regression.py" in readme
    assert "RUN_VISUAL_REGRESSION=1 scripts/ci_gate.sh" in readme
