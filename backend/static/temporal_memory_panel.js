(function () {
    function render(memory, root, escapeHtml) {
        if (!root) return;
        const prompt = memory?.reflection_prompt || '';
        const previous = memory?.previous_report || {};
        const backtests = memory?.backtests || [];
        if (!prompt && !previous.filename) {
            root.hidden = true;
            root.innerHTML = '';
            return;
        }
        const rows = backtests.slice(0, 3).map(row => {
            const horizon = row.horizon_trading_days ? `${row.horizon_trading_days} 交易日` : `${row.horizon_months || '?'}M`;
            const roi = row.strategy_roi_pct === null || row.strategy_roi_pct === undefined ? 'N/A' : `${row.strategy_roi_pct}%`;
            return `<span>${escapeHtml(horizon)} · ${escapeHtml(row.status || row.outcome || '未評分')} · 毛 ROI ${escapeHtml(roi)}</span>`;
        }).join('');
        root.innerHTML = `
            <strong>Agent 歷史反思</strong>
            <span>${escapeHtml(previous.date || '')} ${escapeHtml(previous.recommendation || '')} ${escapeHtml(previous.target_12m || '')}</span>
            <p>${escapeHtml(prompt).replace(/\n/g, '<br>')}</p>
            ${rows ? `<div class="temporal-memory-backtests">${rows}</div>` : ''}
        `;
        root.hidden = false;
    }

    window.StockAgentTemporalMemoryPanel = { render };
})();
