(function () {
    function create(options) {
        const apiClient = options.apiClient;
        const ui = options.ui;
        const element = options.element;
        const openReport = options.openReport || (() => {});
        const onSelectPipeline = options.onSelectPipeline || (() => {});
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
