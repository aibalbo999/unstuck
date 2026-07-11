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
    const SOURCE_WARNING_SUCCESS_RATE = 0.8, SOURCE_CRITICAL_SUCCESS_RATE = 0.5;
    const HEALTHY_PROVIDER_STATUSES = new Set(['success', 'skipped_fresh_cache', 'degraded_enrichment']);
    const sourceSets = entries => Object.fromEntries(Object.entries(entries).map(([key, names]) => [key, new Set(names)]));
    const SOURCE_AGGREGATE_PROVIDERS = sourceSets({
        recent_catalysts: ['Recent catalysts providers', 'News/Search providers'], peer_discovery: ['Peer discovery providers'], alternative_data: ['Alternative data providers'], social_sentiment: ['Social Forum Sentiment'], sec_edgar: ['SEC EDGAR Filings'], earnings_call: ['MOPS investor conference'],
        global_market_context: ['Global market context', 'yfinance global context'], international_news_context: ['International news context', 'GDELT / Google News RSS'], macro_indicators: ['FRED macro indicators'], chip_data: ['TDCC/TWSE chip data'], taiwan_open_data: ['Taiwan Open Data', 'Taiwan Open Data (Exchange Rates)']
    });
    const EXPECTED_CONTEXT_SOURCES = [{ source: 'global_market_context', provider: 'yfinance global context', message: '尚未建立檢查樣本；下一次新分析或重新抓取後會更新全球市場脈絡。' }, { source: 'international_news_context', provider: 'GDELT / Google News RSS', message: '尚未建立檢查樣本；下一次新分析或重新抓取後會更新國際新聞脈絡。' }];

    function providerSlaClass(level) { return ['ok', 'warning', 'critical'].includes(level) ? level : 'ok'; }
    function formatSuccessRate(value) { const numeric = Number(value); return Number.isFinite(numeric) ? `${Math.round(numeric * 100)}%` : '尚無紀錄'; }
    function providerSlaWindowLabel(windowKey) { const labels = { all: '全部紀錄', last_1h: '近 1 小時', last_24h: '近 24 小時', last_7d: '近 7 天' }; return labels[windowKey] || labels.all; }
    function providerSlaStatsForWindow(item, selectedWindow) {
        if (item.selected_window && item.selected_window !== 'all') return item;
        if (selectedWindow !== 'all' && item.windows && item.windows[selectedWindow]) return item.windows[selectedWindow];
        return item;
    }

    function healthyCountForStats(stats) { return Number(stats.success_count || 0) + Number(stats.skipped_fresh_cache_count || 0) + Number(stats.degraded_enrichment_count || 0); }
    function availabilityAttemptsForStats(stats) { return Number.isFinite(Number(stats.availability_attempts)) ? Number(stats.availability_attempts) : Math.max(0, Number(stats.attempts || 0) - Number(stats.not_configured_count || 0)); }
    function readableSource(source) { return SOURCE_LABELS[source] || String(source || '其他資料'); }
    function sourceImpact(source) { return SOURCE_IMPACT[source] || '影響部分補充資料'; }
    function sourceIsCore(source) { return CORE_ANALYSIS_SOURCES.has(source); }
    function providerStatusIsHealthy(status) { return HEALTHY_PROVIDER_STATUSES.has(String(status || '')); }
    function providerHasHealthyEvidence(provider) { return providerStatusIsHealthy(provider.lastStatus) && (Number(provider.totalRecords || 0) > 0 || provider.lastStatus === 'degraded_enrichment'); }
    function isAggregateProviderForSource(source, provider) { const names = SOURCE_AGGREGATE_PROVIDERS[source]; return Boolean(names && names.has(String(provider || ''))); }
    function hasHealthySourceEvidence(group) { return (Number(group.healthyCount || 0) > 0 && Number(group.totalRecords || 0) > 0) || (group.providerRows || []).some(providerHasHealthyEvidence); }
    function hasHealthyAggregateEvidence(group) { return (group.providerRows || []).some(provider => isAggregateProviderForSource(group.source, provider.provider) && providerHasHealthyEvidence(provider)); }
    function hasLatestHealthyLiveProvider(group) { return (group.providerRows || []).some(provider => provider.provider !== 'cache' && providerHasHealthyEvidence(provider)); }
    function bestLiveProviderSuccessRate(group) {
        const liveRows = (group.providerRows || []).filter(provider => provider.provider !== 'cache' && Number(provider.totalRecords || 0) > 0);
        if (!liveRows.length) return NaN;
        return Math.max(...liveRows.map(provider => Number(provider.successRate)).filter(Number.isFinite));
    }

    function sourceGroupLevel(group) {
        if (hasHealthyAggregateEvidence(group)) return 'ok';
        if (hasLatestHealthyLiveProvider(group)) return 'ok';
        const bestLiveRate = bestLiveProviderSuccessRate(group);
        if (Number.isFinite(bestLiveRate) && bestLiveRate >= SOURCE_WARNING_SUCCESS_RATE) return 'ok';
        const availabilityAttempts = Number(group.availabilityAttempts || 0);
        const healthyCount = Number(group.healthyCount || 0);
        const successRate = availabilityAttempts ? healthyCount / availabilityAttempts : NaN;
        const worstProviderLevel = group.worstProviderLevel || 'ok';
        let level = 'ok';
        if (availabilityAttempts >= 3 && Number.isFinite(successRate) && successRate < SOURCE_CRITICAL_SUCCESS_RATE) {
            level = 'critical';
        } else if (availabilityAttempts >= 3 && Number.isFinite(successRate) && successRate < SOURCE_WARNING_SUCCESS_RATE) {
            level = 'warning';
        }
        if ((LEVEL_WEIGHT[worstProviderLevel] || 0) > 0 && level === 'ok' && !hasHealthySourceEvidence(group)) level = 'warning';
        if (!availabilityAttempts && (LEVEL_WEIGHT[worstProviderLevel] || 0) > 0 && !hasHealthySourceEvidence(group)) level = 'warning';
        if (!sourceIsCore(group.source) && level === 'critical') return 'warning';
        return level;
    }

    function stateLabel(level, source) { if (level === 'critical') return sourceIsCore(source) ? '核心資料可能影響分析' : '補充資料不穩'; return level === 'warning' ? '需要留意' : '可安心使用'; }
    function rowStateLabel(row) { if (row.level === 'ok' && !row.attempts) return '無檢查樣本'; if (row.level === 'ok' && Number(row.healthyCount || 0) > 0 && !Number(row.totalRecords || 0)) return '無新增資料'; return stateLabel(row.level, row.source); }

    function groupedProviderRows(providers, selectedWindow) {
        const groups = new Map();
        providers.forEach(item => {
            const stats = providerSlaStatsForWindow(item, selectedWindow);
            const source = item.source || 'unknown';
            const current = groups.get(source) || { source, level: 'ok', worstProviderLevel: 'ok', attempts: 0, availabilityAttempts: 0, healthyCount: 0, totalRecords: 0, providerRows: [], messages: [] };
            const level = providerSlaClass(item.alert_level);
            const attempts = Number(stats.attempts || 0);
            const availabilityAttempts = availabilityAttemptsForStats(stats);
            const healthyCount = healthyCountForStats(stats);
            if ((LEVEL_WEIGHT[level] || 0) > (LEVEL_WEIGHT[current.worstProviderLevel] || 0)) current.worstProviderLevel = level;
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
        return Array.from(groups.values()).map(group => ({ ...group, level: sourceGroupLevel(group) })).sort((a, b) => {
            const levelDelta = (LEVEL_WEIGHT[b.level] || 0) - (LEVEL_WEIGHT[a.level] || 0);
            return levelDelta || b.attempts - a.attempts;
        });
    }

    function hasSource(rows, source) { return rows.some(row => row.source === source); }
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
        if (row.level === 'ok' && Number(row.healthyCount || 0) > 0 && !Number(row.totalRecords || 0)) return `${sourceImpact(row.source)}；本次沒有新增可用記錄，但來源回應正常或空結果可接受。`;
        if (row.level === 'critical' && sourceIsCore(row.source)) return `${sourceImpact(row.source)}，這次分析可能需要稍後重跑。`;
        if (row.level === 'critical') return `${sourceImpact(row.source)}；核心分析仍可進行，需要完整補充脈絡時再稍後重試。`;
        if (row.level === 'warning') return `${sourceImpact(row.source)}；近期偶有失敗，分析時會先使用仍有效的快取，必要時嘗試備援來源。`;
        return `${sourceImpact(row.source)}，最近抓取順利。`;
    }

    function providerStatusLabel(status, provider, sourceOk) { if (sourceOk && status === 'unavailable') return Number(provider.totalRecords || 0) > 0 ? '已由備援覆蓋' : '無新增資料'; return ({ success: '成功', skipped_fresh_cache: '有效快取', degraded_enrichment: '降級可用', not_configured: '選用來源略過', error: '失敗', unavailable: '不可用' })[status] || status || '未記錄'; }

    window.StockAgentProviderSlaHelpers = { LEVEL_WEIGHT, formatSuccessRate, providerSlaStatsForWindow, providerSlaWindowLabel, groupedProviderRows, mergeExpectedContextRows, visibleProviderRows, readableSource, rowStateLabel, insightText, summaryText, sourceIsCore, providerStatusIsHealthy, providerStatusLabel };
})();
