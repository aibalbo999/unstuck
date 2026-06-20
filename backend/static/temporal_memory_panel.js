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
        const rows = backtests.slice(0, 3).map(row => `
            <span>${escapeHtml(row.horizon_months || '?')}M · ${escapeHtml(row.outcome || 'pending')} · ROI ${escapeHtml(row.strategy_roi_pct ?? 'N/A')}%</span>
        `).join('');
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
