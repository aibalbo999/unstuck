(function () {
    function byId(id) { return document.getElementById(id); }
    function fail(summaryEl, listEl, message) {
        if (summaryEl) summaryEl.textContent = message;
        if (listEl) listEl.innerHTML = '<span class="provider-sla-chip is-warning">請稍後重試</span>';
    }
    function create(options) {
        const apiClient = options.apiClient, ui = options.ui;
        const elements = {
            providerSlaSummary: byId('provider-sla-summary'), providerSlaList: byId('provider-sla-list'),
            providerSlaRefresh: byId('provider-sla-refresh'), providerSlaWindow: byId('provider-sla-window'),
            activeJobsSummary: byId('active-jobs-summary'), activeJobsList: byId('active-jobs-list'),
            activeJobsRefresh: byId('active-jobs-refresh'), apiQuotaSummary: byId('api-quota-summary'),
            apiQuotaList: byId('api-quota-list'), apiQuotaRefresh: byId('api-quota-refresh'),
            performanceSummary: byId('performance-summary'), performanceList: byId('performance-list'),
            performanceRefresh: byId('performance-refresh')
        };
        let loaded = false;
        let providerSlaDirty = false;
        let watchlistLoaded = false;
        const watchlistStockSnapshotPanel = window.StockAgentStockSnapshotPanel.create({ apiClient, ui, notify: options.notify || window.StockAgentNotify || { error: () => {} }, onSelectPipeline: options.onSelectPipeline || (() => {}), getSelectedPipeline: options.getSelectedPipeline || (() => 'v1'), elements: { root: byId('watchlist-stock-snapshot-panel') } });
        function onOpenSnapshot(ticker) {
            const root = byId('watchlist-stock-snapshot-panel');
            if (root) root.hidden = false;
            return watchlistStockSnapshotPanel.load(ticker).finally(() => root?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' }));
        }
        const watchlistPanel = window.StockAgentWatchlistPanel.create({
            apiClient, ui, escapeHtml: ui.escapeHtml, onRunQueued: loadActiveJobs, onOpenSnapshot, onOpenReport: options.onOpenReport,
            elements: {
                summaryEl: byId('watchlist-summary'), listEl: byId('watchlist-list'),
                tickerInput: byId('watchlist-ticker-input'), pipelineSelect: byId('watchlist-pipeline-select'),
                suggestionList: byId('watchlist-symbol-suggestions'), importText: byId('watchlist-import-text'),
                preMarketInput: byId('watchlist-pre-market'), postMarketInput: byId('watchlist-post-market'),
                enabledInput: byId('watchlist-enabled'), saveBtn: byId('watchlist-save-btn'), importBtn: byId('watchlist-import-btn'),
                runBtn: byId('watchlist-run-btn'), refreshBtn: byId('watchlist-refresh')
            }
        });
        const portfolioRiskPanel = window.StockAgentPortfolioRiskPanel.create({
            apiClient, ui,
            elements: {
                summaryEl: byId('portfolio-risk-summary'), csvInput: byId('portfolio-risk-csv'),
                runBtn: byId('portfolio-risk-run-btn'), resultEl: byId('portfolio-risk-result')
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
                    limit: 100
                });
                renderProviderSla(payload);
            } catch (err) {
                console.error('Failed to load provider SLA', err);
                fail(elements.providerSlaSummary, elements.providerSlaList, '全系統資料來源狀態讀取失敗');
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
                    escapeHtml: ui.escapeHtml, pipelineModeLabel: ui.pipelineModeLabel
                });
            } catch (err) {
                console.error('Failed to load active jobs', err);
                fail(elements.activeJobsSummary, elements.activeJobsList, '任務狀態讀取失敗');
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
                fail(elements.apiQuotaSummary, elements.apiQuotaList, 'LLM 健康讀取失敗');
            } finally {
                if (elements.apiQuotaRefresh) elements.apiQuotaRefresh.disabled = false;
            }
        }
        async function loadPerformance() {
            if (!elements.performanceSummary || !elements.performanceList) return;
            try {
                if (elements.performanceRefresh) elements.performanceRefresh.disabled = true;
                const payload = await apiClient.fetchPerformanceStats();
                window.StockAgentPerformancePanel.render(payload, {
                    summaryEl: elements.performanceSummary,
                    listEl: elements.performanceList,
                    escapeHtml: ui.escapeHtml
                });
            } catch (err) {
                console.error('Failed to load performance stats', err);
                fail(elements.performanceSummary, elements.performanceList, '決策回測讀取失敗');
            } finally {
                if (elements.performanceRefresh) elements.performanceRefresh.disabled = false;
            }
        }
        function bindEvents() {
            watchlistPanel.bindEvents();
            portfolioRiskPanel.bindEvents();
            if (elements.providerSlaRefresh) elements.providerSlaRefresh.addEventListener('click', loadProviderSla);
            if (elements.providerSlaWindow) elements.providerSlaWindow.addEventListener('change', loadProviderSla);
            if (elements.activeJobsRefresh) elements.activeJobsRefresh.addEventListener('click', loadActiveJobs);
            if (elements.apiQuotaRefresh) elements.apiQuotaRefresh.addEventListener('click', loadApiQuotas);
            if (elements.performanceRefresh) elements.performanceRefresh.addEventListener('click', loadPerformance);
        }
        function loadWatchlist() { return watchlistPanel.load(); }
        function loadWatchlistOnce() {
            if (!watchlistLoaded) { watchlistLoaded = true; return loadWatchlist(); }
            return Promise.resolve();
        }
        function loadAll() { return Promise.allSettled([loadProviderSla(), loadActiveJobs(), loadApiQuotas(), loadPerformance()]); }
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
        return { bindEvents, loadActiveJobs, loadAll, loadAllOnce, loadApiQuotas, loadPerformance, loadProviderSla, loadWatchlist, loadWatchlistOnce, refreshProviderSlaIfLoaded };
    }
    window.StockAgentOpsWorkspace = { create };
})();
