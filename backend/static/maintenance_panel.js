(function () {
    const helpers = window.StockAgentMaintenancePanelHelpers;

    function render(payload, options) {
        helpers.render(payload, options);
    }

    function setButtonsDisabled(buttons, disabled) {
        buttons.forEach(button => {
            if (!button) return;
            if (disabled) button.setAttribute('disabled', 'disabled');
            else button.removeAttribute('disabled');
        });
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
                setButtonsDisabled(allButtons, true);
                const payload = await apiClient.fetchMaintenanceSummary();
                const opsPayload = apiClient.fetchOpsDashboard ? await apiClient.fetchOpsDashboard().catch(err => {
                    console.warn('Failed to load notification delivery health', err);
                    return {};
                }) : {};
                payload.notification_delivery = opsPayload.notification_delivery;
                payload.queue = opsPayload.queue;
                render(payload, options);
            } catch (err) {
                console.error('Failed to load maintenance summary', err);
                options.summaryEl.textContent = '本機維護狀態讀取失敗';
                options.listEl.innerHTML = '<span class="provider-sla-chip is-warning">請稍後重試</span>';
            } finally {
                setButtonsDisabled(allButtons, false);
            }
        }

        async function runAction(action, runner) {
            if (!runner) return;
            try {
                setButtonsDisabled(allButtons, true);
                if (resultEl) resultEl.textContent = '維護中...';
                const payload = await runner();
                if (payload && resultEl) resultEl.textContent = helpers.actionMessage(action, payload);
                if (payload) await loadSummary();
            } catch (err) {
                console.error('Maintenance action failed', err);
                if (resultEl) resultEl.textContent = '維護失敗，請稍後重試';
            } finally {
                setButtonsDisabled(allButtons, false);
            }
        }

        if (refreshEl) refreshEl.addEventListener('click', loadSummary);
        [
            ['reportIndex', 'report-index', 'cleanupReportIndex'],
            ['analysisHistory', 'analysis-history', 'cleanupAnalysisHistory'],
            ['providerSla', 'provider-sla', 'cleanupProviderSla'],
            ['failedQueue', 'failed-queue', 'cleanupFailedQueue']
        ].forEach(([key, action, method]) => {
            if (action === 'failed-queue') actionButtons[key]?.addEventListener('click', () => runAction(action, async () => {
                const preview = await apiClient.previewFailedQueue(), count = Number(preview?.result?.stale_failed_jobs || 0), notify = options.notify || window.StockAgentNotify || window.StockAgentNotificationCenter?.create?.();
                if (!(count > 0)) { if (resultEl) resultEl.textContent = '沒有可清理的過期失敗任務'; return null; }
                if (!notify?.confirm || !(await notify.confirm(`清理前先確認：將刪除 ${count} 筆過期失敗任務。`, { title: '清理過期失敗任務', confirmLabel: '刪除', danger: true }))) { if (resultEl) resultEl.textContent = '已取消清理過期失敗任務'; return null; }
                return apiClient.cleanupFailedQueue();
            })); else actionButtons[key]?.addEventListener('click', () => runAction(action, apiClient[method]));
        });
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
                providerSla: document.getElementById('maintenance-clean-provider-sla'),
                failedQueue: document.getElementById('maintenance-clean-failed-queue')
            }
        });
    });

    window.StockAgentMaintenancePanel = { render, bind };
})();
