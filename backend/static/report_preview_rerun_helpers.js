(function () {
    function setButtonText(button, text) {
        const label = button ? button.querySelector('span') : null;
        if (label) label.textContent = text;
    }

    function configureRerunButtons(elements, pipelineId, pipelineMeta) {
        const meta = typeof pipelineMeta === 'function' ? pipelineMeta(pipelineId) : null;
        const shortLabel = meta?.shortLabel || pipelineId.toUpperCase();
        const isModeB = pipelineId === 'v2';
        setButtonText(elements.rerunFinalBtn, `重跑${shortLabel}報告結論`);
        setButtonText(elements.rerunFullBtn, `完整重跑${shortLabel}`);
        if (elements.rerunModeBBtn) {
            elements.rerunModeBBtn.hidden = isModeB;
            if (!isModeB) setButtonText(elements.rerunModeBBtn, '產生模式 B 報告');
        }
    }

    window.StockAgentReportPreviewRerunHelpers = { configureRerunButtons, setButtonText };
})();
