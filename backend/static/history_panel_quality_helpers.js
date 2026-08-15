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

    function renderHistoricalQualityAudit(audit, escapeHtml) {
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
        const pipelineQuality = audit.quality_metadata_by_pipeline && typeof audit.quality_metadata_by_pipeline === 'object' && !Array.isArray(audit.quality_metadata_by_pipeline) ? audit.quality_metadata_by_pipeline : {};
        const pipelineSummary = Object.entries(pipelineQuality).map(([pipeline, summary]) => {
            const count = Number(summary?.quality_metadata_missing_reports || 0);
            return Number.isFinite(count) && count > 0 ? `${pipeline} ${Math.floor(count)}` : '';
        }).filter(Boolean).join('、');
        const returnedValue = Number(audit.items_returned);
        const returned = Number.isFinite(returnedValue) && returnedValue >= 0 ? Math.floor(returnedValue) : Array.isArray(audit.items) ? audit.items.length : 0;
        const truncation = audit.items_truncated === true && missing > returned ? `（目前顯示 ${returned} 份，另有 ${missing - returned} 份未展開）` : '';
        const auditDetails = missing > 0
            ? `<span>${Math.floor(missing)} 份待人工核對${truncation}</span><em>${fieldSummary ? `缺口：${e(fieldSummary)}` : ''}${pipelineSummary ? `；模式缺口：${e(pipelineSummary)}` : ''}${provenanceSummary ? `；來源：${e(provenanceSummary)}` : ''}</em>`
            : `<span>符合條件的 ${Math.floor(audited)} 份歷史版本沒有品質 metadata 缺口</span>`;
        const targets = (Array.isArray(audit.items) ? audit.items : []).filter(item => item && item.filename).map(item => {
            const ticker = item.ticker || '報告';
            const pipeline = item.pipeline_id || 'v1';
            const reportDate = String(item.report_date || '').trim();
            const title = item.title || '品質缺口';
            const detail = item.detail || title;
            const reasonCodes = Array.isArray(item.reason_codes) ? item.reason_codes.join(',') : '';
            const targetLabel = reportDate ? `${ticker} ${pipeline} · ${reportDate}` : `${ticker} ${pipeline}`;
            return `<button class="history-quality-audit-target" type="button" data-quality-audit-report="${e(item.filename)}" data-quality-audit-ticker="${e(ticker)}" data-quality-audit-pipeline="${e(pipeline)}" data-quality-reason-codes="${e(reasonCodes)}" title="${e(detail)}" aria-label="${e(`人工核對 ${targetLabel}：${title}`)}">查看 ${e(targetLabel)}</button>`;
        }).join('');
        return `<div class="history-quality-audit" role="status"><div class="history-quality-audit-header"><strong>歷史版本品質稽核</strong><span>範圍：${Math.floor(audited)} 份</span></div><div class="history-quality-audit-summary">${auditDetails}</div>${targets ? `<div class="history-quality-audit-actions">${targets}</div>` : ''}</div>`;
    }

    window.StockAgentHistoryPanelQualityHelpers = {
        hasRefreshableDataTrustIssue,
        reportActionBadge,
        trackingActionNote,
        renderHistoricalQualityAudit
    };
})();
