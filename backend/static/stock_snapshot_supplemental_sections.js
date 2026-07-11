(function () {
    const supplementalSectionMethods = {
        renderGrid(snapshot) {
            const quote = snapshot.quote || {}, valuation = snapshot.valuation || {}, dividends = snapshot.dividends || {}, chip = snapshot.chip || {};
            return `<div class="stock-snapshot-grid">${[
                this.metric('現價', quote.price_label || quote.price, this.rangeLabel('52週', quote.range_52w)),
                this.metric('市值', quote.market_cap_label || quote.market_cap, valuation.pe_ratio?.label ? `P/E ${valuation.pe_ratio.label}` : ''),
                this.metric('分析師目標', valuation.analyst_target?.label, this.upsideLabel(valuation.analyst_target)),
                this.metric('股利', dividends.yield_label, dividends.annual_dividend_label ? `年化 ${dividends.annual_dividend_label}` : ''),
                this.metric('Beta', quote.beta, quote.volume ? `量 ${this.compact(quote.volume)}` : ''),
                this.metric('籌碼', chip.institutional_summary || '-', this.chipStatus(chip)),
            ].join('')}</div>`;
        },

        renderEvents(snapshot) {
            const e = this.escapeHtml, events = Array.isArray(snapshot.events) ? snapshot.events : [];
            if (!events.length) return '';
            return `<div class="stock-snapshot-strip">${events.slice(0, 4).map(item => `<span><strong>${e(this.eventLabel(item.type))}</strong>${e(item.label || '-')}</span>`).join('')}</div>`;
        },

        renderNews(snapshot) {
            const e = this.escapeHtml, news = Array.isArray(snapshot.news) ? snapshot.news : [];
            if (!news.length) return '';
            return `<div class="stock-snapshot-news">${news.slice(0, 3).map(item => `<article><strong>${e(item.title)}</strong><span>${e([item.source, item.published_at].filter(Boolean).join(' · '))}</span></article>`).join('')}</div>`;
        },

        renderModes(snapshot) {
            const e = this.escapeHtml, modes = Array.isArray(snapshot.mode_suggestions) ? snapshot.mode_suggestions : [];
            if (!modes.length) return '';
            return `<div class="stock-snapshot-modes">${modes.map(item => `<button type="button" data-stock-snapshot-pipeline="${e(item.pipeline_id)}"><strong>${e(item.label)}</strong><span>${e(item.decision)}</span></button>`).join('')}</div>`;
        },
    };

    window.StockAgentStockSnapshotSupplementalSections = { supplementalSectionMethods };
})();
