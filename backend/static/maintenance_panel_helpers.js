(function () {
    function notificationDelivery() { return window.StockAgentMaintenanceNotificationDelivery || {}; }
    function tableCount(summary, tableName) {
        const value = summary?.task_db?.tables?.[tableName] ?? summary?.cache_db?.tables?.[tableName];
        return value === null || value === undefined ? '未建立' : String(value);
    }
    function maintenanceCounts(summary) {
        const orphans = summary.cache_db?.report_index_orphans || {};
        const history = summary.task_db?.analysis_history || {};
        const orphanRows = Number(orphans.orphan_rows || 0);
        const staleJobs = Number(history.stale_terminal_jobs || 0);
        const orphanEvents = Number(history.orphan_events || 0);
        return { orphanRows, staleJobs, orphanEvents, warnings: orphanRows + staleJobs + orphanEvents };
    }
    function queueStats(queue) {
        const failed = Number((queue?.registries || {}).failed), recent = Number(queue?.failed_recent), stale = Number(queue?.failed_stale), depth = Number(queue?.depth);
        return { available: queue?.available !== false, depth: Number.isFinite(depth) && depth >= 0 ? depth : 0, failed: Number.isFinite(failed) && failed >= 0 ? failed : 0, recent: Number.isFinite(recent) && recent >= 0 ? recent : failed, stale: Number.isFinite(stale) && stale >= 0 ? stale : 0 };
    }
    function queueAttention(queue) {
        if (!queue) return '';
        const stats = queueStats(queue);
        if (!stats.available) return '分析佇列無法使用';
        if (stats.recent > 0) return `分析佇列有 ${stats.recent} 筆近期失敗任務`;
        return stats.stale > 0 ? `分析佇列有 ${stats.stale} 筆過期失敗殘留` : '';
    }
    function summaryText(summary, delivery, queue) {
        const counts = maintenanceCounts(summary);
        const queueWarning = queueAttention(queue);
        if (notificationDelivery().isWarning?.(delivery)) {
            return `健康摘要：通知通道異常${queueWarning ? `；${queueWarning}` : ''}，${counts.warnings ? `${counts.warnings} 筆可清理資料` : '本機儲存狀態正常'}`;
        }
        if (queueWarning) return `健康摘要：${queueWarning}，${counts.warnings ? `${counts.warnings} 筆可清理資料` : '本機儲存狀態正常'}`;
        if (counts.warnings) return `健康摘要：${counts.warnings} 筆可清理資料，正式分析不受影響`;
        return '健康摘要：本機儲存狀態正常';
    }
    function queueChip(queue, escapeHtml) {
        if (!queue) return '';
        const stats = queueStats(queue);
        const tone = stats.available && stats.recent === 0 && stats.stale === 0 ? 'is-ok' : 'is-warning';
        const status = stats.available ? '可用' : '無法使用';
        return `<span class="provider-sla-chip maintenance-chip ${tone}">分析佇列 <strong>${escapeHtml(status)}</strong><em>失敗 ${escapeHtml(String(stats.failed))} · 近期 ${escapeHtml(String(stats.recent))} · 過期 ${escapeHtml(String(stats.stale))} · 排隊 ${escapeHtml(String(stats.depth))}</em></span>`;
    }
    function storageChips(summary, delivery, escapeHtml, queue) {
        const counts = maintenanceCounts(summary);
        return `
            <span class="provider-sla-chip maintenance-chip ${counts.orphanRows ? 'is-warning' : 'is-ok'}">
                報告索引 <strong>${escapeHtml(String(tableCount(summary, 'reports')))}</strong>
                <em>孤兒列 ${escapeHtml(String(counts.orphanRows))}</em>
            </span>
            <span class="provider-sla-chip maintenance-chip ${(counts.staleJobs || counts.orphanEvents) ? 'is-warning' : 'is-ok'}">
                任務紀錄 <strong>${escapeHtml(tableCount(summary, 'analysis_jobs'))}</strong>
                <em>可清任務 ${escapeHtml(String(counts.staleJobs))} · 孤兒事件 ${escapeHtml(String(counts.orphanEvents))}</em>
            </span>
            <span class="provider-sla-chip maintenance-chip is-ok">
                來源健康紀錄 <strong>${escapeHtml(tableCount(summary, 'provider_sla_events'))}</strong>
                <em>依保留天數清理</em>
            </span>
            ${queueChip(queue, escapeHtml)}
            ${notificationDelivery().chip?.(delivery, escapeHtml) || ''}
        `;
    }
    function defaultResultText(delivery, queue) {
        const queueWarning = queueAttention(queue);
        if (queueWarning) return `${queueWarning}；請安排人工清理，不會自動清除或重試。`;
        return notificationDelivery().isWarning?.(delivery)
            ? '通知通道有失敗或重試耗盡項目；請檢查外部 webhook 或憑證，再重跑 sender。'
            : '健康摘要已更新；需要時再展開清理過舊任務、孤兒索引與來源健康事件。';
    }
    function actionMessage(action, payload) {
        const result = payload?.result || {};
        if (action === 'report-index') return `已清理報告索引 ${result.deleted_rows || 0} 列`;
        if (action === 'analysis-history') return `已清理任務 ${result.deleted_jobs || 0} 筆、事件 ${result.deleted_events || 0} 筆`;
        if (action === 'provider-sla') return `已清理來源健康事件 ${result.deleted || 0} 筆`;
        if (action === 'failed-queue') return `已清理過期失敗任務 ${result.deleted_jobs || 0} 筆`;
        return '維護完成';
    }
    function render(payload, options) {
        const summaryEl = options.summaryEl;
        const listEl = options.listEl;
        const resultEl = options.resultEl;
        const escapeHtml = options.escapeHtml || (value => String(value ?? ''));
        const summary = payload?.summary || {};
        const delivery = payload?.notification_delivery || null;
        const queue = payload?.queue || null;
        if (!summaryEl || !listEl) return;
        summaryEl.textContent = summaryText(summary, delivery, queue);
        listEl.innerHTML = storageChips(summary, delivery, escapeHtml, queue);
        if (resultEl && !resultEl.textContent) resultEl.textContent = defaultResultText(delivery, queue);
    }
    window.StockAgentMaintenancePanelHelpers = {
        actionMessage,
        defaultResultText,
        maintenanceCounts,
        render, storageChips,
        summaryText,
        tableCount
    };
})();
