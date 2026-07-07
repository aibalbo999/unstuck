(function () {
    const jsonRequest = window.StockAgentApiClient.requestJson;

    async function fetchApiQuotas() { return jsonRequest('/api/observability/api-quotas'); }
    async function fetchPerformanceStats() { return jsonRequest('/api/performance/stats'); }
    async function fetchStockSnapshot(ticker) {
        return jsonRequest(`/api/stocks/${encodeURIComponent(String(ticker || '').trim())}/snapshot`);
    }

    async function compareReports(left, right) {
        const params = new URLSearchParams({ left, right });
        return jsonRequest(`/api/reports/compare?${params.toString()}`);
    }

    async function fetchWatchlist() { return jsonRequest('/api/watchlist'); }
    async function fetchDailyDecisionDashboard() { return jsonRequest('/api/watchlist/daily-dashboard'); }
    async function fetchSymbolSuggestions(q, limit = 10) { const params = new URLSearchParams({ q: q || '', limit: String(limit) }); return jsonRequest(`/api/watchlist/symbols?${params.toString()}`); }
    async function importWatchlistText(text) { return jsonRequest('/api/watchlist/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: text || '' }) }); }
    async function analyzePortfolioRisk(csv, thesisHealth = {}) { return jsonRequest('/api/watchlist/portfolio/risk', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ csv, thesis_health: thesisHealth || {} }) }); }

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

    async function fetchMarketScreener(params = {}) {
        const query = new URLSearchParams(Object.entries(params || {}).filter(([, value]) => value !== undefined && value !== null && value !== ''));
        const suffix = query.toString() ? `?${query.toString()}` : '';
        return jsonRequest(`/api/watchlist/screener${suffix}`);
    }
    async function runMarketScreener() {
        return jsonRequest('/api/watchlist/screener/run', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force: true })
        });
    }

    async function fetchDecisionTracking() { return jsonRequest('/api/decision-tracking'); }

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

    Object.assign(window.StockAgentApiClient, { fetchApiQuotas, fetchPerformanceStats, fetchStockSnapshot, compareReports, fetchWatchlist, fetchDailyDecisionDashboard, fetchSymbolSuggestions, importWatchlistText, analyzePortfolioRisk, saveWatchlistItem, deleteWatchlistItem, runWatchlist, fetchMarketScreener, runMarketScreener, fetchDecisionTracking, saveDecisionTrackingItem, deleteDecisionTrackingItem, refreshDecisionTracking });
})();
