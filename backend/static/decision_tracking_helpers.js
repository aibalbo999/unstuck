(function () {
    const qualityPolicy = () => window.StockAgentReportQualityPolicy || {};

    function trackedGroups(payload) {
        return (payload?.items || [])
            .filter(item => item.enabled)
            .map(item => {
                const reports = (item.latest_reports && item.latest_reports.length ? item.latest_reports : [item.latest_report])
                    .filter(report => report && report.filename)
                    .map(report => ({ ...report, tracking_item: item }));
                return {
                    ticker: reports.find(report => report.ticker)?.ticker || item.ticker,
                    company_name: reports[0]?.company_name || item.company_name || '',
                    tracking_item: item,
                    reports
                };
            })
            .filter(group => group.reports.length);
    }

    const trackedSet = payload => new Set((payload?.items || []).filter(item => item.enabled).map(item => item.ticker));

    const recommendedActionForReport = report => qualityPolicy().reportRecommendedAction?.(report) || null;

    function uniqueRecommendedActions(payload) {
        const seen = new Set(), actions = [];
        trackedGroups(payload).flatMap(group => group.reports || []).forEach(report => {
            const action = recommendedActionForReport(report);
            if (!action) return;
            const key = `${action.type}:${action.filename}`;
            if (seen.has(key)) return;
            seen.add(key);
            actions.push(action);
        });
        return actions;
    }

    window.StockAgentDecisionTrackingHelpers = { recommendedActionForReport, trackedGroups, trackedSet, uniqueRecommendedActions };
})();
