(function () {
    async function jsonRequest(url, options) {
        const res = await fetch(url, options);
        const payload = await res.json();
        if (!res.ok || payload.success === false) {
            throw new Error(payload.error || payload.detail || `HTTP ${res.status}`);
        }
        return payload;
    }

    async function fetchProviderSla({ windowValue = 'all', limit = 12 } = {}) {
        const params = new URLSearchParams({ limit: String(limit) });
        if (windowValue) params.set('window', windowValue);
        return jsonRequest(`/api/observability/provider-sla?${params.toString()}`);
    }

    async function fetchActiveJobs({ limit = 5, eventLimit = 40 } = {}) {
        const params = new URLSearchParams({ limit: String(limit), event_limit: String(eventLimit) });
        return jsonRequest(`/api/observability/active-jobs?${params.toString()}`);
    }

    async function fetchMaintenanceSummary() {
        return jsonRequest('/api/maintenance/storage-summary');
    }

    async function cleanupReportIndex() {
        return jsonRequest('/api/maintenance/cleanup-report-index?write=true', { method: 'POST' });
    }

    async function cleanupAnalysisHistory({ retentionDays = 30, keepRecentJobs = 20 } = {}) {
        const params = new URLSearchParams({
            write: 'true',
            retention_days: String(retentionDays),
            keep_recent_jobs: String(keepRecentJobs)
        });
        return jsonRequest(`/api/maintenance/cleanup-analysis-history?${params.toString()}`, { method: 'POST' });
    }

    async function cleanupProviderSla({ retentionDays = 90 } = {}) {
        const params = new URLSearchParams({ retention_days: String(retentionDays) });
        return jsonRequest(`/api/maintenance/cleanup-provider-sla?${params.toString()}`, { method: 'POST' });
    }

    async function fetchReports({ page, limit, query, pipeline, recommendation, dataTrust, includeVersions }) {
        const params = new URLSearchParams({
            page: String(page),
            limit: String(limit)
        });
        if (query) params.set('q', query);
        if (pipeline && pipeline !== 'all') params.set('pipeline', pipeline);
        if (recommendation && recommendation !== 'all') params.set('recommendation', recommendation);
        if (dataTrust && dataTrust !== 'all') params.set('data_trust', dataTrust);
        if (includeVersions) params.set('include_versions', '1');
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
        fetchActiveJobs,
        fetchMaintenanceSummary,
        cleanupReportIndex,
        cleanupAnalysisHistory,
        cleanupProviderSla,
        fetchReports,
        refreshReportDataSnapshot,
        deleteReport
    };
})();
