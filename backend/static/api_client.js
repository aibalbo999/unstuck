(function () {
    const requestJson = window.StockAgentApiRequest.requestJson;

    async function fetchProviderSla({ windowValue = 'all', limit = 12 } = {}) {
        const params = new URLSearchParams({ limit: String(limit) });
        if (windowValue) params.set('window', windowValue);
        return requestJson(`/api/observability/provider-sla?${params.toString()}`);
    }
    async function fetchActiveJobs({ limit = 5, eventLimit = 40 } = {}) {
        const params = new URLSearchParams({ limit: String(limit), event_limit: String(eventLimit) });
        return requestJson(`/api/observability/active-jobs?${params.toString()}`);
    }
    async function fetchMaintenanceSummary() {
        return requestJson('/api/maintenance/storage-summary', { mutation: true });
    }
    async function fetchOpsDashboard() {
        return requestJson('/api/observability/dashboard');
    }
    async function cleanupReportIndex() {
        return requestJson('/api/maintenance/cleanup-report-index?write=true', { method: 'POST' });
    }
    async function cleanupAnalysisHistory({ retentionDays = 30, keepRecentJobs = 20 } = {}) {
        const params = new URLSearchParams({
            write: 'true',
            retention_days: String(retentionDays),
            keep_recent_jobs: String(keepRecentJobs)
        });
        return requestJson(`/api/maintenance/cleanup-analysis-history?${params.toString()}`, { method: 'POST' });
    }
    async function cleanupProviderSla({ retentionDays = 90 } = {}) {
        const params = new URLSearchParams({ write: 'true', retention_days: String(retentionDays) });
        return requestJson(`/api/maintenance/cleanup-provider-sla?${params.toString()}`, { method: 'POST' });
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
        return requestJson(`/api/reports?${params.toString()}`);
    }
    async function refreshReportDataSnapshot(filename) {
        return requestJson(`/api/report/${encodeURIComponent(filename)}/refresh/data`, { method: 'POST' });
    }
    async function deleteReport(filename) {
        return requestJson(`/api/reports/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    }
    window.StockAgentApiClient = {
        requestJson,
        fetchProviderSla,
        fetchActiveJobs,
        fetchMaintenanceSummary,
        fetchOpsDashboard,
        cleanupReportIndex,
        cleanupAnalysisHistory,
        cleanupProviderSla,
        fetchReports,
        refreshReportDataSnapshot,
        deleteReport
    };
})();
