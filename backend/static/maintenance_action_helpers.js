(function () {
    const actions = {
        'report-index': {
            preview: 'previewReportIndex',
            run: 'cleanupReportIndex',
            count: result => Number(result.orphan_rows || 0),
            message: result => `清理前先確認：將刪除 ${Number(result.orphan_rows || 0)} 筆孤兒報告索引。`,
            empty: '沒有可清理的孤兒報告索引',
            cancel: '已取消清理孤兒報告索引'
        },
        'analysis-history': {
            preview: 'previewAnalysisHistory',
            run: 'cleanupAnalysisHistory',
            count: result => Number(result.stale_terminal_jobs || 0) + Number(result.orphan_events || 0),
            message: result => `清理前先確認：將刪除 ${Number(result.stale_terminal_jobs || 0)} 筆過期任務、${Number(result.orphan_events || 0)} 筆孤立事件。`,
            empty: '沒有可清理的過期任務或孤立事件',
            cancel: '已取消清理任務紀錄'
        },
        'provider-sla': {
            preview: 'previewProviderSla',
            run: 'cleanupProviderSla',
            count: result => Number(result.stale_events || 0),
            message: result => `清理前先確認：將刪除 ${Number(result.stale_events || 0)} 筆過期來源健康紀錄。`,
            empty: '沒有可清理的過期來源健康紀錄',
            cancel: '已取消清理來源健康紀錄'
        },
        'failed-queue': {
            preview: 'previewFailedQueue',
            run: 'cleanupFailedQueue',
            count: result => Number(result.stale_failed_jobs || 0),
            message: result => `清理前先確認：將刪除 ${Number(result.stale_failed_jobs || 0)} 筆過期失敗任務。`,
            empty: '沒有可清理的過期失敗任務',
            cancel: '已取消清理過期失敗任務'
        }
    };

    function details(action, payload) {
        const config = actions[action];
        const result = payload?.result || {};
        return config ? { count: config.count(result), message: config.message(result), empty: config.empty } : { count: 0, message: '', empty: '維護動作不存在' };
    }

    async function runConfirmedAction({ action, apiClient, notify, onMessage }) {
        const config = actions[action];
        if (!config) return null;
        const preview = await apiClient[config.preview]();
        const summary = details(action, preview);
        if (!(summary.count > 0)) { onMessage?.(summary.empty); return null; }
        const confirmed = notify?.confirm ? await notify.confirm(summary.message, { title: '確認清理', confirmLabel: '刪除', danger: true }) : false;
        if (!confirmed) { onMessage?.(actions[action].cancel); return null; }
        return apiClient[config.run]();
    }

    window.StockAgentMaintenanceActionHelpers = { details, runConfirmedAction };
})();
