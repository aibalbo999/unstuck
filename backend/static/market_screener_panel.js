(function () {
    const CATEGORY_LABELS = {
        institutional_accumulation: '外資投信同步',
        technical_heat: '股價大漲跌/成交量暴增'
    };
    const PIPELINE_OPTIONS = [
        { value: 'v1', label: '模式 A', shortLabel: '學術深度派' },
        { value: 'v2', label: '模式 B', shortLabel: '實戰交易派' },
        { value: 'v3', label: '模式 C', shortLabel: '逆勢泡沫狙擊' },
        { value: 'v4', label: '模式 D', shortLabel: '短線波段派' }
    ];
    function categoryLabel(value) { return CATEGORY_LABELS[value] || value || 'Auto-Screener'; }
    function selectorEscape(value) {
        return String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    }
    function dailyTrigger(item) {
        return (item.triggers || []).find(entry => entry.type === 'daily_screener') || {};
    }
    function triggerReason(item) {
        const trigger = dailyTrigger(item);
        return trigger.reason || item.latest_trigger_event?.message || 'Auto-Screener';
    }
    function companyName(item) {
        const trigger = dailyTrigger(item);
        return item.company_name || trigger.company_name || trigger.metrics?.company_name || '';
    }
    function create(options) {
        const apiClient = options.apiClient, ui = options.ui || {}, elements = options.elements || {};
        const escapeHtml = ui.escapeHtml || (value => String(value ?? ''));
        let payload = { items: [] }, loaded = false, selectedTicker = '', selectedModes = {};
        function setSummary(text) { if (elements.summaryEl) elements.summaryEl.textContent = text; }
        function providersLabel() {
            return (payload.providers || payload.data_sources || []).join('、') || '-';
        }
        function selectedModeValues(ticker, fallbackPipeline) {
            return selectedModes[ticker] || [fallbackPipeline || 'v4'];
        }
        function renderBoard(items) {
            const enabled = items.filter(item => item.enabled !== false);
            const modeD = enabled.filter(item => (item.pipeline || '') === 'v4').length;
            return `<div class="market-screener-grid">
                <span><strong>${escapeHtml(String(enabled.length))}</strong><em>候選股</em></span>
                <span><strong>${escapeHtml(String(modeD))}</strong><em>Mode D</em></span>
                <span><strong>${escapeHtml(providersLabel())}</strong><em>資料源</em></span>
                <span><strong>${escapeHtml(String(payload.updated_at || '-').slice(0, 10))}</strong><em>更新</em></span>
            </div>`;
        }
        function renderModePicker(item) {
            const ticker = String(item.ticker || '').toUpperCase();
            if (ticker !== selectedTicker) return '';
            const values = selectedModeValues(ticker, item.pipeline);
            return `<div class="market-screener-mode-picker" data-screener-mode-picker="${escapeHtml(ticker)}">
                <div class="market-screener-mode-options">
                    ${PIPELINE_OPTIONS.map(option => `<label class="market-screener-mode-option">
                        <input type="checkbox" data-screener-mode="${escapeHtml(ticker)}" value="${escapeHtml(option.value)}" ${values.includes(option.value) ? 'checked' : ''} />
                        <span>${escapeHtml(option.label)}</span>
                        <em>${escapeHtml(option.shortLabel)}</em>
                    </label>`).join('')}
                </div>
                <button class="maintenance-button market-screener-analyze-button" type="button" data-screener-run-modes="${escapeHtml(ticker)}">
                    <span>排入分析</span>
                </button>
            </div>`;
        }
        function render() {
            const items = payload.items || [];
            setSummary(items.length ? `Auto-Screener ${items.length} 檔` : '尚無掃描候選');
            if (elements.boardEl) elements.boardEl.innerHTML = renderBoard(items);
            if (!elements.listEl) return;
            elements.listEl.innerHTML = items.length ? items.map(item => {
                const tags = (item.tags || []).filter(tag => tag !== 'Auto-Screener').map(categoryLabel).join('、');
                const ticker = String(item.ticker || '').toUpperCase();
                const company = companyName(item);
                return `<div class="market-screener-item">
                    <button class="provider-sla-chip market-screener-chip ${item.enabled === false ? 'is-warning' : 'is-ok'} ${ticker === selectedTicker ? 'is-selected' : ''}" type="button" data-screener-select="${escapeHtml(ticker)}" aria-expanded="${ticker === selectedTicker ? 'true' : 'false'}">
                        <strong>${escapeHtml(ticker)}${company ? `<small>${escapeHtml(company)}</small>` : ''}</strong>
                        <em>${escapeHtml((item.pipeline || 'v4').toUpperCase())}</em>
                        <span>${escapeHtml(tags || 'Auto-Screener')}</span>
                        <span>${escapeHtml(triggerReason(item))}</span>
                    </button>
                    ${renderModePicker(item)}
                </div>`;
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
                payload = Object.assign({}, payload, {
                    providers: result.providers || payload.providers,
                    data_sources: result.data_sources || payload.data_sources
                });
                render();
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
        async function runSelectedModes(ticker) {
            const item = (payload.items || []).find(entry => String(entry.ticker || '').toUpperCase() === ticker);
            const modes = selectedModeValues(ticker, item?.pipeline).filter(Boolean);
            if (!modes.length) {
                setSummary('請至少選擇一個模式');
                return;
            }
            const button = elements.listEl?.querySelector(`[data-screener-run-modes="${selectorEscape(ticker)}"]`);
            try {
                if (button) button.disabled = true;
                const result = await apiClient.runWatchlist(modes.map(pipeline => ({ ticker, pipeline })));
                const queued = result.queued || [];
                const skipped = result.skipped || [];
                setSummary(`已排入 ${queued.length} 個分析任務，略過 ${skipped.length} 個`);
            } catch (err) {
                console.error('Failed to run selected screener modes', err);
                setSummary(`排入分析失敗：${err.message || err}`);
            } finally {
                if (button) button.disabled = false;
            }
        }
        function bindEvents() {
            if (elements.refreshBtn) elements.refreshBtn.addEventListener('click', load);
            if (elements.runBtn) elements.runBtn.addEventListener('click', run);
            if (elements.listEl) {
                elements.listEl.addEventListener('click', event => {
                    const runButton = event.target.closest('[data-screener-run-modes]');
                    if (runButton) {
                        runSelectedModes(String(runButton.dataset.screenerRunModes || '').toUpperCase());
                        return;
                    }
                    const selectButton = event.target.closest('[data-screener-select]');
                    if (!selectButton) return;
                    const ticker = String(selectButton.dataset.screenerSelect || '').toUpperCase();
                    selectedTicker = selectedTicker === ticker ? '' : ticker;
                    render();
                });
                elements.listEl.addEventListener('change', event => {
                    const input = event.target.closest('[data-screener-mode]');
                    if (!input) return;
                    const ticker = String(input.dataset.screenerMode || '').toUpperCase();
                    selectedModes[ticker] = Array.from(elements.listEl.querySelectorAll(`[data-screener-mode="${selectorEscape(ticker)}"]:checked`))
                        .map(item => item.value)
                        .filter(Boolean);
                });
            }
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
