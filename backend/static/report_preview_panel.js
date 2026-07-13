(function () {
    const helpers = window.StockAgentReportPreviewHelpers;
    const qualityPolicy = () => window.StockAgentReportQualityPolicy || {};
    const trackingHelpers = window.StockAgentReportPreviewTrackingHelpers;
    const rerunHelpers = window.StockAgentReportPreviewRerunHelpers;

    function create(options) {
        const elements = options.elements || {};
        const doc = typeof document === 'undefined' ? null : document;
        elements.decisionRow = elements.decisionRow || elements.root?.querySelector?.('.preview-decision-row');
        elements.targets = elements.targets || elements.root?.querySelector?.('.preview-targets');
        elements.readingNotice = elements.readingNotice || elements.root?.querySelector?.('.preview-reading-notice');
        elements.trackingRoot = elements.trackingRoot || doc?.getElementById('preview-tracking');
        elements.trackingLatest = elements.trackingLatest || doc?.getElementById('preview-tracking-latest');
        elements.trackingReturn = elements.trackingReturn || doc?.getElementById('preview-tracking-return');
        elements.trackingGap = elements.trackingGap || doc?.getElementById('preview-tracking-gap');
        elements.trackingSummary = elements.trackingSummary || doc?.getElementById('preview-tracking-summary');
        elements.temporalMemoryRoot = elements.temporalMemoryRoot || doc?.getElementById('preview-temporal-memory');

        function setPreviewOpen(open) {
            if (elements.workspace) elements.workspace.classList.toggle('has-preview', open);
        }

        function show(report) {
            if (!report || !elements.root) return false;
            const rec = report.recommendation || {};
            const pipelineId = report.pipeline_id || 'v1';
            const preview = report.preview || helpers.legacyPreview(report, rec, options);
            const decisionMetrics = [preview.primary, ...(preview.metrics || [])].filter(Boolean);

            elements.mode.innerHTML = `${options.renderPipelineModeBadge(pipelineId)}${options.renderDataTrustBadge(report.data_trust)}${helpers.reportQualityBadge(report, options.escapeHtml)}<span class="preview-date">${options.escapeHtml(report.date || '')}</span>`;
            rerunHelpers.configureRerunButtons(elements, pipelineId, options.pipelineMeta);
            elements.title.textContent = preview.title || `${report.ticker} 報告建議`;
            if (elements.readingNotice) {
                const boundary = qualityPolicy().reportReadingBoundary?.(report);
                elements.readingNotice.hidden = !boundary;
                elements.readingNotice.className = boundary ? `preview-reading-notice is-${boundary.state}` : 'preview-reading-notice';
                elements.readingNotice.innerHTML = boundary ? helpers.reportReadingNotice(report, options.escapeHtml) : '';
            }
            helpers.renderMetrics(elements.decisionRow, decisionMetrics, 'preview-decision', options.escapeHtml);
            helpers.renderMetrics(elements.targets, preview.targets, '', options.escapeHtml);
            elements.summary.textContent = preview.summary || rec.summary || helpers.FALLBACK_SUMMARY;
            trackingHelpers.renderTracking(report.decision_tracking, elements);
            if (window.StockAgentTemporalMemoryPanel) {
                window.StockAgentTemporalMemoryPanel.render(report.temporal_memory, elements.temporalMemoryRoot, options.escapeHtml);
            }

            if (elements.staleNotice) {
                const recommendedAction = qualityPolicy().reportRecommendedAction?.(report);
                const hasActionPolicy = typeof qualityPolicy().reportRecommendedAction === 'function';
                const useLegacyRerun = !hasActionPolicy || (!recommendedAction && !report.filename);
                const needsRerun = recommendedAction?.type === 'rerun_full_report'
                    || (useLegacyRerun && Boolean(qualityPolicy().reportNeedsRerun?.(report)));
                const staleMessage = qualityPolicy().reportRerunMessage?.(report) || '資料快照已刷新，投資結論需要完整重跑。';
                elements.staleNotice.textContent = staleMessage;
                elements.staleNotice.hidden = !needsRerun;
            }

            elements.root.hidden = false;
            setPreviewOpen(true);
            return true;
        }

        function hide() {
            if (elements.root) elements.root.hidden = true;
            if (elements.trackingRoot) elements.trackingRoot.hidden = true;
            if (elements.temporalMemoryRoot) elements.temporalMemoryRoot.hidden = true;
            setPreviewOpen(false);
        }

        function setStatus(message) {
            if (!elements.staleNotice) return;
            elements.staleNotice.textContent = message || '';
            elements.staleNotice.hidden = !message;
        }

        return { hide, setStatus, show };
    }

    window.StockAgentReportPreviewPanel = { create };
})();
