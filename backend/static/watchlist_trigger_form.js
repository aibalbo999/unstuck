(function () {
    function byId(id) { return document.getElementById(id); }
    function checked(id) { return Boolean(byId(id)?.checked); }
    function num(id, fallback) {
        const value = Number(byId(id)?.value);
        return Number.isFinite(value) && value > 0 ? value : fallback;
    }

    function payload() {
        const triggers = [];
        if (checked('watchlist-trigger-sma')) triggers.push({ type: 'price_below_sma', sma_days: num('watchlist-trigger-sma-days', 60) });
        if (checked('watchlist-trigger-foreign')) triggers.push({
            type: 'foreign_sell_streak',
            days: num('watchlist-trigger-foreign-days', 3),
            min_lots: num('watchlist-trigger-foreign-lots', 1000)
        });
        if (checked('watchlist-trigger-vix')) triggers.push({ type: 'vix_above', threshold: num('watchlist-trigger-vix-threshold', 30) });
        if (checked('watchlist-trigger-revenue')) triggers.push({ type: 'revenue_record_high' });
        return triggers;
    }

    function reset() {
        ['watchlist-trigger-sma', 'watchlist-trigger-foreign', 'watchlist-trigger-vix', 'watchlist-trigger-revenue'].forEach(id => {
            const el = byId(id);
            if (el) el.checked = false;
        });
    }

    function renderItem(item, escapeHtml) {
        const triggers = item.triggers || [];
        const event = item.latest_trigger_event || {};
        const names = triggers.map(trigger => trigger.type).join('、') || '未設定觸發條件';
        const eventText = event.trigger_type ? `${event.trigger_type} · ${event.message || ''}` : '尚無事件';
        return `
            <span class="watchlist-trigger-summary">${escapeHtml(names)}</span>
            <span class="watchlist-trigger-event">${escapeHtml(eventText)}</span>
        `;
    }

    window.StockAgentWatchlistTriggerForm = { payload, renderItem, reset };
})();
