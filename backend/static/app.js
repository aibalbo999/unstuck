document.addEventListener('DOMContentLoaded', () => {
    const ui = window.StockAgentUi;
    const apiClient = window.StockAgentApiClient;
    const homeView = document.getElementById('home-view');
    const loadingView = document.getElementById('loading-view');
    const reportView = document.getElementById('report-view');
    
    const tickerInput = document.getElementById('ticker-input');
    const analyzeBtn = document.getElementById('analyze-btn');
    const analyzeBtnText = analyzeBtn ? analyzeBtn.querySelector('span') : null;
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

    let currentReportFilename = null;
    let pendingAuditNotice = null;
    let currentPipeline = 'v1';
    const notify = window.StockAgentNotificationCenter.create();

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

    function updateAnalyzeButtonCopy() {
        if (!analyzeBtnText) return;
        const selectedPipeline = getSelectedPipeline();
        if (selectedPipeline === 'both') {
            analyzeBtnText.textContent = '連續執行 A+B+C';
        } else if (selectedPipeline === 'v4') {
            analyzeBtnText.textContent = '開始模式 D 分析';
        } else if (selectedPipeline === 'v3') {
            analyzeBtnText.textContent = '開始模式 C 分析';
        } else if (selectedPipeline === 'v2') {
            analyzeBtnText.textContent = '開始模式 B 分析';
        } else {
            analyzeBtnText.textContent = '開始模式 A 分析';
        }
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

    const opsWorkspace = window.StockAgentOpsWorkspace.create({ apiClient, ui });
    const operatorSummary = window.StockAgentOperatorSummaryPanel.create({ apiClient, ui });

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
    window.StockAgentHomeTabs.bind({
        onActivate: tabName => {
            if (tabName === 'ops') opsWorkspace.loadAllOnce();
        }
    });

    pipelineInputs.forEach(input => {
        input.addEventListener('change', updateAnalyzeButtonCopy);
    });
    updateAnalyzeButtonCopy();

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

    tickerInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            analyzeBtn.click();
        }
    });
});
