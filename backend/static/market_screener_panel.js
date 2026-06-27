(function () {
    const CATEGORY_LABELS = {
        institutional_accumulation: '外資投信同步',
        technical_heat: '技術/量能異常'
    };
    function categoryLabel(value) { return CATEGORY_LABELS[value] || value || 'Auto-Screener'; }
    function triggerReason(item) {
        const trigger = (item.triggers || []).find(entry => entry.type === 'daily_screener') || {};
        return trigger.reason || item.latest_trigger_event?.message || 'Auto-Screener';
    }
    function create(options) {
        const apiClient = options.apiClient, ui = options.ui || {}, elements = options.elements || {};
        const escapeHtml = ui.escapeHtml || (value => String(value ?? ''));
        let payload = { items: [] }, loaded = false;
        function setSummary(text) { if (elements.summaryEl) elements.summaryEl.textContent = text; }
        function renderBoard(items) {
            const enabled = items.filter(item => item.enabled !== false);
            const modeD = enabled.filter(item => (item.pipeline || '') === 'v4').length;
            return `<div class="market-screener-grid">
                <span><strong>${escapeHtml(String(enabled.length))}</strong><em>候選股</em></span>
                <span><strong>${escapeHtml(String(modeD))}</strong><em>Mode D</em></span>
                <span><strong>${escapeHtml(String(payload.updated_at || '-').slice(0, 10))}</strong><em>更新</em></span>
            </div>`;
        }
        function render() {
            const items = payload.items || [];
            setSummary(items.length ? `Auto-Screener ${items.length} 檔` : '尚無掃描候選');
            if (elements.boardEl) elements.boardEl.innerHTML = renderBoard(items);
            if (!elements.listEl) return;
            elements.listEl.innerHTML = items.length ? items.map(item => {
                const tags = (item.tags || []).filter(tag => tag !== 'Auto-Screener').map(categoryLabel).join('、');
                return `<span class="provider-sla-chip market-screener-chip ${item.enabled === false ? 'is-warning' : 'is-ok'}">
                    <strong>${escapeHtml(item.ticker)}</strong>
                    <em>${escapeHtml((item.pipeline || 'v4').toUpperCase())}</em>
                    <span>${escapeHtml(tags || 'Auto-Screener')}</span>
                    <span>${escapeHtml(triggerReason(item))}</span>
                </span>`;
            }).join('') : '<span class="provider-sla-chip is-warning">尚無 Auto-Screener 候選</span>';
        }
        async function load() {
            try {
                if (elements.refreshBtn) elements.refreshBtn.disabled = true;
                payload = await apiClient.fetchMarketScreener();
                render();
            } catch (err) {
                console.error('Failed to load market screener', err);
                setSummary(`市場掃描讀取失敗：${err.message || err}`);
            } finally {
                if (elements.refreshBtn) elements.refreshBtn.disabled = false;
            }
        }
        async function run() {
            try {
                if (elements.runBtn) elements.runBtn.disabled = true;
                const result = await apiClient.runMarketScreener();
                await load();
                if (result.scan_success === false) {
                    setSummary(result.message || '市場掃描暫無可用資料');
                } else {
                    setSummary(`已匯入 ${result.imported_count || 0} 檔`);
                }
            } catch (err) {
                console.error('Failed to run market screener', err);
                setSummary(`市場掃描失敗：${err.message || err}`);
            } finally {
                if (elements.runBtn) elements.runBtn.disabled = false;
            }
        }
        function bindEvents() {
            if (elements.refreshBtn) elements.refreshBtn.addEventListener('click', load);
            if (elements.runBtn) elements.runBtn.addEventListener('click', run);
        }
        function loadOnce() {
            if (loaded) return Promise.resolve();
            loaded = true;
            return load();
        }
        return { bindEvents, load, loadOnce };
    }
    window.StockAgentMarketScreenerPanel = { create };
})();
