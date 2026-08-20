(function () {
    function render(audit, escapeHtml) {
        const e = escapeHtml || (value => String(value ?? ''));
        if (!audit || audit.status === 'unavailable') {
            return '<div class="history-quality-audit" role="status"><div class="history-quality-audit-header"><strong>歷史版本品質稽核</strong><span>暫時無法讀取</span></div></div>';
        }
        if (audit.status === 'loading') {
            return '<div class="history-quality-audit" role="status"><div class="history-quality-audit-header"><strong>歷史版本品質稽核</strong><span>載入中</span></div></div>';
        }
        const missing = Number(audit.quality_metadata_missing_reports || 0);
        const audited = Number(audit.audited_reports || 0);
        const fieldLabels = [['report_conformance', '報告一致性'], ['evidence_exit_gate', '證據關卡'], ['content_credibility', '內容可信度']];
        const fieldSummary = fieldLabels.map(([key, label]) => {
            const count = Number(audit.missing_quality_field_counts?.[key] || 0);
            return Number.isFinite(count) && count > 0 ? `${label} ${Math.floor(count)}` : '';
        }).filter(Boolean).join('、');
        const provenanceLabels = [['before_refresh', '刷新前已有缺口'], ['after_refresh', '有刷新歸因'], ['no_refresh_provenance', '未標記刷新來源']];
        const provenanceSummary = provenanceLabels.map(([key, label]) => {
            const count = Number(audit.quality_metadata_missing_by_provenance?.[key] || 0);
            return Number.isFinite(count) && count > 0 ? `${label} ${Math.floor(count)}` : '';
        }).filter(Boolean).join('、');
        const rerunExecutionLabels = [['full_rerun_required', '完整重跑'], ['partial_rerun_available', '局部重跑可用'], ['partial_rerun_review_required', '局部重跑需確認'], ['partial_rerun_unavailable', '無可用局部重跑'], ['not_evaluated', '重跑策略未判定']]; const rerunExecutionSummary = rerunExecutionLabels.map(([key, label]) => { const count = Number(audit.quality_metadata_missing_by_rerun_execution?.[key] || 0); return Number.isFinite(count) && count > 0 ? `${label} ${Math.floor(count)}` : ''; }).filter(Boolean).join('、');
        const rerunContextLabels = [['present', '原始上下文完整'], ['partial', '原始上下文部分可用'], ['artifact_fallback_available', 'artifact 前序可查'], ['missing', '無可用局部上下文'], ['not_evaluated', '上下文未判定']]; const rerunContextSummary = rerunContextLabels.map(([key, label]) => { const count = Number(audit.quality_metadata_missing_by_rerun_context?.[key] || 0); return Number.isFinite(count) && count > 0 ? `${label} ${Math.floor(count)}` : ''; }).filter(Boolean).join('、');
        const reviewLabels = [['pending', '待人工核對'], ['approved_with_gap', '已核准保留缺口'], ['rejected', '退回處理'], ['deferred', '已暫緩']]; const reviewCount = key => { const count = Number(audit.quality_review_by_status?.[key] || 0); return Number.isFinite(count) && count > 0 ? Math.floor(count) : 0; }; const reviewSummary = reviewLabels.map(([key, label]) => { const count = reviewCount(key); return count > 0 ? `${label} ${count}` : ''; }).filter(Boolean).join('、'); const reviewTotal = reviewLabels.reduce((total, [key]) => total + reviewCount(key), 0); const reviewCompleted = reviewLabels.slice(1).reduce((total, [key]) => total + reviewCount(key), 0); const reviewProgressSummary = reviewTotal > 0 ? `人工審核進度：${reviewCompleted}/${reviewTotal}` : ''; const versionLabels = [['current', '目前版本缺口'], ['historical', '歷史版本缺口'], ['unknown', '版本未判定']]; const versionSummary = versionLabels.map(([key, label]) => { const count = Number(audit.quality_metadata_missing_by_version_status?.[key] || 0); return Number.isFinite(count) && count > 0 ? `${label} ${Math.floor(count)}` : ''; }).filter(Boolean).join('、'); const reviewFilter = String(audit.review_status_filter || 'all').trim().toLowerCase() || 'all'; const reviewFilterLabel = { pending: '待人工核對', approved_with_gap: '已核准保留缺口', rejected: '退回處理', deferred: '已暫緩' }[reviewFilter] || reviewFilter; const reviewFilterActions = window.StockAgentHistoryPanelQualityHelpers?.renderQualityReviewStatusFilters?.(audit, e) || ''; const missingFieldFilter = String(audit.missing_quality_field_filter || 'all').trim().toLowerCase() || 'all'; const missingFieldFilterLabel = { report_conformance: '報告一致性', evidence_exit_gate: '證據關卡', content_credibility: '內容可信度' }[missingFieldFilter] || missingFieldFilter; const missingFieldFilterActions = window.StockAgentHistoryPanelQualityHelpers?.renderQualityMissingFieldFilters?.(audit, e) || ''; const versionStatusFilter = String(audit.report_version_status_filter || 'all').trim().toLowerCase() || 'all'; const versionStatusFilterLabel = { current: '目前版本', historical: '歷史版本', unknown: '版本未判定' }[versionStatusFilter] || versionStatusFilter; const versionStatusFilterActions = window.StockAgentHistoryPanelQualityHelpers?.renderQualityVersionStatusFilters?.(audit, e) || '';
        const artifactEvidenceSummary = [['present', 'artifact 摘要可查'], ['not_found', 'artifact 無 gate 摘要'], ['unavailable', 'artifact 無法讀取']].map(([key, label]) => { const count = Number(audit.artifact_quality_summary_by_status?.[key] || 0); return Number.isFinite(count) && count > 0 ? `${label} ${Math.floor(count)} 份` : ''; }).filter(Boolean).join('、');
        const artifactFieldStats = audit.artifact_quality_summary_by_field && typeof audit.artifact_quality_summary_by_field === 'object' && !Array.isArray(audit.artifact_quality_summary_by_field) ? audit.artifact_quality_summary_by_field : null;
        const artifactFieldSummary = artifactFieldStats ? fieldLabels.map(([key, label]) => { const count = Number(artifactFieldStats[key] || 0); return Number.isFinite(count) && count >= 0 ? `${label} ${Math.floor(count)}` : ''; }).filter(Boolean).join('、') : '';
        const pipelineQuality = audit.quality_metadata_by_pipeline && typeof audit.quality_metadata_by_pipeline === 'object' && !Array.isArray(audit.quality_metadata_by_pipeline) ? audit.quality_metadata_by_pipeline : {};
        const pipelineSummary = Object.entries(pipelineQuality).map(([pipeline, summary]) => {
            const count = Number(summary?.quality_metadata_missing_reports || 0);
            return Number.isFinite(count) && count > 0 ? `${pipeline} ${Math.floor(count)}` : '';
        }).filter(Boolean).join('、');
        const pipelineActions = Object.entries(pipelineQuality).map(([pipeline, summary]) => {
            const count = Number(summary?.quality_metadata_missing_reports || 0);
            return Number.isFinite(count) && count > 0
                ? `<button class="history-quality-audit-filter" type="button" data-quality-audit-pipeline="${e(pipeline)}" aria-label="只看 ${e(pipeline)} 模式的品質缺口">只看 ${e(pipeline)} 缺口（${Math.floor(count)}）</button>`
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
        const invalidSnapshots = Number(audit.snapshot_invalid_reports || 0);
        const unverifiedSnapshots = Number(audit.snapshot_unverified_reports || 0);
        const invalidCount = Number.isFinite(invalidSnapshots) && invalidSnapshots > 0 ? Math.floor(invalidSnapshots) : 0;
        const unverifiedCount = Number.isFinite(unverifiedSnapshots) && unverifiedSnapshots > 0 ? Math.floor(unverifiedSnapshots) : 0;
        const snapshotSummary = invalidCount + unverifiedCount > 0
            ? `snapshot 無法驗證 ${invalidCount + unverifiedCount} 份（invalid ${invalidCount}、未驗證 ${unverifiedCount}）`
            : '';
        const basisSummary = [scopeSummary ? '' : coverageSummary, snapshotSummary].filter(Boolean).join('；');
        const verifiedValue = Number(audit.verified_snapshot_reports);
        const verified = Number.isFinite(verifiedValue) && verifiedValue >= 0 ? Math.floor(verifiedValue) : Math.max(0, Math.floor(audited - invalidCount - unverifiedCount));
        const completeValue = Number(audit.quality_metadata_complete_reports);
        const complete = Number.isFinite(completeValue) && completeValue >= 0 ? Math.floor(completeValue) : Math.max(0, verified - missing);
        const returnedValue = Number(audit.items_returned);
        const returned = Number.isFinite(returnedValue) && returnedValue >= 0 ? Math.floor(returnedValue) : Array.isArray(audit.items) ? audit.items.length : 0;
        const offsetValue = Number(audit.items_offset);
        const itemOffset = Number.isFinite(offsetValue) && offsetValue >= 0 ? Math.floor(offsetValue) : 0;
        const totalValue = Number(audit.items_total);
        const itemTotal = Number.isFinite(totalValue) && totalValue >= 0 ? Math.floor(totalValue) : missing;
        const pageEnd = Math.min(itemTotal, itemOffset + returned);
        const truncation = itemOffset > 0 && returned > 0
            ? `（目前顯示第 ${itemOffset + 1}-${pageEnd} 份，共 ${itemTotal} 份）`
            : audit.items_truncated === true && missing > returned ? `（目前顯示 ${returned} 份，另有 ${missing - returned} 份未展開）` : '';
        const pageControls = [
            audit.items_has_prev === true ? '<button class="history-quality-audit-page" type="button" data-quality-audit-page="prev" aria-label="查看上一批品質缺口">上一批</button>' : '',
            audit.items_has_next === true ? '<button class="history-quality-audit-page" type="button" data-quality-audit-page="next" aria-label="查看下一批品質缺口">下一批</button>' : ''
        ].filter(Boolean).join('');
        const summaryItems = [fieldSummary ? `缺口：${fieldSummary}` : '', pipelineSummary ? `模式缺口：${pipelineSummary}` : '', versionSummary ? `版本：${versionSummary}` : '', reviewSummary ? `審核狀態：${reviewSummary}` : '', reviewProgressSummary, provenanceSummary ? `來源：${provenanceSummary}` : '', rerunExecutionSummary ? `重跑策略：${rerunExecutionSummary}` : '', rerunContextSummary ? `上下文：${rerunContextSummary}` : ''].filter(Boolean);
        const auditDetails = missing > 0
            ? `<span>${Math.floor(missing)} 份品質 metadata 缺口${truncation}</span>${scopeItems.map(scope => `<em class="history-quality-audit-summary-scope">${e(scope)}</em>`).join('')}${summaryItems.map(item => `<em class="history-quality-audit-summary-item">${e(item)}</em>`).join('')}${artifactEvidenceSummary ? `<em>${e(artifactEvidenceSummary)}</em>` : ''}${artifactFieldSummary ? `<em>${e(`artifact 欄位可查：${artifactFieldSummary}`)}</em>` : ''}${basisSummary ? `<em>${e(basisSummary)}</em>` : ''}`
            : filteredEmptyLabel ? `<span>目前沒有符合「${e(filteredEmptyLabel)}」的品質 metadata 缺口</span>${basisSummary ? `<em>${e(basisSummary)}</em>` : ''}` : `<span>符合條件的 ${complete} 份已驗證 snapshot 沒有品質 metadata 缺口</span>${basisSummary ? `<em>${e(basisSummary)}</em>` : ''}`;
        const targets = (Array.isArray(audit.items) ? audit.items : []).filter(item => item && item.filename).map(item => {
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
        return `<div class="history-quality-audit" role="status"><div class="history-quality-audit-header"><strong>歷史版本品質稽核</strong><span>範圍：${Math.floor(audited)} 份</span></div><div class="history-quality-audit-summary">${auditDetails}</div>${pipelineActions ? `<div class="history-quality-audit-filter-actions" aria-label="按模式查看品質缺口">${pipelineActions}</div>` : ''}${versionStatusFilterActions}${missingFieldFilterActions}${reviewFilterActions}${pageControls ? `<div class="history-quality-audit-pagination" aria-label="品質缺口分頁">${pageControls}</div>` : ''}${targets ? `<div class="history-quality-audit-actions">${targets}</div>` : ''}</div>`;
    }

    window.StockAgentHistoricalQualityAuditRenderer = { render };
})();
