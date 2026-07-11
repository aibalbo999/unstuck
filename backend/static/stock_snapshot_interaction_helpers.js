(function () {
    const interactionMethods = {
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
        },
    };

    window.StockAgentStockSnapshotInteractionHelpers = { interactionMethods };
})();
