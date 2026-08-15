(function () {
    function create(options) {
        const searchEl = options.searchEl;
        const pipelineEl = options.pipelineEl;
        const recommendationEl = options.recommendationEl;
        const dataTrustEl = options.dataTrustEl;
        const includeVersionsEl = options.includeVersionsEl;
        const debounceMs = options.debounceMs || 200;
        let searchTimer = null;

        function values() {
            return {
                query: searchEl ? searchEl.value.trim() : '',
                pipelineFilter: pipelineEl ? pipelineEl.value : 'all',
                recommendationFilter: recommendationEl ? recommendationEl.value : 'all',
                dataTrustFilter: dataTrustEl ? dataTrustEl.value : 'all',
                includeVersions: includeVersionsEl ? includeVersionsEl.checked : false
            };
        }
        function setValues(next = {}) {
            if (searchEl && next.query !== undefined) searchEl.value = String(next.query ?? '');
            if (pipelineEl && next.pipelineFilter !== undefined) pipelineEl.value = String(next.pipelineFilter || 'all');
            if (recommendationEl && next.recommendationFilter !== undefined) recommendationEl.value = String(next.recommendationFilter || 'all');
            if (dataTrustEl && next.dataTrustFilter !== undefined) dataTrustEl.value = String(next.dataTrustFilter || 'all');
            if (includeVersionsEl && next.includeVersions !== undefined) includeVersionsEl.checked = Boolean(next.includeVersions);
        }

        function bind(handlers) {
            const onSearch = handlers.onSearch || function () {};
            const onFilter = handlers.onFilter || function () {};

            if (searchEl) {
                searchEl.addEventListener('input', () => {
                    clearTimeout(searchTimer);
                    searchTimer = setTimeout(onSearch, debounceMs);
                });
            }

            [pipelineEl, recommendationEl, dataTrustEl, includeVersionsEl].forEach(filter => {
                if (!filter) return;
                filter.addEventListener('change', onFilter);
            });
        }

        return { values, bind, setValues };
    }

    window.StockAgentHistoryFilters = { create };
})();
