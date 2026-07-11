(function () {
    const numericMethods = window.StockAgentStockSnapshotNumericFormatHelpers?.numericMethods || {};
    const domainFormatMethods = window.StockAgentStockSnapshotDomainFormatHelpers?.domainMethods || {};
    const performanceMethods = window.StockAgentStockSnapshotPerformanceHelpers?.performanceMethods || {};
    const domainLabelMethods = {
        rangeLabel(label, range) {
            if (!range || (range.high === null && range.low === null)) return '';
            return `${label} ${range.low ?? '-'} / ${range.high ?? '-'}`;
        },
        upsideLabel(target) {
            if (!target || target.upside_pct === null || target.upside_pct === undefined) return target?.recommendation || '';
            const value = Number(target.upside_pct);
            return `${value >= 0 ? '+' : ''}${value.toFixed(1)}% ${target.recommendation || ''}`.trim();
        },
        chipStatus(chip) {
            const margin = chip?.margin_short_sales || {}, tdcc = chip?.shareholder_distribution || {};
            return [margin.status === 'success' ? '資券' : '', tdcc.status === 'success' ? '股權分布' : ''].filter(Boolean).join(' · ');
        },
        shortText(value, limit) {
            const text = String(value || '').trim();
            if (!text || text.length <= limit) return text;
            return `${text.slice(0, Math.max(0, limit - 1)).trim()}…`;
        },
        earningsForecastDetail(next, analystCount) {
            const parts = [];
            const timing = this.eventTimingLabel(next);
            if (timing) parts.push(timing);
            const count = Number(analystCount);
            if (Number.isFinite(count)) parts.push(`${count.toFixed(0)} 位分析師`);
            return parts.join(' · ');
        },
        alertCategoryLabel(category) {
            return { event: '事件', price: '價格', fundamental: '基本面' }[category] || '提醒';
        },
        eventTimingLabel(item) {
            const days = Number(item?.days_until);
            if (Number.isFinite(days)) {
                if (days === 0) return '今天';
                return days > 0 ? `${days} 天後` : `${Math.abs(days)} 天前`;
            }
            return item?.timing === 'upcoming' ? '即將到來' : '';
        },
        eventLabel(type) {
            return { monthly_revenue: '月營收', earnings_call: '法說會', earnings_date: '財報日', ex_dividend_date: '除息日', dividend_pay_date: '股利發放日', most_recent_quarter: '最近財報季度' }[type] || '事件';
        }
    };

    const panelMethods = { ...numericMethods, ...domainFormatMethods, ...performanceMethods, ...domainLabelMethods };
    window.StockAgentStockSnapshotFormatHelpers = { panelMethods };
})();
