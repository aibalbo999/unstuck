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

        return { values, bind };
    }

    window.StockAgentHistoryFilters = { create };
})();
