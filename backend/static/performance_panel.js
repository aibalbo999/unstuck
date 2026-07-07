(function () {
    function fmtPct(value) {
        const num = Number(value);
        return Number.isFinite(num) ? `${num.toFixed(2)}%` : '0.00%';
    }

    function fmtPrice(value) {
        const num = Number(value);
        return Number.isFinite(num) ? num.toLocaleString('zh-TW', { maximumFractionDigits: 2 }) : 'N/A';
    }

    function sampleConfidenceLabel(total) {
        const count = Number(total || 0);
        if (!count) return '尚無樣本';
        return count >= 10 ? '樣本基礎可追蹤' : '樣本不足，僅供觀察';
    }

    function tone(row) {
        if ((row.outcome || '') === 'hit') return 'ok';
        if (Number(row.strategy_roi_pct || 0) < 0) return 'critical';
        return 'warning';
    }

    function render(payload, options) {
        const escapeHtml = options.escapeHtml;
        const summary = payload?.summary || {};
        const horizons = payload?.by_horizon || [];
        const details = payload?.details || [];
        options.summaryEl.textContent = `命中率 ${fmtPct(summary.hit_rate_pct)} · 平均 ROI ${fmtPct(summary.average_strategy_roi_pct)} · ${summary.total_predictions || 0} 筆 · ${sampleConfidenceLabel(summary.total_predictions)}`;
        const horizonHtml = horizons.map(row => `
            <span class="performance-chip is-${Number(row.total || 0) >= 10 ? 'ok' : 'warning'}">
                <strong>${escapeHtml(row.horizon_months)}M</strong>
                <em>命中率 ${escapeHtml(fmtPct(row.hit_rate_pct))} · ${escapeHtml(sampleConfidenceLabel(row.total))}</em>
                <span>ROI ${escapeHtml(fmtPct(row.average_strategy_roi_pct))} · ${escapeHtml(row.total || 0)} 筆</span>
            </span>
        `).join('');
        const detailHtml = details.slice(0, 8).map(row => `
            <span class="performance-chip recent-backtest is-${tone(row)}">
                <strong>${escapeHtml(row.ticker || 'N/A')} · ${escapeHtml(row.horizon_months)}M</strong>
                <em>${escapeHtml(row.outcome || 'miss')} · ROI ${escapeHtml(fmtPct(row.strategy_roi_pct))}</em>
                <span>${escapeHtml(row.recommendation || '')} ${escapeHtml(fmtPrice(row.initial_price))} → ${escapeHtml(fmtPrice(row.actual_price))}</span>
            </span>
        `).join('');
        options.listEl.innerHTML = (horizonHtml + detailHtml) || '<span class="performance-chip is-warning">尚無到期回測結果</span>';
    }

    window.StockAgentPerformancePanel = { render };
})();
