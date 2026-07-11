document.addEventListener('DOMContentLoaded', () => {
    const ui = window.StockAgentUi;
    const apiClient = window.StockAgentApiClient;
    const elements = window.StockAgentAppElements.collect(document);
    const {
        homeView, loadingView, reportView, tickerInput, analyzeBtn, analyzeBtnText,
        pipelineModeHint, backBtn, loadingStatus, loadingMsg, loadingHint, progressBar,
        pipelineInputs, reportIframe, reportTickerTitle, reportAuditNotice,
        historyPipelineFilter, downloadHtmlBtn, downloadMdBtn, downloadDataBtn
    } = elements;
    let currentReportFilename = null, pendingAuditNotice = null;
    let currentPipeline = 'v1';
    const notify = window.StockAgentNotificationCenter.create();
    window.StockAgentNotify = notify;
    const viewController = window.StockAgentViewController.create({
        views: { 'home-view': homeView, 'loading-view': loadingView, 'report-view': reportView }
    });
    const switchView = viewController.switchView;
    const pipelineControls = window.StockAgentAppPipelineControls.create({ ui, doc: document, pipelineInputs, analyzeBtnText, pipelineModeHint, historyPipelineFilter });
    const getSelectedPipeline = pipelineControls.getSelectedPipeline;
    const selectPipelineMode = pipelineControls.selectPipelineMode;
    const pipelineCatalogLoad = typeof ui.loadPipelineMeta === 'function' ? ui.loadPipelineMeta() : Promise.resolve(false);

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

    function openReport(filename, ticker, pipelineId = 'v1') {
        currentReportFilename = filename;
        currentPipeline = pipelineId;
        window.StockAgentReportActions.setReportTitle({ titleEl: reportTickerTitle, ticker, pipelineId, pipelineMeta: ui.pipelineMeta });
        setAuditNotice(null);
        reportIframe.src = `/api/report/${encodeURIComponent(filename)}`;
        switchView('report-view');
    }
    window.openReport = openReport;

    const appPanels = window.StockAgentAppPanels.create({ apiClient, ui, notify, elements, doc: document, openReport, switchView, selectPipelineMode, getSelectedPipeline });
    const opsWorkspace = appPanels.opsWorkspace;
    const marketScreenerPanel = appPanels.marketScreenerPanel;
    const loadHistory = appPanels.loadHistory;
    appPanels.bindPanelEvents();
    window.StockAgentReportActions.bindDownloads({ htmlBtn: downloadHtmlBtn, mdBtn: downloadMdBtn, dataBtn: downloadDataBtn, getFilename: () => currentReportFilename });
    window.StockAgentReportNavigation.bind(reportIframe);
    appPanels.loadInitialPanels();

    window.StockAgentHomeTabs.bind({
        onActivate: tabName => {
            if (tabName === 'screener') marketScreenerPanel.loadOnce();
            if (tabName === 'tracking') opsWorkspace.loadWatchlistOnce();
            if (tabName === 'ops') opsWorkspace.loadAllOnce();
        }
    });
    pipelineInputs.forEach(input => {
        input.addEventListener('change', () => {
            pipelineControls.updateAnalyzeButtonCopy();
            pipelineControls.updatePipelineModeHint();
        });
    });
    pipelineControls.syncPipelineOptionLabels();
    pipelineControls.updateAnalyzeButtonCopy();
    pipelineControls.updatePipelineModeHint();
    pipelineCatalogLoad.then(applied => {
        if (!applied) return;
        pipelineControls.syncPipelineOptionLabels();
        pipelineControls.updateAnalyzeButtonCopy();
        pipelineControls.updatePipelineModeHint();
    });

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
            if (Object.prototype.hasOwnProperty.call(patch, 'currentReportFilename')) currentReportFilename = patch.currentReportFilename;
            if (Object.prototype.hasOwnProperty.call(patch, 'currentPipeline')) currentPipeline = patch.currentPipeline;
            if (Object.prototype.hasOwnProperty.call(patch, 'pendingAuditNotice')) pendingAuditNotice = patch.pendingAuditNotice;
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
        reportIframe.src = 'about:blank';
        tickerInput.value = '';
        switchView('home-view');
    });
    tickerInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); analyzeBtn.click(); }
    });
});
