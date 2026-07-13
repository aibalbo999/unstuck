(function () {
    const overviewSectionMethods = {
        renderCompanyProfile(snapshot) {
            const profile = snapshot.company_profile || {};
            const facts = Array.isArray(profile.facts) ? profile.facts : [];
            if (profile.status !== 'available' && !profile.summary && !profile.website && !facts.length) return '';
            const e = this.escapeHtml;
            const website = profile.website ? `<a href="${e(profile.website)}" target="_blank" rel="noreferrer">官網</a>` : '';
            const summary = profile.summary ? `<p>${e(this.shortText(profile.summary, 220))}</p>` : '';
            const factGrid = facts.length ? `<div class="stock-snapshot-company-profile-grid">${facts.slice(0, 6).map(item => this.profileFact(item.label, item.value)).join('')}</div>` : '';
            return `<section class="stock-snapshot-company-profile"><div class="stock-snapshot-company-profile-header"><div><span>公司檔案</span><strong>${e(profile.label || '公司檔案')}</strong></div>${website}</div>${summary}${factGrid}</section>`;
        },

        renderMarketSession(snapshot) {
            const session = snapshot.market_session || {};
            if (session.current_price === null || session.current_price === undefined) return '';
            const e = this.escapeHtml;
            const range = session.day_range || {};
            const rangeText = range.low !== null && range.low !== undefined && range.high !== null && range.high !== undefined
                ? `${this.priceLabel(range.low)} / ${this.priceLabel(range.high)}`
                : '-';
            const volumeText = session.volume ? `量 ${this.compact(session.volume)}` : '量 -';
            return `<section class="stock-snapshot-session is-${e(session.direction || 'flat')}"><div class="stock-snapshot-session-main"><span>今日行情</span><strong>${e(this.priceLabel(session.current_price))}</strong><em>${e(this.signedPriceLabel(session.change))} · ${e(this.returnLabel(session.change_pct))}</em></div><div class="stock-snapshot-session-grid">${this.sessionMetric('開盤', this.priceLabel(session.open), '')}${this.sessionMetric('昨收', this.priceLabel(session.previous_close), '')}${this.sessionMetric('日內', rangeText, this.positionLabel(session.day_position_pct))}${this.sessionMetric('成交量', volumeText, `較均量 ${this.volumeVsAvgLabel(session.volume_vs_avg_pct)}`)}</div></section>`;
        },

        renderTrend(snapshot) {
            const trend = snapshot.price_trend || {};
            const points = Array.isArray(trend.sparkline) ? trend.sparkline : [];
            if (points.length < 2) return '';
            const e = this.escapeHtml;
            return `<div class="stock-snapshot-trend"><div><span>${e(trend.label || '近一年月收盤')}</span><strong>${e(this.priceLabel(trend.latest_price))}</strong></div><svg class="stock-snapshot-trend-chart" viewBox="0 0 120 42" aria-hidden="true"><polyline points="${e(this.sparklinePoints(points))}" /></svg><div class="stock-snapshot-trend-returns">${['1m', '3m', '1y'].map(key => `<span><em>${e(key.toUpperCase())}</em><strong class="${this.returnClass(trend.returns?.[key])}">${e(this.returnLabel(trend.returns?.[key]))}</strong></span>`).join('')}</div></div>`;
        },

        renderPerformanceHistory(snapshot) {
            const performance = snapshot.performance_history || {};
            const ranges = Array.isArray(performance.ranges) ? performance.ranges : [];
            if (performance.status !== 'available' || !ranges.length) return '';
            const e = this.escapeHtml;
            const active = this.performanceRange(performance.default_range, ranges) || ranges[0];
            return `<section class="stock-snapshot-performance"><div class="stock-snapshot-performance-header"><div><span>多週期走勢</span><strong>${e(performance.label || '多週期走勢')}</strong></div><em>${e(performance.source || '')}</em></div><div class="stock-snapshot-performance-controls">${ranges.map(item => `<button type="button" class="${item.key === active.key ? 'is-active' : ''}" data-stock-snapshot-range="${e(item.key)}">${e(item.label || item.key.toUpperCase())}</button>`).join('')}</div><div class="stock-snapshot-performance-chart" data-stock-snapshot-performance-chart>${this.performanceRangeChart(active)}</div></section>`;
        },

        renderTechnicalSummary(snapshot) {
            const summary = snapshot.technical_summary || {};
            if (summary.status !== 'available') return '';
            const e = this.escapeHtml;
            const averages = summary.moving_averages || {};
            const range = summary.range_52w || {};
            const momentum = summary.momentum || {};
            const signals = Array.isArray(summary.signals) ? summary.signals : [];
            return `<section class="stock-snapshot-technical"><div class="stock-snapshot-technical-header"><div><span>技術面</span><strong>${e(summary.label || '技術摘要')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-technical-grid">${this.technicalMetric(averages.ma_3m?.label || '3M 均線', this.priceLabel(averages.ma_3m?.value), this.percentDeltaLabel(averages.ma_3m?.distance_pct))}${this.technicalMetric(averages.ma_6m?.label || '6M 均線', this.priceLabel(averages.ma_6m?.value), this.percentDeltaLabel(averages.ma_6m?.distance_pct))}${this.technicalMetric('52週位置', this.percentLabel(range.position_pct), `距高點 ${this.percentDeltaLabel(range.drawdown_from_high_pct)}`)}${this.technicalMetric('3M 動能', this.returnLabel(momentum['3m']), `1Y ${this.returnLabel(momentum['1y'])}`)}</div></section>`;
        }
    };

    window.StockAgentStockSnapshotOverviewSections = { overviewSectionMethods };
})();
