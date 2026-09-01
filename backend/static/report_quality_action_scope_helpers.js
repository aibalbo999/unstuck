(function () {
    function formatQualityActionProjectionSummary(counts, scope) {
        const summary = window.StockAgentReportQualityEvidence?.formatQualityActionSummary?.(counts) || '';
        const value = scope && typeof scope === 'object' && !Array.isArray(scope) ? scope : {};
        return summary && value.is_daily_queue === false
            ? summary.replace('品質處理建議：', '品質處理建議（唯讀品質投影，不等同今日待辦）：')
            : summary;
    }

    window.StockAgentReportQualityActionScope = { formatQualityActionProjectionSummary };
})();
