(function () {
    function fmtPct(value) {
        if (value === null || value === undefined || value === '') return 'N/A';
        const num = Number(value);
        return Number.isFinite(num) ? `${num.toFixed(2)}%` : 'N/A';
    }

    function fmtPrice(value) {
        if (value === null || value === undefined || value === '') return 'N/A';
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

    function horizonLabel(row) {
        return row.horizon_trading_days ? `${row.horizon_trading_days} 交易日` : `${row.horizon_months || '?'}M`;
    }

    function statusLabel(row) {
        const labels = {target_first: '先達目標', stop_first: '先觸停損', horizon_exit: '期滿退出',
            not_entered: '未成交', no_trade: '不交易', ambiguous: '日內順序不明', insufficient_data: '資料不足'};
        return labels[row.status] || row.outcome || '未評分';
    }

    function render(payload, options) {
        const escapeHtml = options.escapeHtml;
        const summary = payload?.summary || {};
        const horizons = payload?.by_horizon || [];
        const details = payload?.details || [];
        const trade = payload?.trade_summary || {};
        options.summaryEl.textContent = `月度研究：命中率 ${fmtPct(summary.hit_rate_pct)} · 平均 ROI ${fmtPct(summary.average_strategy_roi_pct)} · ${summary.total_predictions || 0} 筆 · ${sampleConfidenceLabel(summary.total_predictions)}｜交易計畫：命中率 ${fmtPct(trade.hit_rate_pct)} · 平均毛 ROI ${fmtPct(trade.average_strategy_roi_pct)} · ${trade.total_evaluations || 0} 筆`;
        const horizonHtml = horizons.map(row => `
            <span class="performance-chip is-${Number(row.total || 0) >= 10 ? 'ok' : 'warning'}">
                <strong>${escapeHtml(row.horizon_months)}M</strong>
                <em>命中率 ${escapeHtml(fmtPct(row.hit_rate_pct))} · ${escapeHtml(sampleConfidenceLabel(row.total))}</em>
                <span>ROI ${escapeHtml(fmtPct(row.average_strategy_roi_pct))} · ${escapeHtml(row.total || 0)} 筆</span>
            </span>
        `).join('');
        const tradeHtml = Object.entries(payload?.trade_by_horizon || {}).map(([days, row]) => `
            <span class="performance-chip is-warning">
                <strong>${escapeHtml(days)} 交易日</strong>
                <em>命中率 ${escapeHtml(fmtPct(row.hit_rate_pct))} · 未評分 ${escapeHtml(row.unscored_count || 0)} 筆</em>
                <span>毛 ROI ${escapeHtml(fmtPct(row.average_strategy_roi_pct))} · ${escapeHtml(row.total_evaluations || 0)} 筆</span>
            </span>
        `).join('');
        const detailHtml = details.slice(0, 8).map(row => `
            <span class="performance-chip recent-backtest is-${tone(row)}">
                <strong>${escapeHtml(row.ticker || 'N/A')} · ${escapeHtml(horizonLabel(row))}</strong>
                <em>${escapeHtml(statusLabel(row))} · 毛 ROI ${escapeHtml(fmtPct(row.strategy_roi_pct))}</em>
                <span>${escapeHtml(row.recommendation || '')} ${escapeHtml(fmtPrice(row.entry_price ?? row.initial_price))} → ${escapeHtml(fmtPrice(row.exit_price ?? row.actual_price))}</span>
            </span>
        `).join('');
        options.listEl.innerHTML = (horizonHtml + tradeHtml + detailHtml) || '<span class="performance-chip is-warning">尚無到期回測結果</span>';
    }

    window.StockAgentPerformancePanel = { render };
})();
