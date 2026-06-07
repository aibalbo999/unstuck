(function () {
    async function jsonRequest(url, options) {
        const res = await fetch(url, options);
        const payload = await res.json();
        if (!res.ok || payload.success === false) {
            throw new Error(payload.error || `HTTP ${res.status}`);
        }
        return payload;
    }

    async function fetchProviderSla({ windowValue = 'all', limit = 12 } = {}) {
        const params = new URLSearchParams({ limit: String(limit) });
        if (windowValue) params.set('window', windowValue);
        return jsonRequest(`/api/observability/provider-sla?${params.toString()}`);
    }

    async function fetchReports({ page, limit, query, pipeline, recommendation, dataTrust }) {
        const params = new URLSearchParams({
            page: String(page),
            limit: String(limit)
        });
        if (query) params.set('q', query);
        if (pipeline && pipeline !== 'all') params.set('pipeline', pipeline);
        if (recommendation && recommendation !== 'all') params.set('recommendation', recommendation);
        if (dataTrust && dataTrust !== 'all') params.set('data_trust', dataTrust);
        return jsonRequest(`/api/reports?${params.toString()}`);
    }

    async function refreshReportDataSnapshot(filename) {
        return jsonRequest(`/api/report/${encodeURIComponent(filename)}/refresh/data`, { method: 'POST' });
    }

    async function deleteReport(filename) {
        return jsonRequest(`/api/reports/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    }

    window.StockAgentApiClient = {
        fetchProviderSla,
        fetchReports,
        refreshReportDataSnapshot,
        deleteReport
    };
})();
