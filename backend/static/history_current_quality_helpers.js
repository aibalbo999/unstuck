(function () {
    const statusLabels = { passed: '符合', warning: '警示', blocked: '阻斷', unknown: '無法判定' };

    function positiveInteger(value) {
        const count = Number(value);
        return Number.isFinite(count) && Number.isInteger(count) && count > 0 ? count : null;
    }

    function validated(summary) {
        const conformance = summary?.report_conformance_by_status || {};
        const content = summary?.content_credibility_by_status || {};
        const evidence = summary?.evidence_exit_gate_by_verdict || {};
        const audited = Number(summary?.audited_reports);
        const nonPassed = Number(summary?.non_passed_reports);
        const total = Number(summary?.items_total);
        const returned = Number(summary?.items_returned);
        const items = Array.isArray(summary?.items) ? summary.items : [];
        const count = (values, keys = ['passed', 'warning', 'blocked', 'unknown']) => values && typeof values === 'object' && !Array.isArray(values) && keys.every(key => Number.isFinite(Number(values[key])) && Number.isInteger(Number(values[key])) && Number(values[key]) >= 0) && Object.keys(values).every(key => keys.includes(key));
        const validTarget = item => item && typeof item === 'object' && !Array.isArray(item) && typeof item.filename === 'string' && item.filename.trim() !== '' && ['passed', 'warning', 'blocked', 'unknown'].includes(item.report_conformance_status) && ['passed', 'warning', 'blocked', 'unknown'].includes(item.content_credibility_status) && ['approved', 'caution', 'rejected', 'unknown'].includes(item.evidence_exit_gate_verdict) && (item.report_conformance_status !== 'passed' || item.content_credibility_status !== 'passed' || item.evidence_exit_gate_verdict !== 'approved');
        if (summary?.schema_version !== 'report_current_quality_summary.v1' || summary?.scope !== 'historical_filter_current_latest' || summary?.selection_basis !== 'latest_per_ticker_pipeline' || ![audited, nonPassed, total, returned].every(value => Number.isFinite(value) && Number.isInteger(value)) || audited < 0 || nonPassed < 0 || nonPassed > audited || total !== nonPassed || returned < 0 || returned > total || returned !== items.length || !items.every(validTarget) || !count(conformance) || !count(content) || !count(evidence, ['approved', 'caution', 'rejected', 'unknown']) || Object.values(conformance).reduce((sum, value) => sum + Number(value), 0) !== audited || Object.values(content).reduce((sum, value) => sum + Number(value), 0) !== audited || Object.values(evidence).reduce((sum, value) => sum + Number(value), 0) !== audited) return null;
        return { summary, conformance, content, evidence, audited, nonPassed };
    }

    function render(summary, escapeHtml) {
        const data = validated(summary);
        if (!data) return '';
        const e = escapeHtml || (value => String(value ?? ''));
        const filters = summary.filters && typeof summary.filters === 'object' ? summary.filters : {};
        const query = String(filters.q || '').trim();
        const pipeline = String(filters.pipeline || 'all').trim().toLowerCase() || 'all';
        const filterText = [query ? `查詢：${query}` : '', pipeline !== 'all' ? `模式：${pipeline}` : ''].filter(Boolean).join('；');
        const scope = filterText ? `目前版本品質（${filterText}；只看最新版本）` : '目前版本品質（只看最新版本）';
        const conformance = ['passed', 'warning', 'blocked', 'unknown'].map(key => `${statusLabels[key]} ${Math.floor(Number(data.conformance[key]))}`).join('、');
        const contentAttention = Math.floor(Number(data.content.warning)) + Math.floor(Number(data.content.blocked));
        const evidenceAttention = Math.floor(Number(data.evidence.caution)) + Math.floor(Number(data.evidence.rejected));
        const failedCount = positiveInteger(summary.evidence_failed_count), evidenceFailureSummary = failedCount !== null ? `證據數值不一致 ${failedCount}` : '';
        const evidenceMismatchFreshnessSummary = window.StockAgentReportQualityEvidence?.formatEvidenceMismatchFreshnessSummary?.(summary.evidence_mismatch_claims_by_freshness, summary.evidence_mismatch_reports_by_freshness) || '';
        const evidenceReasonSummary = window.StockAgentReportQualityEvidence?.formatUnverifiableReasonSummary?.(summary.evidence_unverifiable_reason_counts) || '';
        const evidenceReasonFreshnessSummary = window.StockAgentReportQualityEvidence?.formatUnverifiableReasonFreshnessSummary?.(summary.evidence_unverifiable_reason_counts_by_freshness, summary.evidence_unverifiable_reports_by_freshness, summary.evidence_unverifiable_claims_by_freshness) || '';
        const blockerSummary = window.StockAgentReportQualityEvidence?.formatQualityBlockerSummary?.(summary.report_conformance_blocker_counts, summary.content_credibility_blocker_counts) || '';
        const contentBlockerFreshnessSummary = window.StockAgentReportQualityEvidence?.formatContentBlockerFreshnessSummary?.(summary.content_credibility_blocker_reports_by_freshness) || '';
        const qualityActionSummary = window.StockAgentReportQualityActionScope?.formatQualityActionProjectionSummary?.(summary.quality_gate_action_counts, summary.quality_gate_action_scope, summary.quality_gate_action_counts_by_freshness) || window.StockAgentReportQualityEvidence?.formatQualityActionSummary?.(summary.quality_gate_action_counts) || '';
        const evidenceDetail = [evidenceFailureSummary, evidenceMismatchFreshnessSummary, evidenceReasonSummary, evidenceReasonFreshnessSummary, blockerSummary, contentBlockerFreshnessSummary, qualityActionSummary].filter(Boolean).join('；');
        return `<em class="history-quality-audit-current-summary">${e(scope)}：${e(`一致性 ${conformance}；內容可信度需注意 ${contentAttention}；證據關卡需注意 ${evidenceAttention}；非通過 ${data.nonPassed}${evidenceDetail ? `；${evidenceDetail}` : ''}`)}</em>`;
    }

    window.StockAgentHistoricalCurrentQualityHelpers = { render, validated };
})();
