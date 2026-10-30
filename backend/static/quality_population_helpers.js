(function () {
    const categories = { calendar_session_integrity: '交易日／輸入完整性', observation_freshness: '觀測日期／時效', source_evidence_gap: '來源／期間／口徑缺證', consistency_guardrail: '論述一致性攔截', unknown: '待分類核對' };
    const warnings = { v4_raw_fcf_period_unverified: '即期FCF期間未核', v4_preserved_quote_fcf_period_unverified: '保存quote期間未核', v4_latest_completed_session_unconfirmed: '最新交易日未齊', non_fresh_data_trust: '資料時效不足', v4_institutional_observation_unaligned: '法人與行情日期未齊', v4_volume_scope_mismatch: '成交量口徑不同', v4_market_observation_lag: '行情日期落後', v4_price_adjustment_basis_unknown: '價格調整基準未核', v4_institutional_primary_source_unverified: '法人原件未核', non_approved_evidence_gate: '證據未完全通過' };
    const count = value => typeof value === 'number' && Number.isInteger(value) && value >= 0;
    function formatQualityPopulationSummary(summary) {
        const denominator = summary?.denominator, cohorts = summary?.report_date_cohorts;
        if (!denominator || denominator.unit !== 'ticker_pipeline_latest_report' || denominator.count !== summary.audited_reports || !count(denominator.count) || cohorts?.timezone !== 'Asia/Taipei') return '';
        const values = cohorts.counts || {}, keys = ['today', 'older', 'future', 'unknown'];
        if (!keys.every(key => count(values[key])) || keys.reduce((sum, key) => sum + values[key], 0) !== denominator.count) return '';
        return `範圍：股票×流程最新版 ${denominator.count} 份（台北日期 ${cohorts.as_of_date}；今日版本 ${values.today}、較舊 ${values.older}、未來日期 ${values.future}、日期未知 ${values.unknown}）；不是今日生成數或股票檔數`;
    }
    function formatQualityReasonClassification(summary) {
        const classification = summary?.reason_classification, total = summary?.audited_reports;
        if (classification?.schema !== 'report_quality_reason_classification.v1' || classification.counts_may_overlap !== true || classification.does_not_establish_root_cause !== true || !count(total)) return '';
        const pairs = Object.entries(classification.reports_by_category || {});
        if (!pairs.length || !pairs.every(([key, value]) => key in categories && count(value) && value <= total)) return '';
        return `原因分類（份數可重疊）：${pairs.map(([key, value]) => `${categories[key]} ${value}`).join('、')}；分類不等於程式故障或誤攔判定`;
    }
    function formatQualityWarningSummary(counts) {
        if (!counts || typeof counts !== 'object' || Array.isArray(counts)) return '';
        const pairs = Object.entries(counts).filter(([, value]) => count(value) && value > 0).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
        return pairs.length ? `內容警示（每碼每份一次、原因可重疊）：${pairs.map(([key, value]) => `${warnings[key] || key} ${value}`).join('、')}` : '';
    }
    window.StockAgentReportQualityEvidence = { ...(window.StockAgentReportQualityEvidence || {}), formatQualityPopulationSummary, formatQualityReasonClassification, formatQualityWarningSummary };
})();
