(function () {
    const qualityPolicy = () => window.StockAgentReportQualityPolicy || {};
    function providerSlaOnlyPartial(trust) {
        return Boolean(qualityPolicy().dataTrustProviderSlaOnlyPartial?.(trust));
    }
    function dataTrustLabel(trust) {
        const status = trust && trust.status ? trust.status : 'unknown';
        const labels = {
            fresh: '本報告資料新鮮',
            partial: providerSlaOnlyPartial(trust) ? '本報告來源提醒' : '本報告資料需留意',
            stale: '本報告部分過期',
            error: '本報告來源異常',
            unknown: '本報告未記錄'
        };
        return labels[status] || labels.unknown;
    }
    function dataTrustClass(trust) {
        const status = trust && trust.status ? trust.status : 'unknown';
        return ['fresh', 'partial', 'stale', 'error'].includes(status) ? status : 'unknown';
    }
    function dataTrustReasonLabel(code) {
        const parts = String(code || '').split(':'), base = parts[0], source = parts[1] || '';
        const labels = { fresh_core_sources: '核心資料新鮮', critical_sources_error: '核心來源異常', missing_usable_critical_data: '缺少核心資料', data_source_notes_present: '含口徑註記', provider_sla_critical: '系統來源當時不穩', provider_sla_core_health_notice: '核心來源穩定度提醒', provider_sla_optional_critical: '補充來源穩定度提醒', provider_sla_warning_note: '來源穩定度提醒', missing_data_trust_snapshot: '未記錄報告資料狀態', source_error: '來源異常', source_stale: '來源過期', optional_source_error: '補充來源異常', optional_source_stale: '補充來源過期', optional_source_degraded: '補充來源降級', optional_source_not_configured: '補充來源未設定' };
        const sourceLabels = { market_data: '市場資料', financial_statements: '年度財報', monthly_revenue: '月營收', institutional_trading: '法人籌碼', dynamic_peer_metrics: '同業指標', pe_river_chart: 'P/E 河流圖', recent_catalysts: '近期催化劑', peer_discovery: '同業搜尋', social_sentiment: '社群討論情緒', alternative_data: '另類數據', earnings_call: '法說會資料' };
        return `${labels[base] || base}${source ? `：${sourceLabels[source] || source}` : ''}`;
    }
    function dataTrustReasonSummary(trust) {
        const codes = trust && Array.isArray(trust.reason_codes) ? trust.reason_codes : [], reasons = codes.slice(0, 2).map(dataTrustReasonLabel);
        const scoreReasons = trust && Array.isArray(trust.score_reasons) ? trust.score_reasons : [];
        if (!reasons.length && scoreReasons.length) return scoreReasons.slice(0, 2).join('、');
        return reasons.join('、');
    }
    function dataTrustScoreLabel(trust) {
        const score = trust && Number(trust.score);
        return Number.isFinite(score) ? `${Math.max(0, Math.min(100, Math.round(score)))}分` : '';
    }
    window.StockAgentUiDataTrust = { dataTrustClass, dataTrustLabel, dataTrustReasonSummary, dataTrustScoreLabel, providerSlaOnlyPartial };
})();
