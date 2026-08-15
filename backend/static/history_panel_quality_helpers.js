(function () {
    const qualityPolicy = () => window.StockAgentReportQualityPolicy || {};
    function hasRefreshableDataTrustIssue(report) {
        return Boolean(qualityPolicy().hasRefreshableDataTrustIssue?.(report));
    }
    function hasProviderSlaOnlyPartial(report) {
        return Boolean(qualityPolicy().hasProviderSlaOnlyPartial?.(report));
    }
    function reportNeedsDataRefresh(report) {
        return Boolean(qualityPolicy().reportNeedsDataRefresh?.(report));
    }
    function reportActionBadge(report, escapeHtml) {
        const status = qualityPolicy().dataTrustStatus?.(report) || 'unknown';
        const action = qualityPolicy().reportRecommendedAction?.(report);
        const hasActionPolicy = typeof qualityPolicy().reportRecommendedAction === 'function';
        const useLegacyAction = !hasActionPolicy || (!action && !report.filename);
        const qualityGateAction = qualityPolicy().reportQualityGateAction?.(report);
        let label = '可直接使用';
        let tone = 'ok';
        let detail = '資料與結論可直接查看';
        if (action?.type === 'manual_review' && status === 'error') {
            label = '暫勿採用'; tone = 'critical'; detail = '來源異常，請先重跑或改看其他報告';
        } else if (action?.type === 'manual_review' && qualityGateAction) {
            label = qualityGateAction.label; tone = qualityGateAction.tone; detail = qualityGateAction.detail;
        } else if (action?.type === 'manual_review') {
            label = '需人工查看'; tone = 'warning'; detail = '請開啟報告確認品質警示';
        } else if (useLegacyAction && qualityGateAction) {
            label = qualityGateAction.label; tone = qualityGateAction.tone; detail = qualityGateAction.detail;
        } else if (action?.type === 'rerun_full_report') {
            label = '建議完整重跑'; tone = 'critical'; detail = '結論可能已落後於最新資料';
        } else if (action?.type === 'refresh_data_snapshot') {
            label = '建議刷新資料'; tone = 'warning'; detail = '先刷新資料快照再決策';
        } else if (useLegacyAction && qualityPolicy().reportNeedsRerun?.(report)) {
            label = '建議完整重跑'; tone = 'critical'; detail = '結論可能已落後於最新資料';
        } else if (useLegacyAction && reportNeedsDataRefresh(report)) {
            label = '建議刷新資料'; tone = 'warning'; detail = '先刷新資料快照再決策';
        } else if (status === 'partial') {
            label = hasProviderSlaOnlyPartial(report) ? '來源提醒' : '資料需留意';
            tone = 'warning'; detail = '資料已是最新快照，請查看來源審計與健康度';
        }
        return `<span class="history-action-badge is-${tone}" title="${escapeHtml(detail)}">${escapeHtml(label)}</span>`;
    }
    function trackingActionNote(report, escapeHtml) {
        const action = qualityPolicy().reportRecommendedAction?.(report);
        const hasActionPolicy = typeof qualityPolicy().reportRecommendedAction === 'function';
        const useLegacyAction = !hasActionPolicy || (!action && !report.filename);
        let label = '', tone = '', detail = '';
        if (action?.type === 'rerun_full_report') {
            label = '需完整重跑'; tone = 'critical';
            detail = qualityPolicy().reportRerunMessage?.(report) || '資料快照已刷新，投資結論需要完整重跑。';
        } else if (action?.type === 'refresh_data_snapshot') {
            label = '需刷新資料'; tone = 'warning'; detail = '先刷新資料快照，再用追蹤結果做決策。';
        } else if (useLegacyAction && qualityPolicy().reportNeedsRerun?.(report)) {
            label = '需完整重跑'; tone = 'critical';
            detail = qualityPolicy().reportRerunMessage?.(report) || '資料快照已刷新，投資結論需要完整重跑。';
        } else if (useLegacyAction && reportNeedsDataRefresh(report)) {
            label = '需刷新資料'; tone = 'warning'; detail = '先刷新資料快照，再用追蹤結果做決策。';
        }
        return label ? `<span class="tracking-action-note is-${tone}" title="${escapeHtml(detail)}">${escapeHtml(label)}</span>` : '';
    }
    function renderQualityReview(item, targetLabel, escapeHtml) {
        const e = escapeHtml || (value => String(value ?? ''));
        const review = item.quality_review && typeof item.quality_review === 'object' ? item.quality_review : {};
        const status = String(review.status || 'pending').trim() || 'pending';
        const label = String(review.decision_label || (status === 'pending' ? '待人工核對' : status)).trim();
        const note = String(review.note || '').trim();
        const summary = status === 'pending' ? '人工審核：待核對' : `人工審核：${label}${review.event_count > 1 ? `（第 ${Math.floor(Number(review.event_count))} 次）` : ''}`;
        const revision = String(item.report_quality_revision || review.report_quality_revision || '').trim();
        const revisionLabel = revision.length > 12 ? `${revision.slice(0, 12)}...` : revision;
        const revisionHtml = revision ? `<small class="history-quality-audit-review-revision" title="${e(`完整版本識別碼：${revision}`)}" aria-label="${e(`目前報告版本識別碼：${revision}`)}">目前版本識別碼：${e(revisionLabel)}</small>` : '';
        const history = Array.isArray(item.quality_review_history) ? item.quality_review_history : [];
        const historyHtml = history.length ? `<details class="history-quality-audit-review-history"><summary>審核紀錄（${history.length} 次）</summary><ol>${history.map(entry => {
            const eventId = Number(entry.event_id) > 0 ? `#${Math.floor(Number(entry.event_id))}` : '';
            const eventLabel = [eventId, entry.reviewed_at, entry.reviewer_label, entry.decision_label].filter(Boolean).join(' · ');
            return `<li><span>${e(eventLabel)}</span><small>${e(entry.note || '')}</small></li>`;
        }).join('')}</ol></details>` : '';
        const actions = revision ? [['approved_with_gap', '核准保留缺口'], ['rejected', '退回處理'], ['deferred', '暫緩']].map(([decision, text]) => `<button class="history-quality-audit-review" type="button" data-quality-review-decision="${decision}" data-quality-review-filename="${e(item.filename)}" data-quality-review-ticker="${e(item.ticker || '')}" data-quality-review-pipeline="${e(item.pipeline_id || 'v1')}" data-quality-review-revision="${e(revision)}" aria-label="${e(`${text}：${targetLabel}`)}">${text}</button>`).join('') : '';
        return `<div class="history-quality-audit-review" title="${e(note ? `${summary}：${note}` : summary)}">${revisionHtml}<small>${e(summary)}</small>${historyHtml}${actions ? `<div class="history-quality-audit-review-actions" aria-label="${e(`更新人工審核：${targetLabel}`)}">${actions}</div>` : ''}</div>`;
    }
    function renderQualityReviewStatusFilters(audit, escapeHtml) {
        const e = escapeHtml || (value => String(value ?? ''));
        const current = String(audit?.review_status_filter || 'all').trim().toLowerCase() || 'all';
        const labels = [['all', '全部審核狀態'], ['pending', '待人工核對'], ['approved_with_gap', '已核准保留缺口'], ['rejected', '退回處理'], ['deferred', '已暫緩']];
        const buttons = labels.map(([key, label]) => {
            const count = Number(audit?.quality_review_by_status?.[key] || 0);
            if (key === 'all' ? current === 'all' : current !== key && (!Number.isFinite(count) || count <= 0)) return '';
            return `<button class="history-quality-audit-filter" type="button" data-quality-audit-review-status="${e(key)}"${current === key ? ' aria-pressed="true"' : ''}>${e(label)}${key === 'all' ? '' : `（${Math.floor(count)}）`}</button>`;
        }).filter(Boolean).join('');
        return buttons ? `<div class="history-quality-audit-filter-actions" aria-label="按審核狀態查看品質缺口">${buttons}</div>` : '';
    }

    window.StockAgentHistoryPanelQualityHelpers = {
        hasRefreshableDataTrustIssue,
        reportActionBadge,
        trackingActionNote,
        renderQualityReview,
        renderQualityReviewStatusFilters
    };
})();
