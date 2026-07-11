(function () {
    const renderMethods = {
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
        },
    };

    window.StockAgentStockSnapshotRenderHelpers = { renderMethods };
})();
