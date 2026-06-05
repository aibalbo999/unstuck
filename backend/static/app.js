document.addEventListener('DOMContentLoaded', () => {
    const homeView = document.getElementById('home-view');
    const loadingView = document.getElementById('loading-view');
    const reportView = document.getElementById('report-view');
    
    const tickerInput = document.getElementById('ticker-input');
    const analyzeBtn = document.getElementById('analyze-btn');
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
    const historyPagination = document.getElementById('history-pagination');
    const historyPrev = document.getElementById('history-prev');
    const historyNext = document.getElementById('history-next');
    const historyPageInfo = document.getElementById('history-page-info');
    
    const downloadHtmlBtn = document.getElementById('download-html-btn');
    const downloadMdBtn = document.getElementById('download-md-btn');

    let eventSource = null;
    let currentReportFilename = null;
    let pendingAuditNotice = null;
    let historyPage = 1;
    const historyLimit = 10;
    let historySearchTimer = null;
    let currentJobId = null;
    let lastEventId = 0;
    let reconnectTimer = null;
    let reconnectAttempts = 0;
    let streamClosedByClient = false;
    let currentPipeline = 'v1';

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
        }
    };

    function getSelectedPipeline() {
        const selected = pipelineInputs.find(input => input.checked);
        return selected ? selected.value : 'v1';
    }

    function pipelineMeta(pipelineId) {
        return PIPELINE_META[pipelineId] || PIPELINE_META.v1;
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
            const params = new URLSearchParams({
                page: String(historyPage),
                limit: String(historyLimit)
            });
            if (query) params.set('q', query);
            const res = await fetch(`/api/reports?${params.toString()}`);
            const data = await res.json();
            const pagination = data.pagination || { page: 1, total_pages: 1, total: 0, has_prev: false, has_next: false };
            
            if (data.reports && data.reports.length > 0) {
                historyList.innerHTML = data.reports.map(r => `
                    <div class="history-item" data-filename="${escapeHtml(r.filename)}" data-ticker="${escapeHtml(r.ticker)}" data-pipeline="${escapeHtml(r.pipeline_id || 'v1')}">
                        <div class="history-info" role="button" tabindex="0">
                            <div class="history-ticker">
                                ${escapeHtml(r.ticker)}${r.company_name && r.company_name !== r.ticker ? `<span class="history-company">${escapeHtml(r.company_name)}</span>` : ''}
                            </div>
                            <div class="history-date">${escapeHtml(r.date)}<span class="history-mode">${escapeHtml(r.pipeline_label || pipelineMeta(r.pipeline_id).shortLabel)}</span></div>
                        </div>
                        <button class="delete-btn" title="刪除報告" data-delete-filename="${escapeHtml(r.filename)}">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                        </button>
                    </div>
                `).join('');
            } else {
                historyList.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.9rem; text-align: center; padding: 20px 0;">尚無報告紀錄</div>';
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

    historyList.addEventListener('click', (event) => {
        const deleteBtn = event.target.closest('.delete-btn');
        if (deleteBtn) {
            deleteReport(deleteBtn.dataset.deleteFilename, event);
            return;
        }
        const item = event.target.closest('.history-item');
        if (item) {
            openReport(item.dataset.filename, item.dataset.ticker, item.dataset.pipeline || 'v1');
        }
    });

    historyList.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter') return;
        const item = event.target.closest('.history-item');
        if (item) openReport(item.dataset.filename, item.dataset.ticker, item.dataset.pipeline || 'v1');
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

    // 刪除報告
    async function deleteReport(filename, event) {
        event.stopPropagation();
        if (confirm('確定要刪除這份報告嗎？')) {
            try {
                const res = await fetch(`/api/reports/${encodeURIComponent(filename)}`, { method: 'DELETE' });
                const result = await res.json();
                if (result.success) {
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

    if (historySearch) {
        historySearch.addEventListener('input', () => {
            clearTimeout(historySearchTimer);
            historySearchTimer = setTimeout(() => {
                historyPage = 1;
                loadHistory();
            }, 200);
        });
    }

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

    function closeAnalysisStream() {
        streamClosedByClient = true;
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
    }

    function connectAnalysisStream(ticker, pipelineId) {
        clearTimeout(reconnectTimer);
        streamClosedByClient = false;
        if (eventSource) eventSource.close();

        const params = new URLSearchParams();
        params.set('pipeline', pipelineId || 'v1');
        if (currentJobId) params.set('job_id', currentJobId);
        if (lastEventId) params.set('last_event_id', String(lastEventId));
        const query = params.toString();
        const url = `/api/analyze/${encodeURIComponent(ticker)}${query ? `?${query}` : ''}`;
        eventSource = new EventSource(url);

        eventSource.onmessage = (event) => {
            reconnectAttempts = 0;
            if (event.lastEventId) {
                const parsedId = Number(event.lastEventId);
                if (Number.isFinite(parsedId)) lastEventId = Math.max(lastEventId, parsedId);
            }

            try {
                handleAnalysisEvent(JSON.parse(event.data), ticker);
            } catch (err) {
                console.error("Parse error:", err);
            }
        };

        eventSource.onerror = () => {
            if (streamClosedByClient) return;
            if (eventSource) eventSource.close();
            const delay = Math.min(30000, 1000 * (2 ** reconnectAttempts));
            reconnectAttempts += 1;
            loadingMsg.textContent = `連線中斷，${Math.ceil(delay / 1000)} 秒後自動接續...`;
            reconnectTimer = setTimeout(() => connectAnalysisStream(ticker, pipelineId), delay);
        };
    }

    function handleAnalysisEvent(data, ticker) {
        if (data.type === 'job') {
            currentJobId = data.job_id || currentJobId;
            currentPipeline = data.pipeline_id || currentPipeline;
            if (loadingHint) loadingHint.textContent = pipelineMeta(currentPipeline).hint;
            if (data.resume_after_id) lastEventId = Math.max(lastEventId, Number(data.resume_after_id) || 0);
            return;
        }

        if (data.type === 'status') {
            loadingStatus.textContent = data.message;
            if (data.detail) {
                loadingMsg.textContent = data.detail;
            }
        } else if (data.type === 'progress') {
            loadingStatus.textContent = `分析中：第 ${data.current}/${data.total} 位分析師`;
            loadingMsg.textContent = data.name;
            const percent = (data.current / data.total) * 100;
            progressBar.style.width = `${percent}%`;
        } else if (data.type === 'done') {
            closeAnalysisStream();

            currentReportFilename = data.filename;
            reportTickerTitle.textContent = `${ticker} ${pipelineMeta(data.pipeline_id || currentPipeline).reportSuffix}`;
            setAuditNotice(data.audit || pendingAuditNotice);
            reportIframe.src = `/api/report/${encodeURIComponent(data.filename)}`;

            setTimeout(() => {
                switchView('report-view');
                loadHistory();
            }, 800);
        } else if (data.type === 'error') {
            loadingStatus.textContent = '發生錯誤';
            loadingMsg.textContent = data.message;
            closeAnalysisStream();

            setTimeout(() => {
                switchView('home-view');
            }, 5000);
        } else if (data.type === 'audit') {
            pendingAuditNotice = data.audit || data;
            if (pendingAuditNotice.status === 'needs_attention') {
                loadingStatus.textContent = pendingAuditNotice.message;
            }
        }
    }

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
        currentJobId = null;
        lastEventId = 0;
        reconnectAttempts = 0;
        setAuditNotice(null);
        closeAnalysisStream();
        switchView('loading-view');
        connectAnalysisStream(ticker, currentPipeline);
    });

    backBtn.addEventListener('click', () => {
        closeAnalysisStream();
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
