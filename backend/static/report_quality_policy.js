(function () {
    const dataTrustReasonCodes = report => {
        const codes = report?.data_trust?.reason_codes;
        return Array.isArray(codes) ? codes.map(code => String(code || '')) : [];
    };
    const dataTrustStatus = report => report?.data_trust?.status || 'unknown';
    const dataTrustStaleSources = report => {
        const sources = report?.data_trust?.stale_sources;
        return Array.isArray(sources) ? sources.filter(Boolean) : [];
    };
    const reportNeedsRerun = report => Boolean(report?.analysis_text_stale || report?.decision_freshness?.requires_rerun || report?.requires_rerun);
    const reportRerunMessage = report => {
        const freshness = report?.decision_freshness || {};
        return freshness.message
            || freshness.requires_rerun_reason
            || report?.analysis_text_stale_message
            || '資料快照已刷新，投資結論需要完整重跑。';
    };
    function decisionFreshnessStatusLabel(freshness) {
        if (!freshness) return 'N/A';
        if (freshness.requires_rerun || freshness.status === 'needs_rerun') return '需重跑';
        if (freshness.status === 'current') return '有效';
        return freshness.status || 'N/A';
    }
    const reportDecisionStatusLabel = report => reportNeedsRerun(report)
        ? '需重跑'
        : decisionFreshnessStatusLabel(report?.decision_freshness);
    const reportHasFreshData = report => dataTrustStatus(report) === 'fresh';
    const reportConformanceStatus = report => String(report?.report_conformance?.status || '');
    const evidenceExitGateVerdict = report => String(report?.evidence_exit_gate?.verdict || '');
    const reportReadingBoundary = report => window.StockAgentReportReadingBoundaryPolicy?.reportReadingBoundary?.(report) || null;
    const evidenceExitGateNeedsAction = report => ['rejected', 'caution'].includes(evidenceExitGateVerdict(report));
    const reportQualityGateAction = report => window.StockAgentReportQualityGatePolicy?.reportQualityGateAction?.(report, {
        evidenceExitGateVerdict,
        reportConformanceStatus
    }) || null;
    function hasRefreshableDataTrustIssue(report) {
        return dataTrustStatus(report) === 'stale'
            || dataTrustStaleSources(report).length > 0
            || dataTrustReasonCodes(report).some(code => code.startsWith('source_stale:'));
    }
    function dataTrustProviderSlaOnlyPartial(trust) {
        const report = { data_trust: trust || {} };
        const failures = report.data_trust.critical_failures;
        return dataTrustStatus(report) === 'partial'
            && !hasRefreshableDataTrustIssue(report)
            && dataTrustReasonCodes(report).includes('provider_sla_critical')
            && !(Array.isArray(failures) && failures.filter(Boolean).length);
    }
    const hasProviderSlaOnlyPartial = report => dataTrustProviderSlaOnlyPartial(report?.data_trust);
    function reportNeedsDataRefresh(report) {
        return hasRefreshableDataTrustIssue(report)
            || (dataTrustStatus(report) === 'partial' && !hasProviderSlaOnlyPartial(report));
    }
    const hasSourceError = report => dataTrustReasonCodes(report).some(code => code.startsWith('source_error:'));
    function reportRecommendedAction(report) {
        const filename = report?.filename;
        if (!filename) return null;
        if (dataTrustStatus(report) === 'error' || hasSourceError(report) || reportQualityGateAction(report)) return { type: 'manual_review', filename };
        if (reportNeedsRerun(report)) return { type: 'rerun_full_report', filename };
        if (reportNeedsDataRefresh(report)) return { type: 'refresh_data_snapshot', filename };
        return null;
    }
    function requiresDataTrustAction(report) {
        return dataTrustStatus(report) === 'error'
            || ['blocked', 'warning'].includes(reportConformanceStatus(report))
            || evidenceExitGateNeedsAction(report)
            || hasRefreshableDataTrustIssue(report)
            || reportNeedsRerun(report)
            || hasSourceError(report);
    }
    const sourceNoticeReports = reports => (reports || []).filter(hasProviderSlaOnlyPartial);
    window.StockAgentReportQualityPolicy = {
        dataTrustStatus, dataTrustProviderSlaOnlyPartial, decisionFreshnessStatusLabel,
        evidenceExitGateVerdict, hasProviderSlaOnlyPartial, hasRefreshableDataTrustIssue,
        reportConformanceStatus, reportDecisionStatusLabel, reportHasFreshData, reportNeedsDataRefresh, reportReadingBoundary,
        reportNeedsRerun, reportQualityGateAction, reportRecommendedAction, reportRerunMessage, requiresDataTrustAction, sourceNoticeReports
    };
})();
