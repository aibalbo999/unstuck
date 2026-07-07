(function () {
    function countValues(values) {
        return Object.values(values || {}).reduce((sum, count) => sum + Number(count || 0), 0);
    }

    function llmSummary(job) {
        const stage = job.stage_summary || {};
        const retries = Number(stage.llm_retry_count_sampled ?? countValues(job.llm_retry_counts));
        const errors = Number(stage.llm_error_count_sampled ?? countValues(job.llm_error_counts));
        const parts = [];
        if (retries) parts.push(`模型重試 ${retries} 次`);
        if (errors) parts.push(`模型錯誤 ${errors} 次`);
        return parts.join(' · ');
    }

    function progressLabel(stage) {
        const current = Number(stage?.progress_current);
        const total = Number(stage?.progress_total);
        if (Number.isFinite(current) && Number.isFinite(total) && total > 0) {
            return `${current}/${total}`;
        }
        if (Number.isFinite(stage?.report_done_count_sampled) && Number(stage.report_done_count_sampled) > 0) {
            return `已產生 ${Number(stage.report_done_count_sampled)} 份`;
        }
        return '';
    }

    function statusLabel(job, showingHistory) {
        if (showingHistory && job.status === 'done') return '最近完成';
        if (job.status === 'running') return '執行中';
        if (job.status === 'queued') return '排隊中';
        if (job.status === 'waiting_retry') return '等待重試';
        if (job.status === 'error') return '失敗';
        return job.status || 'unknown';
    }

    function render(payload, options) {
        const summaryEl = options.summaryEl;
        const listEl = options.listEl;
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        const pipelineModeLabel = options.pipelineModeLabel
            || window.StockAgentUi?.pipelineModeLabel
            || (value => String(value || 'N/A'));
        if (!summaryEl || !listEl) return;

        const jobs = payload?.jobs || [];
        const active = jobs.filter(job => ['queued', 'running', 'waiting_retry'].includes(job.status));
        const showingHistory = !active.length && jobs.length;
        summaryEl.textContent = active.length
            ? `${active.length} 個分析任務執行中`
            : (jobs.length ? '目前無執行中任務，以下為最近完成任務' : '尚無任務紀錄');
        listEl.innerHTML = jobs.length
            ? jobs.slice(0, 5).map(job => {
                const stage = job.stage_summary || {};
                const modelHealth = llmSummary(job);
                const tone = ['running', 'waiting_retry'].includes(job.status) ? 'warning' : job.status === 'done' ? 'ok' : 'critical';
                const phase = stage.phase || (job.status === 'done' ? '完成' : 'idle');
                const progress = progressLabel(stage);
                const details = [phase, progress, modelHealth].filter(Boolean).join(' · ');
                const pipelineLabel = job.pipeline_id ? pipelineModeLabel(job.pipeline_id) : 'N/A';
                return `
                    <span class="provider-sla-chip is-${tone}" title="${escapeHtml(stage.message || job.error || '')}">
                        ${escapeHtml(job.ticker || 'N/A')} · ${escapeHtml(pipelineLabel)}
                        <strong>${escapeHtml(statusLabel(job, showingHistory))}</strong>
                        <em>${escapeHtml(details)}</em>
                    </span>
                `;
            }).join('')
            : '<span class="provider-sla-chip is-ok">等待下一次分析任務</span>';
    }

    window.StockAgentActiveJobsPanel = { render };
})();
