(function () {
    const ui = window.StockAgentUi;
    if (!ui) return;

    function applyPipelineModeCatalog(payload) {
        if (payload?.schema_version !== 'pipeline_modes.v1' || !Array.isArray(payload.modes)) return false;
        let applied = false;
        payload.modes.forEach(mode => {
            if (!mode?.id || !ui.PIPELINE_META[mode.id]) return;
            ui.PIPELINE_META[mode.id] = Object.assign({}, ui.PIPELINE_META[mode.id], mode);
            applied = true;
        });
        return applied;
    }

    async function loadPipelineMeta(fetchImpl = window.fetch) {
        if (typeof fetchImpl !== 'function') return false;
        try {
            const response = await fetchImpl('/api/pipeline-modes', { headers: { Accept: 'application/json' } });
            if (!response?.ok) return false;
            return applyPipelineModeCatalog(await response.json());
        } catch (_error) {
            return false;
        }
    }

    ui.applyPipelineModeCatalog = applyPipelineModeCatalog;
    ui.loadPipelineMeta = loadPipelineMeta;
})();
