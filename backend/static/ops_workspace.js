(function () {
    function byId(id) {
        return document.getElementById(id);
    }

    function create(options) {
        const apiClient = options.apiClient;
        const ui = options.ui;
        const elements = {
            providerSlaSummary: byId('provider-sla-summary'),
            providerSlaList: byId('provider-sla-list'),
            providerSlaRefresh: byId('provider-sla-refresh'),
            providerSlaWindow: byId('provider-sla-window'),
            activeJobsSummary: byId('active-jobs-summary'),
            activeJobsList: byId('active-jobs-list'),
            activeJobsRefresh: byId('active-jobs-refresh'),
            apiQuotaSummary: byId('api-quota-summary'),
            apiQuotaList: byId('api-quota-list'),
            apiQuotaRefresh: byId('api-quota-refresh')
        };
        let loaded = false;
        let providerSlaDirty = false;
        const watchlistPanel = window.StockAgentWatchlistPanel.create({
            apiClient,
            escapeHtml: ui.escapeHtml,
            onRunQueued: loadActiveJobs,
            elements: {
                summaryEl: byId('watchlist-summary'),
                listEl: byId('watchlist-list'),
                tickerInput: byId('watchlist-ticker-input'),
                pipelineSelect: byId('watchlist-pipeline-select'),
                preMarketInput: byId('watchlist-pre-market'),
                postMarketInput: byId('watchlist-post-market'),
                enabledInput: byId('watchlist-enabled'),
                saveBtn: byId('watchlist-save-btn'),
                runBtn: byId('watchlist-run-btn'),
                refreshBtn: byId('watchlist-refresh')
            }
        });

        function renderProviderSla(payload) {
            window.StockAgentProviderSlaPanel.render(payload, {
                summaryEl: elements.providerSlaSummary,
                listEl: elements.providerSlaList,
                windowEl: elements.providerSlaWindow,
                escapeHtml: ui.escapeHtml
            });
        }

        async function loadProviderSla() {
            if (!elements.providerSlaSummary || !elements.providerSlaList) return;
            try {
                if (elements.providerSlaRefresh) elements.providerSlaRefresh.disabled = true;
                const payload = await apiClient.fetchProviderSla({
                    windowValue: elements.providerSlaWindow ? elements.providerSlaWindow.value || 'all' : 'all',
                    limit: 12
                });
                renderProviderSla(payload);
            } catch (err) {
                console.error('Failed to load provider SLA', err);
                elements.providerSlaSummary.textContent = '全系統資料來源狀態讀取失敗';
                elements.providerSlaList.innerHTML = '<span class="provider-sla-chip is-warning">請稍後重試</span>';
            } finally {
                if (elements.providerSlaRefresh) elements.providerSlaRefresh.disabled = false;
            }
        }

        async function loadActiveJobs() {
            if (!elements.activeJobsSummary || !elements.activeJobsList) return;
            try {
                if (elements.activeJobsRefresh) elements.activeJobsRefresh.disabled = true;
                const payload = await apiClient.fetchActiveJobs({ limit: 5, eventLimit: 40 });
                window.StockAgentActiveJobsPanel.render(payload, {
                    summaryEl: elements.activeJobsSummary,
                    listEl: elements.activeJobsList,
                    escapeHtml: ui.escapeHtml
                });
            } catch (err) {
                console.error('Failed to load active jobs', err);
                elements.activeJobsSummary.textContent = '任務狀態讀取失敗';
                elements.activeJobsList.innerHTML = '<span class="provider-sla-chip is-warning">請稍後重試</span>';
            } finally {
                if (elements.activeJobsRefresh) elements.activeJobsRefresh.disabled = false;
            }
        }

        async function loadApiQuotas() {
            if (!elements.apiQuotaSummary || !elements.apiQuotaList) return;
            try {
                if (elements.apiQuotaRefresh) elements.apiQuotaRefresh.disabled = true;
                const payload = await apiClient.fetchApiQuotas();
                window.StockAgentApiQuotaPanel.render(payload, {
                    summaryEl: elements.apiQuotaSummary,
                    listEl: elements.apiQuotaList,
                    escapeHtml: ui.escapeHtml
                });
            } catch (err) {
                console.error('Failed to load API quotas', err);
                elements.apiQuotaSummary.textContent = 'LLM 健康讀取失敗';
                elements.apiQuotaList.innerHTML = '<span class="provider-sla-chip is-warning">請稍後重試</span>';
            } finally {
                if (elements.apiQuotaRefresh) elements.apiQuotaRefresh.disabled = false;
            }
        }

        function bindEvents() {
            watchlistPanel.bindEvents();
            if (elements.providerSlaRefresh) elements.providerSlaRefresh.addEventListener('click', loadProviderSla);
            if (elements.providerSlaWindow) elements.providerSlaWindow.addEventListener('change', loadProviderSla);
            if (elements.activeJobsRefresh) elements.activeJobsRefresh.addEventListener('click', loadActiveJobs);
            if (elements.apiQuotaRefresh) elements.apiQuotaRefresh.addEventListener('click', loadApiQuotas);
        }

        function loadAll() {
            return Promise.allSettled([
                loadProviderSla(),
                loadActiveJobs(),
                loadApiQuotas(),
                watchlistPanel.load()
            ]);
        }

        function loadAllOnce() {
            if (!loaded) {
                loaded = true;
                providerSlaDirty = false;
                return loadAll();
            }
            if (providerSlaDirty) {
                providerSlaDirty = false;
                return loadProviderSla();
            }
            return Promise.resolve();
        }

        function refreshProviderSlaIfLoaded() {
            if (!loaded) {
                providerSlaDirty = true;
                return Promise.resolve();
            }
            providerSlaDirty = false;
            return loadProviderSla();
        }

        return {
            bindEvents,
            loadActiveJobs,
            loadAll,
            loadAllOnce,
            loadApiQuotas,
            loadProviderSla,
            refreshProviderSlaIfLoaded
        };
    }

    window.StockAgentOpsWorkspace = { create };
})();
