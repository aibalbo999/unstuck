(function () {
    const byId = id => document.getElementById(id);
    const helpers = window.StockAgentOperatorSummaryHelpers;
    function setItem(el, tone, value, detail) { if (!el) return; el.className = `operator-summary-item is-${tone}`; const strong = el.querySelector('strong'), em = el.querySelector('em'); if (strong) strong.textContent = value; if (em) em.textContent = detail || ''; }
    function setShift(els, tone, value, detail) { [...els].forEach(el => { el.className = `${el.dataset.operatorShiftClass || 'operator-shift-summary'} is-${tone}`; const strong = el.querySelector('strong'), em = el.querySelector('em'); if (strong) strong.textContent = value; if (em) em.textContent = detail || ''; }); }
    function create(options) {
        const apiClient = options.apiClient, notify = options.notify || { error: () => {} }, escapeHtml = options.ui?.escapeHtml || (value => String(value ?? ''));
        const dashboardActions = window.StockAgentOperatorDashboardActions;
        let loadVersion = 0;
        const candidateCallbacks = { 'candidate-snapshot': options.onCandidateSnapshot, 'candidate-watchlist': options.onCandidateWatchlist, 'candidate-prepare-analysis': options.onCandidatePrepareAnalysis };
        const elements = { shift: document.querySelectorAll('[data-operator-shift-summary]'), activeJobs: byId('operator-active-jobs'), dataTrust: byId('operator-data-trust'), apiQuota: byId('operator-api-quota'), rerun: byId('operator-rerun'), actionList: byId('operator-action-list') };
        function renderCandidate(item) {
            const candidate = item.candidate || dashboardActions.candidateActionModel(item);
            const actions = [{ type: item.action, label: item.label, primary: true }, { type: 'candidate-watchlist', label: '加入追蹤' }, { type: 'candidate-prepare-analysis', label: '選擇分析模式' }];
            return `<div class="operator-action-row operator-candidate-row"><span><strong>${escapeHtml(item.title || candidate.companyName)}</strong><em>${escapeHtml(candidate.reason || '')}</em></span><div class="operator-candidate-actions">${actions.map(action => `<button class="operator-action-button ${action.primary ? 'is-primary' : ''}" type="button" data-candidate-action="${escapeHtml(action.type)}" data-ticker="${escapeHtml(candidate.ticker || '')}">${escapeHtml(action.label)}</button>`).join('')}</div></div>`;
        }
        function actionCountText(items, queueSummary) {
            const displayed = dashboardActions.actionableActionCount(items), total = Number(queueSummary?.total_actionable), summaryDisplayed = Number(queueSummary?.displayed_count);
            return Number.isInteger(total) && total >= 0 && Number.isInteger(summaryDisplayed) && summaryDisplayed === displayed && total > displayed
                ? `顯示 ${displayed} / 共 ${total} 件快速操作`
                : `${displayed} 件快速操作`;
        }
        function renderActions(items, queueSummary) { if (!elements.actionList) return; elements.actionList.innerHTML = `<div class="operator-action-list-header"><strong>今日待處理</strong><span>${escapeHtml(actionCountText(items, queueSummary))}</span></div>${items.map(item => item.type === 'review_candidate' ? renderCandidate(item) : `<div class="operator-action-row"><span><strong>${escapeHtml(item.title)}</strong><em>${escapeHtml(item.detail || '')}</em></span><button class="operator-action-button ${item.action === 'rerun-all-reports' ? 'is-primary' : ''}" type="button" data-operator-action="${escapeHtml(item.action)}" data-filename="${escapeHtml(item.filename || '')}" data-filenames="${escapeHtml(JSON.stringify(item.filenames || []))}" data-ticker="${escapeHtml(item.ticker || '')}" data-pipeline="${escapeHtml(item.pipeline || 'v1')}" data-target-tab="${escapeHtml(item.targetTab || '')}" data-target-panel="${escapeHtml(item.targetPanel || '')}">${escapeHtml(item.label)}</button></div>`).join('')}`; }
        function parseFilenames(button) { try { const parsed = JSON.parse(button.dataset.filenames || '[]'); return Array.isArray(parsed) ? parsed.filter(Boolean) : []; } catch (err) { return []; } }
        async function rerunReport(filename) { return apiClient.requestJson(`/api/report/${encodeURIComponent(filename)}/rerun?scope=full_report`, { method: 'POST' }); }
        async function load() {
            const requestVersion = ++loadVersion;
            const readCard = (request, targets) => Promise.resolve(request).then(
                value => { if (requestVersion === loadVersion) targets.forEach(([el, format]) => { const item = value ? format(value) : { tone: 'warning', value: '讀取失敗', detail: '' }; setItem(el, item.tone, item.value, item.detail); }); return value; },
                () => { if (requestVersion === loadVersion) targets.forEach(([el]) => setItem(el, 'warning', '讀取失敗', '')); return null; }
            );
            const jobsRequest = readCard(apiClient.fetchActiveJobs({ limit: 3, eventLimit: 20 }), [[elements.activeJobs, helpers.activeJobText]]);
            const quotasRequest = readCard(apiClient.fetchApiQuotas(), [[elements.apiQuota, helpers.quotaText]]);
            const reportsRequest = readCard(apiClient.fetchReports({ page: 1, limit: 20, includeVersions: false }), [[elements.dataTrust, helpers.trustText], [elements.rerun, helpers.rerunText]]);
            const watchlistRequest = Promise.resolve(apiClient.fetchWatchlist()).catch(() => null);
            const dailyDashboardRequest = Promise.allSettled([apiClient.fetchDailyDecisionDashboard()]).then(results => results[0]);
            const [jobsValue, quotasValue, reportsValue, watchlistValue] = await Promise.all([jobsRequest, quotasRequest, reportsRequest, watchlistRequest]);
            if (requestVersion !== loadVersion) return;
            const [jobsText, quotasText, trust, rerun] = [[jobsValue, helpers.activeJobText], [quotasValue, helpers.quotaText], [reportsValue, helpers.trustText], [reportsValue, helpers.rerunText]]
                .map(([value, format]) => value ? format(value) : { tone: 'warning', value: '讀取失敗', detail: '' });
            const fallbackActions = helpers.operatorActionItems(jobsValue, quotasValue, reportsValue, watchlistValue);
            renderActions(fallbackActions, null); setShift(elements.shift, 'warning', '今日工作台彙整中', '報告與基本狀態已更新，待辦總覽仍在讀取');
            const dailyDashboard = await dailyDashboardRequest;
            if (requestVersion !== loadVersion) return;
            const dashboardValue = dailyDashboard.status === 'fulfilled' ? dailyDashboard.value : null;
            const dashboardSummary = dashboardValue ? dashboardActions.dashboardText(dashboardValue) : null, dashboardActionItems = dashboardValue ? dashboardActions.dashboardActionItems(dashboardValue) : [];
            const actions = dashboardActionItems.length ? dashboardActionItems : fallbackActions;
            const warningCount = [jobsText, quotasText, trust, rerun, dashboardSummary].filter(Boolean).filter(item => item.tone === 'warning').length, next = actions[0] || {}, updated = new Date().toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' });
            setShift(elements.shift, warningCount ? 'warning' : 'ok', warningCount ? `${warningCount} 類訊號需注意` : '可正常操作', `${updated} · 下一步：${next.label || '查看狀態'} — ${next.title || '目前沒有急件'}`);
            renderActions(actions, dashboardValue?.decision_queue?.summary);
        }
        async function handleCandidateAction(event) {
            const button = event.target.closest('[data-candidate-action]');
            if (!button) return false;
            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = ({ 'candidate-snapshot': '載入快照中…', 'candidate-watchlist': '加入追蹤中…', 'candidate-prepare-analysis': '準備分析中…' })[button.dataset.candidateAction] || '處理中';
            try {
                const action = button.dataset.candidateAction, ticker = String(button.dataset.ticker || '').trim();
                if (!ticker) {
                    notify.error('候選股票代號遺失，請重新整理後再試。');
                } else if (typeof candidateCallbacks[action] === 'function') {
                    await candidateCallbacks[action](ticker);
                } else {
                    notify.error('候選操作目前無法使用，請重新整理後再試。');
                }
            } catch (err) {
                console.error('Candidate action failed', err);
                notify.error('候選操作失敗，請稍後再試。');
            } finally {
                button.disabled = false;
                button.textContent = originalText;
            }
            return true;
        }
        async function handleAction(event) {
            if (await handleCandidateAction(event)) return;
            const button = event.target.closest('[data-operator-action]');
            if (!button) return;
            const action = button.dataset.operatorAction, filename = button.dataset.filename, filenames = parseFilenames(button), originalText = button.textContent;
            button.disabled = true;
            button.textContent = action === 'run-watchlist' ? '排程中' : '處理中';
            try {
                if (action === 'view-report' && filename && window.openReport) window.openReport(filename, button.dataset.ticker || '報告', button.dataset.pipeline || 'v1');
                else if (action === 'quality-audit-review' && filename) await window.StockAgentOpenHistoricalQualityAudit?.({ query: filename, pipeline: button.dataset.pipeline || 'all' });
                else if (action === 'refresh-report' && filename) { await apiClient.refreshReportDataSnapshot(filename); await load(); }
                else if (action === 'rerun-report' && filename) { await rerunReport(filename); button.textContent = '已排程'; await load(); }
                else if (action === 'rerun-all-reports' && filenames.length) { for (const item of filenames) await rerunReport(item); button.textContent = '已排程'; await load(); }
                else if (action === 'run-watchlist') { await apiClient.runWatchlist(); await load(); }
                else { byId(`home-tab-${button.dataset.targetTab || 'ops'}`)?.click(); setTimeout(() => byId(button.dataset.targetPanel || '')?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }), 0); }
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
