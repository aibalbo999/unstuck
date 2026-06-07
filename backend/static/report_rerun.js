(function () {
    function buttonForScope(scope, buttons) {
        return scope === 'mode_b' ? buttons.modeB : buttons.final;
    }

    function setButtonLabel(button, text) {
        const label = button ? button.querySelector('span') : null;
        if (label) label.textContent = text;
    }

    function disableButtons(buttons, disabled) {
        [buttons.final, buttons.modeB].forEach(button => {
            if (!button) return;
            button.disabled = disabled;
        });
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

        const scope = options.scope || 'final_recommendation';
        const buttons = options.buttons || {};
        const button = buttonForScope(scope, buttons);
        const originalText = button ? (button.querySelector('span')?.textContent || '局部重跑') : '局部重跑';
        disableButtons(buttons, true);
        setButtonLabel(button, '排入重跑');
        setStatus(options.statusEl, '正在建立報告重跑任務...');

        try {
            const filename = previewReport.filename;
            const res = await fetch(`/api/report/${encodeURIComponent(filename)}/rerun?scope=${encodeURIComponent(scope)}`, { method: 'POST' });
            const payload = await res.json();
            if (!res.ok || payload.success === false) {
                throw new Error(payload.error || payload.detail || `HTTP ${res.status}`);
            }

            setButtonLabel(button, '重跑中');
            const donePayload = payload.queued && payload.stream_url
                ? await openRerunStream({
                    streamUrl: payload.stream_url,
                    onStatus: message => setStatus(options.statusEl, message)
                })
                : payload;

            await options.loadHistory();
            await options.loadProviderSla();
            if (donePayload.filename) {
                options.openReport(
                    donePayload.filename,
                    previewReport.ticker,
                    donePayload.pipeline_id || previewReport.pipeline_id || 'v1'
                );
            }
            setStatus(options.statusEl, '');
            window.alert(`${payload.scope_label || donePayload.scope_label || '局部重跑'}完成：${donePayload.filename || '已產生新報告'}`);
        } catch (err) {
            console.error('Failed to rerun report', err);
            setStatus(options.statusEl, `局部重跑失敗：${err.message || err}`);
            window.alert(`局部重跑失敗：${err.message || err}`);
        } finally {
            disableButtons(buttons, false);
            setButtonLabel(button, originalText);
        }
    }

    window.StockAgentReportRerun = {
        rerunPreviewReport
    };
})();
