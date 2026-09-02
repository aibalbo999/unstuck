(function () {
    const contextBuckets = ['present', 'partial', 'artifact_fallback_available', 'missing', 'not_evaluated'];

    function nonNegativeInteger(value) {
        const count = Number(value);
        return Number.isFinite(count) && Number.isInteger(count) && count >= 0 ? count : null;
    }

    function completeDistribution(counts, totalValue, allowedKeys) {
        const total = nonNegativeInteger(totalValue);
        if (total === null || !counts || typeof counts !== 'object' || Array.isArray(counts)) return false;
        const allowed = Array.isArray(allowedKeys) ? new Set(allowedKeys) : null;
        let sum = 0;
        for (const [key, value] of Object.entries(counts)) {
            const count = nonNegativeInteger(value);
            if (!key.trim() || allowed && !allowed.has(key) || count === null) return false;
            sum += count;
        }
        return sum === total;
    }

    function sanitizeAuditDistributions(payload, includeVersion = false) {
        if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return payload;
        const specifications = [
            ['quality_metadata_missing_by_provenance', ['before_refresh', 'after_refresh', 'no_refresh_provenance']],
            ['quality_metadata_missing_by_rerun_execution', ['full_rerun_required', 'partial_rerun_available', 'partial_rerun_review_required', 'partial_rerun_unavailable', 'not_evaluated']],
            ['quality_metadata_missing_by_rerun_context', contextBuckets],
            ['quality_review_by_status', ['pending', 'approved_with_gap', 'rejected', 'deferred']],
        ];
        if (includeVersion) specifications.push(['quality_metadata_missing_by_version_status', ['current', 'historical', 'unknown']]);
        for (const [field, allowedKeys] of specifications) {
            if (payload[field] !== undefined && payload[field] !== null && !completeDistribution(payload[field], payload.quality_metadata_missing_reports, allowedKeys)) delete payload[field];
        }
        return payload;
    }

    function pipelineEntries(pipelineQuality, totalMissing) {
        const total = nonNegativeInteger(totalMissing);
        if (total === null || !pipelineQuality || typeof pipelineQuality !== 'object' || Array.isArray(pipelineQuality)) return null;
        const entries = Object.entries(pipelineQuality);
        if (!entries.length) return null;
        let sum = 0;
        const result = [];
        for (const [pipeline, summary] of entries) {
            const count = summary && typeof summary === 'object' && !Array.isArray(summary)
                ? nonNegativeInteger(summary.quality_metadata_missing_reports)
                : null;
            if (!String(pipeline || '').trim() || count === null) return null;
            sum += count;
            result.push({ pipeline, summary, count });
        }
        return sum === total ? result : null;
    }

    function pipelineMissingSummary(pipelineQuality, totalMissing) {
        const entries = pipelineEntries(pipelineQuality, totalMissing);
        return entries ? entries.filter(entry => entry.count > 0).map(entry => `${entry.pipeline} ${entry.count}`).join('、') : '';
    }

    function pipelineContextScopeValid(pipelineQuality, totalMissing) {
        const entries = pipelineEntries(pipelineQuality, totalMissing);
        return Boolean(entries && entries.every(({ summary, count }) => {
            const context = summary.quality_metadata_missing_by_rerun_context;
            if (!context || typeof context !== 'object' || Array.isArray(context)) return false;
            if (Object.keys(context).some(key => !contextBuckets.includes(key))) return false;
            let contextTotal = 0;
            for (const bucket of Object.keys(context)) {
                const value = nonNegativeInteger(context[bucket]);
                if (value === null) return false;
                contextTotal += value;
            }
            return contextTotal === count;
        }));
    }

    window.StockAgentReportQualityAuditScope = { completeDistribution, sanitizeAuditDistributions, pipelineMissingSummary, pipelineContextScopeValid };
})();
