(function () {
    const researchSectionMethods = {
        renderValuationRange(snapshot) {
            const range = snapshot.valuation_range || {};
            const bands = Array.isArray(range.bands) ? range.bands : [];
            if (range.status !== 'available' || !bands.length) return '';
            const e = this.escapeHtml;
            return `<section class="stock-snapshot-valuation-range"><div class="stock-snapshot-valuation-header"><div><span>估值區間</span><strong>${e(range.label || '估值參考')}</strong></div><div><em>距中位 ${e(this.percentDeltaLabel(range.price_vs_mid_pct))}</em><em>${e(range.source || 'P/E 河流圖')}</em></div></div><div class="stock-snapshot-valuation-bands">${bands.map(item => this.valuationBand(item)).join('')}</div><div class="stock-snapshot-valuation-mid"><span>目前價 ${e(this.priceLabel(range.current_price))}</span><span>中位估值 ${e(this.priceLabel(range.mid_price))}</span></div></section>`;
        },

        renderAnalystOutlook(snapshot) {
            const outlook = snapshot.analyst_outlook || {};
            if (outlook.status !== 'available') return '';
            const e = this.escapeHtml;
            const target = outlook.target || {};
            const consensus = outlook.consensus || {};
            const valuation = outlook.valuation || {};
            const growth = outlook.growth || {};
            const signals = Array.isArray(outlook.signals) ? outlook.signals : [];
            return `<section class="stock-snapshot-analyst"><div class="stock-snapshot-analyst-header"><div><span>分析師展望</span><strong>${e(outlook.label || '分析師展望')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-analyst-grid">${this.analystMetric('目標價', target.label || this.priceLabel(target.price), this.percentDeltaLabel(target.upside_pct))}${this.analystMetric('共識', consensus.recommendation_label || '-', consensus.analyst_count ? `${consensus.analyst_count} 位` : '')}${this.analystMetric('Forward P/E', valuation.forward_pe?.label, '')}${this.analystMetric('EPS 成長', growth.earnings_growth?.label, '')}</div></section>`;
        },

        renderEarningsForecast(snapshot) {
            const forecast = snapshot.earnings_forecast || {};
            if (forecast.status !== 'available') return '';
            const e = this.escapeHtml;
            const growth = forecast.growth || {};
            const next = forecast.next_earnings || {};
            const signals = Array.isArray(forecast.signals) ? forecast.signals : [];
            return `<section class="stock-snapshot-earnings"><div class="stock-snapshot-earnings-header"><div><span>盈餘預估</span><strong>${e(forecast.label || '盈餘預估')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-earnings-grid">${this.earningsMetric('Trailing EPS', forecast.trailing_eps?.label, '')}${this.earningsMetric('Forward EPS', forecast.forward_eps?.label, `較 TTM ${this.percentDeltaLabel(forecast.forward_eps_change_pct)}`)}${this.earningsMetric('EPS 成長', growth.earnings_growth?.label, growth.revenue_growth?.label ? `營收 ${growth.revenue_growth.label}` : '')}${this.earningsMetric('下次財報', next.date || '-', this.earningsForecastDetail(next, forecast.analyst_count))}</div></section>`;
        }
    };

    window.StockAgentStockSnapshotResearchSections = { researchSectionMethods };
})();
