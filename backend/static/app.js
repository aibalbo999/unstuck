document.addEventListener('DOMContentLoaded', () => {
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

    const PIPELINE_META = {
        v1: {
            label: '模式 A：學術深度派',
            shortLabel: '學術深度派',
            reportSuffix: '深度分析報告',
            hint: '請稍候，7 位 AI 分析師正在為您撰寫深度研報...'
        },
        v2: {
            label: '模式 B：實戰交易派',
            shortLabel: '實戰交易派',
            reportSuffix: '實戰交易決策報告',
            hint: '請稍候，6 位 AI 分析師正在整合總經、籌碼與進出場策略...'
        },
        both: {
            label: '連續模式：模式 A → 模式 B',
            shortLabel: 'A+B 連續',
            reportSuffix: '雙模式分析完成',
            hint: '將先執行學術深度派，再接續實戰交易派；完成後會產出兩份獨立報告。'
        }
    };

    function getSelectedPipeline() {
        const selected = document.querySelector('input[name="pipeline-mode"]:checked') || pipelineInputs.find(input => input.checked);
        return selected ? selected.value : 'v1';
    }

    function pipelineMeta(pipelineId) {
        return PIPELINE_META[pipelineId] || PIPELINE_META.v1;
    }

    function pipelineModeClass(pipelineId) {
        if (pipelineId === 'both') return 'is-both';
        return pipelineId === 'v2' ? 'is-v2' : 'is-v1';
    }

    function pipelineModeLabel(pipelineId) {
        if (pipelineId === 'both') return '連續 A+B · 兩份報告';
        return pipelineId === 'v2' ? '模式 B · 實戰交易派' : '模式 A · 學術深度派';
    }

    function renderPipelineModeBadge(pipelineId) {
        return `<span class="history-mode ${pipelineModeClass(pipelineId)}">${escapeHtml(pipelineModeLabel(pipelineId))}</span>`;
    }

    function dataTrustLabel(trust) {
        const status = trust && trust.status ? trust.status : 'unknown';
        const labels = {
            fresh: '資料新鮮',
            partial: '部分異常',
            stale: '部分過期',
            error: '來源異常',
            unknown: '未記錄'
        };
        return labels[status] || labels.unknown;
    }

    function dataTrustClass(trust) {
        const status = trust && trust.status ? trust.status : 'unknown';
        return ['fresh', 'partial', 'stale', 'error'].includes(status) ? status : 'unknown';
    }

    function renderDataTrustBadge(trust) {
        return `<span class="data-trust-badge is-${dataTrustClass(trust)}">${escapeHtml(dataTrustLabel(trust))}</span>`;
    }

    function renderProviderSla(payload) {
        window.StockAgentProviderSlaPanel.render(payload, {
            summaryEl: providerSlaSummary,
            listEl: providerSlaList,
            windowEl: providerSlaWindow,
            escapeHtml
        });
    }

    async function loadProviderSla() {
        if (!providerSlaSummary || !providerSlaList) return;
        try {
            if (providerSlaRefresh) providerSlaRefresh.setAttribute('disabled', 'disabled');
            const params = new URLSearchParams({ limit: '12' });
            if (providerSlaWindow) params.set('window', providerSlaWindow.value || 'all');
            const res = await fetch(`/api/observability/provider-sla?${params.toString()}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            providerSlaPayload = await res.json();
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

    function normalizeRecommendation(value) {
        const text = String(value || 'N/A');
        if (text.includes('買入')) return '買入';
        if (text.includes('避免') || text.includes('賣出')) return '避免';
        if (text.includes('持有')) return '持有';
        return text;
    }

    function recommendationTone(value) {
        const text = normalizeRecommendation(value);
        if (text === '買入') return 'is-buy';
        if (text === '避免') return 'is-avoid';
        return 'is-hold';
    }

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (char) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[char]));
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

    // 載入歷史報告
    async function loadHistory() {
        try {
            const query = historySearch ? historySearch.value.trim() : '';
            const pipelineFilter = historyPipelineFilter ? historyPipelineFilter.value : 'all';
            const recommendationFilter = historyRecommendationFilter ? historyRecommendationFilter.value : 'all';
            const dataTrustFilter = historyDataTrustFilter ? historyDataTrustFilter.value : 'all';
            const params = new URLSearchParams({
                page: String(historyPage),
                limit: String(historyLimit)
            });
            if (query) params.set('q', query);
            if (pipelineFilter !== 'all') params.set('pipeline', pipelineFilter);
            if (recommendationFilter !== 'all') params.set('recommendation', recommendationFilter);
            if (dataTrustFilter !== 'all') params.set('data_trust', dataTrustFilter);
            const res = await fetch(`/api/reports?${params.toString()}`);
            const data = await res.json();
            const pagination = data.pagination || { page: 1, total_pages: 1, total: 0, has_prev: false, has_next: false };
            historyReports = new Map((data.reports || []).map(report => [report.filename, report]));
            
            if (data.reports && data.reports.length > 0) {
                historyList.innerHTML = data.reports.map(r => `
                    <div class="history-item" data-filename="${escapeHtml(r.filename)}" data-ticker="${escapeHtml(r.ticker)}" data-pipeline="${escapeHtml(r.pipeline_id || 'v1')}">
                        <div class="history-info" role="button" tabindex="0">
                            <div class="history-ticker">
                                ${escapeHtml(r.ticker)}${r.company_name && r.company_name !== r.ticker ? `<span class="history-company">${escapeHtml(r.company_name)}</span>` : ''}
                            </div>
                            <div class="history-date">
                                <span>${escapeHtml(r.date)}</span>
                                ${renderPipelineModeBadge(r.pipeline_id || 'v1')}
                                ${renderDataTrustBadge(r.data_trust)}
                            </div>
                            <div class="history-decision">
                                <span class="history-rec ${recommendationTone(r.recommendation?.recommendation)}">${escapeHtml(normalizeRecommendation(r.recommendation?.recommendation))}</span>
                                <span>${escapeHtml(r.recommendation?.target_12m || 'N/A')}</span>
                                <span>${escapeHtml(r.recommendation?.confidence || 'N/A')}</span>
                            </div>
                        </div>
                        <button class="delete-btn" title="刪除報告" data-delete-filename="${escapeHtml(r.filename)}">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                        </button>
                    </div>
                `).join('');
                if (previewReport && historyReports.has(previewReport.filename)) {
                    historyList.querySelectorAll('.history-item').forEach(item => {
                        item.classList.toggle('is-selected', item.dataset.filename === previewReport.filename);
                    });
                } else if (previewReport) {
                    hideReportPreview();
                }
            } else {
                historyList.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.9rem; text-align: center; padding: 20px 0;">尚無報告紀錄</div>';
                hideReportPreview();
            }
            renderHistoryPagination(pagination);
        } catch (err) {
            console.error('Failed to load history', err);
        }
    }

    function renderHistoryPagination(pagination) {
        if (!historyPagination || !historyPrev || !historyNext || !historyPageInfo) return;
        const totalPages = pagination.total_pages || 1;
        historyPagination.hidden = totalPages <= 1;
        historyPrev.disabled = !pagination.has_prev;
        historyNext.disabled = !pagination.has_next;
        historyPage = pagination.page || 1;
        historyPageInfo.textContent = `${historyPage} / ${totalPages}`;
    }

    function hideReportPreview() {
        previewReport = null;
        if (reportPreview) reportPreview.hidden = true;
        historyList.querySelectorAll('.history-item.is-selected').forEach(item => {
            item.classList.remove('is-selected');
        });
    }

    function showReportPreview(filename) {
        const report = historyReports.get(filename);
        if (!report || !reportPreview) return;
        previewReport = report;
        const rec = report.recommendation || {};
        const pipelineId = report.pipeline_id || 'v1';

        previewMode.innerHTML = `${renderPipelineModeBadge(pipelineId)}${renderDataTrustBadge(report.data_trust)}<span class="preview-date">${escapeHtml(report.date || '')}</span>`;
        previewTitle.textContent = `${report.ticker} 投資建議`;
        previewPrice.textContent = rec.current_price || 'N/A';
        previewRecommendation.textContent = normalizeRecommendation(rec.recommendation);
        previewRecommendation.className = recommendationTone(rec.recommendation);
        previewConfidence.textContent = rec.confidence || 'N/A';
        previewTarget3m.textContent = rec.target_3m || 'N/A';
        previewTarget6m.textContent = rec.target_6m || 'N/A';
        previewTarget12m.textContent = rec.target_12m || 'N/A';
        previewSummary.textContent = rec.summary || '這份報告沒有可讀的一頁式摘要，可直接查看完整報告。';
        if (previewStaleNotice) {
            const staleMessage = report.analysis_text_stale_message
                || '資料快照已刷新，但這份 HTML/Markdown 分析本文尚未重新執行。';
            previewStaleNotice.textContent = staleMessage;
            previewStaleNotice.hidden = !report.analysis_text_stale;
        }

        historyList.querySelectorAll('.history-item').forEach(item => {
            item.classList.toggle('is-selected', item.dataset.filename === filename);
        });
        reportPreview.hidden = false;
    }

    async function refreshPreviewDataSnapshot() {
        if (!previewReport || !previewRefreshDataBtn) return;
        const filename = previewReport.filename;
        const label = previewRefreshDataBtn.querySelector('span');
        const originalText = label ? label.textContent : '刷新資料快照';
        previewRefreshDataBtn.disabled = true;
        if (label) label.textContent = '刷新中';
        try {
            const res = await fetch(`/api/report/${encodeURIComponent(filename)}/refresh/data`, { method: 'POST' });
            const payload = await res.json();
            if (!res.ok || payload.success === false) {
                throw new Error(payload.error || `HTTP ${res.status}`);
            }
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

    historyList.addEventListener('click', (event) => {
        const deleteBtn = event.target.closest('.delete-btn');
        if (deleteBtn) {
            deleteReport(deleteBtn.dataset.deleteFilename, event);
            return;
        }
        const item = event.target.closest('.history-item');
        if (item) {
            showReportPreview(item.dataset.filename);
        }
    });

    historyList.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter') return;
        const item = event.target.closest('.history-item');
        if (item) showReportPreview(item.dataset.filename);
    });

    // 開啟報告
    function openReport(filename, ticker, pipelineId = 'v1') {
        currentReportFilename = filename;
        currentPipeline = pipelineId;
        reportTickerTitle.textContent = `${ticker} ${pipelineMeta(pipelineId).reportSuffix}`;
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
                const res = await fetch(`/api/reports/${encodeURIComponent(filename)}`, { method: 'DELETE' });
                const result = await res.json();
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
        pipelineMeta,
        pipelineModeLabel,
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
        if (loadingHint) loadingHint.textContent = pipelineMeta(currentPipeline).hint;
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
