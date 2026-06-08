(function () {
    function countValues(values) {
        return Object.values(values || {}).reduce((sum, count) => sum + Number(count || 0), 0);
    }

    function llmSummary(job) {
        const retries = countValues(job.llm_retry_counts);
        const errors = countValues(job.llm_error_counts);
        const parts = [];
        if (retries) parts.push(`模型重試 ${retries} 次`);
        if (errors) parts.push(`模型錯誤 ${errors} 次`);
        return parts.join(' · ');
    }

    function statusLabel(job, showingHistory) {
        if (showingHistory && job.status === 'done') return '最近完成';
        if (job.status === 'running') return '執行中';
        if (job.status === 'queued') return '排隊中';
        if (job.status === 'error') return '失敗';
        return job.status || 'unknown';
    }

    function render(payload, options) {
        const summaryEl = options.summaryEl;
        const listEl = options.listEl;
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        if (!summaryEl || !listEl) return;

        const jobs = payload?.jobs || [];
        const active = jobs.filter(job => ['queued', 'running'].includes(job.status));
        const showingHistory = !active.length && jobs.length;
        summaryEl.textContent = active.length
            ? `${active.length} 個分析任務執行中`
            : (jobs.length ? '目前無執行中任務，以下為最近完成任務' : '尚無任務紀錄');
        listEl.innerHTML = jobs.length
            ? jobs.slice(0, 5).map(job => {
                const last = job.last_event || {};
                const modelHealth = llmSummary(job);
                const tone = job.status === 'running' ? 'warning' : job.status === 'done' ? 'ok' : 'critical';
                const phase = last.phase || (job.status === 'done' ? '完成' : 'idle');
                return `
                    <span class="provider-sla-chip is-${tone}" title="${escapeHtml(last.message || job.error || '')}">
                        ${escapeHtml(job.ticker || 'N/A')} · ${escapeHtml(job.pipeline_id || 'N/A')}
                        <strong>${escapeHtml(statusLabel(job, showingHistory))}</strong>
                        <em>${escapeHtml(phase)}${modelHealth ? ` · ${escapeHtml(modelHealth)}` : ''}</em>
                    </span>
                `;
            }).join('')
            : '<span class="provider-sla-chip is-ok">等待下一次分析任務</span>';
    }

    window.StockAgentActiveJobsPanel = { render };
})();
