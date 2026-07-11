(function () {
    const { dataTrustClass, dataTrustLabel, dataTrustReasonSummary, dataTrustScoreLabel, providerSlaOnlyPartial } = window.StockAgentUiDataTrust;
    const fallbackCatalog = window.StockAgentUiPipelineModeFallback || {};
    const PIPELINE_META = Object.fromEntries(
        (Array.isArray(fallbackCatalog.modes) ? fallbackCatalog.modes : []).map(mode => [mode.id, mode])
    );
    function pipelineMeta(pipelineId) {
        return PIPELINE_META[pipelineId] || PIPELINE_META.v1 || {};
    }
    function pipelineChoices(options = {}) {
        const ids = options.includeBoth ? ['v1', 'v2', 'v3', 'v4', 'both'] : ['v1', 'v2', 'v3', 'v4'];
        return ids.map(id => Object.assign({ value: id }, pipelineMeta(id)));
    }
    function pipelineModeClass(pipelineId) {
        if (pipelineId === 'both') return 'is-both';
        if (pipelineId === 'v4') return 'is-v4';
        if (pipelineId === 'v3') return 'is-v3';
        return pipelineId === 'v2' ? 'is-v2' : 'is-v1';
    }
    function pipelineModeLabel(pipelineId) { return pipelineMeta(pipelineId).displayLabel || pipelineMeta(pipelineId).label; }
    function pipelineCtaLabel(pipelineId) { return pipelineMeta(pipelineId).ctaLabel || `開始${pipelineMeta(pipelineId).codeLabel || '模式 A'}分析`; }
    function normalizeRecommendation(value) {
        const text = String(value || 'N/A');
        const lower = text.toLowerCase();
        if (text.includes('強烈放空') || text.includes('放空') || text.includes('做空') || text.includes('空方') || ['short', 'strong short'].includes(lower)) return '放空';
        if (text.includes('買入') || text.includes('買進') || text.includes('強烈買入') || text.includes('加碼') || text.includes('增持') || ['buy', 'strong buy'].includes(lower)) return '買入';
        if (text.includes('避免') || text.includes('賣出') || text.includes('減碼') || text.includes('避險觀察') || ['avoid', 'sell', 'reduce'].includes(lower)) return '避免';
        if (text.includes('持有') || text.includes('觀望') || text.includes('中立') || text.includes('中性') || text.includes('偏多觀察') || ['hold', 'neutral'].includes(lower)) return '持有';
        return text;
    }
    function recommendationTone(value) {
        const text = normalizeRecommendation(value);
        if (text === '買入') return 'is-buy';
        if (text === '放空') return 'is-short';
        if (text === '避免') return 'is-avoid';
        return 'is-hold';
    }
    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (char) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[char]));
    }
    function renderPipelineModeBadge(pipelineId) {
        return `<span class="history-mode ${pipelineModeClass(pipelineId)}">${escapeHtml(pipelineModeLabel(pipelineId))}</span>`;
    }
    function renderDataTrustBadge(trust) {
        const label = dataTrustLabel(trust);
        const score = dataTrustScoreLabel(trust);
        const text = score ? `${label} · ${score}` : label;
        return `<span class="data-trust-badge is-${dataTrustClass(trust)}" title="${escapeHtml(text)}">${escapeHtml(text)}</span>`;
    }
    function renderDataTrustReason(trust) {
        const summary = dataTrustReasonSummary(trust);
        return summary ? `<span class="data-trust-reason">${escapeHtml(summary)}</span>` : '';
    }

    window.StockAgentUi = {
        PIPELINE_META,
        pipelineMeta,
        pipelineChoices,
        pipelineModeClass,
        pipelineModeLabel,
        pipelineCtaLabel,
        dataTrustLabel,
        dataTrustClass,
        dataTrustReasonSummary,
        dataTrustScoreLabel,
        normalizeRecommendation,
        recommendationTone,
        escapeHtml,
        providerSlaOnlyPartial,
        renderPipelineModeBadge,
        renderDataTrustBadge,
        renderDataTrustReason
    };
})();
