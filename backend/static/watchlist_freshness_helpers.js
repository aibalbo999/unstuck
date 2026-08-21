(function () {
    function summaryValues(audit) {
        const summary = audit?.decision_freshness_summary || {};
        const audited = Number(summary.audited_reports), current = Number(summary.current_reports), rerun = Number(summary.needs_rerun_reports), unknown = Number(summary.unknown_reports);
        if ((summary.schema_version && summary.schema_version !== 'report_freshness_summary.v1') || summary.scope !== 'all_indexed_reports' || summary.selection_basis !== 'latest_per_ticker_pipeline' || ![audited, current, rerun, unknown].every(Number.isFinite) || audited < 0 || current < 0 || rerun < 0 || unknown < 0 || current + rerun + unknown !== audited) return null;
        return { audited, current, rerun, unknown, scope: summary.scope, selectionBasis: summary.selection_basis };
    }

    function validatedItems(audit) {
        const data = summaryValues(audit), items = audit?.decision_freshness_items || {};
        const total = Number(items.items_total), returned = Number(items.items_returned);
        if (!data || items.schema_version !== 'report_freshness_items.v1' || items.scope !== data.scope || items.selection_basis !== data.selectionBasis || ![total, returned].every(Number.isFinite) || total !== data.rerun || returned < 0 || returned > total || returned !== (Array.isArray(items.items) ? items.items.length : -1)) return null;
        return { ...data, items, total, returned };
    }

    function summary(audit) {
        const data = summaryValues(audit);
        if (!data) return '';
        return `分析新鮮度：目前一致 ${Math.floor(data.current)}、需完整重跑 ${Math.floor(data.rerun)}${data.unknown > 0 ? `、無法判定 ${Math.floor(data.unknown)}` : ''}`;
    }

    function targets(audit, escapeHtml) {
        const data = validatedItems(audit), e = escapeHtml || (value => String(value ?? ''));
        if (!data || !data.returned) return '';
        const label = data.items.items_truncated ? `待重跑報告（顯示 ${data.returned}/${data.total}）` : `待重跑報告（${data.total}）`;
        const buttons = data.items.items.map(item => {
            const ticker = e(item.ticker || '報告'), pipeline = e(item.pipeline_id || 'v1'), filename = e(item.filename || ''), reason = e(item.reason || '資料快照與分析本文不同步');
            return filename ? `<button class="watchlist-quality-history-button" type="button" data-quality-history-audit-target data-quality-history-query="${filename}" data-quality-history-pipeline="${pipeline}" aria-label="查看 ${ticker} ${pipeline} 的待重跑報告"><span>查看 ${ticker} ${pipeline}</span><small>${reason}</small></button>` : '';
        }).filter(Boolean).join('');
        return buttons ? `<div class="watchlist-quality-freshness-targets"><strong>${e(label)}</strong><div class="watchlist-quality-audit-actions">${buttons}</div></div>` : '';
    }

    window.StockAgentWatchlistFreshnessHelpers = { summary, targets };
})();
