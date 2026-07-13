(function () {
    function byId(doc, id) {
        return doc.getElementById(id);
    }

    function create(options) {
        const apiClient = options.apiClient, ui = options.ui, notify = options.notify, elements = options.elements || {};
        const doc = options.doc || document;
        const openReport = options.openReport || (() => {});
        const switchView = options.switchView || (() => {});
        const selectPipelineMode = options.selectPipelineMode || (() => {});
        const getSelectedPipeline = options.getSelectedPipeline || (() => 'v1'), tickerInput = elements.tickerInput || byId(doc, 'ticker-input');

        const opsWorkspace = window.StockAgentOpsWorkspace.create({ apiClient, ui, notify, onOpenReport: openReport, onSelectPipeline: selectPipelineMode, getSelectedPipeline });
        const marketScreenerPanel = window.StockAgentMarketScreenerPanel.create({
            apiClient,
            ui,
            elements: {
                summaryEl: byId(doc, 'market-screener-summary'),
                boardEl: byId(doc, 'market-screener-board'),
                listEl: byId(doc, 'market-screener-list'),
                runBtn: byId(doc, 'market-screener-run-btn'),
                refreshBtn: byId(doc, 'market-screener-refresh')
            }
        });
        const stockSnapshotPanel = window.StockAgentStockSnapshotPanel.create({
            apiClient,
            ui,
            notify,
            onSelectPipeline: selectPipelineMode,
            onWatchlistUpdated: opsWorkspace.loadWatchlistOnce,
            getSelectedPipeline,
            elements: {
                root: elements.stockSnapshotPanelEl,
                loadButton: elements.stockSnapshotLoadBtn,
                shortcutsRoot: elements.stockSnapshotShortcutsEl,
                tickerInput: elements.tickerInput
            }
        });
        function activateAnalysis(ticker) {
            const normalized = String(ticker || '').trim().toUpperCase();
            if (!normalized) { notify?.error?.('候選股票缺少代號。'); return ''; }
            switchView('home-view'); byId(doc, 'home-tab-analysis')?.click?.();
            if (tickerInput) tickerInput.value = normalized;
            return normalized;
        }
        const operatorSummary = window.StockAgentOperatorSummaryPanel.create({
            apiClient,
            ui,
            notify,
            onCandidateSnapshot: async ticker => {
                const normalized = activateAnalysis(ticker);
                if (!normalized) return;
                await stockSnapshotPanel.load(normalized);
                elements.stockSnapshotPanelEl?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
            },
            onCandidateWatchlist: ticker => stockSnapshotPanel.addToWatchlist(String(ticker || '').trim().toUpperCase()),
            onCandidatePrepareAnalysis: ticker => {
                const normalized = activateAnalysis(ticker);
                if (!normalized) return;
                const selector = doc.querySelector('.pipeline-selector');
                selector?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
                selector?.querySelector?.('input:checked')?.focus?.();
            }
        });
        const historyWorkspace = window.StockAgentHistoryWorkspace.create({
            apiClient,
            ui,
            notify,
            refreshProviderSlaIfLoaded: opsWorkspace.refreshProviderSlaIfLoaded,
            openReport,
            elements: {
                historyWorkspace: elements.historyWorkspaceEl,
                historyList: elements.historyList,
                historySearch: elements.historySearch,
                historyPipelineFilter: elements.historyPipelineFilter,
                historyRecommendationFilter: elements.historyRecommendationFilter,
                historyDataTrustFilter: elements.historyDataTrustFilter,
                historyIncludeVersions: elements.historyIncludeVersions,
                historyPagination: elements.historyPagination,
                historyPrev: elements.historyPrev,
                historyNext: elements.historyNext,
                historyPageInfo: elements.historyPageInfo,
                historyTrackingTable: elements.historyTrackingTable,
                decisionTrackingStockSnapshotPanel: elements.decisionTrackingStockSnapshotPanel,
                decisionTrackingSummary: elements.decisionTrackingSummary,
                decisionTrackingRefresh: elements.decisionTrackingRefresh,
                decisionTrackingDensity: elements.decisionTrackingDensity,
                decisionTrackingRunActions: elements.decisionTrackingRunActions,
                reportPreview: elements.reportPreview,
                previewMode: elements.previewMode,
                previewTitle: elements.previewTitle,
                previewPrice: elements.previewPrice,
                previewRecommendation: elements.previewRecommendation,
                previewConfidence: elements.previewConfidence,
                previewTarget3m: elements.previewTarget3m,
                previewTarget6m: elements.previewTarget6m,
                previewTarget12m: elements.previewTarget12m,
                previewSummary: elements.previewSummary,
                previewStaleNotice: elements.previewStaleNotice,
                previewOpenReportBtn: elements.previewOpenReportBtn,
                previewRefreshDataBtn: elements.previewRefreshDataBtn,
                previewCompareAddBtn: elements.previewCompareAddBtn,
                previewRerunFinalBtn: elements.previewRerunFinalBtn,
                previewRerunFullBtn: elements.previewRerunFullBtn,
                previewRerunModeBBtn: elements.previewRerunModeBBtn,
                previewRerunCancelBtn: elements.previewRerunCancelBtn,
                previewCloseBtn: elements.previewCloseBtn,
                reportCompareSummary: elements.reportCompareSummary,
                reportCompareResult: elements.reportCompareResult,
                reportCompareClearBtn: elements.reportCompareClearBtn
            }
        });
        function bindPanelEvents() {
            historyWorkspace.bindEvents();
            opsWorkspace.bindEvents();
            marketScreenerPanel.bindEvents();
            stockSnapshotPanel.bindEvents();
        }
        function loadInitialPanels() {
            historyWorkspace.loadHistory();
            operatorSummary.load();
        }

        return { bindPanelEvents, historyWorkspace, loadHistory: historyWorkspace.loadHistory, loadInitialPanels, marketScreenerPanel, operatorSummary, opsWorkspace, stockSnapshotPanel };
    }
    window.StockAgentAppPanels = { create };
})();
