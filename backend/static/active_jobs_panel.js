(function () {
    function render(payload, options) {
        const summaryEl = options.summaryEl;
        const listEl = options.listEl;
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        if (!summaryEl || !listEl) return;

        const jobs = payload?.jobs || [];
        const active = jobs.filter(job => ['queued', 'running'].includes(job.status));
        summaryEl.textContent = active.length
            ? `${active.length} 個分析任務執行中`
            : (jobs.length ? '目前無執行中任務' : '尚無任務紀錄');
        listEl.innerHTML = jobs.length
            ? jobs.slice(0, 5).map(job => {
                const last = job.last_event || {};
                const errors = Object.entries(job.llm_error_counts || {})
                    .slice(0, 2)
                    .map(([key, count]) => `${key} ${count}`)
                    .join(' · ');
                const tone = job.status === 'running' ? 'warning' : job.status === 'done' ? 'ok' : 'critical';
                return `
                    <span class="provider-sla-chip is-${tone}" title="${escapeHtml(last.message || job.error || '')}">
                        ${escapeHtml(job.ticker || 'N/A')} · ${escapeHtml(job.pipeline_id || 'N/A')}
                        <strong>${escapeHtml(job.status || 'unknown')}</strong>
                        <em>${escapeHtml(last.phase || 'idle')}${errors ? ` · ${escapeHtml(errors)}` : ''}</em>
                    </span>
                `;
            }).join('')
            : '<span class="provider-sla-chip is-ok">等待下一次分析任務</span>';
    }

    window.StockAgentActiveJobsPanel = { render };
})();
