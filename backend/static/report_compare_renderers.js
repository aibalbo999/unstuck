(function () {
    function create(options) {
        const helpers = options.helpers || window.StockAgentReportCompareHelpers;
        const { compareSummaryLabel, compareWarningMessage, dateOrderLabel, formatDelta, reportDecisionStatusLabel } = helpers;
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        const pipelineModeLabel = options.pipelineModeLabel || window.StockAgentUi?.pipelineModeLabel || ((pipelineId) => String(pipelineId || 'v1'));

        function gridCell(label, value) {
            return `<span><strong>${escapeHtml(label)}</strong><em>${escapeHtml(value)}</em></span>`;
        }

        function selectionSummary(selected) {
            if (!selected.length) return '尚未選取比較報告';
            return selected
                .map(report => `${report.ticker || 'N/A'} · ${pipelineModeLabel(report.pipeline_id || 'v1')} · ${report.date || ''}`)
                .join(' ↔ ');
        }

        function compatibilityHtml(compatibility, left, right) {
            const warnings = Array.isArray(compatibility.warnings) ? compatibility.warnings : [];
            if (!warnings.length) {
                return `<div class="report-compare-compatibility">
                    <span class="provider-sla-chip is-ok">可比較 · ${escapeHtml(dateOrderLabel(compatibility.date_order))}</span>
                </div>`;
            }
            return `<div class="report-compare-compatibility">
                ${warnings.map(item => `
                    <span class="provider-sla-chip is-${item.level === 'info' ? 'warning' : 'critical'}">
                        ${escapeHtml(compareWarningMessage(item, left, right, pipelineModeLabel))}
                    </span>
                `).join('')}
            </div>`;
        }

        function resultHtml(payload) {
            const diff = payload?.diff || {};
            const left = payload?.left || {};
            const right = payload?.right || {};
            const compatibility = payload?.compatibility || {};
            const gridRows = [
                ['比較結論', compareSummaryLabel(compatibility)],
                [left.ticker || 'Left', left.filename || ''],
                [right.ticker || 'Right', right.filename || ''],
                ['比較基準', `${pipelineModeLabel(left.pipeline_id || 'v1')} → ${pipelineModeLabel(right.pipeline_id || 'v1')}`],
                ['比較樣本', `${left.date || 'N/A'} → ${right.date || 'N/A'} · ${dateOrderLabel(compatibility.date_order)}`],
                ['使用提醒', '僅比較既有報告，不代表即時交易指令'],
                ['判讀層次', '報告差異不等於市場因果；搭配資料可信度與追蹤報酬判讀'],
                ['報告建議變化', `${diff.recommendation?.before || 'N/A'} → ${diff.recommendation?.after || 'N/A'}`],
                ['當日股價', formatDelta(diff.current_price)],
                ['3/6/12月目標', `${formatDelta(diff.target_3m)} · ${formatDelta(diff.target_6m)} · ${formatDelta(diff.target_12m)}`],
                ['資料可信度', `${diff.data_trust?.status_before || 'N/A'} → ${diff.data_trust?.status_after || 'N/A'} · ${formatDelta(diff.data_trust?.score)}`],
                ['決策狀態', `${reportDecisionStatusLabel(left)} → ${reportDecisionStatusLabel(right)}`],
                ['追蹤報酬', formatDelta(diff.tracking?.return_pct)],
                ['最新股價', formatDelta(diff.tracking?.latest_price)],
            ].map(([label, value]) => gridCell(label, value)).join('');
            return `${compatibilityHtml(compatibility, left, right)}<div class="report-compare-grid">${gridRows}</div>`;
        }

        return { resultHtml, selectionSummary };
    }

    window.StockAgentReportCompareRenderers = { create };
})();
