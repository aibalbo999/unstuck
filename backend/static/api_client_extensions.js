(function () {
    const jsonRequest = window.StockAgentApiClient.requestJson;

    async function fetchApiQuotas() {
        return jsonRequest('/api/observability/api-quotas');
    }

    async function fetchPerformanceStats() {
        return jsonRequest('/api/performance/stats');
    }

    async function compareReports(left, right) {
        const params = new URLSearchParams({ left, right });
        return jsonRequest(`/api/reports/compare?${params.toString()}`);
    }

    async function fetchWatchlist() {
        return jsonRequest('/api/watchlist');
    }

    async function saveWatchlistItem(item) {
        return jsonRequest('/api/watchlist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(item || {})
        });
    }

    async function deleteWatchlistItem(ticker, pipeline = 'all') {
        const params = new URLSearchParams({ pipeline });
        return jsonRequest(`/api/watchlist/${encodeURIComponent(ticker)}?${params.toString()}`, { method: 'DELETE' });
    }

    async function runWatchlist(items) {
        return jsonRequest('/api/watchlist/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(Array.isArray(items) ? { items } : {})
        });
    }

    async function fetchDecisionTracking() {
        return jsonRequest('/api/decision-tracking');
    }

    async function saveDecisionTrackingItem(item) {
        return jsonRequest('/api/decision-tracking', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(item || {})
        });
    }

    async function deleteDecisionTrackingItem(ticker) {
        return jsonRequest(`/api/decision-tracking/${encodeURIComponent(ticker)}`, { method: 'DELETE' });
    }

    async function refreshDecisionTracking(tickers) {
        return jsonRequest('/api/decision-tracking/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(Array.isArray(tickers) ? { tickers } : {})
        });
    }

    Object.assign(window.StockAgentApiClient, {
        fetchApiQuotas,
        fetchPerformanceStats,
        compareReports,
        fetchWatchlist,
        saveWatchlistItem,
        deleteWatchlistItem,
        runWatchlist,
        fetchDecisionTracking,
        saveDecisionTrackingItem,
        deleteDecisionTrackingItem,
        refreshDecisionTracking
    });
})();
