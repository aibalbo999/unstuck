(function () {
    function setButtonText(button, text) {
        const label = button ? button.querySelector('span') : null;
        if (label) label.textContent = text;
    }

    function configureRerunButtons(elements, pipelineId) {
        const isModeB = pipelineId === 'v2';
        setButtonText(elements.rerunFinalBtn, isModeB ? '重跑模式 B 最終建議' : '重跑模式 A 最終建議');
        setButtonText(elements.rerunModeBBtn, isModeB ? '重跑完整模式 B' : '產生模式 B 報告');
    }

    function create(options) {
        const elements = options.elements || {};

        function show(report) {
            if (!report || !elements.root) return false;
            const rec = report.recommendation || {};
            const pipelineId = report.pipeline_id || 'v1';

            elements.mode.innerHTML = `${options.renderPipelineModeBadge(pipelineId)}${options.renderDataTrustBadge(report.data_trust)}<span class="preview-date">${options.escapeHtml(report.date || '')}</span>`;
            configureRerunButtons(elements, pipelineId);
            elements.title.textContent = `${report.ticker} 投資建議`;
            elements.price.textContent = rec.current_price || 'N/A';
            elements.recommendation.textContent = options.normalizeRecommendation(rec.recommendation);
            elements.recommendation.className = options.recommendationTone(rec.recommendation);
            elements.confidence.textContent = rec.confidence || 'N/A';
            elements.target3m.textContent = rec.target_3m || 'N/A';
            elements.target6m.textContent = rec.target_6m || 'N/A';
            elements.target12m.textContent = rec.target_12m || 'N/A';
            elements.summary.textContent = rec.summary || '這份報告沒有可讀的一頁式摘要，可直接查看完整報告。';

            if (elements.staleNotice) {
                const staleMessage = report.analysis_text_stale_message
                    || '資料快照已刷新，但這份 HTML/Markdown 分析本文尚未重新執行。';
                elements.staleNotice.textContent = staleMessage;
                elements.staleNotice.hidden = !report.analysis_text_stale;
            }

            elements.root.hidden = false;
            return true;
        }

        function hide() {
            if (elements.root) elements.root.hidden = true;
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
