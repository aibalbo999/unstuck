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
        const audit = daily?.report_quality_audit || {}, missingQuality = Number(audit.quality_metadata_missing_reports || 0), coverage = audit.quality_metadata_coverage_pct;
        const auditText = audit.status === 'unavailable' ? ' · 全量報告品質：暫時無法讀取' : missingQuality > 0 ? ` · 全量報告品質：${missingQuality} 份待人工核對${coverage == null ? '' : `（覆蓋 ${coverage}%）`}` : '';
        if (top && top.type !== 'monitor' && total > 0) {
            const secondary = Number(queue.secondary_count || 0), source = window.StockAgentDailyQueueContext?.sourceLabel?.(top.source) || top.source || 'queue';
            const attentionContext = window.StockAgentDailyQueueContext?.attentionContextText?.(top);
            const contextText = attentionContext ? ` · ${escapeHtml(attentionContext)}` : '';
            return `<div class="watchlist-daily-board"><strong>今日工作台</strong><span>需處理 ${escapeHtml(String(total))} 件 · 次要待辦 ${escapeHtml(String(secondary))}${escapeHtml(auditText)}</span><em>最高優先：${escapeHtml(top.title || '今日待處理')} · 來源：${escapeHtml(source)} · priority_score ${escapeHtml(String(top.priority_score ?? ''))}${contextText}</em></div>`;
        }
        const enabled = items.filter(item => item.enabled !== false);
        const needs = enabled.filter(item => ['high', 'medium'].includes(item.decision_priority));
        const next = needs.slice(0, 3).map(item => item.ticker).join('、') || '無急件';
        const detail = auditText ? auditText.slice(3) : next;
        return `<div class="watchlist-daily-board"><strong>今日工作台</strong><span>需處理 ${escapeHtml(String(needs.length))} 檔${escapeHtml(auditText)}</span><em>${escapeHtml(detail)}</em></div>`;
    }

    function renderSuggestions(elements, payload, escapeHtml) {
        if (elements.suggestionList) elements.suggestionList.innerHTML = (payload.items || []).map(item => `<option value="${escapeHtml(item.ticker)}">${escapeHtml(item.name || item.market || '')}</option>`).join('');
    }

    window.StockAgentWatchlistPanelHelpers = { itemPayload, priorityLabel, renderSuggestions, reportButton, resetForm, slotLabel, watchlistDailyBoard };
})();
