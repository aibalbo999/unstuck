(function () {
    const CATEGORY_LABELS = { institutional_accumulation: '外資投信同步', technical_heat: '股價大漲跌/成交量暴增' };
    const PIPELINE_OPTIONS = [
        { value: 'v1', label: '模式 A', shortLabel: '學術深度派' }, { value: 'v2', label: '模式 B', shortLabel: '實戰交易派' },
        { value: 'v3', label: '模式 C', shortLabel: '逆勢泡沫狙擊' }, { value: 'v4', label: '模式 D', shortLabel: '短線波段派' }
    ];
    const COLUMNS = [
        ['ticker', '股票'], ['score', '分數'], ['bias_pct', '乖離'], ['rsi_14', 'RSI'],
        ['revenue_growth_yoy_pct', '營收 YoY'], ['total_net_buy_shares', '法人買超'], ['watchlist', '狀態']
    ];
    function create(options) { return new MarketScreenerPanel(options); }
    function categoryLabel(value) { return CATEGORY_LABELS[value] || value || 'Auto-Screener'; }
    function selectorEscape(value) { return String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"'); }
    function dailyTrigger(item) { return (item.triggers || []).find(entry => entry.type === 'daily_screener') || {}; }
    function triggerReason(item) { const trigger = dailyTrigger(item); return item.reason || trigger.reason || item.latest_trigger_event?.message || 'Auto-Screener'; }
    function companyName(item) { const trigger = dailyTrigger(item); return item.company_name || trigger.company_name || trigger.metrics?.company_name || ''; }
    function metric(item, key) { const metrics = item.metrics || dailyTrigger(item).metrics || {}; return key === 'score' ? item.score : metrics[key]; }
    function numberValue(value) { const n = Number(String(value ?? '').replace(/,/g, '')); return Number.isFinite(n) ? n : null; }
    function compactNumber(value) { const n = numberValue(value); return n === null ? '-' : (Math.abs(n) >= 10000 ? `${Math.round(n / 1000).toLocaleString()}張` : n.toLocaleString()); }
    function formatSignedMetric(value, suffix = '%') {
        const n = numberValue(value);
        if (n === null) return '<span class="metric-muted">-</span>';
        const cls = n > 0 ? 'metric-positive' : (n < 0 ? 'metric-negative' : 'metric-muted');
        return `<span class="${cls}">${n > 0 ? '+' : ''}${n.toFixed(Math.abs(n) >= 10 ? 1 : 2)}${suffix}</span>`;
    }
    class MarketScreenerPanel {
        constructor(options) {
            this.apiClient = options.apiClient; this.ui = options.ui || {}; this.elements = options.elements || {};
            this.escapeHtml = this.ui.escapeHtml || (value => String(value ?? ''));
            this.payload = { items: [] }; this.loaded = false; this.loading = false; this.selectedTicker = ''; this.selectedModes = {};
            this.sort = { key: 'score', direction: 'desc' }; this.filters = { category: '', minScore: 0, rsiMax: 90 };
        }
        setSummary(text) { if (this.elements.summaryEl) this.elements.summaryEl.textContent = text; }
        setLoading(value) { this.loading = Boolean(value); this.render(); }
        providersLabel() { return (this.payload.providers || this.payload.data_sources || []).join('、') || '-'; }
        selectedModeValues(ticker, fallbackPipeline) { return this.selectedModes[ticker] || [fallbackPipeline || 'v4']; }
        params() {
            const params = { limit: 50, offset: 0, sort_by: this.sort.key, sort_direction: this.sort.direction };
            if (this.filters.category) params.category = this.filters.category;
            if (this.filters.minScore > 0) params.min_score = this.filters.minScore;
            if (this.filters.rsiMax < 90) params.technical_rsi_max = this.filters.rsiMax;
            return params;
        }
        sortedItems() {
            const dir = this.sort.direction === 'asc' ? 1 : -1;
            return [...(this.payload.items || [])].sort((a, b) => {
                const av = this.sort.key === 'ticker' ? String(a.ticker || '') : numberValue(metric(a, this.sort.key));
                const bv = this.sort.key === 'ticker' ? String(b.ticker || '') : numberValue(metric(b, this.sort.key));
                if (typeof av === 'string' || typeof bv === 'string') return String(av).localeCompare(String(bv)) * dir;
                return ((av ?? -Infinity) - (bv ?? -Infinity)) * dir;
            });
        }
        renderBoard(items) {
            const e = this.escapeHtml, enabled = items.filter(item => item.enabled !== false), modeD = enabled.filter(item => (item.pipeline || '') === 'v4').length;
            const updated = String(this.payload.last_updated_time || this.payload.updated_at || '-').slice(0, 16).replace('T', ' ');
            return `<div class="market-screener-grid"><span><strong>${e(String(enabled.length))}</strong><em>候選股</em></span><span><strong>${e(String(modeD))}</strong><em>Mode D</em></span><span><strong>${e(this.providersLabel())}</strong><em>資料源</em></span><span><strong>${e(updated)}</strong><em>更新</em></span></div>${this.renderControls()}`;
        }
        renderControls() {
            const e = this.escapeHtml;
            return `<div class="market-screener-controls"><label>分類<select class="market-screener-filter-select" data-screener-filter="category"><option value="">全部標籤</option>${Object.keys(CATEGORY_LABELS).map(key => `<option value="${e(key)}" ${this.filters.category === key ? 'selected' : ''}>${e(categoryLabel(key))}</option>`).join('')}</select></label><label>最低分數 <output>${e(String(this.filters.minScore))}</output><input class="market-screener-range" type="range" min="0" max="100" step="5" value="${e(String(this.filters.minScore))}" data-screener-filter="minScore" /></label><label>RSI 上限 <output>${e(String(this.filters.rsiMax))}</output><input class="market-screener-range" type="range" min="40" max="90" step="5" value="${e(String(this.filters.rsiMax))}" data-screener-filter="rsiMax" /></label></div>`;
        }
        renderModePicker(item) {
            const e = this.escapeHtml, ticker = String(item.ticker || '').toUpperCase();
            if (ticker !== this.selectedTicker) return '';
            const values = this.selectedModeValues(ticker, item.pipeline);
            return `<tr class="market-screener-detail-row"><td colspan="7"><div class="market-screener-mode-picker" data-screener-mode-picker="${e(ticker)}"><div class="market-screener-mode-options">${PIPELINE_OPTIONS.map(option => `<label class="market-screener-mode-option"><input type="checkbox" data-screener-mode="${e(ticker)}" value="${e(option.value)}" ${values.includes(option.value) ? 'checked' : ''} /><span>${e(option.label)}</span><em>${e(option.shortLabel)}</em></label>`).join('')}</div><button class="maintenance-button market-screener-analyze-button" type="button" data-screener-run-modes="${e(ticker)}"><span>排入分析</span></button></div></td></tr>`;
        }
        renderTable(items) {
            const e = this.escapeHtml;
            if (this.loading) return '<div class="market-screener-skeleton"><span></span><span></span><span></span></div>';
            if (!items.length) return '<div class="market-screener-empty">查無資料，請放寬條件</div>';
            const head = COLUMNS.map(([key, label]) => `<th><button class="market-screener-sort-button" type="button" data-screener-sort="${e(key)}">${e(label)}${this.sort.key === key ? (this.sort.direction === 'asc' ? ' ↑' : ' ↓') : ''}</button></th>`).join('');
            const rows = items.map(item => {
                const ticker = String(item.ticker || '').toUpperCase(), company = companyName(item), tags = (item.tags || item.categories || []).filter(tag => tag !== 'Auto-Screener').map(categoryLabel).join('、');
                const status = item.watchlist_status || {}, watch = status.in_watchlist || item.is_in_watchlist ? '已在觀察' : '可加入';
                return `<tr><td><button class="market-screener-chip market-screener-row-button ${ticker === this.selectedTicker ? 'is-selected' : ''}" type="button" data-screener-select="${e(ticker)}" aria-expanded="${ticker === this.selectedTicker ? 'true' : 'false'}"><strong>${e(ticker)}</strong><small>${e(company || '-')}</small></button></td><td>${e(String(item.score ?? '-'))}</td><td>${formatSignedMetric(metric(item, 'bias_pct'))}</td><td>${e(String(metric(item, 'rsi_14') ?? '-'))}</td><td>${formatSignedMetric(metric(item, 'revenue_growth_yoy_pct'))}</td><td>${e(compactNumber(metric(item, 'total_net_buy_shares')))}</td><td><span class="market-screener-tag">${e(tags || 'Auto-Screener')}</span><small>${e(watch)}</small><em>${e(triggerReason(item))}</em></td></tr>${this.renderModePicker(item)}`;
            }).join('');
            return `<div class="market-screener-table-shell"><table class="market-screener-table"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
        }
        render() {
            const items = this.sortedItems();
            this.setSummary(this.loading ? '市場掃描載入中' : (items.length ? `Auto-Screener ${items.length} 檔` : '尚無掃描候選'));
            if (this.elements.boardEl) this.elements.boardEl.innerHTML = this.renderBoard(items);
            if (this.elements.listEl) this.elements.listEl.innerHTML = this.renderTable(items);
        }
        async load() {
            try {
                this.setLoading(true); if (this.elements.refreshBtn) this.elements.refreshBtn.disabled = true;
                this.payload = await this.apiClient.fetchMarketScreener(this.params()); this.render();
            } catch (err) {
                console.error('Failed to load market screener', err); this.setSummary(`市場掃描讀取失敗：${err.message || err}`);
            } finally {
                this.loading = false; if (this.elements.refreshBtn) this.elements.refreshBtn.disabled = false; this.render();
            }
        }
        async run() {
            try {
                if (this.elements.runBtn) this.elements.runBtn.disabled = true;
                const result = await this.apiClient.runMarketScreener(); await this.load();
                this.payload = Object.assign({}, this.payload, { providers: result.providers || this.payload.providers, data_sources: result.data_sources || this.payload.data_sources });
                this.setSummary(result.scan_success === false ? (result.message || '市場掃描暫無可用資料') : `已匯入 ${result.imported_count || 0} 檔`);
            } catch (err) {
                console.error('Failed to run market screener', err); this.setSummary(`市場掃描失敗：${err.message || err}`);
            } finally { if (this.elements.runBtn) this.elements.runBtn.disabled = false; }
        }
        async runSelectedModes(ticker) {
            const item = (this.payload.items || []).find(entry => String(entry.ticker || '').toUpperCase() === ticker), modes = this.selectedModeValues(ticker, item?.pipeline).filter(Boolean);
            if (!modes.length) { this.setSummary('請至少選擇一個模式'); return; }
            const button = this.elements.listEl?.querySelector(`[data-screener-run-modes="${selectorEscape(ticker)}"]`);
            try { if (button) button.disabled = true; const result = await this.apiClient.runWatchlist(modes.map(pipeline => ({ ticker, pipeline }))); this.setSummary(`已排入 ${(result.queued || []).length} 個分析任務，略過 ${(result.skipped || []).length} 個`); }
            catch (err) { console.error('Failed to run selected screener modes', err); this.setSummary(`排入分析失敗：${err.message || err}`); }
            finally { if (button) button.disabled = false; }
        }
        bindEvents() {
            if (this.elements.refreshBtn) this.elements.refreshBtn.addEventListener('click', () => this.load());
            if (this.elements.runBtn) this.elements.runBtn.addEventListener('click', () => this.run());
            const root = this.elements.boardEl?.parentElement || this.elements.listEl?.parentElement;
            root?.addEventListener('change', event => { const input = event.target.closest('[data-screener-filter]'); if (!input) return; this.filters[input.dataset.screenerFilter] = input.type === 'range' ? Number(input.value) : input.value; this.load(); });
            this.elements.listEl?.addEventListener('click', event => {
                const sortButton = event.target.closest('[data-screener-sort]'), runButton = event.target.closest('[data-screener-run-modes]'), selectButton = event.target.closest('[data-screener-select]');
                if (sortButton) { const key = sortButton.dataset.screenerSort; this.sort = { key, direction: this.sort.key === key && this.sort.direction === 'desc' ? 'asc' : 'desc' }; this.load(); return; }
                if (runButton) { this.runSelectedModes(String(runButton.dataset.screenerRunModes || '').toUpperCase()); return; }
                if (selectButton) { const ticker = String(selectButton.dataset.screenerSelect || '').toUpperCase(); this.selectedTicker = this.selectedTicker === ticker ? '' : ticker; this.render(); }
            });
            this.elements.listEl?.addEventListener('change', event => { const input = event.target.closest('[data-screener-mode]'); if (!input) return; const ticker = String(input.dataset.screenerMode || '').toUpperCase(); this.selectedModes[ticker] = Array.from(this.elements.listEl.querySelectorAll(`[data-screener-mode="${selectorEscape(ticker)}"]:checked`)).map(item => item.value).filter(Boolean); });
        }
        loadOnce() { if (this.loaded) return Promise.resolve(); this.loaded = true; return this.load(); }
    }
    window.StockAgentMarketScreenerPanel = { create, MarketScreenerPanel, formatSignedMetric };
})();
