(function () {
    const FLAG_LABELS = {
        single_position_over_40_pct: '單一持股超過 40%',
        sector_over_60_pct: '產業曝險超過 60%',
        country_over_80_pct: '單一市場超過 80%',
        invalidated_thesis_position: '投資論文已失效'
    };

    function create(options) {
        const apiClient = options.apiClient;
        const elements = options.elements || {};
        const escapeHtml = options.ui?.escapeHtml || (value => String(value ?? ''));

        function setSummary(text) { if (elements.summaryEl) elements.summaryEl.textContent = text; }

        function pct(value) {
            const number = Number(value);
            return Number.isFinite(number) ? `${number.toFixed(number % 1 === 0 ? 0 : 1)}%` : '-';
        }

        function chipList(title, rows) {
            const entries = Object.entries(rows || {});
            if (!entries.length) return '';
            return `<section class="portfolio-risk-block"><strong>${escapeHtml(title)}</strong><div>${entries.slice(0, 6).map(([key, value]) => `<span class="provider-sla-chip"><em>${escapeHtml(key)}</em><span>${escapeHtml(pct(value))}</span></span>`).join('')}</div></section>`;
        }

        function render(payload) {
            const flags = payload.risk_flags || [];
            const concentration = payload.concentration || {};
            const top = concentration.top_position || {};
            const thesis = payload.thesis_health || {};
            setSummary(`${payload.total_positions || 0} 檔持股 · ${flags.length} 個風險旗標`);
            if (!elements.resultEl) return;
            elements.resultEl.hidden = false;
            elements.resultEl.innerHTML = `
                <div class="portfolio-risk-summary-grid">
                    <div><span>最大持股</span><strong>${escapeHtml(top.ticker || '-')}</strong><em>${escapeHtml(pct(top.weight_pct))}</em></div>
                    <div><span>風險旗標</span><strong>${escapeHtml(String(flags.length))}</strong><em>${escapeHtml(flags.map(flag => FLAG_LABELS[flag] || flag).join('、') || '未觸發')}</em></div>
                    <div><span>投資論文缺口</span><strong>${escapeHtml(String((thesis.invalidated || []).length + (thesis.missing || []).length))}</strong><em>${escapeHtml([...(thesis.invalidated || []), ...(thesis.missing || [])].join('、') || '已覆蓋')}</em></div>
                </div>
                ${chipList('產業曝險', concentration.sector_weights)}
                ${chipList('市場曝險', concentration.country_weights)}
            `;
        }

        function setLoading(value) {
            if (!elements.runBtn) return;
            elements.runBtn.disabled = Boolean(value);
            const label = elements.runBtn.querySelector('span');
            if (label) label.textContent = value ? '分析中' : '分析持股風險';
        }

        async function analyze() {
            const csv = String(elements.csvInput?.value || '').trim();
            if (!csv) { setSummary('請貼上持股 CSV'); return; }
            try {
                setLoading(true);
                render(await apiClient.analyzePortfolioRisk(csv));
            } catch (err) {
                setSummary(`持股風險分析失敗：${err.message || err}`);
            } finally {
                setLoading(false);
            }
        }

        function bindEvents() {
            if (elements.runBtn) elements.runBtn.addEventListener('click', analyze);
        }

        return { analyze, bindEvents, render };
    }

    window.StockAgentPortfolioRiskPanel = { create };
})();
