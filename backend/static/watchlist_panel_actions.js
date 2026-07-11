(function () {
    const { itemPayload, renderSuggestions, resetForm } = window.StockAgentWatchlistPanelHelpers;

    function create(options) {
        const apiClient = options.apiClient, elements = options.elements || {};
        const getPayload = options.getPayload || (() => ({ items: [], schedules: {} }));
        const setPayload = options.setPayload || (() => {});
        const setDailyPayload = options.setDailyPayload || (() => {});
        const setSummary = options.setSummary || (() => {});
        const renderList = options.renderList || (() => {});
        const onRunQueued = options.onRunQueued || (() => {});
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));

        async function load() {
            try {
                if (elements.refreshBtn) elements.refreshBtn.disabled = true;
                const [watchlistResult, dailyResult] = await Promise.allSettled([
                    apiClient.fetchWatchlist(),
                    apiClient.fetchDailyDecisionDashboard ? apiClient.fetchDailyDecisionDashboard() : Promise.resolve(null)
                ]);
                if (watchlistResult.status !== 'fulfilled') throw watchlistResult.reason;
                setPayload(watchlistResult.value);
                setDailyPayload(dailyResult.status === 'fulfilled' ? dailyResult.value : null);
                renderList();
            } catch (err) {
                console.error('Failed to load watchlist', err);
                setSummary('追蹤清單讀取失敗');
                if (elements.listEl) elements.listEl.innerHTML = '<span class="provider-sla-chip is-warning">請稍後重試</span>';
            } finally {
                if (elements.refreshBtn) elements.refreshBtn.disabled = false;
            }
        }

        async function save() {
            const item = itemPayload(elements);
            if (!String(item.ticker || '').trim()) { setSummary('請輸入股票代號'); return; }
            if (!item.schedule_slots.length) { setSummary('請選擇盤前或盤後'); return; }
            try {
                if (elements.saveBtn) elements.saveBtn.disabled = true;
                setPayload(await apiClient.saveWatchlistItem(item));
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
            const query = elements.tickerInput?.value || '';
            if (!apiClient.fetchSymbolSuggestions || !String(query).trim()) return;
            try { renderSuggestions(elements, await apiClient.fetchSymbolSuggestions(query), escapeHtml); }
            catch (err) { console.error('Failed to load symbol suggestions', err); }
        }

        async function importItems() {
            const text = elements.importText?.value || '';
            if (!String(text).trim()) { setSummary('請貼上股票清單'); return; }
            try {
                if (elements.importBtn) elements.importBtn.disabled = true;
                const result = await apiClient.importWatchlistText(text);
                setPayload(result.watchlist || getPayload());
                if (elements.importText) elements.importText.value = '';
                setSummary(`已匯入 ${result.imported_count || 0} 檔`);
                renderList();
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
                const queued = result.queued || [], skipped = result.skipped || [];
                setSummary(`已排入 ${queued.length} 檔，略過 ${skipped.length} 檔`);
                onRunQueued(result);
            } catch (err) {
                console.error('Failed to run watchlist', err);
                setSummary(`追蹤清單分析失敗：${err.message || err}`);
            } finally {
                if (elements.runBtn) elements.runBtn.disabled = false;
            }
        }

        return { importItems, load, loadSuggestions, remove, runAll, save };
    }

    window.StockAgentWatchlistPanelActions = { create };
})();
