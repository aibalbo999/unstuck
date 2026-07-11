(function () {
    const qualityPolicy = () => window.StockAgentReportQualityPolicy || {};
    const reportNeedsRerun = report => Boolean(qualityPolicy().reportNeedsRerun?.(report));
    const reportRerunMessage = report => qualityPolicy().reportRerunMessage?.(report) || '結論與資料可能不同步';
    const reportQualityGateAction = report => qualityPolicy().reportQualityGateAction?.(report) || null;
    const reportRecommendedAction = report => qualityPolicy().reportRecommendedAction?.(report) || null;
    const hasRefreshableDataTrustIssue = report => Boolean(qualityPolicy().hasRefreshableDataTrustIssue?.(report));
    const reportNeedsDataRefresh = report => Boolean(qualityPolicy().reportNeedsDataRefresh?.(report));
    const requiresDataTrustAction = report => Boolean(qualityPolicy().requiresDataTrustAction?.(report));
    const isSourceNotice = report => Boolean(qualityPolicy().hasProviderSlaOnlyPartial?.(report));
    const reportHasFreshData = report => Boolean(qualityPolicy().reportHasFreshData?.(report));
    const sourceNoticeReports = reports => qualityPolicy().sourceNoticeReports?.(reports || []) || [];
    function reportAction(report) {
        const status = qualityPolicy().dataTrustStatus?.(report);
        const qualityGateAction = reportQualityGateAction(report);
        const action = reportRecommendedAction(report);
        const hasActionPolicy = typeof qualityPolicy().reportRecommendedAction === 'function';
        const useLegacyAction = !hasActionPolicy || (!action && !report.filename);
        if (action?.type === 'manual_review' && status === 'error') return { title: '暫勿採用', detail: '來源異常，先查看報告' };
        if (action?.type === 'manual_review' && qualityGateAction) return { title: qualityGateAction.label, detail: qualityGateAction.detail };
        if (action?.type === 'manual_review') return { title: '需人工查看', detail: '請開啟報告確認品質警示' };
        if (useLegacyAction && qualityGateAction) return { title: qualityGateAction.label, detail: qualityGateAction.detail };
        if (action?.type === 'rerun_full_report') return { title: '建議完整重跑', detail: reportRerunMessage(report) };
        if (action?.type === 'refresh_data_snapshot') return { title: '建議刷新資料', detail: '先更新快照再判斷', action: 'refresh-report', label: '刷新資料' };
        if (useLegacyAction && reportNeedsRerun(report)) return { title: '建議完整重跑', detail: reportRerunMessage(report) };
        if (useLegacyAction && reportNeedsDataRefresh(report)) return { title: '建議刷新資料', detail: '先更新快照再判斷', action: 'refresh-report', label: '刷新資料' };
        if (status === 'partial' && !isSourceNotice(report)) return { title: '資料需留意', detail: '資料已是最新快照，請查看來源審計' };
        return null;
    }

    window.StockAgentOperatorSummaryQualityHelpers = {
        hasRefreshableDataTrustIssue,
        isSourceNotice,
        reportAction,
        reportHasFreshData,
        reportNeedsDataRefresh,
        reportNeedsRerun,
        reportQualityGateAction,
        reportRecommendedAction,
        reportRerunMessage,
        requiresDataTrustAction,
        sourceNoticeReports
    };
})();
