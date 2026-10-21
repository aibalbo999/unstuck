(function () {
    function create({ pipelineEl, recommendationEl }) {
        const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
        function groups() {
            const selected = pipelineEl?.value || 'all';
            const modes = window.StockAgentUi?.PIPELINE_META || Object.fromEntries((window.StockAgentUiPipelineModeFallback?.modes || []).map(mode => [mode.id, mode]));
            return ['v1', 'v2', 'v3', 'v4'].filter(id => selected === 'all' || selected === id)
                .map(id => ({code: modes[id]?.codeLabel || id, label: modes[id]?.historyFilter?.label, options: modes[id]?.historyFilter?.options || []}));
        }
        function value(raw) {
            const text = String(raw || '').trim();
            return groups().some(group => group.options.some(option => option.value === text)) ? text : 'all';
        }
        function render() {
            if (!recommendationEl) return;
            const choices = groups(), selected = value(recommendationEl.value);
            const label = recommendationEl.closest?.('.history-filter-field')?.querySelector?.('span');
            if (label) label.textContent = choices.length === 1 ? choices[0].label || '報告判斷' : '報告判斷';
            recommendationEl.innerHTML = '<option value="all">全部報告判斷</option>' + choices.map(group =>
                `<optgroup label="${escape(group.code + ' · ' + (group.label || '報告判斷'))}">${group.options.map(option => `<option value="${escape(option.value)}">${escape(option.label)}</option>`).join('')}</optgroup>`).join('');
            recommendationEl.value = selected;
        }
        return { value, render };
    }
    window.StockAgentHistoryDecisionFilters = { create };
})();
