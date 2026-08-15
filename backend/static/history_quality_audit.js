(function () {
    function create(options) {
        const apiClient = options.apiClient;
        const ui = options.ui;
        const element = options.element;
        const openReport = options.openReport || (() => {});
        let loadVersion = 0;

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
            element.innerHTML = window.StockAgentHistoryPanelQualityHelpers.renderHistoricalQualityAudit(audit, ui.escapeHtml);
            element.removeAttribute('aria-busy');
        }

        async function load(values) {
            const requestVersion = ++loadVersion;
            if (!values?.includeVersions) {
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
                const audit = await fetchAudit({ itemLimit: 5, query: values.query, pipeline: values.pipelineFilter });
                if (requestVersion === loadVersion) render(audit);
            } catch (_error) {
                if (requestVersion === loadVersion) render({ status: 'unavailable' });
            }
        }

        function bindEvents() {
            element?.addEventListener('click', event => {
                const button = event.target.closest('[data-quality-audit-report]');
                if (!button) return;
                openReport(button.dataset.qualityAuditReport, button.dataset.qualityAuditTicker, button.dataset.qualityAuditPipeline || 'v1');
            });
        }

        return { bindEvents, load, render };
    }

    window.StockAgentHistoricalQualityAudit = { create };
})();
