(function () {
    async function jsonRequest(url, options) {
        const res = await fetch(url, options);
        const payload = await res.json();
        if (!res.ok || payload.success === false) {
            throw new Error(payload.error || payload.detail || `HTTP ${res.status}`);
        }
        return payload;
    }

    async function fetchApiQuotas() {
        return jsonRequest('/api/observability/api-quotas');
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

    Object.assign(window.StockAgentApiClient, {
        fetchApiQuotas,
        compareReports,
        fetchWatchlist,
        saveWatchlistItem,
        deleteWatchlistItem,
        runWatchlist
    });
})();
