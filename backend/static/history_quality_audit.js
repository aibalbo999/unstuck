(function () {
    function create(options) {
        const apiClient = options.apiClient;
        const ui = options.ui;
        const element = options.element;
        const openReport = options.openReport || (() => {});
        const onSelectPipeline = options.onSelectPipeline || (() => {});
        const notify = options.notify || { error: () => {} };
        const itemLimit = 5;
        let loadVersion = 0, itemOffset = 0, filterKey = '', currentValues = null, lastAudit = null;

        function auditFilterKey(values) {
            return JSON.stringify([values?.includeVersions, values?.query || '', values?.pipelineFilter || 'all']);
        }

        function render(audit) {
            if (!element) return;
            if (!audit) {
                element.hidden = true;
                element.innerHTML = '';
                element.removeAttribute('aria-busy');
                return;
            }
            element.hidden = false;
            element.setAttribute('aria-busy', 'true');
            element.innerHTML = window.StockAgentHistoricalQualityAuditRenderer.render(audit, ui.escapeHtml);
            element.removeAttribute('aria-busy');
        }

        async function load(values) {
            const nextFilterKey = auditFilterKey(values);
            if (nextFilterKey !== filterKey) itemOffset = 0;
            filterKey = nextFilterKey;
            currentValues = values ? { ...values } : null;
            const requestVersion = ++loadVersion;
            if (!values?.includeVersions) {
                itemOffset = 0;
                lastAudit = null;
                if (requestVersion === loadVersion) render(null);
                return;
            }
            const fetchAudit = apiClient?.fetchHistoricalReportQualityAudit;
            if (typeof fetchAudit !== 'function') {
                if (requestVersion === loadVersion) render({ status: 'unavailable' });
                return;
            }
            render({ status: 'loading' });
            try {
                const audit = await fetchAudit({ itemLimit, itemOffset, query: values.query, pipeline: values.pipelineFilter });
                if (requestVersion === loadVersion) { lastAudit = audit; render(audit); }
            } catch (_error) {
                if (requestVersion === loadVersion) render({ status: 'unavailable' });
            }
        }

        function bindEvents() {
            element?.addEventListener('click', event => {
                const pageButton = event.target.closest('[data-quality-audit-page]');
                if (pageButton?.dataset?.qualityAuditPage) {
                    const pageSize = Number(lastAudit?.items_limit) || itemLimit;
                    const currentOffset = Number(lastAudit?.items_offset);
                    const offset = Number.isFinite(currentOffset) && currentOffset >= 0 ? currentOffset : itemOffset;
                    itemOffset = pageButton.dataset.qualityAuditPage === 'next' ? offset + pageSize : Math.max(0, offset - pageSize);
                    return load(currentValues);
                }
                const reviewButton = event.target.closest('[data-quality-review-decision]');
                if (reviewButton?.dataset?.qualityReviewDecision) {
                    const saveReview = apiClient?.saveHistoricalReportQualityReview;
                    if (typeof saveReview !== 'function') return;
                    const decision = reviewButton.dataset.qualityReviewDecision;
                    const label = { approved_with_gap: '核准保留缺口', rejected: '退回處理', deferred: '暫緩' }[decision] || decision;
                    const note = typeof window.prompt === 'function'
                        ? window.prompt(`${label}：請留下核對理由`, '')
                        : '';
                    if (!String(note || '').trim()) return;
                    Promise.resolve(saveReview({
                        filename: reviewButton.dataset.qualityReviewFilename,
                        ticker: reviewButton.dataset.qualityReviewTicker,
                        pipeline_id: reviewButton.dataset.qualityReviewPipeline || 'v1',
                        report_quality_revision: reviewButton.dataset.qualityReviewRevision,
                        decision,
                        note: String(note).trim()
                    })).then(() => load(currentValues)).catch(error => notify.error(error?.message || '人工審核未儲存'));
                    return;
                }
                const pipelineButton = event.target.closest('[data-quality-audit-pipeline]');
                if (pipelineButton?.dataset?.qualityAuditPipeline && !pipelineButton?.dataset?.qualityAuditReport) {
                    onSelectPipeline(pipelineButton.dataset.qualityAuditPipeline || 'all');
                    return;
                }
                const button = event.target.closest('[data-quality-audit-report]');
                if (!button) return;
                openReport(button.dataset.qualityAuditReport, button.dataset.qualityAuditTicker, button.dataset.qualityAuditPipeline || 'v1');
            });
        }

        return { bindEvents, load, render };
    }

    window.StockAgentHistoricalQualityAudit = { create };
})();
