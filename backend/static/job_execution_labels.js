(function () {
    const states = {running: '執行中', waiting_retry: '等待重試', queued: '排隊中', completed: '已完成', terminal_quality: '品質檢查未通過，已停止', failed: '已失敗', cancelled: '已取消', unknown: '狀態未知'};
    const reasons = {registry_unknown: '佇列狀態未知', registry_missing: '找不到佇列紀錄，需核對', registry_conflict: '工作與佇列狀態不一致，需核對', worker_heartbeat_stale: 'Worker 心跳過久，需核對', cooldown: '冷卻中', retry_due: '已到重試時間，等待排程器', retry_queued: '重試已進入佇列'};
    function identity(job) {
        const pipeline = String(job.pipeline_id || '');
        if (!pipeline.startsWith('rerun:')) {
            return {ticker: job.ticker || 'N/A', pipeline: /^v[1-4]$/.test(pipeline) ? pipeline : null};
        }
        // Display only: require an explicit mode and a known generated filename shape.
        // Legacy/ambiguous names cannot establish a mode without source metadata.
        const source = String(job.ticker || '');
        const match = source.match(/^([A-Z0-9]+(?:[._-][A-Z0-9]+)*)_(v[1-4])_report_(?:job_[a-f0-9]{12}|\d{8}_\d{6})\.html$/);
        return match ? {ticker: match[1].replace(/_/g, '.'), pipeline: match[2]}
            : {ticker: '來源股票未知', pipeline: null};
    }
    function label(job) {
        const state = job.execution_state;
        if (!state) return '';
        const warning = job.execution_health === 'needs_check' || job.execution_health === 'unknown';
        return (states[state] || '狀態未知') + (warning ? '（待確認）' : '');
    }
    function details(job) {
        const parts = [reasons[job.execution_reason_code] || ''];
        if (job.stall_assessment === 'suspected_stall') parts.unshift('疑似停滯，需核對（僅依更新時間）');
        if (job.execution_state === 'waiting_retry' && job.retry_at) {
            const when = new Date(job.retry_at);
            if (!Number.isNaN(when.getTime())) parts.push(`${job.retry_at_basis === 'registry' ? '排程' : '記錄的預計'}重試時間 ${when.toLocaleString('zh-TW')}`);
        }
        if (job.registry) parts.push(`RQ：${job.registry.state || 'unknown'}`);
        if (job.last_progress?.at) parts.push(`最後進度 ${new Date(job.last_progress.at).toLocaleTimeString('zh-TW')}`);
        if (job.attempts?.events_sampled) parts.push(`最近事件內模型嘗試 ${Number(job.attempts.provider_requests_sampled || 0)} 次`);
        return parts.filter(Boolean).join(' · ');
    }
    window.StockAgentJobExecutionLabels = {label, details, identity};
})();
