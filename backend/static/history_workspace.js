(function () {
    function create(options) {
        const { apiClient, ui, elements, openReport } = options;
        const notify = options.notify || { success: () => {}, error: () => {}, confirm: async () => false };
        const refreshProviderSlaIfLoaded = options.refreshProviderSlaIfLoaded || (() => Promise.resolve());
        let historyPage = 1;
        const historyLimit = 20;
        let historyReports = new Map();
        let previewReport = null;

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
                workspace: elements.historyWorkspace,
                root: elements.reportPreview,
                mode: elements.previewMode,
                title: elements.previewTitle,
                price: elements.previewPrice,
                recommendation: elements.previewRecommendation,
                confidence: elements.previewConfidence,
                target3m: elements.previewTarget3m,
                target6m: elements.previewTarget6m,
                target12m: elements.previewTarget12m,
                summary: elements.previewSummary,
                staleNotice: elements.previewStaleNotice,
                rerunFinalBtn: elements.previewRerunFinalBtn,
                rerunFullBtn: elements.previewRerunFullBtn,
                rerunModeBBtn: elements.previewRerunModeBBtn
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
            elements: {
                addBtn: elements.previewCompareAddBtn,
                summaryEl: elements.reportCompareSummary,
                resultEl: elements.reportCompareResult,
                clearBtn: elements.reportCompareClearBtn
            }
        });

        async function loadHistory() {
            try {
                const { query, pipelineFilter, recommendationFilter, dataTrustFilter, includeVersions } = historyFilters.values();
                const data = await apiClient.fetchReports({
                    page: historyPage,
                    limit: historyLimit,
                    query,
                    pipeline: pipelineFilter,
                    recommendation: recommendationFilter,
                    dataTrust: dataTrustFilter,
                    includeVersions
                });
                const pagination = data.pagination || { page: 1, total_pages: 1, total: 0, has_prev: false, has_next: false };
                const reports = data.reports || [];
                historyReports = new Map(reports.map(report => [report.filename, report]));
                historyPanel.renderReports(reports, previewReport && previewReport.filename);
                if (!reports.length || (previewReport && !historyReports.has(previewReport.filename))) {
                    hideReportPreview();
                }
                historyPage = historyPanel.renderPagination(pagination);
            } catch (err) {
                console.error('Failed to load history', err);
            }
        }

        function hideReportPreview() {
            previewReport = null;
            reportPreviewPanel.hide();
            historyPanel.clearSelection();
        }

        function showReportPreview(filename) {
            const report = historyReports.get(filename);
            if (!report) return;
            previewReport = report;
            if (reportPreviewPanel.show(report)) {
                historyPanel.select(filename);
            }
        }

        async function refreshPreviewDataSnapshot() {
            const button = elements.previewRefreshDataBtn;
            if (!previewReport || !button) return;
            const filename = previewReport.filename;
            const label = button.querySelector('span');
            const originalText = label ? label.textContent : '刷新資料快照';
            button.disabled = true;
            if (label) label.textContent = '刷新中';
            try {
                const payload = await apiClient.refreshReportDataSnapshot(filename);
                const updated = {
                    ...previewReport,
                    data_trust: payload.data_trust || previewReport.data_trust,
                    data_snapshot_filename: payload.data_filename || previewReport.data_snapshot_filename,
                    analysis_text_stale: payload.analysis_text_stale || previewReport.analysis_text_stale,
                    analysis_text_stale_message: payload.analysis_text_stale_message || previewReport.analysis_text_stale_message,
                    decision_freshness: payload.decision_freshness || previewReport.decision_freshness
                };
                historyReports.set(filename, updated);
                previewReport = updated;
                showReportPreview(filename);
                await loadHistory();
                await refreshProviderSlaIfLoaded();
                const summary = payload.refresh_diff && Array.isArray(payload.refresh_diff.summary)
                    ? payload.refresh_diff.summary.slice(0, 3).join('；')
                    : '資料快照已刷新';
                notify.success(`資料快照已刷新：${summary}`);
            } catch (err) {
                console.error('Failed to refresh data snapshot', err);
                notify.error(`刷新資料快照失敗：${err.message || err}`);
            } finally {
                button.disabled = false;
                if (label) label.textContent = originalText;
            }
        }

        async function rerunPreviewReport(scope) {
            return window.StockAgentReportRerun.rerunPreviewReport({
                apiClient,
                scope,
                previewReport,
                buttons: {
                    final: elements.previewRerunFinalBtn,
                    full: elements.previewRerunFullBtn,
                    modeB: elements.previewRerunModeBBtn,
                    cancel: elements.previewRerunCancelBtn
                },
                statusEl: elements.previewStaleNotice,
                loadHistory,
                notify,
                refreshProviderSlaIfLoaded,
                openReport
            });
        }

        async function deleteReport(filename, event) {
            event.stopPropagation();
            const confirmed = await notify.confirm ('確定要刪除這份報告嗎？', {
                title: '刪除報告',
                confirmLabel: '刪除'
            });
            if (!confirmed) return;
            try {
                const result = await apiClient.deleteReport(filename);
                if (result.success) {
                    if (previewReport && previewReport.filename === filename) hideReportPreview();
                    loadHistory();
                } else {
                    notify.error('刪除失敗：' + result.error);
                }
            } catch (err) {
                console.error(err);
                notify.error('刪除失敗');
            }
        }

        function bindEvents() {
            historyPanel.bindEvents({ onDelete: deleteReport, onSelect: showReportPreview });
            if (elements.previewOpenReportBtn) {
                elements.previewOpenReportBtn.addEventListener('click', () => {
                    if (!previewReport) return;
                    openReport(previewReport.filename, previewReport.ticker, previewReport.pipeline_id || 'v1');
                });
            }

            [
                [elements.previewRefreshDataBtn, refreshPreviewDataSnapshot],
                [elements.previewRerunFinalBtn, () => rerunPreviewReport('final_recommendation')],
                [elements.previewRerunFullBtn, () => rerunPreviewReport('full_report')],
                [elements.previewRerunModeBBtn, () => rerunPreviewReport('mode_b')],
                [elements.previewCloseBtn, hideReportPreview]
            ].forEach(([button, handler]) => {
                if (button) button.addEventListener('click', handler);
            });
            reportComparePanel.bindEvents(() => previewReport);

            historyFilters.bind({
                onSearch: () => {
                    historyPage = 1;
                    loadHistory();
                },
                onFilter: () => {
                    historyPage = 1;
                    hideReportPreview();
                    loadHistory();
                }
            });

            if (elements.historyPrev) {
                elements.historyPrev.addEventListener('click', () => {
                    if (historyPage > 1) {
                        historyPage -= 1;
                        loadHistory();
                    }
                });
            }
            if (elements.historyNext) {
                elements.historyNext.addEventListener('click', () => {
                    historyPage += 1;
                    loadHistory();
                });
            }
            window.deleteReport = deleteReport;
        }

        return {
            bindEvents,
            hideReportPreview,
            loadHistory,
            getPreviewReport: () => previewReport
        };
    }

    window.StockAgentHistoryWorkspace = { create };
})();
