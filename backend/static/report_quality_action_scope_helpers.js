(function () {
    const actionLabels = { manual_review: '人工審核', rerun_analysis: '完整重跑', refresh_data_snapshot: '刷新資料', wait_provider_recovery: '等待來源恢復', unknown: '無法判定' };
    const freshnessLabels = { current: '本文目前版本', needs_rerun: '資料已更新、本文需完整重跑', unknown: 'freshness 未判定' };
    const freshnessOrder = ['current', 'needs_rerun', 'unknown'];

    function positiveInteger(value) {
        const count = Number(value);
        return Number.isFinite(count) && Number.isInteger(count) && count > 0 ? count : null;
    }

    function actionEntries(counts) {
        return counts && typeof counts === 'object' && !Array.isArray(counts)
            ? Object.entries(counts)
                .map(([key, value]) => [String(key || '').trim(), positiveInteger(value)])
                .filter(([key, value]) => key && value !== null)
                .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
            : [];
    }

    function nonNegativeInteger(value) {
        const count = Number(value);
        return Number.isFinite(count) && Number.isInteger(count) && count >= 0 ? count : null;
    }

    function validCountMap(counts) {
        if (!counts || typeof counts !== 'object' || Array.isArray(counts)) return null;
        const result = {};
        for (const [key, value] of Object.entries(counts)) {
            const normalizedKey = String(key || '').trim(), count = nonNegativeInteger(value);
            if (!normalizedKey || count === null) return null;
            result[normalizedKey] = count;
        }
        return result;
    }

    function freshnessCountsConsistent(counts, countsByFreshness) {
        const total = validCountMap(counts);
        if (!total || !countsByFreshness || typeof countsByFreshness !== 'object' || Array.isArray(countsByFreshness)) return false;
        if (Object.keys(countsByFreshness).some(bucket => !freshnessOrder.includes(bucket))) return false;
        const aggregate = {};
        for (const bucket of freshnessOrder) {
            const values = countsByFreshness[bucket] === undefined ? {} : validCountMap(countsByFreshness[bucket]);
            if (!values) return false;
            for (const [key, count] of Object.entries(values)) aggregate[key] = (aggregate[key] || 0) + count;
        }
        const actionKeys = new Set([...Object.keys(total), ...Object.keys(aggregate)]);
        return [...actionKeys].every(key => (total[key] || 0) === (aggregate[key] || 0));
    }

    function formatQualityActionFreshnessSummary(countsByFreshness) {
        if (!countsByFreshness || typeof countsByFreshness !== 'object' || Array.isArray(countsByFreshness)) return '';
        const parts = freshnessOrder.map(bucket => {
            const entries = actionEntries(countsByFreshness[bucket]);
            return entries.length
                ? `${freshnessLabels[bucket] || bucket}：${entries.map(([key, value]) => `${actionLabels[key] || key} ${value}`).join('、')}`
                : '';
        }).filter(Boolean);
        return parts.length ? `按資料新鮮度：${parts.join('；')}` : '';
    }

    function formatQualityActionProjectionSummary(counts, scope, countsByFreshness) {
        const summary = window.StockAgentReportQualityEvidence?.formatQualityActionSummary?.(counts) || '';
        const value = scope && typeof scope === 'object' && !Array.isArray(scope) ? scope : {};
        const scopedSummary = summary && value.is_daily_queue === false
            ? summary.replace('品質處理建議：', '品質處理建議（唯讀品質投影，不等同今日待辦）：')
            : summary;
        const freshnessSummary = freshnessCountsConsistent(counts, countsByFreshness)
            ? formatQualityActionFreshnessSummary(countsByFreshness)
            : '';
        return scopedSummary && freshnessSummary ? `${scopedSummary}；${freshnessSummary}` : scopedSummary;
    }

    window.StockAgentReportQualityActionScope = { formatQualityActionProjectionSummary, formatQualityActionFreshnessSummary };
})();
