(function () {
    const summaryMethods = {
        renderHeader(snapshot) {
            const e = this.escapeHtml;
            const identity = snapshot.identity || {};
            const quality = snapshot.data_quality || {};
            const qualityScore = quality.score === null || quality.score === undefined ? '' : ` · ${e(String(Math.round(Number(quality.score))))}分`;
            const ticker = e(snapshot.ticker || this.currentTicker);
            return `<div class="stock-snapshot-header"><div><span class="stock-snapshot-kicker">股票快照</span><h2>${ticker} ${e(identity.company_name || '')}</h2><p>${e([identity.sector, identity.industry].filter(Boolean).join(' · '))}</p><div class="stock-snapshot-actions-row"><button type="button" class="maintenance-button" data-stock-snapshot-watchlist="${ticker}"><span>加入追蹤</span></button></div></div><span class="stock-snapshot-quality is-${e(quality.status || 'unknown')}">${e(quality.status || 'unknown')}${qualityScore}</span></div>`;
        },

        renderSummaryRail(snapshot) {
            const session = snapshot.market_session || {};
            const quote = snapshot.quote || {};
            const valuationRange = snapshot.valuation_range || {};
            const analyst = snapshot.analyst_outlook || {};
            const quality = snapshot.profitability_quality || {};
            const calendar = snapshot.event_calendar || {};
            const nextEvent = calendar.next_event || {};
            const items = [
                this.summaryRailItem('現價', quote.price_label || this.priceLabel(session.current_price || quote.price), this.returnLabel(session.change_pct), session.direction),
                this.summaryRailItem('估值', valuationRange.label || '-', this.percentDeltaLabel(valuationRange.price_vs_mid_pct), 'neutral'),
                this.summaryRailItem('展望', analyst.label || '-', analyst.target?.upside_pct !== undefined ? this.percentDeltaLabel(analyst.target.upside_pct) : '', 'neutral'),
                this.summaryRailItem('獲利', quality.label || '-', Array.isArray(quality.signals) ? quality.signals[0] : '', 'positive'),
                this.summaryRailItem('事件', nextEvent.label || nextEvent.date_label || '-', this.eventTimingLabel(nextEvent), 'neutral'),
            ].filter(Boolean);
            if (!items.length) return '';
            return `<div class="stock-snapshot-summary-rail">${items.join('')}</div>`;
        },

        summaryRailItem(label, value, detail, tone) {
            if (!value || value === '-') return '';
            const e = this.escapeHtml;
            return `<div class="is-${e(tone || 'neutral')}"><span>${e(label)}</span><strong>${e(value)}</strong><em>${e(detail || '')}</em></div>`;
        },

        renderError(err) {
            const root = this.elements.root;
            if (!root) return;
            root.hidden = false;
            root.innerHTML = `<div class="stock-snapshot-error"><strong>股票快照讀取失敗</strong><span>${this.escapeHtml(err.message || err)}</span></div>`;
        },
    };

    window.StockAgentStockSnapshotSummaryHelpers = { summaryMethods };
})();
