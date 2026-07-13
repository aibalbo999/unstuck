(function () {
    function create(options) {
        const apiClient = options.apiClient;
        const elements = options.elements || {};
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        const pipelineModeLabel = options.pipelineModeLabel
            || window.StockAgentUi?.pipelineModeLabel
            || ((pipelineId) => String(pipelineId || 'v1'));
        const renderers = window.StockAgentReportCompareRenderers.create({ escapeHtml, pipelineModeLabel });
        let selected = [];

        function renderSelection() {
            if (elements.summaryEl) elements.summaryEl.textContent = renderers.selectionSummary(selected);
        }

        function renderResult(payload) {
            if (!elements.resultEl) return;
            elements.resultEl.hidden = false;
            elements.resultEl.innerHTML = renderers.resultHtml(payload);
        }

        async function compare() {
            if (selected.length < 2) return;
            try {
                if (elements.addBtn) elements.addBtn.disabled = true;
                if (elements.resultEl) {
                    elements.resultEl.hidden = false;
                    elements.resultEl.innerHTML = '<span class="provider-sla-chip is-warning">比較中</span>';
                }
                renderResult(await apiClient.compareReports(selected[0].filename, selected[1].filename));
            } catch (err) {
                console.error('Failed to compare reports', err);
                if (elements.resultEl) {
                    elements.resultEl.hidden = false;
                    elements.resultEl.innerHTML = `<span class="provider-sla-chip is-critical">比較失敗：${escapeHtml(err.message || err)}</span>`;
                }
            } finally {
                if (elements.addBtn) elements.addBtn.disabled = false;
            }
        }

        function addReport(report) {
            if (!report || !report.filename) return;
            selected = selected.filter(item => item.filename !== report.filename);
            selected.push(report);
            if (selected.length > 2) selected = selected.slice(-2);
            renderSelection();
            if (selected.length === 2) compare();
        }

        function clear() {
            selected = [];
            renderSelection();
            if (elements.resultEl) {
                elements.resultEl.hidden = true;
                elements.resultEl.innerHTML = '';
            }
        }

        function bindEvents(getReport) {
            if (elements.addBtn) elements.addBtn.addEventListener('click', () => addReport(getReport ? getReport() : null));
            if (elements.clearBtn) elements.clearBtn.addEventListener('click', clear);
        }

        renderSelection();
        return { addReport, bindEvents, clear };
    }

    window.StockAgentReportComparePanel = { create };
})();
