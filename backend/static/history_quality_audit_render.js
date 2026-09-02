(function () {
    function render(audit, escapeHtml) {
        const e = escapeHtml || (value => String(value ?? ''));
        function nonNegativeInteger(value, fallback = 0) { if (value === undefined || value === null) return fallback; const number = Number(value); return Number.isFinite(number) && Number.isInteger(number) && number >= 0 ? number : null; }
        if (!audit || audit.status === 'unavailable') {
            return '<div class="history-quality-audit" role="status"><div class="history-quality-audit-header"><strong>歷史版本品質稽核</strong><span>暫時無法讀取</span></div></div>';
        }
        if (audit.status === 'loading') {
            return '<div class="history-quality-audit" role="status"><div class="history-quality-audit-header"><strong>歷史版本品質稽核</strong><span>載入中</span></div></div>';
        }
        window.StockAgentReportQualityAuditScope?.sanitizeAuditDistributions?.(audit, true);
        const missing = nonNegativeInteger(audit.quality_metadata_missing_reports);
        const audited = nonNegativeInteger(audit.audited_reports), verifiedValue = nonNegativeInteger(audit.verified_snapshot_reports, null), completeValue = nonNegativeInteger(audit.quality_metadata_complete_reports, null), invalidSnapshotValue = nonNegativeInteger(audit.snapshot_invalid_reports, null), unverifiedSnapshotValue = nonNegativeInteger(audit.snapshot_unverified_reports, null), returnedValue = nonNegativeInteger(audit.items_returned, null), totalValue = nonNegativeInteger(audit.items_total, null), itemOffset = nonNegativeInteger(audit.items_offset), items = Array.isArray(audit.items) ? audit.items : [];
        const coreCountsValid = missing !== null && audited !== null && missing <= audited && (audit.verified_snapshot_reports == null || verifiedValue !== null && missing <= verifiedValue && verifiedValue <= audited) && (audit.quality_metadata_complete_reports == null || completeValue !== null && completeValue <= audited && (verifiedValue === null || completeValue + missing === verifiedValue)) && (audit.verified_snapshot_reports == null || audit.snapshot_invalid_reports == null || audit.snapshot_unverified_reports == null || invalidSnapshotValue !== null && unverifiedSnapshotValue !== null && verifiedValue + invalidSnapshotValue + unverifiedSnapshotValue === audited) && (audit.items_total == null || totalValue !== null && totalValue === missing) && (audit.items_returned == null || returnedValue !== null && returnedValue === items.length) && (audit.items_total == null || audit.items_returned == null || totalValue !== null && returnedValue !== null && returnedValue <= totalValue && (audit.items_offset == null || itemOffset !== null && itemOffset <= totalValue && itemOffset + returnedValue <= totalValue));
        const fieldLabels = [['report_conformance', '報告一致性'], ['evidence_exit_gate', '證據關卡'], ['content_credibility', '內容可信度']];
        const fieldSummary = fieldLabels.map(([key, label]) => {
            const count = nonNegativeInteger(audit.missing_quality_field_counts?.[key]);
            return count !== null && count > 0 ? `${label} ${count}` : '';
        }).filter(Boolean).join('、');
        const provenanceLabels = [['before_refresh', '刷新前已有缺口'], ['after_refresh', '有刷新歸因'], ['no_refresh_provenance', '未標記刷新來源']];
        const provenanceSummary = provenanceLabels.map(([key, label]) => {
            const count = nonNegativeInteger(audit.quality_metadata_missing_by_provenance?.[key]);
            return count !== null && count > 0 ? `${label} ${count}` : '';
        }).filter(Boolean).join('、');
        const rerunExecutionLabels = [['full_rerun_required', '完整重跑'], ['partial_rerun_available', '局部重跑可用'], ['partial_rerun_review_required', '局部重跑需確認'], ['partial_rerun_unavailable', '無可用局部重跑'], ['not_evaluated', '重跑策略未判定']]; const rerunExecutionSummary = rerunExecutionLabels.map(([key, label]) => { const count = nonNegativeInteger(audit.quality_metadata_missing_by_rerun_execution?.[key]); return count !== null && count > 0 ? `${label} ${count}` : ''; }).filter(Boolean).join('、');
        const rerunContextLabels = [['present', '原始上下文完整'], ['partial', '原始上下文部分可用'], ['artifact_fallback_available', 'artifact 前序可查'], ['missing', '無可用局部上下文'], ['not_evaluated', '上下文未判定']]; const rerunContextSummary = rerunContextLabels.map(([key, label]) => { const count = nonNegativeInteger(audit.quality_metadata_missing_by_rerun_context?.[key]); return count !== null && count > 0 ? `${label} ${count}` : ''; }).filter(Boolean).join('、');
        const reviewLabels = [['pending', '待人工核對'], ['approved_with_gap', '已核准保留缺口'], ['rejected', '退回處理'], ['deferred', '已暫緩']]; const reviewCounts = reviewLabels.map(([key]) => nonNegativeInteger(audit.quality_review_by_status?.[key])); const reviewCountsValid = reviewCounts.every(count => count !== null); const reviewCount = index => reviewCounts[index] || 0; const reviewSummary = reviewCountsValid ? reviewLabels.map(([key, label], index) => { const count = reviewCount(index); return count > 0 ? `${label} ${count}` : ''; }).filter(Boolean).join('、') : ''; const reviewTotal = reviewCountsValid ? reviewCounts.reduce((total, count) => total + count, 0) : 0; const reviewCompleted = reviewCountsValid ? reviewCounts.slice(1).reduce((total, count) => total + count, 0) : 0; const reviewProgressSummary = reviewCountsValid && reviewTotal > 0 ? `人工審核進度：${reviewCompleted}/${reviewTotal}` : ''; const versionLabels = [['current', '目前版本缺口'], ['historical', '歷史版本缺口'], ['unknown', '版本未判定']]; const versionSummary = versionLabels.map(([key, label]) => { const count = nonNegativeInteger(audit.quality_metadata_missing_by_version_status?.[key]); return count !== null && count > 0 ? `${label} ${count}` : ''; }).filter(Boolean).join('、'); const reviewFilter = String(audit.review_status_filter || 'all').trim().toLowerCase() || 'all'; const reviewFilterLabel = { pending: '待人工核對', approved_with_gap: '已核准保留缺口', rejected: '退回處理', deferred: '已暫緩' }[reviewFilter] || reviewFilter; const reviewFilterActions = window.StockAgentHistoryPanelQualityHelpers?.renderQualityReviewStatusFilters?.(audit, e) || ''; const missingFieldFilter = String(audit.missing_quality_field_filter || 'all').trim().toLowerCase() || 'all'; const missingFieldFilterLabel = { report_conformance: '報告一致性', evidence_exit_gate: '證據關卡', content_credibility: '內容可信度' }[missingFieldFilter] || missingFieldFilter; const missingFieldFilterActions = window.StockAgentHistoryPanelQualityHelpers?.renderQualityMissingFieldFilters?.(audit, e) || ''; const versionStatusFilter = String(audit.report_version_status_filter || 'all').trim().toLowerCase() || 'all'; const versionStatusFilterLabel = { current: '目前版本', historical: '歷史版本', unknown: '版本未判定' }[versionStatusFilter] || versionStatusFilter; const versionStatusFilterActions = window.StockAgentHistoryPanelQualityHelpers?.renderQualityVersionStatusFilters?.(audit, e) || '';
        const artifactEvidenceSummary = [['present', 'artifact 摘要可查'], ['not_found', 'artifact 無 gate 摘要'], ['unavailable', 'artifact 無法讀取']].map(([key, label]) => { const count = nonNegativeInteger(audit.artifact_quality_summary_by_status?.[key]); return count !== null && count > 0 ? `${label} ${count} 份` : ''; }).filter(Boolean).join('、');
        const artifactFieldStats = audit.artifact_quality_summary_by_field && typeof audit.artifact_quality_summary_by_field === 'object' && !Array.isArray(audit.artifact_quality_summary_by_field) ? audit.artifact_quality_summary_by_field : null;
        const artifactFieldSummary = artifactFieldStats ? fieldLabels.map(([key, label]) => { const count = nonNegativeInteger(artifactFieldStats[key]); return count !== null && count >= 0 ? `${label} ${count}` : ''; }).filter(Boolean).join('、') : '';
        const currentQualitySummary = window.StockAgentHistoricalCurrentQualityHelpers?.render?.(audit.current_quality_summary, e) || '';
        const pipelineQuality = audit.quality_metadata_by_pipeline && typeof audit.quality_metadata_by_pipeline === 'object' && !Array.isArray(audit.quality_metadata_by_pipeline) ? audit.quality_metadata_by_pipeline : {};
        const pipelineSummary = window.StockAgentReportQualityAuditScope?.pipelineMissingSummary?.(pipelineQuality, missing) || '';
        const pipelineContextScopeValid = window.StockAgentReportQualityAuditScope?.pipelineContextScopeValid?.(pipelineQuality, missing) || false;
        const pipelineContextSummary = pipelineSummary && pipelineContextScopeValid ? Object.entries(pipelineQuality).map(([pipeline, summary]) => { const context = rerunContextLabels.map(([key, label]) => { const count = nonNegativeInteger(summary?.quality_metadata_missing_by_rerun_context?.[key]); return count !== null && count > 0 ? `${label} ${count}` : ''; }).filter(Boolean).join('、'); return context ? `${pipeline} ${context}` : ''; }).filter(Boolean).join('、') : '';
        const pipelineActions = Object.entries(pipelineQuality).map(([pipeline, summary]) => {
            const count = nonNegativeInteger(summary?.quality_metadata_missing_reports);
            return count !== null && count > 0
                ? `<button class="history-quality-audit-filter" type="button" data-quality-audit-pipeline="${e(pipeline)}" aria-label="只看 ${e(pipeline)} 模式的品質缺口">只看 ${e(pipeline)} 缺口（${count}）</button>`
                : '';
        }).filter(Boolean).join('');
        const coverageValue = Number(audit.quality_metadata_coverage_pct);
        const coverage = Number.isFinite(coverageValue) && coverageValue >= 0 && coverageValue <= 100
            ? Math.round(coverageValue * 100) / 100
            : null;
        const scopeItems = [reviewFilter !== 'all' ? `審核範圍：${reviewFilterLabel}` : '', missingFieldFilter !== 'all' ? `缺口範圍：${missingFieldFilterLabel}` : '', versionStatusFilter !== 'all' ? `版本範圍：${versionStatusFilterLabel}` : ''].filter(Boolean);
        const scopeSummary = scopeItems.join('；');
        const filteredEmptyLabel = [reviewFilter !== 'all' ? reviewFilterLabel : '', missingFieldFilter !== 'all' ? missingFieldFilterLabel : '', versionStatusFilter !== 'all' ? versionStatusFilterLabel : ''].filter(Boolean).join('；');
        const coverageSummary = scopeSummary || (coverage != null && audit.quality_metadata_coverage_basis === 'verified_snapshot_reports' ? `品質 metadata 完整度：${coverage}%（分母：已驗證快照）` : '');
        const invalidSnapshots = nonNegativeInteger(audit.snapshot_invalid_reports), unverifiedSnapshots = nonNegativeInteger(audit.snapshot_unverified_reports), snapshotCountsValid = invalidSnapshots !== null && unverifiedSnapshots !== null;
        const invalidCount = snapshotCountsValid && invalidSnapshots > 0 ? invalidSnapshots : 0;
        const unverifiedCount = snapshotCountsValid && unverifiedSnapshots > 0 ? unverifiedSnapshots : 0;
        const snapshotSummary = snapshotCountsValid && invalidCount + unverifiedCount > 0
            ? `snapshot 無法驗證 ${invalidCount + unverifiedCount} 份（invalid ${invalidCount}、未驗證 ${unverifiedCount}）`
            : '';
        const basisSummary = [scopeSummary ? '' : coverageSummary, snapshotSummary].filter(Boolean).join('；');
        const verified = verifiedValue !== null ? verifiedValue : audit.verified_snapshot_reports == null && snapshotCountsValid && audited !== null ? Math.max(0, audited - invalidCount - unverifiedCount) : null;
        const complete = completeValue !== null ? completeValue : audit.quality_metadata_complete_reports == null && verified !== null && missing !== null ? Math.max(0, verified - missing) : null;
        const returned = returnedValue !== null ? returnedValue : audit.items_returned == null ? Array.isArray(audit.items) ? audit.items.length : 0 : null;
        const itemTotal = totalValue !== null ? totalValue : audit.items_total == null ? missing : null;
        const pageEnd = itemTotal === null || itemOffset === null || returned === null ? 0 : Math.min(itemTotal, itemOffset + returned); const hasBoundedScopeFields = audit.items_total !== undefined && audit.items_total !== null && audit.items_returned !== undefined && audit.items_returned !== null; const itemLimit = audit.items_limit === undefined || audit.items_limit === null ? undefined : Number(audit.items_limit); const boundedScopeConsistent = window.StockAgentReportQualityQueueScope?.boundedItemsConsistent; const boundedScopeNeedsConfirmation = hasBoundedScopeFields && itemTotal !== null && returned !== null && typeof boundedScopeConsistent === 'function' && !boundedScopeConsistent(itemTotal, returned, audit.items_truncated, itemLimit);
        const truncation = boundedScopeNeedsConfirmation ? `（目前顯示 ${returned}/${itemTotal}；範圍資料需確認）` : itemOffset > 0 && returned > 0 ? `（目前顯示第 ${itemOffset + 1}-${pageEnd} 份，共 ${itemTotal} 份）` : audit.items_truncated === true && missing > returned ? `（目前顯示 ${returned} 份，另有 ${missing - returned} 份未展開）` : '';
        const pageControls = [
            audit.items_has_prev === true ? '<button class="history-quality-audit-page" type="button" data-quality-audit-page="prev" aria-label="查看上一批品質缺口">上一批</button>' : '',
            audit.items_has_next === true ? '<button class="history-quality-audit-page" type="button" data-quality-audit-page="next" aria-label="查看下一批品質缺口">下一批</button>' : ''
        ].filter(Boolean).join('');
        const summaryItems = [fieldSummary ? `缺口：${fieldSummary}` : '', pipelineSummary ? `模式缺口：${pipelineSummary}` : '', pipelineContextSummary ? `模式上下文：${pipelineContextSummary}` : '', versionSummary ? `版本：${versionSummary}` : '', reviewSummary ? `審核狀態：${reviewSummary}` : '', reviewProgressSummary, provenanceSummary ? `來源：${provenanceSummary}` : '', rerunExecutionSummary ? `重跑策略：${rerunExecutionSummary}` : '', rerunContextSummary ? `上下文：${rerunContextSummary}` : ''].filter(Boolean);
        const auditDetails = !coreCountsValid
            ? '<span>品質 metadata 範圍資料需確認</span>'
            : missing > 0
            ? `<span>${Math.floor(missing)} 份品質 metadata 缺口${truncation}</span>${scopeItems.map(scope => `<em class="history-quality-audit-summary-scope">${e(scope)}</em>`).join('')}${summaryItems.map(item => `<em class="history-quality-audit-summary-item">${e(item)}</em>`).join('')}${artifactEvidenceSummary ? `<em>${e(artifactEvidenceSummary)}</em>` : ''}${artifactFieldSummary ? `<em>${e(`artifact 欄位可查：${artifactFieldSummary}`)}</em>` : ''}${basisSummary ? `<em>${e(basisSummary)}</em>` : ''}${currentQualitySummary}`
            : filteredEmptyLabel ? `<span>目前沒有符合「${e(filteredEmptyLabel)}」的品質 metadata 缺口</span>${basisSummary ? `<em>${e(basisSummary)}</em>` : ''}${currentQualitySummary}` : complete === null ? '<span>snapshot 完整度資料需確認</span>' : `<span>符合條件的 ${complete} 份已驗證 snapshot 沒有品質 metadata 缺口</span>${basisSummary ? `<em>${e(basisSummary)}</em>` : ''}${currentQualitySummary}`;
        const targets = items.filter(item => item && item.filename).map(item => {
            const ticker = item.ticker || '報告';
            const pipeline = item.pipeline_id || 'v1';
            const reportDate = String(item.report_date || '').trim();
            const title = item.title || '品質缺口';
            const detail = item.detail || title;
            const reasonCodes = Array.isArray(item.reason_codes) ? item.reason_codes.join(',') : '';
            const evidence = window.StockAgentReportQualityEvidence?.context?.(item) || {};
            const evidenceDetail = evidence.detail || evidence.targetContext || '';
            const targetReviewStatus = String(item.quality_review?.status || '').trim().toLowerCase(), targetReviewSummary = targetReviewStatus ? `審核狀態：${({ pending: '待人工核對', approved_with_gap: '已核准保留缺口', rejected: '退回處理', deferred: '已暫緩' })[targetReviewStatus] || targetReviewStatus}` : '', targetWarning = evidence.targetWarning || '', targetContext = [targetReviewSummary, evidence.targetContext || ''].filter(Boolean).join('；'), targetView = window.StockAgentReportQualityEvidence?.renderTargetContext?.({ reviewStatus: targetReviewSummary, evidenceContext: evidence.targetContext, warning: targetWarning }, e) || { html: `${targetReviewSummary ? `<small class="quality-evidence-review-status">${e(targetReviewSummary)}</small>` : ''}${evidence.targetContext ? `<small class="quality-evidence-context">${e(evidence.targetContext)}</small>` : ''}${targetWarning ? `<small class="quality-evidence-warning">${e(targetWarning)}</small>` : ''}` };
            const targetDetail = targetContext ? `${title}；品質缺口：${targetContext}` : title;
            const targetAriaLabel = [targetDetail, targetWarning].filter(Boolean).join('；');
            const targetLabel = reportDate ? `${ticker} ${pipeline} · ${reportDate}` : `${ticker} ${pipeline}`;
            const reviewHtml = window.StockAgentHistoryPanelQualityHelpers?.renderQualityReview?.(item, targetLabel, e) || '';
            return `<div class="history-quality-audit-target-row"><button class="history-quality-audit-target" type="button" data-quality-audit-report="${e(item.filename)}" data-quality-audit-ticker="${e(ticker)}" data-quality-audit-pipeline="${e(pipeline)}" data-quality-reason-codes="${e(reasonCodes)}" data-quality-evidence-detail="${e(evidenceDetail)}" title="${e(`${detail}${targetContext ? `；${targetContext}` : ''}`)}" aria-label="${e(`人工核對 ${targetLabel}：${targetAriaLabel}`)}"><span>查看 ${e(targetLabel)}</span>${targetView.html}</button>${reviewHtml}</div>`;
        }).join('');
        return `<div class="history-quality-audit" role="status"><div class="history-quality-audit-header"><strong>歷史版本品質稽核</strong><span>範圍：${audited === null ? '資料需確認' : `${audited} 份`}</span></div><div class="history-quality-audit-summary">${auditDetails}</div>${pipelineActions ? `<div class="history-quality-audit-filter-actions" aria-label="按模式查看品質缺口">${pipelineActions}</div>` : ''}${versionStatusFilterActions}${missingFieldFilterActions}${reviewFilterActions}${pageControls ? `<div class="history-quality-audit-pagination" aria-label="品質缺口分頁">${pageControls}</div>` : ''}${targets ? `<div class="history-quality-audit-actions">${targets}</div>` : ''}</div>`;
    }

    window.StockAgentHistoricalQualityAuditRenderer = { render };
})();
