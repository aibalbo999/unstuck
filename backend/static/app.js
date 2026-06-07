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
    
    const downloadHtmlBtn = document.getElementById('download-html-btn');
    const downloadMdBtn = document.getElementById('download-md-btn');
    const downloadDataBtn = document.getElementById('download-data-btn');

    let currentReportFilename = null;
    let pendingAuditNotice = null;
    let historyPage = 1;
    const historyLimit = 20;
    let historySearchTimer = null;
    let currentPipeline = 'v1';
    let historyReports = new Map();
    let previewReport = null;
    let providerSlaPayload = null;

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
            providerSlaSummary.textContent = '來源健康度讀取失敗';
            providerSlaList.innerHTML = '<span class="provider-sla-chip is-warning">請稍後重試</span>';
        } finally {
            if (providerSlaRefresh) providerSlaRefresh.removeAttribute('disabled');
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

    const historyPanel = window.StockAgentHistoryPanel.create({
        listEl: historyList,
        paginationEl: historyPagination,
        prevBtn: historyPrev,
        nextBtn: historyNext,
        pageInfoEl: historyPageInfo,
        escapeHtml: ui.escapeHtml,
        renderPipelineModeBadge: ui.renderPipelineModeBadge,
        renderDataTrustBadge: ui.renderDataTrustBadge,
        recommendationTone: ui.recommendationTone,
        normalizeRecommendation: ui.normalizeRecommendation
    });

    const reportPreviewPanel = window.StockAgentReportPreviewPanel.create({
        elements: {
            root: reportPreview,
            mode: previewMode,
            title: previewTitle,
            price: previewPrice,
            recommendation: previewRecommendation,
            confidence: previewConfidence,
            target3m: previewTarget3m,
            target6m: previewTarget6m,
            target12m: previewTarget12m,
            summary: previewSummary,
            staleNotice: previewStaleNotice
        },
        escapeHtml: ui.escapeHtml,
        renderPipelineModeBadge: ui.renderPipelineModeBadge,
        renderDataTrustBadge: ui.renderDataTrustBadge,
        recommendationTone: ui.recommendationTone,
        normalizeRecommendation: ui.normalizeRecommendation
    });

    // 載入歷史報告
    async function loadHistory() {
        try {
            const query = historySearch ? historySearch.value.trim() : '';
            const pipelineFilter = historyPipelineFilter ? historyPipelineFilter.value : 'all';
            const recommendationFilter = historyRecommendationFilter ? historyRecommendationFilter.value : 'all';
            const dataTrustFilter = historyDataTrustFilter ? historyDataTrustFilter.value : 'all';
            const data = await apiClient.fetchReports({
                page: historyPage,
                limit: historyLimit,
                query,
                pipeline: pipelineFilter,
                recommendation: recommendationFilter,
                dataTrust: dataTrustFilter
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
        if (!previewReport || !previewRefreshDataBtn) return;
        const filename = previewReport.filename;
        const label = previewRefreshDataBtn.querySelector('span');
        const originalText = label ? label.textContent : '刷新資料快照';
        previewRefreshDataBtn.disabled = true;
        if (label) label.textContent = '刷新中';
        try {
            const payload = await apiClient.refreshReportDataSnapshot(filename);
            const updated = {
                ...previewReport,
                data_trust: payload.data_trust || previewReport.data_trust,
                data_snapshot_filename: payload.data_filename || previewReport.data_snapshot_filename,
                analysis_text_stale: payload.analysis_text_stale || previewReport.analysis_text_stale,
                analysis_text_stale_message: payload.analysis_text_stale_message || previewReport.analysis_text_stale_message
            };
            historyReports.set(filename, updated);
            previewReport = updated;
            showReportPreview(filename);
            await loadHistory();
            await loadProviderSla();
            const summary = payload.refresh_diff && Array.isArray(payload.refresh_diff.summary)
                ? payload.refresh_diff.summary.slice(0, 3).join('；')
                : '資料快照已刷新';
            alert(`資料快照已刷新：${summary}`);
        } catch (err) {
            console.error('Failed to refresh data snapshot', err);
            alert(`刷新資料快照失敗：${err.message || err}`);
        } finally {
            previewRefreshDataBtn.disabled = false;
            if (label) label.textContent = originalText;
        }
    }

    async function rerunPreviewReport(scope) {
        return window.StockAgentReportRerun.rerunPreviewReport({
            scope,
            previewReport,
            buttons: {
                final: previewRerunFinalBtn,
                modeB: previewRerunModeBBtn,
                cancel: previewRerunCancelBtn
            },
            statusEl: previewStaleNotice,
            loadHistory,
            loadProviderSla,
            openReport
        });
    }

    historyPanel.bindEvents({ onDelete: deleteReport, onSelect: showReportPreview });

    // 開啟報告
    function openReport(filename, ticker, pipelineId = 'v1') {
        currentReportFilename = filename;
        currentPipeline = pipelineId;
        reportTickerTitle.textContent = `${ticker} ${ui.pipelineMeta(pipelineId).reportSuffix}`;
        setAuditNotice(null);
        reportIframe.src = `/api/report/${encodeURIComponent(filename)}`;
        switchView('report-view');
    }
    window.openReport = openReport;

    if (previewOpenReportBtn) {
        previewOpenReportBtn.addEventListener('click', () => {
            if (!previewReport) return;
            openReport(previewReport.filename, previewReport.ticker, previewReport.pipeline_id || 'v1');
        });
    }

    if (previewRefreshDataBtn) {
        previewRefreshDataBtn.addEventListener('click', refreshPreviewDataSnapshot);
    }

    if (previewRerunFinalBtn) {
        previewRerunFinalBtn.addEventListener('click', () => rerunPreviewReport('final_recommendation'));
    }

    if (previewRerunModeBBtn) {
        previewRerunModeBBtn.addEventListener('click', () => rerunPreviewReport('mode_b'));
    }

    if (previewCloseBtn) {
        previewCloseBtn.addEventListener('click', hideReportPreview);
    }

    if (downloadHtmlBtn) {
        downloadHtmlBtn.addEventListener('click', () => {
            if (currentReportFilename) {
                window.location.href = `/api/report/${encodeURIComponent(currentReportFilename)}/download/html`;
            }
        });
    }

    if (downloadMdBtn) {
        downloadMdBtn.addEventListener('click', () => {
            if (currentReportFilename) {
                window.location.href = `/api/report/${encodeURIComponent(currentReportFilename)}/download/md`;
            }
        });
    }

    if (downloadDataBtn) {
        downloadDataBtn.addEventListener('click', () => {
            if (currentReportFilename) {
                window.location.href = `/api/report/${encodeURIComponent(currentReportFilename)}/download/data`;
            }
        });
    }

    // 刪除報告
    async function deleteReport(filename, event) {
        event.stopPropagation();
        if (confirm('確定要刪除這份報告嗎？')) {
            try {
                const result = await apiClient.deleteReport(filename);
                if (result.success) {
                    if (previewReport && previewReport.filename === filename) hideReportPreview();
                    loadHistory();
                } else {
                    alert('刪除失敗：' + result.error);
                }
            } catch (err) {
                console.error(err);
                alert('刪除失敗');
            }
        }
    }
    window.deleteReport = deleteReport;

    // 初始化時載入歷史
    loadHistory();
    loadProviderSla();

    if (providerSlaRefresh) {
        providerSlaRefresh.addEventListener('click', loadProviderSla);
    }

    if (providerSlaWindow) {
        providerSlaWindow.addEventListener('change', loadProviderSla);
    }

    if (historySearch) {
        historySearch.addEventListener('input', () => {
            clearTimeout(historySearchTimer);
            historySearchTimer = setTimeout(() => {
                historyPage = 1;
                loadHistory();
            }, 200);
        });
    }

    [historyPipelineFilter, historyRecommendationFilter, historyDataTrustFilter].forEach(filter => {
        if (!filter) return;
        filter.addEventListener('change', () => {
            historyPage = 1;
            hideReportPreview();
            loadHistory();
        });
    });

    pipelineInputs.forEach(input => {
        input.addEventListener('change', updateAnalyzeButtonCopy);
    });
    updateAnalyzeButtonCopy();

    if (historyPrev) {
        historyPrev.addEventListener('click', () => {
            if (historyPage > 1) {
                historyPage -= 1;
                loadHistory();
            }
        });
    }

    if (historyNext) {
        historyNext.addEventListener('click', () => {
            historyPage += 1;
            loadHistory();
        });
    }

    function switchView(viewId) {
        // 隱藏所有 view
        [homeView, loadingView, reportView].forEach(v => {
            v.classList.remove('active');
            setTimeout(() => {
                if (!v.classList.contains('active')) {
                    v.style.display = 'none';
                }
            }, 500); // match CSS transition time
        });

        // 顯示目標 view
        const target = document.getElementById(viewId);
        target.style.display = 'flex';
        // force reflow
        void target.offsetWidth;
        target.classList.add('active');
    }

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

    // 支援 Enter 鍵送出
    tickerInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            analyzeBtn.click();
        }
    });
});
