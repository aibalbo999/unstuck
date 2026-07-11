(function () {
    function formatPct(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return 'N/A';
        return `${number > 0 ? '+' : ''}${number.toFixed(2)}%`;
    }
    function formatNumber(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return 'N/A';
        return number.toLocaleString('zh-TW', { maximumFractionDigits: 2 });
    }
    function normalizeTrackingRecommendation(value) {
        return window.StockAgentUi?.normalizeRecommendation
            ? window.StockAgentUi.normalizeRecommendation(value)
            : String(value || '');
    }
    function trackingTone(tracking) {
        const value = Number(tracking && tracking.return_pct);
        if (!Number.isFinite(value) || value === 0) return 'is-neutral';
        if (tracking.status === 'target_hit' || tracking.status === 'avoided_loss') return 'is-positive';
        if (['避免', '放空'].includes(normalizeTrackingRecommendation(tracking.recommendation))) return value < 0 ? 'is-positive' : 'is-negative';
        return value > 0 ? 'is-positive' : 'is-negative';
    }
    function awaitingTrackingPrice(tracking) {
        return tracking?.status === 'tracked'
            && !tracking.snapshot_refreshed_at
            && Number(tracking.return_pct) === 0
            && Number(tracking.initial_price) === Number(tracking.latest_price);
    }
    function renderTrackingBadge(tracking, escapeHtml) {
        if (!tracking || !tracking.status || tracking.status === 'unavailable' || !Number.isFinite(Number(tracking.return_pct))) return '';
        if (awaitingTrackingPrice(tracking)) return '<span class="history-tracking is-neutral" title="尚待下一筆價格更新">追蹤 待新價格</span>';
        const title = tracking.summary || '決策追蹤';
        return `<span class="history-tracking ${trackingTone(tracking)}" title="${escapeHtml(title)}">追蹤 ${escapeHtml(formatPct(tracking.return_pct))}</span>`;
    }
    function qualityHelpers() {
        return window.StockAgentHistoryPanelQualityHelpers || {};
    }
    function hasRefreshableDataTrustIssue(report) {
        return Boolean(qualityHelpers().hasRefreshableDataTrustIssue?.(report));
    }
    function reportActionBadge(report, escapeHtml) {
        return qualityHelpers().reportActionBadge?.(report, escapeHtml) || '';
    }
    function trackingActionNote(report, escapeHtml) {
        return qualityHelpers().trackingActionNote?.(report, escapeHtml) || '';
    }
    function trackingPipelineLabel(report) {
        if (window.StockAgentUi?.pipelineModeLabel && report?.pipeline_id) return window.StockAgentUi.pipelineModeLabel(report.pipeline_id);
        return report?.pipeline_label || report?.pipeline_id || '報告';
    }
    function targetComparisonCell(tracking, key, escapeHtml) {
        const comparison = tracking?.target_comparisons?.[key] || {};
        const period = { target_3m: '3月', target_6m: '6月', target_12m: '12月' }[key] || '目標';
        const fullPeriod = { target_3m: '3月目標', target_6m: '6月目標', target_12m: '12月目標' }[key] || '目標';
        const status = comparison.status || 'unavailable';
        const label = comparison.label || (status === 'below_target' ? '低於目標' : (status === 'near_target' ? '接近目標' : (status === 'above_target' ? '已高於目標' : '無法比較')));
        const shortLabel = { below_target: '低於', near_target: '接近', above_target: '高於' }[status] || '無法';
        const className = String(status).replace(/_/g, '-');
        const title = comparison.gap_pct === null || comparison.gap_pct === undefined ? `${fullPeriod} ${label}` : `${fullPeriod} ${label} ${formatPct(comparison.gap_pct)}`;
        return `<span class="tracking-target-cell tracking-target-chip is-${className}" title="${escapeHtml(title)}"><span class="tracking-target-period">${escapeHtml(period)}</span><strong class="tracking-target-value">${escapeHtml(formatNumber(comparison.target || tracking?.[key]))}</strong><span class="tracking-target-label">${escapeHtml(shortLabel)}</span></span>`;
    }
    function trackingSummaryTone(tracking) {
        const comparisons = tracking?.target_comparisons || {};
        for (const key of ['target_12m', 'target_6m', 'target_3m']) {
            const status = comparisons[key]?.status;
            if (status === 'above_target' || status === 'near_target') return `is-${status.replace(/_/g, '-')}`;
        }
        return comparisons.target_12m?.status === 'below_target' ? 'is-below-target' : 'is-unavailable';
    }
    function isActivationKey(event) {
        return event.key === 'Enter' || event.key === ' ';
    }

    window.StockAgentHistoryPanelHelpers = {
        formatPct,
        formatNumber,
        trackingTone,
        renderTrackingBadge,
        reportActionBadge,
        trackingActionNote,
        trackingPipelineLabel,
        targetComparisonCell,
        trackingSummaryTone,
        isActivationKey,
        hasRefreshableDataTrustIssue
    };
})();
