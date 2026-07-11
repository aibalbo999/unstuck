(function () {
    const signalSectionMethods = {
        renderShareStatistics(snapshot) {
            const stats = snapshot.share_statistics || {};
            if (stats.status !== 'available') return '';
            const e = this.escapeHtml;
            const shortInterest = stats.short_interest || {};
            const signals = Array.isArray(stats.signals) ? stats.signals : [];
            return `<section class="stock-snapshot-shares"><div class="stock-snapshot-shares-header"><div><span>股本結構</span><strong>${e(stats.label || '股本結構')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-shares-grid">${this.shareMetric('在外股數', this.compact(stats.shares_outstanding), '')}${this.shareMetric('流通股數', this.compact(stats.float_shares), stats.float_pct_of_shares !== null && stats.float_pct_of_shares !== undefined ? `流通股 ${this.percentLabel(stats.float_pct_of_shares)}` : '')}${this.shareMetric('機構持股', this.percentLabel(stats.institutional_ownership_pct), stats.insider_ownership_pct !== null && stats.insider_ownership_pct !== undefined ? `內部人 ${this.percentLabel(stats.insider_ownership_pct)}` : '')}${this.shareMetric('放空壓力', this.compact(shortInterest.shares_short), `空單/流通 ${this.percentLabel(shortInterest.short_percent_of_float_pct)} · Short ratio ${this.numericLabel(shortInterest.short_ratio)}`)}</div></section>`;
        },

        renderRiskLiquidity(snapshot) {
            const risk = snapshot.risk_liquidity || {};
            if (risk.status !== 'available') return '';
            const e = this.escapeHtml;
            const signals = Array.isArray(risk.signals) ? risk.signals : [];
            return `<section class="stock-snapshot-risk"><div class="stock-snapshot-risk-header"><div><span>風險與流動性</span><strong>${e(risk.label || '風險摘要')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-risk-grid">${this.riskMetric('Beta', risk.beta?.label, '')}${this.riskMetric('52週回撤', this.percentDeltaLabel(risk.drawdown_from_52w_high_pct), '')}${this.riskMetric('成交量/均量', this.percentDeltaLabel(risk.volume_vs_avg_pct), '')}${this.riskMetric('負債權益比', this.percentLabel(risk.debt_to_equity_pct), '')}${this.riskMetric('流動比率', risk.current_ratio?.label, '')}</div></section>`;
        },

        renderProfitabilityQuality(snapshot) {
            const quality = snapshot.profitability_quality || {};
            if (quality.status !== 'available') return '';
            const e = this.escapeHtml;
            const signals = Array.isArray(quality.signals) ? quality.signals : [];
            return `<section class="stock-snapshot-profitability"><div class="stock-snapshot-profitability-header"><div><span>獲利品質</span><strong>${e(quality.label || '獲利品質')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-profitability-grid">${this.profitabilityMetric('毛利率', this.percentLabel(quality.gross_margin_pct), '')}${this.profitabilityMetric('營業利益率', this.percentLabel(quality.operating_margin_pct), '')}${this.profitabilityMetric('淨利率', this.percentLabel(quality.net_margin_pct), '')}${this.profitabilityMetric('ROE', this.percentLabel(quality.roe_pct), '')}${this.profitabilityMetric('ROA', this.percentLabel(quality.roa_pct), '')}${this.profitabilityMetric('FCF margin', this.percentLabel(quality.fcf_margin_pct), '')}</div></section>`;
        },

        renderDividendProfile(snapshot) {
            const profile = snapshot.dividend_profile || {};
            if (profile.status !== 'available') return '';
            const e = this.escapeHtml;
            const history = profile.history || {};
            const coverage = profile.coverage || {};
            const signals = Array.isArray(profile.signals) ? profile.signals : [];
            return `<section class="stock-snapshot-dividend"><div class="stock-snapshot-dividend-header"><div><span>股利品質</span><strong>${e(profile.label || '股利摘要')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-dividend-grid">${this.dividendMetric('年化股利', profile.annual_dividend?.label, '')}${this.dividendMetric('殖利率', profile.yield?.label, '')}${this.dividendMetric('配息率', profile.payout_ratio?.label, '')}${this.dividendMetric('FCF 覆蓋', this.coverageLabel(coverage.fcf_coverage_ratio), '')}</div>${this.dividendBars(history)}</section>`;
        },

        renderEventCalendar(snapshot) {
            const calendar = snapshot.event_calendar || {};
            const events = Array.isArray(calendar.events) ? calendar.events : [];
            if (calendar.status !== 'available' || !events.length) return '';
            const e = this.escapeHtml;
            return `<section class="stock-snapshot-calendar"><div class="stock-snapshot-calendar-header"><div><span>關鍵日期</span><strong>${e(calendar.label || '近期關鍵日期')}</strong></div><div>${calendar.next_event?.days_until !== undefined ? `<em>${e(this.eventTimingLabel(calendar.next_event))}</em>` : ''}</div></div><div class="stock-snapshot-calendar-grid">${events.slice(0, 4).map(item => this.calendarEvent(item)).join('')}</div></section>`;
        },

        renderAlertSuggestions(snapshot) {
            const alerts = snapshot.alert_suggestions || {};
            const suggestions = Array.isArray(alerts.suggestions) ? alerts.suggestions : [];
            if (alerts.status !== 'available' || !suggestions.length) return '';
            const e = this.escapeHtml;
            return `<section class="stock-snapshot-alerts"><div class="stock-snapshot-alert-header"><div><span>提醒建議</span><strong>${e(alerts.label || '提醒建議')}</strong></div></div><div class="stock-snapshot-alert-grid">${suggestions.slice(0, 4).map((item, index) => this.alertSuggestion(item, index)).join('')}</div></section>`;
        },
    };

    window.StockAgentStockSnapshotSignalSections = { signalSectionMethods };
})();
