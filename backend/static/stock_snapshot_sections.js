(function () {
    const sectionMethods = {
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
        },

        renderFinancialTrends(snapshot) {
            const trends = snapshot.financial_trends || {};
            const rows = Array.isArray(trends.rows) ? trends.rows : [];
            if (trends.status !== 'available' || !rows.length) return '';
            const e = this.escapeHtml;
            const signals = Array.isArray(trends.signals) ? trends.signals : [];
            return `<section class="stock-snapshot-financial-trends"><div class="stock-snapshot-financial-trends-header"><div><span>財報趨勢</span><strong>${e(trends.label || '財報趨勢')}</strong></div><div>${signals.map(item => `<em>${e(item)}</em>`).join('')}</div></div><div class="stock-snapshot-financial-trend-table" role="table" aria-label="財報趨勢"><div class="stock-snapshot-financial-trend-row is-head" role="row"><span>期間</span><span>營收</span><span>淨利</span><span>FCF</span><span>利潤率</span></div>${rows.slice(-5).map(row => this.financialTrendRow(row)).join('')}</div></section>`;
        },

        renderPeerComparison(snapshot) {
            const comparison = snapshot.peer_comparison || {};
            const target = comparison.target || {};
            const peers = Array.isArray(comparison.peers) ? comparison.peers : [];
            if (!peers.length) return '';
            const summary = comparison.summary || {};
            const rows = [target, ...peers].filter(row => row && (row.ticker || row.name));
            const e = this.escapeHtml;
            return `<section class="stock-snapshot-peers"><div class="stock-snapshot-peers-header"><div><span>同業比較</span><strong>${e(summary.valuation_label || '同業資料')}</strong></div><div><em>P/E vs 同業中位 ${e(this.percentDeltaLabel(summary.pe_vs_peer_median_pct))}</em><em>毛利差 ${e(this.pointDeltaLabel(summary.gross_margin_spread_pct))}</em></div></div><div class="stock-snapshot-peer-table" role="table" aria-label="同業比較"><div class="stock-snapshot-peer-row is-head" role="row"><span>公司</span><span>毛利率</span><span>ROE</span><span>P/E</span><span>P/S</span></div>${rows.map(row => this.peerRow(row)).join('')}</div></section>`;
        },

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
    };

    window.StockAgentStockSnapshotSections = { sectionMethods };
})();
