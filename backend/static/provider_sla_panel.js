(function () {
    const SOURCE_LABELS = {
        market_data: '股價與基本資料',
        financial_statements: '財報資料',
        recent_catalysts: '新聞與事件',
        peer_discovery: '同業比較',
        monthly_revenue: '月營收',
        institutional_trading: '法人籌碼',
        dynamic_peer_metrics: '同業指標',
        pe_river_chart: '估值區間'
    };
    const SOURCE_IMPACT = {
        market_data: '影響目前股價、估值與報告起點',
        financial_statements: '影響營收、獲利與財務比率',
        recent_catalysts: '影響近期題材與風險事件',
        peer_discovery: '影響同業比較與估值參照',
        monthly_revenue: '影響台股月營收判讀',
        institutional_trading: '影響法人籌碼判讀',
        dynamic_peer_metrics: '影響同業財務與估值指標',
        pe_river_chart: '影響本益比區間參考'
    };
    const LEVEL_WEIGHT = { ok: 0, warning: 1, critical: 2 };

    function providerSlaClass(level) {
        return ['ok', 'warning', 'critical'].includes(level) ? level : 'ok';
    }

    function formatSuccessRate(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return '尚無紀錄';
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

    function readableSource(source) {
        return SOURCE_LABELS[source] || String(source || '其他資料');
    }

    function sourceImpact(source) {
        return SOURCE_IMPACT[source] || '影響部分補充資料';
    }

    function stateLabel(level) {
        if (level === 'critical') return '可能影響分析';
        if (level === 'warning') return '需要留意';
        return '可安心使用';
    }

    function groupedProviderRows(providers, selectedWindow) {
        const groups = new Map();
        providers.forEach(item => {
            const stats = providerSlaStatsForWindow(item, selectedWindow);
            const source = item.source || 'unknown';
            const current = groups.get(source) || {
                source,
                level: 'ok',
                attempts: 0,
                healthyCount: 0,
                totalRecords: 0,
                providers: [],
                messages: []
            };
            const level = providerSlaClass(item.alert_level);
            if ((LEVEL_WEIGHT[level] || 0) > (LEVEL_WEIGHT[current.level] || 0)) current.level = level;
            current.attempts += Number(stats.attempts || 0);
            current.healthyCount += Number(stats.success_count || 0) + Number(stats.skipped_fresh_cache_count || 0);
            current.totalRecords += Number(stats.total_records || 0);
            if (item.provider) current.providers.push(item.provider);
            if (item.alert_message || item.last_message) current.messages.push(item.alert_message || item.last_message);
            groups.set(source, current);
        });
        return Array.from(groups.values()).sort((a, b) => {
            const levelDelta = (LEVEL_WEIGHT[b.level] || 0) - (LEVEL_WEIGHT[a.level] || 0);
            return levelDelta || b.attempts - a.attempts;
        });
    }

    function summaryText(rows, windowLabel, providers) {
        if (!providers.length) return `正式分析流程 · ${windowLabel} · 尚未建立全系統來源紀錄`;
        const critical = rows.filter(row => row.level === 'critical').length;
        const warning = rows.filter(row => row.level === 'warning').length;
        if (critical) return `正式分析流程 · ${windowLabel} · ${critical} 類資料可能影響分析，建議稍後重試`;
        if (warning) return `正式分析流程 · ${windowLabel} · ${warning} 類資料較不穩，系統會改用快取或備援`;
        return `正式分析流程 · ${windowLabel} · 資料抓取穩定，可放心分析`;
    }

    function insightText(row) {
        if (!row.attempts) return '這段時間還沒有用到這類資料。';
        if (row.level === 'critical') return `${sourceImpact(row.source)}，這次分析可能需要稍後重跑。`;
        if (row.level === 'warning') return `${sourceImpact(row.source)}；系統會優先補快取或其他來源。`;
        return `${sourceImpact(row.source)}，最近抓取順利。`;
    }

    function render(payload, options) {
        const summaryEl = options.summaryEl;
        const listEl = options.listEl;
        const windowEl = options.windowEl;
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        if (!summaryEl || !listEl) return;

        const providers = payload?.providers || [];
        const selectedWindow = windowEl ? windowEl.value : 'all';
        const windowLabel = providerSlaWindowLabel(selectedWindow);
        const rows = groupedProviderRows(providers, selectedWindow);
        summaryEl.textContent = summaryText(rows, windowLabel, providers);
        listEl.innerHTML = rows.length
            ? rows.slice(0, 6).map(row => {
                const successRate = row.attempts ? row.healthyCount / row.attempts : NaN;
                const recordsLabel = row.totalRecords ? `取得 ${row.totalRecords} 筆資料` : '資料量尚少';
                const checksLabel = row.attempts ? `檢查 ${row.attempts} 次` : '尚未檢查';
                const title = `${readableSource(row.source)}：${stateLabel(row.level)}。${insightText(row)}`;
                return `
                    <span class="provider-sla-chip provider-sla-insight is-${row.level}" title="${escapeHtml(title)}">
                        <span class="provider-sla-insight-top">
                            <strong>${escapeHtml(readableSource(row.source))}</strong>
                            <em>${escapeHtml(stateLabel(row.level))}</em>
                        </span>
                        <span class="provider-sla-detail">${escapeHtml(insightText(row))}</span>
                        <span class="provider-sla-meta">${escapeHtml(recordsLabel)} · 資料取得率 ${escapeHtml(formatSuccessRate(successRate))} · ${escapeHtml(checksLabel)}</span>
                    </span>
                `;
            }).join('')
            : '<span class="provider-sla-chip is-ok">下一次分析後會更新全系統資料來源狀態</span>';
    }

    window.StockAgentProviderSlaPanel = {
        render,
        providerSlaStatsForWindow,
        providerSlaWindowLabel,
        groupedProviderRows
    };
})();
