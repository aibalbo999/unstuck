(function () {
    function formatNumber(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return 'N/A';
        return number.toLocaleString('zh-TW', { maximumFractionDigits: 2 });
    }

    function formatPct(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return 'N/A';
        return `${number > 0 ? '+' : ''}${number.toFixed(2)}%`;
    }

    function pctTone(value) {
        const number = Number(value);
        if (!Number.isFinite(number) || number === 0) return 'is-neutral';
        return number > 0 ? 'is-positive' : 'is-negative';
    }

    function normalizeTrackingRecommendation(value) {
        return window.StockAgentUi?.normalizeRecommendation
            ? window.StockAgentUi.normalizeRecommendation(value)
            : String(value || '');
    }

    function returnTone(tracking) {
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

    function trackingView(tracking) {
        const awaiting = awaitingTrackingPrice(tracking);
        return {
            latestText: formatNumber(tracking.latest_price),
            returnText: awaiting ? '待新價格' : formatPct(tracking.return_pct),
            returnTone: returnTone(tracking),
            gapText: formatPct(tracking.target_12m_gap_pct),
            gapTone: pctTone(tracking.target_12m_gap_pct),
            summary: awaiting ? '尚待新價格更新後計算建議後報酬。' : (tracking.summary || '已建立決策追蹤。')
        };
    }

    function renderTracking(tracking, elements) {
        if (!elements.trackingRoot) return;
        if (!tracking || !tracking.status || tracking.status === 'unavailable') {
            elements.trackingRoot.hidden = true;
            return;
        }
        const view = trackingView(tracking);
        elements.trackingLatest.textContent = view.latestText;
        elements.trackingReturn.textContent = view.returnText;
        elements.trackingReturn.className = view.returnTone;
        elements.trackingGap.textContent = view.gapText;
        elements.trackingGap.className = view.gapTone;
        elements.trackingSummary.textContent = view.summary;
        elements.trackingRoot.hidden = false;
    }

    window.StockAgentReportPreviewTrackingHelpers = {
        formatNumber, formatPct, pctTone, normalizeTrackingRecommendation,
        returnTone, awaitingTrackingPrice, trackingView, renderTracking
    };
})();
