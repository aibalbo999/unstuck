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
        const provenanceLabels = [['after_refresh', '刷新後缺口'], ['no_refresh_provenance', '未標記刷新來源']];
        const provenanceSummary = provenanceLabels.map(([key, label]) => {
            const count = Number(audit.quality_metadata_missing_by_provenance?.[key] || 0);
            return Number.isFinite(count) && count > 0 ? `${label} ${Math.floor(count)}` : '';
        }).filter(Boolean).join('、');
        const reviewLabels = [['pending', '待人工核對'], ['approved_with_gap', '已核准保留缺口'], ['rejected', '退回處理'], ['deferred', '已暫緩']]; const reviewSummary = reviewLabels.map(([key, label]) => { const count = Number(audit.quality_review_by_status?.[key] || 0); return Number.isFinite(count) && count > 0 ? `${label} ${Math.floor(count)}` : ''; }).filter(Boolean).join('、'); const reviewFilter = String(audit.review_status_filter || 'all').trim().toLowerCase() || 'all'; const reviewFilterLabel = { pending: '待人工核對', approved_with_gap: '已核准保留缺口', rejected: '退回處理', deferred: '已暫緩' }[reviewFilter] || reviewFilter; const reviewFilterActions = window.StockAgentHistoryPanelQualityHelpers?.renderQualityReviewStatusFilters?.(audit, e) || '';
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
        const coverageSummary = reviewFilter !== 'all'
            ? `審核範圍：${reviewFilterLabel}`
            : coverage != null && audit.quality_metadata_coverage_basis === 'verified_snapshot_reports' ? `品質 metadata 完整度：${coverage}%（分母：已驗證快照）` : '';
        const invalidSnapshots = Number(audit.snapshot_invalid_reports || 0);
        const unverifiedSnapshots = Number(audit.snapshot_unverified_reports || 0);
        const invalidCount = Number.isFinite(invalidSnapshots) && invalidSnapshots > 0 ? Math.floor(invalidSnapshots) : 0;
        const unverifiedCount = Number.isFinite(unverifiedSnapshots) && unverifiedSnapshots > 0 ? Math.floor(unverifiedSnapshots) : 0;
        const snapshotSummary = invalidCount + unverifiedCount > 0
            ? `snapshot 無法驗證 ${invalidCount + unverifiedCount} 份（invalid ${invalidCount}、未驗證 ${unverifiedCount}）`
            : '';
        const basisSummary = [coverageSummary, snapshotSummary].filter(Boolean).join('；');
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
        const auditDetails = missing > 0
            ? `<span>${Math.floor(missing)} 份品質 metadata 缺口${truncation}</span><em>${fieldSummary ? `缺口：${e(fieldSummary)}` : ''}${pipelineSummary ? `；模式缺口：${e(pipelineSummary)}` : ''}${reviewSummary ? `；審核狀態：${e(reviewSummary)}` : ''}${provenanceSummary ? `；來源：${e(provenanceSummary)}` : ''}</em>${artifactEvidenceSummary ? `<em>${e(artifactEvidenceSummary)}</em>` : ''}${artifactFieldSummary ? `<em>artifact 欄位可查：${e(artifactFieldSummary)}</em>` : ''}${basisSummary ? `<em>${e(basisSummary)}</em>` : ''}`
            : `<span>符合條件的 ${complete} 份已驗證 snapshot 沒有品質 metadata 缺口</span>${basisSummary ? `<em>${e(basisSummary)}</em>` : ''}`;
        const targets = (Array.isArray(audit.items) ? audit.items : []).filter(item => item && item.filename).map(item => {
            const ticker = item.ticker || '報告';
            const pipeline = item.pipeline_id || 'v1';
            const reportDate = String(item.report_date || '').trim();
            const title = item.title || '品質缺口';
            const detail = item.detail || title;
            const reasonCodes = Array.isArray(item.reason_codes) ? item.reason_codes.join(',') : '';
            const missingFields = Array.isArray(item.missing_quality_fields) ? item.missing_quality_fields : [];
            const missingFieldText = missingFields.map(field => fieldLabels.find(([key]) => key === field)?.[1] || field).filter(Boolean).join('、');
            const provenance = item.quality_metadata_provenance === 'after_refresh' || reasonCodes.includes('quality_metadata_after_refresh')
                ? '刷新後'
                : item.quality_metadata_provenance === 'no_refresh_provenance' ? '未標記刷新來源' : '';
            const artifactSummary = item.artifact_quality_summary?.status === 'present'
                ? (Array.isArray(item.artifact_quality_summary.fields) ? item.artifact_quality_summary.fields : [])
                    .map(field => fieldLabels.find(([key]) => key === field)?.[1] || field).filter(Boolean).join('、')
                : '';
            const targetContext = [missingFieldText ? `缺少${missingFieldText}` : '', provenance ? `來源：${provenance}` : '', artifactSummary ? `artifact 摘要可查：${artifactSummary}` : ''].filter(Boolean).join('；');
            const targetDetail = targetContext ? `${title}；品質缺口：${targetContext}` : title;
            const targetLabel = reportDate ? `${ticker} ${pipeline} · ${reportDate}` : `${ticker} ${pipeline}`;
            const reviewHtml = window.StockAgentHistoryPanelQualityHelpers?.renderQualityReview?.(item, targetLabel, e) || '';
            return `<div class="history-quality-audit-target-row"><button class="history-quality-audit-target" type="button" data-quality-audit-report="${e(item.filename)}" data-quality-audit-ticker="${e(ticker)}" data-quality-audit-pipeline="${e(pipeline)}" data-quality-reason-codes="${e(reasonCodes)}" title="${e(`${detail}${targetContext ? `；${targetContext}` : ''}`)}" aria-label="${e(`人工核對 ${targetLabel}：${targetDetail}`)}"><span>查看 ${e(targetLabel)}</span>${targetContext ? `<small>${e(targetContext)}</small>` : ''}</button>${reviewHtml}</div>`;
        }).join('');
        return `<div class="history-quality-audit" role="status"><div class="history-quality-audit-header"><strong>歷史版本品質稽核</strong><span>範圍：${Math.floor(audited)} 份</span></div><div class="history-quality-audit-summary">${auditDetails}</div>${pipelineActions ? `<div class="history-quality-audit-filter-actions" aria-label="按模式查看品質缺口">${pipelineActions}</div>` : ''}${reviewFilterActions}${pageControls ? `<div class="history-quality-audit-pagination" aria-label="品質缺口分頁">${pageControls}</div>` : ''}${targets ? `<div class="history-quality-audit-actions">${targets}</div>` : ''}</div>`;
    }

    window.StockAgentHistoricalQualityAuditRenderer = { render };
})();
