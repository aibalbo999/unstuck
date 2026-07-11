(function () {
    function byId(doc, id) {
        return doc.getElementById(id);
    }

    function collect(doc = document) {
        const watchlistStockSnapshotRoot = byId(doc, 'watchlist-stock-snapshot-panel');
        const watchlistElements = {
            summaryEl: byId(doc, 'watchlist-summary'),
            listEl: byId(doc, 'watchlist-list'),
            tickerInput: byId(doc, 'watchlist-ticker-input'),
            pipelineSelect: byId(doc, 'watchlist-pipeline-select'),
            suggestionList: byId(doc, 'watchlist-symbol-suggestions'),
            importText: byId(doc, 'watchlist-import-text'),
            preMarketInput: byId(doc, 'watchlist-pre-market'),
            postMarketInput: byId(doc, 'watchlist-post-market'),
            enabledInput: byId(doc, 'watchlist-enabled'),
            saveBtn: byId(doc, 'watchlist-save-btn'),
            importBtn: byId(doc, 'watchlist-import-btn'),
            runBtn: byId(doc, 'watchlist-run-btn'),
            refreshBtn: byId(doc, 'watchlist-refresh')
        };
        const portfolioRiskElements = {
            summaryEl: byId(doc, 'portfolio-risk-summary'),
            csvInput: byId(doc, 'portfolio-risk-csv'),
            runBtn: byId(doc, 'portfolio-risk-run-btn'),
            resultEl: byId(doc, 'portfolio-risk-result')
        };
        return {
            providerSlaSummary: byId(doc, 'provider-sla-summary'),
            providerSlaList: byId(doc, 'provider-sla-list'),
            providerSlaRefresh: byId(doc, 'provider-sla-refresh'),
            providerSlaWindow: byId(doc, 'provider-sla-window'),
            activeJobsSummary: byId(doc, 'active-jobs-summary'),
            activeJobsList: byId(doc, 'active-jobs-list'),
            activeJobsRefresh: byId(doc, 'active-jobs-refresh'),
            apiQuotaSummary: byId(doc, 'api-quota-summary'),
            apiQuotaList: byId(doc, 'api-quota-list'),
            apiQuotaRefresh: byId(doc, 'api-quota-refresh'),
            performanceSummary: byId(doc, 'performance-summary'),
            performanceList: byId(doc, 'performance-list'),
            performanceRefresh: byId(doc, 'performance-refresh'),
            watchlistStockSnapshotRoot,
            watchlistElements,
            portfolioRiskElements
        };
    }

    window.StockAgentOpsWorkspaceElements = { collect };
})();
