(function () {
    const CATEGORY_LABELS = { institutional_accumulation: '外資投信同步', technical_heat: '股價大漲跌/成交量暴增' };
    const COLUMNS = [
        ['ticker', '股票'], ['score', '分數'], ['bias_pct', '乖離'], ['rsi_14', 'RSI'],
        ['revenue_growth_yoy_pct', '營收 YoY'], ['total_net_buy_shares', '法人買超'], ['watchlist', '狀態']
    ];
    const DEFAULT_FILTERS = { category: '', minScore: 0, revenueGrowthMin: '', revenueGrowthMax: '', rsiMin: '', rsiMax: 90, macdMin: '', macdHistogramMin: '', totalNetBuyMin: '', foreignNetBuyMin: '', investmentTrustNetBuyMin: '', dealerNetBuyMin: '', pageSize: 50 };
    const PARAM_KEYS = { minScore: 'min_score', revenueGrowthMin: 'fundamental_revenue_growth_yoy_min', revenueGrowthMax: 'fundamental_revenue_growth_yoy_max', rsiMin: 'technical_rsi_min', rsiMax: 'technical_rsi_max', macdMin: 'technical_macd_min', macdHistogramMin: 'technical_macd_histogram_min', totalNetBuyMin: 'institutional_total_net_buy_min', foreignNetBuyMin: 'institutional_foreign_net_buy_min', investmentTrustNetBuyMin: 'institutional_investment_trust_net_buy_min', dealerNetBuyMin: 'institutional_dealer_net_buy_min' };
    const NUMBER_CONTROLS = [['revenueGrowthMin', '營收 YoY 下限', '%'], ['revenueGrowthMax', '營收 YoY 上限', '%'], ['rsiMin', 'RSI 下限', ''], ['macdMin', 'MACD 下限', ''], ['macdHistogramMin', 'MACD 柱下限', ''], ['totalNetBuyMin', '法人總買超', '股'], ['foreignNetBuyMin', '外資買超', '股'], ['investmentTrustNetBuyMin', '投信買超', '股'], ['dealerNetBuyMin', '自營商買超', '股']];
    function categoryLabel(value) { return CATEGORY_LABELS[value] || value || 'Auto-Screener'; }
    function selectorEscape(value) { return String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"'); }
    function fallbackPipelineChoices() { return [{ value: 'v1', codeLabel: '模式 A', decisionLabel: '長線研究' }, { value: 'v2', codeLabel: '模式 B', decisionLabel: '部位決策' }, { value: 'v3', codeLabel: '模式 C', decisionLabel: '逆勢風控' }, { value: 'v4', codeLabel: '模式 D', decisionLabel: '事件波段' }]; }
    function dailyTrigger(item) { return (item.triggers || []).find(entry => entry.type === 'daily_screener') || {}; }
    function triggerReason(item) { const trigger = dailyTrigger(item); return item.reason || trigger.reason || item.latest_trigger_event?.message || 'Auto-Screener'; }
    function companyName(item) { const trigger = dailyTrigger(item); return item.company_name || trigger.company_name || trigger.metrics?.company_name || ''; }
    function metric(item, key) { const metrics = item.metrics || dailyTrigger(item).metrics || {}; return key === 'score' ? item.score : metrics[key]; }
    function numberValue(value) { const n = Number(String(value ?? '').replace(/,/g, '')); return Number.isFinite(n) ? n : null; }
    function numericOrBlank(value) { const n = numberValue(value); return n === null ? '' : n; }
    function readFilterValue(input) { return input.type === 'range' || input.type === 'number' || input.dataset.screenerFilter === 'pageSize' ? numericOrBlank(input.value) : input.value; }
    function compactNumber(value) { const n = numberValue(value); return n === null ? '-' : (Math.abs(n) >= 10000 ? `${Math.round(n / 1000).toLocaleString()}張` : n.toLocaleString()); }
    function formatSignedMetric(value, suffix = '%') { const n = numberValue(value); if (n === null) return '<span class="metric-muted">-</span>'; const cls = n > 0 ? 'metric-positive' : (n < 0 ? 'metric-negative' : 'metric-muted'); return `<span class="${cls}">${n > 0 ? '+' : ''}${n.toFixed(Math.abs(n) >= 10 ? 1 : 2)}${suffix}</span>`; }

    window.StockAgentMarketScreenerHelpers = { CATEGORY_LABELS, COLUMNS, DEFAULT_FILTERS, NUMBER_CONTROLS, PARAM_KEYS, categoryLabel, compactNumber, fallbackPipelineChoices, formatSignedMetric, metric, numberValue, readFilterValue, selectorEscape, triggerReason, companyName };
})();
