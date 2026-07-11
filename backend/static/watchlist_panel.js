(function () {
    const { priorityLabel, reportButton, resetForm, slotLabel, watchlistDailyBoard } = window.StockAgentWatchlistPanelHelpers;

    function create(options) {
        const apiClient = options.apiClient, elements = options.elements || {}, ui = options.ui || window.StockAgentUi || {};
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        const onOpenSnapshot = options.onOpenSnapshot || (() => {}), onOpenReport = options.onOpenReport || (() => {});
        let payload = { items: [], schedules: {} };
        let dailyPayload = null;
        let suggestionTimer = null;

        function setSummary(message) { if (elements.summaryEl) elements.summaryEl.textContent = message; }
        function modeLabel(pipeline) { return typeof ui.pipelineModeLabel === 'function' ? ui.pipelineModeLabel(pipeline || 'v1') : String(pipeline || 'v1'); }
        function setPayload(nextPayload) { payload = nextPayload || { items: [], schedules: {} }; }

        function renderList() {
            const items = payload.items || [];
            if (!elements.listEl) return;
            setSummary(items.length ? `${items.length} 檔追蹤中` : '尚未建立追蹤清單');
            elements.listEl.innerHTML = watchlistDailyBoard(items, dailyPayload, escapeHtml) + (items.length
                ? items.map(item => {
                    const disabled = item.enabled ? '' : ' · 停用';
                    const priorityClass = item.decision_priority === 'high' ? 'is-critical' : (item.decision_priority === 'medium' ? 'is-warning' : '');
                    return `
                        <span class="provider-sla-chip watchlist-chip ${priorityClass || (item.enabled ? 'is-ok' : 'is-warning')}">
                            <button class="watchlist-ticker-button" type="button" data-watchlist-snapshot="${escapeHtml(item.ticker)}">${escapeHtml(item.ticker)}</button>
                            <em>${escapeHtml(modeLabel(item.pipeline))}${disabled}</em>
                            <span>${escapeHtml(slotLabel(item.schedule_slots, payload.schedules))}</span>
                            <span>${escapeHtml(priorityLabel(item))}</span>
                            ${window.StockAgentWatchlistTriggerForm?.renderItem({ ...item, latest_trigger_event: item.latest_trigger_event }, escapeHtml) || ''}
                            ${reportButton(item, escapeHtml)}
                            <button class="watchlist-delete-button" type="button" data-watchlist-delete="${escapeHtml(item.ticker)}" data-watchlist-pipeline="${escapeHtml(item.pipeline || 'v1')}" aria-label="刪除 ${escapeHtml(item.ticker)}">刪除</button>
                        </span>
                    `;
                }).join('')
                : '<span class="provider-sla-chip is-warning">尚無追蹤項目</span>');
        }

        const actions = window.StockAgentWatchlistPanelActions.create({
            apiClient,
            elements,
            escapeHtml,
            getPayload: () => payload,
            onRunQueued: options.onRunQueued || (() => {}),
            renderList,
            setDailyPayload: nextPayload => { dailyPayload = nextPayload; },
            setPayload,
            setSummary
        });

        function bindEvents() {
            if (elements.saveBtn) elements.saveBtn.addEventListener('click', actions.save);
            if (elements.importBtn) elements.importBtn.addEventListener('click', actions.importItems);
            if (elements.refreshBtn) elements.refreshBtn.addEventListener('click', actions.load);
            if (elements.runBtn) elements.runBtn.addEventListener('click', actions.runAll);
            if (elements.tickerInput) {
                elements.tickerInput.addEventListener('keypress', event => { if (event.key === 'Enter') actions.save(); });
                elements.tickerInput.addEventListener('input', () => { window.clearTimeout(suggestionTimer); suggestionTimer = window.setTimeout(actions.loadSuggestions, 180); });
            }
            if (elements.listEl) {
                elements.listEl.addEventListener('click', event => {
                    const deleteButton = event.target.closest('[data-watchlist-delete]');
                    if (deleteButton) { actions.remove(deleteButton.dataset.watchlistDelete, deleteButton.dataset.watchlistPipeline || 'all'); return; }
                    const snapshotButton = event.target.closest('[data-watchlist-snapshot]');
                    if (snapshotButton) { onOpenSnapshot(snapshotButton.dataset.watchlistSnapshot); return; }
                    const button = event.target.closest('[data-watchlist-report]');
                    if (button) onOpenReport(button.dataset.watchlistReport, button.dataset.watchlistReportTicker, button.dataset.watchlistReportPipeline || 'v1');
                });
            }
        }

        resetForm(elements);
        return { bindEvents, load: actions.load };
    }

    window.StockAgentWatchlistPanel = { create };
})();
