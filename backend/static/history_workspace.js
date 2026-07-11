(function () {
    function create(options) {
        const { apiClient, ui, elements, openReport } = options;
        const notify = options.notify || { success: () => {}, error: () => {}, confirm: async () => false };
        const refreshProviderSlaIfLoaded = options.refreshProviderSlaIfLoaded || (() => Promise.resolve());
        let historyPage = 1;
        const historyLimit = 20;
        let historyReports = new Map(), previewReport = null, trackedTickers = new Set();
        let trackingCompact = false, previewCompactMode = false;

        const {
            historyFilters,
            historyPanel,
            reportPreviewPanel,
            reportComparePanel,
            trackingSnapshotPanel,
            decisionTrackingPanel
        } = window.StockAgentHistoryWorkspacePanels.create({
            apiClient,
            ui,
            elements,
            notify,
            onTrackedTickersChange: tickers => { trackedTickers = tickers; }
        });
        function setTrackingCompact(value, fromPreview = false) {
            trackingCompact = Boolean(value);
            previewCompactMode = Boolean(fromPreview && trackingCompact);
            historyPanel.setTrackingCompact(trackingCompact);
            const density = elements.decisionTrackingDensity, label = density?.querySelector('span');
            if (label) label.textContent = trackingCompact ? '展開追蹤表' : '精簡追蹤表';
            if (density) density.setAttribute('aria-pressed', String(trackingCompact));
        }
        function mergeTrackingReports(trackingPayload) {
            (trackingPayload?.items || []).flatMap(item => [item.latest_report, ...(item.latest_reports || [])])
                .forEach(report => { if (report?.filename) historyReports.set(report.filename, report); });
        }
        async function loadHistory() {
            try {
                const trackingPayload = await decisionTrackingPanel.load();
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
                mergeTrackingReports(trackingPayload);
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
            if (previewCompactMode) setTrackingCompact(false);
        }
        async function openTrackingSnapshot(ticker) { if (!ticker) return; hideReportPreview(); elements.historyWorkspace?.classList.add('has-preview'); await trackingSnapshotPanel.load(ticker); elements.decisionTrackingStockSnapshotPanel?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
        function showReportPreview(filename) {
            const report = historyReports.get(filename);
            if (!report) return;
            if (elements.decisionTrackingStockSnapshotPanel) elements.decisionTrackingStockSnapshotPanel.hidden = true;
            previewReport = report;
            setTrackingCompact(true, true);
            if (reportPreviewPanel.show(report)) historyPanel.select(filename);
        }
        const actions = window.StockAgentHistoryWorkspaceActions.create({
            apiClient,
            notify,
            elements,
            decisionTrackingPanel,
            getPreviewReport: () => previewReport,
            setPreviewReport: report => { previewReport = report; },
            getReport: filename => historyReports.get(filename),
            setReport: (filename, report) => { historyReports.set(filename, report); },
            showReportPreview,
            hideReportPreview,
            loadHistory,
            refreshProviderSlaIfLoaded,
            openReport
        });
        function bindEvents() {
            historyPanel.bindEvents({ onDelete: actions.deleteReport, onSelect: showReportPreview, onToggleTracking: actions.toggleDecisionTracking, onOpenSnapshot: openTrackingSnapshot });
            trackingSnapshotPanel.bindEvents();
            if (elements.previewOpenReportBtn) {
                elements.previewOpenReportBtn.addEventListener('click', () => {
                    if (!previewReport) return;
                    openReport(previewReport.filename, previewReport.ticker, previewReport.pipeline_id || 'v1');
                });
            }

            [
                [elements.previewRefreshDataBtn, actions.refreshPreviewDataSnapshot],
                [elements.previewRerunFinalBtn, () => actions.rerunPreviewReport('final_recommendation')],
                [elements.previewRerunFullBtn, () => actions.rerunPreviewReport('full_report')],
                [elements.previewRerunModeBBtn, () => actions.rerunPreviewReport('mode_b')],
                [elements.previewCloseBtn, hideReportPreview]
            ].forEach(([button, handler]) => {
                if (button) button.addEventListener('click', handler);
            });
            if (elements.decisionTrackingDensity) elements.decisionTrackingDensity.addEventListener('click', () => setTrackingCompact(!trackingCompact));
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
            window.deleteReport = actions.deleteReport;
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
