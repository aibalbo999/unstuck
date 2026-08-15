(function () {
    function slotLabel(slots, schedules) {
        return (slots || []).map(slot => schedules?.[slot]?.label || slot).join('、') || '未排程';
    }

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
        const audit = daily?.report_quality_audit || {}, missingQuality = Number(audit.quality_metadata_missing_reports || 0), excludedSnapshots = Number(audit.snapshot_invalid_reports || 0) + Number(audit.snapshot_unverified_reports || 0), coverage = audit.quality_metadata_coverage_pct, coverageLabel = audit.quality_metadata_coverage_basis === 'verified_snapshot_reports' ? '已驗證快照覆蓋' : '覆蓋';
        const missingFieldLabels = [['report_conformance', '報告一致性'], ['evidence_exit_gate', '證據關卡'], ['content_credibility', '內容可信度']];
        const missingFieldSummary = missingFieldLabels.map(([key, label]) => { const count = Number(audit.missing_quality_field_counts?.[key] || 0); return Number.isFinite(count) && count > 0 ? `${label} ${Math.floor(count)}` : ''; }).filter(Boolean).join('、');
        const provenanceLabels = [['after_refresh', '刷新後缺口'], ['no_refresh_provenance', '未標記刷新來源']];
        const provenanceSummary = provenanceLabels.map(([key, label]) => { const count = Number(audit.quality_metadata_missing_by_provenance?.[key] || 0); return Number.isFinite(count) && count > 0 ? `${label} ${Math.floor(count)}` : ''; }).filter(Boolean).join('、');
        const pipelineQuality = audit.quality_metadata_by_pipeline && typeof audit.quality_metadata_by_pipeline === 'object' && !Array.isArray(audit.quality_metadata_by_pipeline) ? audit.quality_metadata_by_pipeline : {};
        const missingPipelineSummary = Object.entries(pipelineQuality).map(([pipeline, summary]) => { const count = Number(summary?.quality_metadata_missing_reports || 0); return Number.isFinite(count) && count > 0 ? `${pipeline} ${Math.floor(count)}` : ''; }).filter(Boolean).join('、');
        const auditItems = Array.isArray(audit.items) ? audit.items.filter(item => item && item.filename) : [];
        const returnedItemsValue = Number(audit.items_returned);
        const returnedItems = Number.isFinite(returnedItemsValue) && returnedItemsValue >= 0 ? Math.floor(returnedItemsValue) : auditItems.length;
        const auditScopeLabel = audit.selection_basis === 'latest_per_ticker_pipeline' ? '全量報告品質（每 ticker/pipeline 最新一筆）' : '全量報告品質';
        const auditParts = [];
        const truncationNote = audit.items_truncated === true && missingQuality > returnedItems && `（目前顯示 ${returnedItems} 份，另有 ${missingQuality - returnedItems} 份未展開）`;
        if (missingQuality > 0) auditParts.push(`${missingQuality} 份待人工核對${truncationNote || ''}${missingFieldSummary ? `；缺口：${missingFieldSummary}` : ''}${missingPipelineSummary ? `；模式缺口：${missingPipelineSummary}` : ''}${provenanceSummary ? `；來源：${provenanceSummary}` : ''}${coverage == null ? '' : `（${coverageLabel} ${coverage}%）`}`);
        if (excludedSnapshots > 0) auditParts.push(`${excludedSnapshots} 份 snapshot 無法驗證`);
        const auditText = audit.status === 'unavailable' ? ` · ${auditScopeLabel}：暫時無法讀取` : auditParts.length ? ` · ${auditScopeLabel}：${auditParts.join('；')}` : '';
        const auditButtons = auditItems.map(item => {
            const ticker = item.ticker || '報告';
            const pipeline = item.pipeline_id || 'v1';
            const title = item.title || '品質缺口';
            const detail = item.detail || title;
            const reasonCodes = Array.isArray(item.reason_codes) ? item.reason_codes.join(',') : '';
            const missingQualityFields = Array.isArray(item.missing_quality_fields) ? item.missing_quality_fields.join(',') : '';
            return `<button class="watchlist-quality-report-button" type="button" data-quality-report="${escapeHtml(item.filename)}" data-quality-report-ticker="${escapeHtml(ticker)}" data-quality-report-pipeline="${escapeHtml(pipeline)}" data-quality-reason-codes="${escapeHtml(reasonCodes)}" data-quality-missing-fields="${escapeHtml(missingQualityFields)}" title="${escapeHtml(detail)}" aria-label="${escapeHtml(`人工核對 ${ticker} ${pipeline}：${title}`)}">查看 ${escapeHtml(ticker)} ${escapeHtml(pipeline)}</button>`;
        }).join('');
        const historicalAuditButton = audit.selection_basis === 'latest_per_ticker_pipeline' && missingQuality > 0
            ? '<button class="watchlist-quality-history-button" type="button" data-quality-history-audit>查看歷史版本稽核</button>'
            : '';
        const auditControls = historicalAuditButton || auditButtons
            ? `<div class="watchlist-quality-audit-actions">${historicalAuditButton}${auditButtons}</div>`
            : '';
        if (top && top.type !== 'monitor' && total > 0) {
            const secondary = Number(queue.secondary_count || 0), source = window.StockAgentDailyQueueContext?.sourceLabel?.(top.source) || top.source || 'queue';
            const attentionContext = window.StockAgentDailyQueueContext?.attentionContextText?.(top);
            const contextText = attentionContext ? ` · ${escapeHtml(attentionContext)}` : '';
            return `<div class="watchlist-daily-board"><strong>今日工作台</strong><span>需處理 ${escapeHtml(String(total))} 件 · 次要待辦 ${escapeHtml(String(secondary))}${escapeHtml(auditText)}</span><em>最高優先：${escapeHtml(top.title || '今日待處理')} · 來源：${escapeHtml(source)} · priority_score ${escapeHtml(String(top.priority_score ?? ''))}${contextText}</em>${auditControls}</div>`;
        }
        const enabled = items.filter(item => item.enabled !== false);
        const needs = enabled.filter(item => ['high', 'medium'].includes(item.decision_priority));
        const next = needs.slice(0, 3).map(item => item.ticker).join('、') || '無急件';
        const detail = auditText ? auditText.slice(3) : next;
        return `<div class="watchlist-daily-board"><strong>今日工作台</strong><span>需處理 ${escapeHtml(String(needs.length))} 檔${escapeHtml(auditText)}</span><em>${escapeHtml(detail)}</em>${auditControls}</div>`;
    }

    function renderSuggestions(elements, payload, escapeHtml) {
        if (elements.suggestionList) elements.suggestionList.innerHTML = (payload.items || []).map(item => `<option value="${escapeHtml(item.ticker)}">${escapeHtml(item.name || item.market || '')}</option>`).join('');
    }

    window.StockAgentWatchlistPanelHelpers = { itemPayload, priorityLabel, renderSuggestions, reportButton, resetForm, slotLabel, watchlistDailyBoard };
})();
