(function () {
    const inFlight = new Map();
    const { buttonForScope, setButtonLabel, disableButtons, configureCancelButton, setStatus } = window.StockAgentReportRerunControls;

    function rerunPreviewReport(options) {
        const filename = options.previewReport?.filename;
        if (!filename) return Promise.resolve();
        if (inFlight.has(filename)) return inFlight.get(filename);
        const pending = Promise.resolve().then(() => runPreviewReport(options));
        inFlight.set(filename, pending);
        pending.then(() => inFlight.delete(filename), () => inFlight.delete(filename));
        return pending;
    }

    async function runPreviewReport(options) {
        const previewReport = options.previewReport;
        if (!previewReport) return;

        const apiClient = options.apiClient || window.StockAgentApiClient;
        const notify = options.notify || { success: () => {}, error: () => {} };
        const refreshProviderSlaIfLoaded = options.refreshProviderSlaIfLoaded || (() => Promise.resolve());
        const scope = options.scope || 'final_recommendation';
        const buttons = options.buttons || {};
        const button = buttonForScope(scope, buttons);
        const originalText = button ? (button.querySelector('span')?.textContent || '局部重跑') : '局部重跑';
        disableButtons(buttons, true);
        configureCancelButton(buttons.cancel, false);
        setButtonLabel(button, '排入重跑');
        setStatus(options.statusEl, '正在建立報告重跑任務...');

        try {
            const filename = previewReport.filename;
            const payload = await apiClient.requestJson(
                `/api/report/${encodeURIComponent(filename)}/rerun?scope=${encodeURIComponent(scope)}`,
                { method: 'POST', headers: { 'X-Stock-Agent-Action-Source': 'report_preview' } }
            );

            setButtonLabel(button, '重跑中');
            if (payload.job_id) {
                configureCancelButton(buttons.cancel, true, async () => {
                    if (!buttons.cancel || buttons.cancel.disabled) return;
                    buttons.cancel.disabled = true;
                    setStatus(options.statusEl, '已送出取消要求，正在等待目前步驟收尾...');
                    try {
                        const cancelUrl = `/api/report/${encodeURIComponent(filename)}/rerun/cancel?job_id=${encodeURIComponent(payload.job_id)}`;
                        await apiClient.requestJson(cancelUrl, { method: 'POST' });
                    } catch (err) {
                        buttons.cancel.disabled = false;
                        setStatus(options.statusEl, `取消重跑失敗：${err.message || err}`);
                    }
                });
            }
            const donePayload = payload.queued && payload.stream_url
                ? await window.StockAgentReportRerunStream.open({
                    streamUrl: payload.stream_url,
                    onStatus: message => setStatus(options.statusEl, message)
                })
                : payload;

            await options.loadHistory();
            await refreshProviderSlaIfLoaded();
            if (donePayload.filename) {
                options.openReport(
                    donePayload.filename,
                    previewReport.ticker,
                    donePayload.pipeline_id || previewReport.pipeline_id || 'v1'
                );
            }
            setStatus(options.statusEl, '');
            notify.success(`${payload.scope_label || donePayload.scope_label || '局部重跑'}完成：${donePayload.filename || '已產生新報告'}`);
        } catch (err) {
            console.error('Failed to rerun report', err);
            setStatus(options.statusEl, `局部重跑失敗：${err.message || err}`);
            notify.error(`局部重跑失敗：${err.message || err}`);
        } finally {
            disableButtons(buttons, false);
            configureCancelButton(buttons.cancel, false);
            setButtonLabel(button, originalText);
        }
    }

    window.StockAgentReportRerun = {
        rerunPreviewReport
    };
})();
