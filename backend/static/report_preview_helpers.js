(function () {
    const FALLBACK_SUMMARY = '這份報告沒有可讀的一頁式摘要，可直接查看完整報告；報告建議仍需自行判斷。';
    const qualityPolicy = () => window.StockAgentReportQualityPolicy || {};

    function legacyPreview(report, rec, options) {
        return {
            title: `${report.ticker} 報告建議`,
            primary: { label: '報告建議', value: options.normalizeRecommendation(rec.recommendation), tone: options.recommendationTone(rec.recommendation) },
            metrics: [{ label: '當日股價', value: rec.current_price || 'N/A' }, { label: '信心', value: rec.confidence || 'N/A' }],
            targets: [{ label: '3個月', value: rec.target_3m || 'N/A' }, { label: '6個月', value: rec.target_6m || 'N/A' }, { label: '12個月', value: rec.target_12m || 'N/A' }],
            summary: rec.summary || FALLBACK_SUMMARY
        };
    }

    function metricCard(item, className, escapeHtml) {
        const tone = item?.tone ? ` class="${escapeHtml(item.tone)}"` : '';
        const cardClass = className ? ` class="${className}"` : '';
        return `<div${cardClass}><span class="preview-label">${escapeHtml(item?.label || '')}</span><strong${tone}>${escapeHtml(item?.value || 'N/A')}</strong></div>`;
    }

    function renderMetrics(container, metrics, className, escapeHtml) {
        if (!container) return;
        const items = (metrics || []).filter(Boolean);
        container.hidden = !items.length;
        container.innerHTML = items.map(item => metricCard(item, className, escapeHtml)).join('');
    }

    function reportAnalysisCompletenessBadge(report, escapeHtml) {
        const value = report?.analysis_completeness;
        if (!value || typeof value !== 'object') return '';
        const labels = {complete:'分析完整', observation:'正常觀望', degraded:'資料不足降級', quality_warning:'分析品質警告'};
        const label = value.status === 'quality_warning' && value.quality_warning !== true ? '分析完整度未確認' : (labels[value.status] || '分析完整度未確認');
        const tone = value.status === 'complete' || value.status === 'observation' ? 'ok' : 'warning';
        return `<span class="history-action-badge is-${tone}" title="${escapeHtml(value.summary || '分析完整度尚未確認')}" aria-label="${escapeHtml(`分析完整度：${label}`)}">${escapeHtml(label)}</span>`;
    }

    function reportQualityBadge(report, escapeHtml) {
        const completeness = reportAnalysisCompletenessBadge(report, escapeHtml);
        const action = qualityPolicy().reportQualityGateAction?.(report);
        if (!action) return completeness;
        const evidence = window.StockAgentReportQualityEvidence?.context?.(report);
        const detail = evidence?.detail || action.detail;
        const canOpenAudit = action.label === '結構化品質缺口' && evidence?.hasStructuredGap && report?.filename;
        const attrs = canOpenAudit
            ? ` type="button" data-quality-history-audit-target data-quality-history-query="${escapeHtml(report.filename)}" data-quality-history-pipeline="${escapeHtml(report.pipeline_id || 'v1')}" data-quality-evidence-detail="${escapeHtml(detail)}" aria-label="${escapeHtml(`前往 ${report.ticker || '報告'} ${report.pipeline_id || 'v1'} 的歷史品質稽核：${detail}`)}"`
            : '';
        const tag = canOpenAudit ? 'button' : 'span';
        return `<${tag} class="history-action-badge is-${action.tone}${canOpenAudit ? ' is-clickable' : ''}"${attrs} title="${escapeHtml(detail)}">${escapeHtml(action.label)}</${tag}>${completeness}`;
    }

    function withAnalysisCompletenessBadge(report, badge, defaultUsable, escapeHtml) {
        const completeness = reportAnalysisCompletenessBadge(report, escapeHtml);
        return completeness && defaultUsable && !['complete', 'observation'].includes(report.analysis_completeness?.status) ? completeness : badge + completeness;
    }

    function reportReadingNotice(report, escapeHtml) {
        const boundary = qualityPolicy().reportReadingBoundary?.(report);
        if (!boundary) return '';
        return `<strong>報告使用範圍與判讀限制：${escapeHtml(boundary.label)}</strong><span>${escapeHtml(boundary.detail)}</span>`;
    }

    window.StockAgentReportPreviewHelpers = {
        FALLBACK_SUMMARY, legacyPreview, metricCard, renderMetrics, reportQualityBadge, reportReadingNotice, reportAnalysisCompletenessBadge, withAnalysisCompletenessBadge
    };
})();
