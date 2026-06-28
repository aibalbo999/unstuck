(function () {
    const byId = id => document.getElementById(id);
    function setItem(el, tone, value, detail) {
        if (!el) return;
        el.className = `operator-summary-item is-${tone}`;
        const strong = el.querySelector('strong');
        const em = el.querySelector('em');
        if (strong) strong.textContent = value;
        if (em) em.textContent = detail || '';
    }
    function quotaErrorCount(service) {
        const usage = service?.usage || {};
        return Number(usage.observed_quota_errors_since_reset || usage.observed_24h_errors || 0);
    }
    function activeJobText(payload) {
        const active = Number(payload?.active_count || 0);
        const jobs = payload?.jobs || [];
        if (active) return { tone: 'warning', value: `${active} 個進行中`, detail: jobs[0]?.ticker || '' };
        return { tone: 'ok', value: '無進行中任務', detail: jobs[0] ? `最近 ${jobs[0].ticker || 'N/A'}` : '等待下一次分析' };
    }
    const dataTrustReasonCodes = report => Array.isArray(report?.data_trust?.reason_codes) ? report.data_trust.reason_codes.map(code => String(code || '')) : [];
    const reportNeedsRerun = report => Boolean(report?.analysis_text_stale || report?.decision_freshness?.requires_rerun || report?.requires_rerun);
    function requiresDataTrustAction(report) {
        const status = report?.data_trust?.status || 'unknown';
        const codes = dataTrustReasonCodes(report);
        return status === 'error' || hasRefreshableDataTrustIssue(report) || reportNeedsRerun(report) || codes.some(code => code.startsWith('source_error:'));
    }
    const isSourceNotice = report => report?.data_trust?.status === 'partial' && !requiresDataTrustAction(report) && dataTrustReasonCodes(report).includes('provider_sla_critical');
    const sourceNoticeReports = reports => reports.filter(isSourceNotice);
    function trustText(payload) {
        const reports = payload?.reports || [];
        if (!reports.length) return { tone: 'warning', value: '尚無報告', detail: '等待資料快照' };
        const fresh = reports.filter(report => report?.data_trust?.status === 'fresh').length;
        const actionCount = reports.filter(requiresDataTrustAction).length;
        if (actionCount) return { tone: 'warning', value: `${actionCount} 份需處理`, detail: `fresh ${fresh} / sampled ${reports.length}` };
        const notices = sourceNoticeReports(reports).length;
        if (notices) return { tone: 'warning', value: `${notices} 份來源提醒`, detail: `無需刷新/重跑 · fresh ${fresh} / sampled ${reports.length}` };
        return { tone: 'ok', value: '近期資料正常', detail: `${reports.length} 份近期報告` };
    }
    function quotaText(payload) {
        const services = payload?.services || [];
        const configured = services.filter(service => service.configured);
        const health = quotaHealth(services);
        if (health.errors) return { tone: 'warning', value: `LLM 健康警示`, detail: `${health.errors} 次額度/來源錯誤` };
        return { tone: 'ok', value: 'LLM 健康正常', detail: `${configured.length} 個服務可用` };
    }
    const quotaHealth = services => ({ errors: (services || []).reduce((sum, service) => sum + quotaErrorCount(service), 0) });
    function rerunText(payload) {
        const reports = payload?.reports || [];
        const needs = reports.filter(reportNeedsRerun);
        if (needs.length) return { tone: 'warning', value: `${needs.length} 份需重跑`, detail: needs[0]?.ticker || '' };
        return { tone: 'ok', value: '無立即重跑', detail: reports.length ? '依近期報告判斷' : '尚無判斷資料' };
    }
    function hasRefreshableDataTrustIssue(report) {
        const trust = report?.data_trust || {};
        const sources = trust.stale_sources;
        return trust.status === 'stale' || (Array.isArray(sources) && sources.filter(Boolean).length > 0)
            || dataTrustReasonCodes(report).some(code => code.startsWith('source_stale:'));
    }
    function reportAction(report) {
        const status = report?.data_trust?.status;
        if (status === 'error') return { title: '暫勿採用', detail: '來源異常，先查看報告' };
        if (reportNeedsRerun(report)) return { title: '建議完整重跑', detail: '結論與資料可能不同步' };
        if (hasRefreshableDataTrustIssue(report)) return { title: '建議刷新資料', detail: '先更新快照再判斷', action: 'refresh-report', label: '刷新資料' };
        if (status === 'partial' && !isSourceNotice(report)) return { title: '資料需留意', detail: '資料已是最新快照，請查看來源審計' };
        return null;
    }
    function watchlistActionDetail(items) {
        const missing = items.filter(item => item?.decision_alert?.reason === 'missing_report').length;
        const rerun = items.filter(item => item?.decision_alert?.reason === 'needs_rerun').length;
        const other = Math.max(0, items.length - missing - rerun);
        const parts = [];
        if (missing) parts.push(`${missing} 檔尚未建立報告`);
        if (rerun) parts.push(`${rerun} 檔資料更新需重跑`);
        if (other) parts.push(`${other} 檔需確認`);
        const samples = items.slice(0, 3).map(item => item.ticker).filter(Boolean).join('、');
        return `${parts.join('，')}${samples ? ` · 例如 ${samples}` : ''}`;
    }
    function operatorActionItems(jobsPayload, quotaPayload, reportPayload, watchlistPayload) {
            const items = [];
            (reportPayload?.reports || []).some(report => {
                const action = reportAction(report);
                if (!action) return false;
                items.push({ action: action.action || 'view-report', label: action.label || '查看報告', title: `${report.ticker || '報告'} ${action.title}`, detail: action.detail, filename: report.filename, ticker: report.ticker, pipeline: report.pipeline_id || 'v1' });
                return items.length >= 2;
        });
        const watchNeeds = (watchlistPayload?.items || []).filter(item => item.enabled !== false && ['high', 'medium'].includes(item.decision_priority));
        if (watchNeeds.length) items.push({ action: 'run-watchlist', label: '建立/更新報告', title: `${watchNeeds.length} 檔 watchlist 待建立/更新報告`, detail: watchlistActionDetail(watchNeeds) });
        const quotaErrors = quotaHealth(quotaPayload?.services).errors;
        if (quotaErrors) items.push({ action: 'open-ops', label: '系統維護', title: 'LLM 健康需留意', detail: `${quotaErrors} 次額度/來源錯誤` });
        const active = Number(jobsPayload?.active_count || 0);
        if (!items.length && active) items.push({ action: 'open-ops', label: '查看任務', title: `${active} 個任務進行中`, detail: '查看進度與近期事件' });
        if (!items.length) items.push({ action: 'open-ops', label: '系統維護', title: '目前沒有急件', detail: '可展開健康摘要查看細節' }); return items.slice(0, 3);
    }
    function create(options) {
        const apiClient = options.apiClient;
        const escapeHtml = options.ui?.escapeHtml || (value => String(value ?? ''));
        const elements = { activeJobs: byId('operator-active-jobs'), dataTrust: byId('operator-data-trust'), apiQuota: byId('operator-api-quota'), rerun: byId('operator-rerun'), actionList: byId('operator-action-list') };
        function renderActions(items) {
            if (!elements.actionList) return;
            elements.actionList.innerHTML = `
                <div class="operator-action-list-header"><strong>今日待處理</strong><span>快速操作</span></div>
                ${items.map(item => `
                    <div class="operator-action-row">
                        <span><strong>${escapeHtml(item.title)}</strong><em>${escapeHtml(item.detail || '')}</em></span>
                        <button class="operator-action-button" type="button" data-operator-action="${escapeHtml(item.action)}" data-filename="${escapeHtml(item.filename || '')}" data-ticker="${escapeHtml(item.ticker || '')}" data-pipeline="${escapeHtml(item.pipeline || 'v1')}">${escapeHtml(item.label)}</button>
                    </div>
                `).join('')}
            `;
        }
        async function load() {
            const [jobs, quotas, reports, watchlist] = await Promise.allSettled([apiClient.fetchActiveJobs({ limit: 3, eventLimit: 20 }), apiClient.fetchApiQuotas(), apiClient.fetchReports({ page: 1, limit: 8, includeVersions: false }), apiClient.fetchWatchlist()]);
            const jobsText = jobs.status === 'fulfilled' ? activeJobText(jobs.value) : { tone: 'warning', value: '讀取失敗', detail: '' };
            const quotasText = quotas.status === 'fulfilled' ? quotaText(quotas.value) : { tone: 'warning', value: '讀取失敗', detail: '' };
            const trust = reports.status === 'fulfilled' ? trustText(reports.value) : { tone: 'warning', value: '讀取失敗', detail: '' };
            const rerun = reports.status === 'fulfilled' ? rerunText(reports.value) : { tone: 'warning', value: '讀取失敗', detail: '' };
            setItem(elements.activeJobs, jobsText.tone, jobsText.value, jobsText.detail);
            setItem(elements.dataTrust, trust.tone, trust.value, trust.detail);
            setItem(elements.apiQuota, quotasText.tone, quotasText.value, quotasText.detail);
            setItem(elements.rerun, rerun.tone, rerun.value, rerun.detail);
            renderActions(operatorActionItems(jobs.status === 'fulfilled' ? jobs.value : null, quotas.status === 'fulfilled' ? quotas.value : null, reports.status === 'fulfilled' ? reports.value : null, watchlist.status === 'fulfilled' ? watchlist.value : null));
        }
        async function handleAction(event) {
            const button = event.target.closest('[data-operator-action]');
            if (!button) return;
            const action = button.dataset.operatorAction;
            const filename = button.dataset.filename;
            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = action === 'run-watchlist' ? '排程中' : '處理中';
            try {
                if (action === 'view-report' && filename && window.openReport) window.openReport(filename, button.dataset.ticker || '報告', button.dataset.pipeline || 'v1');
                else if (action === 'refresh-report' && filename) { await apiClient.refreshReportDataSnapshot(filename); await load(); }
                else if (action === 'run-watchlist') { await apiClient.runWatchlist(); await load(); }
                else byId('home-tab-ops')?.click();
            } catch (err) {
                console.error('Operator action failed', err);
                button.textContent = '失敗';
                setTimeout(() => { button.textContent = originalText; }, 1600);
            } finally {
                button.disabled = false;
                if (button.textContent !== '失敗') button.textContent = originalText;
            }
        }
        if (elements.actionList) elements.actionList.addEventListener('click', handleAction);
        return { load };
    }
    window.StockAgentOperatorSummaryPanel = { create };
})();
