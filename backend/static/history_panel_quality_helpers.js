(function () {
    const qualityPolicy = () => window.StockAgentReportQualityPolicy || {};
    function hasRefreshableDataTrustIssue(report) {
        return Boolean(qualityPolicy().hasRefreshableDataTrustIssue?.(report));
    }
    function hasProviderSlaOnlyPartial(report) {
        return Boolean(qualityPolicy().hasProviderSlaOnlyPartial?.(report));
    }
    function reportNeedsDataRefresh(report) {
        return Boolean(qualityPolicy().reportNeedsDataRefresh?.(report));
    }
    function reportActionBadge(report, escapeHtml) {
        const status = qualityPolicy().dataTrustStatus?.(report) || 'unknown';
        const action = qualityPolicy().reportRecommendedAction?.(report);
        const hasActionPolicy = typeof qualityPolicy().reportRecommendedAction === 'function';
        const useLegacyAction = !hasActionPolicy || (!action && !report.filename);
        const qualityGateAction = qualityPolicy().reportQualityGateAction?.(report);
        let label = '可直接使用';
        let tone = 'ok';
        let detail = '資料與結論可直接查看';
        if (action?.type === 'manual_review' && status === 'error') {
            label = '暫勿採用'; tone = 'critical'; detail = '來源異常，請先重跑或改看其他報告';
        } else if (action?.type === 'manual_review' && qualityGateAction) {
            label = qualityGateAction.label; tone = qualityGateAction.tone; detail = qualityGateAction.detail;
        } else if (action?.type === 'manual_review') {
            label = '需人工查看'; tone = 'warning'; detail = '請開啟報告確認品質警示';
        } else if (useLegacyAction && qualityGateAction) {
            label = qualityGateAction.label; tone = qualityGateAction.tone; detail = qualityGateAction.detail;
        } else if (action?.type === 'rerun_full_report') {
            label = '建議完整重跑'; tone = 'critical'; detail = '結論可能已落後於最新資料';
        } else if (action?.type === 'refresh_data_snapshot') {
            label = '建議刷新資料'; tone = 'warning'; detail = '先刷新資料快照再決策';
        } else if (useLegacyAction && qualityPolicy().reportNeedsRerun?.(report)) {
            label = '建議完整重跑'; tone = 'critical'; detail = '結論可能已落後於最新資料';
        } else if (useLegacyAction && reportNeedsDataRefresh(report)) {
            label = '建議刷新資料'; tone = 'warning'; detail = '先刷新資料快照再決策';
        } else if (status === 'partial') {
            label = hasProviderSlaOnlyPartial(report) ? '來源提醒' : '資料需留意';
            tone = 'warning'; detail = '資料已是最新快照，請查看來源審計與健康度';
        }
        return `<span class="history-action-badge is-${tone}" title="${escapeHtml(detail)}">${escapeHtml(label)}</span>`;
    }
    function trackingActionNote(report, escapeHtml) {
        const action = qualityPolicy().reportRecommendedAction?.(report);
        const hasActionPolicy = typeof qualityPolicy().reportRecommendedAction === 'function';
        const useLegacyAction = !hasActionPolicy || (!action && !report.filename);
        let label = '', tone = '', detail = '';
        if (action?.type === 'rerun_full_report') {
            label = '需完整重跑'; tone = 'critical';
            detail = qualityPolicy().reportRerunMessage?.(report) || '資料快照已刷新，投資結論需要完整重跑。';
        } else if (action?.type === 'refresh_data_snapshot') {
            label = '需刷新資料'; tone = 'warning'; detail = '先刷新資料快照，再用追蹤結果做決策。';
        } else if (useLegacyAction && qualityPolicy().reportNeedsRerun?.(report)) {
            label = '需完整重跑'; tone = 'critical';
            detail = qualityPolicy().reportRerunMessage?.(report) || '資料快照已刷新，投資結論需要完整重跑。';
        } else if (useLegacyAction && reportNeedsDataRefresh(report)) {
            label = '需刷新資料'; tone = 'warning'; detail = '先刷新資料快照，再用追蹤結果做決策。';
        }
        return label ? `<span class="tracking-action-note is-${tone}" title="${escapeHtml(detail)}">${escapeHtml(label)}</span>` : '';
    }

    window.StockAgentHistoryPanelQualityHelpers = {
        hasRefreshableDataTrustIssue,
        reportActionBadge,
        trackingActionNote
    };
})();
