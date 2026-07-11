(function () {
    const uniqueValues = (contexts, getter) => [...new Set(contexts.map(getter).filter(Boolean))].slice(0, 3);
    const rowContext = row => row?.context || {};
    const sourceLabels = { report_repair: '報告修復', provider_impact: '資料來源', notification_delivery: '通知通道', backtest_due: '決策回測', rerun_report: '報告重跑', model_route_budget: '模型路由', watchlist: '追蹤清單', screener: '候選清單', free_mode: '免費模式', monitor: '監控' };
    const sourceKey = source => String(source ?? '').trim();
    const sourceLabel = source => sourceLabels[sourceKey(source)] || sourceKey(source);
    const sourceText = source => sourceLabels[sourceKey(source)] ? `${sourceLabel(source)} (${sourceKey(source)})` : sourceKey(source);
    const hasText = value => Boolean(String(value ?? '').trim());
    const contextSourceText = context => hasText(context.source_text) ? context.source_text : (hasText(context.source_label) && hasText(context.source) ? `${String(context.source_label).trim()} (${sourceKey(context.source)})` : sourceText(context.source));

    function attentionContextText(item) {
        const rows = Array.isArray(item?.attention_contexts) ? item.attention_contexts : [];
        const contexts = rows.map(rowContext);
        if (!contexts.length && !rows.length) return '';
        const tickers = uniqueValues(contexts, context => context.ticker);
        const reports = uniqueValues(contexts, context => context.filename || context.report_filename);
        const labels = uniqueValues(contexts, context => context.operator_action_label);
        const targets = uniqueValues(contexts, context => context.target_panel || context.target_tab);
        const sources = uniqueValues(contexts, context => contextSourceText(context));
        const ranks = uniqueValues(contexts, context => Number(context.queue_rank || 0) ? String(context.queue_rank) : '');
        const displayedCounts = uniqueValues(
            contexts,
            context => Number(context.queue_displayed_count || 0) ? String(context.queue_displayed_count) : ''
        );
        const hasTopPriority = contexts.some(context => context.is_top_priority === true);
        const channels = uniqueValues(rows, row => row.channel_id);
        const statuses = uniqueValues(rows, row => row.delivery_status);
        const attempts = uniqueValues(rows, row => Number(row.attempt_count || 0) ? String(row.attempt_count) : '');
        const parts = [];
        if (tickers.length) parts.push(`影響 ${tickers.join('、')}`);
        if (reports.length) parts.push(`報告 ${reports.join('、')}`);
        if (labels.length) parts.push(`CTA ${labels.join('、')}`);
        else if (targets.length) parts.push(`目標 ${targets.join('、')}`);
        if (sources.length) parts.push(`原始來源 ${sources.join('、')}`);
        if (ranks.length) parts.push(`隊列 ${ranks.join('、')}`);
        if (displayedCounts.length) parts.push(`顯示 ${displayedCounts.join('、')}`);
        if (hasTopPriority) parts.push('最高優先');
        if (!parts.length) {
            if (channels.length) parts.push(`通道 ${channels.join('、')}`);
            if (statuses.length) parts.push(`狀態 ${statuses.join('、')}`);
            if (attempts.length) parts.push(`嘗試 ${attempts.join('、')}`);
        }
        return parts.join(' / ');
    }

    window.StockAgentDailyQueueContext = { attentionContextText, sourceLabel, sourceText, sourceLabels: Object.freeze({ ...sourceLabels }) };
})();
