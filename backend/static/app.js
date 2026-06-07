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
    const previewRerunFinalBtn = document.getElementById('preview-rerun-final-btn');
    const previewRerunModeBBtn = document.getElementById('preview-rerun-modeb-btn');
    const previewRerunCancelBtn = document.getElementById('preview-rerun-cancel-btn');
    const previewCloseBtn = document.getElementById('preview-close-btn');
    const providerSlaSummary = document.getElementById('provider-sla-summary');
    const providerSlaList = document.getElementById('provider-sla-list');
    const providerSlaRefresh = document.getElementById('provider-sla-refresh');
    const providerSlaWindow = document.getElementById('provider-sla-window');
    const activeJobsSummary = document.getElementById('active-jobs-summary');
    const activeJobsList = document.getElementById('active-jobs-list');
    const activeJobsRefresh = document.getElementById('active-jobs-refresh');
    
    const downloadHtmlBtn = document.getElementById('download-html-btn');
    const downloadMdBtn = document.getElementById('download-md-btn');
    const downloadDataBtn = document.getElementById('download-data-btn');

    let currentReportFilename = null;
    let pendingAuditNotice = null;
    let currentPipeline = 'v1';
    let providerSlaPayload = null;

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

    function renderProviderSla(payload) {
        window.StockAgentProviderSlaPanel.render(payload, {
            summaryEl: providerSlaSummary,
            listEl: providerSlaList,
            windowEl: providerSlaWindow,
            escapeHtml: ui.escapeHtml
        });
    }

    async function loadProviderSla() {
        if (!providerSlaSummary || !providerSlaList) return;
        try {
            if (providerSlaRefresh) providerSlaRefresh.setAttribute('disabled', 'disabled');
            providerSlaPayload = await apiClient.fetchProviderSla({
                windowValue: providerSlaWindow ? providerSlaWindow.value || 'all' : 'all',
                limit: 12
            });
            renderProviderSla(providerSlaPayload);
        } catch (err) {
            console.error('Failed to load provider SLA', err);
            providerSlaSummary.textContent = '全系統資料來源狀態讀取失敗';
            providerSlaList.innerHTML = '<span class="provider-sla-chip is-warning">請稍後重試</span>';
        } finally {
            if (providerSlaRefresh) providerSlaRefresh.removeAttribute('disabled');
        }
    }

    async function loadActiveJobs() {
        if (!activeJobsSummary || !activeJobsList) return;
        try {
            if (activeJobsRefresh) activeJobsRefresh.setAttribute('disabled', 'disabled');
            const payload = await apiClient.fetchActiveJobs({ limit: 5, eventLimit: 40 });
            window.StockAgentActiveJobsPanel.render(payload, {
                summaryEl: activeJobsSummary,
                listEl: activeJobsList,
                escapeHtml: ui.escapeHtml
            });
        } catch (err) {
            console.error('Failed to load active jobs', err);
            activeJobsSummary.textContent = '任務狀態讀取失敗';
            activeJobsList.innerHTML = '<span class="provider-sla-chip is-warning">請稍後重試</span>';
        } finally {
            if (activeJobsRefresh) activeJobsRefresh.removeAttribute('disabled');
        }
    }

    function updateAnalyzeButtonCopy() {
        if (!analyzeBtnText) return;
        const selectedPipeline = getSelectedPipeline();
        if (selectedPipeline === 'both') {
            analyzeBtnText.textContent = '連續執行 A+B';
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

    const historyWorkspace = window.StockAgentHistoryWorkspace.create({
        apiClient,
        ui,
        loadProviderSla,
        openReport,
        elements: {
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
            previewRerunFinalBtn,
            previewRerunModeBBtn,
            previewRerunCancelBtn,
            previewCloseBtn
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

    loadHistory();
    loadProviderSla();
    loadActiveJobs();

    if (providerSlaRefresh) {
        providerSlaRefresh.addEventListener('click', loadProviderSla);
    }

    if (providerSlaWindow) {
        providerSlaWindow.addEventListener('change', loadProviderSla);
    }

    if (activeJobsRefresh) {
        activeJobsRefresh.addEventListener('click', loadActiveJobs);
    }

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
            alert('請輸入股票代號！');
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
