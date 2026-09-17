(function () {
    function reportAutomaticRerunAction(report, helpers = {}) {
        const filename = report?.filename;
        const requested = [report?.analysis_text_stale, report?.decision_freshness?.requires_rerun, report?.requires_rerun]
            .some(value => value === true || value === 1 || (typeof value === 'string' && ['true', '1'].includes(value.trim().toLowerCase())));
        const snapshot = report?.snapshot_integrity || {};
        if (!filename || !requested || !helpers.hasSourceError || !helpers.dataTrustStatus
            || helpers.dataTrustStatus(report) === 'error' || helpers.hasSourceError(report)
            || String(snapshot.status ?? '').trim().toLowerCase() === 'invalid' || snapshot.valid === false) return null;
        // Re-analyzing stale content does not approve the old report or bypass publication gates.
        return { type: 'rerun_full_report', filename };
    }

    window.StockAgentReportAutomaticRerunPolicy = { reportAutomaticRerunAction };
})();
