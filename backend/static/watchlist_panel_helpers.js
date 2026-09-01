(function () {
    function slotLabel(slots, schedules) {
        return (slots || []).map(slot => schedules?.[slot]?.label || slot).join('、') || '未排程';
    }

    function nonNegativeInteger(value) { const number = Number(value); return Number.isFinite(number) && Number.isInteger(number) && number >= 0 ? number : null; }
    function summaryCount(value) { return nonNegativeInteger(value ?? 0); }
    function itemPayload(elements) {
        return { ticker: elements.tickerInput?.value || '', pipeline: elements.pipelineSelect?.value || 'v1', enabled: Boolean(elements.enabledInput?.checked), schedule_slots: [elements.preMarketInput?.checked ? 'pre_market' : '', elements.postMarketInput?.checked ? 'post_market' : ''].filter(Boolean), triggers: window.StockAgentWatchlistTriggerForm?.payload() || [] };
    }

    function resetForm(elements) {
        if (elements.tickerInput) elements.tickerInput.value = '';
        if (elements.pipelineSelect) elements.pipelineSelect.value = 'v1';
        if (elements.enabledInput) elements.enabledInput.checked = true;
        if (elements.preMarketInput) elements.preMarketInput.checked = true;
        if (elements.postMarketInput) elements.postMarketInput.checked = false;
        window.StockAgentWatchlistTriggerForm?.reset();
    }

    function priorityLabel(item) {
        return item.decision_priority === 'high' ? '需重跑' : (item.decision_priority === 'medium' ? '待分析' : (item.decision_priority === 'low' ? '停用' : '有效'));
    }

    function reportButton(item, escapeHtml) {
        const report = item.latest_report || {};
        return report.filename ? `<button class="watchlist-report-button" type="button" data-watchlist-report="${escapeHtml(report.filename)}" data-watchlist-report-ticker="${escapeHtml(item.ticker)}" data-watchlist-report-pipeline="${escapeHtml(item.pipeline || 'v1')}">最新報告</button>` : '<span class="watchlist-report-empty">尚無報告</span>';
    }

    function watchlistDailyBoard(items, daily, escapeHtml) {
        const queue = daily?.decision_queue || {}, queueItems = Array.isArray(queue.items) ? queue.items : [], top = queueItems[0], total = Number(queue.summary?.total_actionable || 0);
        const audit = daily?.report_quality_audit || {}, missingQuality = nonNegativeInteger(audit.quality_metadata_missing_reports), excludedSnapshots = (nonNegativeInteger(audit.snapshot_invalid_reports) || 0) + (nonNegativeInteger(audit.snapshot_unverified_reports) || 0), coverageValue = Number(audit.quality_metadata_coverage_pct), coverage = Number.isFinite(coverageValue) && coverageValue >= 0 && coverageValue <= 100 ? Math.round(coverageValue * 100) / 100 : null, coverageLabel = audit.quality_metadata_coverage_basis === 'verified_snapshot_reports' ? '已驗證快照覆蓋' : '覆蓋'; const freshnessSummary = window.StockAgentWatchlistFreshnessHelpers?.summary?.(audit) || ''; const repairQueueSummary = daily?.repair_queue?.summary || {}; const repairQueueSampled = nonNegativeInteger(repairQueueSummary.sampled_reports); const repairQueueScopeSummary = audit.scope === 'all_indexed_reports' && repairQueueSampled > 0 ? `修復 queue 範圍：取樣 ${repairQueueSampled} 份報告` : ''; const repairQueueBoundedSummary = window.StockAgentReportQualityQueueScope?.boundedRepairQueueScope?.(repairQueueSummary) || ''; const repairSampleOverlap = audit.repair_sample_overlap || {}; const repairSampleOverlapStatus = String(repairSampleOverlap.status || '').trim().toLowerCase(); const repairSampleGap = nonNegativeInteger(repairSampleOverlap.audit_gap_reports); const repairSampleIn = nonNegativeInteger(repairSampleOverlap.audit_gap_reports_in_repair_sample); const repairSampleOutside = nonNegativeInteger(repairSampleOverlap.audit_gap_reports_outside_repair_sample); const repairSampleReturned = nonNegativeInteger(repairSampleOverlap.audit_gap_items_returned); const repairSampleOverlapSummary = repairSampleOverlapStatus === 'complete' && Number.isFinite(repairSampleGap) && repairSampleGap > 0 && Number.isFinite(repairSampleIn) && Number.isFinite(repairSampleOutside) && Number.isFinite(repairSampleReturned) && repairSampleReturned === repairSampleGap && repairSampleIn + repairSampleOutside === repairSampleGap ? `品質缺口與 repair sample：${repairSampleIn}/${repairSampleGap} 在 sample；${repairSampleOutside} 份不在 sample` : repairSampleOverlapStatus === 'partial' && Number.isFinite(repairSampleGap) && Number.isFinite(repairSampleReturned) && repairSampleGap > repairSampleReturned ? `品質缺口與 repair sample：只載入 ${repairSampleReturned}/${repairSampleGap} 份缺口，未展開部分無法判定` : '';
        const currentQualitySummary = window.StockAgentWatchlistCurrentQualityHelpers?.summary?.(audit) || '';
        const missingFieldLabels = [['report_conformance', '報告一致性'], ['evidence_exit_gate', '證據關卡'], ['content_credibility', '內容可信度']];
        const missingFieldSummary = missingFieldLabels.map(([key, label]) => { const count = summaryCount(audit.missing_quality_field_counts?.[key]); return count !== null && count > 0 ? `${label} ${count}` : ''; }).filter(Boolean).join('、');
        const reviewLabels = [['pending', '待人工核對'], ['approved_with_gap', '已核准保留缺口'], ['rejected', '退回處理'], ['deferred', '已暫緩']];
        const reviewCounts = reviewLabels.map(([key]) => summaryCount(audit.quality_review_by_status?.[key])), reviewCountsValid = reviewCounts.every(count => count !== null); const reviewCount = index => reviewCountsValid ? reviewCounts[index] : 0; const reviewSummary = reviewCountsValid ? reviewLabels.map(([key, label], index) => { const count = reviewCount(index); return count > 0 ? `${label} ${count}` : ''; }).filter(Boolean).join('、') : ''; const reviewTotal = reviewCountsValid ? reviewCounts.reduce((total, count) => total + count, 0) : 0; const reviewCompleted = reviewCountsValid ? reviewCounts.slice(1).reduce((total, count) => total + count, 0) : 0; const reviewProgressSummary = reviewCountsValid && reviewTotal > 0 ? `人工審核進度：${reviewCompleted}/${reviewTotal}` : '';
        const provenanceLabels = [['before_refresh', '刷新前已有缺口'], ['after_refresh', '有刷新歸因'], ['no_refresh_provenance', '未標記刷新來源']];
        const provenanceSummary = provenanceLabels.map(([key, label]) => { const count = summaryCount(audit.quality_metadata_missing_by_provenance?.[key]); return count !== null && count > 0 ? `${label} ${count}` : ''; }).filter(Boolean).join('、');
        const rerunExecutionLabels = [['full_rerun_required', '完整重跑'], ['partial_rerun_available', '局部重跑可用'], ['partial_rerun_review_required', '局部重跑需確認'], ['partial_rerun_unavailable', '無可用局部重跑'], ['not_evaluated', '重跑策略未判定']]; const rerunExecutionSummary = rerunExecutionLabels.map(([key, label]) => { const count = summaryCount(audit.quality_metadata_missing_by_rerun_execution?.[key]); return count !== null && count > 0 ? `${label} ${count}` : ''; }).filter(Boolean).join('、'); const rerunContextLabels = [['present', '原始上下文完整'], ['partial', '原始上下文部分可用'], ['artifact_fallback_available', 'artifact 前序可查'], ['missing', '無可用局部上下文'], ['not_evaluated', '上下文未判定']]; const rerunContextSummary = rerunContextLabels.map(([key, label]) => { const count = summaryCount(audit.quality_metadata_missing_by_rerun_context?.[key]); return count !== null && count > 0 ? `${label} ${count}` : ''; }).filter(Boolean).join('、');
        const artifactSummary = [['present', 'artifact 摘要可查'], ['not_found', 'artifact 無 gate 摘要'], ['unavailable', 'artifact 無法讀取']].map(([key, label]) => { const count = summaryCount(audit.artifact_quality_summary_by_status?.[key]); return count !== null && count > 0 ? `${label} ${count} 份` : ''; }).filter(Boolean).join('、');
        const artifactFieldStats = audit.artifact_quality_summary_by_field && typeof audit.artifact_quality_summary_by_field === 'object' && !Array.isArray(audit.artifact_quality_summary_by_field) ? audit.artifact_quality_summary_by_field : null;
        const artifactFieldSummary = artifactFieldStats ? missingFieldLabels.map(([key, label]) => { const count = summaryCount(artifactFieldStats[key]); return count !== null ? `${label} ${count}` : ''; }).filter(Boolean).join('、') : '';
        const pipelineQuality = audit.quality_metadata_by_pipeline && typeof audit.quality_metadata_by_pipeline === 'object' && !Array.isArray(audit.quality_metadata_by_pipeline) ? audit.quality_metadata_by_pipeline : {};
        const missingPipelineSummary = Object.entries(pipelineQuality).map(([pipeline, summary]) => { const count = summaryCount(summary?.quality_metadata_missing_reports); return count !== null && count > 0 ? `${pipeline} ${count}` : ''; }).filter(Boolean).join('、'); const pipelineContextSummary = Object.entries(pipelineQuality).map(([pipeline, summary]) => { const context = rerunContextLabels.map(([key, label]) => { const count = summaryCount(summary?.quality_metadata_missing_by_rerun_context?.[key]); return count !== null && count > 0 ? `${label} ${count}` : ''; }).filter(Boolean).join('、'); return context ? `${pipeline} ${context}` : ''; }).filter(Boolean).join('、');
        const auditItems = Array.isArray(audit.items) ? audit.items.filter(item => item && item.filename) : [];
        const returnedItemsValue = nonNegativeInteger(audit.items_returned); const returnedItems = returnedItemsValue !== null ? returnedItemsValue : audit.items_returned === undefined || audit.items_returned === null ? auditItems.length : null; const totalItemsValue = nonNegativeInteger(audit.items_total); const itemLimitProvided = audit.items_limit !== undefined && audit.items_limit !== null; const itemLimit = itemLimitProvided ? nonNegativeInteger(audit.items_limit) : undefined; const hasBoundedScopeFields = audit.items_total !== undefined && audit.items_total !== null && audit.items_returned !== undefined && audit.items_returned !== null; const boundedScopeMalformed = audit.items_total !== undefined && audit.items_total !== null && totalItemsValue === null || audit.items_returned !== undefined && audit.items_returned !== null && returnedItemsValue === null || itemLimitProvided && itemLimit === null; const boundedItemsConsistent = window.StockAgentReportQualityQueueScope?.boundedItemsConsistent; const boundedScopeNeedsConfirmation = boundedScopeMalformed || hasBoundedScopeFields && typeof boundedItemsConsistent === 'function' && !boundedItemsConsistent(totalItemsValue, returnedItems, audit.items_truncated, itemLimit);
        const auditScopeLabel = audit.selection_basis === 'latest_per_ticker_pipeline' ? '全量報告品質（每 ticker/pipeline 最新一筆）' : '全量報告品質';
        const auditParts = [freshnessSummary, currentQualitySummary].filter(Boolean), auditSummaryItems = [freshnessSummary, currentQualitySummary].filter(Boolean);
        const truncationNote = boundedScopeNeedsConfirmation ? boundedScopeMalformed ? '（範圍資料需確認）' : `（目前顯示 ${returnedItems}/${totalItemsValue}；範圍資料需確認）` : audit.items_truncated === true && missingQuality !== null && returnedItems !== null && missingQuality > returnedItems && `（目前顯示 ${returnedItems} 份，另有 ${missingQuality - returnedItems} 份未展開）`;
        if (missingQuality > 0) { const summaryParts = [`${missingQuality} 份品質 metadata 缺口${truncationNote || ''}`, repairQueueScopeSummary, repairQueueBoundedSummary, repairSampleOverlapSummary, missingFieldSummary ? `缺口：${missingFieldSummary}` : '', missingPipelineSummary ? `模式缺口：${missingPipelineSummary}` : '', pipelineContextSummary ? `模式上下文：${pipelineContextSummary}` : '', reviewSummary ? `審核狀態：${reviewSummary}` : '', reviewProgressSummary, provenanceSummary ? `來源：${provenanceSummary}` : '', rerunExecutionSummary ? `重跑策略：${rerunExecutionSummary}` : '', rerunContextSummary ? `上下文：${rerunContextSummary}` : '', artifactSummary, artifactFieldSummary ? `artifact 欄位可查：${artifactFieldSummary}` : '', coverage == null ? '' : `（${coverageLabel} ${coverage}%）`].filter(Boolean); auditParts.push(summaryParts.join('；')); auditSummaryItems.push(...summaryParts); }
        if (excludedSnapshots > 0) { const item = `${excludedSnapshots} 份 snapshot 無法驗證`; auditParts.push(item); auditSummaryItems.push(item); }
        const auditText = audit.status === 'unavailable' ? ` · ${auditScopeLabel}：暫時無法讀取` : auditParts.length ? ` · ${auditScopeLabel}：${auditParts.join('；')}` : '', auditSummaryHtml = auditSummaryItems.length ? `<div class="watchlist-daily-quality-summary"><strong class="watchlist-daily-quality-scope">${escapeHtml(auditScopeLabel)}</strong>${auditSummaryItems.map(item => `<em class="watchlist-daily-quality-item">${escapeHtml(item)}</em>`).join('')}</div>` : '';
        const auditButtons = auditItems.map(item => {
            const ticker = item.ticker || '報告';
            const pipeline = item.pipeline_id || 'v1';
            const title = item.title || '品質缺口';
            const detail = item.detail || title;
            const reasonCodes = Array.isArray(item.reason_codes) ? item.reason_codes.join(',') : '';
            const evidence = window.StockAgentReportQualityEvidence?.context?.(item) || {};
            const missingFields = evidence.missingFields || [], missingQualityFields = missingFields.join(','), artifactFields = evidence.artifactFields || [];
            const qualityReview = item.quality_review && typeof item.quality_review === 'object' ? item.quality_review : {};
            const reviewStatus = String(qualityReview.status || '').trim().toLowerCase();
            const reviewLabels = { pending: '待人工核對', approved_with_gap: '已核准保留缺口', rejected: '退回處理', deferred: '已暫緩' };
            const reviewSummary = reviewStatus ? `審核狀態：${reviewLabels[reviewStatus] || reviewStatus}` : '';
            const targetWarning = evidence.targetWarning || '', targetView = window.StockAgentReportQualityEvidence?.renderTargetContext?.({ reviewStatus: reviewSummary, evidenceContext: evidence.targetContext, warning: targetWarning }, escapeHtml, { reviewStatus: 'watchlist-quality-review-status', evidenceContext: 'watchlist-quality-evidence-context' }) || { html: `${reviewSummary ? `<small class="watchlist-quality-review-status">${escapeHtml(reviewSummary)}</small>` : ''}${evidence.targetContext ? `<small class="watchlist-quality-evidence-context">${escapeHtml(evidence.targetContext)}</small>` : ''}${targetWarning ? `<small class="quality-evidence-warning">${escapeHtml(targetWarning)}</small>` : ''}` };
            const targetContext = [reviewSummary, evidence.targetContext || ''].filter(Boolean).join('；');
            const targetDetail = [detail, targetContext].filter(Boolean).join('；');
            const targetAriaLabel = [`人工核對 ${ticker} ${pipeline}：${title}`, targetContext, targetWarning].filter(Boolean).join('；');
            return `<div class="watchlist-quality-report-target"><button class="watchlist-quality-report-button" type="button" data-quality-report="${escapeHtml(item.filename)}" data-quality-report-ticker="${escapeHtml(ticker)}" data-quality-report-pipeline="${escapeHtml(pipeline)}" data-quality-reason-codes="${escapeHtml(reasonCodes)}" data-quality-missing-fields="${escapeHtml(missingQualityFields)}" data-quality-artifact-fields="${escapeHtml(artifactFields.join(','))}" data-quality-evidence-detail="${escapeHtml(evidence.detail || targetContext)}" title="${escapeHtml(targetDetail)}" aria-label="${escapeHtml(targetAriaLabel)}"><span>查看 ${escapeHtml(ticker)} ${escapeHtml(pipeline)}</span>${targetView.html}</button><button class="watchlist-quality-review-button" type="button" data-quality-history-audit-target data-quality-history-query="${escapeHtml(item.filename)}" data-quality-history-pipeline="${escapeHtml(pipeline)}" aria-label="前往 ${escapeHtml(ticker)} ${escapeHtml(pipeline)} 的人工核對">前往人工核對</button></div>`;
        }).join('');
        const historicalAuditButton = audit.selection_basis === 'latest_per_ticker_pipeline' && missingQuality > 0
            ? '<button class="watchlist-quality-history-button" type="button" data-quality-history-audit>查看歷史版本稽核</button>'
            : '';
        const freshnessTargetsHtml = window.StockAgentWatchlistFreshnessHelpers?.targets?.(audit, escapeHtml) || ''; const currentQualityTargetsHtml = window.StockAgentWatchlistCurrentQualityHelpers?.targets?.(audit, escapeHtml) || ''; const auditControls = freshnessTargetsHtml || currentQualityTargetsHtml || historicalAuditButton || auditButtons ? `<div class="watchlist-quality-audit-actions">${currentQualityTargetsHtml}${freshnessTargetsHtml}${historicalAuditButton}${auditButtons}</div>` : '';
        if (top && top.type !== 'monitor' && total > 0) {
            const secondary = Number(queue.summary?.secondary_count ?? queue.secondary_count ?? 0), source = window.StockAgentDailyQueueContext?.sourceLabel?.(top.source) || top.source || 'queue';
            const attentionContext = window.StockAgentDailyQueueContext?.attentionContextText?.(top);
            const contextText = attentionContext ? ` · ${escapeHtml(attentionContext)}` : '';
            return `<div class="watchlist-daily-board"><strong>今日工作台</strong><span>需處理 ${escapeHtml(String(total))} 件 · 次要待辦 ${escapeHtml(String(secondary))}</span>${auditSummaryHtml || (auditText ? `<span>${escapeHtml(auditText)}</span>` : '')}<em>最高優先：${escapeHtml(top.title || '今日待處理')} · 來源：${escapeHtml(source)} · priority_score ${escapeHtml(String(top.priority_score ?? ''))}${contextText}</em>${auditControls}</div>`;
        }
        const enabled = items.filter(item => item.enabled !== false);
        const needs = enabled.filter(item => ['high', 'medium'].includes(item.decision_priority));
        const next = needs.slice(0, 3).map(item => item.ticker).join('、') || '無急件';
        const detail = auditText ? auditText.slice(3) : next;
        return `<div class="watchlist-daily-board"><strong>今日工作台</strong><span>需處理 ${escapeHtml(String(needs.length))} 檔</span>${auditSummaryHtml || `<em>${escapeHtml(detail)}</em>`}${auditControls}</div>`;
    }

    function renderSuggestions(elements, payload, escapeHtml) {
        if (elements.suggestionList) elements.suggestionList.innerHTML = (payload.items || []).map(item => `<option value="${escapeHtml(item.ticker)}">${escapeHtml(item.name || item.market || '')}</option>`).join('');
    }

    window.StockAgentWatchlistPanelHelpers = { itemPayload, priorityLabel, renderSuggestions, reportButton, resetForm, slotLabel, watchlistDailyBoard };
})();
