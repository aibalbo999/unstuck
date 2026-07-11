(function () {
    function create(options) {
        const { apiClient, ui, elements, notify, onTrackedTickersChange } = options;
        const historyFilters = window.StockAgentHistoryFilters.create({
            searchEl: elements.historySearch,
            pipelineEl: elements.historyPipelineFilter,
            recommendationEl: elements.historyRecommendationFilter,
            dataTrustEl: elements.historyDataTrustFilter,
            includeVersionsEl: elements.historyIncludeVersions
        });
        const historyPanel = window.StockAgentHistoryPanel.create({
            listEl: elements.historyList,
            trackingTableEl: elements.historyTrackingTable,
            paginationEl: elements.historyPagination,
            prevBtn: elements.historyPrev,
            nextBtn: elements.historyNext,
            pageInfoEl: elements.historyPageInfo,
            escapeHtml: ui.escapeHtml,
            renderPipelineModeBadge: ui.renderPipelineModeBadge,
            renderDataTrustBadge: ui.renderDataTrustBadge,
            renderDataTrustReason: ui.renderDataTrustReason,
            recommendationTone: ui.recommendationTone,
            normalizeRecommendation: ui.normalizeRecommendation
        });
        const reportPreviewPanel = window.StockAgentReportPreviewPanel.create({
            elements: {
                workspace: elements.historyWorkspace, root: elements.reportPreview,
                mode: elements.previewMode, title: elements.previewTitle, price: elements.previewPrice,
                recommendation: elements.previewRecommendation, confidence: elements.previewConfidence,
                target3m: elements.previewTarget3m, target6m: elements.previewTarget6m,
                target12m: elements.previewTarget12m, summary: elements.previewSummary,
                readingNotice: elements.previewReadingNotice,
                staleNotice: elements.previewStaleNotice, rerunFinalBtn: elements.previewRerunFinalBtn,
                rerunFullBtn: elements.previewRerunFullBtn, rerunModeBBtn: elements.previewRerunModeBBtn
            },
            escapeHtml: ui.escapeHtml,
            renderPipelineModeBadge: ui.renderPipelineModeBadge,
            renderDataTrustBadge: ui.renderDataTrustBadge,
            recommendationTone: ui.recommendationTone,
            normalizeRecommendation: ui.normalizeRecommendation
        });
        const reportComparePanel = window.StockAgentReportComparePanel.create({
            apiClient,
            escapeHtml: ui.escapeHtml,
            pipelineModeLabel: ui.pipelineModeLabel,
            elements: {
                addBtn: elements.previewCompareAddBtn,
                summaryEl: elements.reportCompareSummary,
                resultEl: elements.reportCompareResult,
                clearBtn: elements.reportCompareClearBtn
            }
        });
        const trackingSnapshotPanel = window.StockAgentStockSnapshotPanel.create({
            apiClient, ui, notify,
            elements: { root: elements.decisionTrackingStockSnapshotPanel }
        });
        const decisionTrackingPanel = window.StockAgentDecisionTrackingPanel.create({
            apiClient, historyPanel, notify,
            elements: {
                summaryEl: elements.decisionTrackingSummary,
                refreshBtn: elements.decisionTrackingRefresh,
                runActionsBtn: elements.decisionTrackingRunActions
            },
            onChange: tickers => {
                historyPanel.setTrackedTickers(tickers);
                if (typeof onTrackedTickersChange === 'function') onTrackedTickersChange(tickers);
            }
        });
        return { historyFilters, historyPanel, reportPreviewPanel, reportComparePanel, trackingSnapshotPanel, decisionTrackingPanel };
    }

    window.StockAgentHistoryWorkspacePanels = { create };
})();
