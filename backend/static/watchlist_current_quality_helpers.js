(function () {
    const statusLabels = { passed: '符合', warning: '警示', blocked: '阻斷', unknown: '無法判定' };
    const evidenceLabels = { approved: '核准', caution: '需注意', rejected: '拒絕', unknown: '無法判定' };

    function validated(audit) {
        const summary = audit?.current_quality_summary || {}, conformance = summary.report_conformance_by_status || {}, content = summary.content_credibility_by_status || {}, evidence = summary.evidence_exit_gate_by_verdict || {};
        const audited = Number(summary.audited_reports), nonPassed = Number(summary.non_passed_reports), total = Number(summary.items_total), returned = Number(summary.items_returned);
        const items = Array.isArray(summary.items) ? summary.items : [];
        const count = values => ['passed', 'warning', 'blocked', 'unknown'].every(key => Number.isFinite(Number(values[key])) && Number.isInteger(Number(values[key])) && Number(values[key]) >= 0);
        if (summary.schema_version !== 'report_current_quality_summary.v1' || summary.scope !== 'all_indexed_reports' || summary.selection_basis !== 'latest_per_ticker_pipeline' || ![audited, nonPassed, total, returned].every(value => Number.isFinite(value) && Number.isInteger(value)) || audited < 0 || nonPassed < 0 || total !== nonPassed || returned < 0 || returned > total || returned !== items.length || !count(conformance) || !count(content) || !['approved', 'caution', 'rejected', 'unknown'].every(key => Number.isFinite(Number(evidence[key])) && Number.isInteger(Number(evidence[key])) && Number(evidence[key]) >= 0) || Object.values(conformance).reduce((sum, value) => sum + Number(value), 0) !== audited || Object.values(content).reduce((sum, value) => sum + Number(value), 0) !== audited || Object.values(evidence).reduce((sum, value) => sum + Number(value), 0) !== audited) return null;
        return { summary, conformance, content, evidence, audited, nonPassed, total, returned, items };
    }

    function summary(audit) {
        const data = validated(audit);
        if (!data) return '';
        const conformance = ['passed', 'warning', 'blocked', 'unknown'].map(key => `${statusLabels[key]} ${Math.floor(Number(data.conformance[key]))}`).join('、');
        const contentWarnings = Math.floor(Number(data.content.warning)), contentBlocked = Math.floor(Number(data.content.blocked));
        const evidenceAttention = Math.floor(Number(data.evidence.caution)) + Math.floor(Number(data.evidence.rejected));
        const failedCount = Number(data.summary.evidence_failed_count), evidenceFailureSummary = Number.isFinite(failedCount) && failedCount > 0 ? `證據數值不一致 ${Math.floor(failedCount)}` : '';
        const evidenceMismatchFreshnessSummary = window.StockAgentReportQualityEvidence?.formatEvidenceMismatchFreshnessSummary?.(data.summary.evidence_mismatch_claims_by_freshness, data.summary.evidence_mismatch_reports_by_freshness) || '';
        const evidenceReasonSummary = window.StockAgentReportQualityEvidence?.formatUnverifiableReasonSummary?.(data.summary.evidence_unverifiable_reason_counts) || '';
        const evidenceReasonFreshnessSummary = window.StockAgentReportQualityEvidence?.formatUnverifiableReasonFreshnessSummary?.(data.summary.evidence_unverifiable_reason_counts_by_freshness, data.summary.evidence_unverifiable_reports_by_freshness, data.summary.evidence_unverifiable_claims_by_freshness) || '';
        const blockerSummary = window.StockAgentReportQualityEvidence?.formatQualityBlockerSummary?.(data.summary.report_conformance_blocker_counts, data.summary.content_credibility_blocker_counts) || '';
        const contentBlockerFreshnessSummary = window.StockAgentReportQualityEvidence?.formatContentBlockerFreshnessSummary?.(data.summary.content_credibility_blocker_reports_by_freshness) || '';
        const qualityActionSummary = window.StockAgentReportQualityActionScope?.formatQualityActionProjectionSummary?.(data.summary.quality_gate_action_counts, data.summary.quality_gate_action_scope, data.summary.quality_gate_action_counts_by_freshness) || window.StockAgentReportQualityEvidence?.formatQualityActionSummary?.(data.summary.quality_gate_action_counts) || '';
        const evidenceDetail = [evidenceFailureSummary, evidenceMismatchFreshnessSummary, evidenceReasonSummary, evidenceReasonFreshnessSummary, blockerSummary, contentBlockerFreshnessSummary, qualityActionSummary].filter(Boolean).join('；');
        return `目前品質：${conformance}；內容可信度警示 ${contentWarnings}、阻斷 ${contentBlocked}；證據關卡需注意 ${evidenceAttention}${evidenceDetail ? `；${evidenceDetail}` : ''}`;
    }

    function targets(audit, escapeHtml) {
        const data = validated(audit), e = escapeHtml || (value => String(value ?? ''));
        if (!data || !data.returned) return '';
        const label = window.StockAgentReportQualityQueueScope?.boundedItemsLabel?.('目前品質待查看', data.total, data.returned, data.summary.items_truncated, data.summary.items_limit) || (data.summary.items_truncated === true ? `目前品質待查看（顯示 ${data.returned}/${data.total}）` : (data.returned < data.total ? `目前品質待查看（顯示 ${data.returned}/${data.total}；範圍資料需確認）` : `目前品質待查看（${data.total}）`));
        const buttons = data.items.map(item => {
            const ticker = e(item.ticker || '報告'), pipeline = e(item.pipeline_id || 'v1'), filename = e(item.filename || ''), status = e(statusLabels[item.report_conformance_status] || '無法判定'), content = e(statusLabels[item.content_credibility_status] || '無法判定'), evidence = e(evidenceLabels[item.evidence_exit_gate_verdict] || '無法判定'), reason = item.reason || '目前品質狀態需要人工查看。', failedCount = Number(item.evidence_failed_count), contentBlockerText = window.StockAgentReportQualityEvidence?.formatQualityBlockerIds?.(item.content_credibility_blocker_ids) || '', contentBlockerFreshnessStatus = window.StockAgentReportQualityEvidence?.formatContentBlockerFreshnessStatus?.(item.content_credibility_freshness_status) || '', contentBlockerSummary = contentBlockerText ? `內容阻斷：${contentBlockerText}` : '', contentBlockerFreshnessSummary = contentBlockerFreshnessStatus ? `內容阻斷版本：${contentBlockerFreshnessStatus}` : '', contentBlockerMessageText = window.StockAgentReportQualityEvidence?.formatQualityBlockerMessages?.(item.content_credibility_blocker_messages) || '', contentBlockerMessageSummary = contentBlockerMessageText ? `內容阻斷原因：${contentBlockerMessageText}` : '', evidenceFailureSummary = Number.isFinite(failedCount) && failedCount > 0 ? `證據數值不一致 ${Math.floor(failedCount)}` : '', evidenceMismatchFreshness = window.StockAgentReportQualityEvidence?.formatEvidenceMismatchFreshness?.(item.evidence_mismatch_freshness_status, failedCount) || '', evidenceReasonSummary = window.StockAgentReportQualityEvidence?.formatUnverifiableReasonSummary?.(item.evidence_unverifiable_reason_counts) || '', evidenceReasonFreshnessStatus = window.StockAgentReportQualityEvidence?.formatUnverifiableReasonFreshnessStatus?.(item.evidence_unverifiable_freshness_status, item.evidence_unverifiable_reason_counts) || '', evidenceReasonFreshness = evidenceReasonFreshnessStatus ? `證據未驗證版本：${evidenceReasonFreshnessStatus}` : '', qualityActionSummary = window.StockAgentReportQualityEvidence?.formatQualityAction?.(item.quality_action) || '', reasonText = [reason, evidenceFailureSummary, evidenceMismatchFreshness, evidenceReasonSummary, evidenceReasonFreshness, contentBlockerSummary, contentBlockerFreshnessSummary, contentBlockerMessageSummary, qualityActionSummary].filter(Boolean).map(e).join('；');
            return filename ? `<button class="watchlist-quality-history-button" type="button" data-quality-history-audit-target data-quality-history-query="${filename}" data-quality-history-pipeline="${pipeline}" aria-label="查看 ${ticker} ${pipeline} 的目前品質"><span>查看 ${ticker} ${pipeline}</span><small>一致性：${status}；內容：${content}；證據：${evidence}；${reasonText}</small></button>` : '';
        }).filter(Boolean).join('');
        return buttons ? `<div class="watchlist-quality-current-targets"><strong>${e(label)}</strong><div class="watchlist-quality-audit-actions">${buttons}</div></div>` : '';
    }

    window.StockAgentWatchlistCurrentQualityHelpers = { summary, targets };
})();
