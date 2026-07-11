(function () {
    const qualityPolicy = () => window.StockAgentReportQualityPolicy || {};

    function formatDelta(delta) {
        if (!delta || delta.delta === null || delta.delta === undefined) return 'N/A';
        const number = Number(delta.delta);
        if (!Number.isFinite(number)) return 'N/A';
        const pct = Number(delta.delta_pct);
        const pctText = Number.isFinite(pct) ? ` (${pct > 0 ? '+' : ''}${pct.toFixed(2)}%)` : '';
        return `${number > 0 ? '+' : ''}${number.toLocaleString('zh-TW', { maximumFractionDigits: 2 })}${pctText}`;
    }

    function dateOrderLabel(order) {
        if (order === 'chronological') return '舊→新';
        if (order === 'reverse') return '新→舊';
        if (order === 'same') return '同時間';
        return '時間未知';
    }

    function decisionStatusLabel(freshness) {
        return qualityPolicy().decisionFreshnessStatusLabel?.(freshness) || 'N/A';
    }

    function reportDecisionStatusLabel(report) {
        return qualityPolicy().reportDecisionStatusLabel?.(report) || 'N/A';
    }

    function compareWarningMessage(item, left, right, pipelineModeLabel) {
        const label = pipelineModeLabel || (pipelineId => String(pipelineId || 'v1'));
        if (item?.code === 'different_pipeline') return `兩份報告模式不同：${label(left.pipeline_id || 'v1')} 與 ${label(right.pipeline_id || 'v1')}；這是跨視角比較。`;
        if (item?.code?.includes('decision_needs_rerun')) return `${item.code.startsWith('left_') ? '左側' : '右側'}報告若要比較投資判斷，需先重跑結論。`;
        return item?.message || item;
    }

    function compareSummaryLabel(compatibility) {
        if (compatibility.same_ticker && compatibility.same_pipeline) return `同股票同模式 · ${dateOrderLabel(compatibility.date_order)}`;
        if (!compatibility.same_ticker) return `股票不同 · ${dateOrderLabel(compatibility.date_order)}`;
        if (!compatibility.same_pipeline) return `跨視角比較 · ${dateOrderLabel(compatibility.date_order)}`;
        return `需留意 · ${dateOrderLabel(compatibility.date_order)}`;
    }

    window.StockAgentReportCompareHelpers = { compareSummaryLabel, compareWarningMessage, dateOrderLabel, decisionStatusLabel, formatDelta, reportDecisionStatusLabel };
})();
