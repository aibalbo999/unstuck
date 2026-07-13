(function () {
    const performanceMethods = {
        sparklinePoints(points, width = 120, height = 42) {
            const prices = points.map(item => Number(item.price)).filter(Number.isFinite);
            if (prices.length < 2) return '';
            const min = Math.min(...prices), max = Math.max(...prices), span = max - min || 1;
            return prices.map((price, index) => {
                const x = prices.length === 1 ? 0 : (index / (prices.length - 1)) * width;
                const y = height - 4 - ((price - min) / span) * (height - 8);
                return `${x.toFixed(1)},${y.toFixed(1)}`;
            }).join(' ');
        },
        performanceRange(key, ranges) {
            const source = Array.isArray(ranges) ? ranges : (Array.isArray(this.lastSnapshot?.performance_history?.ranges) ? this.lastSnapshot.performance_history.ranges : []);
            return source.find(item => item.key === key) || null;
        },
        performanceRangeChart(range) {
            if (!range) return '';
            const e = this.escapeHtml;
            const points = Array.isArray(range.points) ? range.points : [];
            return `<div><span>${e(range.label || range.key || '')}</span><strong class="${this.returnClass(range.return_pct)}">${e(this.returnLabel(range.return_pct))}</strong><em>${e(this.priceLabel(range.start_price))} → ${e(this.priceLabel(range.end_price))}</em></div><svg class="stock-snapshot-performance-line" viewBox="0 0 140 52" aria-hidden="true"><polyline points="${e(this.sparklinePoints(points, 140, 52))}" /></svg>`;
        }
    };

    window.StockAgentStockSnapshotPerformanceHelpers = { performanceMethods };
})();
