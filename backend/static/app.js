document.addEventListener('DOMContentLoaded', () => {
    const homeView = document.getElementById('home-view');
    const loadingView = document.getElementById('loading-view');
    const reportView = document.getElementById('report-view');
    
    const tickerInput = document.getElementById('ticker-input');
    const analyzeBtn = document.getElementById('analyze-btn');
    const backBtn = document.getElementById('back-btn');
    
    const loadingStatus = document.getElementById('loading-status');
    const loadingMsg = document.getElementById('loading-msg');
    const progressBar = document.getElementById('progress-bar');
    
    const reportIframe = document.getElementById('report-iframe');
    const reportTickerTitle = document.getElementById('report-ticker-title');
    const reportAuditNotice = document.getElementById('report-audit-notice');
    const historyList = document.getElementById('history-list');
    
    const downloadHtmlBtn = document.getElementById('download-html-btn');
    const downloadMdBtn = document.getElementById('download-md-btn');

    let eventSource = null;
    let currentReportFilename = null;
    let pendingAuditNotice = null;

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
            const res = await fetch('/api/reports');
            const data = await res.json();
            
            if (data.reports && data.reports.length > 0) {
                historyList.innerHTML = data.reports.map(r => `
                    <div class="history-item" data-filename="${r.filename}">
                        <div class="history-info" onclick="openReport('${r.filename}', '${r.ticker}')">
                            <div class="history-ticker">
                                ${r.ticker}${r.company_name && r.company_name !== r.ticker ? `<span class="history-company">${r.company_name}</span>` : ''}
                            </div>
                            <div class="history-date">${r.date}</div>
                        </div>
                        <button class="delete-btn" onclick="deleteReport('${r.filename}', event)" title="刪除報告">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                        </button>
                    </div>
                `).join('');
            } else {
                historyList.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.9rem; text-align: center; padding: 20px 0;">尚無報告紀錄</div>';
            }
        } catch (err) {
            console.error('Failed to load history', err);
        }
    }

    // 開啟報告
    window.openReport = function(filename, ticker) {
        currentReportFilename = filename;
        reportTickerTitle.textContent = `${ticker} 深度分析報告`;
        setAuditNotice(null);
        reportIframe.src = `/api/report/${filename}`;
        switchView('report-view');
    };

    if (downloadHtmlBtn) {
        downloadHtmlBtn.addEventListener('click', () => {
            if (currentReportFilename) {
                window.location.href = `/api/report/${currentReportFilename}/download/html`;
            }
        });
    }

    if (downloadMdBtn) {
        downloadMdBtn.addEventListener('click', () => {
            if (currentReportFilename) {
                window.location.href = `/api/report/${currentReportFilename}/download/md`;
            }
        });
    }

    // 刪除報告
    window.deleteReport = async function(filename, event) {
        event.stopPropagation();
        if (confirm('確定要刪除這份報告嗎？')) {
            try {
                const res = await fetch(`/api/reports/${filename}`, { method: 'DELETE' });
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
    };

    // 初始化時載入歷史
    loadHistory();

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

    analyzeBtn.addEventListener('click', () => {
        const ticker = tickerInput.value.trim().toUpperCase();
        if (!ticker) {
            alert('請輸入股票代號！');
            return;
        }

        // 準備 Loading 畫面
        loadingStatus.textContent = '連接 Wall Street 系統...';
        loadingMsg.textContent = '';
        progressBar.style.width = '0%';
        pendingAuditNotice = null;
        setAuditNotice(null);
        switchView('loading-view');

        // 啟動 SSE
        if (eventSource) {
            eventSource.close();
        }

        eventSource = new EventSource(`/api/analyze/${ticker}`);

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === 'status') {
                    loadingStatus.textContent = data.message;
                } else if (data.type === 'progress') {
                    loadingStatus.textContent = `分析中：Agent ${data.current}/${data.total}`;
                    loadingMsg.textContent = data.name;
                    const percent = (data.current / data.total) * 100;
                    progressBar.style.width = `${percent}%`;
                } else if (data.type === 'done') {
                    eventSource.close();
                    
                    // 載入報告
                    currentReportFilename = data.filename;
                    reportTickerTitle.textContent = `${ticker} 深度分析報告`;
                    setAuditNotice(data.audit || pendingAuditNotice);
                    reportIframe.src = `/api/report/${data.filename}`;
                    
                    // 等待一下下再切換，讓進度條跑滿動畫看完
                    setTimeout(() => {
                        switchView('report-view');
                        loadHistory(); // 重新整理歷史紀錄
                    }, 800);
                } else if (data.type === 'error') {
                    loadingStatus.textContent = '發生錯誤';
                    loadingMsg.textContent = data.message;
                    eventSource.close();
                    
                    setTimeout(() => {
                        switchView('home-view');
                    }, 5000);
                } else if (data.type === 'audit') {
                    pendingAuditNotice = data.audit || data;
                    if (pendingAuditNotice.status === 'needs_attention') {
                        loadingStatus.textContent = pendingAuditNotice.message;
                    }
                }
            } catch (err) {
                console.error("Parse error:", err);
            }
        };

        eventSource.onerror = (err) => {
            console.log("SSE Error or connection closed.");
        };
    });

    backBtn.addEventListener('click', () => {
        if (eventSource) {
            eventSource.close();
        }
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
