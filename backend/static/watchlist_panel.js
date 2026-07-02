(function () {
    function slotLabel(slots, schedules) { return (slots || []).map(slot => schedules?.[slot]?.label || slot).join('、') || '未排程'; }

    function itemPayload(elements) {
        return {
            ticker: elements.tickerInput?.value || '',
            pipeline: elements.pipelineSelect?.value || 'v1',
            enabled: Boolean(elements.enabledInput?.checked),
            schedule_slots: [
                elements.preMarketInput?.checked ? 'pre_market' : '',
                elements.postMarketInput?.checked ? 'post_market' : ''
            ].filter(Boolean),
            triggers: window.StockAgentWatchlistTriggerForm?.payload() || []
        };
    }

    function resetForm(elements) {
        if (elements.tickerInput) elements.tickerInput.value = '';
        if (elements.pipelineSelect) elements.pipelineSelect.value = 'v1';
        if (elements.enabledInput) elements.enabledInput.checked = true;
        if (elements.preMarketInput) elements.preMarketInput.checked = true;
        if (elements.postMarketInput) elements.postMarketInput.checked = false;
        window.StockAgentWatchlistTriggerForm?.reset();
    }

    function priorityLabel(item) { return item.decision_priority === 'high' ? '需重跑' : (item.decision_priority === 'medium' ? '待分析' : (item.decision_priority === 'low' ? '停用' : '有效')); }

    function watchlistDailyBoard(items, escapeHtml) {
        const enabled = items.filter(item => item.enabled !== false);
        const needs = enabled.filter(item => ['high', 'medium'].includes(item.decision_priority));
        const next = needs.slice(0, 3).map(item => item.ticker).join('、') || '無急件';
        return `
            <div class="watchlist-daily-board">
                <strong>今日工作台</strong>
                <span>需處理 ${escapeHtml(String(needs.length))} 檔</span>
                <em>${escapeHtml(next)}</em>
            </div>
        `;
    }
    function renderSuggestions(elements, payload, escapeHtml) { if (elements.suggestionList) elements.suggestionList.innerHTML = (payload.items || []).map(item => `<option value="${escapeHtml(item.ticker)}">${escapeHtml(item.name || item.market || '')}</option>`).join(''); }

    function create(options) {
        const apiClient = options.apiClient;
        const elements = options.elements || {};
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        const onRunQueued = options.onRunQueued || (() => {});
        let payload = { items: [], schedules: {} };
        let suggestionTimer = null;

        function setSummary(message) { if (elements.summaryEl) elements.summaryEl.textContent = message; }

        function renderList() {
            const items = payload.items || [];
            if (!elements.listEl) return;
            setSummary(items.length ? `${items.length} 檔追蹤中` : '尚未建立追蹤清單');
            elements.listEl.innerHTML = watchlistDailyBoard(items, escapeHtml) + (items.length
                ? items.map(item => {
                    const disabled = item.enabled ? '' : ' · 停用';
                    const priorityClass = item.decision_priority === 'high' ? 'is-critical' : (item.decision_priority === 'medium' ? 'is-warning' : '');
                    return `
                        <span class="provider-sla-chip watchlist-chip ${priorityClass || (item.enabled ? 'is-ok' : 'is-warning')}">
                            <strong>${escapeHtml(item.ticker)}</strong>
                            <em>${escapeHtml((item.pipeline || 'v1').toUpperCase())}${disabled}</em>
                            <span>${escapeHtml(slotLabel(item.schedule_slots, payload.schedules))}</span>
                            <span>${escapeHtml(priorityLabel(item))}</span>
                            ${window.StockAgentWatchlistTriggerForm?.renderItem({ ...item, latest_trigger_event: item.latest_trigger_event }, escapeHtml) || ''}
                            <button class="watchlist-delete-button" type="button" data-watchlist-delete="${escapeHtml(item.ticker)}" data-watchlist-pipeline="${escapeHtml(item.pipeline || 'v1')}" aria-label="刪除 ${escapeHtml(item.ticker)}">
                                刪除
                            </button>
                        </span>
                    `;
                }).join('')
                : '<span class="provider-sla-chip is-warning">尚無 watchlist</span>');
        }

        async function load() {
            if (!elements.listEl) return;
            try {
                if (elements.refreshBtn) elements.refreshBtn.disabled = true;
                payload = await apiClient.fetchWatchlist();
                renderList();
            } catch (err) {
                console.error('Failed to load watchlist', err);
                setSummary('watchlist 讀取失敗');
                elements.listEl.innerHTML = '<span class="provider-sla-chip is-warning">請稍後重試</span>';
            } finally {
                if (elements.refreshBtn) elements.refreshBtn.disabled = false;
            }
        }

        async function save() {
            const item = itemPayload(elements);
            if (!String(item.ticker || '').trim()) {
                setSummary('請輸入股票代號');
                return;
            }
            if (!item.schedule_slots.length) {
                setSummary('請選擇盤前或盤後');
                return;
            }
            try {
                if (elements.saveBtn) elements.saveBtn.disabled = true;
                payload = await apiClient.saveWatchlistItem(item);
                resetForm(elements);
                renderList();
            } catch (err) {
                console.error('Failed to save watchlist item', err);
                setSummary(`儲存失敗：${err.message || err}`);
            } finally {
                if (elements.saveBtn) elements.saveBtn.disabled = false;
            }
        }
        async function loadSuggestions() {
            const query = elements.tickerInput?.value || ''; if (!apiClient.fetchSymbolSuggestions || !String(query).trim()) return;
            try { renderSuggestions(elements, await apiClient.fetchSymbolSuggestions(query), escapeHtml); } catch (err) { console.error('Failed to load symbol suggestions', err); }
        }
        async function importItems() {
            const text = elements.importText?.value || '';
            if (!String(text).trim()) { setSummary('請貼上股票清單'); return; }
            try {
                if (elements.importBtn) elements.importBtn.disabled = true;
                const result = await apiClient.importWatchlistText(text); payload = result.watchlist || payload;
                if (elements.importText) elements.importText.value = '';
                setSummary(`已匯入 ${result.imported_count || 0} 檔`); renderList();
            } catch (err) {
                console.error('Failed to import watchlist', err);
                setSummary(`匯入失敗：${err.message || err}`);
            } finally {
                if (elements.importBtn) elements.importBtn.disabled = false;
            }
        }

        async function remove(ticker, pipeline) {
            try { await apiClient.deleteWatchlistItem(ticker, pipeline); await load(); }
            catch (err) { console.error('Failed to delete watchlist item', err); setSummary(`刪除失敗：${err.message || err}`); }
        }

        async function runAll() {
            try {
                if (elements.runBtn) elements.runBtn.disabled = true;
                const result = await apiClient.runWatchlist();
                const queued = result.queued || [];
                const skipped = result.skipped || [];
                setSummary(`已排入 ${queued.length} 檔，略過 ${skipped.length} 檔`);
                onRunQueued(result);
            } catch (err) {
                console.error('Failed to run watchlist', err);
                setSummary(`批次分析失敗：${err.message || err}`);
            } finally {
                if (elements.runBtn) elements.runBtn.disabled = false;
            }
        }

        function bindEvents() {
            if (elements.saveBtn) elements.saveBtn.addEventListener('click', save);
            if (elements.importBtn) elements.importBtn.addEventListener('click', importItems);
            if (elements.refreshBtn) elements.refreshBtn.addEventListener('click', load);
            if (elements.runBtn) elements.runBtn.addEventListener('click', runAll);
            if (elements.tickerInput) {
                elements.tickerInput.addEventListener('keypress', event => { if (event.key === 'Enter') save(); });
                elements.tickerInput.addEventListener('input', () => { window.clearTimeout(suggestionTimer); suggestionTimer = window.setTimeout(loadSuggestions, 180); });
            }
            if (elements.listEl) {
                elements.listEl.addEventListener('click', event => {
                    const button = event.target.closest('[data-watchlist-delete]');
                    if (!button) return;
                    remove(button.dataset.watchlistDelete, button.dataset.watchlistPipeline || 'all');
                });
            }
        }

        resetForm(elements);
        return { bindEvents, load };
    }

    window.StockAgentWatchlistPanel = { create };
})();
