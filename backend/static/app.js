document.addEventListener('DOMContentLoaded', () => {
    const ui = window.StockAgentUi;
    const apiClient = window.StockAgentApiClient;
    const homeView = document.getElementById('home-view');
    const loadingView = document.getElementById('loading-view');
    const reportView = document.getElementById('report-view');
    const tickerInput = document.getElementById('ticker-input');
    const analyzeBtn = document.getElementById('analyze-btn');
    const analyzeBtnText = analyzeBtn ? analyzeBtn.querySelector('span') : null;
    const stockSnapshotPanelEl = document.getElementById('stock-snapshot-panel');
    const stockSnapshotLoadBtn = document.getElementById('stock-snapshot-load-btn');
    const stockSnapshotShortcutsEl = document.getElementById('stock-snapshot-shortcuts');
    const pipelineModeHint = document.getElementById('pipeline-mode-hint');
    const backBtn = document.getElementById('back-btn');
    const loadingStatus = document.getElementById('loading-status');
    const loadingMsg = document.getElementById('loading-msg');
    const loadingHint = document.getElementById('loading-hint');
    const progressBar = document.getElementById('progress-bar');
    const pipelineInputs = Array.from(document.querySelectorAll('input[name="pipeline-mode"]'));
    const reportIframe = document.getElementById('report-iframe');
    const reportTickerTitle = document.getElementById('report-ticker-title');
    const reportAuditNotice = document.getElementById('report-audit-notice');
    const historyList = document.getElementById('history-list');
    const historySearch = document.getElementById('history-search');
    const historyPipelineFilter = document.getElementById('history-pipeline-filter');
    const historyRecommendationFilter = document.getElementById('history-recommendation-filter');
    const historyDataTrustFilter = document.getElementById('history-data-trust-filter');
    const historyIncludeVersions = document.getElementById('history-include-versions');
    const historyPagination = document.getElementById('history-pagination');
    const historyPrev = document.getElementById('history-prev');
    const historyNext = document.getElementById('history-next');
    const historyPageInfo = document.getElementById('history-page-info');
    const historyTrackingTable = document.getElementById('history-tracking-table');
    const decisionTrackingSummary = document.getElementById('decision-tracking-summary');
    const decisionTrackingRefresh = document.getElementById('decision-tracking-refresh');
    const decisionTrackingDensity = document.getElementById('decision-tracking-density');
    const decisionTrackingRunActions = document.getElementById('decision-tracking-run-actions');
    const historyWorkspaceEl = document.querySelector('.history-workspace');
    const reportPreview = document.getElementById('report-preview');
    const previewMode = document.getElementById('preview-mode');
    const previewTitle = document.getElementById('preview-title');
    const previewPrice = document.getElementById('preview-price');
    const previewRecommendation = document.getElementById('preview-recommendation');
    const previewConfidence = document.getElementById('preview-confidence');
    const previewTarget3m = document.getElementById('preview-target-3m');
    const previewTarget6m = document.getElementById('preview-target-6m');
    const previewTarget12m = document.getElementById('preview-target-12m');
    const previewSummary = document.getElementById('preview-summary');
    const previewStaleNotice = document.getElementById('preview-stale-notice');
    const previewOpenReportBtn = document.getElementById('preview-open-report-btn');
    const previewRefreshDataBtn = document.getElementById('preview-refresh-data-btn');
    const previewCompareAddBtn = document.getElementById('preview-compare-add-btn');
    const previewRerunFinalBtn = document.getElementById('preview-rerun-final-btn');
    const previewRerunFullBtn = document.getElementById('preview-rerun-full-btn');
    const previewRerunModeBBtn = document.getElementById('preview-rerun-modeb-btn');
    const previewRerunCancelBtn = document.getElementById('preview-rerun-cancel-btn');
    const previewCloseBtn = document.getElementById('preview-close-btn');
    const reportCompareSummary = document.getElementById('report-compare-summary');
    const reportCompareResult = document.getElementById('report-compare-result');
    const reportCompareClearBtn = document.getElementById('report-compare-clear-btn');
    const downloadHtmlBtn = document.getElementById('download-html-btn');
    const downloadMdBtn = document.getElementById('download-md-btn');
    const downloadDataBtn = document.getElementById('download-data-btn');
    let currentReportFilename = null, pendingAuditNotice = null;
    let currentPipeline = 'v1';
    const notify = window.StockAgentNotificationCenter.create();
    window.StockAgentNotify = notify;
    const viewController = window.StockAgentViewController.create({
        views: {
            'home-view': homeView,
            'loading-view': loadingView,
            'report-view': reportView
        }
    });
    const switchView = viewController.switchView;
    function getSelectedPipeline() {
        const selected = document.querySelector('input[name="pipeline-mode"]:checked') || pipelineInputs.find(input => input.checked);
        return selected ? selected.value : 'v1';
    }
    function syncPipelineOptionLabels() {
        const choices = typeof ui.pipelineChoices === 'function' ? ui.pipelineChoices({ includeBoth: true }) : [];
        choices.forEach(choice => {
            const selector = `input[name="pipeline-mode"][value="${choice.value}"]`;
            const input = document.querySelector(selector);
            const label = input ? input.closest('.pipeline-option') : null;
            if (label) {
                const title = label.querySelector('strong');
                const subtitle = label.querySelector('small');
                if (title) title.textContent = choice.codeLabel || choice.label || choice.value;
                if (subtitle) subtitle.textContent = choice.optionLabel || choice.shortLabel || choice.intent || '';
            }
            const historyOption = historyPipelineFilter?.querySelector(`option[value="${choice.value}"]`);
            if (historyOption) historyOption.textContent = ui.pipelineModeLabel(choice.value);
            const watchlistOption = document.querySelector(`#watchlist-pipeline-select option[value="${choice.value}"]`);
            if (watchlistOption) watchlistOption.textContent = ui.pipelineModeLabel(choice.value);
        });
    }
    function updateAnalyzeButtonCopy() {
        if (!analyzeBtnText) return;
        analyzeBtnText.textContent = ui.pipelineCtaLabel(getSelectedPipeline());
    }
    function updatePipelineModeHint() {
        if (!pipelineModeHint) return;
        pipelineModeHint.textContent = ui.pipelineMeta(getSelectedPipeline()).intent || '';
    }
    function selectPipelineMode(pipelineId) {
        const input = pipelineInputs.find(item => item.value === pipelineId);
        if (!input) return;
        input.checked = true;
        updateAnalyzeButtonCopy();
        updatePipelineModeHint();
    }
    function setAuditNotice(audit) {
        if (!reportAuditNotice) return;
        if (!audit || audit.status === 'passed') {
            reportAuditNotice.hidden = true;
            reportAuditNotice.textContent = '';
            reportAuditNotice.className = 'report-audit-notice';
            return;
        }
        const label = audit.status === 'needs_attention' ? '稽核提醒' : '稽核註記';
        const detail = audit.status !== 'needs_attention' && Array.isArray(audit.issues) && audit.issues.length > 0
            ? ` ${audit.issues.slice(0, 2).join('；')}`
            : '';
        reportAuditNotice.textContent = `${label}：${audit.message || '請查看報告內的系統稽核區塊。'}${detail}`;
        reportAuditNotice.className = `report-audit-notice ${audit.status === 'needs_attention' ? 'is-warning' : 'is-note'}`;
        reportAuditNotice.hidden = false;
    }
    // 開啟報告
    function openReport(filename, ticker, pipelineId = 'v1') {
        currentReportFilename = filename;
        currentPipeline = pipelineId;
        window.StockAgentReportActions.setReportTitle({
            titleEl: reportTickerTitle,
            ticker,
            pipelineId,
            pipelineMeta: ui.pipelineMeta
        });
        setAuditNotice(null);
        reportIframe.src = `/api/report/${encodeURIComponent(filename)}`;
        switchView('report-view');
    }
    window.openReport = openReport;
    const opsWorkspace = window.StockAgentOpsWorkspace.create({ apiClient, ui, notify, onOpenReport: openReport, onSelectPipeline: selectPipelineMode, getSelectedPipeline });
    const operatorSummary = window.StockAgentOperatorSummaryPanel.create({ apiClient, ui });
    const marketScreenerPanel = window.StockAgentMarketScreenerPanel.create({
        apiClient,
        ui,
        elements: {
            summaryEl: document.getElementById('market-screener-summary'),
            boardEl: document.getElementById('market-screener-board'),
            listEl: document.getElementById('market-screener-list'),
            runBtn: document.getElementById('market-screener-run-btn'),
            refreshBtn: document.getElementById('market-screener-refresh')
        }
    });
    const stockSnapshotPanel = window.StockAgentStockSnapshotPanel.create({
        apiClient, ui, notify,
        onSelectPipeline: selectPipelineMode,
        onWatchlistUpdated: opsWorkspace.loadWatchlistOnce,
        getSelectedPipeline,
        elements: {
            root: stockSnapshotPanelEl,
            loadButton: stockSnapshotLoadBtn,
            shortcutsRoot: stockSnapshotShortcutsEl,
            tickerInput
        }
    });
    const historyWorkspace = window.StockAgentHistoryWorkspace.create({
        apiClient,
        ui,
        notify,
        refreshProviderSlaIfLoaded: opsWorkspace.refreshProviderSlaIfLoaded,
        openReport,
        elements: {
            historyWorkspace: historyWorkspaceEl,
            historyList,
            historySearch,
            historyPipelineFilter,
            historyRecommendationFilter,
            historyDataTrustFilter,
            historyIncludeVersions,
            historyPagination,
            historyPrev,
            historyNext,
            historyPageInfo,
            historyTrackingTable,
            decisionTrackingStockSnapshotPanel: document.getElementById('decision-tracking-stock-snapshot-panel'),
            decisionTrackingSummary,
            decisionTrackingRefresh,
            decisionTrackingDensity,
            decisionTrackingRunActions,
            reportPreview,
            previewMode,
            previewTitle,
            previewPrice,
            previewRecommendation,
            previewConfidence,
            previewTarget3m,
            previewTarget6m,
            previewTarget12m,
            previewSummary,
            previewStaleNotice,
            previewOpenReportBtn,
            previewRefreshDataBtn,
            previewCompareAddBtn,
            previewRerunFinalBtn,
            previewRerunFullBtn,
            previewRerunModeBBtn,
            previewRerunCancelBtn,
            previewCloseBtn,
            reportCompareSummary,
            reportCompareResult,
            reportCompareClearBtn
        }
    });
    historyWorkspace.bindEvents();
    const loadHistory = historyWorkspace.loadHistory;
    window.StockAgentReportActions.bindDownloads({
        htmlBtn: downloadHtmlBtn,
        mdBtn: downloadMdBtn,
        dataBtn: downloadDataBtn,
        getFilename: () => currentReportFilename
    });
    window.StockAgentReportNavigation.bind(reportIframe);
    loadHistory();
    operatorSummary.load();
    opsWorkspace.bindEvents();
    marketScreenerPanel.bindEvents();
    stockSnapshotPanel.bindEvents();
    window.StockAgentHomeTabs.bind({
        onActivate: tabName => {
            if (tabName === 'screener') marketScreenerPanel.loadOnce();
            if (tabName === 'tracking') opsWorkspace.loadWatchlistOnce();
            if (tabName === 'ops') opsWorkspace.loadAllOnce();
        }
    });
    pipelineInputs.forEach(input => {
        input.addEventListener('change', () => {
            updateAnalyzeButtonCopy();
            updatePipelineModeHint();
        });
    });
    syncPipelineOptionLabels();
    updateAnalyzeButtonCopy();
    updatePipelineModeHint();
    const analysisStream = window.StockAgentAnalysisStream.create({
        loadingStatus,
        loadingMsg,
        loadingHint,
        progressBar,
        reportTickerTitle,
        reportIframe,
        pipelineMeta: ui.pipelineMeta,
        pipelineModeLabel: ui.pipelineModeLabel,
        setAuditNotice,
        switchView,
        loadHistory,
        getState: () => ({ currentPipeline, pendingAuditNotice }),
        setState: (patch) => {
            if (Object.prototype.hasOwnProperty.call(patch, 'currentReportFilename')) {
                currentReportFilename = patch.currentReportFilename;
            }
            if (Object.prototype.hasOwnProperty.call(patch, 'currentPipeline')) {
                currentPipeline = patch.currentPipeline;
            }
            if (Object.prototype.hasOwnProperty.call(patch, 'pendingAuditNotice')) {
                pendingAuditNotice = patch.pendingAuditNotice;
            }
        }
    });
    analyzeBtn.addEventListener('click', () => {
        const ticker = tickerInput.value.trim().toUpperCase();
        if (!ticker) {
            notify.error('請輸入股票代號。');
            return;
        }
        currentPipeline = getSelectedPipeline();
        loadingStatus.textContent = '連接 Wall Street 系統...';
        loadingMsg.textContent = '';
        if (loadingHint) loadingHint.textContent = ui.pipelineMeta(currentPipeline).hint;
        progressBar.style.width = '0%';
        pendingAuditNotice = null;
        setAuditNotice(null);
        analysisStream.close();
        switchView('loading-view');
        analysisStream.resetAndConnect(ticker, currentPipeline);
    });
    backBtn.addEventListener('click', () => {
        analysisStream.close();
        reportIframe.src = 'about:blank'; // 清除記憶體
        tickerInput.value = ''; // 清空輸入框
        switchView('home-view');
    });
    tickerInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); analyzeBtn.click(); }
    });
});
