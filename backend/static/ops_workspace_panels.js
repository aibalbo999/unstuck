(function () {
    function createPanels(options) {
        const apiClient = options.apiClient, ui = options.ui, elements = options.elements;
        const notify = options.notify || window.StockAgentNotify || { error: () => {} };
        const loadActiveJobs = options.loadActiveJobs || (() => Promise.resolve());
        const watchlistStockSnapshotPanel = window.StockAgentStockSnapshotPanel.create({
            apiClient,
            ui,
            notify,
            onSelectPipeline: options.onSelectPipeline || (() => {}),
            getSelectedPipeline: options.getSelectedPipeline || (() => 'v1'),
            elements: { root: elements.watchlistStockSnapshotRoot }
        });

        function onOpenSnapshot(ticker) {
            const root = elements.watchlistStockSnapshotRoot;
            if (root) root.hidden = false;
            return Promise.resolve(watchlistStockSnapshotPanel.load(ticker))
                .finally(() => root?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' }));
        }

        const watchlistPanel = window.StockAgentWatchlistPanel.create({
            apiClient,
            ui,
            escapeHtml: ui.escapeHtml,
            onRunQueued: loadActiveJobs,
            onOpenSnapshot,
            onOpenReport: options.onOpenReport,
            elements: elements.watchlistElements
        });
        const portfolioRiskPanel = window.StockAgentPortfolioRiskPanel.create({
            apiClient,
            ui,
            elements: elements.portfolioRiskElements
        });
        return { onOpenSnapshot, portfolioRiskPanel, watchlistPanel, watchlistStockSnapshotPanel };
    }

    function createLoaders(options) {
        const apiClient = options.apiClient, ui = options.ui, elements = options.elements, loadPanel = options.loadPanel;

        function loadProviderSla() {
            return loadPanel({
                summaryEl: elements.providerSlaSummary,
                listEl: elements.providerSlaList,
                refreshEl: elements.providerSlaRefresh,
                fetchPayload: () => apiClient.fetchProviderSla({
                    windowValue: elements.providerSlaWindow ? elements.providerSlaWindow.value || 'all' : 'all',
                    limit: 100
                }),
                renderPayload: payload => window.StockAgentProviderSlaPanel.render(payload, {
                    summaryEl: elements.providerSlaSummary,
                    listEl: elements.providerSlaList,
                    windowEl: elements.providerSlaWindow,
                    escapeHtml: ui.escapeHtml
                }),
                failureMessage: '全系統資料來源狀態讀取失敗',
                errorLabel: 'provider SLA'
            });
        }

        function loadActiveJobs() {
            return loadPanel({
                summaryEl: elements.activeJobsSummary,
                listEl: elements.activeJobsList,
                refreshEl: elements.activeJobsRefresh,
                fetchPayload: () => apiClient.fetchActiveJobs({ limit: 5, eventLimit: 40 }),
                renderPayload: payload => window.StockAgentActiveJobsPanel.render(payload, {
                    summaryEl: elements.activeJobsSummary,
                    listEl: elements.activeJobsList,
                    escapeHtml: ui.escapeHtml,
                    pipelineModeLabel: ui.pipelineModeLabel
                }),
                failureMessage: '任務狀態讀取失敗',
                errorLabel: 'active jobs'
            });
        }

        function loadApiQuotas() {
            return loadPanel({
                summaryEl: elements.apiQuotaSummary,
                listEl: elements.apiQuotaList,
                refreshEl: elements.apiQuotaRefresh,
                fetchPayload: () => apiClient.fetchApiQuotas(),
                renderPayload: payload => window.StockAgentApiQuotaPanel.render(payload, {
                    summaryEl: elements.apiQuotaSummary,
                    listEl: elements.apiQuotaList,
                    escapeHtml: ui.escapeHtml
                }),
                failureMessage: 'LLM 健康讀取失敗',
                errorLabel: 'API quotas'
            });
        }

        function loadPerformance() {
            return loadPanel({
                summaryEl: elements.performanceSummary,
                listEl: elements.performanceList,
                refreshEl: elements.performanceRefresh,
                fetchPayload: () => apiClient.fetchPerformanceStats(),
                renderPayload: payload => window.StockAgentPerformancePanel.render(payload, {
                    summaryEl: elements.performanceSummary,
                    listEl: elements.performanceList,
                    escapeHtml: ui.escapeHtml
                }),
                failureMessage: '決策回測讀取失敗',
                errorLabel: 'performance stats'
            });
        }

        return { loadActiveJobs, loadApiQuotas, loadPerformance, loadProviderSla };
    }

    window.StockAgentOpsWorkspacePanels = { createLoaders, createPanels };
})();
