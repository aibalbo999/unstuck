(function () {
    function create(options) {
        const apiClient = options.apiClient, ui = options.ui;
        const elements = window.StockAgentOpsWorkspaceElements.collect(document);
        const { loadPanel } = window.StockAgentOpsWorkspaceLoaders;
        let loaded = false, providerSlaDirty = false, watchlistLoaded = false;
        const loaders = window.StockAgentOpsWorkspacePanels.createLoaders({
            apiClient, ui, elements, loadPanel
        });
        const panels = window.StockAgentOpsWorkspacePanels.createPanels({
            apiClient,
            ui,
            elements,
            notify: options.notify,
            loadActiveJobs: loaders.loadActiveJobs,
            onSelectPipeline: options.onSelectPipeline,
            getSelectedPipeline: options.getSelectedPipeline,
            onOpenReport: options.onOpenReport
        });
        const { loadActiveJobs, loadApiQuotas, loadPerformance, loadProviderSla } = loaders;
        const { portfolioRiskPanel, watchlistPanel } = panels;

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
        function loadWatchlistOnce() { if (!watchlistLoaded) { watchlistLoaded = true; return loadWatchlist(); } return Promise.resolve(); }
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
