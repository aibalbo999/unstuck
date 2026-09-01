(function () {
    function nonNegativeInteger(value) {
        const count = Number(value);
        return Number.isFinite(count) && Number.isInteger(count) && count >= 0 ? count : null;
    }

    function pipelineMissingSummary(pipelineQuality, totalMissing) {
        const total = nonNegativeInteger(totalMissing);
        if (total === null || !pipelineQuality || typeof pipelineQuality !== 'object' || Array.isArray(pipelineQuality)) return '';
        const entries = Object.entries(pipelineQuality);
        if (!entries.length) return '';
        let sum = 0;
        const parts = [];
        for (const [pipeline, summary] of entries) {
            const count = summary && typeof summary === 'object' && !Array.isArray(summary)
                ? nonNegativeInteger(summary.quality_metadata_missing_reports)
                : null;
            if (!String(pipeline || '').trim() || count === null) return '';
            sum += count;
            if (count > 0) parts.push(`${pipeline} ${count}`);
        }
        return sum === total ? parts.join('、') : '';
    }

    window.StockAgentReportQualityAuditScope = { pipelineMissingSummary };
})();
