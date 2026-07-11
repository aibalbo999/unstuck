(function () {
    const panelMethods = window.StockAgentStockSnapshotFormatHelpers?.panelMethods || {};

    const simpleMetric = className => function (label, value, detail) {
        const e = this.escapeHtml;
        const classAttr = className ? ` class="${className}"` : '';
        return `<div${classAttr}><span>${e(label)}</span><strong>${e(value || '-')}</strong><em>${e(detail || '')}</em></div>`;
    };

    const fragmentMethods = {
        metric(label, value, detail) {
            const e = this.escapeHtml;
            return `<div class="stock-snapshot-metric"><span>${e(label)}</span><strong>${e(value ?? '-')}</strong><em>${e(detail || '')}</em></div>`;
        },
        sessionMetric: simpleMetric(''),
        fundamentalMetric: simpleMetric(''),
        technicalMetric: simpleMetric(''),
        analystMetric: simpleMetric(''),
        earningsMetric: simpleMetric(''),
        shareMetric: simpleMetric(''),
        riskMetric: simpleMetric(''),
        profitabilityMetric: simpleMetric(''),
        dividendMetric: simpleMetric(''),
        ownershipMetric: simpleMetric(''),
        profileFact(label, value) {
            const e = this.escapeHtml;
            return `<div><span>${e(label || '')}</span><strong>${e(value || '-')}</strong></div>`;
        },
        financialTrendRow(row) {
            const e = this.escapeHtml;
            return `<div class="stock-snapshot-financial-trend-row" role="row"><span>${e(row.period || '-')}</span><span><strong>${e(this.financialValueLabel(row.revenue))}</strong><em class="${this.returnClass(row.revenue_yoy_pct)}">${e(this.returnLabel(row.revenue_yoy_pct))}</em></span><span><strong>${e(this.financialValueLabel(row.net_income))}</strong><em class="${this.returnClass(row.net_income_yoy_pct)}">${e(this.returnLabel(row.net_income_yoy_pct))}</em></span><span><strong>${e(this.financialValueLabel(row.free_cash_flow))}</strong><em class="${this.returnClass(row.free_cash_flow_yoy_pct)}">${e(this.returnLabel(row.free_cash_flow_yoy_pct))}</em></span><span><strong>${e(`毛利率 ${this.percentLabel(row.gross_margin_pct)}`)}</strong><em>${e(`營業 ${this.percentLabel(row.operating_margin_pct)}`)}</em></span></div>`;
        },
        dividendBars(history) {
            const years = Array.isArray(history?.years) ? history.years : [];
            const dividends = Array.isArray(history?.dividends) ? history.dividends : [];
            const rows = years.map((year, index) => ({ year, value: Number(dividends[index]) })).filter(row => Number.isFinite(row.value));
            if (!rows.length) return '';
            const e = this.escapeHtml;
            const max = Math.max(...rows.map(row => row.value), 1);
            return `<div class="stock-snapshot-dividend-bars">${rows.map(row => `<span><i style="height:${Math.max(8, (row.value / max) * 54).toFixed(0)}px"></i><strong>${e(String(row.year))}</strong><em>${e(this.priceLabel(row.value))}</em></span>`).join('')}</div>`;
        },
        calendarEvent(item) {
            const e = this.escapeHtml;
            const detail = [this.eventTimingLabel(item), item.source].filter(Boolean).join(' · ');
            return `<article class="is-${e(item.timing || 'upcoming')}"><span>${e(item.label || this.eventLabel(item.type))}</span><strong>${e(item.date_label || item.date || '-')}</strong><em>${e(detail)}</em></article>`;
        },
        alertSuggestion(item, index) {
            const e = this.escapeHtml;
            return `<article><span>${e(this.alertCategoryLabel(item.category))}</span><strong>${e(item.label || '提醒')}</strong><em>${e(item.detail || '')}</em><button type="button" data-stock-snapshot-alert="${e(String(index))}">套用提醒</button></article>`;
        },
        valuationBand(item) {
            const e = this.escapeHtml;
            return `<div class="stock-snapshot-valuation-band"><span>${e(item.label || '-')}</span><strong>${e(this.priceLabel(item.price))}</strong></div>`;
        },
        peerRow(row) {
            const e = this.escapeHtml;
            const name = [row.name, row.ticker].filter(Boolean).join(' · ');
            return `<div class="stock-snapshot-peer-row ${row.is_target ? 'is-target' : ''}" role="row"><span>${e(name || '-')}</span><span>${e(this.percentLabel(row.gross_margin_pct))}</span><span>${e(this.percentLabel(row.roe_pct))}</span><span>${e(this.multipleLabel(row.pe_ttm))}</span><span>${e(this.multipleLabel(row.ps_ttm))}</span></div>`;
        },
        balanceDetail(balance) {
            const parts = [];
            if (balance?.debt_label) parts.push(`負債 ${balance.debt_label}`);
            if (balance?.debt_to_equity_label) parts.push(`D/E ${balance.debt_to_equity_label}`);
            return parts.join(' · ');
        }
    };

    window.StockAgentStockSnapshotHelpers = { panelMethods, fragmentMethods };
})();
