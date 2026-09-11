(function () {
    const SOURCE_LABELS = {
        earnings_call: '法說會資料', sec_edgar: '美國申報文件', social_sentiment: '社群討論', taiwan_open_data: '台灣開放資料', twse_official: '交易所資料', market_data: '股價與基本資料', financial_statements: '財報資料', recent_catalysts: '新聞與事件',
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
    const LEVEL_WEIGHT = { neutral: 0, ok: 1, warning: 2, critical: 3 };
    const EXPECTED_CONTEXT_SOURCES = ['global_market_context', 'international_news_context'];
    const COUNTER_LABELS = {
        fetched_count: '取得資料', empty_count: '未取得資料', failed_count: '失敗／不可用',
        degraded_count: '降級資料', fresh_cache_count: '有效快取', empty_cache_count: '空快取',
        stale_cache_count: '過期快取', unknown_count: '未確認', not_configured_count: '選用來源略過'
    };
    const count = (row, key) => Number.isFinite(Number(row?.[key])) ? Math.max(0, Number(row[key])) : 0;
    function formatSuccessRate(value) {
        if (value === null || value === undefined || !Number.isFinite(Number(value))) return '無抓取樣本';
        const n = Math.max(0, Math.min(1, Number(value)));
        return `${n === 1 ? 100 : Math.min(99.9, Math.round(n * 1000) / 10)}%`;
    }
    function providerSlaWindowLabel(key) {
        return ({all: '已保留紀錄', last_1h: '近 1 小時', last_24h: '近 24 小時', last_7d: '近 7 天'})[key] || '已保留紀錄';
    }
    function readableSource(source) { return SOURCE_LABELS[source] || String(source || '其他資料'); }
    function sourceIsCore(source) { return CORE_ANALYSIS_SOURCES.has(source); }
    function sourceImpact(source) { return SOURCE_IMPACT[source] || '補充分析資料'; }
    function sourceGroupLevel(row) {
        if (count(row, 'failed_count') && sourceIsCore(row.source) && !count(row, 'fetched_count')) return 'critical';
        if (['failed_count', 'empty_count', 'degraded_count', 'stale_cache_count', 'empty_cache_count', 'unknown_count'].some(key => count(row, key))) return 'warning';
        return count(row, 'fetched_count') ? 'ok' : 'neutral';
    }
    function rowStateLabel(row) {
        if (!count(row, 'observations')) return count(row, 'aggregate_count') ? '原始觀測不足' : '無檢查樣本';
        if (row.level === 'critical') return '核心資料可能影響分析';
        if (count(row, 'failed_count')) return '有來源失敗';
        if (count(row, 'unknown_count')) return '有未確認紀錄';
        if (!count(row, 'fetched_count') && (count(row, 'empty_count') || count(row, 'empty_cache_count'))) return '未取得資料';
        if (count(row, 'degraded_count') || count(row, 'stale_cache_count')) return '有降級紀錄';
        if (count(row, 'empty_count') || count(row, 'empty_cache_count')) return '部分未取得';
        if (!count(row, 'fetch_attempts') && count(row, 'fresh_cache_count')) return '僅使用快取';
        if (!count(row, 'fetch_attempts')) return '無抓取樣本';
        return '已取得資料';
    }
    function groupedProviderRows(sources) {
        return sources.map(row => ({...row, level: sourceGroupLevel(row)})).sort((a, b) =>
            LEVEL_WEIGHT[b.level] - LEVEL_WEIGHT[a.level] || count(b, 'failed_count') - count(a, 'failed_count') || String(a.source).localeCompare(String(b.source)));
    }
    function hasSource(rows, source) { return rows.some(row => row.source === source); }
    function mergeExpectedContextRows(rows) {
        return rows.concat(EXPECTED_CONTEXT_SOURCES.filter(source => !hasSource(rows, source)).map(source => ({
            source, level: 'neutral', observations: 0, nonempty_rate: null, providers: [], expectedContext: true
        })));
    }
    function visibleProviderRows(rows) { return rows; }
    function summaryText(rows, windowLabel) {
        if (rows.every(row => !count(row, 'observations') && !count(row, 'aggregate_count'))) return `資料來源觀測 · ${windowLabel} · 無檢查樣本，請查看 24 小時或已保留紀錄`;
        const warning = rows.filter(row => ['warning', 'critical'].includes(row.level)).length;
        return `資料來源觀測 · ${windowLabel} · ${warning ? `${warning} 類資料需留意` : '依實際取得情況列示'}；單份報告請以報告資料可信度與今日工作台為準`;
    }
    function insightText(row) {
        if (!count(row, 'observations')) return count(row, 'aggregate_count')
            ? '僅有彙總結果，缺少原始供應商觀測，無法計算取得資料率。'
            : '尚未建立檢查樣本；下一次抓取後會更新。';
        return `${sourceImpact(row.source)}。空結果僅表示未取得資料，不代表來源正常或沒有事件。`;
    }
    function breakdownText(row) {
        return Object.entries(COUNTER_LABELS).filter(([key]) => count(row, key)).map(([key, label]) => `${label} ${count(row, key)}`).join(' · ') || '無檢查樣本';
    }
    function providerStatusLabel(kind) { return COUNTER_LABELS[kind] || '未確認'; }
    window.StockAgentProviderSlaHelpers = {
        LEVEL_WEIGHT, count, formatSuccessRate, providerSlaWindowLabel, groupedProviderRows, mergeExpectedContextRows,
        visibleProviderRows, readableSource, rowStateLabel, insightText, summaryText, sourceIsCore,
        breakdownText, providerStatusLabel, sourceGroupLevel
    };
})();
