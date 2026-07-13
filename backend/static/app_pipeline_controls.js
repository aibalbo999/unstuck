(function () {
    function create(options) {
        const {
            ui,
            pipelineInputs,
            analyzeBtnText,
            pipelineModeHint,
            historyPipelineFilter
        } = options;
        const doc = options.doc || document;

        function getSelectedPipeline() {
            const selected = doc.querySelector('input[name="pipeline-mode"]:checked') || pipelineInputs.find(input => input.checked);
            return selected ? selected.value : 'v1';
        }

        function syncPipelineOptionLabels() {
            const choices = typeof ui.pipelineChoices === 'function' ? ui.pipelineChoices({ includeBoth: true }) : [];
            choices.forEach(choice => {
                const selector = `input[name="pipeline-mode"][value="${choice.value}"]`;
                const input = doc.querySelector(selector);
                const label = input ? input.closest('.pipeline-option') : null;
                if (label) {
                    const title = label.querySelector('strong');
                    const subtitle = label.querySelector('small');
                    if (title) title.textContent = choice.codeLabel || choice.label || choice.value;
                    if (subtitle) subtitle.textContent = choice.optionLabel || choice.shortLabel || choice.intent || '';
                }
                const historyOption = historyPipelineFilter?.querySelector(`option[value="${choice.value}"]`);
                if (historyOption) historyOption.textContent = ui.pipelineModeLabel(choice.value);
                const watchlistOption = doc.querySelector(`#watchlist-pipeline-select option[value="${choice.value}"]`);
                if (watchlistOption) watchlistOption.textContent = ui.pipelineModeLabel(choice.value);
            });
        }

        function updateAnalyzeButtonCopy() {
            if (!analyzeBtnText) return;
            analyzeBtnText.textContent = ui.pipelineCtaLabel(getSelectedPipeline());
        }

        function updatePipelineModeHint() {
            if (!pipelineModeHint) return;
            pipelineModeHint.textContent = ui.pipelineMeta(getSelectedPipeline()).intent || '';
        }

        function selectPipelineMode(pipelineId) {
            const input = pipelineInputs.find(item => item.value === pipelineId);
            if (!input) return;
            pipelineInputs.forEach(item => { item.checked = item === input; });
            updateAnalyzeButtonCopy();
            updatePipelineModeHint();
        }

        return { getSelectedPipeline, syncPipelineOptionLabels, updateAnalyzeButtonCopy, updatePipelineModeHint, selectPipelineMode };
    }

    window.StockAgentAppPipelineControls = { create };
})();
