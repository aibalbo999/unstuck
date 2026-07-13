(function () {
    function create(options) {
        const helpers = options.helpers || window.StockAgentHistoryPanelHelpers;
        const escapeHtml = options.escapeHtml || (value => String(value ?? ''));
        const recommendationTone = options.recommendationTone || (() => '');
        const normalizeRecommendation = options.normalizeRecommendation || (value => String(value || ''));
        const renderPipelineModeBadge = options.renderPipelineModeBadge || (() => '');
        const renderDataTrustBadge = options.renderDataTrustBadge || (() => '');
        const renderDataTrustReason = options.renderDataTrustReason || (() => '');
        const reportTracked = options.reportTracked || (() => false);

        function trackButton(report) {
            const tracked = reportTracked(report);
            const label = tracked ? '取消追蹤' : '加入追蹤';
            return `<button class="decision-track-toggle ${tracked ? 'is-tracked' : ''}" type="button" data-track-filename="${escapeHtml(report.filename)}" aria-label="${escapeHtml(label)} ${escapeHtml(report.ticker || '')}">${escapeHtml(label)}</button>`;
        }
        function reportHasTracking(report) {
            return report.decision_tracking && report.decision_tracking.status && report.decision_tracking.status !== 'unavailable';
        }
        function previewPrimaryValue(report) {
            return report.preview?.primary?.value || report.recommendation?.recommendation;
        }
        function previewPrimaryTone(report) {
            return report.preview?.primary?.tone || recommendationTone(previewPrimaryValue(report));
        }
        function previewListValues(report) {
            const metrics = Array.isArray(report.preview?.list_metrics) ? report.preview.list_metrics : [];
            if (metrics.length) return metrics.slice(0, 2).map(item => item?.value || 'N/A');
            return [report.recommendation?.target_12m || 'N/A', report.recommendation?.confidence || 'N/A'];
        }
        function isSwingTradeReport(report) {
            return report?.pipeline_id === 'v4' || report?.preview?.kind === 'swing_trade';
        }
        function swingMetricItems(report) {
            const preview = report?.preview || {};
            const preferred = Array.isArray(preview.list_metrics) && preview.list_metrics.length
                ? preview.list_metrics
                : (Array.isArray(preview.targets) ? preview.targets : []);
            return preferred.filter(item => item && (item.value || item.label)).slice(0, 3);
        }
        function swingMetricCell(item) {
            const title = `${item?.label || '短線'} ${item?.value || 'N/A'}`;
            return `<span class="tracking-target-cell tracking-target-chip is-swing" title="${escapeHtml(title)}"><span class="tracking-target-period">${escapeHtml(item?.label || '短線')}</span><strong class="tracking-target-value">${escapeHtml(item?.value || 'N/A')}</strong><span class="tracking-target-label">短線</span></span>`;
        }
        function swingMetricGrid(report) {
            const items = swingMetricItems(report);
            return items.length ? `<div class="tracking-target-grid tracking-swing-grid">${items.map(swingMetricCell).join('')}</div>` : '';
        }
        function swingStatusText(report) {
            const metrics = Array.isArray(report?.preview?.metrics) ? report.preview.metrics : [];
            const risk = metrics.find(item => String(item?.label || '').includes('風險'));
            return risk?.value ? `風險 ${risk.value}` : '短線計畫';
        }
        function groupLatestReport(group) {
            return (group.reports || []).reduce((best, report) => (
                !best || Number(report.timestamp || 0) > Number(best.timestamp || 0) ? report : best
            ), null);
        }
        function reportCard(report, trackingCompact) {
            const tracking = report.decision_tracking || {};
            const pipelineLabel = helpers.trackingPipelineLabel(report);
            const swingTrade = isSwingTradeReport(report);
            const primaryValue = swingTrade ? previewPrimaryValue(report) : (tracking.recommendation || report.recommendation?.recommendation);
            const primaryTone = swingTrade ? previewPrimaryTone(report) : recommendationTone(primaryValue);
            const statusText = swingTrade ? swingStatusText(report) : (tracking.tracking_summary_status || helpers.formatPct(tracking.return_pct));
            const trackingStatusClass = trackingCompact ? `tracking-compact-note ${helpers.trackingSummaryTone(tracking)}` : helpers.trackingTone(tracking);
            const targetGrid = swingTrade ? swingMetricGrid(report) : `<div class="tracking-target-grid">${helpers.targetComparisonCell(tracking, 'target_3m', escapeHtml)}${helpers.targetComparisonCell(tracking, 'target_6m', escapeHtml)}${helpers.targetComparisonCell(tracking, 'target_12m', escapeHtml)}</div>`;
            return `
                <div class="tracking-report-card" data-filename="${escapeHtml(report.filename)}" role="button" tabindex="0" aria-label="預覽 ${escapeHtml(report.ticker || 'N/A')} ${escapeHtml(pipelineLabel)} 追蹤">
                    <div class="tracking-report-cell tracking-report-head">
                        <strong>${escapeHtml(pipelineLabel)}</strong>
                        <span class="tracking-report-date">${escapeHtml(report.date || '')}</span>
                        ${helpers.trackingActionNote(report, escapeHtml)}
                    </div>
                    <div class="tracking-report-line tracking-report-metrics">
                        <span class="tracking-recommendation ${primaryTone}">${escapeHtml(swingTrade ? primaryValue : normalizeRecommendation(primaryValue))}</span>
                        <strong class="tracking-latest-price">${escapeHtml(helpers.formatNumber(tracking.latest_price))}</strong>
                        <span class="${swingTrade ? 'tracking-compact-note is-swing' : trackingStatusClass}">${escapeHtml(statusText)}</span>
                    </div>
                    ${trackingCompact ? '' : targetGrid}
                </div>
            `;
        }
        function visibleTrackingGroups(groups) {
            return (groups || [])
                .map(group => ({ ...group, reports: (group.reports || []).filter(reportHasTracking) }))
                .filter(group => group.reports.length)
                .slice(0, 8);
        }
        function renderTrackingGroups(groups, trackingCompact) {
            const visibleGroups = visibleTrackingGroups(groups);
            if (!visibleGroups.length) return '';
            return `
                <div class="decision-tracking-title">每日決策追蹤表<span>${trackingCompact ? '精簡比較' : '高密度三模式比較'}</span></div>
                <div class="tracking-group-list">
                    ${visibleGroups.map(group => {
                        const latest = groupLatestReport(group) || {};
                        const tracking = latest.decision_tracking || {};
                        const ticker = group.ticker || latest.ticker || '';
                        return `
                            <section class="tracking-stock-group tracking-density-row">
                                <div class="tracking-stock-cell">
                                    <button class="tracking-stock-snapshot-button" type="button" data-tracking-snapshot="${escapeHtml(ticker)}" aria-label="查看 ${escapeHtml(ticker || 'N/A')} 股票快照">${escapeHtml(ticker || 'N/A')}</button>
                                    <span class="tracking-company-name">${escapeHtml(group.company_name || latest.company_name || '')}</span>
                                    <span class="tracking-stock-price">最新 ${escapeHtml(helpers.formatNumber(tracking.latest_price))}</span>
                                </div>
                                <div class="tracking-group-reports">${group.reports.map(report => reportCard(report, trackingCompact)).join('')}</div>
                            </section>
                        `;
                    }).join('')}
                </div>
            `;
        }
        function renderHistoryList(reports) {
            if (!reports || reports.length === 0) return '<div style="color: var(--text-secondary); font-size: 0.9rem; text-align: center; padding: 20px 0;">尚無報告紀錄</div>';
            return reports.map(r => `
                <div class="history-item" data-filename="${escapeHtml(r.filename)}" data-ticker="${escapeHtml(r.ticker)}" data-pipeline="${escapeHtml(r.pipeline_id || 'v1')}">
                    <div class="history-info" role="button" tabindex="0" aria-label="預覽 ${escapeHtml(r.ticker || 'N/A')} 報告">
                        <div class="history-ticker">${escapeHtml(r.ticker)}${r.company_name && r.company_name !== r.ticker ? `<span class="history-company">${escapeHtml(r.company_name)}</span>` : ''}</div>
                        <div class="history-date">
                            <span>${escapeHtml(r.date)}</span>
                            ${renderPipelineModeBadge(r.pipeline_id || 'v1')}
                            ${renderDataTrustBadge(r.data_trust)}
                            ${renderDataTrustReason(r.data_trust)}
                            ${helpers.reportActionBadge(r, escapeHtml)}
                        </div>
                        <div class="history-decision">
                            <span class="history-rec ${recommendationTone(previewPrimaryValue(r))}">${escapeHtml(normalizeRecommendation(previewPrimaryValue(r)))}</span>
                            ${previewListValues(r).map(value => `<span>${escapeHtml(value)}</span>`).join('')}
                            ${helpers.renderTrackingBadge(r.decision_tracking, escapeHtml)}
                        </div>
                    </div>
                    ${trackButton(r)}
                    <button class="delete-btn" title="刪除報告" aria-label="刪除 ${escapeHtml(r.ticker || r.filename)} 報告" data-delete-filename="${escapeHtml(r.filename)}">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                    </button>
                </div>
            `).join('');
        }
        return { reportHasTracking, groupLatestReport, renderHistoryList, renderReportCard: reportCard, renderTrackingGroups };
    }
    window.StockAgentHistoryPanelRenderers = { create };
})();
