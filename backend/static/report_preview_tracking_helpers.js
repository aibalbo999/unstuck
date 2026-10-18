(function () {
    function finiteNumber(value) {
        if (typeof value !== 'number' && (typeof value !== 'string' || !value.trim())) return NaN;
        return Number(value);
    }
    function formatNumber(value) {
        const number = finiteNumber(value);
        if (!Number.isFinite(number)) return '尚未確認';
        return number.toLocaleString('zh-TW', { maximumFractionDigits: 2 });
    }

    function formatPct(value) {
        const number = finiteNumber(value);
        if (!Number.isFinite(number)) return '尚未確認';
        return `${number > 0 ? '+' : ''}${number.toFixed(2)}%`;
    }

    function pctTone(value) {
        const number = finiteNumber(value);
        if (!Number.isFinite(number) || number === 0) return 'is-neutral';
        return number > 0 ? 'is-positive' : 'is-negative';
    }

    function normalizeTrackingRecommendation(value) {
        return window.StockAgentUi?.normalizeRecommendation
            ? window.StockAgentUi.normalizeRecommendation(value)
            : String(value || '');
    }

    function returnTone(tracking) {
        const value = finiteNumber(tracking && tracking.return_pct);
        if (!Number.isFinite(value) || value === 0) return 'is-neutral';
        if (tracking.status === 'target_hit' || tracking.status === 'avoided_loss') return 'is-positive';
        if (['避免', '放空'].includes(normalizeTrackingRecommendation(tracking.recommendation))) return value < 0 ? 'is-positive' : 'is-negative';
        return value > 0 ? 'is-positive' : 'is-negative';
    }

    function awaitingTrackingPrice(tracking) {
        const initial = finiteNumber(tracking?.initial_price);
        const latest = finiteNumber(tracking?.latest_price);
        return tracking?.status === 'tracked'
            && !tracking.snapshot_refreshed_at
            && finiteNumber(tracking.return_pct) === 0
            && Number.isFinite(initial) && initial > 0 && initial === latest;
    }

    function trackingView(tracking, preview = {}) {
        const awaiting = awaitingTrackingPrice(tracking);
        const missingGap = preview.kind === 'swing_trade' ? '不適用（短線模式不比較12個月目標）'
            : !Number.isFinite(finiteNumber(tracking.target_12m)) ? '尚未確認（未提供可比較的目標價）'
                : !Number.isFinite(finiteNumber(tracking.latest_price)) ? '尚未確認（未取得可比較的最新股價）'
                    : '尚未確認（目前價格與目標無法計算差距）';
        return {
            latestText: formatNumber(tracking.latest_price),
            returnText: awaiting ? '待新價格' : formatPct(tracking.return_pct),
            returnTone: returnTone(tracking),
            gapText: Number.isFinite(finiteNumber(tracking.target_12m_gap_pct))
                ? formatPct(tracking.target_12m_gap_pct) : missingGap,
            gapTone: pctTone(tracking.target_12m_gap_pct),
            summary: awaiting ? '尚待新價格更新後計算建議後報酬。' : (tracking.summary || '已建立決策追蹤。')
        };
    }

    function renderTracking(tracking, elements, preview = {}) {
        if (!elements.trackingRoot) return;
        if (!tracking || !tracking.status || tracking.status === 'unavailable') {
            elements.trackingRoot.hidden = true;
            return;
        }
        const view = trackingView(tracking, preview);
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
