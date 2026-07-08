(function () {
    const SOURCE_LABELS = {
        market_data: '股價與基本資料', financial_statements: '財報資料', recent_catalysts: '新聞與事件',
        global_market_context: '全球市場脈絡', international_news_context: '國際新聞脈絡', macro_indicators: 'FRED 總經指標', chip_data: '深度籌碼', alternative_data: '另類數據', peer_discovery: '同業比較',
        monthly_revenue: '月營收', institutional_trading: '法人籌碼', dynamic_peer_metrics: '同業指標', pe_river_chart: '估值區間'
    };
    const SOURCE_IMPACT = {
        market_data: '影響目前股價、估值與報告起點', financial_statements: '影響營收、獲利與財務比率',
        recent_catalysts: '補充資料，影響近期題材與風險事件', global_market_context: '補充資料，影響總經、匯率、利率與美股風險偏好判讀',
        international_news_context: '補充資料，影響國際重大新聞與供應鏈事件判讀', macro_indicators: '補充資料，只供總經策略師使用', chip_data: '補充資料，供量化交易員與法證籌碼追蹤使用', alternative_data: '補充資料，供成長預測與財務排雷交叉驗證使用', peer_discovery: '補充資料，影響同業比較與估值參照',
        monthly_revenue: '影響台股月營收判讀', institutional_trading: '影響法人籌碼判讀',
        dynamic_peer_metrics: '影響同業財務與估值指標', pe_river_chart: '影響本益比區間參考'
    };
    const CORE_ANALYSIS_SOURCES = new Set(['market_data', 'financial_statements', 'monthly_revenue', 'institutional_trading', 'twse_official', 'dynamic_peer_metrics', 'pe_river_chart']);
    const LEVEL_WEIGHT = { ok: 0, warning: 1, critical: 2 };
    const EXPECTED_CONTEXT_SOURCES = [
        { source: 'global_market_context', provider: 'yfinance global context', message: '尚未建立檢查樣本；下一次新分析或重新抓取後會更新全球市場脈絡。' },
        { source: 'international_news_context', provider: 'GDELT / Google News RSS', message: '尚未建立檢查樣本；下一次新分析或重新抓取後會更新國際新聞脈絡。' }
    ];

    function providerSlaClass(level) {
        return ['ok', 'warning', 'critical'].includes(level) ? level : 'ok';
    }

    function formatSuccessRate(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return '尚無紀錄';
        return `${Math.round(numeric * 100)}%`;
    }

    function providerSlaWindowLabel(windowKey) {
        const labels = { all: '全部紀錄', last_1h: '近 1 小時', last_24h: '近 24 小時', last_7d: '近 7 天' };
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

    function healthyCountForStats(stats) {
        return Number(stats.success_count || 0) + Number(stats.skipped_fresh_cache_count || 0) + Number(stats.degraded_enrichment_count || 0);
    }
    function availabilityAttemptsForStats(stats) {
        return Number.isFinite(Number(stats.availability_attempts)) ? Number(stats.availability_attempts) : Math.max(0, Number(stats.attempts || 0) - Number(stats.not_configured_count || 0));
    }

    function readableSource(source) {
        return SOURCE_LABELS[source] || String(source || '其他資料');
    }

    function sourceImpact(source) {
        return SOURCE_IMPACT[source] || '影響部分補充資料';
    }

    function sourceIsCore(source) { return CORE_ANALYSIS_SOURCES.has(source); }

    function stateLabel(level, source) {
        if (level === 'critical') return sourceIsCore(source) ? '核心資料可能影響分析' : '補充資料不穩';
        if (level === 'warning') return '需要留意';
        return '可安心使用';
    }
    function rowStateLabel(row) {
        if (row.level === 'ok' && !row.attempts) return '無檢查樣本';
        return stateLabel(row.level, row.source);
    }

    function groupedProviderRows(providers, selectedWindow) {
        const groups = new Map();
        providers.forEach(item => {
            const stats = providerSlaStatsForWindow(item, selectedWindow);
            const source = item.source || 'unknown';
            const current = groups.get(source) || { source, level: 'ok', attempts: 0, availabilityAttempts: 0, healthyCount: 0, totalRecords: 0, providerRows: [], messages: [] };
            const level = providerSlaClass(item.alert_level);
            const attempts = Number(stats.attempts || 0);
            const availabilityAttempts = availabilityAttemptsForStats(stats);
            const healthyCount = healthyCountForStats(stats);
            if ((LEVEL_WEIGHT[level] || 0) > (LEVEL_WEIGHT[current.level] || 0)) current.level = level;
            current.attempts += attempts;
            current.availabilityAttempts += availabilityAttempts;
            current.healthyCount += healthyCount;
            current.totalRecords += Number(stats.total_records || 0);
            if (item.provider) {
                current.providerRows.push({ provider: item.provider, level, attempts, healthyCount, successRate: availabilityAttempts ? healthyCount / availabilityAttempts : NaN,
                    totalRecords: Number(stats.total_records || 0), lastStatus: item.last_status || '', lastMessage: item.alert_message || item.last_message || '' });
            }
            if (item.alert_message || item.last_message) current.messages.push(item.alert_message || item.last_message);
            groups.set(source, current);
        });
        return Array.from(groups.values()).sort((a, b) => {
            const levelDelta = (LEVEL_WEIGHT[b.level] || 0) - (LEVEL_WEIGHT[a.level] || 0);
            return levelDelta || b.attempts - a.attempts;
        });
    }

    function hasSource(rows, source) {
        return rows.some(row => row.source === source);
    }

    function mergeExpectedContextRows(rows) {
        const merged = rows.slice();
        EXPECTED_CONTEXT_SOURCES.forEach(expected => {
            if (hasSource(merged, expected.source)) return;
            merged.push({ source: expected.source, level: 'ok', attempts: 0, availabilityAttempts: 0, healthyCount: 0, totalRecords: 0, messages: [expected.message], expectedContext: true,
                providerRows: [{ provider: expected.provider, level: 'ok', attempts: 0, healthyCount: 0, successRate: NaN, totalRecords: 0, lastStatus: '', lastMessage: expected.message }] });
        });
        return merged;
    }

    function visibleProviderRows(rows) {
        const visible = rows.slice(0, 6);
        EXPECTED_CONTEXT_SOURCES.forEach(expected => {
            const contextRow = rows.find(row => row.source === expected.source);
            if (contextRow && !hasSource(visible, expected.source)) visible.push(contextRow);
        });
        return visible;
    }

    function summaryText(rows, windowLabel, providers) {
        if (!providers.length) return `正式分析流程 · ${windowLabel} · 尚未建立全系統來源紀錄`;
        if (rows.length && rows.every(row => !row.attempts)) return `正式分析流程 · ${windowLabel} · 尚無檢查樣本，請查看 24 小時或全部紀錄`;
        const coreCritical = rows.filter(row => row.level === 'critical' && sourceIsCore(row.source)).length, enrichmentCritical = rows.filter(row => row.level === 'critical' && !sourceIsCore(row.source)).length, warning = rows.filter(row => row.level === 'warning').length;
        if (coreCritical) return `正式分析流程 · ${windowLabel} · ${coreCritical} 類核心資料可能影響分析，建議稍後重試`;
        if (enrichmentCritical) return `正式分析流程 · ${windowLabel} · ${enrichmentCritical} 類補充資料不穩，核心分析仍可進行；需要完整題材或同業資料時再重試`;
        if (warning) return `正式分析流程 · ${windowLabel} · ${warning} 類資料近期不穩，分析時會使用有效快取或備援來源`;
        return `正式分析流程 · ${windowLabel} · 資料抓取穩定，可放心分析`;
    }

    function insightText(row) {
        if (!row.attempts && row.expectedContext) return '尚未建立檢查樣本；下一次新分析或重新抓取後會更新。';
        if (!row.attempts) return '這段時間還沒有用到這類資料。';
        if (row.level === 'critical' && sourceIsCore(row.source)) return `${sourceImpact(row.source)}，這次分析可能需要稍後重跑。`;
        if (row.level === 'critical') return `${sourceImpact(row.source)}；核心分析仍可進行，需要完整補充脈絡時再稍後重試。`;
        if (row.level === 'warning') return `${sourceImpact(row.source)}；近期偶有失敗，分析時會先使用仍有效的快取，必要時嘗試備援來源。`;
        return `${sourceImpact(row.source)}，最近抓取順利。`;
    }

    function providerStatusLabel(status) {
        if (status === 'success') return '成功';
        if (status === 'skipped_fresh_cache') return '有效快取';
        if (status === 'degraded_enrichment') return '降級可用';
        if (status === 'not_configured') return '未設定';
        if (status === 'error') return '失敗';
        if (status === 'unavailable') return '不可用';
        return status || '未記錄';
    }

    function providerDetailsHtml(row, escapeHtml) {
        const providerRows = (row.providerRows || []).slice().sort((a, b) => {
            const levelDelta = (LEVEL_WEIGHT[b.level] || 0) - (LEVEL_WEIGHT[a.level] || 0);
            return levelDelta || Number(b.attempts || 0) - Number(a.attempts || 0);
        }).slice(0, 4);
        if (!providerRows.length) return '';
        return `
            <span class="provider-sla-provider-list" aria-label="來源明細">
                <span class="provider-sla-provider-title">來源明細</span>
                ${providerRows.map(provider => `
                    <span class="provider-sla-provider is-${provider.level}" title="${escapeHtml(provider.lastMessage || '')}">
                        <strong>${escapeHtml(provider.provider)}</strong>
                        <em>${escapeHtml(formatSuccessRate(provider.successRate))} · ${escapeHtml(providerStatusLabel(provider.lastStatus))} · ${escapeHtml(String(provider.attempts || 0))} 次</em>
                    </span>
                `).join('')}
            </span>
        `;
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
        const rows = mergeExpectedContextRows(groupedProviderRows(providers, selectedWindow));
        summaryEl.textContent = summaryText(rows, windowLabel, providers);
        listEl.innerHTML = rows.length
            ? visibleProviderRows(rows).map(row => {
                const successRate = row.availabilityAttempts ? row.healthyCount / row.availabilityAttempts : NaN;
                const recordsLabel = row.totalRecords ? `取得 ${row.totalRecords} 筆資料` : '資料量尚少';
                const checksLabel = row.attempts ? `檢查 ${row.attempts} 次` : '尚未檢查';
                const title = `${readableSource(row.source)}：${rowStateLabel(row)}。${insightText(row)}`;
                return `
                    <span class="provider-sla-chip provider-sla-insight is-${row.level}" title="${escapeHtml(title)}">
                        <span class="provider-sla-insight-top">
                            <strong>${escapeHtml(readableSource(row.source))}</strong>
                            <em>${escapeHtml(rowStateLabel(row))}</em>
                        </span>
                        <span class="provider-sla-detail">${escapeHtml(insightText(row))}</span>
                        <span class="provider-sla-meta">${escapeHtml(recordsLabel)} · 資料取得率 ${escapeHtml(formatSuccessRate(successRate))} · ${escapeHtml(checksLabel)}</span>
                        ${providerDetailsHtml(row, escapeHtml)}
                    </span>
                `;
            }).join('')
            : '<span class="provider-sla-chip is-ok">下一次分析後會更新全系統資料來源狀態</span>';
    }

    window.StockAgentProviderSlaPanel = { render, providerSlaStatsForWindow, providerSlaWindowLabel, groupedProviderRows, mergeExpectedContextRows, visibleProviderRows, sourceIsCore };
})();
