(function () {
    function tableCount(summary, tableName) {
        const value = summary?.task_db?.tables?.[tableName] ?? summary?.cache_db?.tables?.[tableName];
        return value === null || value === undefined ? '未建立' : String(value);
    }

    function render(payload, options) {
        const summaryEl = options.summaryEl;
        const listEl = options.listEl;
        const resultEl = options.resultEl;
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        const summary = payload?.summary || {};
        const orphans = summary.cache_db?.report_index_orphans || {};
        const history = summary.task_db?.analysis_history || {};
        if (!summaryEl || !listEl) return;

        const orphanRows = Number(orphans.orphan_rows || 0);
        const staleJobs = Number(history.stale_terminal_jobs || 0);
        const orphanEvents = Number(history.orphan_events || 0);
        const warnings = orphanRows + staleJobs + orphanEvents;
        summaryEl.textContent = warnings
            ? `健康摘要：${warnings} 筆可清理資料，正式分析不受影響`
            : '健康摘要：本機儲存狀態正常';
        listEl.innerHTML = `
            <span class="provider-sla-chip maintenance-chip ${orphanRows ? 'is-warning' : 'is-ok'}">
                報告索引 <strong>${escapeHtml(String(tableCount(summary, 'reports')))}</strong>
                <em>孤兒列 ${escapeHtml(String(orphanRows))}</em>
            </span>
            <span class="provider-sla-chip maintenance-chip ${(staleJobs || orphanEvents) ? 'is-warning' : 'is-ok'}">
                任務紀錄 <strong>${escapeHtml(tableCount(summary, 'analysis_jobs'))}</strong>
                <em>可清任務 ${escapeHtml(String(staleJobs))} · 孤兒事件 ${escapeHtml(String(orphanEvents))}</em>
            </span>
            <span class="provider-sla-chip maintenance-chip is-ok">
                來源健康紀錄 <strong>${escapeHtml(tableCount(summary, 'provider_sla_events'))}</strong>
                <em>依保留天數清理</em>
            </span>
        `;
        if (resultEl && !resultEl.textContent) {
            resultEl.textContent = '健康摘要已更新；需要時再展開清理過舊任務、孤兒索引與來源健康事件。';
        }
    }

    function actionMessage(action, payload) {
        const result = payload?.result || {};
        if (action === 'report-index') return `已清理報告索引 ${result.deleted_rows || 0} 列`;
        if (action === 'analysis-history') return `已清理任務 ${result.deleted_jobs || 0} 筆、事件 ${result.deleted_events || 0} 筆`;
        if (action === 'provider-sla') return `已清理來源健康事件 ${result.deleted || 0} 筆`;
        return '維護完成';
    }

    function bind(options) {
        const apiClient = options.apiClient;
        const refreshEl = options.refreshEl;
        const resultEl = options.resultEl;
        const actionButtons = options.actionButtons || {};
        const allButtons = [refreshEl, ...Object.values(actionButtons)].filter(Boolean);

        async function loadSummary() {
            if (!apiClient || !options.summaryEl || !options.listEl) return;
            try {
                allButtons.forEach(button => button.setAttribute('disabled', 'disabled'));
                const payload = await apiClient.fetchMaintenanceSummary();
                render(payload, options);
            } catch (err) {
                console.error('Failed to load maintenance summary', err);
                options.summaryEl.textContent = '本機維護狀態讀取失敗';
                options.listEl.innerHTML = '<span class="provider-sla-chip is-warning">請稍後重試</span>';
            } finally {
                allButtons.forEach(button => button.removeAttribute('disabled'));
            }
        }

        async function runAction(action, runner) {
            if (!runner) return;
            try {
                allButtons.forEach(button => button.setAttribute('disabled', 'disabled'));
                if (resultEl) resultEl.textContent = '維護中...';
                const payload = await runner();
                if (resultEl) resultEl.textContent = actionMessage(action, payload);
                await loadSummary();
            } catch (err) {
                console.error('Maintenance action failed', err);
                if (resultEl) resultEl.textContent = '維護失敗，請稍後重試';
            } finally {
                allButtons.forEach(button => button.removeAttribute('disabled'));
            }
        }

        if (refreshEl) refreshEl.addEventListener('click', loadSummary);
        if (actionButtons.reportIndex) {
            actionButtons.reportIndex.addEventListener('click', () => runAction('report-index', apiClient.cleanupReportIndex));
        }
        if (actionButtons.analysisHistory) {
            actionButtons.analysisHistory.addEventListener('click', () => runAction('analysis-history', apiClient.cleanupAnalysisHistory));
        }
        if (actionButtons.providerSla) {
            actionButtons.providerSla.addEventListener('click', () => runAction('provider-sla', apiClient.cleanupProviderSla));
        }
        loadSummary();
    }

    document.addEventListener('DOMContentLoaded', () => {
        const apiClient = window.StockAgentApiClient;
        const ui = window.StockAgentUi;
        const panel = document.getElementById('maintenance-panel');
        if (!panel || !apiClient) return;
        bind({
            apiClient,
            escapeHtml: ui?.escapeHtml,
            summaryEl: document.getElementById('maintenance-summary'),
            listEl: document.getElementById('maintenance-list'),
            resultEl: document.getElementById('maintenance-result'),
            refreshEl: document.getElementById('maintenance-refresh'),
            actionButtons: {
                reportIndex: document.getElementById('maintenance-clean-report-index'),
                analysisHistory: document.getElementById('maintenance-clean-analysis-history'),
                providerSla: document.getElementById('maintenance-clean-provider-sla')
            }
        });
    });

    window.StockAgentMaintenancePanel = { render, bind };
})();
