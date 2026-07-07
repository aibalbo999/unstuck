(function () {
    const RECENT_TICKERS_KEY = 'stockAgent.stockSnapshot.recentTickers';
    const DEFAULT_SHORTCUT_TICKERS = ['2330.TW', '2317.TW', '2454.TW', 'AAPL', 'NVDA'];

    function create(options) {
        return new StockSnapshotPanel(options || {});
    }

    class StockSnapshotPanel {
        constructor(options) {
            this.apiClient = options.apiClient;
            this.ui = options.ui || {};
            this.notify = options.notify || { error: () => {} };
            this.elements = options.elements || {};
            this.onSelectPipeline = options.onSelectPipeline || (() => {});
            this.onWatchlistUpdated = options.onWatchlistUpdated || (() => {});
            this.getSelectedPipeline = options.getSelectedPipeline || (() => '');
            this.escapeHtml = this.ui.escapeHtml || (value => String(value ?? ''));
            this.currentTicker = '';
            this.lastSnapshot = null;
            this.defaultShortcuts = Array.isArray(options.defaultShortcuts) && options.defaultShortcuts.length
                ? options.defaultShortcuts
                : DEFAULT_SHORTCUT_TICKERS;
        }

        bindEvents() {
            const button = this.elements.loadButton;
            if (button) button.addEventListener('click', () => this.loadFromInput());
            this.elements.tickerInput?.addEventListener('keydown', event => {
                if (event.key !== 'Enter' || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return undefined;
                event.preventDefault?.();
                event.stopPropagation?.();
                event.stopImmediatePropagation?.();
                return this.loadFromInput();
            });
            this.elements.shortcutsRoot?.addEventListener('click', event => {
                const shortcutButton = event.target.closest('[data-stock-snapshot-shortcut]');
                if (!shortcutButton) return;
                const ticker = this.normalizeTickerInput(shortcutButton.dataset.stockSnapshotShortcut);
                if (!ticker) return;
                this.setTickerInput(ticker);
                this.load(ticker);
            });
            this.renderShortcuts();
            this.elements.root?.addEventListener('click', event => {
                const watchlistButton = event.target.closest('[data-stock-snapshot-watchlist]');
                if (watchlistButton) {
                    this.addToWatchlist(watchlistButton.dataset.stockSnapshotWatchlist);
                    return;
                }
                const alertButton = event.target.closest('[data-stock-snapshot-alert]');
                if (alertButton) {
                    this.applyAlertSuggestion(Number(alertButton.dataset.stockSnapshotAlert));
                    return;
                }
                const rangeButton = event.target.closest('[data-stock-snapshot-range]');
                if (rangeButton) {
                    this.selectPerformanceRange(rangeButton.dataset.stockSnapshotRange);
                    return;
                }
                const button = event.target.closest('[data-stock-snapshot-pipeline]');
                if (!button) return;
                this.onSelectPipeline(button.dataset.stockSnapshotPipeline);
            });
        }

        async loadFromInput() {
            const ticker = this.normalizeTickerInput(this.elements.tickerInput?.value);
            if (!ticker) {
                this.notify.error('請輸入股票代號。');
                return;
            }
            this.setTickerInput(ticker);
            await this.load(ticker);
        }

        async load(ticker) {
            if (!this.apiClient || typeof this.apiClient.fetchStockSnapshot !== 'function') return;
            const normalizedTicker = this.normalizeTickerInput(ticker);
            if (!normalizedTicker) return;
            this.currentTicker = normalizedTicker;
            this.setTickerInput(normalizedTicker);
            this.setLoading(true);
            try {
                const snapshot = await this.apiClient.fetchStockSnapshot(normalizedTicker);
                this.rememberTicker(snapshot?.ticker || normalizedTicker);
                this.renderShortcuts();
                this.render(snapshot);
            } catch (err) {
                this.renderError(err);
            } finally {
                this.setLoading(false);
            }
        }

        setLoading(value) {
            const button = this.elements.loadButton;
            if (!button) return;
            button.disabled = Boolean(value);
            const label = button.querySelector('span');
            if (label) label.textContent = value ? '載入中' : '股票快照';
        }

        renderShortcuts() {
            const root = this.elements.shortcutsRoot;
            if (!root) return;
            const recent = this.getRecentTickers();
            const common = this.defaultShortcuts
                .map(ticker => this.normalizeTickerInput(ticker))
                .filter(Boolean)
                .filter((ticker, index, list) => list.indexOf(ticker) === index && !recent.includes(ticker))
                .slice(0, 5);
            root.innerHTML = `<div class="stock-snapshot-shortcuts-row">${this.shortcutGroup('最近', recent)}${this.shortcutGroup('常用', common)}</div>`;
        }

        shortcutGroup(label, tickers) {
            const e = this.escapeHtml;
            if (!Array.isArray(tickers) || !tickers.length) return '';
            return `<div class="stock-snapshot-shortcuts-group"><span>${e(label)}</span>${tickers.map(ticker => `<button type="button" data-stock-snapshot-shortcut="${e(ticker)}">${e(ticker)}</button>`).join('')}</div>`;
        }

        getRecentTickers() {
            try {
                const storage = window.localStorage;
                if (!storage) return [];
                const parsed = JSON.parse(storage.getItem(RECENT_TICKERS_KEY) || '[]');
                if (!Array.isArray(parsed)) return [];
                return parsed
                    .map(ticker => this.normalizeTickerInput(ticker))
                    .filter(Boolean)
                    .filter((ticker, index, list) => list.indexOf(ticker) === index)
                    .slice(0, 5);
            } catch (_) {
                return [];
            }
        }

        rememberTicker(ticker) {
            const normalized = this.normalizeTickerInput(ticker);
            if (!normalized) return;
            try {
                const storage = window.localStorage;
                if (!storage) return;
                const tickers = [normalized, ...this.getRecentTickers().filter(item => item !== normalized)].slice(0, 5);
                storage.setItem(RECENT_TICKERS_KEY, JSON.stringify(tickers));
            } catch (_) {
                // Browser privacy settings can block localStorage; shortcuts still work without recents.
            }
        }

        normalizeTickerInput(value) {
            const ticker = String(value || '').trim().toUpperCase();
            if (!ticker) return '';
            if (/^\d{4}$/.test(ticker)) return `${ticker}.TW`;
            return ticker.replace(/\s+/g, '');
        }

        setTickerInput(ticker) {
            if (this.elements.tickerInput) this.elements.tickerInput.value = ticker;
        }

        render(snapshot) {
            const root = this.elements.root;
            if (!root) return;
            this.lastSnapshot = snapshot;
            root.hidden = false;
            root.innerHTML = [
                this.renderHeader(snapshot),
                this.renderSummaryRail(snapshot),
                this.renderCompanyProfile(snapshot),
                this.renderMarketSession(snapshot),
                this.renderTrend(snapshot),
                this.renderPerformanceHistory(snapshot),
                this.renderTechnicalSummary(snapshot),
                this.renderValuationRange(snapshot),
                this.renderAnalystOutlook(snapshot),
                this.renderEarningsForecast(snapshot),
                this.renderShareStatistics(snapshot),
                this.renderRiskLiquidity(snapshot),
                this.renderProfitabilityQuality(snapshot),
                this.renderDividendProfile(snapshot),
                this.renderEventCalendar(snapshot),
                this.renderAlertSuggestions(snapshot),
                this.renderFinancialHealth(snapshot),
                this.renderFinancialTrends(snapshot),
                this.renderPeerComparison(snapshot),
                this.renderOwnershipFlow(snapshot),
                this.renderGrid(snapshot),
                this.renderEvents(snapshot),
                this.renderNews(snapshot),
                this.renderModes(snapshot),
            ].join('');
        }

        renderHeader(snapshot) {
            const e = this.escapeHtml;
            const identity = snapshot.identity || {};
            const quality = snapshot.data_quality || {};
            const qualityScore = quality.score === null || quality.score === undefined ? '' : ` · ${e(String(Math.round(Number(quality.score))))}分`;
            const ticker = e(snapshot.ticker || this.currentTicker);
            return `<div class="stock-snapshot-header"><div><span class="stock-snapshot-kicker">股票快照</span><h2>${ticker} ${e(identity.company_name || '')}</h2><p>${e([identity.sector, identity.industry].filter(Boolean).join(' · '))}</p><div class="stock-snapshot-actions-row"><button type="button" class="maintenance-button" data-stock-snapshot-watchlist="${ticker}"><span>加入追蹤</span></button></div></div><span class="stock-snapshot-quality is-${e(quality.status || 'unknown')}">${e(quality.status || 'unknown')}${qualityScore}</span></div>`;
        }

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
        }

        summaryRailItem(label, value, detail, tone) {
            if (!value || value === '-') return '';
            const e = this.escapeHtml;
            return `<div class="is-${e(tone || 'neutral')}"><span>${e(label)}</span><strong>${e(value)}</strong><em>${e(detail || '')}</em></div>`;
        }

        renderCompanyProfile(snapshot) {
            const profile = snapshot.company_profile || {};
            const facts = Array.isArray(profile.facts) ? profile.facts : [];
            if (profile.status !== 'available' && !profile.summary && !profile.website && !facts.length) return '';
            const e = this.escapeHtml;
            const website = profile.website ? `<a href="${e(profile.website)}" target="_blank" rel="noreferrer">官網</a>` : '';
            const summary = profile.summary ? `<p>${e(this.shortText(profile.summary, 220))}</p>` : '';
            const factGrid = facts.length ? `<div class="stock-snapshot-company-profile-grid">${facts.slice(0, 6).map(item => this.profileFact(item.label, item.value)).join('')}</div>` : '';
            return `<section class="stock-snapshot-company-profile"><div class="stock-snapshot-company-profile-header"><div><span>公司檔案</span><strong>${e(profile.label || '公司檔案')}</strong></div>${website}</div>${summary}${factGrid}</section>`;
        }

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
        }

        renderTrend(snapshot) {
            const trend = snapshot.price_trend || {};
            const points = Array.isArray(trend.sparkline) ? trend.sparkline : [];
            if (points.length < 2) return '';
            const e = this.escapeHtml;
            return `<div class="stock-snapshot-trend"><div><span>${e(trend.label || '近一年月收盤')}</span><strong>${e(this.priceLabel(trend.latest_price))}</strong></div><svg class="stock-snapshot-trend-chart" viewBox="0 0 120 42" aria-hidden="true"><polyline points="${e(this.sparklinePoints(points))}" /></svg><div class="stock-snapshot-trend-returns">${['1m', '3m', '1y'].map(key => `<span><em>${e(key.toUpperCase())}</em><strong class="${this.returnClass(trend.returns?.[key])}">${e(this.returnLabel(trend.returns?.[key]))}</strong></span>`).join('')}</div></div>`;
        }

        renderPerformanceHistory(snapshot) {
            const performance = snapshot.performance_history || {};
            const ranges = Array.isArray(performance.ranges) ? performance.ranges : [];
            if (performance.status !== 'available' || !ranges.length) return '';
            const e = this.escapeHtml;
            const active = this.performanceRange(performance.default_range, ranges) || ranges[0];
            return `<section class="stock-snapshot-performance"><div class="stock-snapshot-performance-header"><div><span>多週期走勢</span><strong>${e(performance.label || '多週期走勢')}</strong></div><em>${e(performance.source || '')}</em></div><div class="stock-snapshot-performance-controls">${ranges.map(item => `<button type="button" class="${item.key === active.key ? 'is-active' : ''}" data-stock-snapshot-range="${e(item.key)}">${e(item.label || item.key.toUpperCase())}</button>`).join('')}</div><div class="stock-snapshot-performance-chart" data-stock-snapshot-performance-chart>${this.performanceRangeChart(active)}</div></section>`;
        }

        selectPerformanceRange(key) {
            const ranges = Array.isArray(this.lastSnapshot?.performance_history?.ranges) ? this.lastSnapshot.performance_history.ranges : [];
            const range = this.performanceRange(key, ranges);
            if (!range) return;
            const root = this.elements.root;
            const chart = root?.querySelector?.('[data-stock-snapshot-performance-chart]');
            if (chart) chart.innerHTML = this.performanceRangeChart(range);
            root?.querySelectorAll?.('[data-stock-snapshot-range]').forEach(button => {
                button.classList?.toggle('is-active', button.dataset.stockSnapshotRange === range.key);
            });
        }

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

        renderValuationRange(snapshot) {
            const range = snapshot.valuation_range || {};
            const bands = Array.isArray(range.bands) ? range.bands : [];
            if (range.status !== 'available' || !bands.length) return '';
            const e = this.escapeHtml;
            return `<section class="stock-snapshot-valuation-range"><div class="stock-snapshot-valuation-header"><div><span>估值區間</span><strong>${e(range.label || '估值參考')}</strong></div><div><em>距中位 ${e(this.percentDeltaLabel(range.price_vs_mid_pct))}</em><em>${e(range.source || 'P/E 河流圖')}</em></div></div><div class="stock-snapshot-valuation-bands">${bands.map(item => this.valuationBand(item)).join('')}</div><div class="stock-snapshot-valuation-mid"><span>目前價 ${e(this.priceLabel(range.current_price))}</span><span>中位估值 ${e(this.priceLabel(range.mid_price))}</span></div></section>`;
        }

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
        }

        renderEarningsForecast(snapshot) {
            const forecast = snapshot.earnings_forecast || {};
            if (forecast.status !== 'available') return '';
            const e = this.escapeHtml;
            const growth = forecast.growth || {};
            const next = forecast.next_earnings || {};
            const signals = Array.isArray(forecast.signals) ? forecast.signals : [];
            return `<section class="stock-snapshot-earnings"><div class="stock-snapshot-earnings-header"><div><span>盈餘預估</span><strong>${e(forecast.label || '盈餘預估')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-earnings-grid">${this.earningsMetric('Trailing EPS', forecast.trailing_eps?.label, '')}${this.earningsMetric('Forward EPS', forecast.forward_eps?.label, `較 TTM ${this.percentDeltaLabel(forecast.forward_eps_change_pct)}`)}${this.earningsMetric('EPS 成長', growth.earnings_growth?.label, growth.revenue_growth?.label ? `營收 ${growth.revenue_growth.label}` : '')}${this.earningsMetric('下次財報', next.date || '-', this.earningsForecastDetail(next, forecast.analyst_count))}</div></section>`;
        }

        renderShareStatistics(snapshot) {
            const stats = snapshot.share_statistics || {};
            if (stats.status !== 'available') return '';
            const e = this.escapeHtml;
            const shortInterest = stats.short_interest || {};
            const signals = Array.isArray(stats.signals) ? stats.signals : [];
            return `<section class="stock-snapshot-shares"><div class="stock-snapshot-shares-header"><div><span>股本結構</span><strong>${e(stats.label || '股本結構')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-shares-grid">${this.shareMetric('在外股數', this.compact(stats.shares_outstanding), '')}${this.shareMetric('流通股數', this.compact(stats.float_shares), stats.float_pct_of_shares !== null && stats.float_pct_of_shares !== undefined ? `流通股 ${this.percentLabel(stats.float_pct_of_shares)}` : '')}${this.shareMetric('機構持股', this.percentLabel(stats.institutional_ownership_pct), stats.insider_ownership_pct !== null && stats.insider_ownership_pct !== undefined ? `內部人 ${this.percentLabel(stats.insider_ownership_pct)}` : '')}${this.shareMetric('放空壓力', this.compact(shortInterest.shares_short), `空單/流通 ${this.percentLabel(shortInterest.short_percent_of_float_pct)} · Short ratio ${this.numericLabel(shortInterest.short_ratio)}`)}</div></section>`;
        }

        renderRiskLiquidity(snapshot) {
            const risk = snapshot.risk_liquidity || {};
            if (risk.status !== 'available') return '';
            const e = this.escapeHtml;
            const signals = Array.isArray(risk.signals) ? risk.signals : [];
            return `<section class="stock-snapshot-risk"><div class="stock-snapshot-risk-header"><div><span>風險與流動性</span><strong>${e(risk.label || '風險摘要')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-risk-grid">${this.riskMetric('Beta', risk.beta?.label, '')}${this.riskMetric('52週回撤', this.percentDeltaLabel(risk.drawdown_from_52w_high_pct), '')}${this.riskMetric('成交量/均量', this.percentDeltaLabel(risk.volume_vs_avg_pct), '')}${this.riskMetric('負債權益比', this.percentLabel(risk.debt_to_equity_pct), '')}${this.riskMetric('流動比率', risk.current_ratio?.label, '')}</div></section>`;
        }

        renderProfitabilityQuality(snapshot) {
            const quality = snapshot.profitability_quality || {};
            if (quality.status !== 'available') return '';
            const e = this.escapeHtml;
            const signals = Array.isArray(quality.signals) ? quality.signals : [];
            return `<section class="stock-snapshot-profitability"><div class="stock-snapshot-profitability-header"><div><span>獲利品質</span><strong>${e(quality.label || '獲利品質')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-profitability-grid">${this.profitabilityMetric('毛利率', this.percentLabel(quality.gross_margin_pct), '')}${this.profitabilityMetric('營業利益率', this.percentLabel(quality.operating_margin_pct), '')}${this.profitabilityMetric('淨利率', this.percentLabel(quality.net_margin_pct), '')}${this.profitabilityMetric('ROE', this.percentLabel(quality.roe_pct), '')}${this.profitabilityMetric('ROA', this.percentLabel(quality.roa_pct), '')}${this.profitabilityMetric('FCF margin', this.percentLabel(quality.fcf_margin_pct), '')}</div></section>`;
        }

        renderDividendProfile(snapshot) {
            const profile = snapshot.dividend_profile || {};
            if (profile.status !== 'available') return '';
            const e = this.escapeHtml;
            const history = profile.history || {};
            const coverage = profile.coverage || {};
            const signals = Array.isArray(profile.signals) ? profile.signals : [];
            return `<section class="stock-snapshot-dividend"><div class="stock-snapshot-dividend-header"><div><span>股利品質</span><strong>${e(profile.label || '股利摘要')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-dividend-grid">${this.dividendMetric('年化股利', profile.annual_dividend?.label, '')}${this.dividendMetric('殖利率', profile.yield?.label, '')}${this.dividendMetric('配息率', profile.payout_ratio?.label, '')}${this.dividendMetric('FCF 覆蓋', this.coverageLabel(coverage.fcf_coverage_ratio), '')}</div>${this.dividendBars(history)}</section>`;
        }

        renderEventCalendar(snapshot) {
            const calendar = snapshot.event_calendar || {};
            const events = Array.isArray(calendar.events) ? calendar.events : [];
            if (calendar.status !== 'available' || !events.length) return '';
            const e = this.escapeHtml;
            return `<section class="stock-snapshot-calendar"><div class="stock-snapshot-calendar-header"><div><span>關鍵日期</span><strong>${e(calendar.label || '近期關鍵日期')}</strong></div><div>${calendar.next_event?.days_until !== undefined ? `<em>${e(this.eventTimingLabel(calendar.next_event))}</em>` : ''}</div></div><div class="stock-snapshot-calendar-grid">${events.slice(0, 4).map(item => this.calendarEvent(item)).join('')}</div></section>`;
        }

        renderAlertSuggestions(snapshot) {
            const alerts = snapshot.alert_suggestions || {};
            const suggestions = Array.isArray(alerts.suggestions) ? alerts.suggestions : [];
            if (alerts.status !== 'available' || !suggestions.length) return '';
            const e = this.escapeHtml;
            return `<section class="stock-snapshot-alerts"><div class="stock-snapshot-alert-header"><div><span>提醒建議</span><strong>${e(alerts.label || '提醒建議')}</strong></div></div><div class="stock-snapshot-alert-grid">${suggestions.slice(0, 4).map((item, index) => this.alertSuggestion(item, index)).join('')}</div></section>`;
        }

        renderFinancialHealth(snapshot) {
            const health = snapshot.financial_health || {};
            const balance = health.balance_sheet || {};
            const chips = Array.isArray(health.highlights) ? health.highlights : [];
            const metrics = [
                ['TTM 營收', health.revenue_ttm?.label, health.revenue_growth?.label ? `營收成長 ${health.revenue_growth.label}` : ''],
                ['毛利率', health.gross_margin?.label, health.operating_margin?.label ? `營業 ${health.operating_margin.label}` : ''],
                ['淨利率', health.profit_margin?.label, health.free_cash_flow?.label ? `自由現金流 ${health.free_cash_flow.label}` : ''],
                ['現金/負債', balance.cash_label, this.balanceDetail(balance)],
            ];
            const hasMetric = metrics.some(item => item[1]);
            if (!hasMetric && !chips.length) return '';
            const e = this.escapeHtml;
            return `<section class="stock-snapshot-fundamentals"><div class="stock-snapshot-fundamentals-header"><div><span>基本面</span><strong>財務健康摘要</strong></div><div>${chips.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-fundamental-grid">${metrics.map(item => this.fundamentalMetric(item[0], item[1], item[2])).join('')}</div></section>`;
        }

        renderFinancialTrends(snapshot) {
            const trends = snapshot.financial_trends || {};
            const rows = Array.isArray(trends.rows) ? trends.rows : [];
            if (trends.status !== 'available' || !rows.length) return '';
            const e = this.escapeHtml;
            const signals = Array.isArray(trends.signals) ? trends.signals : [];
            return `<section class="stock-snapshot-financial-trends"><div class="stock-snapshot-financial-trends-header"><div><span>財報趨勢</span><strong>${e(trends.label || '財報趨勢')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-financial-trend-table" role="table" aria-label="財報趨勢"><div class="stock-snapshot-financial-trend-row is-head" role="row"><span>期間</span><span>營收</span><span>淨利</span><span>FCF</span><span>利潤率</span></div>${rows.slice(-5).map(row => this.financialTrendRow(row)).join('')}</div></section>`;
        }

        renderPeerComparison(snapshot) {
            const comparison = snapshot.peer_comparison || {};
            const target = comparison.target || {};
            const peers = Array.isArray(comparison.peers) ? comparison.peers : [];
            if (!peers.length) return '';
            const summary = comparison.summary || {};
            const rows = [target, ...peers].filter(row => row && (row.ticker || row.name));
            const e = this.escapeHtml;
            return `<section class="stock-snapshot-peers"><div class="stock-snapshot-peers-header"><div><span>同業比較</span><strong>${e(summary.valuation_label || '同業資料')}</strong></div><div><em>P/E vs 同業中位 ${e(this.percentDeltaLabel(summary.pe_vs_peer_median_pct))}</em><em>毛利差 ${e(this.pointDeltaLabel(summary.gross_margin_spread_pct))}</em></div></div><div class="stock-snapshot-peer-table" role="table" aria-label="同業比較"><div class="stock-snapshot-peer-row is-head" role="row"><span>公司</span><span>毛利率</span><span>ROE</span><span>P/E</span><span>P/S</span></div>${rows.map(row => this.peerRow(row)).join('')}</div></section>`;
        }

        renderOwnershipFlow(snapshot) {
            const flow = snapshot.ownership_flow || {};
            if (flow.status !== 'available') return '';
            const e = this.escapeHtml;
            const institutional = flow.institutional || {};
            const margin = flow.margin || {};
            const holders = flow.holders || {};
            const signals = Array.isArray(flow.signals) ? flow.signals : [];
            const categories = Array.isArray(institutional.categories) ? institutional.categories : [];
            const categoryCards = categories.slice(0, 3).map(row => this.ownershipMetric(row.label, this.lotsLabel(row.net_buy_thousand_shares), this.flowWord(row.net_buy_thousand_shares))).join('');
            const marginCards = [
                this.ownershipMetric('融資餘額', this.lotsLabel(margin.margin_balance), margin.short_balance !== null && margin.short_balance !== undefined ? `融券 ${this.lotsLabel(margin.short_balance)}` : ''),
                this.ownershipMetric('千張以上大戶', this.percentLabel(holders.major_holders_gt_1000_lots_pct), holders.retail_holders_lt_50_lots_pct !== null && holders.retail_holders_lt_50_lots_pct !== undefined ? `散戶 ${this.percentLabel(holders.retail_holders_lt_50_lots_pct)}` : ''),
            ].join('');
            return `<section class="stock-snapshot-ownership"><div class="stock-snapshot-ownership-header"><div><span>籌碼結構</span><strong>${e(flow.label || '籌碼摘要')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-ownership-grid">${categoryCards}${marginCards}</div></section>`;
        }

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
        }

        renderEvents(snapshot) {
            const e = this.escapeHtml, events = Array.isArray(snapshot.events) ? snapshot.events : [];
            if (!events.length) return '';
            return `<div class="stock-snapshot-strip">${events.slice(0, 4).map(item => `<span><strong>${e(this.eventLabel(item.type))}</strong>${e(item.label || '-')}</span>`).join('')}</div>`;
        }

        renderNews(snapshot) {
            const e = this.escapeHtml, news = Array.isArray(snapshot.news) ? snapshot.news : [];
            if (!news.length) return '';
            return `<div class="stock-snapshot-news">${news.slice(0, 3).map(item => `<article><strong>${e(item.title)}</strong><span>${e([item.source, item.published_at].filter(Boolean).join(' · '))}</span></article>`).join('')}</div>`;
        }

        renderModes(snapshot) {
            const e = this.escapeHtml, modes = Array.isArray(snapshot.mode_suggestions) ? snapshot.mode_suggestions : [];
            if (!modes.length) return '';
            return `<div class="stock-snapshot-modes">${modes.map(item => `<button type="button" data-stock-snapshot-pipeline="${e(item.pipeline_id)}"><strong>${e(item.label)}</strong><span>${e(item.decision)}</span></button>`).join('')}</div>`;
        }

        renderError(err) {
            const root = this.elements.root;
            if (!root) return;
            root.hidden = false;
            root.innerHTML = `<div class="stock-snapshot-error"><strong>股票快照讀取失敗</strong><span>${this.escapeHtml(err.message || err)}</span></div>`;
        }

        async addToWatchlist(ticker) {
            const normalizedTicker = String(ticker || this.currentTicker || '').trim().toUpperCase();
            if (!normalizedTicker || !this.apiClient || typeof this.apiClient.saveWatchlistItem !== 'function') {
                this.notify.error('追蹤清單目前無法使用。');
                return;
            }
            this.setWatchlistLoading(true);
            try {
                const pipeline = this.resolveWatchlistPipeline();
                await this.apiClient.saveWatchlistItem({
                    ticker: normalizedTicker,
                    pipeline,
                    enabled: true,
                    schedule_slots: ['pre_market'],
                    triggers: []
                });
                this.notify.success?.(`${normalizedTicker} 已加入追蹤清單。`);
                await this.onWatchlistUpdated();
            } catch (err) {
                this.notify.error(`加入追蹤失敗：${err.message || err}`);
            } finally {
                this.setWatchlistLoading(false);
            }
        }

        async applyAlertSuggestion(index) {
            const suggestion = this.lastSnapshot?.alert_suggestions?.suggestions?.[index];
            const ticker = String(this.lastSnapshot?.ticker || this.currentTicker || '').trim().toUpperCase();
            const triggers = Array.isArray(suggestion?.triggers) ? suggestion.triggers : [];
            if (!ticker || !suggestion || !triggers.length || !this.apiClient || typeof this.apiClient.saveWatchlistItem !== 'function') {
                this.notify.error('提醒建議目前無法套用。');
                return;
            }
            this.setAlertLoading(true);
            try {
                await this.apiClient.saveWatchlistItem({
                    ticker,
                    pipeline: suggestion.pipeline || this.resolveWatchlistPipeline(),
                    enabled: true,
                    schedule_slots: Array.isArray(suggestion.schedule_slots) && suggestion.schedule_slots.length ? suggestion.schedule_slots : ['pre_market'],
                    triggers,
                    trigger_source: 'stock_snapshot_suggestion'
                });
                this.notify.success?.(`${ticker} 已套用「${suggestion.label || '提醒'}」。`);
                await this.onWatchlistUpdated();
            } catch (err) {
                this.notify.error(`套用提醒失敗：${err.message || err}`);
            } finally {
                this.setAlertLoading(false);
            }
        }

        resolveWatchlistPipeline() {
            const selected = String(this.getSelectedPipeline() || '').trim();
            if (selected) return selected;
            const suggestions = Array.isArray(this.lastSnapshot?.mode_suggestions) ? this.lastSnapshot.mode_suggestions : [];
            return suggestions[0]?.pipeline_id || 'v1';
        }

        setWatchlistLoading(value) {
            const root = this.elements.root;
            if (!root) return;
            root.querySelectorAll('[data-stock-snapshot-watchlist]').forEach(button => {
                button.disabled = Boolean(value);
                const label = button.querySelector('span');
                if (label) label.textContent = value ? '加入中' : '加入追蹤';
            });
        }

        setAlertLoading(value) {
            const root = this.elements.root;
            if (!root) return;
            root.querySelectorAll?.('[data-stock-snapshot-alert]').forEach(button => {
                button.disabled = Boolean(value);
            });
        }

        metric(label, value, detail) {
            const e = this.escapeHtml;
            return `<div class="stock-snapshot-metric"><span>${e(label)}</span><strong>${e(value ?? '-')}</strong><em>${e(detail || '')}</em></div>`;
        }

        sessionMetric(label, value, detail) {
            const e = this.escapeHtml;
            return `<div><span>${e(label)}</span><strong>${e(value || '-')}</strong><em>${e(detail || '')}</em></div>`;
        }

        fundamentalMetric(label, value, detail) {
            const e = this.escapeHtml;
            return `<div><span>${e(label)}</span><strong>${e(value || '-')}</strong><em>${e(detail || '')}</em></div>`;
        }

        profileFact(label, value) {
            const e = this.escapeHtml;
            return `<div><span>${e(label || '')}</span><strong>${e(value || '-')}</strong></div>`;
        }

        financialTrendRow(row) {
            const e = this.escapeHtml;
            return `<div class="stock-snapshot-financial-trend-row" role="row"><span>${e(row.period || '-')}</span><span><strong>${e(this.financialValueLabel(row.revenue))}</strong><em class="${this.returnClass(row.revenue_yoy_pct)}">${e(this.returnLabel(row.revenue_yoy_pct))}</em></span><span><strong>${e(this.financialValueLabel(row.net_income))}</strong><em class="${this.returnClass(row.net_income_yoy_pct)}">${e(this.returnLabel(row.net_income_yoy_pct))}</em></span><span><strong>${e(this.financialValueLabel(row.free_cash_flow))}</strong><em class="${this.returnClass(row.free_cash_flow_yoy_pct)}">${e(this.returnLabel(row.free_cash_flow_yoy_pct))}</em></span><span><strong>${e(`毛利率 ${this.percentLabel(row.gross_margin_pct)}`)}</strong><em>${e(`營業 ${this.percentLabel(row.operating_margin_pct)}`)}</em></span></div>`;
        }

        technicalMetric(label, value, detail) {
            const e = this.escapeHtml;
            return `<div><span>${e(label)}</span><strong>${e(value || '-')}</strong><em>${e(detail || '')}</em></div>`;
        }

        analystMetric(label, value, detail) {
            const e = this.escapeHtml;
            return `<div><span>${e(label)}</span><strong>${e(value || '-')}</strong><em>${e(detail || '')}</em></div>`;
        }

        earningsMetric(label, value, detail) {
            const e = this.escapeHtml;
            return `<div><span>${e(label)}</span><strong>${e(value || '-')}</strong><em>${e(detail || '')}</em></div>`;
        }

        shareMetric(label, value, detail) {
            const e = this.escapeHtml;
            return `<div><span>${e(label)}</span><strong>${e(value || '-')}</strong><em>${e(detail || '')}</em></div>`;
        }

        riskMetric(label, value, detail) {
            const e = this.escapeHtml;
            return `<div><span>${e(label)}</span><strong>${e(value || '-')}</strong><em>${e(detail || '')}</em></div>`;
        }

        profitabilityMetric(label, value, detail) {
            const e = this.escapeHtml;
            return `<div><span>${e(label)}</span><strong>${e(value || '-')}</strong><em>${e(detail || '')}</em></div>`;
        }

        dividendMetric(label, value, detail) {
            const e = this.escapeHtml;
            return `<div><span>${e(label)}</span><strong>${e(value || '-')}</strong><em>${e(detail || '')}</em></div>`;
        }

        dividendBars(history) {
            const years = Array.isArray(history?.years) ? history.years : [];
            const dividends = Array.isArray(history?.dividends) ? history.dividends : [];
            const rows = years.map((year, index) => ({ year, value: Number(dividends[index]) })).filter(row => Number.isFinite(row.value));
            if (!rows.length) return '';
            const e = this.escapeHtml;
            const max = Math.max(...rows.map(row => row.value), 1);
            return `<div class="stock-snapshot-dividend-bars">${rows.map(row => `<span><i style="height:${Math.max(8, (row.value / max) * 54).toFixed(0)}px"></i><strong>${e(String(row.year))}</strong><em>${e(this.priceLabel(row.value))}</em></span>`).join('')}</div>`;
        }

        calendarEvent(item) {
            const e = this.escapeHtml;
            const detail = [this.eventTimingLabel(item), item.source].filter(Boolean).join(' · ');
            return `<article class="is-${e(item.timing || 'upcoming')}"><span>${e(item.label || this.eventLabel(item.type))}</span><strong>${e(item.date_label || item.date || '-')}</strong><em>${e(detail)}</em></article>`;
        }

        alertSuggestion(item, index) {
            const e = this.escapeHtml;
            return `<article><span>${e(this.alertCategoryLabel(item.category))}</span><strong>${e(item.label || '提醒')}</strong><em>${e(item.detail || '')}</em><button type="button" data-stock-snapshot-alert="${e(String(index))}">套用提醒</button></article>`;
        }

        ownershipMetric(label, value, detail) {
            const e = this.escapeHtml;
            return `<div><span>${e(label)}</span><strong>${e(value || '-')}</strong><em>${e(detail || '')}</em></div>`;
        }

        valuationBand(item) {
            const e = this.escapeHtml;
            return `<div class="stock-snapshot-valuation-band"><span>${e(item.label || '-')}</span><strong>${e(this.priceLabel(item.price))}</strong></div>`;
        }

        peerRow(row) {
            const e = this.escapeHtml;
            const name = [row.name, row.ticker].filter(Boolean).join(' · ');
            return `<div class="stock-snapshot-peer-row ${row.is_target ? 'is-target' : ''}" role="row"><span>${e(name || '-')}</span><span>${e(this.percentLabel(row.gross_margin_pct))}</span><span>${e(this.percentLabel(row.roe_pct))}</span><span>${e(this.multipleLabel(row.pe_ttm))}</span><span>${e(this.multipleLabel(row.ps_ttm))}</span></div>`;
        }

        balanceDetail(balance) {
            const parts = [];
            if (balance?.debt_label) parts.push(`負債 ${balance.debt_label}`);
            if (balance?.debt_to_equity_label) parts.push(`D/E ${balance.debt_to_equity_label}`);
            return parts.join(' · ');
        }

        sparklinePoints(points, width = 120, height = 42) {
            const prices = points.map(item => Number(item.price)).filter(Number.isFinite);
            if (prices.length < 2) return '';
            const min = Math.min(...prices), max = Math.max(...prices), span = max - min || 1;
            return prices.map((price, index) => {
                const x = prices.length === 1 ? 0 : (index / (prices.length - 1)) * width;
                const y = height - 4 - ((price - min) / span) * (height - 8);
                return `${x.toFixed(1)},${y.toFixed(1)}`;
            }).join(' ');
        }

        performanceRange(key, ranges) {
            const source = Array.isArray(ranges) ? ranges : (Array.isArray(this.lastSnapshot?.performance_history?.ranges) ? this.lastSnapshot.performance_history.ranges : []);
            return source.find(item => item.key === key) || null;
        }

        performanceRangeChart(range) {
            if (!range) return '';
            const e = this.escapeHtml;
            const points = Array.isArray(range.points) ? range.points : [];
            return `<div><span>${e(range.label || range.key || '')}</span><strong class="${this.returnClass(range.return_pct)}">${e(this.returnLabel(range.return_pct))}</strong><em>${e(this.priceLabel(range.start_price))} → ${e(this.priceLabel(range.end_price))}</em></div><svg class="stock-snapshot-performance-line" viewBox="0 0 140 52" aria-hidden="true"><polyline points="${e(this.sparklinePoints(points, 140, 52))}" /></svg>`;
        }

        priceLabel(value) {
            const number = Number(value);
            return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '-';
        }

        returnLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            const rounded = this.roundToOneDecimal(number);
            return `${rounded >= 0 ? '+' : ''}${rounded.toFixed(1)}%`;
        }

        signedPriceLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            return `${number >= 0 ? '+' : ''}${number.toFixed(2)}`;
        }

        volumeVsAvgLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            const rounded = this.roundToOneDecimal(number);
            return `${rounded >= 0 ? '+' : ''}${rounded.toFixed(1)}%`;
        }

        positionLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '';
            return `區間 ${number.toFixed(0)}%`;
        }

        percentDeltaLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            const rounded = this.roundToOneDecimal(number);
            return `${rounded >= 0 ? '+' : ''}${rounded.toFixed(1)}%`;
        }

        pointDeltaLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            return `${number >= 0 ? '+' : ''}${number.toFixed(1)}pp`;
        }

        percentLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            return `${number.toFixed(1)}%`;
        }

        multipleLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            return number.toFixed(1);
        }

        numericLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            return Number.isInteger(number) ? number.toLocaleString() : number.toFixed(1);
        }

        roundToOneDecimal(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return number;
            return Math.sign(number || 1) * Math.round(Math.abs(number) * 10) / 10;
        }

        returnClass(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '';
            return number >= 0 ? 'is-positive' : 'is-negative';
        }

        rangeLabel(label, range) {
            if (!range || (range.high === null && range.low === null)) return '';
            return `${label} ${range.low ?? '-'} / ${range.high ?? '-'}`;
        }

        upsideLabel(target) {
            if (!target || target.upside_pct === null || target.upside_pct === undefined) return target?.recommendation || '';
            const value = Number(target.upside_pct);
            return `${value >= 0 ? '+' : ''}${value.toFixed(1)}% ${target.recommendation || ''}`.trim();
        }

        chipStatus(chip) {
            const margin = chip?.margin_short_sales || {}, tdcc = chip?.shareholder_distribution || {};
            return [margin.status === 'success' ? '資券' : '', tdcc.status === 'success' ? '股權分布' : ''].filter(Boolean).join(' · ');
        }

        compact(value) {
            if (value === null || value === undefined || value === '') return '-';
            const number = Number(value);
            if (!Number.isFinite(number)) return String(value ?? '-');
            if (Math.abs(number) >= 100000000) return `${this.compactScaled(number, 100000000)}億`;
            if (Math.abs(number) >= 10000) return `${this.compactScaled(number, 10000)}萬`;
            return number.toLocaleString();
        }

        compactScaled(value, divisor) {
            return (Number(value) / divisor).toLocaleString(undefined, {
                maximumFractionDigits: 1,
                minimumFractionDigits: 1
            });
        }

        shortText(value, limit) {
            const text = String(value || '').trim();
            if (!text || text.length <= limit) return text;
            return `${text.slice(0, Math.max(0, limit - 1)).trim()}…`;
        }

        financialValueLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            return `${number.toLocaleString(undefined, { maximumFractionDigits: 1 })}B`;
        }

        lotsLabel(value) {
            const number = Math.abs(Number(value));
            if (!Number.isFinite(number)) return '-';
            const digits = Number.isInteger(number) ? 0 : 1;
            return `${number.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits })}張`;
        }

        flowWord(value) {
            const number = Number(value);
            if (!Number.isFinite(number) || number === 0) return '持平';
            return number > 0 ? '買超' : '賣超';
        }

        coverageLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            return `${number.toFixed(1)}x`;
        }

        earningsForecastDetail(next, analystCount) {
            const parts = [];
            const timing = this.eventTimingLabel(next);
            if (timing) parts.push(timing);
            const count = Number(analystCount);
            if (Number.isFinite(count)) parts.push(`${count.toFixed(0)} 位分析師`);
            return parts.join(' · ');
        }

        alertCategoryLabel(category) {
            return { event: '事件', price: '價格', fundamental: '基本面' }[category] || '提醒';
        }

        eventTimingLabel(item) {
            const days = Number(item?.days_until);
            if (Number.isFinite(days)) {
                if (days === 0) return '今天';
                return days > 0 ? `${days} 天後` : `${Math.abs(days)} 天前`;
            }
            return item?.timing === 'upcoming' ? '即將到來' : '';
        }

        eventLabel(type) {
            return { monthly_revenue: '月營收', earnings_call: '法說會', earnings_date: '財報日', ex_dividend_date: '除息日', dividend_pay_date: '股利發放日', most_recent_quarter: '最近財報季度' }[type] || '事件';
        }
    }

    window.StockAgentStockSnapshotPanel = { create, StockSnapshotPanel };
})();
