(function () {
    function create(options) {
        const { searchEl, pipelineEl, recommendationEl, dataTrustEl, includeVersionsEl } = options, debounceMs = options.debounceMs || 200;
        const storageKey = 'stock-agent.history.filters.v1';
        const allowed = { pipelineFilter: ['all', 'v1', 'v2', 'v3', 'v4'], recommendationFilter: ['all', '買入', '持有', '避免', '放空'], dataTrustFilter: ['all', 'fresh', 'partial', 'stale', 'error', 'unknown'] };
        let searchTimer = null;

        function readPersistedValues() { try { const raw = window.sessionStorage?.getItem(storageKey), parsed = raw ? JSON.parse(raw) : {}; return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}; } catch (_error) { return {}; } }
        function normalizedOption(value, key) {
            const normalized = String(value || '').trim();
            return allowed[key]?.includes(normalized) ? normalized : 'all';
        }
        function values() { return { query: String(searchEl?.value ?? '').trim(), pipelineFilter: normalizedOption(pipelineEl?.value, 'pipelineFilter'), recommendationFilter: normalizedOption(recommendationEl?.value, 'recommendationFilter'), dataTrustFilter: normalizedOption(dataTrustEl?.value, 'dataTrustFilter'), includeVersions: Boolean(includeVersionsEl?.checked) }; }
        function persistValues() { try { window.sessionStorage?.setItem(storageKey, JSON.stringify(values())); } catch (_error) { } }
        function setValues(next = {}) {
            if (searchEl && next.query !== undefined) searchEl.value = String(next.query ?? '');
            if (pipelineEl && next.pipelineFilter !== undefined) pipelineEl.value = normalizedOption(next.pipelineFilter, 'pipelineFilter');
            if (recommendationEl && next.recommendationFilter !== undefined) recommendationEl.value = normalizedOption(next.recommendationFilter, 'recommendationFilter');
            if (dataTrustEl && next.dataTrustFilter !== undefined) dataTrustEl.value = normalizedOption(next.dataTrustFilter, 'dataTrustFilter');
            if (includeVersionsEl && next.includeVersions !== undefined) includeVersionsEl.checked = next.includeVersions === true;
            persistValues();
        }

        function bind(handlers) {
            const onSearch = handlers.onSearch || function () {};
            const onFilter = handlers.onFilter || function () {};
            searchEl?.addEventListener('input', () => { persistValues(); clearTimeout(searchTimer); searchTimer = setTimeout(onSearch, debounceMs); });
            [pipelineEl, recommendationEl, dataTrustEl, includeVersionsEl].forEach(filter => filter?.addEventListener('change', () => { persistValues(); onFilter(); }));
        }

        setValues(readPersistedValues());
        return { values, bind, setValues };
    }

    window.StockAgentHistoryFilters = { create };
})();
