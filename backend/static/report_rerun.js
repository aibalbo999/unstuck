(function () {
    function buttonForScope(scope, buttons) {
        if (scope === 'mode_b') return buttons.modeB;
        if (scope === 'full_report') return buttons.full;
        return buttons.final;
    }

    function setButtonLabel(button, text) {
        const label = button ? button.querySelector('span') : null;
        if (label) label.textContent = text;
    }

    function disableButtons(buttons, disabled) {
        [buttons.final, buttons.full, buttons.modeB].forEach(button => {
            if (!button) return;
            button.disabled = disabled;
        });
    }

    function configureCancelButton(button, visible, handler) {
        if (!button) return;
        button.hidden = !visible;
        button.disabled = false;
        button.onclick = handler || null;
    }

    function setStatus(statusEl, message) {
        if (!statusEl) return;
        statusEl.textContent = message || '';
        statusEl.hidden = !message;
    }

    function openRerunStream(options) {
        return new Promise((resolve, reject) => {
            const eventSource = new EventSource(options.streamUrl);
            eventSource.onmessage = (event) => {
                let payload = {};
                try {
                    payload = JSON.parse(event.data);
                } catch (err) {
                    return;
                }

                if (payload.type === 'status') {
                    options.onStatus(payload.message || '報告重跑中...');
                    return;
                }
                if (payload.type === 'progress') {
                    const name = payload.name ? `：${payload.name}` : '';
                    options.onStatus(`報告重跑中${name}`);
                    return;
                }
                if (payload.type === 'report_done') {
                    options.onStatus('新報告已產生，正在整理列表...');
                    return;
                }
                if (payload.type === 'done') {
                    eventSource.close();
                    resolve(payload);
                    return;
                }
                if (payload.type === 'error') {
                    eventSource.close();
                    reject(new Error(payload.message || '報告重跑失敗'));
                }
            };
            eventSource.onerror = () => {
                options.onStatus('重跑連線暫時中斷，瀏覽器正在自動接續...');
            };
        });
    }

    async function rerunPreviewReport(options) {
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
                { method: 'POST' }
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
                ? await openRerunStream({
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
