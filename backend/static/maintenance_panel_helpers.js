(function () {
    function notificationDelivery() {
        return window.StockAgentMaintenanceNotificationDelivery || {};
    }
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
    function summaryText(summary, delivery) {
        const counts = maintenanceCounts(summary);
        if (notificationDelivery().isWarning?.(delivery)) {
            return `健康摘要：通知通道異常，${counts.warnings ? `${counts.warnings} 筆可清理資料` : '本機儲存狀態正常'}`;
        }
        if (counts.warnings) return `健康摘要：${counts.warnings} 筆可清理資料，正式分析不受影響`;
        return '健康摘要：本機儲存狀態正常';
    }
    function storageChips(summary, delivery, escapeHtml) {
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
            ${notificationDelivery().chip?.(delivery, escapeHtml) || ''}
        `;
    }
    function defaultResultText(delivery) {
        return notificationDelivery().isWarning?.(delivery)
            ? '通知通道有失敗或重試耗盡項目；請檢查外部 webhook 或憑證，再重跑 sender。'
            : '健康摘要已更新；需要時再展開清理過舊任務、孤兒索引與來源健康事件。';
    }
    function actionMessage(action, payload) {
        const result = payload?.result || {};
        if (action === 'report-index') return `已清理報告索引 ${result.deleted_rows || 0} 列`;
        if (action === 'analysis-history') return `已清理任務 ${result.deleted_jobs || 0} 筆、事件 ${result.deleted_events || 0} 筆`;
        if (action === 'provider-sla') return `已清理來源健康事件 ${result.deleted || 0} 筆`;
        return '維護完成';
    }
    function render(payload, options) {
        const summaryEl = options.summaryEl;
        const listEl = options.listEl;
        const resultEl = options.resultEl;
        const escapeHtml = options.escapeHtml || (value => String(value ?? ''));
        const summary = payload?.summary || {};
        const delivery = payload?.notification_delivery || null;
        if (!summaryEl || !listEl) return;
        summaryEl.textContent = summaryText(summary, delivery);
        listEl.innerHTML = storageChips(summary, delivery, escapeHtml);
        if (resultEl && !resultEl.textContent) resultEl.textContent = defaultResultText(delivery);
    }
    window.StockAgentMaintenancePanelHelpers = {
        actionMessage,
        defaultResultText,
        maintenanceCounts,
        render,
        storageChips,
        summaryText,
        tableCount
    };
})();
