(function () {
    function create(options) {
        const {
            apiClient,
            notify,
            elements,
            decisionTrackingPanel,
            getPreviewReport,
            setPreviewReport,
            getReport,
            setReport,
            showReportPreview,
            hideReportPreview,
            loadHistory,
            refreshProviderSlaIfLoaded,
            openReport
        } = options;

        async function refreshPreviewDataSnapshot() {
            const previewReport = getPreviewReport();
            const button = elements.previewRefreshDataBtn;
            if (!previewReport || !button) return;
            const filename = previewReport.filename;
            const label = button.querySelector('span');
            const originalText = label ? label.textContent : '刷新資料快照';
            button.disabled = true;
            if (label) label.textContent = '刷新中';
            try {
                const payload = await apiClient.refreshReportDataSnapshot(filename);
                const updated = {
                    ...previewReport,
                    data_trust: payload.data_trust || previewReport.data_trust,
                    data_snapshot_filename: payload.data_filename || previewReport.data_snapshot_filename,
                    analysis_text_stale: payload.analysis_text_stale ?? previewReport.analysis_text_stale,
                    analysis_text_stale_message: payload.analysis_text_stale_message ?? previewReport.analysis_text_stale_message,
                    decision_freshness: payload.decision_freshness ?? previewReport.decision_freshness
                };
                setReport(filename, updated);
                setPreviewReport(updated);
                showReportPreview(filename);
                await loadHistory();
                await refreshProviderSlaIfLoaded();
                const summary = payload.refresh_diff && Array.isArray(payload.refresh_diff.summary)
                    ? payload.refresh_diff.summary.slice(0, 3).join('；')
                    : '資料快照已刷新';
                notify.success(`資料快照已刷新：${summary}`);
            } catch (err) {
                console.error('Failed to refresh data snapshot', err);
                notify.error(`刷新資料快照失敗：${err.message || err}`);
            } finally {
                button.disabled = false;
                if (label) label.textContent = originalText;
            }
        }

        async function rerunPreviewReport(scope) {
            return window.StockAgentReportRerun.rerunPreviewReport({
                apiClient,
                scope,
                previewReport: getPreviewReport(),
                buttons: {
                    final: elements.previewRerunFinalBtn,
                    full: elements.previewRerunFullBtn,
                    modeB: elements.previewRerunModeBBtn,
                    cancel: elements.previewRerunCancelBtn
                },
                statusEl: elements.previewStaleNotice,
                loadHistory,
                notify,
                refreshProviderSlaIfLoaded,
                openReport
            });
        }

        async function deleteReport(filename, event) {
            event.stopPropagation();
            const confirmed = await notify.confirm ('確定要刪除這份報告嗎？', {
                title: '刪除報告',
                confirmLabel: '刪除'
            });
            if (!confirmed) return;
            try {
                const result = await apiClient.deleteReport(filename);
                const previewReport = getPreviewReport();
                if (result.success) {
                    if (previewReport && previewReport.filename === filename) hideReportPreview();
                    loadHistory();
                } else {
                    notify.error('刪除失敗：' + result.error);
                }
            } catch (err) {
                console.error(err);
                notify.error('刪除失敗');
            }
        }

        async function toggleDecisionTracking(filename, event) {
            event.stopPropagation();
            const report = getReport(filename);
            if (report) { await decisionTrackingPanel.toggleDecisionTracking(report); await loadHistory(); }
        }

        return { refreshPreviewDataSnapshot, rerunPreviewReport, deleteReport, toggleDecisionTracking };
    }

    window.StockAgentHistoryWorkspaceActions = { create };
})();
