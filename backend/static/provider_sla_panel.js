(function () {
    function providerSlaClass(level) {
        return ['ok', 'warning', 'critical'].includes(level) ? level : 'ok';
    }

    function formatSuccessRate(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return 'N/A';
        return `${Math.round(numeric * 100)}%`;
    }

    function providerSlaWindowLabel(windowKey) {
        const labels = {
            all: '全部紀錄',
            last_1h: '近 1 小時',
            last_24h: '近 24 小時',
            last_7d: '近 7 天'
        };
        return labels[windowKey] || labels.all;
    }

    function providerSlaStatsForWindow(item, selectedWindow) {
        if (item.selected_window && item.selected_window !== 'all') {
            return item;
        }
        if (selectedWindow !== 'all' && item.windows && item.windows[selectedWindow]) {
            return item.windows[selectedWindow];
        }
        return item;
    }

    function render(payload, options) {
        const summaryEl = options.summaryEl;
        const listEl = options.listEl;
        const windowEl = options.windowEl;
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        if (!summaryEl || !listEl) return;

        const providers = payload?.providers || [];
        const alerts = payload?.alerts || [];
        const selectedWindow = windowEl ? windowEl.value : 'all';
        const windowLabel = providerSlaWindowLabel(selectedWindow);
        summaryEl.textContent = alerts.length
            ? `${windowLabel} · ${alerts.length} 個來源需要注意`
            : (providers.length ? `${windowLabel} · 來源狀態正常` : `${windowLabel} · 尚無來源審計紀錄`);
        listEl.innerHTML = providers.length
            ? providers.slice(0, 8).map(item => {
                const stats = providerSlaStatsForWindow(item, selectedWindow);
                const attempts = Number(stats.attempts || 0);
                const attemptsLabel = attempts ? `${attempts} 次` : '無紀錄';
                return `
                    <span class="provider-sla-chip is-${providerSlaClass(item.alert_level)}" title="${escapeHtml(item.alert_message || item.last_message || '')}">
                        ${escapeHtml(item.source || 'unknown')} · ${escapeHtml(item.provider || 'unknown')}
                        <strong>${escapeHtml(formatSuccessRate(stats.success_rate))}</strong>
                        <em>${escapeHtml(attemptsLabel)}</em>
                    </span>
                `;
            }).join('')
            : '<span class="provider-sla-chip is-ok">等待下一次分析紀錄</span>';
    }

    window.StockAgentProviderSlaPanel = {
        render,
        providerSlaStatsForWindow,
        providerSlaWindowLabel
    };
})();
